"""The shell steps of .github/workflows/gauntlet.yml, run locally the way the runner runs them (`bash -e`).

GitHub Actions itself is not available here, so everything the steps take from the runner is stubbed: RUNNER_TEMP,
GITHUB_OUTPUT, the JAVA_HOME_<major>_<ARCH> variables setup-java exports, and ./gradlew.
"""
import os
import stat
import tempfile
import unittest

import kit

PLAN = "Resolve the guarded builds and their Java versions"
BASE = "Resolve the base branch"
RUN = "Run the gauntlet in every guarded build"

# a wrapper that records how it was called and, like Gradle, reads whatever stdin offers
GRADLEW = """#!/usr/bin/env bash
cat >/dev/null
echo "$(basename "$PWD")|$*|JAVA_HOME=$JAVA_HOME|GATE=$GAUNTLET_GATE_JAVA_HOME|java=$(command -v java)" >> "$CALLS"
[ ! -f fail ] || exit 1
"""


def workflow():
    return kit.read(os.path.join(kit.kit(), ".github", "workflows", "gauntlet.yml"))


def step_script(name):
    """The `run: |` block of the named step, dedented - a tiny reader for this one file, no YAML library."""
    lines = workflow().split("\n")
    start = lines.index(f"      - name: {name}")
    run = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "run: |")
    indent = len(lines[run]) - len(lines[run].lstrip())
    body = []
    for line in lines[run + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line[indent + 2:])
    return "\n".join(body).rstrip() + "\n"


class Workspace:
    """A checked-out repository as the job sees it."""

    def __init__(self, tmp, modules=""):
        self.root = os.path.join(tmp, "repo")
        self.temp = os.path.join(tmp, "runner-temp")
        self.output = os.path.join(tmp, "github-output")
        self.calls = os.path.join(tmp, "calls")
        self.jdks = os.path.join(tmp, "jdks")
        os.makedirs(self.temp)
        kit.write(os.path.join(self.root, "gauntlet/config/gauntlet.properties"),
                  f"module={modules}\nbaseRef=origin/develop\nproject.java.version=17\ngate.java.version=21\n")
        for module in [m.strip() for m in modules.split(",") if m.strip()] or ["."]:
            self.wrapper(module)

    def wrapper(self, module):
        path = kit.write(os.path.join(self.root, module, "gradlew"), GRADLEW)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)

    def jdk(self, major):
        java = kit.write(os.path.join(self.jdks, str(major), "bin", "java"), "#!/bin/sh\n")
        os.chmod(java, 0o755)
        return os.path.dirname(os.path.dirname(java))

    def env(self, jdks=(17, 21), **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JAVA_HOME")}
        env.update(RUNNER_TEMP=self.temp, GITHUB_OUTPUT=self.output, CALLS=self.calls)
        for major in jdks:
            env[f"JAVA_HOME_{major}_X64"] = self.jdk(major)
        env.update(extra)
        return env

    def step(self, name, **env):
        script = kit.write(os.path.join(self.temp, "step.sh"), step_script(name))
        return kit.run(["bash", "--noprofile", "--norc", "-e", script], cwd=self.root, env=self.env(**env))

    def plan(self):
        return [line.split("\t") for line in kit.read(os.path.join(self.temp, "gauntlet-plan")).splitlines()]

    def outputs(self):
        return kit.read(self.output) if os.path.exists(self.output) else ""

    def called(self):
        return kit.read(self.calls).splitlines() if os.path.exists(self.calls) else []


class WorkflowText(unittest.TestCase):

    def test_scripts_take_runner_values_from_the_environment(self):
        # an expression inside a script is pasted into the shell text; env: keeps the value data
        for name in (PLAN, BASE, RUN):
            self.assertNotIn("${{", step_script(name), name)

    def test_one_setup_java_step_installs_every_planned_version(self):
        text = workflow()
        self.assertEqual(text.count("actions/setup-java@"), 1)
        self.assertIn("java-version: ${{ steps.plan.outputs.java }}", text)

    def test_full_history_is_fetched(self):
        self.assertIn("fetch-depth: 0", workflow())


class PlanStep(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_root_build(self):
        ws = Workspace(self.tmp.name)
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [[".", "17", "21"]])
        self.assertIn("java<<GAUNTLET_EOF\n17\n21\nGAUNTLET_EOF\n", ws.outputs())

    def test_module_overlay_overrides_the_common_versions(self):
        ws = Workspace(self.tmp.name, "core,adapter")
        kit.write(os.path.join(ws.root, "gauntlet/config/adapter/gauntlet.properties"),
                  "project.java.version=21\ngate.java.version=17\n")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["core", "17", "21"], ["adapter", "21", "17"]])
        self.assertIn("java<<GAUNTLET_EOF\n17\n21\nGAUNTLET_EOF\n", ws.outputs())    # each version once

    def test_overlay_key_without_a_value_still_wins_as_in_gradle(self):
        ws = Workspace(self.tmp.name, "core")
        kit.write(os.path.join(ws.root, "gauntlet/config/core/gauntlet.properties"), "gate.java.version=\n")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["core", "17", "17"]])      # no gate version: the tools run on the project JVM

    def test_whitespace_and_carriage_returns_are_not_part_of_a_version(self):
        ws = Workspace(self.tmp.name)
        kit.write(os.path.join(ws.root, "gauntlet/config/gauntlet.properties"),
                  "module=\r\nproject.java.version = 17  \r\ngate.java.version=21\r\n")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [[".", "17", "21"]])

    def test_missing_project_version_stops_the_job(self):
        ws = Workspace(self.tmp.name)
        kit.write(os.path.join(ws.root, "gauntlet/config/gauntlet.properties"), "module=\ngate.java.version=21\n")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 1, r)
        self.assertIn("::error::Set project.java.version", r.out)


