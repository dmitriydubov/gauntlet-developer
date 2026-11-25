"""Synthetic check of grok_hooks.py session-start / stop / report against the kit's session_start.sh and stop_gate.py.

A fake ./gradlew in the fixture prints a '> Task' line for every gate task and fails while FAKE_RED exists.
Usage: python3 -I test_grok_stop.py <fixture repo>
"""
import json
import os
import stat
import subprocess
import sys

PROJ = os.path.abspath(sys.argv[1])
BRIDGE = os.path.join(PROJ, "gauntlet", "adapters", "grok", "grok_hooks.py")
ENV = dict(os.environ, CLAUDE_PROJECT_DIR=PROJ, GROK_WORKSPACE_ROOT=PROJ)
for name in ("GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK", "CLAUDE_CODE_REMOTE"):
    ENV.pop(name, None)
RED = os.path.join(PROJ, "FAKE_RED")
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
subprocess.run(["git", "update-index", "--add", "--chmod=+x", "gradlew"], cwd=PROJ, capture_output=True)
subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "fake gradle", "--", "gradlew"],
               cwd=PROJ, capture_output=True)


def envelope(event, pascal, legacy=False, **payload):
    base = {"hookEventName": event, "sessionId": "grok-session-1", "cwd": PROJ, "workspaceRoot": PROJ,
            "timestamp": "2026-11-24T06:00:00Z", "permissionMode": "bypassPermissions"}
    base.update(payload)
    aliases = [("sessionId", "session_id"), ("permissionMode", "permission_mode")]
    if not legacy:   # 1.0.92 adds these; 1.0.45 sent them camelCase only
        aliases += [("stopHookActive", "stop_hook_active"), ("lastAssistantMessage", "last_assistant_message")]
    for camel, snake in aliases:
        if camel in base:
            base.setdefault(snake, base[camel])
    base["hook_event_name"] = pascal
    return base


def run(args, event):
    proc = subprocess.run([sys.executable, "-B", BRIDGE] + args, input=json.dumps(event), capture_output=True,
                          text=True, cwd=PROJ, env=ENV, timeout=600)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def calls():
    path = os.path.join(PROJ, ".fake-gradle-calls")
    return open(path).read().split() if os.path.exists(path) else []


def check(label, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + (f": {detail}" if detail else ""))


def stop_event(active=False, reason="end_turn", tasks=None, legacy=False):
    return envelope("stop", "Stop", legacy=legacy, reason=reason, stopHookActive=active,
                    lastAssistantMessage="done", backgroundTasks=tasks or [], sessionCrons=[])


GATE = ["stop", "--task", "gauntletFast", "--max-attempts", "3", "--timeout", "120"]

print("== SessionStart")
code, out, err = run(["session-start"], envelope("session_start", "SessionStart", source="startup"))
hook_dir = subprocess.run(["git", "rev-parse", "--git-path", "gauntlet-hook"], cwd=PROJ, capture_output=True,
                          text=True).stdout.strip()
hook_dir = hook_dir if os.path.isabs(hook_dir) else os.path.join(PROJ, hook_dir)
status_file = os.path.join(hook_dir, "grok-status.txt")
status = open(status_file).read() if os.path.exists(status_file) else ""
check("status line written for the agent", "[gauntlet] active" in status and "guard: on" in status, status.strip())
check("baseline recorded under the Grok session id",
      os.path.exists(os.path.join(hook_dir, "grok-session-1.start")))

print("== Stop with a red gate: blocked with the causes, attempts counted through stop_hook_active")
with open(os.path.join(PROJ, "src/main/java/com/example/service/App.java"), "a") as f:
    f.write("// change\n")
open(RED, "w").close()
for attempt, active in ((1, False), (2, True), (3, True)):
    code, out, err = run(GATE, stop_event(active=active))
    check(f"attempt {attempt}: exit 2, reason in stderr", code == 2 and f"RED (attempt {attempt}/3)" in err,
          f"exit {code}, {err.splitlines()[0] if err else out}")
code, out, err = run(GATE, stop_event(active=True))
check("attempt 4: released with 'work is NOT done'", code == 0 and "NOT done" in out, out[:120])

print("== the same with the 1.0.45 envelope (stopHookActive only, no snake_case alias)")
with open(os.path.join(PROJ, "src/main/java/com/example/service/App.java"), "a") as f:
    f.write("// change 2\n")
codes = []
for active in (False, True, True, True):
    code, out, err = run(GATE, stop_event(active=active, legacy=True))
    codes.append(code)
check("blocks 3 times, then releases", codes == [2, 2, 2, 0], str(codes))

print("== Stop at session end and Stop while subagents run")
before = len(calls())
code, out, err = run(GATE, stop_event(reason="shutdown"))
check("session-end Stop: no Gradle run, exit 0", code == 0 and len(calls()) == before)
tasks = [{"id": "sub-7", "type": "subagent", "status": "running", "description": "карта кода", "agentType":
          "gauntlet-card-map"}]
