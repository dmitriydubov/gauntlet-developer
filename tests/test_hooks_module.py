"""The hooks read `module` the way the CI workflow reads it (gauntlet/hooks/stop_gate.py and guard.py).

CI strips an entry of blanks and slashes and enters it with `cd`: ./core, core/. and core/ are the build in core,
. and ./ the build at the repository root. Git names a changed path without ./, and the hooks compared the entry as
written with git's paths. With module=./core the Stop hook ran no Gradle and let the agent stop on a red build, and
the guard left the module's specification open to the main agent while it refused the specifier and the hardener
everything. CI was red on the same commit; only the hooks were blind.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import kit
import test_ci_workflow as ci

FEATURES = "src/acceptanceTest/resources/features"
RED_GRADLEW = "#!/bin/sh\necho \"fake gradle $*\"\necho 'CRAP FAIL com.example.X#y'\nexit 1\n"
# (the build on disk, module= as written): the documented spelling and the ones CI reads the same way
LAYOUTS = (("core", "core"), ("core", "./core"), ("core", "core/."), ("", ""), ("", "."))
# what the hooks reported as the guarded builds: the stop gate's MODULES and the guard's Context.modules
HOOKS_MODULES = (
    "import importlib.util, json, sys\n"
    "sys.dont_write_bytecode = True\n"
    "def load(name):\n"
    "    spec = importlib.util.spec_from_file_location(name, 'gauntlet/hooks/' + name + '.py')\n"
    "    module = importlib.util.module_from_spec(spec)\n"
    "    spec.loader.exec_module(module)\n"
    "    return module\n"
    "stop_gate = load('stop_gate')\n"
    "stop_gate.configure_module()\n"
    "print(json.dumps([stop_gate.MODULES, load('guard').Context('.').modules]))\n")


def git(cwd, *args):
    r = kit.run(["git", *args], cwd=cwd)
    assert r.code == 0, f"git {' '.join(args)}: {r.out}"
    return r.out


class Project:
    """A repository with the kit's gauntlet/ and one Gradle build whose wrapper is always red."""

    def __init__(self, tmp, build, module):
        self.root = os.path.join(tmp, "service")
        self.prefix = build + "/" if build else ""
        shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(self.root, "gauntlet"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        kit.set_property(self.root, "module", module)
        kit.write(self.path("build.gradle.kts"), "plugins { java }\n")
        kit.write(self.path("src/main/java/x/Order.java"), "package x; class Order {}\n")
        kit.write(self.path(FEATURES + "/.gitkeep"), "")
        os.chmod(kit.write(self.path("gradlew"), RED_GRADLEW), 0o755)
        bare = os.path.join(tmp, "origin.git")
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "add", "-A")
        git(self.root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "base")
        git(tmp, "init", "-q", "--bare", bare)
        git(self.root, "remote", "add", "origin", bare)
        git(self.root, "push", "-q", "origin", "main")
        git(self.root, "checkout", "-q", "-b", "claude/task")

    def path(self, rel):
        return os.path.join(self.root, self.prefix + rel)

    def hook(self, script, event, *args):
        env = {k: v for k, v in os.environ.items() if k not in ("GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK")}
        env.update(CLAUDE_PROJECT_DIR=self.root, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, os.path.join(self.root, "gauntlet", "hooks", script), *args],
                              cwd=self.root, input=json.dumps(event), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env)

    def guard(self, agent, tool, **params):
        """The guard's reason to refuse, None when it allows."""
        event = {"session_id": "s", "cwd": self.root, "tool_name": tool, "tool_input": params}
        if agent != "main":
            event["agent_type"] = agent
        r = self.hook("guard.py", event)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"] if r.stdout.strip() else None


