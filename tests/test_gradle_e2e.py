"""Real-Gradle scenarios: the kit from the bundle installed into a small project and run for real.

Only with `python3 tests/run.py --gradle` (GAUNTLET_E2E=1): needs `gradle` 8.14+ on PATH, a JDK 21+, and Maven
Central plus the Gradle plugin portal. Every scenario here is a defect that a review round found - or that
reviews missed - reproduced against a real build rather than a stub.
"""
import glob
import os
import re
import shutil
import tempfile
import unittest

import kit

CUCUMBER, JUNIT = "7.23.0", "5.12.2"

BUILD = """plugins {{
    id 'java'
    id 'info.solidsoft.pitest' version '1.19.0'
}}
group = 'com.example'
repositories {{ mavenCentral() }}
dependencies {{
    testImplementation platform('org.junit:junit-bom:{junit}')
    testImplementation 'org.junit.jupiter:junit-jupiter'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}}
test {{ useJUnitPlatform() }}
{extra}
apply from: 'gauntlet/gauntlet.gradle'
"""

ORDERS = """package com.example.service.domain;

public class Orders {
    public int total(int sum, int discount) {
        return sum - discount;
    }
}
"""

ORDERS_TEST = """package com.example.service.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class OrdersTest {
    @Test
    void subtractsTheDiscount() {
        assertEquals(9900, new Orders().total(10000, 100));
    }
}
"""

DISCOUNT_STEPS = """package com.example.service.acceptance;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.example.service.domain.Orders;
import io.cucumber.java.ru.Дано;
import io.cucumber.java.ru.Когда;
import io.cucumber.java.ru.Тогда;

public class DiscountSteps {
    private int discount;
    private int total;

    @Дано("клиент со скидкой {int} руб.")
    public void client(int value) {
        discount = value;
    }

    @Когда("клиент оформляет заказ на сумму {int} руб.")
    public void order(int sum) {
        total = new Orders().total(sum, discount);
    }

    @Тогда("итог заказа составляет {int} руб.")
    public void result(int expected) {
        %s;
    }
}
"""

DOMAIN = "src/main/java/com/example/service/domain/"
DOMAIN_TEST = "src/test/java/com/example/service/domain/"
GLUE = "src/acceptanceTest/java/com/example/service/acceptance/"
ACCOUNT_STEPS = """package com.example.service.acceptance;

import static org.junit.jupiter.api.Assertions.assertNull;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import java.util.HashMap;
import java.util.Map;

public class AccountSteps {
    private static final Map<String, Integer> ACCOUNTS = new HashMap<>();
    private String current;

    @Given("a new account {string}")
    public void open(String id) {
        assertNull(ACCOUNTS.putIfAbsent(id, 0), "account " + id + " already exists");
        current = id;
    }

    @When("{int} is deposited")
    public void deposit(int amount) {
        ACCOUNTS.merge(current, amount, Integer::sum);
    }

    @Then("the balance is {int}")
    public void balance(int expected) {
    }
}
"""
ORDER_STEPS = """package com.example.service.acceptance;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

public class OrderSteps {
    private Status status;

    @Given("an order in status {}")
    public void order(Status initial) {
        status = initial;
    }

    @When("the order is paid")
    public void pay() {
        status = Status.PAID;
    }

    @Then("the order is in status {}")
    public void inStatus(Status expected) {
    }
}
"""
ARGUMENT_PROVIDER = """abstract class GenerateSchemas extends DefaultTask {
    @OutputDirectory abstract DirectoryProperty getOutputDir()

    @TaskAction void generate() {
        def f = outputDir.get().file('json/orders.json').asFile
        f.parentFile.mkdirs()
        f.text = '{}\\n'
    }
}
def generateSchemas = tasks.register('generateSchemas', GenerateSchemas) {
    outputDir = layout.buildDirectory.dir('generated/schemas')
}
abstract class SchemaArgs implements CommandLineArgumentProvider {
    @InputDirectory @PathSensitive(PathSensitivity.RELATIVE) abstract DirectoryProperty getSchemas()

    @Override Iterable<String> asArguments() {
        return ["-Aschema.dir=${schemas.get().asFile}".toString()]
    }
}
tasks.named('compileJava') {
    def args = objects.newInstance(SchemaArgs)
    args.schemas = generateSchemas.flatMap { it.outputDir }.map { it.dir('json') }
    options.compilerArgumentProviders.add(args)
}"""
FEATURES = "src/acceptanceTest/resources/features/"


