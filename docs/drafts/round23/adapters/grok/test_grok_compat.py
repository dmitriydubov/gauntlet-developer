"""What the kit's stop_gate.py does when Grok runs it straight from .claude/settings.json (no bridge).

Grok's SubagentStop carries subagentId, not agent_id, so the hardener's green mutationGate is recorded under the main
agent's stop mark; the main agent's next Stop on the same code then passes without running gauntletFast. Through the
bridge the two marks stay apart and gauntletFast runs.
Usage: python3 -I test_grok_compat.py <fresh fixture repo>
"""
import json
import os
import stat
import subprocess
import sys

PROJ = os.path.abspath(sys.argv[1])
GATE = os.path.join(PROJ, "gauntlet", "hooks", "stop_gate.py")
BRIDGE = os.path.join(PROJ, "gauntlet", "adapters", "grok", "grok_hooks.py")
ENV = dict(os.environ, CLAUDE_PROJECT_DIR=PROJ)
for name in ("GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK", "CLAUDE_CODE_REMOTE"):
    ENV.pop(name, None)
failures = 0

with open(os.path.join(PROJ, "gradlew"), "w") as f:
    f.write("#!/bin/sh\ntask=$1\necho \"$task\" >> \"$(dirname \"$0\")/.fake-gradle-calls\"\n"
            "if [ \"$task\" = gauntletFast ]; then for t in gauntletScope integrityCheck checkstyleGate pmdGate test "
            "archTest testCensus acceptanceTest acceptanceCheck jacocoTestReport crapGate cpdReport dryGate "
            "gauntletFast; do echo \"> Task :$t\"; done; echo 'CRAP FAIL com.example.service.App#run 12.0'; "
            "echo 'BUILD FAILED'; exit 1; fi\n"
            "if [ \"$task\" = mutationGate ]; then for t in gauntletScope pitest pitSummary mutationGate; do "
            "echo \"> Task :$t\"; done; echo 'BUILD SUCCESSFUL'; exit 0; fi\n")
os.chmod(os.path.join(PROJ, "gradlew"), stat.S_IRWXU)
subprocess.run(["git", "update-index", "--add", "--chmod=+x", "gradlew"], cwd=PROJ, capture_output=True)
subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "fake gradle", "--", "gradlew"],
               cwd=PROJ, capture_output=True)


def event(pascal, camel, **payload):
    base = {"hookEventName": camel, "hook_event_name": pascal, "sessionId": "s-compat", "session_id": "s-compat",
            "cwd": PROJ, "workspaceRoot": PROJ, "timestamp": "2026-11-24T06:00:00Z"}
    base.update(payload)
    if "stopHookActive" in base:
        base["stop_hook_active"] = base["stopHookActive"]
    return base


def run(cmd, ev):
    p = subprocess.run(cmd, input=json.dumps(ev), capture_output=True, text=True, cwd=PROJ, env=ENV, timeout=300)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def calls():
    path = os.path.join(PROJ, ".fake-gradle-calls")
    return open(path).read().split() if os.path.exists(path) else []


def check(label, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + (f": {detail}" if detail else ""))


def scenario(cmd_stop, cmd_sub, label):
    run(["bash", os.path.join(PROJ, "gauntlet", "hooks", "session_start.sh")],
        event("SessionStart", "session_start", source="startup"))
    with open(os.path.join(PROJ, "src/main/java/com/example/service/App.java"), "a") as f:
        f.write(f"// {label}\n")
    sub = event("SubagentStop", "subagent_stop", phase="gate", subagentId=f"hardener-{label}",
                subagentType="hardener", stopHookActive=False, lastAssistantMessage="done")
    code_sub, _, _ = run(cmd_sub + ["--task", "mutationGate", "--max-attempts", "2", "--timeout", "120"], sub)
    before = calls().count("gauntletFast")
    stop = event("Stop", "stop", reason="end_turn", stopHookActive=False, lastAssistantMessage="done",
                 backgroundTasks=[], sessionCrons=[])
    code, out, err = run(cmd_stop + ["--task", "gauntletFast", "--max-attempts", "3", "--timeout", "120"], stop)
    ran = calls().count("gauntletFast") > before
    return code_sub, code, ran


print("== kit's stop_gate.py run straight from .claude/settings.json (Grok compatibility mode)")
code_sub, code, ran = scenario([sys.executable, "-B", GATE], [sys.executable, "-B", GATE], "compat")
check("hardener's mutationGate green", code_sub == 0)
check("main Stop on the same code: 4.6 checks task-specific green_file, so gauntletFast runs and blocks (red)",
      code == 2 and ran, f"exit {code}, gauntletFast ran: {ran}")

print("== the same through grok_hooks.py")
code_sub, code, ran = scenario([sys.executable, "-B", BRIDGE, "stop"], [sys.executable, "-B", BRIDGE, "stop"], "bridge")
check("hardener's mutationGate green", code_sub == 0)
check("main Stop: gauntletFast runs and blocks (red)", code == 2 and ran, f"exit {code}, gauntletFast ran: {ran}")

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
