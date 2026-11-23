"""Real-Gradle scenarios: the kit from the bundle installed into a small project and run for real.

Only with `python3 tests/run.py --gradle` (GAUNTLET_E2E=1): needs `gradle` 8.14+ on PATH, a JDK 21+, and Maven
Central plus the Gradle plugin portal. Every scenario here is a defect that a review round found - or that
reviews missed - reproduced against a real build rather than a stub.
"""
import glob
import json
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
CREDIT_STEPS = """package com.example.service.acceptance;

import static org.junit.jupiter.api.Assertions.assertTrue;

import io.cucumber.java.en.When;
import java.util.concurrent.atomic.AtomicInteger;

public class CreditSteps {
    // the stand's quota: two purchases, the third one is refused
    private static final AtomicInteger PURCHASES = new AtomicInteger();

    @When("{int} credits are spent")
    public void spend(int credits) {
        System.out.println("purchase on " + Thread.currentThread().getName());
        assertTrue(PURCHASES.incrementAndGet() <= 2, "quota exceeded");
    }
}
"""
PURCHASE_STEPS = """package com.example.service.acceptance;

import io.cucumber.java.en.Then;

public class PurchaseSteps {
    @Then("the purchase is accepted")
    public void accepted() {
    }
}
"""
CREDITS = ("Feature: Credits\n\n  Scenario Outline: Credits are spent within the quota\n"
           "    When <credits> credits are spent\n    Then the purchase is accepted\n\n"
           "    Examples:\n      | credits |\n      | 3       |\n")
PARALLEL = {"cucumber.execution.parallel.enabled": "true", "cucumber.execution.parallel.config.strategy": "fixed",
            "cucumber.execution.parallel.config.fixed.parallelism": "2",
            "cucumber.execution.parallel.config.fixed.max-pool-size": "2"}
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
STATUS_TYPES = """package com.example.service.acceptance;

import io.cucumber.java.ParameterType;

public class StatusTypes {
    @ParameterType(".*")
    public Status status(String name) {
        return Status.valueOf(name);
    }
}
"""
VIEW_STEPS = """package com.example.service.acceptance;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;

public class ViewSteps {
    private Status status;

    @Given("an order in status {status}")
    public void order(Status initial) {
        status = initial;
    }

    @Then("the order can be viewed")
    public void viewed() {
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
LEDGER_STEPS = """package com.example.service.acceptance;

import static org.junit.jupiter.api.Assertions.assertEquals;

import io.cucumber.java.Before;
import io.cucumber.java.Scenario;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public class LedgerSteps {
    private String scenario;
    private int balance;

    @Before
    public void name(Scenario s) {
        scenario = s.getName();
    }

    @Given("the ledger is open")
    public void open() throws IOException {
        // a mark per scenario in the build directory tells a retry from the first attempt
        Path mark = Path.of("build", "attempts", scenario.replaceAll("\\\\W+", "_"));
        boolean retry = Files.exists(mark);
        Files.createDirectories(mark.getParent());
        Files.writeString(mark, "ran");
        if (!retry && scenario.startsWith(System.getProperty("ledger.first", "-"))) {
            throw new AssertionError("the ledger is not open yet");
        }
        if (retry && scenario.startsWith(System.getProperty("ledger.again", "-"))) {
            throw new AssertionError("the ledger is left over from the previous attempt");
        }
    }

    @When("{int} is deposited")
    public void deposit(int amount) {
        balance += amount;
    }

    @Then("the balance is {int}")
    public void balance(int expected) {
        assertEquals(expected, balance);
    }
}
"""
LEDGER = ("Feature: Deposits\n\n  Scenario Outline: A deposit increases the balance\n    Given the ledger is open\n"
          "    When <amount> is deposited\n    Then the balance is <balance>\n\n"
          "    Examples:\n      | amount | balance |\n      | 100    | 100     |\n")
RETRY = """tasks.withType(Test).configureEach {
    retry { maxRetries = 1 }
    reports.junitXml.mergeReruns = providers.gradleProperty('mergeReruns').map { it.toBoolean() }.orElse(false)
%s
}"""
BALANCE = """    public int balance(int[] amounts, int limit) {
        int total = 0;
        int count = 0;
        for (int amount : amounts) {
            if (amount > limit) {
                total += limit;
                count++;
            } else if (amount < 0) {
                total -= amount;
                count--;
            } else {
                total += amount;
                count += amount % 2;
            }
        }
        return count > 0 ? total / count : total;
    }