def jdk_homes():
    """Installed JDK homes by major version (for the two-JVM scenario): under /usr/lib/jvm, and wherever the
    JAVA_HOME_<major>_<ARCH> variables of a CI runner (actions/setup-java) point."""
    homes = {}
    candidates = [os.path.dirname(release) for release in sorted(glob.glob("/usr/lib/jvm/*/release"))]
    candidates += [home for name, home in sorted(os.environ.items()) if re.fullmatch(r"JAVA_HOME(_\d+_\w+)?", name)]
    for home in candidates:
        release = os.path.join(home, "release")
        m = re.search(r'JAVA_VERSION="(\d+)', kit.read(release)) if os.path.isfile(release) else None
        if m and os.access(os.path.join(home, "bin", "java"), os.X_OK):
            homes.setdefault(int(m.group(1)), os.path.realpath(home))
    return homes


@unittest.skipUnless(os.environ.get("GAUNTLET_E2E"), "real-Gradle scenarios run only with --gradle")
@unittest.skipUnless(shutil.which("gradle"), "gradle is not on PATH")
class GradleCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gauntlet-e2e-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lab = os.path.join(self.tmp, "lab")

    # -- the project ---------------------------------------------------------------------------------------

    def project(self, build_extra="", steps_assert="assertEquals(expected, total)", example=True):
        """The kit's discount example as a single build at the repository root, on a feature branch."""
        shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(self.lab, "gauntlet"))
        for key, value in (("module", ""), ("acceptance.spring", "false"), ("cucumber.version", CUCUMBER)):
            kit.set_property(self.lab, key, value)
        arch = os.path.join(self.lab, "gauntlet/config/architecture.properties")
        kit.write(arch, re.sub(r"(?m)^(allowed\.(application|api|infrastructure)|forbidden\.application)=.*\n", "",
                               kit.read(arch)))
        self.file("settings.gradle", "rootProject.name = 'lab'\n")
        self.file("build.gradle", BUILD.format(junit=JUNIT, extra=build_extra))
        self.file(DOMAIN + "Orders.java", ORDERS)
        self.file(DOMAIN_TEST + "OrdersTest.java", ORDERS_TEST)
        self.file(".gitignore", "build/\n.gradle/\n")
        if example:
            self.file(GLUE + "DiscountSteps.java", DISCOUNT_STEPS % steps_assert)
            shutil.copy(os.path.join(self.lab, "gauntlet/templates/acceptanceTest/resources/features/example_discount.feature"),
                        self.file(FEATURES + "example_discount.feature", ""))
        self.git("init", "-q", "-b", "main", ".")
        self.git("config", "user.email", "lab@example.invalid")
        self.git("config", "user.name", "lab")
        self.commit("base")
        origin = os.path.join(self.tmp, "origin.git")
        self.git("clone", "-q", "--bare", ".", origin)
        self.git("remote", "add", "origin", origin)
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", "feature")

    def file(self, rel, text, encoding="utf-8"):
        return kit.write(os.path.join(self.lab, rel), text, encoding)

    def git(self, *args):
        r = kit.run(["git", *args], cwd=self.lab)
        self.assertEqual(r.code, 0, r)
        return r.out

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def gradle(self, *args, env=None):
        environment = kit.java_env()
        environment.update(env or {})
        return kit.run(["gradle", *args, "--console=plain"], cwd=self.lab, env=environment)

    def assert_build(self, result, ok):
        self.assertIn("BUILD SUCCESSFUL" if ok else "BUILD FAILED", result.out, result.out[-4000:])


