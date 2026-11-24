"""Synthetic check of grok_hooks.py against the kit's own guard.py and stop_gate.py.

Events follow the Grok Build hook envelope: camelCase keys (xai-grok-hooks/src/event.rs, source 1.0.45) plus the
snake_case aliases that 1.0.92 sends (session_id, tool_name, tool_input, stop_hook_active, last_assistant_message).
Usage: python3 -I test_grok_hooks.py <fixture repo with gauntlet/ and gauntlet/adapters/grok/grok_hooks.py>
"""
import json
import os
import subprocess
import sys

PROJ = os.path.abspath(sys.argv[1])
GUARD = os.path.join(PROJ, "gauntlet", "hooks", "guard.py")
BRIDGE = os.path.join(PROJ, "gauntlet", "adapters", "grok", "grok_hooks.py")
GROK_HOME = os.path.join(os.path.dirname(PROJ), "grok-home")
os.makedirs(GROK_HOME, exist_ok=True)
ENV = dict(os.environ, CLAUDE_PROJECT_DIR=PROJ, GROK_WORKSPACE_ROOT=PROJ, GROK_HOME=GROK_HOME)
ENV.pop("GAUNTLET_GUARD", None)
ENV.pop("GAUNTLET_STOP_HOOK", None)
failures = 0


def envelope(event, **payload):
    base = {"hookEventName": event, "sessionId": "grok-session-1", "cwd": PROJ, "workspaceRoot": PROJ,
            "timestamp": "2026-11-24T06:00:00Z", "permissionMode": "bypassPermissions"}
    base.update(payload)
    for camel, snake in (("sessionId", "session_id"), ("permissionMode", "permission_mode"), ("toolName", "tool_name"),
                         ("toolInput", "tool_input"), ("toolUseId", "tool_use_id"),
                         ("stopHookActive", "stop_hook_active"), ("lastAssistantMessage", "last_assistant_message")):
        if camel in base:
            base.setdefault(snake, base[camel])
    base["hook_event_name"] = {"pre_tool_use": "PreToolUse", "stop": "Stop", "subagent_stop": "SubagentStop",
                               "session_start": "SessionStart"}[event]
    return base


def pre(tool, tool_input, subagent=None):
    extra = {"toolName": tool, "toolUseId": "call-1", "toolInput": tool_input, "toolInputTruncated": False}
    if subagent:
        extra["subagentType"] = subagent
    return envelope("pre_tool_use", **extra)


def run(cmd, event):
    proc = subprocess.run(cmd, input=json.dumps(event), capture_output=True, text=True, cwd=PROJ, env=ENV, timeout=600)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def decision(out):
    if not out:
        return "allow"
    try:
        doc = json.loads(out)
    except ValueError:
        return "allow (non-JSON: " + out[:80] + ")"
    hso = doc.get("hookSpecificOutput") or {}
    return hso.get("permissionDecision") or doc.get("decision") or ("message" if "systemMessage" in doc else "allow")


def check(label, got, want):
    global failures
    ok = got == want
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got}" + ("" if ok else f" (want {want})"))


