""".github/workflows/gauntlet-kit.yml: the pull request check "gauntlet kit unchanged".

The guard hook keeps agents out of the kit by reading their commands, and no reading of commands is complete. This
workflow judges the result: a pull request that changes, relative to its merge base, a path the guard protects as
human-owned is red, and the human decides. Its shell step runs here as the runner runs it (`bash -e`), in a full clone
of the default branch - what actions/checkout leaves - against a throwaway origin that holds the base branches and
each pull request only as refs/pull/<n>/head, the way GitHub keeps the head of a fork's pull request.
"""
import ast
import os
import re
import subprocess
import tempfile
import unittest

import kit
import test_ci_workflow as ci

STEP = "Compare the pull request with its merge base"
IDENTITY = ("-c", "user.email=t@example.com", "-c", "user.name=t")
# the default branch with the kit installed: every path the guard protects, and some it does not
INSTALLED = {
    "gauntlet/config/gauntlet.properties": "crap.threshold=8\n",
    "gauntlet/tools/CrapGate.java": "class CrapGate {}\n",
    "gauntlet/hooks/guard.py": "print('guard')\n",
    ".claude/settings.json": "{}\n",
    "CLAUDE.md": "@gauntlet/CLAUDE.md\n",
    ".github/workflows/gauntlet.yml": "name: gauntlet\n",
    ".github/workflows/gauntlet-kit.yml": "name: gauntlet kit\n",
    "README.md": "# service\n",
    "core/CLAUDE.md": "# core module\n",
    "src/main/java/App.java": "class App {}\n",
    "src/main/java/Helper.java": "class Helper {}\n",
}
KIT_PATHS = ("gauntlet", ".claude", "CLAUDE.md", ".github")


def workflow():
    return ci.workflow("gauntlet-kit.yml")