class BaseStep(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Workspace(self.tmp.name)
        origin = os.path.join(self.tmp.name, "origin.git")
        for cmd in (["git", "init", "-q", "-b", "develop", self.ws.root],
                    ["git", "-C", self.ws.root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q",
                     "--allow-empty", "-m", "base"],
                    ["git", "-C", self.ws.root, "branch", "release"],
                    ["git", "clone", "-q", "--bare", self.ws.root, origin],
                    ["git", "-C", self.ws.root, "remote", "add", "origin", origin]):
            self.assertEqual(kit.run(cmd).code, 0, cmd)

    def test_pull_request_base_comes_from_the_event(self):
        r = self.ws.step(BASE, BASE_REF="release")
        self.assertEqual(r.code, 0, r)
        self.assertIn("ref=origin/release\n", self.ws.outputs())

    def test_manual_run_falls_back_to_the_configured_base(self):
        r = self.ws.step(BASE, BASE_REF="")
        self.assertEqual(r.code, 0, r)
        self.assertIn("ref=origin/develop\n", self.ws.outputs())


class RunStep(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def planned(self, modules, plan):
        ws = Workspace(self.tmp.name, modules)
        kit.write(os.path.join(ws.temp, "gauntlet-plan"), "".join("\t".join(row) + "\n" for row in plan))
        return ws

    def test_every_build_runs_on_its_own_jvms(self):
        ws = self.planned("core,adapter", [["core", "17", "21"], ["adapter", "21", "17"]])
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main")
        self.assertEqual(r.code, 0, r)
        jdk17, jdk21 = ws.jdk(17), ws.jdk(21)
        calls = ws.called()
        self.assertEqual(len(calls), 6, calls)       # --version, gauntletInfo, gauntlet in both builds
        self.assertEqual(calls[2], f"core|gauntlet --continue --console=plain -Pgauntlet.baseRef=origin/main|"
                                   f"JAVA_HOME={jdk17}|GATE={jdk21}|java={jdk17}/bin/java")
        self.assertEqual(calls[5], f"adapter|gauntlet --continue --console=plain -Pgauntlet.baseRef=origin/main|"
                                   f"JAVA_HOME={jdk21}|GATE={jdk17}|java={jdk21}/bin/java")

    def test_plain_java_on_the_path_is_the_application_jvm(self):
        # setup-java leaves the LAST installed JDK first on PATH; a task running `java` must get the project JVM
        ws = self.planned("", [[".", "17", "21"]])
        env = ws.env()
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main", PATH=ws.jdk(21) + "/bin:" + env["PATH"])
        self.assertEqual(r.code, 0, r)
        self.assertTrue(all(c.endswith(f"java={ws.jdk(17)}/bin/java") for c in ws.called()), ws.called())

    def test_missing_module_fails_and_never_runs_the_root_wrapper(self):
        ws = self.planned("", [["missing-module", "17", "21"]])       # the root has a working wrapper
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main")
        self.assertEqual(r.code, 1, r)
        self.assertEqual(ws.called(), [])
        self.assertIn("::error::guarded build 'missing-module'", r.out)

    def test_missing_module_does_not_hide_the_other_builds(self):
        ws = self.planned("core", [["missing-module", "17", "21"], ["core", "17", "21"]])
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main")
        self.assertEqual(r.code, 1, r)
        self.assertEqual([c.split("|")[0] for c in ws.called()], ["core"] * 3)

    def test_red_build_fails_the_job_but_the_next_build_still_runs(self):
        ws = self.planned("core,adapter", [["core", "17", "21"], ["adapter", "17", "21"]])
        kit.write(os.path.join(ws.root, "core", "fail"), "")
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main")
        self.assertEqual(r.code, 1, r)
        self.assertEqual([c.split("|")[0] for c in ws.called()], ["core"] + ["adapter"] * 3)

    def test_version_without_an_installed_jdk_fails(self):
        ws = self.planned("", [[".", "11", "21"]])
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main")
        self.assertEqual(r.code, 1, r)
        self.assertEqual(ws.called(), [])
        self.assertIn("::error::no JDK 11", r.out)

    def test_empty_plan_is_not_a_green_job(self):
        ws = self.planned("", [])
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main")
        self.assertEqual(r.code, 1, r)
        self.assertIn("::error::no guarded build ran", r.out)


if __name__ == "__main__":
    unittest.main()