class WholeGauntlet(GradleCase):

    def test_shipped_example_passes_every_gate(self):
        self.project()
        r = self.gradle("gauntlet", "-Pgauntlet.scope=all", "--continue")
        self.assert_build(r, True)
        for line in ("Integrity check: OK", "Checkstyle: OK", "PMD: OK", "Acceptance: 3 scenario(s), none skipped - OK",
                     "CRAP gate: OK", "DRY gate: OK", "PIT summary: 2 mutant(s) {KILLED=2}",
                     "Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s); 6 control(s) - 6 passed",
                     "Gherkin mutation: OK"):
            self.assertIn(line, r.out)

    def test_hollow_step_definition_leaves_survivors(self):
        self.project(steps_assert="assertEquals(true, total > 0)")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, False)
        self.assertIn("MUTANT SURVIVED", r.out)
        self.assertIn("6 control(s) - 6 passed", r.out)


class GherkinVerdict(GradleCase):

    def test_cucumber_s_own_table_diff_in_a_step_is_a_kill(self):
        # DataTable.diff throws io.cucumber.datatable.TableDiffException - no java.lang.AssertionError by name
        self.project(example=False)
        self.file(FEATURES + "doubling.feature",
                  "Feature: Doubling\n\n  Scenario Outline: The price is doubled\n    When the price <price> is doubled\n"
                  "    Then the result table is:\n      | value    |\n      | <result> |\n\n"
                  "    Examples:\n      | price | result |\n      | 5     | 10     |\n")
        self.file(GLUE + "DoublingSteps.java", """package com.example.service.acceptance;

import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import java.util.List;

public class DoublingSteps {
    private int actual;

    @When("the price {int} is doubled")
    public void doubled(int price) {
        actual = price * 2;
    }

    @Then("the result table is:")
    public void resultTable(DataTable expected) {
        expected.diff(DataTable.create(List.of(List.of("value"), List.of(String.valueOf(actual)))));
    }
}
""")
        self.commit("doubling")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, True)
        self.assertIn("Gherkin mutation: 2 mutant(s) - 2 killed (2 by a non-assertion exception thrown in a step), "
                      "0 survived, 0 error(s); 2 control(s) - 2 passed", r.out)

    def test_fixture_that_fails_in_the_mutant_run_is_no_kill(self):
        self.project()
        self.file(GLUE + "Harness.java", """package com.example.service.acceptance;

import io.cucumber.java.Before;
import io.cucumber.java.Scenario;
import java.io.IOException;

public class Harness {
    @Before
    public void connect(Scenario scenario) throws IOException {
        if (scenario.getName().startsWith("MUTANT") || scenario.getName().startsWith("CONTROL")) {
            throw new IOException("Database URL is undefined");
        }
    }
}
""")
        self.commit("a fixture that is down for the mutant run")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, False)
        self.assertIn("Gherkin mutation: 9 mutant(s) - 0 killed, 0 survived, 9 error(s); 6 control(s) - 0 passed", r.out)
        self.assertIn("failed outside a step (java.io.IOException", r.out)

    def test_mutants_of_a_scenario_whose_prerequisite_never_runs_are_no_kills(self):
        # Scenario B needs state that scenario A (another, unchanged feature) leaves behind. scope=changed runs
        # only B's mutants: every one fails on the missing prerequisite. Its Then step is hollow, so in a sound
        # harness its mutant survives - counting those failures as kills is a green gate over an unchecked step.
        self.project(example=False)
        self.file(GLUE + "RateSteps.java", """package com.example.service.acceptance;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

public class RateSteps {
    private static Integer baseRate;
    private int rated;

    @When("the base rate is set to {int}")
    public void setBaseRate(int rate) {
        baseRate = rate;
    }

    @Then("the stored base rate is {int}")
    public void storedBaseRate(int expected) {
        assertEquals(expected, baseRate);
    }

    @When("the price {int} is rated")
    public void rate(int price) {
        assertNotNull(baseRate, "no base rate - scenario A must run first");
        rated = price * baseRate;
    }

    @Then("the rated price is {int}")
    public void ratedPrice(int expected) {
        assertEquals(true, rated > 0);
    }
}
""")
        self.file(FEATURES + "a.feature",
                  "Feature: Rates A\n\n  Scenario Outline: The base rate is stored\n    When the base rate is set to <rate>\n"
                  "    Then the stored base rate is <stored>\n\n    Examples:\n      | rate | stored |\n      | 10   | 10     |\n")
        self.git("checkout", "-q", "main")
        self.commit("scenario A and the steps")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-B", "feature", "main")
        self.file(FEATURES + "b.feature",
                  "Feature: Rates B\n\n  Scenario Outline: A price uses the stored base rate\n    When the price <price> is rated\n"
                  "    Then the rated price is <rated>\n\n    Examples:\n      | price | rated |\n      | 5     | 50    |\n")
        self.commit("scenario B")
        r = self.gradle("gherkinMutation")
        self.assert_build(r, False)
        self.assertIn("2 control(s) - 0 passed", r.out)
        self.assertRegex(r.out, r"MUTANT ERROR +c1 control \(unmutated scenario\) failed in a step")


