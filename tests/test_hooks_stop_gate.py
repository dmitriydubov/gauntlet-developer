"""gauntlet/hooks/stop_gate.py when the gate cannot even run: the agent keeps working on red, within its attempts.

Claude Code takes exit 2 of a Stop hook as "keep working" and any other failure of the hook as an error that lets
the agent stop. An OSError while starting Gradle or writing the hook log (gradlew a directory, build/gauntlet or the
module path a file, the log path a directory) ended the hook with a traceback and exit 1, and so did Gradle output
that was not UTF-8: the agent stopped on a build that never ran. Outside a git repository the hook returned 0 without
a word. Each failure is now a red run that goes through the attempts counter: held while attempts remain, let go with
a warning after them - never held for ever.

A green exit is not enough either: one line in a build script (gradle.startParameter.excludedTaskNames) left every
gate out of the task graph, Gradle printed BUILD SUCCESSFUL, and the hook let the agent stop. The hook now demands a
"> Task" line for every gate task of the task it runs (GATE_TASKS), except those it left out itself.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import kit

RED_GRADLEW = "#!/bin/sh\necho 'CRAP FAIL com.example.X#y'\nexit 1\n"
ATTEMPTS = 3


def green_gradlew(prefix=":"):
    """A wrapper that, like Gradle with --console=plain, prints "> Task <prefix><name>" for every gate task of the
    task it runs - except those given with -x and those named in the file left-out ("*" = all) - and exits 0."""
    gate = kit.stop_gate()
    lines = ["#!/usr/bin/env bash", 'echo "$*" >> gradle-calls', "task=$1", "declare -A excluded", "prev="]
    lines += ['for a in "$@"; do [ "$prev" != -x ] || excluded[$a]=1; prev=$a; done']
    lines += ["case $task in"]
    for name in gate.GATE_TASKS:
        lines += [f"  {name}) names='{' '.join(gate.gate_tasks(name))}' ;;"]
    lines += ["  *) names=$task ;;", "esac"]
    lines += ["for n in $names; do",
              "  [ -z \"${excluded[$n]}\" ] || continue",
              "  grep -qxF -e \"$n\" -e '*' left-out 2>/dev/null && continue",
              f"  echo \"> Task {prefix}$n\"",
              "done", "echo 'BUILD SUCCESSFUL in 1s'", "exit 0", ""]
    return "\n".join(lines)


class Project:
    """A committed repository with the kit's hooks and one Gradle build (at the root, or in the module `core`)."""

    def __init__(self, tmp, module="", git=True):
        self.root = os.path.join(tmp, "service")
        self.prefix = module + "/" if module else ""
        shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(self.root, "gauntlet"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        kit.set_property(self.root, "module", module)
        kit.write(self.path("build.gradle.kts"), "plugins { java }\n")
        kit.write(self.path("src/main/java/x/Order.java"), "package x; class Order {}\n")
        self.gradlew(RED_GRADLEW)
        if git:
            self.git("init", "-q", "-b", "main")
            self.git("add", "-A")
            self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "base")
        self.hook({"session_id": "s", "hook_event_name": "SessionStart"}, "--record-start")

    def path(self, rel):
        return os.path.join(self.root, self.prefix + rel)

    def git(self, *args):
        r = kit.run(["git", *args], cwd=self.root)
        assert r.code == 0, r

    def gradlew(self, text):
        os.chmod(kit.write(self.path("gradlew"), text), 0o755)

    def hook(self, event, *args, **env):
        clean = {k: v for k, v in os.environ.items() if k not in ("GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK")}
        clean.update(CLAUDE_PROJECT_DIR=self.root, PYTHONDONTWRITEBYTECODE="1", **env)
        return subprocess.run([sys.executable, os.path.join(self.root, "gauntlet", "hooks", "stop_gate.py"), *args],
                              cwd=self.root, input=json.dumps(event), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=clean)

    def stop(self, first=False, **env):
        event = {"session_id": "s", "hook_event_name": "Stop", "stop_hook_active": not first}
        return self.hook(event, "--task", "gauntletFast", "--max-attempts", str(ATTEMPTS), "--timeout", "60", **env)

    def change(self):
        kit.write(self.path("src/main/java/x/Price.java"), "package x; class Price {}\n")


class HookCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def assert_held_then_released(self, p, *causes):
        """Red within the attempts, the causes in what the agent reads; released with a warning after them."""
        for attempt in range(1, ATTEMPTS + 1):
            r = p.stop(first=attempt == 1)
            self.assertEqual(r.returncode, 2, f"attempt {attempt}: the agent may stop on a gate that never ran\n"
                                              f"{r.stdout}{r.stderr}")
            self.assertIn(f"is RED (attempt {attempt}/{ATTEMPTS})", r.stderr)
            for cause in causes:
                self.assertIn(cause, r.stderr)
        r = p.stop()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"still RED after {ATTEMPTS} attempts", json.loads(r.stdout)["systemMessage"])