"""
LEDGER_JAVA = "package com.example.service.domain;\n\npublic class Ledger {\n" + BALANCE + "}\n"
# the same method once more (CPD: 82 tokens), untested (CRAP 30), and an empty catch block (PMD)
LEDGER_COPY = ("package com.example.service.domain;\n\nclass LedgerCopy {\n" + BALANCE + "\n    int parsed(String text) {\n"
               "        try {\n            return Integer.parseInt(text);\n        } catch (NumberFormatException e) {\n"
               "        }\n        return 0;\n    }\n}\n")


LATE_READER = """allprojects {
    afterEvaluate { p ->
        // what an IDE's model builder or a plugin in an init script does: read the launcher of every JVM task
        p.tasks.withType(JavaExec).each { it.javaLauncher.getOrNull() }
        p.tasks.withType(Test).each { it.javaLauncher.getOrNull() }
    }
}
"""
EVALUATED_READER = """gradle.projectsEvaluated { g ->
    // the same once every project is evaluated: Gradle calls an init script's listener before the build's own
    g.rootProject.allprojects { p ->
        p.tasks.withType(JavaExec).each { it.javaLauncher.getOrNull() }
        p.tasks.withType(Test).each { it.javaLauncher.getOrNull() }
    }
}
"""
REPORT_JVM = """gradle.taskGraph.afterTask { t ->
    if (t instanceof JavaExec || t instanceof Test) {
        println "${t.name} ran on ${t.javaLauncher.get().executablePath.asFile.canonicalPath}"
    }
}"""


def jdk_homes():
    """Installed JDK homes by major version (for the two-JVM scenarios): wherever the JAVA_HOME_<major>_<ARCH>
    variables of a CI runner (actions/setup-java) point, then under /usr/lib/jvm. Only a JDK: a scenario's project
    JVM compiles."""
    homes = {}
    candidates = [home for name, home in sorted(os.environ.items()) if re.fullmatch(r"JAVA_HOME(_\d+_\w+)?", name)]
    candidates += [os.path.dirname(release) for release in sorted(glob.glob("/usr/lib/jvm/*/release"))]
    for home in candidates:
        release = os.path.join(home, "release")
        m = re.search(r'JAVA_VERSION="(?:1\.)?(\d+)', kit.read(release)) if os.path.isfile(release) else None
        if m and all(os.access(os.path.join(home, "bin", tool), os.X_OK) for tool in ("java", "javac")):
            homes.setdefault(int(m.group(1)), os.path.realpath(home))
    return homes


def java_major(java):
    """The major version of the JVM whose bin/java this is (its release file), or None."""
    release = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(java))), "release")
    m = re.search(r'JAVA_VERSION="(?:1\.)?(\d+)', kit.read(release)) if os.path.isfile(release) else None
    return int(m.group(1)) if m else None


def class_java(path):
    """The Java version a class file is compiled for (JVMS 4.1: major_version - 44)."""
    with open(path, "rb") as f:
        head = f.read(8)
    return int.from_bytes(head[6:8], "big") - 44


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
        # A scenario proves what the gates do when they run. A build cache the machine enables (org.gradle.caching=true
        # in ~/.gradle/gradle.properties) hands a task the outputs of an earlier run of the same scenario instead:
        # pitest came FROM-CACHE, printed no ">> Generated" and skipped the kit's doFirst checks (review of efa4c50).
        # Only a scenario about the build cache asks for it, with a cache directory of its own. The configuration
        # cache likewise (org.gradle.configuration-cache=true): it refuses the afterTask listener of REPORT_JVM.
        cache = [] if "--build-cache" in args else ["--no-build-cache"]
        cache += [] if "--configuration-cache" in args else ["--no-configuration-cache"]
        return kit.run(["gradle", *args, *cache, "--console=plain"], cwd=self.lab, env=environment)

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


class GherkinRetry(GradleCase):
    """The test-retry plugin runs a failed scenario again - every scenario of the run, in fact: Cucumber reports one
    class, its engine. Gradle writes the attempts as a <testcase> each or, with reports.junitXml.mergeReruns, those
    of a test that failed in one <testcase> (<flakyFailure>; <failure> + <rerunFailure>). Every attempt is judged:
    the same verdict on every attempt is that verdict, different verdicts are no kill and a broken control."""

    def ledger(self, **fails):
        # first=<title prefix>: that scenario fails on its first attempt only; again=<title prefix>: on every later one
        self.project(example=False, build_extra=RETRY % "\n".join(f"    systemProperty 'ledger.{key}', '{prefix}'"
                                                                  for key, prefix in fails.items()))
        build = os.path.join(self.lab, "build.gradle")
        plugin = "    id 'org.gradle.test-retry' version '1.6.2'\n"
        kit.write(build, kit.read(build).replace("    id 'java'\n", "    id 'java'\n" + plugin))
        self.file(GLUE + "LedgerSteps.java", LEDGER_STEPS)
        self.file(FEATURES + "deposits.feature", LEDGER)
        self.commit("a ledger")

    def mutation(self, merge):
        shutil.rmtree(os.path.join(self.lab, "build", "attempts"), ignore_errors=True)
        return self.gradle("gherkinMutation", "-Pgauntlet.scope=all", f"-PmergeReruns={merge}")

    def results(self):
        """The JUnit XML of the mutant run: the scenario must have produced the shape it is about."""
        return "".join(kit.read(p) for p in glob.glob(os.path.join(self.lab, "build/gherkin-mutation/results/*.xml")))

    def test_a_control_that_passed_only_on_a_retry_is_broken(self):
        # merged, the control's failed attempt is a <flakyFailure> and no <failure>: it counted as passed and the
        # gate passed (review of 2c1cd0b)
        self.ledger(first="CONTROL c1 |")
        for merge in ("true", "false"):
            with self.subTest(mergeReruns=merge):
                r = self.mutation(merge)
                self.assertEqual(merge == "true", "<flakyFailure " in self.results())
                self.assert_build(r, False)
                # both mutants failed on both attempts - a retried kill stays a kill -, z1 passed on both
                self.assertIn("Gherkin mutation: 2 mutant(s) - 2 killed, 0 survived, 0 error(s); 2 control(s) - 1"
                              " passed", r.out)
                self.assertRegex(r.out, r"MUTANT ERROR +c1 control \(unmutated scenario\) ran more than once with "
                                        r"different results")

    def test_a_mutant_that_failed_before_the_value_on_a_retry_is_no_kill(self):
        # m1 fails in its Then step (line 6, after <amount> on line 5) and, on the retry, in its Given step (line 4):
        # the first failure was kept, a kill (review of 2c1cd0b)
        self.ledger(again="MUTANT m1 |")
        for merge in ("true", "false"):
            with self.subTest(mergeReruns=merge):
                r = self.mutation(merge)
                self.assertEqual(merge == "true", "<rerunFailure " in self.results())
                self.assert_build(r, False)
                self.assertIn("Gherkin mutation: 2 mutant(s) - 1 killed, 0 survived, 1 error(s); 2 control(s) - 2"
                              " passed", r.out)
                self.assertRegex(r.out, r"MUTANT ERROR +m1 ran more than once with different results")


class GherkinScope(GradleCase):

    def test_a_deleted_glue_file_mutates_every_feature(self):
        # deleting a hook or a step class changes the glue as much as editing one; git's ACMR filter left the
        # deletion out, and no feature was mutated (review of 65c03da)
        self.project()
        self.file(GLUE + "AuditHooks.java", "package com.example.service.acceptance;\n\nclass AuditHooks {\n}\n")
        self.commit("audit hooks")
        self.git("push", "-q", "origin", "HEAD:main")
        self.git("fetch", "-q", "origin")
        self.git("rm", "-q", GLUE + "AuditHooks.java")
        self.commit("no audit hooks")
        r = self.gradle("gherkinMutation")
        self.assert_build(r, True)
        self.assertIn("acceptance glue file(s) changed (" + GLUE + "AuditHooks.java) - every feature is mutated", r.out)
        self.assertIn("Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s)", r.out)

    def changed_feature_under(self, features_setting):
        # the features directory as a human may write it: Gradle reads it as the same directory, and so must the
        # changed scope - as a text prefix "features/" or "./features" named no changed path, and scope=changed
        # mutated nothing (review of the merged fixes for 2c1cd0b)
        self.project()
        kit.set_property(self.lab, "acceptance.features", features_setting)
        self.git("mv", FEATURES + "example_discount.feature", FEATURES + "discount.feature")
        self.commit("the feature renamed")
        r = self.gradle("gherkinMutation")
        self.assert_build(r, True)
        self.assertIn("Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s)", r.out)

    def test_a_trailing_slash_in_the_features_setting(self):
        self.changed_feature_under("src/acceptanceTest/resources/features/")

    def test_a_leading_dot_in_the_features_setting(self):
        self.changed_feature_under("./src/acceptanceTest/resources/features")


class PathLists(GradleCase):
    """A name that holds a separator reaches every tool whole (review of 2c1cd0b)."""

    def test_a_changed_feature_named_with_a_comma_or_a_double_quote_is_mutated(self):
        # gauntlet.gradle joined the changed features with commas for GherkinMutator, and git quotes a name with a
        # double quote: either way scope=changed mutated nothing and gherkinMutation passed
        self.project()
        current = "example_discount.feature"
        for name in ("Скидка, рубли.feature", 'Скидка "VIP".feature'):
            with self.subTest(name):
                self.git("mv", FEATURES + current, FEATURES + name)
                self.commit("the example feature renamed")
                current = name
                r = self.gradle("gherkinMutation")
                self.assert_build(r, True)
                self.assertIn("Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s); 6 control(s) - 6 passed",
                              r.out)

    def test_a_changed_source_named_with_a_comma_is_judged_by_every_gate(self):
        # PMD split its --dir at the comma and judged no file ("PMD: OK"), CrapGate could not read either half
        # (exit 2), DryGate matched the duplication to neither half ("DRY gate: OK")
        self.project()
        self.git("checkout", "-q", "main")
        self.file(DOMAIN + "Ledger.java", LEDGER_JAVA)
        self.commit("a ledger")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-B", "feature", "main")
        self.file(DOMAIN + "Ledger,Copy.java", LEDGER_COPY)
        self.commit("a copy of the ledger in a file named with a comma")
        r = self.gradle("pmdGate", "crapGate", "dryGate", "--continue")
        self.assert_build(r, False)
        self.assertRegex(r.out, r"Ledger,Copy\.java:25: Avoid empty catch blocks \[EmptyCatchBlock\]")
        self.assertRegex(r.out, r"CRAP FAIL .*LedgerCopy#balance \(Ledger,Copy\.java:5\)")
        self.assertIn("DRY gate: 1 duplication(s) found by CPD, 1 in scope (1 changed file(s))", r.out)

    def test_a_project_in_a_directory_named_with_a_comma(self):
        # PMD, CPD and Cucumber split their path options at commas, PIT its class paths: PMD loaded no rules, CPD and
        # Cucumber found nothing to read, and PIT nothing to mutate - mutationGate passed
        self.lab = os.path.join(self.tmp, "acme, inc", "lab")
        self.project()
        self.file(DOMAIN + "Ledger.java", LEDGER_JAVA)
        self.file(DOMAIN + "LedgerCopy.java", LEDGER_COPY)
        self.commit("a ledger and its copy")
        r = self.gradle("pmdGate", "dryGate", "gherkinMutation", "mutationGate", "-Pgauntlet.scope=all", "--continue")
        self.assert_build(r, False)
        self.assertRegex(r.out, r"LedgerCopy\.java:25: Avoid empty catch blocks \[EmptyCatchBlock\]")
        self.assertIn("DRY gate: 1 duplication(s) found by CPD, 1 in scope (all sources)", r.out)
        self.assertIn("Acceptance: 3 scenario(s), none skipped - OK", r.out)
        self.assertIn("Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s); 6 control(s) - 6 passed", r.out)
        self.assertIn("Build from a directory without a comma in its path", r.out)       # PIT: refused, not green


class GherkinHarness(GradleCase):
    """Failures the changed value did not cause are no kills: a row that cannot be repeated in one run, a stand that
    fails in a step before the one that uses the value, a value Cucumber rejected before the step definition saw it."""

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

    def test_the_controls_run_before_and_after_the_mutants_whatever_the_project_s_own_acceptance_run_does(self):
        # the project runs its scenarios in parallel - in junit-platform.properties, as system properties of every
        # Test task after the kit, in a doFirst of its own or as JVM arguments before the kit - or, on Cucumber 8, in
        # a random order: both controls ran first, the stand's quota failed the mutant - a "kill" of a step that
        # ignores <credits> - and the gate passed (review of efa4c50 and of its fixes). Its forks each ran every
        # scenario once more.
        self.project(example=False)
        self.file(GLUE + "CreditSteps.java", CREDIT_STEPS)
        self.file(GLUE + "PurchaseSteps.java", PURCHASE_STEPS)
        self.file(FEATURES + "credits.feature", CREDITS)
        build = os.path.join(self.lab, "build.gradle")
        properties_file = os.path.join(self.lab, "src/acceptanceTest/resources/junit-platform.properties")
        plain = kit.read(build)
        apply = "apply from: 'gauntlet/gauntlet.gradle'"

        def results(task):
            return "".join(kit.read(p) for p in glob.glob(os.path.join(self.lab, "build", task, "*.xml")))

        def before_the_kit(block):
            return plain.replace(apply, "tasks.withType(Test).configureEach {\n" + block + "}\n" + apply, 1)

        properties = "".join(f"        systemProperty '{key}', '{value}'\n" for key, value in PARALLEL.items())
        arguments = ", ".join(f"'-D{key}={value}'" for key, value in PARALLEL.items())
        variants = {    # build script, junit-platform.properties, Cucumber, the project's own run is parallel
            "tasks.withType(Test) after the kit": (plain + "tasks.withType(Test).configureEach {\n    maxParallelForks = 2\n"
                                                   "    forkEvery = 1\n" + properties.replace("        ", "    ") + "}\n",
                                                   None, CUCUMBER, True),
            "junit-platform.properties": (plain, PARALLEL, CUCUMBER, True),
            "a doFirst of the project before the kit": (before_the_kit("    doFirst {\n" + properties + "    }\n"), None,
                                                        CUCUMBER, True),
            "JVM arguments of a provider before the kit": (before_the_kit(
                "    jvmArgumentProviders.add({ [" + arguments + "] } as CommandLineArgumentProvider)\n"), None, CUCUMBER, True),
            "a random order on Cucumber 8": (plain, {"cucumber.execution.order": "random",
                                                     "cucumber.execution.order.random.seed": "7"}, "8.0.1", False),
        }
        for where, (script, platform, version, parallel) in variants.items():
            with self.subTest(where):
                kit.write(build, script)
                kit.set_property(self.lab, "cucumber.version", version)
                if platform:
                    kit.write(properties_file, "".join(f"{key}={value}\n" for key, value in platform.items()))
                elif os.path.exists(properties_file):
                    os.remove(properties_file)
                self.commit(where)
                r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
                self.assert_build(r, False)
                self.assertIn("1 mutant(s) - 0 killed, 1 survived, 0 error(s); 2 control(s) - 1 passed", r.out)
                self.assertRegex(r.out, r"MUTANT ERROR +z1 control \(unmutated scenario, after the mutants\) failed")
                mutant_run = results("gherkin-mutation/results")
                self.assertEqual(3, mutant_run.count("<testcase "), "c1, m1 and z1 once each, one at a time")
                self.assertNotIn("purchase on ForkJoinPool-", mutant_run)
                if parallel:    # the project's own acceptance run keeps its parallel mode
                    self.assertIn("purchase on ForkJoinPool-", results("test-results/acceptanceTest"))

    def test_a_stand_failure_in_a_step_whose_text_holds_a_line_break_kills_nothing(self):
        # the address cell holds \n, so the Given's text - and Cucumber's step frame - holds a line break. The stand
        # is down while the mutant of <count> runs, in that Given, before the hollow Then that first uses <count>. Read
        # only to the end of the frame's first line, the failure named no line and counted as a kill (review of efa4c50)
        self.project(example=False)
        self.file(GLUE + "LabelSteps.java", """package com.example.service.acceptance;