class GherkinHarness(GradleCase):
    """Failures the changed value did not cause are no kills: a row that cannot be repeated in one run, a value
    Cucumber rejected before the step definition saw it."""

    def test_a_row_that_cannot_run_twice_on_one_stand_kills_nothing(self):
        # every scenario shares one account store (as a cached Spring context shares a database); the Then step is
        # hollow. The control before the mutants passes, then each mutant fails on "already exists".
        self.project(example=False)
        self.file(GLUE + "AccountSteps.java", ACCOUNT_STEPS)
        self.file(FEATURES + "deposits.feature", "Feature: Deposits\n\n  Scenario Outline: A deposit increases the balance\n"
                  "    Given a new account \"ACC-1\"\n    When <amount> is deposited\n    Then the balance is <balance>\n\n"
                  "    Examples:\n      | amount | balance |\n      | 100    | 100     |\n")
        self.commit("deposits")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, False)
        self.assertIn("2 mutant(s) - 0 killed, 0 survived, 2 error(s); 2 control(s) - 1 passed", r.out)
        self.assertIn("before the first step that uses <amount>", r.out)
        self.assertRegex(r.out, r"MUTANT ERROR +z1 control \(unmutated scenario, after the mutants\) failed in a step")

    def test_a_value_the_step_never_receives_is_no_kill(self):
        # a dithered enum constant cannot be converted: Cucumber fails before the hollow Then step runs
        self.project(example=False)
        self.file(GLUE + "Status.java", "package com.example.service.acceptance;\n\npublic enum Status { NEW, PAID, SHIPPED }\n")
        self.file(GLUE + "OrderSteps.java", ORDER_STEPS)
        self.file(FEATURES + "orders.feature", "Feature: Order status\n\n  Scenario Outline: Paying moves the order on\n"
                  "    Given an order in status <before>\n    When the order is paid\n    Then the order is in status <after>\n\n"
                  "    Examples:\n      | before | after   |\n      | NEW    | SHIPPED |\n")
        self.commit("order status")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, False)
        self.assertIn("0 killed, 0 survived, 2 error(s)", r.out)
        self.assertIn("the value never reached a step definition", r.out)


