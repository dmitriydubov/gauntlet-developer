"""The shell steps of .github/workflows/gauntlet.yml, run locally the way the runner runs them (`bash -e`).

GitHub Actions itself is not available here, so everything the steps take from the runner is stubbed: RUNNER_TEMP,
GITHUB_OUTPUT, the JAVA_HOME_<major>_<ARCH> variables setup-java exports, and ./gradlew.
"""
import os
import re
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

    def properties(self, text, module=""):
        """Replaces the common gauntlet.properties (or writes the module's overlay)."""
        kit.write(os.path.join(self.root, "gauntlet/config", module, "gauntlet.properties"), text)

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

    def test_setup_java_is_not_a_deprecated_major(self):
        # v1-v4 are deprecated upstream: v4 warns "setup-java v4 is deprecated ..." on every run
        major = re.search(r"uses: actions/setup-java@v(\d+)\n", workflow())
        self.assertIsNotNone(major)
        self.assertGreaterEqual(int(major.group(1)), 5)

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

    def test_colon_and_blank_separate_a_key_from_its_value_as_in_gradle(self):
        # gauntlet.gradle loads both files with java.util.Properties: `key: value` and `key value` are assignments
        ws = Workspace(self.tmp.name, "core,adapter")
        ws.properties("module=core,adapter\nproject.java.version: 17\ngate.java.version 21\n")
        ws.properties("project.java.version\t21\ngate.java.version : 25\r\n", "adapter")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["core", "17", "21"], ["adapter", "21", "25"]])

    def test_overlay_key_alone_on_its_line_assigns_nothing_and_still_wins(self):
        ws = Workspace(self.tmp.name, "core")
        ws.properties("gate.java.version\n", "core")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["core", "17", "17"]])

    def test_comment_or_longer_key_is_no_assignment(self):
        ws = Workspace(self.tmp.name)
        ws.properties("module=\nproject.java.version=17\ngate.java.version=21\n"
                      "# gate.java.version: 8\n! gate.java.version 8\ngate.java.version.note 8\ngate.java.versions: 8\n")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [[".", "17", "21"]])

    def test_last_assignment_wins_on_a_last_line_without_a_newline(self):
        ws = Workspace(self.tmp.name)
        ws.properties("module=\nproject.java.version=17\ngate.java.version=21\ngate.java.version=")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [[".", "17", "17"]])

    def test_two_spellings_of_one_major_stop_the_job(self):
        # setup-java exports ONE JAVA_HOME_21_<ARCH>: both 21.0.2 and 21 would run on whichever came last
        ws = Workspace(self.tmp.name)
        ws.properties("module=\nproject.java.version=21.0.2\ngate.java.version=21\n")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 1, r)
        self.assertIn("::error::Java 21 is asked for as '21.0.2' (project.java.version for '.') and as '21' "
                      "(gate.java.version for '.')", r.out)
        self.assertNotIn("GAUNTLET_EOF", ws.outputs())          # nothing is handed to setup-java

    def test_two_spellings_of_one_major_in_two_builds_name_both_builds(self):
        ws = Workspace(self.tmp.name, "core,adapter")
        ws.properties("project.java.version=17.0.2\n", "adapter")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 1, r)
        self.assertIn("::error::Java 17 is asked for as '17' (project.java.version for 'core') and as '17.0.2' "
                      "(project.java.version for 'adapter')", r.out)

    def test_one_spelling_of_a_major_is_installed_once_for_every_build_that_uses_it(self):
        ws = Workspace(self.tmp.name, "core,adapter")
        ws.properties("module=core,adapter\nproject.java.version=21.0.2\n")       # no gate version: the application's JDK
        ws.properties("project.java.version=17-ea\ngate.java.version=21.0.2\n", "adapter")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["core", "21.0.2", "21.0.2"], ["adapter", "17-ea", "21.0.2"]])
        self.assertIn("java<<GAUNTLET_EOF\n21.0.2\n17-ea\nGAUNTLET_EOF\n", ws.outputs())

    def test_old_1_x_notation_is_planned_in_the_notation_setup_java_takes(self):
        # setup-java rejects java-version 1.8 ("no matching version"): the plan and its output must say 8
        ws = Workspace(self.tmp.name, "core,adapter")
        ws.properties("module=core,adapter\nproject.java.version=1.8\ngate.java.version=21\n")
        ws.properties("project.java.version=8\n", "adapter")                         # the same JDK, no second spelling
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["core", "8", "21"], ["adapter", "8", "21"]])
        self.assertIn("java<<GAUNTLET_EOF\n8\n21\nGAUNTLET_EOF\n", ws.outputs())

    def test_version_that_does_not_begin_with_one_major_stops_the_job(self):
        # the run step finds a JDK by the major a version begins with: a range or a comment has none to offer
        for version in (">=17", "17 || 21", "17||21", "17 # LTS", "latest", "1.x"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                ws = Workspace(tmp)
                ws.properties(f"module=\nproject.java.version={version}\ngate.java.version=21\n")
                r = ws.step(PLAN)
                self.assertEqual(r.code, 1, r)
                self.assertIn(f"::error::project.java.version '{version}' for '.' is not one Java version", r.out)

    def test_module_directory_with_a_space_is_one_build(self):
        ws = Workspace(self.tmp.name, "order service, billing")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["order service", "17", "21"], ["billing", "17", "21"]])

    def test_module_list_is_split_as_the_hooks_split_it(self):
        # commas only; an entry is stripped of blanks and slashes, an empty one is none, nothing is a glob
        ws = Workspace(self.tmp.name)
        ws.properties("module= /svc/adapter/ ,, * ,./core\nproject.java.version=17\n")
        ws.properties("gate.java.version=21\n", "svc/adapter")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [["svc/adapter", "17", "21"], ["*", "17", "17"], ["./core", "17", "17"]])

    def test_module_list_of_empty_entries_is_the_root_build(self):
        ws = Workspace(self.tmp.name)
        ws.properties("module= , \nproject.java.version=17\n")
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        self.assertEqual(ws.plan(), [[".", "17", "17"]])


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

    def test_configured_base_is_read_with_the_separators_gradle_reads(self):
        for line in ("baseRef: origin/release", "baseRef origin/release", "baseRef\t:\torigin/release\r"):
            with self.subTest(line=line):
                self.ws.properties(f"module=\nbaseRef=origin/develop\n{line}\nproject.java.version=17\n")
                if os.path.exists(self.ws.output):
                    os.remove(self.ws.output)
                r = self.ws.step(BASE, BASE_REF="")
                self.assertEqual(r.code, 0, r)
                self.assertEqual(self.ws.outputs(), "ref=origin/release\n")


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

    def test_jdk_is_found_by_the_major_a_version_begins_with(self):
        # setup-java names the variable after the major alone: 17-ea, 21.0.2 and 8.0.282+8 live in JAVA_HOME_17/21/8
        ws = self.planned("core,adapter", [["core", "17-ea", "21.0.2"], ["adapter", "8.0.282+8", "17-ea"]])
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main", jdks=(8, 17, 21))
        self.assertEqual(r.code, 0, r)
        calls = ws.called()
        self.assertEqual(len(calls), 6, calls)
        self.assertTrue(calls[2].endswith(f"|JAVA_HOME={ws.jdk(17)}|GATE={ws.jdk(21)}|java={ws.jdk(17)}/bin/java"), calls[2])
        self.assertTrue(calls[5].endswith(f"|JAVA_HOME={ws.jdk(8)}|GATE={ws.jdk(17)}|java={ws.jdk(8)}/bin/java"), calls[5])

    def test_major_is_not_a_prefix_of_another_major(self):
        ws = self.planned("", [[".", "1", "21"]])                     # JAVA_HOME_17_X64 is no JDK 1
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main")
        self.assertEqual(r.code, 1, r)
        self.assertEqual(ws.called(), [])
        self.assertIn("::error::no JDK 1 for '.'", r.out)