code, out, err = run(GATE, stop_event(tasks=tasks))
doc = json.loads(out) if out.startswith("{") else {}
check("running subagent: blocked, no Gradle run", doc.get("decision") == "block" and len(calls()) == before,
      doc.get("reason", out)[:110])
tasks = [{"id": "bg-1", "type": "shell", "status": "running", "command": "./gradlew gauntletFast --continue"}]
code, out, err = run(GATE, stop_event(tasks=tasks))
check("running background Gradle: blocked", '"block"' in out and len(calls()) == before)

print("== Stop with a green gate")
os.remove(RED)
with open(os.path.join(PROJ, "src/main/java/com/example/service/App.java"), "a") as f:
    f.write("// change 3\n")
code, out, err = run(GATE, stop_event())
check("green: exit 0", code == 0, f"exit {code} {out[:80]} {err[:80]}")

print("== SubagentStop of the hardener: its own stop mark, not the main agent's")
with open(os.path.join(PROJ, "src/test/java/com/example/service/AppTest.java"), "a") as f:
    f.write("// hardened\n")
ev = envelope("subagent_stop", "SubagentStop", phase="gate", subagentId="sub-9", subagentType="hardener",
              stopHookActive=False, lastAssistantMessage="killed 3 of 3")
code, out, err = run(["stop", "--task", "mutationGate", "--max-attempts", "2", "--timeout", "120"], ev)
marks = os.listdir(hook_dir)
check("mutationGate ran for the hardener", code == 0 and calls()[-1] == "mutationGate", str(calls()[-2:]))
check("stop mark keyed by the subagent id", any("sub-9" in m for m in marks), str(sorted(marks)))

print("== report form of a read-only card (SubagentStop)")
bad = "Всё проверил, проблем нет."
good = ("## Итог\nвызовов два\n\n## Проверено (покрытие: 2 из 2 по чек-листу)\n1. вызовов X два — доказательство: "
        "`git grep -n X` → 2 совпадения\n\n## Не проверено\n- нет: чек-лист покрыт полностью\n\n"
        "## Вопросы и риски для координатора\n- нет\n")
card = lambda text, sid: envelope("subagent_stop", "SubagentStop", phase="gate", subagentId=sid,
                                  subagentType="gauntlet-card-map", stopHookActive=False, lastAssistantMessage=text)
results = [json.loads(run(["report"], card(bad, "card-1"))[1] or "{}") for _ in range(3)]
check("bad report: returned twice", [r.get("decision") for r in results[:2]] == ["block", "block"],
      results[0].get("reason", "")[:120])
check("third time: let go with a note for the coordinator", "systemMessage" in results[2])
check("good report: accepted", run(["report"], card(good, "card-2"))[1] == "")
rev = lambda text: envelope("subagent_stop", "SubagentStop", phase="gate", subagentId="rev-1",
                            subagentType="reviewer", stopHookActive=False, lastAssistantMessage=text)
check("reviewer without coverage line: returned",
      json.loads(run(["report"], rev("VERDICT: APPROVED\nResidual risks: none"))[1]).get("decision") == "block")
check("reviewer with verdict, coverage and «Не проверено»: accepted",
      run(["report"], rev("VERDICT: APPROVED\nПокрытие: файлы диффа 3 из 3\n## Не проверено\n- нет\n"))[1] == "")

print("== a linked worktree (grok --worktree) keeps its own status line")
wt = os.path.join(os.path.dirname(PROJ), "wt-step-2")
subprocess.run(["git", "worktree", "add", "--detach", wt, "HEAD"], cwd=PROJ, capture_output=True)
wt_env = dict(ENV, CLAUDE_PROJECT_DIR=wt, GROK_WORKSPACE_ROOT=wt)
ev = envelope("session_start", "SessionStart", source="startup")
ev.update(sessionId="grok-session-2", session_id="grok-session-2", cwd=wt, workspaceRoot=wt)
subprocess.run([sys.executable, "-B", os.path.join(wt, "gauntlet/adapters/grok/grok_hooks.py"), "session-start"],
               input=json.dumps(ev), capture_output=True, text=True, cwd=wt, env=wt_env, timeout=300)
wt_dir = subprocess.run(["git", "rev-parse", "--git-path", "gauntlet-hook"], cwd=wt, capture_output=True,
                        text=True).stdout.strip()
wt_dir = wt_dir if os.path.isabs(wt_dir) else os.path.join(wt, wt_dir)
wt_status = open(os.path.join(wt_dir, "grok-status.txt")).read() if os.path.exists(os.path.join(wt_dir, "grok-status.txt")) else ""
main_status = open(status_file).read()
check("worktree status under its own git dir", "grok-session-2" in wt_status and wt_dir != hook_dir, wt_dir)
check("main copy's status line untouched", "grok-session-1" in main_status)

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