class GateCannotRun(HookCase):

    def test_gradlew_that_is_a_directory(self):
        p = Project(self.tmp.name)
        p.change()
        os.remove(p.path("gradlew"))
        os.makedirs(p.path("gradlew"))
        self.assert_held_then_released(p, "gauntlet: cannot run ./gradlew gauntletFast in .:", "Permission denied")

    def test_build_gauntlet_that_is_a_file(self):
        p = Project(self.tmp.name)
        p.change()
        kit.write(p.path("build/gauntlet"), "not a directory\n")
        self.assert_held_then_released(p, "gauntlet: cannot run ./gradlew gauntletFast in .:", "File exists")

    def test_module_path_that_is_a_file(self):
        p = Project(self.tmp.name, module="core")
        p.git("rm", "-rq", "core")
        kit.write(os.path.join(p.root, "core"), "the module became a file\n")
        self.assert_held_then_released(p, "gauntlet: cannot run gradle gauntletFast in core:", "Not a directory")

    def test_hook_log_that_cannot_be_written(self):
        # Gradle ran and was red; its causes reach the agent on every attempt, not a cached empty log
        p = Project(self.tmp.name)
        p.change()
        os.makedirs(p.path("build/gauntlet/gauntletFast-hook.log"))
        self.assert_held_then_released(p, "CRAP FAIL com.example.X#y", "gauntlet: cannot write the hook log")

    def test_gradle_output_that_is_not_utf8(self):
        p = Project(self.tmp.name)
        p.change()
        p.gradlew("#!/bin/sh\nprintf 'Caf\\351 \\377\\n'\necho 'CRAP FAIL com.example.X#y'\nexit 1\n")
        self.assert_held_then_released(p, "CRAP FAIL com.example.X#y")


