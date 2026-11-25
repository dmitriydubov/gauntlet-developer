"""Tests of the Kimi bridge against the kit's own hooks (guard.py, stop_gate.py, session_start.sh), unchanged.

Event shapes follow @moonshot-ai/kimi-code 2.7.3 (dist/main.mjs: runMatchedHooks/toHookInputData, runPreToolUse,
runStop, notifyTurnStarted, triggerSessionStart, runPromptSubmitHook): snake_case keys, Write/Edit with `path`,
Stop with turn_id and stop_hook_active=false, TurnStarted with origin_kind/origin_name.

  python3 -I -B test_kimi_hooks.py <kit dir> <bridge file>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

KIT = os.path.realpath(sys.argv.pop(1)) if len(sys.argv) > 2 else None
BRIDGE = os.path.realpath(sys.argv.pop(1)) if len(sys.argv) > 1 else None
GATE_TASKS = ["gauntletScope", "integrityCheck", "checkstyleGate", "pmdGate", "test", "archTest", "testCensus",
              "acceptanceTest", "acceptanceCheck", "jacocoTestReport", "crapGate", "cpdReport", "dryGate"]
FAKE_GRADLEW = """#!/bin/sh
echo run >> "$(dirname "$0")/.fake-gradle-runs"
if [ -f "$(dirname "$0")/.fake-gradle-red" ]; then
  echo "> Task :test FAILED"
  echo "OrdersTest > rejectsEmptyOrder() FAILED"
  echo "BUILD FAILED"
  exit 1