class PlannedRun(unittest.TestCase):
    """The plan step's own plan handed to the run step, with the variables setup-java would export for it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_planned(self, ws, jdks):
        r = ws.step(PLAN)
        self.assertEqual(r.code, 0, r)
        r = ws.step(RUN, GAUNTLET_BASE_REF="origin/main", jdks=jdks)
        self.assertEqual(r.code, 0, r)
        return [c.split("|") for c in ws.called()]

    def test_early_access_version(self):
        # setup-java installs 17-ea as JAVA_HOME_17_<ARCH>
        ws = Workspace(self.tmp.name)
        ws.properties("module=\nproject.java.version=17-ea\ngate.java.version=21\n")
        calls = self.run_planned(ws, (17, 21))
        self.assertIn("java<<GAUNTLET_EOF\n17-ea\n21\nGAUNTLET_EOF\n", ws.outputs())
        self.assertEqual(len(calls), 3, calls)
        self.assertEqual(calls[2][2:4], [f"JAVA_HOME={ws.jdk(17)}", f"GATE={ws.jdk(21)}"])

    def test_java_8_written_as_1_8(self):
        ws = Workspace(self.tmp.name)
        ws.properties("module=\nproject.java.version=1.8\ngate.java.version=21\n")
        calls = self.run_planned(ws, (8, 21))
        self.assertIn("java<<GAUNTLET_EOF\n8\n21\nGAUNTLET_EOF\n", ws.outputs())     # setup-java knows no 1.8
        self.assertEqual(len(calls), 3, calls)
        self.assertEqual(calls[2][2:4], [f"JAVA_HOME={ws.jdk(8)}", f"GATE={ws.jdk(21)}"])

    def test_module_directory_with_a_space(self):
        ws = Workspace(self.tmp.name, "order service,billing")
        calls = self.run_planned(ws, (17, 21))
        self.assertEqual([c[0] for c in calls], ["order service"] * 3 + ["billing"] * 3)


if __name__ == "__main__":
    unittest.main()