class GreenExitWithoutTheGates(HookCase):
    """Gradle exited 0: the gate is green only when Gradle ran every gate task of the task the hook runs."""

    def project(self, module="", prefix=":"):
        p = Project(self.tmp.name, module=module)
        p.gradlew(green_gradlew(prefix))
        p.change()
        return p

    def test_every_gate_task_ran(self):
        p = self.project()
        r = p.stop(first=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")

    def test_a_build_that_ran_no_gate_is_red_within_the_attempts(self):
        # gradle.startParameter.excludedTaskNames.addAll(['gauntletFast', 'gauntlet']) in build.gradle: no task ran,
        # BUILD SUCCESSFUL, exit 0 - the agent stopped on it
        p = self.project()
        kit.write(p.path("left-out"), "*\n")
        self.assert_held_then_released(
            p, "gauntlet: Gradle finished gauntletFast without running gauntletFast, gauntletScope, integrityCheck",
            "gradle.startParameter.excludedTaskNames")

    def test_each_gate_task_left_out_is_named(self):
        gate = kit.stop_gate()
        for task in gate.gate_tasks("gauntletFast"):
            with self.subTest(task):
                p = Project(tempfile.mkdtemp(dir=self.tmp.name))
                p.gradlew(green_gradlew())
                p.change()
                kit.write(p.path("left-out"), task + "\n")
                r = p.stop(first=True)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn(f"gauntlet: Gradle finished gauntletFast without running {task} - no", r.stderr)
                self.assertEqual(len(gate.gate_tasks("gauntletFast")), 14)

    def test_the_acceptance_tests_the_hook_leaves_out_for_a_pending_spec(self):
        p = self.project()
        kit.write(p.path("src/acceptanceTest/resources/features/orders.feature"), "Feature: Orders\n")
        r = p.stop(first=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("-x acceptanceTest -x acceptanceCheck", kit.read(p.path("gradle-calls")))
        self.assertIn("Acceptance tests were left out", json.loads(r.stdout)["systemMessage"])

    def test_task_paths_of_a_project_inside_a_multi_project_build(self):
        p = self.project(module="core", prefix=":core:")
        r = p.stop(first=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_hardener_s_mutation_gate(self):
        p = self.project()
        event = {"session_id": "s", "hook_event_name": "SubagentStop", "agent_type": "hardener", "agent_id": "h1",
                 "stop_hook_active": False}
        r = p.hook(event, "--task", "mutationGate", "--max-attempts", "2", "--timeout", "60")
        self.assertEqual(r.returncode, 0, r.stderr)
        kit.write(p.path("left-out"), "pitest\n")
        p.change()
        kit.write(p.path("src/main/java/x/Fee.java"), "package x; class Fee {}\n")
        r = p.hook(event, "--task", "mutationGate", "--max-attempts", "2", "--timeout", "60")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("gauntlet: Gradle finished mutationGate without running pitest - no", r.stderr)


class VerifyRan(unittest.TestCase):
    """--verify-ran: the CI run step's judgement of a green Gradle output, the same as the hook's."""

    def verify(self, task, output):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write(output)
        self.addCleanup(os.remove, f.name)
        return subprocess.run([sys.executable, os.path.join(kit.kit(), "gauntlet", "hooks", "stop_gate.py"),
                               "--verify-ran", task, "--log", f.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True)

    def test_every_gate_task_with_any_outcome(self):
        names = kit.stop_gate().gate_tasks("gauntlet")
        outcomes = ["", " UP-TO-DATE", " NO-SOURCE", " SKIPPED", " FROM-CACHE"]
        output = "".join(f"> Task :{n}{outcomes[i % len(outcomes)]}\n" for i, n in enumerate(names))
        r = self.verify("gauntlet", output + "BUILD SUCCESSFUL in 9s\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_a_missing_task_and_a_line_that_only_mentions_it(self):
        names = [n for n in kit.stop_gate().gate_tasks("gauntlet") if n != "integrityCheck"]
        output = "".join(f"> Task :{n}\n" for n in names)
        output += "Integrity check: OK\n> Task :integrityCheckReport\n  > Task :integrityCheck\n"
        r = self.verify("gauntlet", output)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("without running integrityCheck - no", r.stdout)

    def test_an_unreadable_log_is_no_verdict(self):
        r = subprocess.run([sys.executable, os.path.join(kit.kit(), "gauntlet", "hooks", "stop_gate.py"),
                            "--verify-ran", "gauntlet", "--log", os.path.join(tempfile.gettempdir(), "no-such-log")],
                           stdout=subprocess.PIPE, text=True)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("gauntlet: cannot read the Gradle output", r.stdout)


class GateTasksOfTheKit(unittest.TestCase):
    """GATE_TASKS is what the hook and CI demand of a green run; gauntlet/gauntlet.gradle is what the aggregates run.
    (The e2e suite checks the demand against Gradle's real output of the whole gauntlet.)"""

    def setUp(self):
        self.gradle = kit.read(os.path.join(kit.kit(), "gauntlet", "gauntlet.gradle"))
        self.gate = kit.stop_gate()

    def test_every_dependency_of_an_aggregate_is_demanded(self):
        for task in self.gate.GATE_TASKS:
            with self.subTest(task):
                block = re.search(r"^tasks\.register\('%s'[^\n]*\{\n(.*?)^\}" % task, self.gradle, re.S | re.M)
                self.assertIsNotNone(block, f"gauntlet.gradle registers no {task}")
                lists = re.findall(r"dependsOn\s+((?:'\w+'\s*,\s*)*'\w+')", block.group(1))
                names = {n for found in lists for n in re.findall(r"'(\w+)'", found)}
                self.assertTrue(names, f"{task} depends on nothing in gauntlet.gradle")
                self.assertLessEqual(names, set(self.gate.gate_tasks(task)))

    def test_every_demanded_task_is_one_the_kit_registers_or_configures(self):
        kit_tasks = set(re.findall(r"tasks\.(?:register|named)\('(\w+)'", self.gradle))
        demanded = {n for names in self.gate.GATE_TASKS.values() for n in names} | set(self.gate.GATE_TASKS)
        self.assertEqual(demanded - kit_tasks, set())     # test, pitest, jacocoTestReport: the plugins', named by the kit


class WithoutState(unittest.TestCase):
    """Without git, or without its state directory, there is no attempts counter: the hook says the gate did not
    run and never holds the agent."""

    def test_stop_says_the_gate_did_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, git=False)
            p.change()
            for first in (True, False):
                r = p.stop(first=first)
                self.assertEqual(r.returncode, 0, r.stderr)   # no state to count attempts with: never held
                self.assertIn("gauntletFast did NOT run", json.loads(r.stdout)["systemMessage"])
                self.assertIn("not inside a git repository", r.stdout)
            # switched off by the human, or recording the session start: nothing to report
            r = p.stop(first=True, GAUNTLET_STOP_HOOK="off")
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            r = p.hook({"session_id": "s", "hook_event_name": "SessionStart"}, "--record-start")
            self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_state_directory_that_is_a_file(self):
        # the hook keeps its attempts in .git/gauntlet-hook: without it there is no counter to hold the agent with
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.change()
            shutil.rmtree(os.path.join(p.root, ".git", "gauntlet-hook"))
            kit.write(os.path.join(p.root, ".git", "gauntlet-hook"), "not a directory\n")
            r = p.stop(first=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("gauntletFast did NOT run", json.loads(r.stdout)["systemMessage"])


if __name__ == "__main__":
    unittest.main()