import static org.junit.jupiter.api.Assertions.assertEquals;

import io.cucumber.java.Before;
import io.cucumber.java.Scenario;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;

public class LabelSteps {
    private String scenario;

    @Before
    public void name(Scenario current) {
        scenario = current.getName();
    }

    @Given("the parcel goes to {string}")
    public void address(String value) {
        if (scenario.contains("| count: ")) {
            throw new IllegalStateException("stand unavailable");
        }
        assertEquals("line1\\nline2", value);
    }

    @Then("the label shows {int} parcels")
    public void label(int count) {
    }
}
""")
        self.file(FEATURES + "labels.feature", "Feature: Parcel labels\n\n  Scenario Outline: A parcel is labelled\n"
                  "    Given the parcel goes to \"<address>\"\n    Then the label shows <count> parcels\n\n"
                  "    Examples:\n      | address      | count |\n      | line1\\nline2 | 3     |\n")
        self.commit("labels")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, False)
        self.assertIn("2 mutant(s) - 1 killed, 0 survived, 1 error(s); 2 control(s) - 2 passed", r.out)
        self.assertRegex(r.out, r"MUTANT ERROR +m2 failed on line 4, before the first step that uses <count> \(line 5\)"
                         r" - the changed value did not cause it, not a kill")

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


class GherkinTransformers(GradleCase):
    """A transformer (@ParameterType, ...) is known as Cucumber knows it: by the class and the name of its compiled
    method, whatever the source encoding of the glue, its debug information or a namesake elsewhere."""

    def view_project(self, compile_options, encoding="utf-8"):
        # the Then step is hollow: a value the transformer rejected must be an error, never a kill
        self.project(example=False, build_extra="tasks.withType(JavaCompile).configureEach {\n"
                     f"    if (name == 'compileAcceptanceTestJava') {{\n        {compile_options}\n    }}\n}}")
        self.file(GLUE + "Status.java", "package com.example.service.acceptance;\n\npublic enum Status { NEW, PAID, SHIPPED }\n",
                  encoding)
        self.file(GLUE + "StatusTypes.java", STATUS_TYPES, encoding)
        self.file(GLUE + "ViewSteps.java", VIEW_STEPS, encoding)
        self.file(FEATURES + "view.feature", "Feature: Order view\n\n  Scenario Outline: An order in any status can be viewed\n"
                  "    Given an order in status <status>\n    Then the order can be viewed\n\n"
                  "    Examples:\n      | status |\n      | PAID   |\n")
        self.commit("order view")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, False)
        self.assertIn("1 mutant(s) - 0 killed, 0 survived, 1 error(s); 2 control(s) - 2 passed", r.out)
        self.assertIn("the value never reached a step definition (java.lang.IllegalArgumentException", r.out)

    def test_a_transformer_rejects_the_value_whatever_the_encoding_of_the_glue_sources(self):
        # read as UTF-8, a UTF-16LE source named no transformer: the rejected value was a kill (review of 2c1cd0b)
        self.view_project("options.encoding = 'UTF-16LE'", "utf-16-le")

    def test_a_transformer_compiled_without_debug_information_rejects_the_value(self):
        # without debug information the frame names no source file - "StatusTypes.status(Unknown Source)"
        self.view_project("options.debug = false")

    def test_a_namesake_transformer_in_another_package_takes_no_kill(self):
        # a @ParameterType `result` in another package's DiscountSteps.java turned the 9 kills of the step
        # definition DiscountSteps.result into 9 errors (review of 2c1cd0b)
        self.project()
        self.file(GLUE + "reporting/DiscountSteps.java", """package com.example.service.acceptance.reporting;

