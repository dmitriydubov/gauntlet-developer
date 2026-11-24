"""TestCensus.java: every test class a gate's Test task compiled must be in its JUnit XML results (finding T6).

The fixtures are real class files: javac compiles them against stubs of the JUnit and TestNG annotations (same names,
runtime retention), so the census reads what a build gives it. Which shapes count as test classes mirrors what Gradle
8.14.3 ran and wrote into its XML results with Jupiter 5.12, vintage, JUnit 4 under useJUnit() and TestNG 7.10 under
useTestNG(); tests/test_gradle_e2e.py runs the census on real builds.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

import kit

STUBS = {
    "org/junit/jupiter/api/Test.java": "@Target({ElementType.METHOD, ElementType.ANNOTATION_TYPE}) public @interface Test { }",
    "org/junit/jupiter/api/RepeatedTest.java": "@Target(ElementType.METHOD) public @interface RepeatedTest { int value(); }",
    "org/junit/jupiter/api/TestFactory.java": "@Target(ElementType.METHOD) public @interface TestFactory { }",
    "org/junit/jupiter/api/TestTemplate.java": "@Target({ElementType.METHOD, ElementType.ANNOTATION_TYPE}) public @interface TestTemplate { }",
    "org/junit/jupiter/api/Nested.java": "@Target(ElementType.TYPE) public @interface Nested { }",
    "org/junit/jupiter/api/Disabled.java": "@Target({ElementType.TYPE, ElementType.METHOD}) public @interface Disabled { String value() default \"\"; }",
    "org/junit/jupiter/api/Tag.java": "@Target({ElementType.TYPE, ElementType.METHOD}) public @interface Tag { String value(); }",
    "org/junit/jupiter/params/ParameterizedTest.java": "@Target(ElementType.METHOD) public @interface ParameterizedTest { }",
    "org/junit/Test.java": "@Target(ElementType.METHOD) public @interface Test { Class<?> expected() default Object.class; }",
    "org/junit/Ignore.java": "@Target({ElementType.TYPE, ElementType.METHOD}) public @interface Ignore { String value() default \"\"; }",
    "org/testng/annotations/Test.java": "@Target({ElementType.TYPE, ElementType.METHOD, ElementType.CONSTRUCTOR}) public @interface Test "
                                        "{ boolean enabled() default true; String[] groups() default {}; }",
    "org/testng/annotations/Ignore.java": "@Target({ElementType.TYPE, ElementType.METHOD, ElementType.PACKAGE}) public @interface Ignore { }",
    "org/testng/annotations/BeforeMethod.java": "@Target(ElementType.METHOD) public @interface BeforeMethod { }",
}

# what Jupiter runs and what it does not (Gradle 8.14.3 + Jupiter 5.12: the classes that got a testcase)
JUPITER = {
    "PlainTest": "class PlainTest {\n    @Test void works() { }\n}\n",
    "DisabledTest": "@Disabled(\"waits for the tariff\") class DisabledTest {\n    @Test void later() { }\n}\n",
    "TaggedTest": "@Tag(\"slow\") class TaggedTest {\n    @Test void slow() { }\n}\n",
    "AbstractContract": "abstract class AbstractContract {\n    @Test void inherited() { }\n}\n",
    "InheritsContractTest": "class InheritsContractTest extends AbstractContract {\n}\n",
    "ShadowsContract": "class ShadowsContract extends AbstractContract {\n    @Override void inherited() { }\n}\n",
    "Contract": "interface Contract {\n    @Test default void fromInterface() { }\n    @Test void abstractOne();\n}\n",
    "ImplementsContractTest": "class ImplementsContractTest implements Contract {\n    public void abstractOne() { }\n}\n",
    "OuterTest": "class OuterTest {\n    @Nested class Inner {\n        @Test void inner() { }\n        @Nested class Deeper {\n"
                 "            @Test void deeper() { }\n        }\n    }\n    class NotNested {\n        @Test void never() { }\n    }\n"
                 "    private static class Hidden {\n        @Test void never() { }\n    }\n    static class StaticNested {\n"
                 "        @Test void runs() { }\n    }\n    @Nested private class PrivateNested {\n        @Test void never() { }\n    }\n}\n",
    "AbstractOuter": "abstract class AbstractOuter {\n    @Nested class InnerOfAbstract {\n        @Test void never() { }\n    }\n}\n",
    "PrivateMethodOnly": "class PrivateMethodOnly {\n    @Test private void never() { }\n}\n",
    "StaticMethodOnly": "class StaticMethodOnly {\n    @Test static void never() { }\n}\n",
    "NonVoidOnly": "class NonVoidOnly {\n    @Test int never() { return 1; }\n}\n",
    "FactoryTest": "class FactoryTest {\n    @TestFactory java.util.List<Object> tests() { return java.util.List.of(); }\n}\n",
    "VoidFactoryOnly": "class VoidFactoryOnly {\n    @TestFactory void never() { }\n}\n",
    "RepeatedTestTest": "class RepeatedTestTest {\n    @RepeatedTest(2) void twice() { }\n}\n",
    "ParameterizedOnlyTest": "class ParameterizedOnlyTest {\n    @org.junit.jupiter.params.ParameterizedTest void each(int x) { }\n}\n",
    "TemplateOnlyTest": "class TemplateOnlyTest {\n    @TestTemplate void template() { }\n}\n",
    "LocalAndAnonymous": "class LocalAndAnonymous {\n    Object local() {\n        class Local {\n            @Test void never() { }\n"
                         "        }\n        return new Local();\n    }\n    Object anonymous() {\n        return new Object() {\n"
                         "            @Test void never() { }\n        };\n    }\n}\n",
    "Helper": "class Helper {\n    static int twice(int x) { return 2 * x; }\n}\n",
    "OnlyAnEnum": "enum OnlyAnEnum {\n    A;\n    @Test void never() { }\n}\n",
}
JUPITER_TESTS = {"PlainTest", "DisabledTest", "TaggedTest", "InheritsContractTest", "ImplementsContractTest", "OuterTest$Inner",
                 "OuterTest$Inner$Deeper", "OuterTest$StaticNested", "FactoryTest", "RepeatedTestTest",
                 "ParameterizedOnlyTest", "TemplateOnlyTest"}

# JUnit 4: vintage discovers public classes only; useJUnit() fails a package-private one with an initializationError
JUNIT4 = {
    "PublicJ4Test": "public class PublicJ4Test {\n    @Test public void works() { }\n}\n",
    "IgnoredJ4Test": "@org.junit.Ignore public class IgnoredJ4Test {\n    @Test public void later() { }\n}\n",
    "PackagePrivateJ4": "class PackagePrivateJ4 {\n    @Test public void works() { }\n}\n",
    "J4Holder": "public class J4Holder {\n    public static class NestedJ4Test {\n        @Test public void works() { }\n    }\n"
                "    public class InnerJ4 {\n        @Test public void never() { }\n    }\n}\n",
    "AbstractJ4Base": "public abstract class AbstractJ4Base {\n    @Test public void inherited() { }\n}\n",
    "ChildJ4Test": "public class ChildJ4Test extends AbstractJ4Base {\n}\n",
    "J4Contract": "public interface J4Contract {\n    @Test default void fromInterface() { }\n}\n",
    "ImplementsJ4Contract": "public class ImplementsJ4Contract implements J4Contract {\n}\n",
    "StaticJ4Only": "public class StaticJ4Only {\n    @Test public static void never() { }\n}\n",
}
JUNIT4_TESTS = {"PublicJ4Test", "IgnoredJ4Test", "J4Holder$NestedJ4Test", "ChildJ4Test"}

# TestNG under useTestNG(): its own methods only (Gradle's detection skips the tests of an abstract superclass), and
# nothing @Ignore takes out - TestNG reports nothing for those, integrityCheck T3 judges them
TESTNG = {
    "NgTest": "public class NgTest {\n    @Test public void works() { }\n}\n",
    "PackagePrivateNgTest": "class PackagePrivateNgTest {\n    @Test void works() { }\n}\n",
    "ClassLevelNgTest": "@Test public class ClassLevelNgTest {\n    public void one() { }\n    public int notATest() { return 1; }\n}\n",
    "ClassLevelOnlyConfig": "@Test public class ClassLevelOnlyConfig {\n    @org.testng.annotations.BeforeMethod public void setUp() { }\n"
                            "    void packagePrivate() { }\n}\n",
    "DisabledNgTest": "public class DisabledNgTest {\n    @Test(enabled = false) public void later() { }\n}\n",
    "IgnoredNg": "@org.testng.annotations.Ignore public class IgnoredNg {\n    @Test public void never() { }\n}\n",
    "MethodIgnoredNg": "public class MethodIgnoredNg {\n    @org.testng.annotations.Ignore @Test public void never() { }\n}\n",
    "AbstractNgBase": "public abstract class AbstractNgBase {\n    @Test public void inherited() { }\n}\n",
    "ChildNg": "public class ChildNg extends AbstractNgBase {\n}\n",
    "NonVoidNg": "public class NonVoidNg {\n    @Test public int never() { return 1; }\n}\n",
    "StaticNgOnly": "public class StaticNgOnly {\n    @Test public static void never() { }\n}\n",
}
TESTNG_TESTS = {"NgTest", "PackagePrivateNgTest", "ClassLevelNgTest", "DisabledNgTest"}
IMPORTS = {"jupiter": "import org.junit.jupiter.api.*;\n\n", "junit4": "import org.junit.Test;\n\n",
           "testng": "import org.testng.annotations.Test;\n\n"}


def results_xml(classes, suite="suite"):
    cases = "".join(f'  <testcase name="works()" classname="{c}" time="0.001"/>\n' for c in classes)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="{suite}" tests="{len(classes)}" skipped="0" '
            f'failures="0" errors="0">\n  <properties/>\n{cases}  <system-out><![CDATA[]]></system-out>\n</testsuite>\n')


class CensusCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="gauntlet-census-")
        cls.project = os.path.join(cls.tmp, "project")
        stubs = os.path.join(cls.tmp, "stubs")
        for rel, body in STUBS.items():
            package = os.path.dirname(rel).replace("/", ".")
            kit.write(os.path.join(stubs, rel), f"package {package};\n\nimport java.lang.annotation.*;\n\n"
                                                f"@Retention(RetentionPolicy.RUNTIME)\n{body}\n")
        sources = []
        for package, classes in (("jupiter", JUPITER), ("junit4", JUNIT4), ("testng", TESTNG)):
            for name, body in classes.items():
                sources.append(kit.write(os.path.join(cls.project, "src/test/java", package, name + ".java"),
                                         f"package {package};\n\n{IMPORTS[package]}{body}"))
        sources.append(kit.write(os.path.join(cls.project, "src/test/java/testng/ignored/package-info.java"),
                                 "@org.testng.annotations.Ignore\npackage testng.ignored;\n"))
        sources.append(kit.write(os.path.join(cls.project, "src/test/java/testng/ignored/InIgnoredPackage.java"),
                                 "package testng.ignored;\n\nimport org.testng.annotations.Test;\n\n"
                                 "public class InIgnoredPackage {\n    @Test public void never() { }\n}\n"))
        # a source whose directory is not its package (Kotlin allows it, javac too), and two sources of one name
        sources.append(kit.write(os.path.join(cls.project, "src/test/java/misplaced/ElsewhereTest.java"),
                                 "package jupiter;\n\nimport org.junit.jupiter.api.Test;\n\nclass ElsewhereTest {\n"
                                 "    @Test void works() { }\n}\n"))
        sources.append(kit.write(os.path.join(cls.project, "src/test/java/one/TwiceTest.java"),
                                 "package jupiter;\n\nimport org.junit.jupiter.api.Test;\n\nclass TwiceTest {\n"
                                 "    @Test void works() { }\n}\n"))
        sources.append(kit.write(os.path.join(cls.project, "src/test/java/two/TwiceTest.java"),
                                 "package other;\n\nclass TwiceTest {\n}\n"))
        cls.classes = os.path.join(cls.project, "build/classes/java/test")
        cls.javac(stubs, cls.classes, sources)
        # a class compiled without debug information has no SourceFile attribute
        cls.bare = os.path.join(cls.project, "build/classes/bare/test")
        cls.javac(stubs, cls.bare, [kit.write(os.path.join(cls.tmp, "bare/BareTest.java"),
                                              "package bare;\n\nclass BareTest {\n    @org.junit.jupiter.api.Test void works() { }\n}\n")],
                  "-g:none")

    @classmethod
    def javac(cls, stubs, out, sources, *options):
        stub_classes = os.path.join(cls.tmp, "stub-classes")
        if not os.path.isdir(stub_classes):
            stub_sources = [os.path.join(d, f) for d, _, fs in os.walk(stubs) for f in fs]
            r = subprocess.run(["javac", "-nowarn", "-d", stub_classes, *stub_sources], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, env=kit.java_env())
            assert r.returncode == 0, r.stdout
        r = subprocess.run(["javac", "-nowarn", *options, "-cp", stub_classes, "-d", out, *sources],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=kit.java_env())
        assert r.returncode == 0, r.stdout

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)

    def lists(self, name, paths):
        return kit.write(os.path.join(self.work.name, name), "".join(p + "\0" for p in paths))

    def results(self, classes, extra=None):
        """A results directory whose TEST-*.xml name these classes (binary names)."""
        directory = os.path.join(self.work.name, "results")
        os.makedirs(directory, exist_ok=True)
        for c in classes:
            kit.write(os.path.join(directory, f"TEST-{c}.xml"), results_xml([c], suite=c))
        for name, text in (extra or {}).items():
            kit.write(os.path.join(directory, name), text)
        return directory

    def census(self, *task_args, allowlist=None, classes=None, sources=None):
        args = ["--project-dir", self.project]
        if allowlist is not None:
            args += ["--allowlist", kit.write(os.path.join(self.work.name, "allow.txt"), allowlist)]
        args += ["--task", "test", "--classes-file", self.lists("classes", classes or [self.classes]),
                 "--sources-file", self.lists("sources", sources or [os.path.join(self.project, "src/test/java")]), *task_args]
        return kit.tool("TestCensus", *args)

    @staticmethod
    def t6(result):
        """{class name: path} of the T6 findings."""
        found = {}
        for line in result.out.splitlines():
            if line.startswith("INTEGRITY T6 "):
                head, _, name = line.partition("  |  ")
                found[name] = head.split()[2]
        return found


class Discovery(CensusCase):
    """With no results at all, the census names exactly the classes the frameworks would have run."""

    def test_the_classes_the_frameworks_run_are_the_ones_counted(self):
        r = self.census("--results", os.path.join(self.work.name, "none"))
        self.assertEqual(r.code, 1, r)
        expected = ({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
                    | {"testng." + c for c in TESTNG_TESTS})
        self.assertEqual(set(self.t6(r)), expected)

    def test_every_counted_class_in_the_results_is_ok(self):
        ran = ({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
               | {"testng." + c for c in TESTNG_TESTS})
        r = self.census("--results", self.results(sorted(ran)))
        self.assertEqual(r.code, 0, r)
        self.assertIn("Test census: OK - test classes run (ran/compiled): test 22/22", r.out)

    def test_a_class_left_out_of_the_run_is_t6_named_by_its_source(self):
        ran = ({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
               | {"testng." + c for c in TESTNG_TESTS}) - {"jupiter.TaggedTest", "jupiter.OuterTest$Inner$Deeper"}
        r = self.census("--results", self.results(sorted(ran)))
        self.assertEqual(r.code, 1, r)
        self.assertIn("INTEGRITY T6 src/test/java/jupiter/OuterTest.java  compiled but not run by test  |  "
                      "jupiter.OuterTest$Inner$Deeper", r.out)
        self.assertIn("INTEGRITY T6 src/test/java/jupiter/TaggedTest.java  compiled but not run by test  |  jupiter.TaggedTest", r.out)
        self.assertIn("Test census: FAILED - 2 test class(es) compiled but not run; test classes run (ran/compiled): test 20/22.",
                      r.out)
        self.assertIn("gauntlet/config/integrity-allowlist.txt (path-glob T6)", r.out)


class Paths(CensusCase):

    def test_the_source_is_found_outside_its_package_directory_when_its_name_is_unique(self):
        r = self.census("--results", os.path.join(self.work.name, "none"))
        found = self.t6(r)
        self.assertEqual(found.get("jupiter.ElsewhereTest"), "src/test/java/misplaced/ElsewhereTest.java")
        # two sources of that name and neither in the package directory: the class file names it
        self.assertEqual(found.get("jupiter.TwiceTest"), "build/classes/java/test/jupiter/TwiceTest.class")
        # a nested class lives in its outer class's source
        self.assertEqual(found.get("junit4.J4Holder$NestedJ4Test"), "src/test/java/junit4/J4Holder.java")

    def test_a_class_without_debug_information_is_named_by_its_class_file(self):
        r = self.census("--results", os.path.join(self.work.name, "none"), classes=[self.bare])
        self.assertEqual(self.t6(r), {"bare.BareTest": "build/classes/bare/test/bare/BareTest.class"})


class Allowlist(CensusCase):

    def test_only_a_t6_line_whose_glob_matches_the_path_accepts_a_finding(self):
        ran = ({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
               | {"testng." + c for c in TESTNG_TESTS}) - {"jupiter.TaggedTest", "testng.DisabledNgTest"}
        results = self.results(sorted(ran))
        allow = ("# reviewed by the human\nsrc/test/java/**/TaggedTest.java  T6   # runs in the nightly build\n"
                 "src/test/java/**/DisabledNgTest.java  T1   # the wrong rule accepts nothing\n")
        r = self.census("--results", results, allowlist=allow)
        self.assertEqual(r.code, 1, r)
        self.assertEqual(set(self.t6(r)), {"testng.DisabledNgTest"})
        self.assertIn("(1 allowlisted)", r.out)
        r = self.census("--results", results, allowlist=allow.replace("T1 ", "T6 "))
        self.assertEqual(r.code, 0, r)
        self.assertIn("Test census: OK - test classes run (ran/compiled): test 20/22 (2 allowlisted)", r.out)


class Results(CensusCase):

    def test_the_testcase_classname_counts_not_the_suite_s_display_name(self):
        ran = sorted({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
                     | {"testng." + c for c in TESTNG_TESTS})
        directory = self.results([c for c in ran if c != "jupiter.PlainTest"],
                                 {"TEST-jupiter.PlainTest.xml": results_xml(["jupiter.PlainTest"], suite="Plain orders")})
        self.assertEqual(self.census("--results", directory).code, 0)
        kit.write(os.path.join(directory, "TEST-jupiter.PlainTest.xml"), results_xml([], suite="jupiter.PlainTest"))
        r = self.census("--results", directory)
        self.assertEqual(set(self.t6(r)), {"jupiter.PlainTest"})

    def test_only_gradle_s_own_result_files_count(self):
        # Gradle deletes the TEST-*.xml of an earlier run when the task runs again, and nothing else it finds there
        ran = sorted({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
                     | {"testng." + c for c in TESTNG_TESTS})
        directory = self.results([c for c in ran if c != "jupiter.PlainTest"],
                                 {"planted.xml": results_xml(["jupiter.PlainTest"]),
                                  "TEST-jupiter.PlainTest.txt": results_xml(["jupiter.PlainTest"]),
                                  "binary/TEST-jupiter.PlainTest.xml": results_xml(["jupiter.PlainTest"])})
        r = self.census("--results", directory)
        self.assertEqual(set(self.t6(r)), {"jupiter.PlainTest"})

    def test_a_result_with_a_doctype_is_refused(self):
        directory = self.results([], {"TEST-x.xml": '<?xml version="1.0"?>\n<!DOCTYPE testsuite [<!ENTITY x SYSTEM '
                                                    '"file:///etc/hostname">]>\n<testsuite name="x"><testcase name="a" '
                                                    'classname="&x;"/></testsuite>\n'})
        r = self.census("--results", directory)
        self.assertEqual(r.code, 2, r)
        self.assertIn("cannot read the test results", r.out)

    def test_a_large_result_file_full_of_escaped_names_is_read_on_the_newest_jdk(self):
        # JDK 24+ counted every &quot; of a parameterized test's name against jdk.xml.maxGeneralEntitySizeLimit
        # (100,000 per document): a data-driven class with thousands of green cases stopped the census (review of 4.4)
        java = kit.newest_java(24)
        if java is None:
            self.skipTest("needs a JDK 24 or newer")
        cases = "".join(f'  <testcase name="[{i}] &quot;customer-{i}&quot;" classname="jupiter.PlainTest" time="0"/>\n'
                        for i in range(30000))
        directory = os.path.join(self.work.name, "results")
        kit.write(os.path.join(directory, "TEST-jupiter.PlainTest.xml"),
                  '<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="jupiter.PlainTest">\n' + cases + "</testsuite>\n")
        args = ["--project-dir", self.project, "--task", "test", "--classes-file",
                self.lists("classes", [self.classes]), "--sources-file",
                self.lists("sources", [os.path.join(self.project, "src/test/java")]), "--results", directory]
        r = kit.tool("TestCensus", *args, java=java)
        self.assertNotIn("cannot read the test results", r.out)
        self.assertNotIn("PlainTest", self.t6(r))

    def test_a_task_that_ran_nothing_in_this_build_counts_nothing_on_disk(self):
        ran = sorted({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
                     | {"testng." + c for c in TESTNG_TESTS})
        self.results(ran)       # an earlier run's results stay on disk
        r = self.census("--not-run", "SKIPPED")
        self.assertEqual(r.code, 1, r)
        self.assertIn("Test census: test was SKIPPED in this build, so none of its 22 test class(es) ran", r.out)
        self.assertEqual(len(self.t6(r)), 22)

    def test_no_compiled_test_class_is_ok(self):
        empty = os.path.join(self.work.name, "empty")
        os.makedirs(empty)
        r = self.census("--results", os.path.join(self.work.name, "none"), classes=[empty, os.path.join(self.work.name, "missing")])
        self.assertEqual(r.code, 0, r)
        self.assertIn("Test census: OK - test classes run (ran/compiled): test 0/0", r.out)


class Usage(CensusCase):

    def test_usage_errors(self):
        none = os.path.join(self.work.name, "none")
        for args in ([], ["--task", "test", "--results", none],
                     ["--task", "test", "--classes-file", self.lists("c", [self.classes])],
                     ["--task", "test", "--classes-file", self.lists("c", [self.classes]), "--results", none, "--not-run", "SKIPPED"],
                     ["--results", none, "--task", "test"], ["--task"]):
            with self.subTest(args=args):
                r = kit.tool("TestCensus", "--project-dir", self.project, *args)
                self.assertEqual(r.code, 2, r)
                self.assertIn("usage: java TestCensus.java", r.out)

    def test_two_tasks_are_judged_each_by_its_own_results(self):
        ran = sorted({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
                     | {"testng." + c for c in TESTNG_TESTS})
        results = self.results(ran)
        r = kit.tool("TestCensus", "--project-dir", self.project,
                     "--task", "test", "--classes-file", self.lists("c1", [self.classes]), "--results", results,
                     "--task", "archTest", "--classes-file", self.lists("c2", [self.bare]), "--results", results)
        self.assertEqual(r.code, 1, r)
        self.assertIn("INTEGRITY T6 build/classes/bare/test/bare/BareTest.class  compiled but not run by archTest  |  bare.BareTest",
                      r.out)
        self.assertIn("test classes run (ran/compiled): test 22/22, archTest 0/1", r.out)



class NotCompiled(CensusCase):
    """A test source the compile task left out (a source-set or a compile-task exclude) has no class, so no census of
    the classes can miss it: gauntlet.gradle hands the census the sources on disk that the task did not compile."""

    def test_a_test_source_left_out_of_the_compilation_is_t6(self):
        ran = sorted({"jupiter." + c for c in JUPITER_TESTS | {"ElsewhereTest", "TwiceTest"}} | {"junit4." + c for c in JUNIT4_TESTS}
                     | {"testng." + c for c in TESTNG_TESTS})
        left_out = kit.write(os.path.join(self.project, "src/test/java/jupiter/BrokenTest.java"), "class BrokenTest {\n")
        args = ["--project-dir", self.project, "--task", "test", "--classes-file", self.lists("c", [self.classes]),
                "--not-compiled-file", self.lists("n", [left_out]), "--results", self.results(ran)]
        r = kit.tool("TestCensus", *args)
        self.assertEqual(r.code, 1, r)
        self.assertIn("INTEGRITY T6 src/test/java/jupiter/BrokenTest.java  not compiled for test  |  the build leaves this "
                      "test source out of the compilation", r.out)
        self.assertIn("Test census: FAILED - 0 test class(es) compiled but not run, 1 test source(s) not compiled; "
                      "test classes run (ran/compiled): test 22/22.", r.out)
        allow = kit.write(os.path.join(self.work.name, "allow.txt"), "src/test/java/jupiter/BrokenTest.java T6 # wip\n")
        r = kit.tool("TestCensus", "--allowlist", allow, *args)
        self.assertEqual(r.code, 0, r)
        self.assertIn("Test census: OK - test classes run (ran/compiled): test 22/22 (1 allowlisted)", r.out)


if __name__ == "__main__":
    unittest.main()
