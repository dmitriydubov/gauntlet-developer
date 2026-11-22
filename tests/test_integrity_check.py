"""IntegrityCheck.java: every rule fires on its trick, and switching a packaging task off is not one of them."""
import os
import tempfile
import unittest

import kit

APPLY = "apply from: 'gauntlet/gauntlet.gradle'\n"


class IntegrityCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.file("build.gradle", APPLY)

    def file(self, rel, text, encoding="utf-8"):
        return kit.write(os.path.join(self.root, rel), text, encoding)

    def check(self, *args):
        return kit.tool("IntegrityCheck", "--root", self.root, *args)

    def findings(self, *args):
        """[(rule, path:line)] in report order."""
        out = self.check(*args).out
        return [(l.split()[1], l.split()[2]) for l in out.splitlines() if l.startswith("INTEGRITY ") and ":" in l.split()[2]]

    def rules(self, *args):
        return [rule for rule, _ in self.findings(*args)]


class Rules(IntegrityCase):

    def test_clean_project(self):
        self.file("src/test/java/a/OrderTest.java", "class OrderTest { @Test void works() { } }\n")
        r = self.check()
        self.assertEqual(r.code, 0, r)
        self.assertIn("Integrity check: OK", r.out)

    def test_test_tricks(self):
        cases = {"T1": "@Disabled(\"later\")", "T2": "@EnabledIfSystemProperty(named = \"x\", matches = \"y\")",
                 "T3": "@Ignore", "T4": "assumeTrue(ready);", "T5": "@Testcontainers(disabledWithoutDocker = true)"}
        for rule, line in cases.items():
            with self.subTest(rule=rule):
                self.file("src/test/java/a/T.java", f"class T {{\n    {line}\n}}\n")
                self.assertEqual(self.rules(), [rule])

    def test_other_assumption_forms(self):
        for line in ("Assumptions.assumeFalse(x);", "assumingThat(x, () -> { });", "abort(\"skip\");"):
            with self.subTest(line=line):
                self.file("src/acceptanceTest/java/a/Steps.java", f"class Steps {{ void s() {{ {line} }} }}\n")
                self.assertEqual(self.rules(), ["T4"])

    def test_production_tricks(self):
        cases = {"M1": "@lombok.Generated", "M2": "// CHECKSTYLE:OFF", "M3": "@SuppressWarnings(\"PMD.GodClass\")"}
        for rule, line in cases.items():
            with self.subTest(rule=rule):
                self.file("src/main/java/a/M.java", f"{line}\nclass M {{ }}\n")
                self.assertEqual(self.rules(), [rule])

    def test_generated_value_is_a_jpa_annotation_not_a_trick(self):
        self.file("src/main/java/a/M.java", "class M { @GeneratedValue long id; }\n")
        self.assertEqual(self.rules(), [])

    def test_commented_out_annotation_is_not_a_finding_but_a_suppression_comment_is(self):
        self.file("src/test/java/a/T.java", "class T {\n    // @Disabled\n}\n")
        self.file("src/main/java/a/M.java", "class M {\n    int x; // NOPMD\n}\n")
        self.assertEqual(self.rules(), [("M2")])

    def test_feature_tags(self):
        self.file("src/acceptanceTest/resources/features/a.feature", "Feature: a\n  @smoke @wip\n  Scenario: b\n")
        self.assertEqual(self.findings(), [("F1", "src/acceptanceTest/resources/features/a.feature:2")])

    def test_configured_features_directory(self):
        self.file("specs/features/a.feature", "@ignore\nFeature: a\n")
        self.assertEqual(self.rules("--features", "specs/features"), ["F1"])

    def test_build_script_tricks(self):
        cases = {"B1": "test { ignoreFailures = true }", "B2": "test { filter { excludeTestsMatching '*IT' } }",
                 "B3": "pitest { mutationThreshold = 10 }", "B4": "tasks.named('crapGate') { }",
                 "B5": "afterEvaluate { }"}
        for rule, line in cases.items():
            with self.subTest(rule=rule):
                self.file("build.gradle", APPLY + line + "\n")
                self.assertEqual(self.rules(), [rule])

    def test_build_logic_outside_the_build_script_is_scanned(self):
        self.file("buildSrc/src/main/groovy/Custom.gradle", "test.enabled = false\n")
        self.file("gradle/extra.gradle", "tasks.withType(Test) { onlyIf { false } }\n")
        self.file("settings.gradle", "includeBuild('../lib')\n")
        self.file("../lib/build.gradle", "test { enabled = false }\n")
        self.assertEqual(sorted(self.rules()), ["B1", "B1", "B1"])

    def test_test_properties_filtering_scenarios(self):
        self.file("src/acceptanceTest/resources/junit-platform.properties", "cucumber.filter.tags=not @slow\n")
        self.assertEqual(self.rules(), ["P1"])

    def test_missing_gauntlet_script_is_a_structural_finding(self):
        self.file("build.gradle", "plugins { id 'java' }\n")
        r = self.check()
        self.assertEqual(r.code, 1, r)
        self.assertIn("INTEGRITY build script does not apply gauntlet/gauntlet.gradle", r.out)

    def test_allowlist_accepts_a_finding_by_path_glob_and_rule(self):
        self.file("src/test/java/a/LegacyIT.java", "@Disabled\nclass LegacyIT { }\n")
        allow = self.file("allow.txt", "src/test/java/**/LegacyIT.java T1   # needs a real Oracle\n")
        r = self.check("--allowlist", allow)
        self.assertEqual(r.code, 0, r)
        self.assertIn("(1 allowlisted)", r.out)
        self.file("allow.txt", "src/test/java/**/LegacyIT.java T4\n")
        self.assertEqual(self.check("--allowlist", allow).code, 1)


