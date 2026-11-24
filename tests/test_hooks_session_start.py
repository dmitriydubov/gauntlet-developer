"""gauntlet/hooks/session_start.sh reads baseRef as everything else reads gauntlet.properties.

gauntlet.gradle loads the file with java.util.Properties, where `=`, `:` or blanks end a key; CI and the Stop hook read
it the same way. The SessionStart hook took only `baseRef=`: with `baseRef: origin/release` it fetched and reported
origin/main, and a cloud session's scoped checks ran against a base branch the clone had never fetched.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

import kit


def git(cwd, *args):
    r = kit.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args], cwd=cwd)
    assert r.code == 0, f"git {' '.join(args)}: {r.out}"
    return r.out.strip()


class BaseRef(unittest.TestCase):

    def session_start(self, line):
        """The hook in a cloud session's single-branch clone of main; the base branch `release` is not fetched yet."""
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            os.makedirs(source)
            git(source, "init", "-q", "-b", "main")
            shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(source, "gauntlet"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            props = os.path.join(source, "gauntlet", "config", "gauntlet.properties")
            kit.write(props, kit.read(props) + line + "\n")
            # modules a hook must never import from the project directory
            kit.write(os.path.join(source, "stop_gate.py"), "raise SystemExit('the project directory was imported')\n")
            kit.write(os.path.join(source, "re.py"), "raise SystemExit('the project directory was imported')\n")
            git(source, "add", "-A")
            git(source, "commit", "-q", "-m", "base")
            git(source, "branch", "release")
            git(tmp, "clone", "-q", "--bare", source, "origin.git")
            clone = os.path.join(tmp, "clone")
            git(tmp, "clone", "-q", "--single-branch", "--branch", "main", os.path.join(tmp, "origin.git"), clone)
            self.assertNotIn("origin/release", git(clone, "branch", "-r"))
            env = {k: v for k, v in os.environ.items() if not k.startswith(("GAUNTLET_", "CLAUDE_"))}
            env.update(CLAUDE_PROJECT_DIR=clone, CLAUDE_CODE_REMOTE="true", GAUNTLET_DOCKER="off")
            r = subprocess.run(["bash", os.path.join(clone, "gauntlet", "hooks", "session_start.sh")], cwd=clone,
                               input='{"session_id": "s"}', stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               env=env)
            fetched = "origin/release" in git(clone, "branch", "-r")
            bytecode = [d for d, _, _ in os.walk(os.path.join(clone, "gauntlet")) if d.endswith("__pycache__")]
            return r, fetched, bytecode

    def test_separators_java_util_properties_reads(self):
        for line in ("baseRef=origin/release", "baseRef: origin/release", "baseRef origin/release",
                     "baseRef\t:\torigin/release\r", "baseRef = origin/main\nbaseRef:origin/release"):
            with self.subTest(line=line):
                r, fetched, bytecode = self.session_start(line)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("[gauntlet] active - scope: changed vs origin/release;", r.stdout)
                self.assertTrue(fetched, "the hook fetched another branch than baseRef names:\n" + r.stdout)
                self.assertEqual(bytecode, [])          # reading the setting leaves nothing in gauntlet/

    def test_empty_or_absent_value_is_the_default(self):
        # gauntlet.gradle falls back to origin/main for an empty value too
        for line in ("baseRef=origin/release\nbaseRef=", "baseRef=origin/release\nbaseRef", "# baseRef: origin/x"):
            with self.subTest(line=line):
                r, fetched, _ = self.session_start(line)
                self.assertIn("[gauntlet] active - scope: changed vs origin/main;", r.stdout)
                self.assertFalse(fetched)


if __name__ == "__main__":
    unittest.main()