fi
for t in %s gauntletFast; do echo "> Task :$t"; done
echo "BUILD SUCCESSFUL"
""" % " ".join(GATE_TASKS)
LOCK_HOLDER = """
import java.nio.channels.FileChannel;
import java.nio.file.*;
public class LockHold {
    public static void main(String[] a) throws Exception {
        try (FileChannel c = FileChannel.open(Path.of(a[0]), StandardOpenOption.CREATE, StandardOpenOption.READ,
                StandardOpenOption.WRITE); var lock = c.lock()) {
            System.out.println("locked"); System.out.flush();
            Thread.sleep(Long.parseLong(a[1]) * 1000);
        }
    }
}
"""


def run(cmd, cwd, env=None, stdin=""):
    return subprocess.run(cmd, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, timeout=300)


class Bridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kimi-bridge-")
        cls.home = os.path.join(cls.tmp, "home")
        cls.kimi_home = os.path.join(cls.home, ".kimi-code")
        os.makedirs(cls.kimi_home)
        cls.repo = os.path.realpath(os.path.join(cls.tmp, "repo"))
        origin = os.path.join(cls.tmp, "origin.git")
        cls.env = dict(os.environ, HOME=cls.home, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e", GAUNTLET_DOCKER="off")
        for k in ("CLAUDE_PROJECT_DIR", "KIMI_CODE_HOME", "GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK", "CLAUDE_CODE_REMOTE"):
            cls.env.pop(k, None)
        run(["git", "init", "-q", "--bare", "-b", "main", origin], cls.tmp, cls.env)
        os.makedirs(cls.repo)
        run(["git", "init", "-q", "-b", "main"], cls.repo, cls.env)
        for name in ("gauntlet", ".claude"):
            shutil.copytree(os.path.join(KIT, name), os.path.join(cls.repo, name))
        shutil.copy(os.path.join(KIT, "CLAUDE.md"), os.path.join(cls.repo, "CLAUDE.md"))
        os.makedirs(os.path.join(cls.repo, "gauntlet", "adapters", "kimi"), exist_ok=True)
        cls.bridge = os.path.join(cls.repo, "gauntlet", "adapters", "kimi", "kimi_hooks.py")
        shutil.copy(BRIDGE, cls.bridge)
        cls.features = os.path.join(cls.repo, "src", "acceptanceTest", "resources", "features")
        os.makedirs(cls.features)
        cls.put("src/acceptanceTest/resources/features/orders.feature", "# language: ru\nФункция: Заказы\n")
        cls.put("src/main/java/App.java", "class App {}\n")
        cls.put("build.gradle", "// fake build\n")
        cls.put("gradlew", FAKE_GRADLEW)
        os.chmod(os.path.join(cls.repo, "gradlew"), 0o755)
        cls.put(".gitignore", ".fake-gradle-runs\n.fake-gradle-red\nbuild/\n.gradle/\n")
        cls.put("gauntlet/adapters/kimi/AGENTS.md", "# AGENTS.md - gauntlet in Kimi Code\n")
        os.makedirs(os.path.join(cls.repo, ".kimi-code"))
        os.symlink("../gauntlet/adapters/kimi/AGENTS.md", os.path.join(cls.repo, ".kimi-code", "AGENTS.md"))
        run(["git", "add", "-A"], cls.repo, cls.env)
        run(["git", "commit", "-q", "-m", "base"], cls.repo, cls.env)
        run(["git", "remote", "add", "origin", origin], cls.repo, cls.env)
        run(["git", "push", "-q", "origin", "main"], cls.repo, cls.env)
        run(["git", "fetch", "-q", "origin"], cls.repo, cls.env)
        run(["git", "checkout", "-q", "-b", "task"], cls.repo, cls.env)
        cls.listing = os.path.join(cls.kimi_home, "gauntlet-projects.txt")
        with open(cls.listing, "w") as f:
            f.write(f"# checkouts the gauntlet bridge acts in\n{cls.repo}\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def put(cls, rel, text):
        path = os.path.join(cls.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def hook(self, mode, event, *args, script=None):
        base = {"session_id": "session_t1", "cwd": self.repo, "client_type": "kimi_code_cli", "session_title": "t"}
        base.update(event)
        return run([sys.executable, "-I", "-B", script or self.bridge, mode, *args], self.repo, self.env,
                   json.dumps(base))

    def pre(self, tool, tool_input):
        return self.hook("guard", {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
                                   "tool_call_id": "functions.%s:0" % tool})

    def denied(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout.strip():
            return None
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        return out["permissionDecisionReason"]

    # ------------------------------------------------------------------ PreToolUse

    def test_kit_guard_alone_lets_a_kimi_write_through(self):
        """The reason for the bridge: Kimi names the file `path`, guard.py reads `file_path`."""
        proc = run([sys.executable, "-I", "-B", os.path.join(self.repo, "gauntlet", "hooks", "guard.py")], self.repo,
                   dict(self.env, CLAUDE_PROJECT_DIR=self.repo),
                   json.dumps({"hook_event_name": "PreToolUse", "cwd": self.repo, "tool_name": "Write",
                               "tool_input": {"path": "gauntlet/config/gauntlet.properties", "content": "x"}}))
        self.assertEqual(proc.stdout.strip(), "")

    def test_write_and_edit_to_the_kit_are_denied(self):
        self.assertIn("human-owned", self.denied(self.pre("Write", {"path": "gauntlet/config/gauntlet.properties",
                                                                     "content": "x"})))
        self.assertIn("human-owned", self.denied(self.pre("Edit", {"path": os.path.join(self.repo, ".claude/agents/reviewer.md"),
                                                                    "old_string": "a", "new_string": "b"})))
        self.assertIn("human-owned", self.denied(self.pre("Write", {"path": "CLAUDE.md", "content": "x"})))

    def test_kimi_instructions_and_project_config_are_human_owned(self):
        for rel in ("AGENTS.md", ".kimi-code/local.toml", ".agents/agents/x.md", ".kimi-code/AGENTS.md", ".mcp.json"):
            self.assertIsNotNone(self.denied(self.pre("Write", {"path": rel, "content": "x"})), rel)
        self.assertIsNotNone(self.denied(self.pre("Bash", {"command": "echo '{}' > .mcp.json"})))

    def test_user_kimi_configuration_is_denied_but_session_plans_are_not(self):
        reason = self.denied(self.pre("Write", {"path": os.path.join(self.kimi_home, "config.toml"), "content": "x"}))
        self.assertIn("Kimi Code configuration", reason)
        self.assertIsNotNone(self.denied(self.pre("Edit", {"path": "~/.kimi-code/SYSTEM.md", "old_string": "a",
                                                           "new_string": "b"})))
        self.assertIsNotNone(self.denied(self.pre("Write", {"path": os.path.join(self.home, ".agents", "AGENTS.md"),
                                                            "content": "x"})))
        plan = os.path.join(self.kimi_home, "sessions", "wd", "session_t1", "agents", "main", "plans", "p.md")
        self.assertIsNone(self.denied(self.pre("Write", {"path": plan, "content": "plan"})))

    def test_production_code_is_allowed(self):
        self.assertIsNone(self.denied(self.pre("Write", {"path": "src/main/java/Orders.java", "content": "class O {}"})))
        self.assertIsNone(self.denied(self.pre("Read", {"path": "gauntlet/CLAUDE.md"})))

    def test_spec_draft_is_writable_until_the_spec_commit_then_frozen(self):
        draft = {"path": "src/acceptanceTest/resources/features/orders.feature", "content": "# language: ru\n"}
        self.assertIsNone(self.denied(self.pre("Write", draft)))
        self.assertIn("specification", self.denied(self.pre("Bash", {"command": "echo x >> " + draft["path"]})))
        with open(os.path.join(self.repo, draft["path"]), "a", encoding="utf-8") as f:
            f.write("  Сценарий: пустой заказ\n")
        run(["git", "add", draft["path"]], self.repo, self.env)
        run(["git", "commit", "-q", "-m", "spec: orders"], self.repo, self.env)
        try:
            self.assertIn("frozen", self.denied(self.pre("Edit", dict(draft, old_string="a", new_string="b"))))
        finally:
            run(["git", "reset", "-q", "--hard", "origin/main"], self.repo, self.env)

    def test_bash_follows_the_kimi_cwd_parameter(self):
        self.assertIsNotNone(self.denied(self.pre("Bash", {"command": "rm hooks/guard.py", "cwd": "gauntlet"})))
        self.assertIsNone(self.denied(self.pre("Bash", {"command": "rm -f Orders.java", "cwd": "src/main/java"})))

    def test_bash_human_only_actions_and_user_config(self):
        for command in ("git push --force origin task", "git rebase origin/main", "gh pr merge 12 --squash",
                        "git commit --amend -m x", "echo off > ~/.kimi-code/config.toml", "rm AGENTS.md",
                        "sed -i s/a/b/ .kimi-code/local.toml"):
            self.assertIsNotNone(self.denied(self.pre("Bash", {"command": command})), command)
        self.assertIsNone(self.denied(self.pre("Bash", {"command": "./gradlew gauntletFast --continue"})))

    def test_unlisted_checkout_and_broken_input_pass(self):
        os.rename(self.listing, self.listing + ".off")
        try:
            self.assertIsNone(self.denied(self.pre("Write", {"path": "gauntlet/x", "content": "x"})))
        finally:
            os.rename(self.listing + ".off", self.listing)
        proc = run([sys.executable, "-I", "-B", self.bridge, "guard"], self.repo, self.env, "not json")
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    # ------------------------------------------------------------------ SessionStart / UserPromptSubmit

    def test_status_line_reaches_the_first_prompt_once(self):
        sid = {"session_id": "session_status"}
        self.assertEqual(self.hook("session-start", dict(sid, hook_event_name="SessionStart", source="startup",
                                                         model="kimi-code/k3.1-pro", profile="agent")).returncode, 0)
        first = self.hook("prompt", dict(sid, hook_event_name="UserPromptSubmit", is_steer=False,
                                         prompt=[{"type": "text", "text": "coordinate"}]))
        self.assertTrue(first.stdout.startswith("[gauntlet] "), first.stdout + first.stderr)
        self.assertIn("guard: on", first.stdout)
        second = self.hook("prompt", dict(sid, hook_event_name="UserPromptSubmit", is_steer=False, prompt=[]))
        self.assertEqual(second.stdout, "")

    def test_missing_session_start_is_reported_to_the_model(self):
        out = self.hook("prompt", {"session_id": "session_without_start", "hook_event_name": "UserPromptSubmit",
                                   "prompt": []}).stdout
        self.assertIn("WARNING", out)

    # ------------------------------------------------------------------ Stop

    def gradle_runs(self):
        try:
            with open(os.path.join(self.repo, ".fake-gradle-runs")) as f:
                return len(f.read().split())
        except OSError:
            return 0

    def stop(self, turn, session="session_stop"):
        return self.hook("stop", {"session_id": session, "hook_event_name": "Stop", "turn_id": turn, "step": 2,
                                  "first_step_of_turn": 1, "finish_reason": "stop", "usage": {},
                                  "stop_hook_active": False}, "--task", "gauntletFast", "--max-attempts", "1",
                         "--timeout", "1700")

    def started(self, turn, kind, name=None, session="session_stop"):
        event = {"session_id": session, "hook_event_name": "TurnStarted", "turn_id": turn, "origin_kind": kind,
                 "prompt": []}
        if name:
            event["origin_name"] = name
        self.assertEqual(self.hook("turn", event).returncode, 0)

    def test_stop_gates_the_main_turn_and_skips_the_subagent_turn(self):
        self.hook("session-start", {"session_id": "session_stop", "hook_event_name": "SessionStart", "source": "startup"})
        self.put("src/main/java/App.java", "class App { int x; }\n")
        open(os.path.join(self.repo, ".fake-gradle-red"), "w").close()
        try:
            self.started(0, "user")
            self.started(0, "system_trigger", "subagent")           # a foreground subagent of turn 0
            before = self.gradle_runs()
            sub = self.stop(0)
            self.assertEqual((sub.returncode, self.gradle_runs()), (0, before), sub.stderr)
            main = self.stop(0)
            self.assertEqual(main.returncode, 2, main.stdout + main.stderr)
            self.assertEqual(self.gradle_runs(), before + 1)
            self.assertIn("RED (attempt 1/1)", main.stderr)
            self.assertIn("[gauntlet/Kimi]", main.stderr)
            self.assertIn("--timeout 560", self.gate_args())
        finally:
            os.remove(os.path.join(self.repo, ".fake-gradle-red"))
            run(["git", "checkout", "-q", "--", "src/main/java/App.java"], self.repo, self.env)

    def test_turns_started_by_a_background_task_are_gated(self):
        """Kimi 2.7.3 gives a turn started by a finished background task origin `task` and no agent. When the main
        agent's task finishes mid-turn, Kimi ends that turn without a Stop (requests pending) and starts a `task`
        turn: it must be gated. A subagent's such turn looks the same and is gated too (one run too many, not one
        too few); the block message then tells a subagent to stay within its role."""
        session = "session_task_turns"
        self.hook("session-start", {"session_id": session, "hook_event_name": "SessionStart", "source": "startup"})
        self.put("src/main/java/App.java", "class App { int n; }\n")
        open(os.path.join(self.repo, ".fake-gradle-red"), "w").close()
        try:
            self.started(1, "user", session=session)                          # main: no Stop, its Gradle finished
            self.started(2, "task", session=session)
            main = self.stop(2, session=session)
            self.assertEqual(main.returncode, 2, main.stdout + main.stderr)
            self.started(3, "user", session=session)
            self.started(0, "system_trigger", "subagent", session=session)   # hardener, first turn: not gated
            self.assertEqual(self.stop(0, session=session).returncode, 0)
            self.started(1, "task", session=session)                          # its mutationGate finished
            sub = self.stop(1, session=session)
            self.assertEqual(sub.returncode, 2, sub.stdout + sub.stderr)      # gated like the main agent's turn
            self.assertIn("Если ты сабагент", sub.stderr)
        finally:
            os.remove(os.path.join(self.repo, ".fake-gradle-red"))
            run(["git", "checkout", "-q", "--", "src/main/java/App.java"], self.repo, self.env)

    def gate_args(self):
        """The arguments the bridge gives stop_gate.py, from its own helper."""
        code = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('b', sys.argv[1]); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "print(' '.join(m.capped(['--task','gauntletFast','--timeout','1700'], sys.argv[2])))")
        return run([sys.executable, "-I", "-B", "-c", code, self.bridge, self.repo], self.repo, self.env).stdout

    def test_green_gate_lets_the_agent_stop(self):
        self.hook("session-start", {"session_id": "session_green", "hook_event_name": "SessionStart",
                                    "source": "startup"})
        self.put("src/main/java/App.java", "class App { int y; }\n")
        try:
            self.started(4, "user", session="session_green")
            proc = self.stop(4, session="session_green")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        finally:
            run(["git", "checkout", "-q", "--", "src/main/java/App.java"], self.repo, self.env)

    def test_stop_passes_while_a_gauntlet_gradle_run_holds_the_build_lock(self):
        if not shutil.which("java"):
            self.skipTest("no java to hold a FileChannel lock")
        lock = os.path.join(self.repo, ".gradle", "gauntlet-build.lock")
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        src = os.path.join(self.tmp, "LockHold.java")
        with open(src, "w") as f:
            f.write(LOCK_HOLDER)
        holder = subprocess.Popen(["java", src, lock, "60"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            self.hook("session-start", {"session_id": "session_lock", "hook_event_name": "SessionStart",
                                        "source": "startup"})
            self.put("src/main/java/App.java", "class App { int z; }\n")
            open(os.path.join(self.repo, ".fake-gradle-red"), "w").close()
            before = self.gradle_runs()
            proc = self.stop(9, session="session_lock")
            self.assertEqual((proc.returncode, self.gradle_runs()), (0, before), proc.stderr)
        finally:
            holder.kill()
            holder.wait()
            holder.stdout.close()
            if os.path.exists(os.path.join(self.repo, ".fake-gradle-red")):
                os.remove(os.path.join(self.repo, ".fake-gradle-red"))
            run(["git", "checkout", "-q", "--", "src/main/java/App.java"], self.repo, self.env)
        time.sleep(0.2)
        after = self.stop(10, session="session_lock")                # lock released: the gate runs again
        self.assertEqual(after.returncode, 0, after.stderr)

    # ------------------------------------------------------------------ report form

    def report(self, text, *args):
        return run([sys.executable, "-I", "-B", self.bridge, "report", *args], self.repo, self.env, text)

    GOOD = """## Итог
