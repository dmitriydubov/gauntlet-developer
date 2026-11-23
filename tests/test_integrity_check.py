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

    def test_qualified_annotations(self):
        cases = {"T1": "@org.junit.jupiter.api.Disabled", "T3": "@org.junit.Ignore",
                 "T2": "@org.junit.jupiter.api.condition.EnabledIfSystemProperty(named = \"x\", matches = \"y\")"}
        for rule, line in cases.items():
            with self.subTest(rule=rule):
                self.file("src/test/java/a/T.java", f"class T {{\n    {line}\n    void works() {{ }}\n}}\n")
                self.assertEqual(self.rules(), [rule])

    def test_annotation_as_javac_reads_it(self):
        # javac translates Unicode escapes first and drops ignorable characters from names: both compile as @Disabled
        for line in ("@Dis" + chr(92) + "u0061bled", "@Dis\u00adabled"):
            with self.subTest(line=line):
                self.file("src/test/java/a/T.java", f"class T {{\n    {line}\n    void works() {{ }}\n}}\n")
                self.assertEqual(self.rules(), ["T1"])

    def test_annotation_in_a_string_or_a_block_comment_is_none(self):
        self.file("src/test/java/a/T.java", "class T {\n    String s = \"@Disabled\";\n    /* @Disabled */ void works() { }\n}\n")
        self.assertEqual(self.rules(), [])

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

    def test_a_property_named_by_a_string_is_a_finding(self):
        # Groovy reaches a property through a string as well, so the build rules read strings too; a string that only
        # mentions the words is reported as well - the safe direction, the human allowlists it
        cases = {"B1": "test['ignoreFailures'] = true", "B2": "test.filter.\"excludeTestsMatching\"('*Slow*')",
                 "B3": "test.systemProperty 'cucumber.filter.tags', 'not @slow'"}
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
        "a glob after the parameter": "tasks.withType(Jar).configureEach { t -> t.exclude('**/*.sql'); t.enabled = false }",
        "a glob on the parameter's line": "tasks.named('jar') { Jar archive -> archive.exclude '**/*.sql'\n    archive.enabled = false\n}",
        "many comment lines before the parameter":
            "tasks.named('jar') {\n" + "    // packaging note\n" * 25 + "    Jar archive ->\n    archive.enabled = false\n}",
        "a brace in a string inside the block": "jar {\n    manifest { attributes('X-Note': '}') }\n    enabled = false\n}",
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
        # what looks like a comment before a parameter, but is not one to Groovy
        "a dollar-slashy string is no comment": "tasks.withType(Jar) { $/* packaging */ test -> /$\n    test.enabled = false\n}",
        # the parameter's name does not make the real task harmless
        "parameter named test, tasks.test disabled": "tasks.withType(Jar) { /* packaging */ test ->\n    tasks.test.enabled = false\n}",
        "parameter named test, test looked up": "jar { test ->\n    tasks.getByName('test').enabled = false\n}",
        # the enclosing block is the one that is really open, on text without comments and strings
        "a commented-out opener": "test {\n    // tasks.named('jar') {\n    enabled = false\n}",
        "a packaging block closed before the opener's brace": "jar { }; test {\n    enabled = false\n}",
        "a block comment before the statement": "test {\n    /* tmp */ enabled = false\n}",
        "a string that names jar": "test {\n    def note = 'jar {'\n    enabled = false\n}",
    }
    KOTLIN_FREE = {
        "the jar accessor": "tasks.jar {\n    enabled = false\n}",
        "the bootJar accessor": "tasks.bootJar { enabled = false }",
        "the accessor through project": "project.tasks.jar { enabled = false }",
        "named with a type": "tasks.named<Jar>(\"jar\") {\n    enabled = false\n}",
    }
    KOTLIN_B1 = {
        "the test accessor": "tasks.test { enabled = false }",
        # Kotlin block comments nest: the whole first line is one comment, there is no parameter
        "a nested comment hides no parameter": "tasks.withType<Jar> {\n    /* /* */ test -> */\n    test.enabled = false\n}",
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

    def test_kotlin_dsl_reads_as_kotlin(self):
        os.remove(os.path.join(self.root, "build.gradle"))
        for expected, cases in (([], self.KOTLIN_FREE), (["B1"], self.KOTLIN_B1)):
            for name, script in cases.items():
                with self.subTest(name):
                    self.file("build.gradle.kts", 'apply(from = "gauntlet/gauntlet.gradle")\n' + script + "\n")
                    self.assertEqual(sorted(set(self.rules())), expected)


class TestSelection(IntegrityCase):
    """B2 knows every way Gradle narrows the tests a Test task runs. exclude and include of a Test task count where
    they configure a Test task the gauntlet runs, and the patterns only where they are written; for jar, a copy, a
    source set or a dependency they are no finding. The other selection names count everywhere but in a Test task
    the gauntlet does not run, named as such - a task of its own, a suite other than test."""

    B2 = {
        "exclude in the test block": "test { exclude '**/OrdersTest*' }",
        "include on its own line": "test {\n    include '**/*Fast*'\n}",
        "the excludes property": "test { excludes = ['**/OrdersTest*'] }",
        "the setter": "test { setIncludes(['**/A*']) }",
        "a spec": "test { exclude { it.file.name.contains('Orders') } }",
        "named test": "tasks.named('test') { exclude '**/OrdersTest*' }",
        "named test with its type": "tasks.named('test', Test) { exclude '**/OrdersTest*' }",
        "every Test task": "tasks.withType(Test).configureEach { exclude '**/OrdersTest*' }",
        "every Test task by its full name": "tasks.withType(org.gradle.api.tasks.testing.Test) { exclude '**/X*' }",
        "it in a Test block": "tasks.withType(Test).configureEach { it.exclude '**/OrdersTest*' }",
        "the parameter of a Test block": "tasks.withType(Test).configureEach { t -> t.exclude '**/OrdersTest*' }",
        "on the task": "test.exclude '**/OrdersTest*'",
        "on tasks.test": "tasks.test.exclude('**/OrdersTest*')",
        "on a looked-up task": "tasks.getByName('test').exclude('**/OrdersTest*')",
        "on a provided task": "tasks.named('test').get().exclude('**/OrdersTest*')",
        "the property on the task": "test.excludes = ['**/OrdersTest*']",
        "a method named by a string": "test.\"exclude\"('**/OrdersTest*')",
        "a property named by a string": "test['excludes'] = ['**/OrdersTest*']",
        "inside filter": "test { filter { exclude '**/OrdersTest*' } }",
        "inside doFirst": "test { doFirst { exclude '**/OrdersTest*' } }",
        "in subprojects": "subprojects { test { exclude '**/OrdersTest*' } }",
        "the acceptance tests": "acceptanceTest { exclude '**/*' }",
        "a JVM test suite": "testing { suites { test { targets { all { testTask.configure { exclude '**/X*' } } } } } }",
        "filter patterns": "test { filter { includePatterns = ['*Fast*'] } }",
        "a filter setter": "test { filter { setExcludePatterns(['*Slow*']) } }",
        "one test class": "test { filter { excludeTest 'a.OrdersTest', null } }",
        "engines": "test { useJUnitPlatform { includeEngines 'junit-vintage' } }",
        "a tag setter": "test { useJUnitPlatform { setExcludeTags(['slow'] as Set) } }",
        "JUnit 4 categories": "test { useJUnit { excludeCategories 'a.Slow' } }",
        "TestNG groups": "test { useTestNG { excludeGroups 'slow' } }",
        "test name patterns": "test { setTestNameIncludePatterns(['*Fast*']) }",
        "every JVM test suite": "testing { suites { configureEach { targets { all { testTask.configure { exclude '**/X*' } } } } } }",
        "engines behind the task": "test.useJUnitPlatform { includeEngines 'junit-jupiter' }",
        "a pattern of the task's filter": "test.filter.includePatterns = ['*Fast*']",
        "the test task's filter inside another task": "tasks.register('smokeTest', Test) { test.filter.includePatterns = ['*Fast*'] }",
        "engines under a condition": "test { if (true) { useJUnitPlatform { includeEngines 'junit-jupiter' } } }",
        "the patterns added to": "test.excludes.add('**/OrdersTest*')",
        "the patterns added to with <<": "test { excludes << '**/OrdersTest*' }",
        "engines in a block that names no declared task": "fooTest { useJUnitPlatform { includeEngines 'junit-jupiter' } }",
        "empty parentheses before the block": "tasks.withType(Test).configureEach() { exclude '**/OrdersTest*' }",
        "configure with empty parentheses": "tasks.named('test').configure() { exclude '**/OrdersTest*' }",
        "doFirst with empty parentheses": "test { doFirst() { include '**/*Fast*' } }",
        "an inner block behind the task": "test.doFirst { setExcludes(['**/OrdersTest*']) }",
        "under a condition": "test {\n    if (!project.hasProperty('all')) {\n        exclude '**/OrdersTest*'\n    }\n}",
        "in an else branch": "test {\n    if (project.hasProperty('all')) {\n        println 'all'\n    } else {\n"
                             "        exclude '**/OrdersTest*'\n    }\n}",
    }
    FREE = {
        "jar": "jar { exclude 'META-INF/*.SF' }",
        "resources of the tests": "processTestResources { exclude '**/*.tmp' }",
        "checkstyle of the tests": "checkstyleTest { exclude '**/generated/**' }",
        "a dependency of every configuration": "configurations.all { exclude group: 'commons-logging' }",
        "a test dependency": "dependencies {\n    testImplementation('junit:junit:4.13.2') { exclude group: 'org.hamcrest' }\n}",
        "a source directory": "sourceSets.main.java.exclude '**/Gen*'",
        "the test source set": "sourceSets { test { java { exclude '**/Gen*' } } }",
        "coverage inside the test block": "test { jacoco { excludes = ['a.Gen*'] } }",
        "a named argument": "dependencies { implementation fileTree(dir: 'libs', include: ['*.jar']) }",
        "a named argument inside the test block": "test { classpath += fileTree(dir: 'libs', include: '*.jar') }",
        "a string inside the test block": "test { systemProperty 'exclude', 'x' }",
        "a copy": "copy { from 'a'; into 'b'; include '*.txt' }",
        "a packaging task with a parameter": "tasks.withType(Jar).configureEach { t -> t.exclude('**/*.sql') }",
        "doFirst of jar": "jar { doFirst { exclude 'x' } }",
        "a method reference": "def m = test.&exclude",
        "a comment": "// test { exclude '**/OrdersTest*' }",
        "included builds in settings": "includeBuild('../lib')",
        "a JVM test suite the gauntlet does not run":
            "testing { suites { componentTest(JvmTestSuite) { targets { all { testTask.configure { exclude '**/X*' } } } } } }",
        "a suite reached by its path": "testing.suites.integrationTest.targets.all { testTask.configure { exclude '**/X*' } }",
        "engines of a task the gauntlet does not run":
            "tasks.register('smokeTest', Test) { useJUnitPlatform { includeEngines 'junit-jupiter' } }",
        "categories of a declared task": "task integrationTest(type: Test) { useJUnit { includeCategories 'a.Slow' } }",
        "filter patterns of a registered task": "tasks.register('integrationTest', Test) { filter { includePatterns = ['*IT'] } }",
        "the patterns read for a log line":
            "test.doFirst { logger.lifecycle(\"includes=${test.includes} excludes=${test.excludes}\") }",
        "the patterns read in the test block": "test { doFirst { if (excludes.isEmpty()) { println 'all tests' } } }",
        "the patterns copied into another task": "tasks.register('fastTest', Test) { includes = test.includes }",
        "a task the script declares, configured by its name":
            "tasks.register('smokeTest', Test)\nsmokeTest { useJUnitPlatform { includeEngines 'junit-jupiter' } }",
        "jar under a condition": "jar { if (true) { exclude 'META-INF/*.SF' } }",
        "jar with empty parentheses": "tasks.withType(Jar).configureEach() { exclude 'META-INF/*.SF' }",
        "an inner block behind jar": "jar.doFirst { exclude 'META-INF/*.SF' }",
    }
    KOTLIN_B2 = {
        "the test accessor": "tasks.test { exclude(\"**/OrdersTest*\") }",
        "named with a type": "tasks.named<Test>(\"test\") { exclude(\"**/OrdersTest*\") }",
        "every Test task": "tasks.withType<Test>().configureEach { exclude(\"**/OrdersTest*\") }",
        "every Test task by its class": "tasks.withType(Test::class.java).configureEach { exclude(\"**/X*\") }",
        "inside tasks": "tasks { test { exclude(\"**/OrdersTest*\") } }",
        "on a provided task": "tasks.test.get().exclude(\"**/OrdersTest*\")",
        "safe call": "tasks.findByName(\"test\")?.exclude(\"**/OrdersTest*\")",
        "the excludes property": "tasks.test { excludes += \"**/OrdersTest*\" }",
        "the test suite by its delegate": "testing { suites { val test by getting(JvmTestSuite::class) "
                                          "{ targets { all { testTask.configure { exclude(\"**/X*\") } } } } } }",
        "the patterns added to": "tasks.test { excludes.add(\"**/OrdersTest*\") }",
        "empty parentheses before the block": "tasks.withType<Test>().configureEach() { exclude(\"**/OrdersTest*\") }",
        "under a condition": "tasks.test { if (!project.hasProperty(\"all\")) { exclude(\"**/OrdersTest*\") } }",
    }
    KOTLIN_FREE = {
        "the jar accessor": "tasks.jar { exclude(\"META-INF/*.SF\") }",
        "a dependency of every configuration": "configurations.all { exclude(group = \"commons-logging\") }",
        "a test dependency": "dependencies { testImplementation(\"junit:junit:4.13.2\") { exclude(group = \"org.hamcrest\") } }",
        "a registered suite": "testing { suites { register<JvmTestSuite>(\"componentTest\") "
                              "{ targets { all { testTask.configure { exclude(\"**/X*\") } } } } } }",
        "a suite by its delegate": "testing { suites { val integrationTest by registering(JvmTestSuite::class) "
                                   "{ targets { all { testTask.configure { exclude(\"**/X*\") } } } } } }",
        "engines of a registered task": "tasks.register<Test>(\"smokeTest\") { useJUnitPlatform { includeEngines(\"junit-jupiter\") } }",
        "another task by its delegate": "val integrationTest by tasks.getting(Test::class) { exclude(\"**/X*\") }",
    }

    def test_every_filter_of_a_test_task_is_b2(self):
        for name, script in self.B2.items():
            with self.subTest(name):
                self.file("build.gradle", APPLY + script + "\n")
                self.assertEqual(self.rules(), ["B2"])

    def test_the_patterns_of_anything_else_are_free(self):
        for name, script in self.FREE.items():
            with self.subTest(name):
                self.file("build.gradle", APPLY + script + "\n")
                self.assertEqual(self.rules(), [])

    def test_kotlin_dsl(self):
        os.remove(os.path.join(self.root, "build.gradle"))
        for expected, cases in ((["B2"], self.KOTLIN_B2), ([], self.KOTLIN_FREE)):
            for name, script in cases.items():
                with self.subTest(name):
                    self.file("build.gradle.kts", 'apply(from = "gauntlet/gauntlet.gradle")\n' + script + "\n")
                    self.assertEqual(self.rules(), expected)


class Encoding(IntegrityCase):
    LATIN = "package a;\n/** réduit */\n// CHECKSTYLE:OFF\nclass Tarifé { }\n"

    def test_non_utf8_source_does_not_stop_the_check(self):
        # a Latin-1 source in a UTF-8 scan used to end the whole check with exit 2 (MalformedInputException); text
        # patterns cannot judge a source that is not valid in its charset, so that is a finding of its own - E1
        self.file("src/main/java/a/Tarifs.java", self.LATIN, "iso-8859-1")
        r = self.check()
        self.assertEqual(r.code, 1, r)
        self.assertEqual(sorted(self.rules()), ["E1", "M2"])
        self.assertIn("src/main/java/a/Tarifs.java", next(l for l in r.out.splitlines() if " E1 " in l))
        self.assertEqual(self.rules("--encoding", "ISO-8859-1"), ["M2"])

    def test_each_source_tree_is_read_with_the_charset_of_its_compile_task(self):
        # a UTF-16 test tree next to UTF-8 main sources: read as UTF-8 it hid @Disabled (Integrity check: OK)
        self.file("src/test/java/a/OrderTest.java", "class OrderTest {\n    @Disabled\n    void works() { }\n}\n", "utf-16")
        self.assertEqual(self.rules("--test-encoding", "UTF-16"), ["T1"])
        self.assertEqual(self.rules(), ["E1"])
        self.file("src/acceptanceTest/java/a/Steps.java", "class Steps { void s() { assumeTrue(x); } }\n", "utf-16")
        self.assertEqual(sorted(self.rules("--test-encoding", "UTF-16", "--acceptance-encoding", "UTF-16")), ["T1", "T4"])

    def test_a_nul_in_a_source_is_never_silence(self):
        # javac drops a NUL inside an identifier: @Dis<NUL>abled compiles as @Disabled
        self.file("src/test/java/a/T.java", "class T {\n    @Dis\x00abled\n    void works() { }\n}\n")
        self.assertTrue({"T1", "E1"} & set(self.rules()), self.check())

    def test_non_utf8_build_scripts_and_allowlist_do_not_stop_the_check(self):
        # Gradle reads a build script with the platform charset: a Latin-1 comment is no reason to end with exit 2
        self.file("build.gradle", (APPLY + "// param\u00e8tres\ntest { enabled = false }\n").encode("iso-8859-1"))
        self.file("settings.gradle", "// r\u00e9glages\nrootProject.name = 'x'\n".encode("iso-8859-1"))
        allow = self.file("allow.txt", "# liste autoris\u00e9e\n".encode("iso-8859-1"))
        self.file("src/main/java/a/M.java", "// CHECKSTYLE:OFF\nclass M { }\n")
        r = self.check("--allowlist", allow)
        self.assertEqual(r.code, 1, r)
        self.assertEqual(sorted(set(self.rules("--allowlist", allow))), ["B1", "M2"])

    def test_sources_are_read_with_the_project_encoding(self):
        self.file("src/main/java/a/Tarifs.java", self.LATIN, "utf-16")
        self.assertEqual(self.rules("--encoding", "UTF-16"), ["M2"])

    def test_unknown_charset_is_a_usage_error(self):
        self.assertEqual(self.check("--encoding", "no-such-charset").code, 2)


if __name__ == "__main__":
    unittest.main()
