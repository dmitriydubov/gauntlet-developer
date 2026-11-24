"""Static checks of the Kimi adapter files against what Kimi Code 2.7.3 accepts (docs at the tag and dist/main.mjs).

  python3 -I -B check_files.py <adapter files dir> <kit dir>
Checks: config.toml and tui.toml parse as TOML; [[hooks]] use only event/matcher/command/timeout, known events,
timeout 1..600, matcher compiles; permission patterns have Kimi's Tool(arg) shape; the hook wrapper exits 0 when the
bridge is missing (python3 alone would exit 2 = block); every agent frontmatter parses as YAML (an invalid file is
skipped by Kimi with a warning), names are kebab-case and match the file, tools exist, subagents resolve; the kit's
roles load the same way; AGENTS.md stays under Kimi's 32 KB recommendation.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

import yaml

FILES, KIT = (os.path.realpath(a) for a in sys.argv[1:3])
EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest", "PermissionResult",
          "UserPromptSubmit", "UserPromptQueued", "TurnStarted", "Stop", "StopFailure", "Interrupt", "SessionStart",
          "SessionEnd", "SessionHeartbeat", "SubagentStart", "SubagentStop", "TaskStarted", "PreCompact", "PostCompact",
          "Notification"}
TOOLS = {"Read", "Write", "Edit", "Grep", "Glob", "ReadMediaFile", "Bash", "WebSearch", "FetchURL", "ExitPlanMode",
         "TodoList", "Agent", "AgentSwarm", "AskUserQuestion", "NotifyUser", "Skill", "TaskList", "TaskOutput",
         "TaskStop", "WaitFor", "CronCreate", "CronList", "CronDelete"}
failures = []


def check(ok, what):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        failures.append(what)


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end]), text[end + 5:]


cfg = tomllib.load(open(os.path.join(FILES, "user", "config.toml"), "rb"))
tomllib.load(open(os.path.join(FILES, "user", "tui.toml"), "rb"))
check(True, "config.toml and tui.toml parse")
for hook in cfg["hooks"]:
    check(set(hook) <= {"event", "matcher", "command", "timeout"} and hook["event"] in EVENTS
          and 1 <= hook.get("timeout", 30) <= 600, f"hook {hook['event']}: fields, event name, timeout {hook.get('timeout')}")
    if "matcher" in hook:
        re.compile(hook["matcher"])
for rule in cfg["permission"]["rules"]:
    p = rule["pattern"]
    check(rule["decision"] in ("allow", "deny", "ask") and re.fullmatch(r"[A-Za-z*]+(\(.+\))?", p) is not None,
          f"permission {rule['decision']} {p}")

tmp = tempfile.mkdtemp()
try:
    env = dict(os.environ, KIMI_CODE_HOME=os.path.join(tmp, "kh"), HOME=tmp)
    os.makedirs(env["KIMI_CODE_HOME"])
    event = json.dumps({"hook_event_name": "PreToolUse", "cwd": tmp, "tool_name": "Write", "tool_input": {"path": "x"}})
    for hook in cfg["hooks"]:
        proc = subprocess.run(["sh", "-c", hook["command"]], input=event, capture_output=True, text=True, env=env, cwd=tmp)
        check(proc.returncode == 0 and not proc.stdout, f"hook {hook['event']} wrapper without the bridge exits 0")
    os.makedirs(os.path.join(env["KIMI_CODE_HOME"], "hooks"))
    shutil.copy(os.path.join(FILES, "kimi_hooks.py"), os.path.join(env["KIMI_CODE_HOME"], "hooks", "kimi_hooks.py"))
    for hook in cfg["hooks"]:
        proc = subprocess.run(["sh", "-c", hook["command"]], input=event, capture_output=True, text=True, env=env, cwd=tmp)
        check(proc.returncode == 0, f"hook {hook['event']} wrapper with the bridge outside a listed checkout exits 0")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

ours = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(FILES, "agents", "*.md"))}
roles = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(KIT, ".claude", "agents", "*.md"))}
for path in sorted(glob.glob(os.path.join(FILES, "agents", "*.md")) + glob.glob(os.path.join(KIT, ".claude", "agents", "*.md"))):
    name = os.path.basename(path)[:-3]
    try:
        data, body = frontmatter(path)
    except (ValueError, yaml.YAMLError) as e:
        check(False, f"agent {name}: frontmatter does not parse ({e})")
        continue
    tools = data.get("tools")
    tools = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else (tools or [])
    subagents = data.get("subagents") or []
    subagents = [s.strip() for s in subagents.split(",")] if isinstance(subagents, str) else subagents
    check(data.get("name", name) == name and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) is not None
          and bool(data.get("description")) and all(t in TOOLS for t in tools)
          and all(s in ours | roles for s in subagents),
          f"agent {name}: name, description, tools {tools or 'all'}, subagents {subagents or 'default'}")
    if data.get("subagents"):
        check("${base_prompt}" in body, f"agent {name}: main agent keeps the default prompt (${{base_prompt}})")

size = os.path.getsize(os.path.join(FILES, "AGENTS.md"))
check(size < 32768, f"AGENTS.md {size} bytes < 32768 (Kimi warns above)")
print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