Вызовов OrderService.cancel вне домена нет.

## Проверено (покрытие: 3 из 3 по чек-листу)
1. Точка входа — `OrdersController.cancel` — доказательство: `src/main/java/OrdersController.java:41`: «service.cancel(id)»
2. Других вызовов нет — доказательство: `rg -n "cancel\\(" src/main` → 2 совпадения, оба в OrdersController
3. Пул планировщика без MDC — доказательство: `./gradlew -q dependencies` → spring-context 7.0.8;
   `SchedulingConfig.java:12`: «new ThreadPoolTaskScheduler()»

## Не проверено
- (нет: чек-лист покрыт полностью)

## Вопросы и риски для координатора
- нет
"""

    def test_report_in_form_passes(self):
        proc = self.report(self.GOOD, "--commit", "0123456789abcdef")
        self.assertEqual(proc.returncode, 1)                       # the commit is not named
        self.assertIn("коммит", proc.stdout)
        self.assertEqual(self.report(self.GOOD.replace("## Итог\n", "## Итог\nКоммит 0123456.\n"), "--commit",
                                     "0123456789abcdef").returncode, 0)

    def test_report_gaps_are_listed(self):
        thin = "## Итог\nВсё в порядке, вызовов нет.\n\n## Проверено\n1. Вызовов больше нет.\n"
        proc = self.report(thin)
        self.assertEqual(proc.returncode, 1)
        for gap in ("нет раздела «## Не проверено»", "покрытия числом", "утверждение 1 без «доказательство:»"):
            self.assertIn(gap, proc.stdout)
        partial = self.GOOD.replace("3 из 3", "3 из 5").replace("- (нет: чек-лист покрыт полностью)\n", "")
        self.assertIn("«## Не проверено» пуст", self.report(partial).stdout)
        unsearched = self.GOOD.replace('`rg -n "cancel\\(" src/main` → 2 совпадения, оба в OrdersController',
                                       "не найдено других вызовов")
        self.assertIn("без команды поиска", self.report(unsearched).stdout)


if __name__ == "__main__":
    if not (KIT and BRIDGE):
        sys.exit("usage: test_kimi_hooks.py <kit dir> <kimi_hooks.py>")
    unittest.main(verbosity=2)