import io.cucumber.java.ParameterType;

public class DiscountSteps {
    @ParameterType("сводка|отчёт")
    public String result(String value) {
        return value;
    }
}
""")
        self.commit("a report parameter type")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, True)
        self.assertIn("Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s); 6 control(s) - 6 passed", r.out)


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
        homes, project, gate = self.two_jdks()
        self.project(build_extra=f"tasks.withType(Test).configureEach {{ executable = '{homes[project]}/bin/java' }}")
        kit.set_property(self.lab, "gate.java.version", str(gate))
        r = self.gradle("archTest", "gauntletInfo", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, True)
        self.assertNotIn("does not match toolchain", r.out)
        self.assert_jvm(r, "gate executable: ", gate)

    def test_gate_jvm_by_version_next_to_a_launcher_pinned_after_the_kit(self):
        # a convention plugin pins the launcher in afterEvaluate - after the kit configured its gate tasks
        homes, project, gate = self.two_jdks()
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

    def test_a_build_whose_checks_compile_every_source_set_does_not_need_the_gate_jdk(self):
        # Gradle's checkstyle and pmd plugins (and SpotBugs) give the task of every source set its compiled classes, so
        # `gradle build` compiles the kit's test - with the gate compiler, which failed where no gate JDK is installed
        # (review of the merged fixes for 2c1cd0b)
        self.project(build_extra="apply plugin: 'checkstyle'")
        self.file("config/checkstyle/checkstyle.xml", '<?xml version="1.0"?>\n<!DOCTYPE module PUBLIC '
                  '"-//Checkstyle//DTD Checkstyle Configuration 1.3//EN" "https://checkstyle.org/dtds/configuration_1_3.dtd">\n'
                  '<module name="Checker"/>\n')
        kit.set_property(self.lab, "gate.java.version", "99")
        r = self.gradle("build", "-Porg.gradle.java.installations.auto-download=false")
        self.assert_build(r, True)
        self.assertIn("Task :checkstyleArchTest", r.out)

    def two_jdks(self):
        """The project's JDK and the gate's: the two newest (a runner also carries JDK 8, 11, 17). The project's may
        be any Java - its compiler builds the kit's ArchUnit test, Java 8 code - but the gate runs the kit's tools,
        Java 16 code (records): with no JDK 17+ there is no gate to run them on."""
        homes = jdk_homes()
        if len(homes) < 2:
            self.skipTest("needs two installed JDKs")
        project, gate = sorted(homes)[-2:]
        if gate < 17:
            self.skipTest(f"the gate runs the kit's tools (Java 16 code): needs a JDK 17+, the newest is {gate}")
        return homes, project, gate

    def assert_jvm(self, result, label, where):
        """The JVM a line `<label><path to java>` names: that very JDK when `where` is a home, any JDK of that
        major version when it is a number - by version, Gradle picks the installation."""
        m = re.search("(?m)^" + re.escape(label) + "(.+)$", result.out)
        self.assertTrue(m, f"no line '{label}...'\n" + result.out[-3000:])
        if isinstance(where, int):
            self.assertEqual(java_major(m.group(1)), where, m.group(0))
        else:
            self.assertEqual(os.path.realpath(m.group(1)), os.path.realpath(os.path.join(where, "bin", "java")),
                             m.group(0))

    def assert_ran_on(self, result, where, *tasks):
        for task in tasks:
            self.assert_jvm(result, f"{task} ran on ", where)

    def test_gate_jvm_by_a_full_version(self):
        # gate.java.version=21.0.2 asked for a toolchain "21.0.2" while the build was configured: every build
        # failed, `gradle classes` as well (review of 65c03da)
        homes, project, gate = self.two_jdks()
        self.project(build_extra=REPORT_JVM)
        kit.set_property(self.lab, "gate.java.version", f"{gate}.0.2")
        r = self.gradle("classes", "archTest", "gauntletInfo", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, True)
        self.assert_jvm(r, "gate executable: ", gate)
        self.assert_ran_on(r, gate, "archTest")
        kit.set_property(self.lab, "gate.java.version", "latest")
        r = self.gradle("classes", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, True)                    # no gate task asked for: no gate JVM needed
        r = self.gradle("archTest", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, False)
        self.assertIn("gate.java.version 'latest' names no Java version", r.out)
        # a gate older than the kit's own code: named, not javac's "invalid flag" or a class version error
        kit.set_property(self.lab, "gate.java.version", "1.8")
        r = self.gradle("archTest", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, False)
        self.assertIn("gate.java.version '1.8' is Java 8: the gate JVM runs the gauntlet's own tools", r.out)

    def test_gate_jvm_by_home_runs_the_jvm_gate_tasks_there(self):
        # GAUNTLET_GATE_JAVA_HOME (the kit's CI workflow sets it) names the JVM itself; no toolchain is looked up,
        # so a full version in gate.java.version is no obstacle either (review of 65c03da)
        homes, project, gate = self.two_jdks()
        self.project(build_extra=REPORT_JVM)
        kit.set_property(self.lab, "gate.java.version", f"{gate}.0.2")
        r = self.gradle("checkstyleGate", "archTest", "acceptanceTest", "test", "gauntletInfo",
                        env={"JAVA_HOME": homes[project], "GAUNTLET_GATE_JAVA_HOME": homes[gate]})
        self.assert_build(r, True)
        self.assert_jvm(r, "gate executable: ", homes[gate])
        self.assert_ran_on(r, homes[gate], "checkstyleGate", "archTest", "acceptanceTest")
        self.assert_ran_on(r, homes[project], "test")

    def test_a_launcher_read_by_an_init_script_once_the_project_is_evaluated(self):
        # an IDE's model builder or a plugin in an init script reads the launcher of every JVM task, and Gradle
        # keeps a launcher that was read: setting the gate JVM later threw while the build was configured, whatever
        # task was asked for (review of 65c03da)
        homes, project, gate = self.two_jdks()
        init = kit.write(os.path.join(self.tmp, "late-reader.gradle"), LATE_READER)
        self.project(build_extra=REPORT_JVM)
        kit.set_property(self.lab, "gate.java.version", str(gate))
        r = self.gradle("checkstyleGate", "archTest", "test", "-I", init, env={"JAVA_HOME": homes[project]})
        self.assert_build(r, True)
        self.assert_ran_on(r, gate, "checkstyleGate", "archTest")
        self.assert_ran_on(r, homes[project], "test")
        r = self.gradle("checkstyleGate", "archTest", "-I", init,
                        env={"JAVA_HOME": homes[project], "GAUNTLET_GATE_JAVA_HOME": homes[gate]})
        self.assert_build(r, True)
        self.assert_ran_on(r, homes[gate], "checkstyleGate", "archTest")

    def test_a_launcher_pinned_in_after_evaluate_and_read_once_the_projects_are_evaluated(self):
        # a convention plugin pins the launcher in afterEvaluate - applied before the kit or after it - and an init
        # script reads every launcher once the projects are evaluated, before the kit's own projectsEvaluated: the
        # project's launcher was fixed and the gate tasks stopped on it (review of 2c1cd0b, Kimi P1 - a reader in
        # the user's ~/.gradle/init.d, not the pair of JDKs)
        homes, project, gate = self.two_jdks()
        init = kit.write(os.path.join(self.tmp, "evaluated-reader.gradle"), EVALUATED_READER)
        pin = ("\nafterEvaluate {\n    tasks.withType(Test).configureEach {\n        javaLauncher = "
               f"javaToolchains.launcherFor {{ languageVersion = JavaLanguageVersion.of({project}) }}\n    }}\n}}\n")
        self.project()
        kit.set_property(self.lab, "gate.java.version", str(gate))
        for place, build in (("before the kit", BUILD.format(junit=JUNIT, extra=REPORT_JVM + pin)),
                             ("after the kit", BUILD.format(junit=JUNIT, extra=REPORT_JVM) + pin)):
            with self.subTest(pinned=place):
                self.file("build.gradle", build)
                r = self.gradle("archTest", "acceptanceTest", "test", "-I", init, env={"JAVA_HOME": homes[project]})
                self.assert_build(r, True)
                self.assert_ran_on(r, gate, "archTest", "acceptanceTest")
                self.assert_ran_on(r, homes[project], "test")

    def test_a_launcher_fixed_before_the_kit_could_set_it_is_named(self):
        # a launcher read before the kit set it (here: by the build script itself) cannot be changed any more; the
        # gate task says so instead of running on the project's JVM
        homes, project, gate = self.two_jdks()
        self.project(build_extra="tasks.withType(Test).configureEach { it.javaLauncher.getOrNull() }")
        kit.set_property(self.lab, "gate.java.version", str(gate))
        r = self.gradle("help", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, True)
        r = self.gradle("archTest", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, False)
        self.assertIn(":archTest would run on", r.out)
        self.assertIn(f"not on the gate JVM (Java {gate})", r.out)

    def test_a_result_of_another_gate_jvm_is_not_reused(self):
        # the same fixed launcher passes the check while the gate asks for the project's own version; asked for
        # another one, the gate tasks were UP-TO-DATE or came from the build cache, and the check in doFirst never
        # ran: a green build on the old result (review of 2c1cd0b, Codex 3)
        homes, project, gate = self.two_jdks()
        if project < 17:
            self.skipTest(f"the gate first asks for the project's Java {project}; a gate runs the kit's tools: 17+")
        self.project(build_extra="tasks.withType(Test).configureEach { it.javaLauncher.getOrNull() }\n"
                                 "tasks.withType(JavaExec).configureEach { it.javaLauncher.getOrNull() }")
        cache = os.path.join(self.tmp, "build-cache")             # this build's own: nothing from other builds
        self.file("settings.gradle", f"rootProject.name = 'lab'\nbuildCache {{ local {{ directory = '{cache}' }} }}\n")
        env = {"JAVA_HOME": homes[project]}
        kit.set_property(self.lab, "gate.java.version", str(project))
        r = self.gradle("archTest", "cpdReport", "--build-cache", env=env)
        self.assert_build(r, True)
        kit.set_property(self.lab, "gate.java.version", str(gate))
        with self.subTest("outputs in place"):
            r = self.gradle("archTest", "cpdReport", "--continue", env=env)
            self.assert_build(r, False)
            self.assertIn(":archTest would run on", r.out)
            self.assertIn(":cpdReport would run on", r.out)
            self.assertIn(f"not on the gate JVM (Java {gate})", r.out)
        with self.subTest("build cache"):
            self.assert_build(self.gradle("clean", env=env), True)
            r = self.gradle("archTest", "--build-cache", env=env)
            self.assert_build(r, False)
            self.assertIn(":archTest would run on", r.out)

    ARCH_CLASS = "build/classes/java/archTest/gauntlet/architecture/ArchitectureTest.class"

    def test_the_kit_s_architecture_test_compiles_for_the_project_s_java(self):
        # gauntlet/archtest was Java 16 code (Path.of, String.isBlank, Stream.toList) and the project's compiler
        # builds it: a project that compiles for Java 8 or 11 - on that JDK, with that toolchain or with
        # options.release - failed in compileArchTestJava (review of 2c1cd0b). It is Java 8 code now, built at the
        # project's level and run on the gate JVM. A JDK older than 11 compiles for its own Java; a newer one is
        # asked for Java 11, as such a build does.
        homes, project, gate = self.two_jdks()
        old = "tasks.withType(JavaCompile).configureEach { options.release = 11 }\n" if project >= 11 else ""
        self.project(build_extra=old + REPORT_JVM)
        kit.set_property(self.lab, "gate.java.version", str(gate))
        for where, env in ((gate, {}), (homes[gate], {"GAUNTLET_GATE_JAVA_HOME": homes[gate]})):
            with self.subTest(gate=where):
                r = self.gradle("archTest", env={"JAVA_HOME": homes[project], **env})
                self.assert_build(r, True)
                self.assert_ran_on(r, where, "archTest")
                # the project's compiler, as for the project's own classes: Java 8 code since this round
                self.assertEqual(class_java(os.path.join(self.lab, self.ARCH_CLASS)), min(project, 11))
        # the project's own classes stay as the project compiles them
        orders = os.path.join(self.lab, "build/classes/java/main/com/example/service/domain/Orders.class")
        self.assertEqual(class_java(orders), min(project, 11))
        # no gate JDK to compile with: the gate's own message, not javac's errors about the kit's code
        kit.set_property(self.lab, "gate.java.version", "latest")
        r = self.gradle("archTest", env={"JAVA_HOME": homes[project]})
        self.assert_build(r, False)
        self.assertIn("gate.java.version 'latest' names no Java version", r.out)
        self.assertNotIn("cannot find symbol", r.out)

    def test_the_project_s_compiler_settings_stay_with_the_project(self):
        # compilerArgs and forkOptions made for the project's JDK: Gradle and javac refused them next to the gate
        # compiler's --release, and the kit's test (a source set of the project, read by SpotBugs & co. in `check`)
        # came out at the gate's class version - both worked on 2c1cd0b (review of the merged fixes for 2c1cd0b)
        homes, project, gate = self.two_jdks()
        if project < 9:
            self.skipTest(f"javac {project} has no --release, which this scenario hands the project's compiler")
        self.project(build_extra=REPORT_JVM + "\ntasks.withType(JavaCompile).configureEach {\n"
                     f"    options.compilerArgs.addAll(['--release', '{project}'])\n"
                     f"    options.fork = true\n    options.forkOptions.javaHome = file('{homes[project]}')\n}}\n")
        kit.set_property(self.lab, "gate.java.version", str(gate))
        for where, env in ((gate, {}), (homes[gate], {"GAUNTLET_GATE_JAVA_HOME": homes[gate]})):
            with self.subTest(gate=where):
                r = self.gradle("archTest", env={"JAVA_HOME": homes[project], **env})
                self.assert_build(r, True)
                self.assert_ran_on(r, where, "archTest")
                self.assertEqual(class_java(os.path.join(self.lab, self.ARCH_CLASS)), project)   # the project's --release

    def test_a_build_on_a_jdk_older_than_the_kit_s_code(self):
        # the kit's CI runs ./gradlew on the project's JDK - `1.8` is read as 8 - and a runner carries JDK 8 and 11
        homes = jdk_homes()
        old = min(homes, default=None)
        gate = max(homes, default=None)
        if old is None or old >= 16 or gate < 17:
            self.skipTest("needs a JDK older than 16 and a JDK 17+")
        self.project(build_extra=REPORT_JVM)
        kit.set_property(self.lab, "gate.java.version", str(gate))
        r = self.gradle("archTest", "test", env={"JAVA_HOME": homes[old]})
        self.assert_build(r, True)
        self.assert_ran_on(r, gate, "archTest")
        self.assert_ran_on(r, homes[old], "test")


class ArchPolicy(GradleCase):

    def test_a_stricter_architecture_policy_is_judged(self):
        # archTest got the policy file only as a path: a stricter policy left it UP-TO-DATE, and after clean it came
        # FROM-CACHE - green on the old policy's result
        self.project()
        cache = os.path.join(self.tmp, "build-cache")
        self.file("settings.gradle", f"rootProject.name = 'lab'\nbuildCache {{ local {{ directory = '{cache}' }} }}\n")
        self.assert_build(self.gradle("archTest", "--build-cache"), True)
        arch = os.path.join(self.lab, "gauntlet/config/architecture.properties")
        kit.write(arch, re.sub(r"(?m)^forbidden\.domain=.*$", "forbidden.domain=java.lang..", kit.read(arch)))
        with self.subTest("outputs in place"):
            self.assert_build(self.gradle("archTest", "--build-cache"), False)
        with self.subTest("build cache"):
            self.assert_build(self.gradle("clean"), True)
            r = self.gradle("archTest", "--build-cache")
            self.assert_build(r, False)
            self.assertIn("forbids domain -> [java.lang..]", r.out)


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


class HardenerStop(GradleCase):
    """The hardener's loop as hardener.md has it - ./gradlew mutationGate, edit test code, again - and the SubagentStop
    hook of .claude/settings.json that re-runs mutationGate before the hardener may finish. PIT's incremental analysis
    kept a KILLED verdict while the mutated class and the killing test's class were unchanged, and a SURVIVED one while
    the covering test classes were: a test changed through its test data kept its old verdict, and the hook took it
    over from the hardener's last run (pitest UP-TO-DATE). CI starts without the history (review of efa4c50)."""

    PRICES = ("package com.example.service.domain;\n\npublic class Prices {\n    public int fee(int amount) {\n"
              "        if (amount > 0) {\n            return 5;\n        }\n        return 0;\n    }\n}\n")
    PRICES_TEST = ("package com.example.service.domain;\n\nimport static org.junit.jupiter.api.Assertions.assertEquals;\n\n"
                   "import org.junit.jupiter.api.Test;\n\nclass PricesTest {\n    @Test\n    void noFeeAtTheBoundary() {\n"
                   "        assertEquals(0, new Prices().fee(TestData.boundaryAmount()));\n    }\n\n    @Test\n"
                   "    void feeAboveTheBoundary() {\n        assertEquals(5, new Prices().fee(10));\n    }\n}\n")
    TEST_DATA = ("package com.example.service.domain;\n\nfinal class TestData {\n    private TestData() {\n    }\n\n"
                 "    static int boundaryAmount() {\n        return %d;\n    }\n}\n")

    def prices(self, boundary):
        """Prices.fee with its test; the test's input comes from a test-data class (not a constant javac inlines)."""
        self.file(DOMAIN + "Prices.java", self.PRICES)
        self.file(DOMAIN_TEST + "PricesTest.java", self.PRICES_TEST)
        self.file(DOMAIN_TEST + "TestData.java", self.TEST_DATA % boundary)

    def hook(self, event, command):
        env = kit.java_env()
        env["CLAUDE_PROJECT_DIR"] = self.lab
        for name in ("GAUNTLET_GUARD", "GAUNTLET_STOP_HOOK"):
            env.pop(name, None)
        return kit.run(["bash", "-c", command], cwd=self.lab, env=env, input=json.dumps(dict(event, cwd=self.lab)))

    def start_session(self):
        self.project(example=False)
        r = self.hook({"session_id": "s1", "hook_event_name": "SessionStart"},
                      'python3 "$CLAUDE_PROJECT_DIR/gauntlet/hooks/stop_gate.py" --record-start')   # as session_start.sh
        self.assertEqual(r.code, 0, r)

    def hardener_stops(self):
        """The hardener's SubagentStop hook, run as Claude Code runs it: the command of .claude/settings.json."""
        settings = json.loads(kit.read(os.path.join(kit.kit(), ".claude", "settings.json")))
        command, = [h["command"] for entry in settings["hooks"]["SubagentStop"] if entry.get("matcher") == "^hardener$"
                    for h in entry["hooks"]]
        return self.hook({"session_id": "s1", "hook_event_name": "SubagentStop", "agent_type": "hardener",
                          "agent_id": "h1", "stop_hook_active": False}, command)

    def test_the_survivor_a_test_data_change_leaves_stops_the_hardener(self):
        self.start_session()
        self.prices(boundary=0)
        self.commit("prices")
        self.assert_build(self.gradle("mutationGate", "--continue"), True)      # 3 killed
        self.prices(boundary=-1)                        # the boundary test no longer sits on the boundary
        r = self.gradle("mutationGate", "--continue")
        self.assertIn("{KILLED=2, SURVIVED=1}", r.out)  # was {KILLED=3}: "Incremental analysis reduced ... by 3"
        r = self.hardener_stops()
        self.assertEqual(r.code, 2, r)
        self.assertIn("changed conditional boundary", r.out)

    def test_the_kill_a_test_data_change_makes_lets_the_hardener_go(self):
        self.start_session()
        self.prices(boundary=-1)
        self.commit("prices")
        self.assert_build(self.gradle("mutationGate", "--continue"), False)     # the boundary mutant survives
        self.prices(boundary=0)
        r = self.gradle("mutationGate", "--continue")
        self.assertIn("PIT summary: 3 mutant(s) {KILLED=3}", r.out)             # was the old survivor
        r = self.hardener_stops()
        self.assertEqual(r.code, 0, r)


if __name__ == "__main__":
    unittest.main()
