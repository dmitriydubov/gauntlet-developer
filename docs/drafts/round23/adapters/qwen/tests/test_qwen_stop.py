"""Synthetic check of the kit's session_start.sh and stop_gate.py under Qwen Code 0.28.4 events, called the way the
adapter's .qwen/settings.json calls them (no translation layer).

Qwen Code events (docs/users/features/hooks.md at tag v0.28.4): SessionStart {source, model, agent_type?}, Stop
{stop_hook_active, last_assistant_message, background_tasks, crons, context_usage...}, SubagentStop {stop_hook_active,
agent_id, agent_type, agent_transcript_path, last_assistant_message}. How Qwen Code reads the result (package
@qwen-code/qwen-code@0.28.4, commandResult / convertPlainTextToHookOutput / isBlockingDecision): exit 2 = decision
"deny" with stderr as the reason, which keeps the agent working with that reason as its next prompt; exit 0 with a
JSON object = that object (systemMessage is shown); exit 0 with plain text on SessionStart = model context.
A fake ./gradlew prints a '> Task' line for every gate task and fails while FAKE_RED exists.
Usage: python3 -I test_qwen_stop.py <fixture repo>
"""
import json
import os
import stat
import subprocess
import sys

PROJ = os.path.abspath(sys.argv[1])
HOOKS = os.path.join(PROJ, "gauntlet", "hooks")
ENV = dict(os.environ, QWEN_PROJECT_DIR=PROJ, CLAUDE_PROJECT_DIR=PROJ, GEMINI_PROJECT_DIR=PROJ)
for name in ("GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK", "CLAUDE_CODE_REMOTE"):
    ENV.pop(name, None)
ENV["GAUNTLET_DOCKER"] = "off"
RED = os.path.join(PROJ, "FAKE_RED")
SESSION = "5b1e2a77-qwen-stop"
failures = 0

TASKS = {"gauntletFast": ["gauntletScope", "integrityCheck", "checkstyleGate", "pmdGate", "test", "archTest",
                          "testCensus", "acceptanceTest", "acceptanceCheck", "jacocoTestReport", "crapGate",
                          "cpdReport", "dryGate"],
         "mutationGate": ["gauntletScope", "pitest", "pitSummary"]}
with open(os.path.join(PROJ, "gradlew"), "w") as f:
    f.write("#!/bin/sh\n# fake Gradle for the hook check: one '> Task' line per gate task\ntask=$1\n"
            "echo \"$task\" >> \"$(dirname \"$0\")/.fake-gradle-calls\"\n")
    for task, subs in TASKS.items():
        f.write(f"if [ \"$task\" = {task} ]; then\n")
        for sub in subs + [task]:
            f.write(f"  echo '> Task :{sub}'\n")
        f.write("fi\n")
    f.write("if [ -e \"$(dirname \"$0\")/FAKE_RED\" ]; then echo 'CRAP FAIL com.example.service.App#run 12.0'; "
            "echo 'BUILD FAILED'; exit 1; fi\necho 'BUILD SUCCESSFUL'\n")
os.chmod(os.path.join(PROJ, "gradlew"), stat.S_IRWXU)
with open(os.path.join(PROJ, ".git", "info", "exclude"), "a") as f:
    f.write(".fake-gradle-calls\nFAKE_RED\n")
subprocess.run(["git", "update-index", "--add", "--chmod=+x", "gradlew"], cwd=PROJ, capture_output=True)
subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "fake gradle", "--", "gradlew"],
               cwd=PROJ, capture_output=True)


def base(event, **extra):
    doc = {"session_id": SESSION, "transcript_path": "/tmp/qwen-t.jsonl", "cwd": PROJ, "hook_event_name": event,
           "timestamp": "2026-11-24T07:10:00.000Z", "permission_mode": "auto_edit"}
    doc.update(extra)
    return doc


def stop(active):
    return base("Stop", stop_hook_active=active, last_assistant_message="Готово.", background_tasks=[], crons=[],
                context_usage=0.12, context_limit=1000000, input_tokens=120000)


def subagent_stop(agent_type, active=False):
    return base("SubagentStop", stop_hook_active=active, agent_id=f"{agent_type}-call_7", agent_type=agent_type,
                agent_transcript_path="/tmp/qwen-sub.jsonl", last_assistant_message="Готово.", background_tasks=[],
                crons=[])


def run(cmd, event):
    proc = subprocess.run(cmd, input=json.dumps(event), capture_output=True, text=True, cwd=PROJ, env=ENV, timeout=900)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def qwen_reads(event_name, code, out, err):
    """What Qwen Code does with the result: (blocks?, text the model or the user gets)."""
    if code == 2:
        try:
            doc = json.loads(err)
            if isinstance(doc, dict):
                return doc.get("decision") in ("block", "deny"), doc.get("reason", "")
        except ValueError:
            pass
        return True, err                               # {"decision": "deny", "reason": stderr}
    if code != 0:
        return False, ""                               # non-blocking error, stderr only in debug mode
    if not out:
        return False, ""
    try:
        doc = json.loads(out)
        if isinstance(doc, dict):
            return doc.get("decision") in ("block", "deny") or doc.get("continue") is False, doc.get("systemMessage", "")
    except ValueError:
        pass
    return False, ("context: " if event_name == "SessionStart" else "system message: ") + out