class ModuleSpelling(unittest.TestCase):

    def test_stop_hook_runs_the_build_however_the_entry_is_written(self):
        for build, module in LAYOUTS:
            with self.subTest(build=build, module=module), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp, build, module)
                p.hook("stop_gate.py", {"session_id": "s", "hook_event_name": "SessionStart"}, "--record-start")
                kit.write(p.path("src/main/java/x/Price.java"), "package x; class Price {}\n")
                r = p.hook("stop_gate.py", {"session_id": "s", "hook_event_name": "Stop", "stop_hook_active": False},
                           "--task", "gauntletFast", "--timeout", "60")
                self.assertEqual(r.returncode, 2, "the agent may stop on a red build: " + r.stderr)
                self.assertIn("CRAP FAIL", r.stderr)
                self.assertTrue(os.path.exists(p.path("build/gauntlet/gauntletFast-hook.log")))

    def test_guard_keeps_the_roles_of_the_build_however_the_entry_is_written(self):
        for build, module in LAYOUTS:
            with self.subTest(build=build, module=module), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp, build, module)
                spec = p.path(FEATURES + "/order.feature")
                self.assertIsNotNone(p.guard("main", "Write", file_path=spec, content="x"), "main wrote the spec")
                self.assertIsNotNone(p.guard("main", "Bash", command=f"rm -rf {p.prefix}src/acceptanceTest"))
                self.assertIsNone(p.guard("specifier", "Write", file_path=spec, content="x"))
                self.assertIsNone(p.guard("hardener", "Write", file_path=p.path("src/test/java/x/OrderTest.java"),
                                          content="x"))
                self.assertIsNotNone(p.guard("hardener", "Write", file_path=p.path("src/main/java/x/Order.java"),
                                             content="x"))
                kit.write(spec, "Feature: order\n")
                git(p.root, "add", "-A")
                git(p.root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "spec")
                reason = p.guard("main", "Write", file_path=spec, content="y")
                self.assertIn("frozen", reason or "", "main changed the approved spec")

    def test_a_change_belongs_to_its_module_and_not_to_the_root_build_listed_beside_it(self):
        # '.' beside modules is the build at the root: it owns what no module owns. A module of one letter is as
        # long as '.', and the order of the list must not hand the module's change to the root build
        spec = importlib.util.spec_from_file_location(
            "gauntlet_stop_gate_under_test", os.path.join(kit.kit(), "gauntlet", "hooks", "stop_gate.py"))
        stop_gate = importlib.util.module_from_spec(spec)
        before, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(stop_gate)
        finally:
            sys.dont_write_bytecode = before
        cases = ((".,a", ["a/src/X.java"], ["a"]), ("a,.", ["a/src/X.java"], ["a"]), (".,a", ["src/X.java"], ["."]),
                 (".,core,core/adapter", ["core/adapter/src/X.java"], ["core/adapter"]),
                 (".,a", ["gauntlet/tools/X.java"], [".", "a"]))
        for value, changed, owners in cases:
            with self.subTest(module=value, changed=changed):
                stop_gate.MODULES = stop_gate.module_dirs(value)
                self.assertEqual(sorted(stop_gate.affected_modules(changed)), sorted(owners))

    def test_hooks_name_the_directories_ci_enters(self):
        for value in (" /svc/adapter/ ,, * ,./core", "core/.,./a/b/,a//b,core", ".", "./", " . , ", ".,core"):
            with self.subTest(module=value), tempfile.TemporaryDirectory() as tmp:
                ws = ci.Workspace(tmp)
                ws.properties(f"module={value}\nproject.java.version=17\n")
                r = ws.step(ci.PLAN)
                self.assertEqual(r.code, 0, r)
                entered = []
                for row in ws.plan():       # the directory CI's `cd` enters, as git names it
                    rel = os.path.relpath(os.path.normpath(os.path.join(ws.root, row[0])), ws.root)
                    entered += [rel] if rel not in entered else []
                expected = [] if entered == ["."] else entered      # the build at the root alone is no module
                shutil.copytree(os.path.join(kit.kit(), "gauntlet", "hooks"), os.path.join(ws.root, "gauntlet", "hooks"),
                                dirs_exist_ok=True)     # the CI workspace holds stop_gate.py already (--verify-ran)
                r = kit.run([sys.executable, "-c", HOOKS_MODULES], cwd=ws.root)
                self.assertEqual(r.code, 0, r)
                self.assertEqual(json.loads(r.out), [expected, expected])


if __name__ == "__main__":
    unittest.main()
