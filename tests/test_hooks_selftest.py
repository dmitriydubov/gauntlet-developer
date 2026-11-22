"""The hooks' own selftest (guard, Stop gate, SessionStart), run from the unpacked bundle."""
import os
import re
import sys
import unittest

import kit


@unittest.skipIf(os.environ.get("GAUNTLET_SKIP_SELFTEST"), "skipped by --fast")
class HooksSelftest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_PROJECT_DIR", "GAUNTLET_G", "GAUNTLET_S"))}
        cls.result = kit.run([sys.executable, os.path.join(kit.kit(), "gauntlet", "hooks", "selftest.py")], env=env)
        cls.summary = re.search(r"^(\d+) passed, (\d+) failed$", cls.result.out, re.M)

    def test_no_check_fails(self):
        self.assertIsNotNone(self.summary, self.result)
        self.assertEqual((self.result.code, self.summary.group(2)), (0, "0"), self.result.out[-3000:])

    def test_all_three_layouts_run(self):
        for layout in ("build at the repository root", "builds in modules core", "builds in modules core, adapter"):
            self.assertIn("layout: " + layout + "\n", self.result.out + "\n")

    def test_kit_readme_states_the_real_number_of_checks(self):
        readme = kit.read(os.path.join(kit.kit(), "gauntlet", "README.md"))
        self.assertIn(f"`hooks/selftest.py`, {self.summary.group(1)} провер", readme)

    def test_selftest_leaves_the_kit_untouched(self):
        leftovers = [d for d, _, _ in os.walk(kit.kit()) if os.path.basename(d) == "__pycache__"]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