cases = [
    # label, event, direct guard.py (what .claude/settings.json gives Grok today), through the bridge
    ("search_replace gauntlet/config/gauntlet.properties (main)",
     pre("search_replace", {"file_path": "gauntlet/config/gauntlet.properties", "old_string": "a", "new_string": "b"}),
     "allow", "deny"),
    ("write .claude/settings.json (main)",
     pre("write", {"file_path": os.path.join(PROJ, ".claude/settings.json"), "content": "{}"}), "allow", "deny"),
    ("run_terminal_command: echo >> gauntlet/config/gauntlet.properties (main)",
     pre("run_terminal_command", {"command": "echo x >> gauntlet/config/gauntlet.properties",
                                  "description": "edit"}), "allow", "deny"),
    ("run_terminal_command: git push --force (main)",
     pre("run_terminal_command", {"command": "git push --force origin step-1", "description": "push"}),
     "allow", "deny"),
    ("search_replace src/main App.java (main)",
     pre("search_replace", {"file_path": "src/main/java/com/example/service/App.java", "old_string": "{}",
                            "new_string": "{ }"}), "allow", "allow"),
    ("run_terminal_command: touch src/x (reviewer)",
     pre("run_terminal_command", {"command": "touch src/x", "description": "x"}, "reviewer"), "allow", "deny"),
    ("run_terminal_command: ./gradlew gauntletFast (reviewer)",
     pre("run_terminal_command", {"command": "./gradlew gauntletFast --continue", "description": "gates"}, "reviewer"),
     "allow", "allow"),
    ("search_replace src/main (hardener)",
     pre("search_replace", {"file_path": "src/main/java/com/example/service/App.java", "old_string": "{}",
                            "new_string": "{ }"}, "hardener"), "allow", "deny"),
    ("search_replace src/test (hardener)",
     pre("search_replace", {"file_path": "src/test/java/com/example/service/AppTest.java", "old_string": "{}",
                            "new_string": "{ }"}, "hardener"), "allow", "allow"),
    ("write features (specifier, before the spec commit)",
     pre("write", {"file_path": "src/acceptanceTest/resources/features/b.feature", "content": "# language: ru\n"},
         "specifier"), "allow", "allow"),
    ("write src/main (specifier)",
     pre("write", {"file_path": "src/main/java/com/example/service/B.java", "content": "class B {}"}, "specifier"),
     "allow", "deny"),
    ("write features (main)",
     pre("write", {"file_path": "src/acceptanceTest/resources/features/c.feature", "content": "x"}), "allow", "deny"),
    ("run_terminal_command: git commit (card gauntlet-card-map)",
     pre("run_terminal_command", {"command": "git commit -m x", "description": "x"}, "gauntlet-card-map"),
     "allow", "deny"),
    ("search_replace AGENTS.md (main)",
     pre("search_replace", {"file_path": "AGENTS.md", "old_string": "#", "new_string": "##"}), "allow", "deny"),
    ("run_terminal_command: echo > .grok/hooks/gauntlet.json (main)",
     pre("run_terminal_command", {"command": "echo '{}' > .grok/hooks/gauntlet.json", "description": "x"}),
     "allow", "deny"),
    ("write $GROK_HOME/config.toml (main)",
     pre("write", {"file_path": os.path.join(GROK_HOME, "config.toml"), "content": "[compat.claude]\nhooks=false\n"}),
     "allow", "deny"),
    ("write $GROK_HOME/sessions/x/plan.md (plan file, main)",
     pre("write", {"file_path": os.path.join(GROK_HOME, "sessions", "x", "plan.md"), "content": "plan"}),
     "allow", "allow"),
    ("apply_patch Update File gauntlet/hooks/guard.py (main)",
     pre("apply_patch", {"patch": "*** Begin Patch\n*** Update File: gauntlet/hooks/guard.py\n@@\n-a\n+b\n"
                                  "*** End Patch\n"}), "allow", "deny"),
    ("apply_patch Add File src/main/.../C.java (main)",
     pre("apply_patch", {"patch": "*** Begin Patch\n*** Add File: src/main/java/com/example/service/C.java\n"
                                  "+class C {}\n*** End Patch\n"}), "allow", "allow"),
    ("hashline_edit gauntlet/README.md (main)",
     pre("hashline_edit", {"file_path": "gauntlet/README.md", "edits": [{"op": "write", "content": "x"}]}),
     "allow", "deny"),
    ("read_file gauntlet/CLAUDE.md (main)",
     pre("read_file", {"path": "gauntlet/CLAUDE.md"}), "allow", "allow"),
]

print("== PreToolUse: kit guard.py on the Grok event as it is, then through grok_hooks.py guard")
for label, event, want_direct, want_bridge in cases:
    check("direct  " + label, decision(run([sys.executable, "-B", GUARD], event)[1]), want_direct)
    check("bridge  " + label, decision(run([sys.executable, "-B", BRIDGE, "guard"], event)[1]), want_bridge)

print("== the same events with the kit's own tool names (Claude Code), to show the kit's guard itself works")
claude_case = pre("Edit", {"file_path": "gauntlet/config/gauntlet.properties", "old_string": "a", "new_string": "b"})
check("direct  Edit gauntlet/config/gauntlet.properties", decision(run([sys.executable, "-B", GUARD], claude_case)[1]),
      "deny")

print("== git state after the guard runs: no __pycache__ under gauntlet/")
pyc = [os.path.join(d, n) for d, _, ns in os.walk(os.path.join(PROJ, "gauntlet")) for n in ns if n.endswith(".pyc")]
check("no .pyc written into gauntlet/", len(pyc), 0)

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
