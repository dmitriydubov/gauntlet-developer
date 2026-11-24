"""Synthetic check of qwen_hooks.py (PreToolUse, SubagentStart) against the kit's own guard.py.

Events follow Qwen Code 0.28.4 (docs/users/features/hooks.md at tag v0.28.4): common fields session_id,
transcript_path, cwd, hook_event_name, timestamp, permission_mode, agent_id only inside a subagent; PreToolUse adds
tool_name (runtime id), tool_input, tool_use_id, tool_call_id; SubagentStart adds agent_id and agent_type. The verdict
is read the way the package reads a command hook (commandResult, convertPlainTextToHookOutput, isDenied): exit 2 =
deny with stderr as the reason; exit 0 with a JSON object = its hookSpecificOutput.permissionDecision; anything else
lets the call through.
Usage: python3 -I test_qwen_guard.py <fixture repo with gauntlet/ and gauntlet/adapters/qwen/qwen_hooks.py>
"""
import json
import os
import subprocess
import sys

PROJ = os.path.abspath(sys.argv[1])
GUARD = os.path.join(PROJ, "gauntlet", "hooks", "guard.py")
SHIM = os.path.join(PROJ, "gauntlet", "adapters", "qwen", "qwen_hooks.py")
HOME = os.path.join(os.path.dirname(PROJ), "home")
os.makedirs(os.path.join(HOME, ".qwen"), exist_ok=True)
ENV = dict(os.environ, QWEN_PROJECT_DIR=PROJ, CLAUDE_PROJECT_DIR=PROJ, GEMINI_PROJECT_DIR=PROJ, HOME=HOME)
for name in ("GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK", "QWEN_HOME"):
    ENV.pop(name, None)
SESSION = "8d0c1f9e-qwen-session"
failures = 0


def base(event, **extra):
    doc = {"session_id": SESSION, "transcript_path": os.path.join(HOME, ".qwen", "t.jsonl"), "cwd": PROJ,
           "hook_event_name": event, "timestamp": "2026-11-24T07:00:00.000Z", "permission_mode": "auto_edit"}
    doc.update(extra)
    return doc


def pre(tool, tool_input, agent_id=None):
    extra = {"tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_1764000000000_abc", "tool_call_id": "call_1"}
    if agent_id:
        extra["agent_id"] = agent_id
    return base("PreToolUse", **extra)


def run(cmd, event):
    proc = subprocess.run(cmd, input=json.dumps(event), capture_output=True, text=True, cwd=PROJ, env=ENV, timeout=600)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def qwen_verdict(code, out, err):
    if code == 2:
        return "deny"
    if code != 0 or not out:
        return "allow"
    try:
        doc = json.loads(out)
    except ValueError:
        return "allow"
    hso = doc.get("hookSpecificOutput") or {}
    decision = hso.get("permissionDecision") or doc.get("decision")
    return "deny" if decision in ("deny", "block") else "allow"


def check(label, got, want):
    global failures
    ok = got == want
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got}" + ("" if ok else f" (want {want})"))


def start(agent_id, agent_type):
    code, out, err = run([sys.executable, "-B", SHIM, "subagent-start"],
                         base("SubagentStart", agent_id=agent_id, agent_type=agent_type))
    check(f"SubagentStart {agent_type} recorded silently", (code, out), (0, ""))


app = os.path.join(PROJ, "src/main/java/com/example/service/App.java")
test = os.path.join(PROJ, "src/test/java/com/example/service/AppTest.java")
feature = os.path.join(PROJ, "src/acceptanceTest/resources/features/a.feature")

start("specifier-call_00_spec", "specifier")
start("hardener-call_01_hard", "hardener")
start("reviewer-call_02_rev", "reviewer")
start("precheck-mapper-call_03_map", "precheck-mapper")
start("x7f3a2c1", "hardener")                    # an agent_id without the name prefix: only the record knows the role
start("specifier-lookalike-call_05", "specifier-lookalike")   # a name that starts like a kit role: the record wins