def check(label, got, want):
    global failures
    ok = got == want
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got}" + ("" if ok else f" (want {want})"))


STOP = [sys.executable, "-B", os.path.join(HOOKS, "stop_gate.py"), "--task", "gauntletFast", "--max-attempts", "3",
        "--timeout", "1700"]
HARDENER = [sys.executable, "-B", os.path.join(HOOKS, "stop_gate.py"), "--task", "mutationGate", "--max-attempts", "2",
            "--timeout", "3300"]

code, out, err = run(["bash", os.path.join(HOOKS, "session_start.sh")],
                     base("SessionStart", source="startup", model="qwen4-max"))
blocks, text = qwen_reads("SessionStart", code, out, err)
check("SessionStart: status line goes into the model's context",
      (code, blocks, text.startswith("context: [gauntlet] active - scope: changed vs origin/main")), (0, False, True))
check("SessionStart: status line says guard and stop hook are on", "guard: on; stop hook: on" in text, True)

code, out, err = run(STOP, stop(False))
check("Stop with nothing changed: no gate, the agent may stop", qwen_reads("Stop", code, out, err), (False, ""))

with open(os.path.join(PROJ, "src/main/java/com/example/service/App.java"), "a") as f:
    f.write("// change 1\n")
open(RED, "w").close()
code, out, err = run(STOP, stop(False))
blocks, text = qwen_reads("Stop", code, out, err)
check("Stop, code changed, gate red: Qwen Code keeps the agent working", (code, blocks), (2, True))
check("  ... and the reason it gets is the gate's failure lines", ("attempt 1/3" in text, "CRAP FAIL" in text),
      (True, True))
for attempt in (2, 3):
    code, out, err = run(STOP, stop(True))
    blocks, text = qwen_reads("Stop", code, out, err)
    check(f"Stop again (stop_hook_active true): attempt {attempt}", (code, blocks, f"attempt {attempt}/3" in text),
          (2, True, True))
code, out, err = run(STOP, stop(True))
blocks, text = qwen_reads("Stop", code, out, err)
check("Stop a 4th time: released with a warning that the work is NOT done", (code, blocks, "NOT done" in text),
      (0, False, True))

os.remove(RED)
with open(os.path.join(PROJ, "src/main/java/com/example/service/App.java"), "a") as f:
    f.write("// change 2\n")
code, out, err = run(STOP, stop(False))
check("Stop after a fix, gate green: the agent may stop", qwen_reads("Stop", code, out, err)[0], False)

with open(os.path.join(PROJ, "src/acceptanceTest/resources/features/a.feature"), "a") as f:
    f.write("  Сценарий: черновик\n")
calls_before = open(os.path.join(PROJ, ".fake-gradle-calls")).read().count("\n")
code, out, err = run(STOP, stop(False))
calls_after = open(os.path.join(PROJ, ".fake-gradle-calls")).read().count("\n")
check("Stop after a spec-only change: no gate (the spec waits for the human)",
      (qwen_reads("Stop", code, out, err)[0], calls_after - calls_before), (False, 0))
subprocess.run(["git", "checkout", "--", "src/acceptanceTest/resources/features/a.feature"], cwd=PROJ)

with open(os.path.join(PROJ, "src/test/java/com/example/service/AppTest.java"), "a") as f:
    f.write("// hardened\n")
open(RED, "w").close()
code, out, err = run(HARDENER, subagent_stop("hardener"))
blocks, text = qwen_reads("SubagentStop", code, out, err)
check("SubagentStop hardener, mutationGate red: the hardener keeps working", (code, blocks, "mutationGate" in text),
      (2, True, True))
os.remove(RED)
with open(os.path.join(PROJ, "src/test/java/com/example/service/AppTest.java"), "a") as f:
    f.write("// hardened 2\n")
code, out, err = run(HARDENER, subagent_stop("hardener", True))
check("SubagentStop hardener, mutationGate green: the hardener may finish", qwen_reads("SubagentStop", code, out, err)[0],
      False)

log = os.path.join(PROJ, "build", "gauntlet-fast.log")
os.makedirs(os.path.dirname(log), exist_ok=True)
subprocess.run(f"./gradlew gauntletFast --continue --console=plain > {log} 2>&1", shell=True, cwd=PROJ)
proc = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, "stop_gate.py"), "--verify-ran", "gauntletFast", "--log",
                       log], capture_output=True, text=True, cwd=PROJ, env=ENV)
check("evidence check: stop_gate.py --verify-ran on a saved gauntletFast log", proc.returncode, 0)
with open(log, "w") as f:
    f.write("> Task :test\nBUILD SUCCESSFUL\n")
proc = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, "stop_gate.py"), "--verify-ran", "gauntletFast", "--log",
                       log], capture_output=True, text=True, cwd=PROJ, env=ENV)
check("evidence check: a log with gate tasks missing is refused", proc.returncode != 0, True)
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