class ChangedScope(GradleCase):
    LATIN = "package com.example.service.domain;\n\n/** Tarif réduit. */\nclass Tarifé {\n    int fee(int amount) {\n        return amount + 1;\n    }\n}\n"

    def test_encoding_given_as_a_compiler_argument(self):
        self.project(build_extra="tasks.withType(JavaCompile).configureEach { options.compilerArgs += ['-encoding', 'ISO-8859-1'] }")
        self.file(DOMAIN + "Tarifs.java", self.LATIN, "iso-8859-1")
        self.commit("a Latin-1 source")
        r = self.gradle("integrityCheck", "mutationGate", "--continue")
        self.assertIn("Integrity check: OK", r.out)
        self.assertNotIn("No mutations found", r.out)
        self.assertRegex(r.out, r">> Generated [1-9]\d* mutations")                    # Tarifé is found (and untested)
        self.assert_build(r, False)

    def test_changed_source_that_is_not_valid_in_the_source_encoding(self):
        self.project()
        self.file(DOMAIN + "Tarifs.java", self.LATIN, "iso-8859-1")                    # the build says nothing: UTF-8
        self.commit("a Latin-1 source in a UTF-8 build")
        r = self.gradle("gauntletScope")
        self.assert_build(r, False)
        self.assertIn("cannot read src/main/java/com/example/service/domain/Tarifs.java as UTF-8", r.out)

    def test_type_name_written_with_a_unicode_escape(self):
        # javac translates the escape before it reads the name: the class is Tarifé, and so is the changed type
        self.project()
        self.file(DOMAIN + "Tarifs.java", self.LATIN.replace("Tarifé", "Tarif\\u00e9").replace("réduit", "reduit"))
        self.file(DOMAIN_TEST + "TarifsTest.java", ORDERS_TEST.replace("OrdersTest", "TarifsTest")
                  .replace("assertEquals(9900, new Orders().total(10000, 100))", "assertEquals(3, new Tarif\\u00e9().fee(2))"))
        self.commit("a class named with a Unicode escape")
        r = self.gradle("mutationGate", "crapGate")
        self.assert_build(r, True)
        self.assertRegex(r.out, r">> Generated [1-9]\d* mutations")

    def test_two_changed_files_with_one_name_and_one_declared_package(self):
        self.project(build_extra="tasks.withType(JavaCompile).configureEach { options.debug = false }")
        self.file(DOMAIN + "Rules.java", "package com.example.service.domain;\n\nclass CurrentRules {\n    int fee(int amount) {\n        return amount + 1;\n    }\n}\n")
        self.file(DOMAIN + "variant/Rules.java", "package com.example.service.domain;\n\nclass LegacyRules {\n    int quote(int amount) {\n"
                  "        if (amount > 1000) {\n            return 30;\n        }\n        if (amount > 500) {\n            return 20;\n        }\n        return 5;\n    }\n}\n")
        self.file(DOMAIN_TEST + "CurrentRulesTest.java", ORDERS_TEST.replace("OrdersTest", "CurrentRulesTest")
                  .replace("assertEquals(9900, new Orders().total(10000, 100))", "assertEquals(3, new CurrentRules().fee(2))"))
        self.commit("two Rules.java")
        r = self.gradle("crapGate")
        self.assert_build(r, False)
        self.assertIn("4 method(s) analysed", r.out)
        self.assertRegex(r.out, r"CRAP FAIL +12\.0 .*LegacyRules#quote")


    def test_a_lone_cr_ends_a_line_comment(self):
        # javac ends a // comment at a lone CR: a scan that did not derived no type, and PIT checked nothing
        self.project()
        self.file(DOMAIN + "Pricing.java", "package com.example.service.domain;\n\n// pricing rules\rpublic class Pricing {\n"
                  "    public int withFee(int amount) {\n        return amount + 1;\n    }\n}\n")
        self.file(DOMAIN_TEST + "PricingTest.java", ORDERS_TEST.replace("OrdersTest", "PricingTest")
                  .replace("assertEquals(9900, new Orders().total(10000, 100))", "assertNotNull(new Pricing())")
                  .replace("import static org.junit.jupiter.api.Assertions.assertEquals;",
                           "import static org.junit.jupiter.api.Assertions.assertNotNull;"))
        self.commit("a comment that ends with a lone CR")
        r = self.gradle("mutationGate")
        self.assert_build(r, False)                                     # the weak test leaves survivors
        self.assertNotIn("no changed main classes", r.out)
        self.assertRegex(r.out, r">> Generated [1-9]\d* mutations")

    def test_changed_class_in_a_second_root_of_the_main_source_set(self):
        self.project(build_extra="sourceSets.main.java.srcDir 'src/shared/java'")
        self.file("src/shared/java/com/example/service/domain/Risky.java", "package com.example.service.domain;\n\n"
                  "public class Risky {\n    public int quote(int amount, boolean vip) {\n        if (amount > 1000) {\n"
                  "            return vip ? 30 : 20;\n        }\n        if (amount > 500) {\n            return vip ? 20 : 10;\n"
                  "        }\n        return 5;\n    }\n}\n")
        self.commit("an untested class in a second source root")
        r = self.gradle("crapGate")
        self.assert_build(r, False)
        self.assertRegex(r.out, r"CRAP FAIL .*Risky#quote")

    def test_options_encoding_wins_over_an_encoding_argument(self):
        # Gradle's compiler hands options.encoding to javac's API, which then ignores every -encoding argument
        self.project(build_extra="tasks.withType(JavaCompile).configureEach { options.encoding = 'ISO-8859-1' }\n"
                                 "tasks.named('compileJava') { options.compilerArgs += ['-encoding', 'UTF-8'] }")
        self.file(DOMAIN + "Tarifs.java", self.LATIN, "iso-8859-1")
        self.file(DOMAIN_TEST + "TarifsTest.java", ORDERS_TEST.replace("OrdersTest", "TarifsTest")
                  .replace("assertEquals(9900, new Orders().total(10000, 100))", "assertEquals(3, new Tarifé().fee(2))"),
                  "iso-8859-1")
        self.commit("ISO-8859-1 sources")
        r = self.gradle("crapGate", "mutationGate", "--continue")
        self.assert_build(r, True)
        self.assertNotIn("cannot read", r.out)

    def test_source_excluded_on_the_compile_task_is_not_asked_for_its_classes(self):
        self.project(build_extra="tasks.named('compileJava') { exclude '**/experimental/**' }")
        self.file(DOMAIN + "experimental/Draft.java", "package com.example.service.domain.experimental;\n\n"
                  "class Draft {\n    NotWrittenYet next;\n}\n")
        self.commit("a draft the build leaves out")
        r = self.gradle("crapGate", "mutationGate", "--continue")
        self.assert_build(r, True)

    def test_an_ordinary_build_never_evaluates_lazy_compiler_arguments_early(self):
        # an argument provider wired to a task output cannot answer before that task ran: `gradle build` used to
        # fail at configuration because the gate tasks asked the compile task for its arguments
        self.project(build_extra=ARGUMENT_PROVIDER)
        r = self.gradle("test")
        self.assert_build(r, True)

    def test_module_descriptor_is_not_handed_to_checkstyle(self):
        self.project()
        self.file("src/main/java/module-info.java", "module com.example.service {\n    exports com.example.service.domain;\n}\n")
        self.commit("a module descriptor")
        r = self.gradle("checkstyleGate")
        self.assert_build(r, True)
        self.assertNotIn("SAXParseException", r.out)