class PackagingTasks(IntegrityCase):
    """B1 exempts `enabled = false` only where it switches off the packaging/doc task that encloses it."""

    FREE = {
        "bare assignment in the block": "jar { enabled = false }",
        "multi-line block": "jar {\n    enabled = false\n}",
        "brace closes on the next line": "jar { enabled = false\n}",
        "named task": "tasks.named('bootJar') {\n    enabled = false\n}",
        "typed lookup": "tasks.named(\"jar\", Jar) {\n    setEnabled(false)\n}",
        "own name": "jar {\n    jar.enabled = false\n}",
        "delegate": "tasks.named('jar') {\n    delegate.enabled = false\n}",
        "this": "javadoc {\n    this.enabled = false\n}",
        "implicit it": "tasks.named('jar') {\n    it.enabled = false\n}",
        "named parameter": "tasks.named('jar') { archive ->\n    archive.enabled = false\n}",
        "typed parameter": "tasks.named('jar') { final Jar archive ->\n    archive.enabled = false\n}",
        "parameter on the next line": "tasks.named('jar') {\n    Jar archive ->\n    archive.enabled = false\n}",
        "comment after the brace": "tasks.named('jar') { // packaging\n    Jar archive ->\n    archive.enabled = false\n}",
        "comment line before the parameter": "tasks.named('jar') {\n    // packaging\n    Jar archive ->\n    archive.enabled = false\n}",
        "block comment before the parameter": "tasks.named('jar') {\n    /* packaging */\n    Jar archive ->\n    archive.enabled = false\n}",
        "multi-line block comment": "tasks.named('jar') {\n    /*\n     * packaging\n     */\n    Jar archive ->\n    archive.enabled = false\n}",
        "block comment on the opener line": "tasks.named('jar') { /* packaging */ Jar archive ->\n    archive.enabled = false\n}",
        "single-line block with a comment": "tasks.named('jar') { /* x */ archive -> archive.enabled = false }",
    }
    B1 = {
        "the test task": "test { enabled = false }",
        "test inside jar": "jar { test.enabled = false }",
        "tasks.test inside jar": "jar {\n    tasks.test.enabled = false\n}",
        "named test inside jar": "jar {\n    tasks.named(\"test\").enabled = false\n}",
        "statement before the block": "test.enabled = false; jar { }",
        "statement after the block": "jar { }; test.enabled = false",
        "harmless name only mentioned": "test { dependsOn(jar); enabled = false }",
        "two blocks on one line": "jar { }; test { enabled = false }",
        "parameter named, test disabled": "tasks.named('jar') {\n    /* packaging */\n    Jar archive ->\n    test.enabled = false\n}",
        "parameter only inside a comment": "tasks.named('jar') {\n    /* archive -> */\n    archive.enabled = false\n}",
        "comment does not rename the block": "tasks.named('test') {\n    /* jar */\n    enabled = false\n}",
        "ignoreFailures is never exempt": "jar { ignoreFailures = true }",
        "onlyIf is never exempt": "jar { onlyIf { false } }",
    }

    def test_packaging_task_switched_off_is_free(self):
        for name, script in self.FREE.items():
            with self.subTest(name):
                self.file("build.gradle", APPLY + script + "\n")
                self.assertEqual(self.rules(), [])

    def test_everything_else_is_b1(self):
        for name, script in self.B1.items():
            with self.subTest(name):
                self.file("build.gradle", APPLY + script + "\n")
                self.assertIn("B1", self.rules())


class Encoding(IntegrityCase):
    LATIN = "package a;\n/** réduit */\n// CHECKSTYLE:OFF\nclass Tarifé { }\n"

    def test_non_utf8_source_does_not_stop_the_check(self):
        # a Latin-1 comment in a UTF-8 scan used to end the whole check with exit 2 (MalformedInputException)
        self.file("src/main/java/a/Tarifs.java", self.LATIN, "iso-8859-1")
        r = self.check()
        self.assertEqual(r.code, 1, r)
        self.assertEqual(self.rules(), ["M2"])

    def test_sources_are_read_with_the_project_encoding(self):
        self.file("src/main/java/a/Tarifs.java", self.LATIN, "utf-16")
        self.assertEqual(self.rules("--encoding", "UTF-16"), ["M2"])

    def test_unknown_charset_is_a_usage_error(self):
        self.assertEqual(self.check("--encoding", "no-such-charset").code, 2)


if __name__ == "__main__":
    unittest.main()