def git(cwd, *args):
    r = subprocess.run(["git", *IDENTITY, *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert r.returncode == 0, f"git {' '.join(args)}: {r.stdout}"
    return r.stdout.strip()


def write(root, files):
    for rel, text in files.items():
        kit.write(os.path.join(root, rel), text)


class Origin:
    """A bare origin whose default branch has the kit; pull requests exist only as refs/pull/<n>/head."""

    def __init__(self, tmp):
        self.tmp = tmp
        self.bare = os.path.join(tmp, "origin.git")
        self.work = os.path.join(tmp, "author")
        self.numbers = iter(range(1, 1000))
        git(tmp, "init", "-q", "--bare", "-b", "main", self.bare)       # main is the default branch
        git(tmp, "init", "-q", "-b", "main", self.work)
        write(self.work, INSTALLED)
        os.chmod(os.path.join(self.work, "gauntlet/hooks/guard.py"), 0o755)
        git(self.work, "add", "-A")
        self.commit("the kit is installed")
        git(self.work, "push", "-q", self.bare, "main")

    def commit(self, message):
        git(self.work, "commit", "-q", "--allow-empty", "-m", message)     # each change stages what it changed
        return git(self.work, "rev-parse", "HEAD")

    def branch(self, name, start, change):
        """A base branch other than main: `change` committed on top of start."""
        git(self.work, "checkout", "-q", "-f", "-B", name, start)
        change(self.work)
        self.commit("base " + name)
        git(self.work, "push", "-q", "-f", self.bare, f"{name}:refs/heads/{name}")

    def pull_request(self, *changes, start="main"):
        """Commits each change on top of start and publishes the last commit as the head of a new pull request."""
        git(self.work, "checkout", "-q", "-f", "--detach", start)
        shas = []
        for change in changes:
            change(self.work)
            shas.append(self.commit("change"))
        number = next(self.numbers)
        git(self.work, "push", "-q", self.bare, f"HEAD:refs/pull/{number}/head")
        return number, shas

    def run(self, number, head_sha, base="main", report=False):
        """The step in a fresh clone of the default branch: what actions/checkout leaves with fetch-depth: 0, no ref.
        With report, a stand-in gh records how the step creates the check run (r.reported: its arguments)."""
        root = tempfile.mkdtemp(dir=self.tmp)
        checkout = os.path.join(root, "checkout")
        git(root, "clone", "-q", self.bare, checkout)
        script = kit.write(os.path.join(root, "step.sh"), ci.step_script(STEP, workflow()))
        summary = os.path.join(root, "summary.md")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(PR_NUMBER=str(number), BASE_BRANCH=base, HEAD_SHA=head_sha, FETCH_TOKEN="",
                   GITHUB_STEP_SUMMARY=summary, RUNNER_TEMP=root, REPORT_TOKEN="", GITHUB_REPOSITORY="owner/repo")
        calls = os.path.join(root, "gh-calls")
        if report:
            stub = os.path.join(root, "bin")
            os.makedirs(stub)
            os.chmod(kit.write(os.path.join(stub, "gh"), "#!/usr/bin/env bash\n"
                               "for a in \"$@\"; do case $a in output*=@*) printf '%s\\0' \"${a%%=@*}=$(cat \"${a#*=@}\")\";;"
                               " *) printf '%s\\0' \"$a\";; esac; done >> \"$GH_CALLS\"\n"
                               "printf 'TOKEN=%s\\0' \"$GH_TOKEN\" >> \"$GH_CALLS\"\n"), 0o755)
            env.update(PATH=stub + os.pathsep + env["PATH"], REPORT_TOKEN="t0ken", GH_CALLS=calls)
        r = kit.run(["bash", "--noprofile", "--norc", "-e", script], cwd=checkout, env=env)
        r.reported = kit.read(calls).split("\0")[:-1] if os.path.exists(calls) else []
        r.summary = kit.read(summary) if os.path.exists(summary) else ""
        r.checkout = checkout
        return r


def edit(rel, text):
    def change(work):
        kit.write(os.path.join(work, rel), text)
        git(work, "add", "--", rel)
    return change


def blob(rel, text):
    """A file added through the index only: its name may be one the file system cannot hold apart from another (a
    letter case on macOS) or at all (a line break)."""
    def change(work):
        sha = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=work, input=text, stdout=subprocess.PIPE,
                             text=True, check=True).stdout.strip()
        git(work, "update-index", "--add", "--cacheinfo", f"100644,{sha},{rel}")
    return change


def run_git(*args):
    return lambda work: git(work, *args)


class KitCheck(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.origin = Origin(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, *changes, start="main", base="main"):
        number, shas = self.origin.pull_request(*changes, start=start)
        return self.origin.run(number, shas[-1], base)

    def assert_red(self, r, *lines):
        self.assertEqual(r.code, 1, r)
        self.assertIn("::error title=gauntlet kit changed::", r.out)
        for line in lines:
            self.assertIn("  " + line + "\n", r.out + "\n", r)
            self.assertIn(line + "\n", r.summary)
        self.assertIn("The human decides", r.summary)

    def assert_green(self, r):
        self.assertEqual(r.code, 0, r)
        self.assertNotIn("::error", r.out)
        self.assertEqual(r.summary, "")

    def test_no_kit_change(self):
        self.assert_green(self.check(edit("README.md", "# service, renamed\n")))

    def test_change_only_in_the_code(self):
        r = self.check(edit("src/main/java/App.java", "class App { int x; }\n"),
                       edit("src/main/java/Price.java", "class Price {}\n"))
        self.assert_green(r)
        self.assertIn("No gauntlet kit file changed", r.out)

    def test_changed_threshold(self):
        self.assert_red(self.check(edit("gauntlet/config/gauntlet.properties", "crap.threshold=30\n")),
                        "modified     gauntlet/config/gauntlet.properties")

    def test_claude_settings(self):
        self.assert_red(self.check(edit(".claude/settings.json", '{"disableAllHooks": true}\n')),
                        "modified     .claude/settings.json")

    def test_root_claude_md(self):
        self.assert_red(self.check(edit("CLAUDE.md", "# no gauntlet\n")), "modified     CLAUDE.md")

    def test_module_claude_md_is_not_the_kit(self):
        # the guard protects the root CLAUDE.md only: core/CLAUDE.md is the module's own description
        self.assert_green(self.check(edit("core/CLAUDE.md", "# core module, described\n")))

    def test_rename_into_the_kit(self):
        r = self.check(run_git("mv", "src/main/java/Helper.java", "gauntlet/tools/Helper.java"))
        self.assert_red(r, "renamed      src/main/java/Helper.java -> gauntlet/tools/Helper.java")

    def test_rename_out_of_the_kit(self):
        r = self.check(run_git("mv", "gauntlet/tools/CrapGate.java", "src/main/java/CrapGate.java"))
        self.assert_red(r, "renamed      gauntlet/tools/CrapGate.java -> src/main/java/CrapGate.java")

    def test_deleted_kit_file(self):
        self.assert_red(self.check(run_git("rm", "-q", "gauntlet/tools/CrapGate.java")),
                        "deleted      gauntlet/tools/CrapGate.java")

    def test_mode_change(self):
        def chmod(work):
            os.chmod(os.path.join(work, "gauntlet/hooks/guard.py"), 0o644)
            git(work, "add", "--", "gauntlet/hooks/guard.py")
        self.assert_red(self.check(chmod), "modified     gauntlet/hooks/guard.py (mode 100755 -> 100644)")

    def test_type_change(self):
        def link(work):
            os.remove(os.path.join(work, ".claude/settings.json"))
            os.symlink("../src/settings.json", os.path.join(work, ".claude/settings.json"))
            git(work, "add", "--", ".claude/settings.json")
        self.assert_red(self.check(link), "type changed .claude/settings.json (mode 100644 -> 120000)")

    def test_workflows_and_codeowners(self):
        for rel in (".github/workflows/gauntlet.yml", ".github/workflows/gauntlet-kit.yml", "CODEOWNERS",
                    ".github/CODEOWNERS", ".gitlab/CODEOWNERS"):
            with self.subTest(rel=rel):
                action = "modified" if rel.startswith(".github/workflows/") else "added   "
                self.assert_red(self.check(edit(rel, "# changed by the pull request\n")), f"{action}     {rel}")

    def test_another_workflow_is_not_the_kit(self):
        self.assert_green(self.check(edit(".github/workflows/release.yml", "name: release\n")))

    def test_letter_case_as_the_guard_compares(self):
        # the guard compares paths without regard to case (macOS and Windows check out one file for both)
        for rel in (".Claude/settings.local.json", "Gauntlet/config/gauntlet.properties", "claude.md", "codeowners"):
            with self.subTest(rel=rel):
                self.assert_red(self.check(blob(rel, "x\n")), f"added        {rel}")

    def test_several_changes_are_all_listed(self):
        r = self.check(edit("gauntlet/config/gauntlet.properties", "crap.threshold=30\n"),
                       edit("src/main/java/App.java", "class App { int y; }\n"),
                       run_git("rm", "-q", "CLAUDE.md"))
        self.assert_red(r, "modified     gauntlet/config/gauntlet.properties", "deleted      CLAUDE.md")
        self.assertNotIn("App.java", r.out)

    def test_kit_installation(self):
        def without_kit(work):
            git(work, "rm", "-rq", *KIT_PATHS)
        self.origin.branch("plain", "main", without_kit)
        r = self.check(run_git("checkout", "main", "--", *KIT_PATHS), start="plain", base="plain")
        self.assertEqual(r.code, 0, r)
        self.assertIn("::notice title=gauntlet kit::plain has no gauntlet/config/gauntlet.properties: the kit is not "
                      "installed there", r.out)
        self.assertNotIn("::error", r.out)

    def test_kit_change_on_the_base_after_the_branch_point_is_not_the_pull_request_s(self):
        # the human changed a threshold on the base branch after the pull request branched off: comparing with the
        # base itself would blame the pull request for it, the merge base does not
        number, shas = self.origin.pull_request(edit("src/main/java/App.java", "class App { int z; }\n"))
        self.origin.branch("moved", "main", edit("gauntlet/config/gauntlet.properties", "crap.threshold=6\n"))
        self.assertIn("gauntlet/config/gauntlet.properties",
                      git(self.origin.work, "diff", "--name-only", "moved", shas[-1]))
        self.assert_green(self.origin.run(number, shas[-1], base="moved"))
        merged, shas = self.origin.pull_request(run_git("merge", "-q", "--no-edit", "moved"),
                                                edit("src/main/java/App.java", "class App { int w; }\n"),
                                                start=shas[-1])
        self.assert_green(self.origin.run(merged, shas[-1], base="moved"))

    def test_judges_the_commit_the_event_names(self):
        number, shas = self.origin.pull_request(edit("gauntlet/config/gauntlet.properties", "crap.threshold=30\n"),
                                                edit("gauntlet/config/gauntlet.properties", "crap.threshold=8\n"))
        self.assert_red(self.origin.run(number, shas[0]), "modified     gauntlet/config/gauntlet.properties")
        self.assert_green(self.origin.run(number, shas[1]))
        self.assert_green(self.origin.run(number, "0" * 40))      # pushed away since: the head as it is now

    def assert_reported(self, r, conclusion, head_sha):
        """The verdict reached the pull request's head commit as the check run the branch protection requires."""
        args = r.reported
        self.assertEqual(args[:4], ["api", "--silent", "-X", "POST"], args)
        self.assertEqual(args[4], "repos/owner/repo/check-runs")
        self.assertIn("name=gauntlet kit unchanged", args)
        self.assertIn(f"head_sha={head_sha}", args)
        self.assertIn("status=completed", args)
        self.assertIn(f"conclusion={conclusion}", args)
        self.assertIn("TOKEN=t0ken", args)
        return next(a for a in args if a.startswith("output[summary]="))

    def test_the_verdict_is_a_check_run_on_the_pull_request_head(self):
        # pull_request_target's own check run belongs to the default branch's commit, where the pull request's
        # required checks are not looked for: the verdict is reported on the head commit the event names
        number, shas = self.origin.pull_request(edit("gauntlet/config/gauntlet.properties", "crap.threshold=99\n"))
        r = self.origin.run(number, shas[-1], report=True)
        self.assertEqual(r.code, 1, r)
        summary = self.assert_reported(r, "failure", shas[-1])
        self.assertIn("gauntlet/config/gauntlet.properties", summary)
        self.assertIn("The human decides", summary)
        number, shas = self.origin.pull_request(edit("src/main/java/A.java", "class A { int x; }\n"))
        r = self.origin.run(number, shas[-1], report=True)
        self.assertEqual(r.code, 0, r)
        self.assertIn("No gauntlet kit file changed", self.assert_reported(r, "success", shas[-1]))

    def test_without_a_token_the_check_run_is_not_created_and_the_job_still_judges(self):
        number, shas = self.origin.pull_request(edit("gauntlet/config/gauntlet.properties", "crap.threshold=98\n"))
        r = self.origin.run(number, shas[-1])
        self.assertEqual(r.code, 1, r)
        self.assertIn("::warning title=gauntlet kit::no token or no gh", r.out)
        self.assertEqual(r.reported, [])

    def test_history_without_a_merge_base(self):
        def orphan(work):
            git(work, "checkout", "-q", "--orphan", "unrelated")
            git(work, "rm", "-rqf", ".")
            edit("README.md", "# another history\n")(work)
        r = self.check(orphan)
        self.assertEqual(r.code, 1, r)
        self.assertIn("::error title=gauntlet kit::the pull request has no merge base with main", r.out)

    def test_line_break_in_a_file_name_starts_no_workflow_command(self):
        rel = "gauntlet/notes\n::notice title=gauntlet kit::nothing changed"
        r = self.check(blob(rel, "x\n"))
        self.assertEqual(r.code, 1, r)
        self.assertIn("  added        gauntlet/notes?::notice title=gauntlet kit::nothing changed\n", r.out)
        self.assertFalse(any(line.startswith("::notice") for line in r.out.splitlines()), r.out)

    def test_pull_request_is_never_checked_out(self):
        r = self.check(edit("gauntlet/config/gauntlet.properties", "crap.threshold=30\n"),
                       edit("src/main/java/Only.java", "class Only {}\n"))
        self.assertEqual(r.code, 1, r)
        self.assertEqual(git(r.checkout, "rev-parse", "HEAD"), git(self.origin.bare, "rev-parse", "main"))
        self.assertEqual(git(r.checkout, "status", "--porcelain"), "")
        self.assertFalse(os.path.exists(os.path.join(r.checkout, "src/main/java/Only.java")))
        self.assertEqual(kit.read(os.path.join(r.checkout, "gauntlet/config/gauntlet.properties")), "crap.threshold=8\n")


class WorkflowText(unittest.TestCase):
    """What the workflow may do with the base repository's token: read, and never run the pull request."""

    def setUp(self):
        self.text = workflow()
        self.script = ci.step_script(STEP, self.text)
        # the code without comments and without the lines that only print text
        self.code = "\n".join(line for line in re.sub(r"(?m)(^|\s)#.*$", "", self.script).splitlines()
                              if not line.strip().startswith("echo "))

    def test_the_default_branch_version_runs_on_every_pull_request(self):
        # pull_request would run the pull request's own copy of this file - one that can switch the check off
        self.assertRegex(self.text, r"\non:\n  pull_request_target:\n    types: \[opened, synchronize, reopened, edited\]")
        self.assertNotRegex(self.text, r"\n  pull_request:")
        self.assertNotRegex(self.text, r"\n    (paths|paths-ignore|branches|branches-ignore):")   # required: always reports
        self.assertRegex(self.text, r"\n    name: kit files +#")      # the required check is the check run it creates
        self.assertIn("-f name='gauntlet kit unchanged' -f head_sha=\"$sha\"", self.script)

    def test_the_token_reads_the_code_and_writes_only_the_check(self):
        self.assertEqual(self.text.count("permissions:"), 1)              # no job widens it
        granted = self.text.split("permissions:")[1].split("\nconcurrency:")[0]
        scopes = re.findall(r"(?m)^  ([\w-]+): (\S+)", granted)
        self.assertEqual(scopes, [("contents", "read"), ("checks", "write")])

    def test_nothing_of_the_pull_request_is_checked_out(self):
        self.assertEqual(re.findall(r"uses: (\S+)", self.text), ["actions/checkout@v4"])
        checkout = re.search(r"uses: actions/checkout@v4[^\n]*\n((?:        [^\n]*\n)+)", self.text).group(1)
        self.assertRegex(checkout, r"persist-credentials: false\b")
        self.assertRegex(checkout, r"fetch-depth: 0\b")
        self.assertNotIn("ref:", checkout)
        commands = set(re.findall(r'\bgit (?:"\$\{auth\[@\]\}" )?([a-z-]+)', self.code))
        self.assertEqual(commands, {"fetch", "cat-file", "merge-base", "diff", "rev-parse"})

    def test_no_build_and_no_script_of_the_project_runs(self):
        self.assertEqual(len(re.findall(r"\n      - ", self.text)), 2)       # the checkout and this step
        self.assertEqual(self.text.count("run:"), 1)
        self.assertEqual(re.findall(r"\b(?:gradlew?|python3?|node|npm|make|mvn|source|eval|sh|bash|java)\b|\./",
                                    self.code), [])
        self.assertEqual(set(re.findall(r"\$\(\s*([\w-]+)", self.code)), {"printf", "git", "mktemp", "shown"})
        self.assertEqual(re.findall(r"\bgh (\w+)", self.code), ["api"])     # gh only reports the verdict
        self.assertNotIn("${{", self.script)        # event values reach the script as data, through env

    def test_protects_what_the_guard_protects(self):
        # one list for the hook and the check: HUMAN_OWNED of the guard, but .git/, which never appears in a diff
        source = kit.read(os.path.join(kit.kit(), "gauntlet", "hooks", "guard.py"))
        guard = next(ast.literal_eval(node.value) for node in ast.parse(source).body if isinstance(node, ast.Assign)
                     and any(getattr(t, "id", None) == "HUMAN_OWNED" for t in node.targets))
        owned = re.search(r"\nowned=\(([^)]*)\)", self.script).group(1).split()
        self.assertEqual(sorted(owned), sorted(set(guard) - {".git/"}))
        self.assertIn(".github/workflows/gauntlet-kit.yml", owned)          # the check protects itself


if __name__ == "__main__":
    unittest.main()