class GateJvm(GradleCase):

    def test_gate_jvm_by_version_next_to_a_pinned_test_executable(self):
        homes = jdk_homes()
        if len(homes) < 2:
            self.skipTest("needs two installed JDKs")
        project, gate = sorted(homes)[-2:]            # the two newest: a runner also carries JDK 8, 11, 17
        self.project(build_extra=f"tasks.withType(Test).configureEach {{ executable = '{homes[project]}/bin/java' }}")
        kit.set_property(self.lab, "gate.java.version", str(gate))
        r = self.gradle("archTest", "gauntletInfo", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, True)
        self.assertNotIn("does not match toolchain", r.out)
        self.assertIn(f"gate executable: {homes[gate]}/bin/java", r.out)

    def test_gate_jvm_by_version_next_to_a_launcher_pinned_after_the_kit(self):
        # a convention plugin pins the launcher in afterEvaluate - after the kit configured its gate tasks
        homes = jdk_homes()
        if len(homes) < 2:
            self.skipTest("needs two installed JDKs")
        project, gate = sorted(homes)[-2:]            # the two newest: a runner also carries JDK 8, 11, 17
        self.project(build_extra="afterEvaluate {\n    tasks.withType(Test).configureEach {\n        javaLauncher = "
                                 f"javaToolchains.launcherFor {{ languageVersion = JavaLanguageVersion.of({project}) }}\n    }}\n}}")
        kit.set_property(self.lab, "gate.java.version", str(gate))
        r = self.gradle("archTest", "acceptanceTest", "gauntletInfo", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, True)
        self.assertNotIn("does not match toolchain", r.out)

    def test_ordinary_build_does_not_need_the_gate_jdk(self):
        self.project()
        kit.set_property(self.lab, "gate.java.version", "99")
        r = self.gradle("classes", "-Porg.gradle.java.installations.auto-download=false")
        self.assert_build(r, True)


