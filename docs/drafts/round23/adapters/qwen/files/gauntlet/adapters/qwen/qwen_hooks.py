#!/usr/bin/env python3
"""Qwen Code hooks -> the gauntlet's own guard.py, unchanged.

Part of the Qwen Code adapter. Proposed place: gauntlet/adapters/qwen/qwen_hooks.py, added by the human like any kit
change, so the CI check `gauntlet kit unchanged` covers it with the rest of gauntlet/. The Stop, SubagentStop and
SessionStart hooks need no translation: Qwen Code calls gauntlet/hooks/stop_gate.py and session_start.sh directly
(.qwen/settings.json). Only two events need this script:

  qwen_hooks.py subagent-start   SubagentStart: remember which agent (agent_type) an agent_id belongs to
  qwen_hooks.py pre-tool         PreToolUse: translate the call and ask guard.py
  qwen_hooks.py selftest         what this script relies on in guard.py is still there

Why guard.py alone is not enough under Qwen Code 0.28.4 (docs/users/features/hooks.md at tag v0.28.4 and the package
@qwen-code/qwen-code@0.28.4, read 2026-11-24):
  - tool events carry the runtime tool id in tool_name (write_file, edit, notebook_edit, run_shell_command, monitor),
    not Claude Code's Write/Edit/Bash, so guard.py sees no tool it knows and allows every call;
  - agent_type is reported on SessionStart, SubagentStart and SubagentStop only; a tool call made inside a subagent
    carries agent_id and no agent_type, so guard.py would judge every subagent as the main agent: the specifier could
    not write the specification and the reviewer and hardener would not be limited.
What makes the translation possible:
  - a named subagent's agent_id is "<agent name>-<call id>" and its SubagentStart event carries the same agent_id with
    agent_type = the agent's name (package: `hookOpts={agentId:`${subagentConfig.name}-${agentIdSuffix}`,
    agentType:subagentConfig.name, ...}`; tool calls run inside runWithAgentContext(hookOpts.agentId, ...));
  - the deny answer Qwen Code reads is the one guard.py already prints: {"hookSpecificOutput": {"hookEventName":
    "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": ...}}; a hook that fails or prints nothing
    lets the call through (fail-open, like guard.py itself).

Roles: no agent_id = the main agent (the coder); specifier, hardener and reviewer keep the kit's scopes; every other
subagent (the pre-check cards, Explore, general-purpose, fork) is read-only, as core.md rule 1.6 asks of them.
The human's switch is the kit's: GAUNTLET_GUARD=off in the environment Qwen Code starts with turns this check off,
as it turns off guard.py (guard.py main(); this script calls guard.py's functions, not its main(), so it checks the
switch itself). Qwen Code also takes variables from .env files at start-up (the project's first .qwen/.env or .env,
then ~/.qwen/.env and ~/.env; package findEnvFiles) and hands them to every hook: ~/.env is therefore Qwen Code's
configuration like ~/.qwen, and the project's .env is shadowed by a human-owned .qwen/.env (qwen.md, A.2).
Not run against a live Qwen Code: check it with the smoke test of the adapter (qwen.md, section A.6).
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
KIT_HOOKS = os.path.realpath(os.path.join(HERE, "..", "..", "hooks"))
# Qwen Code's own configuration in the project is human-owned like .claude/ and CLAUDE.md: settings, hooks, agents,
# rules, skills and fork profiles (.qwen/), the context files it loads by default (QWEN.md, AGENTS.md) and the ignore
# files that decide what its search tools see.
EXTRA_OWNED = (".qwen/", "QWEN.md", "AGENTS.md", ".qwenignore", ".agentignore", ".aiignore")
WRITE_TOOLS = {"write_file": "Write", "edit": "Edit", "notebook_edit": "NotebookEdit"}
SHELL_TOOLS = ("run_shell_command", "monitor")
KIT_ROLES = ("specifier", "hardener", "reviewer")
# Turning Qwen Code's hooks off is the human's, like GAUNTLET_GUARD=off (guard.py HOOK_SWITCH): the variables and
# flags that disable every hook of a Qwen Code process (hooks.md "A hook does not fire", item 4; stop cap: "Stop").
QWEN_HOOK_SWITCH = re.compile(
    r"(?:^|[\s;&|(])(?:export\s+)?QWEN_CODE_(?:SAFE_MODE|SIMPLE|STOP_HOOK_BLOCK_CAP)="
    r"|(?:^|[\s;&|(])export\s+QWEN_CODE_(?:SAFE_MODE|SIMPLE|STOP_HOOK_BLOCK_CAP)\b"
    r"|(?:^|[\s;&|(/])qwen\b[^\n;&|]*\s--(?:safe-mode|bare)\b")


def main(argv):
    command = argv[0] if argv else ""
    if command == "selftest":
        return selftest()
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0
    try:
        if command == "subagent-start":
            subagent_start(event)
        elif command == "pre-tool":
            if os.environ.get("GAUNTLET_GUARD", "").lower() == "off":     # the human's switch, as in guard.py main()
                return 0
            reason = pre_tool(event)
            if reason:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "[gauntlet guard] " + reason}}))
    except Exception as error:       # fail-open like guard.py; exit 1 is Qwen Code's non-blocking error (debug log)
        sys.stderr.write(f"[gauntlet qwen] {command} failed: {error!r}\n")
        return 1
    return 0


def project_of(event):
    # Qwen Code sets QWEN_PROJECT_DIR = CLAUDE_PROJECT_DIR = the event's cwd for command hooks (package: commandInvocation)
    return event.get("cwd") or os.environ.get("QWEN_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


# ----------------------------------------------------------------------------- which agent made the call

def state_dir(project):
    """The directory stop_gate.py keeps its state in (.git/gauntlet-hook): under .git/, which the guard closes to
    every agent, so the agent cannot write itself a role."""
    try:
        out = subprocess.run(["git", "rev-parse", "--git-path", "gauntlet-hook"], cwd=project,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    path = out if os.path.isabs(out) else os.path.join(project, out)
    try:
        os.makedirs(os.path.join(path, "qwen-agents"), exist_ok=True)
    except OSError:
        return None
    return path


def record_path(state, event, agent_id):
    session = hashlib.sha1(str(event.get("session_id", "")).encode("utf-8")).hexdigest()[:16]
    return os.path.join(state, "qwen-agents", session + "-" + hashlib.sha1(str(agent_id).encode("utf-8")).hexdigest())


def subagent_start(event):
    agent_id, agent_type = event.get("agent_id"), event.get("agent_type")
    if not agent_id or not agent_type:
        return
    state = state_dir(project_of(event))
    if state:
        with open(record_path(state, event, agent_id), "w", encoding="utf-8") as f:
            f.write(str(agent_type))


def agent_of(event, project):
    """main, a kit role, or the name of another subagent. Recorded at SubagentStart; if that record is missing, the
    agent_id prefix (the agent's name, then '-') names a kit role; anything else is an unnamed subagent."""
    agent_id = event.get("agent_id")
    if not agent_id:
        return "main"
    agent_id = str(agent_id)
    state = state_dir(project)
    if state:
        try:
            with open(record_path(state, event, agent_id), encoding="utf-8") as f:
                recorded = f.read().strip()
            if recorded:
                return recorded if recorded != "main" else "subagent"     # a subagent never gets the coder's rights
        except OSError:
            pass
    for role in sorted(KIT_ROLES, key=len, reverse=True):
        if agent_id.startswith(role + "-"):
            return role
    return "subagent"


# ----------------------------------------------------------------------------- guard.py, with Qwen Code's paths

def qwen_config_paths():
    """Qwen Code's user, system and relocated configuration: settings, hooks, hook approvals, trusted folders, agents,
    memory (settings.md "Settings files"; QWEN_HOME in sandbox.md and cross-session-protocol.md; the approvals file
    QWEN_CODE_HOOK_APPROVALS_PATH in the package, getHookApprovalsPath), and ~/.env, which Qwen Code loads at every
    start-up and hands to every hook, outside the project-hook approval (package: findEnvFiles, pushHomeCandidates,
    readProjectEnvFiles skips user-level files)."""
    paths = [os.path.expanduser("~/.qwen"), "/etc/qwen-code", os.path.expanduser("~/.env")]
    for var in ("QWEN_HOME", "QWEN_CODE_SYSTEM_SETTINGS_PATH", "QWEN_CODE_SYSTEM_DEFAULTS_PATH",
                "QWEN_CODE_HOOK_APPROVALS_PATH"):
        if os.environ.get(var):
            paths.append(os.environ[var])
    return [os.path.realpath(p) for p in paths]


def load_guard():
    spec = importlib.util.spec_from_file_location("gauntlet_guard", os.path.join(KIT_HOOKS, "guard.py"))
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.HUMAN_OWNED = tuple(guard.HUMAN_OWNED) + tuple(p for p in EXTRA_OWNED if p not in guard.HUMAN_OWNED)
    kit_user_config = guard.user_config_violation

    def user_config_violation(path):
        reason = kit_user_config(path)
        if reason or not path:
            return reason
        expanded = os.path.expanduser(str(path))
        if not os.path.isabs(expanded):
            return None
        absolute = os.path.realpath(expanded)
        for owned in qwen_config_paths():
            if absolute == owned or absolute.startswith(owned + os.sep):
                return (f"{owned} is Qwen Code's own configuration (settings, hooks, hook approvals, agents, memory, "
                        f"start-up environment); it could switch the gauntlet off. Do not touch it.")
        return None

    guard.user_config_violation = user_config_violation
    kit_scope = guard.Context.role_scope

    def role_scope(self, agent):
        scope = kit_scope(self, agent)
        if scope is None and agent != "main":
            return ()        # a subagent outside the kit's writing roles only reads (core.md, rule 1.6)
        return scope

    guard.Context.role_scope = role_scope
    return guard


def shell_cwd(params, event, project):
    directory = params.get("directory")
    if isinstance(directory, str) and directory.strip():
        directory = os.path.expanduser(directory.strip())
        # the package documents an absolute path, the user docs a path relative to the project root: take both
        return directory if os.path.isabs(directory) else os.path.join(project, directory)
    return event.get("cwd") or project


def pre_tool(event):
    tool = event.get("tool_name") or ""
    params = event.get("tool_input") or {}
    if not isinstance(params, dict) or (tool not in WRITE_TOOLS and tool not in SHELL_TOOLS):
        return None
    project = project_of(event)
    guard = load_guard()
    agent = agent_of(event, project)
    ctx = guard.Context(project)
    if tool in WRITE_TOOLS:
        path = params.get("file_path") or params.get("notebook_path") or ""
        return guard.user_config_violation(path) or guard.path_violation(agent, ctx.relative(path), ctx)
    command = str(params.get("command") or "")
    if QWEN_HOOK_SWITCH.search(command):
        return ("Switching Qwen Code's hooks off (QWEN_CODE_SAFE_MODE, QWEN_CODE_SIMPLE, --safe-mode, --bare, the "
                "Stop hook cap) is reserved for the human.")
    return guard.bash_violation(agent, command, ctx, shell_cwd(params, event, project))


# ----------------------------------------------------------------------------- selftest

def selftest():
    """The names this script patches or calls in guard.py, so a kit update that renames one fails loudly here
    instead of silently allowing every call."""
    guard = load_guard()
    missing = [name for name in ("HUMAN_OWNED", "user_config_violation", "path_violation", "bash_violation", "Context")
               if not hasattr(guard, name)]
    if not missing and not hasattr(guard.Context, "role_scope"):
        missing.append("Context.role_scope")
    if missing:
        print("qwen_hooks selftest: guard.py no longer has " + ", ".join(missing))
        return 1
    print("qwen_hooks selftest: ok (" + ", ".join(EXTRA_OWNED) + " added to the human-owned paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