cases = [
    # label, event, verdict of guard.py called directly (the kit's .claude/settings.json pointed at Qwen), via the shim
    ("write_file gauntlet/config/gauntlet.properties (main)",
     pre("write_file", {"file_path": os.path.join(PROJ, "gauntlet/config/gauntlet.properties"), "content": "x"}),
     "allow", "deny"),
    ("edit .qwen/settings.json (main)",
     pre("edit", {"file_path": os.path.join(PROJ, ".qwen/settings.json"), "old_string": "{}", "new_string": "{1}"}),
     "allow", "deny"),
    ("write_file QWEN.md (main)", pre("write_file", {"file_path": os.path.join(PROJ, "QWEN.md"), "content": "x"}),
     "allow", "deny"),
    ("write_file ~/.qwen/settings.json (main)",
     pre("write_file", {"file_path": os.path.join(HOME, ".qwen", "settings.json"), "content": "{}"}), "allow", "deny"),
    ("run_shell_command echo >> gauntlet/config/gauntlet.properties (main)",
     pre("run_shell_command", {"command": "echo x >> gauntlet/config/gauntlet.properties", "is_background": False}),
     "allow", "deny"),
    ("run_shell_command rm config/gauntlet.properties, directory=gauntlet (main)",
     pre("run_shell_command", {"command": "rm config/gauntlet.properties", "directory": os.path.join(PROJ, "gauntlet")}),
     "allow", "deny"),
    ("run_shell_command git push --force (main)",
     pre("run_shell_command", {"command": "git push --force origin step-1"}), "allow", "deny"),
    ("run_shell_command gh pr merge (main)", pre("run_shell_command", {"command": "gh pr merge 7 --squash"}),
     "allow", "deny"),
    ("monitor tail >> .qwen/settings.json (main)",
     pre("monitor", {"command": "tail -f /tmp/x >> .qwen/settings.json"}), "allow", "deny"),
    ("run_shell_command QWEN_CODE_SAFE_MODE=1 qwen -p (main)",
     pre("run_shell_command", {"command": "QWEN_CODE_SAFE_MODE=1 qwen -p 'edit gauntlet'"}), "allow", "deny"),
    ("run_shell_command qwen --bare -p (main)",
     pre("run_shell_command", {"command": "qwen --bare -p 'hi'"}), "allow", "deny"),
    ("run_shell_command git clone --bare (main, not a hook switch)",
     pre("run_shell_command", {"command": "git clone --bare https://example.com/r.git /tmp/r.git"}), "allow", "allow"),
    ("edit src/main App.java (main)",
     pre("edit", {"file_path": app, "old_string": "{}", "new_string": "{ }"}), "allow", "allow"),
    ("run_shell_command ./gradlew gauntletFast > build/fast.log (main)",
     pre("run_shell_command", {"command": "./gradlew gauntletFast --continue --console=plain > build/fast.log 2>&1"}),
     "allow", "allow"),
    ("write_file feature (main: only the specifier writes the spec)",
     pre("write_file", {"file_path": feature, "content": "x"}), "allow", "deny"),
    ("write_file feature (specifier, recorded at SubagentStart)",
     pre("write_file", {"file_path": feature, "content": "x"}, "specifier-call_00_spec"), "allow", "allow"),
    ("write_file src/main (specifier)",
     pre("write_file", {"file_path": app, "content": "x"}, "specifier-call_00_spec"), "allow", "deny"),
    ("write_file src/test (hardener)",
     pre("write_file", {"file_path": test, "content": "x"}, "hardener-call_01_hard"), "allow", "allow"),
    ("edit src/main (hardener)",
     pre("edit", {"file_path": app, "old_string": "{}", "new_string": "{ }"}, "hardener-call_01_hard"), "allow", "deny"),
    ("run_shell_command sed -i src/main (hardener)",
     pre("run_shell_command", {"command": "sed -i 's/a/b/' src/main/java/com/example/service/App.java"},
         "hardener-call_01_hard"), "allow", "deny"),
    ("edit src/test (hardener, no SubagentStart record: agent_id prefix)",
     pre("edit", {"file_path": test, "old_string": "{}", "new_string": "{ }"}, "hardener-call_09_new"), "allow", "allow"),
    ("edit src/main (hardener, no SubagentStart record: agent_id prefix)",
     pre("edit", {"file_path": app, "old_string": "{}", "new_string": "{ }"}, "hardener-call_09_new"), "allow", "deny"),
    ("write_file src/test (reviewer)",
     pre("write_file", {"file_path": test, "content": "x"}, "reviewer-call_02_rev"), "allow", "deny"),
    ("run_shell_command git diff (reviewer)",
     pre("run_shell_command", {"command": "git diff $(git merge-base origin/main HEAD)"}, "reviewer-call_02_rev"),
     "allow", "allow"),
    ("run_shell_command git commit (reviewer)",
     pre("run_shell_command", {"command": "git commit -am fix"}, "reviewer-call_02_rev"), "allow", "deny"),
    ("run_shell_command ./gradlew gauntletFast (reviewer)",
     pre("run_shell_command", {"command": "./gradlew gauntletFast --continue"}, "reviewer-call_02_rev"),
     "allow", "allow"),
    ("write_file src/main (precheck-mapper card: read-only)",
     pre("write_file", {"file_path": app, "content": "x"}, "precheck-mapper-call_03_map"), "allow", "deny"),
    ("run_shell_command git grep (precheck-mapper card)",
     pre("run_shell_command", {"command": "git grep -n 'class App' -- src"}, "precheck-mapper-call_03_map"),
     "allow", "allow"),
    ("write_file src/test (hardener known only from the SubagentStart record)",
     pre("write_file", {"file_path": test, "content": "x"}, "x7f3a2c1"), "allow", "allow"),
    ("write_file src/main (hardener known only from the SubagentStart record)",
     pre("write_file", {"file_path": app, "content": "x"}, "x7f3a2c1"), "allow", "deny"),
    ("write_file feature (agent 'specifier-lookalike': the record wins over the prefix)",
     pre("write_file", {"file_path": feature, "content": "x"}, "specifier-lookalike-call_05"), "allow", "deny"),
    ("edit src/main (unknown subagent, no record: read-only)",
     pre("edit", {"file_path": app, "old_string": "{}", "new_string": "{ }"}, "general-purpose-call_04"), "allow", "deny"),
    ("read_file gauntlet/CLAUDE.md (main: not a write)",
     pre("read_file", {"file_path": os.path.join(PROJ, "gauntlet/CLAUDE.md")}), "allow", "allow"),
]