class CiPlan(GradleCase):
    """The workflow's plan step next to the build it plans for: both read gauntlet.properties and must agree."""

    def module(self, name):
        """A build in a module directory: gauntlet/ stays at the repository root."""
        shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(self.lab, "gauntlet"))
        self.file(name + "/settings.gradle", f"rootProject.name = '{name}'\n")
        self.file(name + "/build.gradle", BUILD.format(junit=JUNIT, extra="").replace("'gauntlet/", "'../gauntlet/"))

    def planned(self):
        """The plan step of .github/workflows/gauntlet.yml, run as the runner runs it: {build: (project, gate)}."""
        from test_ci_workflow import PLAN, step_script       # the reader of the workflow's `run:` scripts
        temp = os.path.join(self.tmp, "runner-temp")
        script = kit.write(os.path.join(temp, "plan.sh"), step_script(PLAN))
        env = dict(os.environ, RUNNER_TEMP=temp, GITHUB_OUTPUT=os.path.join(temp, "github-output"))
        r = kit.run(["bash", "--noprofile", "--norc", "-e", script], cwd=self.lab, env=env)
        self.assertEqual(r.code, 0, r)
        rows = [line.split("\t") for line in kit.read(os.path.join(temp, "gauntlet-plan")).splitlines()]
        return {row[0]: tuple(row[1:]) for row in rows}

    def reported(self, module):
        """The same two versions as `gauntletInfo` prints them in the module's build."""
        env = kit.java_env()
        env["GAUNTLET_GATE_JAVA_HOME"] = os.path.join(self.tmp, "gate-jdk")    # the gate JDK itself is not needed
        r = kit.run(["gradle", "gauntletInfo", "-q", "--console=plain"], cwd=os.path.join(self.lab, module), env=env)
        project = re.search(r"(?m)^project\.java\.version = (.*)$", r.out)
        gate = re.search(r"(?m)^gate JVM +: version=(.*); home=", r.out)
        self.assertTrue(project and gate, r.out[-4000:])
        return project.group(1), gate.group(1)

    def test_java_versions_written_with_any_separator_of_a_properties_file(self):
        # java.util.Properties ends a key at `=`, `:` or blanks: what Gradle resolves, CI has to install
        self.module("core")
        common = os.path.join(self.lab, "gauntlet/config/gauntlet.properties")
        other = re.sub(r"(?m)^(module|project\.java\.version|gate\.java\.version)=.*\n", "", kit.read(common))
        for separator in ("=", ": ", " "):
            with self.subTest(separator=separator):
                kit.write(common, other + f"module=core\nproject.java.version{separator}17\ngate.java.version{separator}21\n")
                kit.write(os.path.join(self.lab, "gauntlet/config/core/gauntlet.properties"), f"gate.java.version{separator}25\n")
                self.assertEqual(self.planned(), {"core": ("17", "25")})
                self.assertEqual(self.reported("core"), ("17", "25"))


if __name__ == "__main__":
    unittest.main()