for label, event, direct_want, shim_want in cases:
    check("direct guard.py | " + label, qwen_verdict(*run([sys.executable, "-B", GUARD], event)), direct_want)
    check("qwen_hooks.py   | " + label, qwen_verdict(*run([sys.executable, "-B", SHIM, "pre-tool"], event)), shim_want)

# the specification committed on the branch (= approved): frozen for every agent, the specifier included
subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "spec: example", "--allow-empty"],
               cwd=PROJ, check=True)
with open(feature, "a", encoding="utf-8") as f:
    f.write("  Сценарий: новый\n")
subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "spec: example"], cwd=PROJ,
               check=True)
event = pre("write_file", {"file_path": feature, "content": "x"}, "specifier-call_00_spec")
check("qwen_hooks.py   | write_file feature after the spec commit (specifier: frozen)",
      qwen_verdict(*run([sys.executable, "-B", SHIM, "pre-tool"], event)), "deny")

code, out, err = run([sys.executable, "-B", SHIM, "pre-tool"], {"not": "a tool event"})
check("qwen_hooks.py   | malformed event fails open", (code, out), (0, ""))
proc = subprocess.run([sys.executable, "-B", SHIM, "selftest"], capture_output=True, text=True, cwd=PROJ, env=ENV)
check("qwen_hooks.py   | selftest", (proc.returncode, proc.stdout.split(":")[1].strip()[:2]), (0, "ok"))
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
