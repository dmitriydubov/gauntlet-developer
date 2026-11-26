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


def jvm_homes():
    """JVM homes by the major version their java names in `java -version`, also one without a release file (Ubuntu's
    JDK 8 has none, so jdk_homes() leaves it out): where JAVA_HOME_<major>_<ARCH> point, then under /usr/lib/jvm."""
    homes = {}
    candidates = [home for name, home in sorted(os.environ.items()) if re.fullmatch(r"JAVA_HOME(_\d+_\w+)?", name)]
    candidates += sorted(glob.glob("/usr/lib/jvm/*/"))
    for home in candidates:
        java = os.path.join(home, "bin", "java")
        said = kit.run([java, "-version"]).out if os.access(java, os.X_OK) else ""
        m = re.search(r'(?m)^\S+ version "(?:1\.)?(\d+)', said)
        if m:
            homes.setdefault(int(m.group(1)), os.path.realpath(home))
    return homes


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
                     "Test census: OK - test classes run (ran/compiled): test 1/1, archTest 1/1",
                     "CRAP gate: OK", "DRY gate: OK", "PIT summary: 2 mutant(s) {KILLED=2}",
                     "Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s); 6 control(s) - 6 passed",
                     "Gherkin mutation: OK"):
            self.assertIn(line, r.out)
        # what the Stop hook and CI demand of a green run: Gradle's own "> Task" line for every gate task
        self.assertEqual(kit.stop_gate().not_run("gauntlet", r.out), [])

    def test_hollow_step_definition_leaves_survivors(self):
        self.project(steps_assert="assertEquals(true, total > 0)")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
        self.assert_build(r, False)
        self.assertIn("MUTANT SURVIVED", r.out)
        self.assertIn("6 control(s) - 6 passed", r.out)

    def test_shipped_example_passes_by_cucumber_s_message_streams_on_cucumber_7_and_8(self):
        # The acceptance census and the order of the mutant run are judged by Cucumber's message stream. Cucumber 8
        # writes it only with Jackson on the classpath (the kit's default acceptance dependencies bring Jackson 3);
        # without it the run fails before any scenario.
        self.project()
        for version in (CUCUMBER, "8.0.1"):
            with self.subTest(cucumber=version):
                kit.set_property(self.lab, "cucumber.version", version)
                r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
                self.assert_build(r, True)
                for line in ("Acceptance census: 3 of 3 scenario(s) in 1 feature file(s) ran",
                             "Acceptance: 3 scenario(s), none skipped - OK",
                             "Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s); 6 control(s) - 6 passed",
                             "Gherkin mutation: OK"):
                    self.assertIn(line, r.out)
                self.assertNotIn("run order", r.out)
                for stream in ("build/cucumber-messages/acceptanceTest/jvm-1.ndjson",
                               "build/gherkin-mutation/messages/jvm-1.ndjson"):
                    self.assertIn(f'"version":"{version}"', kit.read(os.path.join(self.lab, stream)).replace(" ", ""))


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

    def test_every_retry_round_is_judged_by_its_own_message_stream(self):
        # each round runs in a JVM of its own and would write the stream anew: the kit keeps one stream per JVM. Here
        # an argument file runs both rounds in parallel on the quota stand - the mutant "killed" on both attempts, the
        # controls passed on both, and the gate passed (issue #4). Gradle lists the file, not the -D inside it.
        self.project(example=False)
        argfile = self.file("build-args/parallel.args", "".join(f"-D{key}={value}\n" for key, value in PARALLEL.items()))
        build = os.path.join(self.lab, "build.gradle")
        kit.write(build, kit.read(build).replace("apply from: 'gauntlet/gauntlet.gradle'\n", RETRY % (
            f"    doFirst {{ jvmArgumentProviders.add({{ ['@{argfile}'] }} as CommandLineArgumentProvider) }}") +
            "\napply from: 'gauntlet/gauntlet.gradle'\n"))
        kit.write(build, kit.read(build).replace("    id 'java'\n", "    id 'java'\n    id 'org.gradle.test-retry' version '1.6.2'\n"))
        self.file(GLUE + "CreditSteps.java", CREDIT_STEPS)
        self.file(GLUE + "PurchaseSteps.java", PURCHASE_STEPS)
        self.file(FEATURES + "credits.feature", CREDITS)
        self.commit("credits, retried")
        for merge in ("true", "false"):
            with self.subTest(mergeReruns=merge):
                r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all", f"-PmergeReruns={merge}")
                self.assert_build(r, False)
                self.assertNotIn("Gherkin mutation: OK", r.out)
                streams = sorted(os.listdir(os.path.join(self.lab, "build/gherkin-mutation/messages")))
                self.assertEqual(["jvm-1.ndjson", "jvm-2.ndjson"], streams)        # a round each
                for stream in streams:
                    self.assertRegex(r.out, r"MUTANT ERROR +run order: \S+ and \S+ ran at the same time \(" + stream)

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


ANY_STEPS = """package com.example.service.acceptance;

import io.cucumber.java.en.Given;

public class AnySteps {
    @Given("^step (.*)$")
    public void any(String text) {
    }
}
"""
CENSUS_FEATURES = {     # next to the kit's example: Outlines with several Examples tables, Rules, a subdirectory
    "outlines.feature": "Feature: Outlines\n\n  Scenario: Plain one\n    Given step one\n\n"
                        "  Scenario Outline: Two tables\n    Given step <a>\n\n    Examples: first\n      | a |\n      | 1 |\n"
                        "      | 2 |\n\n    @slow\n    Examples: second\n      | a |\n      | 3 |\n      | 4 |\n      | 5 |\n\n"
                        "  Scenario Outline: Header only\n    Given step <a>\n\n    Examples:\n      | a |\n\n"
                        "  Scenario: No steps of its own\n",
    "rules.feature": "Feature: Rules\n  Background:\n    Given step background\n\n  Rule: First rule\n    Background:\n"
                     "      Given step rule background\n\n    Scenario: In the first rule\n      Given step r1\n\n"
                     "    Scenario Outline: Outline in a rule\n      Given step <b>\n\n      Examples:\n        | b |\n"
                     "        | x |\n        | y |\n\n  Rule: Second rule\n\n    @slow\n    Scenario: In the second rule\n"
                     "      Given step r2\n",
    "sub/dir/nested.feature": "Feature: Nested\n\n  Scenario: Deep down\n    Given step deep\n",
}


SPRING_BOOT_4 = """plugins {
    id 'java'
    id 'org.springframework.boot' version '4.0.7'
    id 'io.spring.dependency-management' version '1.1.7'
    id 'info.solidsoft.pitest' version '1.19.0'
}
group = 'com.example'
repositories { mavenCentral() }
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}
test { useJUnitPlatform() }
apply from: 'gauntlet/gauntlet.gradle'
"""
SPRING_APPLICATION = """package com.example.service;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class DemoApplication {
    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }
}
"""


class SpringBoot(GradleCase):
    """The reference stack as Spring Initializr makes it: Spring Boot 4 with the dependency-management plugin, the kit's
    defaults (acceptance.spring=true, Cucumber 8.0.1). Review of 4.4: the Jackson the kit adds for Cucumber 8's message
    stream came in its own version next to Boot's jackson-core, and Cucumber failed at start on every run."""

    def test_spring_boot_4_with_dependency_management_runs_the_acceptance_gates(self):
        self.project()
        kit.set_property(self.lab, "acceptance.spring", "true")
        kit.set_property(self.lab, "cucumber.version", "8.0.1")
        self.file("build.gradle", SPRING_BOOT_4)
        self.file("src/main/java/com/example/service/DemoApplication.java", SPRING_APPLICATION)
        template = "gauntlet/templates/acceptanceTest/java/com/example/service/acceptance/CucumberSpringConfiguration.java"
        self.file(GLUE + "CucumberSpringConfiguration.java", kit.read(os.path.join(self.lab, template)))
        self.commit("spring boot 4")
        r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all", "--continue")
        self.assert_build(r, True)
        self.assertIn("Acceptance census: 3 of 3 scenario(s) in 1 feature file(s) ran", r.out)
        self.assertIn("Gherkin mutation: 9 mutant(s) - 9 killed, 0 survived, 0 error(s); 6 control(s) - 6 passed", r.out)
        deps = self.gradle("dependencies", "--configuration", "acceptanceTestRuntimeClasspath")
        self.assertRegex(deps.out, r"tools\.jackson\.core:jackson-databind -> 3\.\d+\.\d+")   # the version Boot manages


class AcceptanceCensus(GradleCase):
    """acceptanceCheck: every scenario the feature files define must have run (issue #4). A filter that drops
    scenarios silently - includeTags/excludeTags of the test platform, a narrower cucumber.features - left the gate
    green; Cucumber's own filters report the scenarios skipped, and fail as before. The census counts what Cucumber
    compiles and runs, as its message stream and the JUnit XML report it."""

    def cucumber_counts(self):
        """Cucumber's own report of the acceptance run: per feature file, the pickles it compiled and those that ran."""
        compiled, ran = {}, {}
        for path in glob.glob(os.path.join(self.lab, "build/cucumber-messages/acceptanceTest/*.ndjson")):
            pickles, cases, started = {}, {}, {}
            for line in kit.read(path).splitlines():
                envelope = json.loads(line)
                if "pickle" in envelope:
                    pickles[envelope["pickle"]["id"]] = os.path.basename(envelope["pickle"]["uri"])
                elif "testCase" in envelope:
                    cases[envelope["testCase"]["id"]] = envelope["testCase"]["pickleId"]
                elif "testCaseStarted" in envelope:
                    started[envelope["testCaseStarted"]["id"]] = envelope["testCaseStarted"]["testCaseId"]
                elif "testCaseFinished" in envelope:
                    name = pickles[cases[started[envelope["testCaseFinished"]["testCaseStartedId"]]]]
                    ran[name] = ran.get(name, 0) + 1
            for name in pickles.values():
                compiled[name] = compiled.get(name, 0) + 1
        return compiled, ran

    def test_the_project_s_cucumber_settings_cannot_skip_the_steps_or_the_scenarios(self):
        # review of 4.4: a dry run (cucumber.execution.dry-run) passed every step without running the glue, and the
        # census counted the scenarios as run; a trailing comma of the project's plugin list broke Cucumber once the
        # kit appended its stream; discovery.as-root-engine=false (a @Suite setup) let Cucumber discover nothing
        self.project(steps_assert="assertEquals(expected + 1, total)")      # every scenario fails when its glue runs
        properties = os.path.join(self.lab, "src/acceptanceTest/resources/junit-platform.properties")
        build = os.path.join(self.lab, "build.gradle")
        plain = kit.read(build)
        for version in (CUCUMBER, "8.0.1"):
            kit.set_property(self.lab, "cucumber.version", version)
            for where, script, platform, failure in (
                    ("the build script", "tasks.withType(Test).configureEach { systemProperty "
                                         "'cucumber.execution.dry-run', 'true' }\n", None, "expected: <"),
                    ("junit-platform.properties", "", "cucumber.execution.dry-run=true\n", "expected: <"),
                    ("_JAVA_OPTIONS of the task", "tasks.withType(Test).configureEach { environment '_JAVA_OPTIONS', "
                                                  "'-Dcucumber.execution.dry-run=true' }\n", None,
                     "acceptanceTest ran with _JAVA_OPTIONS -Dcucumber.execution.dry-run=true")):
                with self.subTest(cucumber=version, dry_run=where):
                    kit.write(build, plain + script)
                    if platform:
                        kit.write(properties, platform)
                    elif os.path.exists(properties):
                        os.remove(properties)
                    r = self.gradle("acceptanceTest", "-Pgauntlet.scope=all")
                    self.assert_build(r, False)
                    self.assertRegex(r.out, r"(?m)^> Task :acceptanceTest FAILED$")
                    self.assertIn(failure, r.out)       # the glue ran and its assertion failed, or the run is refused
        kit.write(build, plain)
        self.file(GLUE + "DiscountSteps.java", DISCOUNT_STEPS % "assertEquals(expected, total)")
        for version, platform in ((CUCUMBER, "cucumber.plugin=pretty,\n"), ("8.0.1", "cucumber.plugin=pretty,\n"),
                                  ("8.0.1", "cucumber.junit-platform.discovery.as-root-engine=false\n")):
            with self.subTest(cucumber=version, properties=platform.strip()):
                kit.set_property(self.lab, "cucumber.version", version)
                kit.write(properties, platform)
                r = self.gradle("acceptanceTest", "-Pgauntlet.scope=all")
                self.assert_build(r, True)
                self.assertIn("Acceptance census: 3 of 3 scenario(s) in 1 feature file(s) ran", r.out)

    def test_every_scenario_the_feature_files_define_ran_or_is_finding_f2(self):
        self.project()
        self.file(GLUE + "AnySteps.java", ANY_STEPS)
        for rel, text in CENSUS_FEATURES.items():
            self.file(FEATURES + rel, text)
        self.commit("feature files for a census")
        build = os.path.join(self.lab, "build.gradle")
        plain = kit.read(build)
        properties = os.path.join(self.lab, "src/acceptanceTest/resources/junit-platform.properties")
        files = {"example_discount.feature": "", "outlines.feature": "", "rules.feature": "", "nested.feature": "sub/dir/"}
        variants = {    # the project's build script after the kit, junit-platform.properties, how the run fails
            "no filter": ("", None, None),
            "excludeTags of the test platform": ("tasks.named('acceptanceTest') { useJUnitPlatform { excludeTags 'slow' } }\n",
                                                 None, "F2"),
            "a narrower cucumber.features": ("tasks.named('acceptanceTest') { systemProperty 'cucumber.features', "
                                             f"file('{FEATURES}sub').absolutePath }}\n", None, "F2"),
            "cucumber.filter.tags": ("", "cucumber.filter.tags=not @slow\n", "skipped"),
            "cucumber.filter.name": ("tasks.named('acceptanceTest') { systemProperty 'cucumber.filter.name', "
                                     "'^(Plain one|Deep down)$' }\n", None, "skipped"),
            "excludeTags accepted by the human": ("tasks.named('acceptanceTest') { useJUnitPlatform { excludeTags 'slow' } }\n",
                                                  None, "accepted"),
        }
        for version in (CUCUMBER, "8.0.1"):
            kit.set_property(self.lab, "cucumber.version", version)
            defined = None
            for what, (script, platform, failure) in variants.items():
                with self.subTest(cucumber=version, variant=what):
                    kit.write(build, plain + script)
                    if platform:
                        kit.write(properties, platform)
                    elif os.path.exists(properties):
                        os.remove(properties)
                    allowlist = os.path.join(self.lab, "gauntlet/config/integrity-allowlist.txt")
                    kit.write(allowlist, "".join(f"{FEATURES}{rel}  F2\n" for rel in ("outlines.feature", "rules.feature"))
                              if failure == "accepted" else "")
                    self.commit(f"{version}: {what}")
                    r = self.gradle("acceptanceTest", "-Pgauntlet.scope=all")
                    compiled, ran = self.cucumber_counts()
                    if defined is None:             # the run without a filter: Cucumber compiles every feature file
                        defined = compiled
                        self.assertEqual({"example_discount.feature": 3, "outlines.feature": 7, "rules.feature": 4,
                                          "nested.feature": 1}, defined)
                        xml = "".join(kit.read(p) for p in glob.glob(os.path.join(self.lab, "build/test-results/acceptanceTest/*.xml")))
                        self.assertEqual(sum(defined.values()), xml.count("<testcase "))
                    total = f"{sum(ran.values())} of {sum(defined.values())} scenario(s) in 4 feature file(s) ran"
                    self.assert_build(r, failure in (None, "accepted"))
                    if failure == "accepted":
                        missing = sum(defined.values()) - sum(ran.values())
                        self.assertIn(f"Acceptance census: {total}; {missing} did not run, accepted by the integrity"
                                      " allowlist (F2)", r.out)
                    else:
                        self.assertIn(f"Acceptance census: {total}", r.out)
                    for name, prefix in files.items():
                        line = (f"ACCEPTANCE F2 {FEATURES}{prefix}{name}  {ran.get(name, 0)} of {defined[name]} scenario(s)"
                                " ran")
                        if failure in ("F2", "skipped") and ran.get(name, 0) < defined[name]:
                            self.assertIn(line, r.out)
                        else:
                            self.assertNotIn(f"ACCEPTANCE F2 {FEATURES}{prefix}{name} ", r.out)
                    if failure == "skipped":        # Cucumber's own filters: reported skipped, as before
                        self.assertIn("scenario(s) skipped", r.out)
                    if what == "a narrower cucumber.features":
                        self.assertIn(f"ACCEPTANCE F2 {FEATURES}outlines.feature  0 of 7 scenario(s) ran - Cucumber did not"
                                      " load the file", r.out)
                        self.assertIn(f"ACCEPTANCE F2 {FEATURES}outlines.feature:3  did not run  |  Plain one", r.out)
                    if what == "excludeTags of the test platform":
                        self.assertIn(f"ACCEPTANCE F2 {FEATURES}rules.feature:23  did not run  |  In the second rule", r.out)
                        # what the gate passed on: the JUnit XML holds 11 scenarios, none skipped
                        xml = "".join(kit.read(p) for p in glob.glob(os.path.join(self.lab, "build/test-results/acceptanceTest/*.xml")))
                        self.assertEqual((11, 0), (xml.count("<testcase "), xml.count("<skipped")))


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

    def test_added_step_in_shared_glue_mutates_only_impacted_feature_and_skips_repeat_mutant_run(self):
        self.project()
        self.git("checkout", "-q", "main")
        self.file(
            GLUE + "StandHooks.java",
            "package com.example.service.acceptance;\n\nimport io.cucumber.java.After;\nimport io.cucumber.java.Before;\n\n"
            "public class StandHooks {\n    @Before\n    public void beforeScenario() {}\n\n"
            "    @After\n    public void afterScenario() {}\n}\n",
        )
        self.commit("unchanged scenario hooks on main")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-B", "feature", "main")
        # Add a new step + static field to DiscountSteps (used by example_discount.feature) and a new vip.feature
        vip_steps = DISCOUNT_STEPS.replace(
            "public class DiscountSteps {\n",
            "public class DiscountSteps {\n    private static final int VIP_BONUS = 50;\n",
        ).replace(
            "    @Тогда(\"итог заказа составляет {int} руб.\")",
            "    @Дано(\"VIP-клиент с базовой скидкой {int} руб.\")\n"
            "    public void vipClient(int base) {\n        discount = base + VIP_BONUS;\n    }\n\n"
            "    @Тогда(\"итог заказа составляет {int} руб.\")",
        ) % "assertEquals(expected, total)"
        self.file(GLUE + "DiscountSteps.java", vip_steps)
        self.file(
            FEATURES + "vip.feature",
            "# language: ru\nФункция: VIP-скидка\n\n  Структура сценария: Заказ VIP-клиента\n"
            "    Дано VIP-клиент с базовой скидкой <база> руб.\n"
            "    Когда клиент оформляет заказ на сумму <сумма> руб.\n"
            "    Тогда итог заказа составляет <итог> руб.\n\n"
            "    Примеры:\n      | база | сумма | итог |\n      | 100  | 1000  | 850  |\n",
        )
        self.commit("vip discount step in shared glue")
        # 1. gherkinMutation narrows scope to vip.feature only (3 mutants + 2 controls, not 9+3=12)
        r1 = self.gradle("gherkinMutation")
        self.assert_build(r1, True)
        self.assertIn("narrowing scope via bytecode + message stream", r1.out)
        self.assertIn("glue impact narrowed scope to 1 of 2 feature file(s)", r1.out)
        self.assertIn("Gherkin mutation: 3 mutant(s) - 3 killed, 0 survived, 0 error(s); 2 control(s) - 2 passed", r1.out)
        # 2. Immediate `gauntlet` skips re-running gherkinMutantsRun while executing gherkinMutants + gherkinMutation
        r2 = self.gradle("gauntlet", "--continue")
        self.assert_build(r2, True)
        self.assertIn("gauntlet: :gherkinMutantsRun skipped by the kit - inputs unchanged since green gherkinMutation", r2.out)
        self.assertIn("Gherkin mutation: OK", r2.out)
        self.assertEqual(kit.stop_gate().not_run("gauntlet", r2.out), [])
        # 3. Non-gauntlet tasks (e.g. dependencies) stay configuration-cache compatible
        deps = self.gradle("dependencies", "--configuration", "testRuntimeClasspath", "--configuration-cache")
        self.assert_build(deps, True)


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

    def test_a_mutant_run_the_project_changed_after_the_kit_is_refused(self):
        # a doFirst registered before the kit - tasks.withType(Test) above the apply line, as a convention plugin,
        # allprojects or an init script registers it - runs after the kit's: its provider won, the scenarios ran in
        # parallel (or at random on Cucumber 8), both controls ran before the mutant, the stand's quota failed it - a
        # kill - and the gate passed; its forks went through as well (review of 7061885). The kit judges the settings
        # once the mutants have run, and a run without the kit's provider is refused as well.
        self.project(example=False)
        self.file(GLUE + "CreditSteps.java", CREDIT_STEPS)
        self.file(GLUE + "PurchaseSteps.java", PURCHASE_STEPS)
        self.file(FEATURES + "credits.feature", CREDITS)
        build = os.path.join(self.lab, "build.gradle")
        plain = kit.read(build)
        apply = "apply from: 'gauntlet/gauntlet.gradle'"

        def provider(properties):
            arguments = ", ".join(f"'-D{key}={value}'" for key, value in properties.items())
            return "        jvmArgumentProviders.add({ [" + arguments + "] } as CommandLineArgumentProvider)\n"

        # The same doFirst reaches acceptanceTest. Without the kit's provider Cucumber writes no message stream there,
        # and the acceptance census fails first; its forks run every scenario in each of two JVMs, and when the two
        # write the one stream at the same time, the census cannot read it (--continue: the mutant run still runs, and
        # is refused as before).
        variants = {    # the project's doFirst, Cucumber, what the kit names, what the acceptance census says
            "a provider that runs the scenarios in parallel": (provider(PARALLEL), CUCUMBER,
                                                               "cucumber.execution.parallel.enabled=true", None),
            "forks": ("        maxParallelForks = 2\n        forkEvery = 1\n", CUCUMBER,
                      "maxParallelForks=2, forkEvery=1", "ACCEPTANCE ERROR cannot read the message stream "),    # or OK
            "a provider of a random order on Cucumber 8": (
                provider({"cucumber.execution.order": "random", "cucumber.execution.order.random.seed": "7"}), "8.0.1",
                "cucumber.execution.order=random", None),
            # without the kit's provider acceptanceTest itself is refused first (review of 4.4: dry-run and the root
            # engine are the kit's there too), and the mutant run never starts
            "the kit's provider removed": ("        jvmArgumentProviders.clear()\n", CUCUMBER,
                                           "acceptanceTest ran with cucumber.execution.dry-run=unset, "
                                           "cucumber.junit-platform.discovery.as-root-engine=unset: the gates judge",
                                           "ACCEPTANCE ERROR no Cucumber message stream in "),
        }
        for what, (block, version, named, census) in variants.items():
            with self.subTest(what):
                kit.write(build, plain.replace(apply, "tasks.withType(Test).configureEach {\n    doFirst {\n" + block
                                               + "    }\n}\n" + apply, 1))
                kit.set_property(self.lab, "cucumber.version", version)
                self.commit(what)
                r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all", "--continue")
                self.assert_build(r, False)
                self.assertIn("gauntlet: " + named if named.startswith("acceptanceTest ") else
                              "gauntlet: gherkinMutantsRun ran with " + named + ": its controls prove nothing", r.out)
                self.assertNotIn("Gherkin mutation: OK", r.out)
                counted = "Acceptance census: 1 of 1 scenario(s) in 1 feature file(s) ran" in r.out
                if what == "forks":         # whether the two JVMs wrote at the same time
                    self.assertTrue(counted or census in r.out, r.out[-3000:])
                elif census:
                    self.assertIn(census, r.out)
                else:
                    self.assertTrue(counted, r.out[-3000:])

    def credits_project(self, version=CUCUMBER):
        """The quota stand: c1 and m1 use up the two purchases, z1 is refused unless the scenarios ran one at a time."""
        self.project(example=False)
        kit.set_property(self.lab, "cucumber.version", version)
        self.file(GLUE + "CreditSteps.java", CREDIT_STEPS)
        self.file(GLUE + "PurchaseSteps.java", PURCHASE_STEPS)
        self.file(FEATURES + "credits.feature", CREDITS)
        self.commit("credits")
        return os.path.join(self.lab, "build.gradle")

    @staticmethod
    def before_the_kit(script, block):
        """The build script with a tasks.withType(Test) block above the apply line: its doFirst runs after the kit's,
        its doLast before the kit's."""
        apply = "apply from: 'gauntlet/gauntlet.gradle'"
        return script.replace(apply, "tasks.withType(Test).configureEach {\n" + block + "}\n" + apply, 1)

    def results(self):
        """The JUnit XML of the mutant run."""
        return "".join(kit.read(p) for p in glob.glob(os.path.join(self.lab, "build/gherkin-mutation/results/*.xml")))

    def test_a_mutant_run_that_ran_otherwise_than_its_arguments_say_is_judged_by_what_it_did(self):
        # The kit checked the arguments Gradle lists for the mutant run, after the run. Past them (review of 7061885,
        # issue #4): _JAVA_OPTIONS in the task's environment, which the JVM reads after its command line; an argument
        # file (@file, -XX:VMOptionsFile) whose -D Gradle never lists; a provider that answers otherwise at launch than
        # when the kit asks after the run; a doLast of the project, run before the kit's, that takes its provider back.
        # The scenarios ran in parallel, the stand's quota failed the mutant - a "kill" of a step that ignores
        # <credits> -, and the gate passed. Cucumber's message stream of the run shows what it did.
        build = self.credits_project()
        plain = kit.read(build)
        arguments = [f"-D{key}={value}" for key, value in PARALLEL.items()]
        listed = ", ".join(f"'{argument}'" for argument in arguments)
        argfile = self.file("build-args/parallel.args", "\n".join(arguments) + "\n")
        random = "-Dcucumber.execution.order=random -Dcucumber.execution.order.random.seed=7"
        variants = {    # the project's tasks.withType(Test) block, Cucumber, whether the scenarios ran in parallel
            "_JAVA_OPTIONS in the task's environment": (f"    environment '_JAVA_OPTIONS', '{' '.join(arguments)}'\n",
                                                        CUCUMBER, True),
            "an argument file": (f"    doFirst {{ jvmArgumentProviders.add({{ ['@{argfile}'] }} as "
                                 "CommandLineArgumentProvider) }\n", CUCUMBER, True),
            "a VM options file": (f"    doFirst {{ jvmArgumentProviders.add({{ ['-XX:VMOptionsFile={argfile}'] }} as "
                                  "CommandLineArgumentProvider) }\n", CUCUMBER, True),
            "a provider that answers otherwise when asked again": ("    doFirst {\n        def asked = 0\n"
                f"        jvmArgumentProviders.add({{ asked++ == 0 ? [{listed}] : [] }} as CommandLineArgumentProvider)\n"
                "    }\n", CUCUMBER, True),
            "a doLast of the project that takes its provider back": (f"    def parallel = {{ [{listed}] }} as "
                "CommandLineArgumentProvider\n    doFirst { jvmArgumentProviders.add(parallel) }\n"
                "    doLast { jvmArgumentProviders.remove(parallel) }\n", CUCUMBER, True),
            "a random order in _JAVA_OPTIONS on Cucumber 8": (f"    environment '_JAVA_OPTIONS', '{random}'\n", "8.0.1",
                                                               False),
        }
        for what, (block, version, parallel) in variants.items():
            with self.subTest(what):
                kit.write(build, self.before_the_kit(plain, block))
                kit.set_property(self.lab, "cucumber.version", version)
                self.commit(what)
                r = self.gradle("gherkinMutation", "-Pgauntlet.scope=all")
                self.assert_build(r, False)
                self.assertNotIn("Gherkin mutation: OK", r.out)
                if "_JAVA_OPTIONS" in what:     # refused after the run, before the verdict (review of 4.4): the same
                    # tasks.withType(Test) block reaches acceptanceTest, which is refused first
                    self.assertRegex(r.out, r"gauntlet: (acceptanceTest|gherkinMutantsRun) ran with _JAVA_OPTIONS -Dcucumber\.")
                    continue
                self.assertNotIn("gherkinMutantsRun ran with", r.out)          # the arguments Gradle lists were the kit's
                self.assertIn("Gherkin mutation: 1 mutant(s) - ", r.out)      # the verdict ran, and judged the order
                self.assertEqual(parallel, "purchase on ForkJoinPool-" in self.results())
                if parallel:
                    self.assertRegex(r.out, r"MUTANT ERROR +run order: \S+ and \S+ ran at the same time \(jvm-1\.ndjson: ")
                self.assertRegex(r.out, r"MUTANT ERROR +run order: m1 did not run between its controls c1 and z1 - ")

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
        self.assertNotIn(":pitest skipped by the kit", r.out)
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

    def test_a_gate_home_older_than_the_kit_s_code_is_named(self):
        # GAUNTLET_GATE_JAVA_HOME names the JVM itself, and the gate skipped the minimum gate.java.version has for
        # it (issue #3): on JDK 8 the gate tasks failed with that JVM's own errors - a main class not found, a class
        # version - and gauntletInfo named JDK 8 as the gate. The home's java is asked for its version when a gate task
        # starts; a build without gate tasks does not start it.
        homes = jvm_homes()
        old = max((version for version in homes if version < 17), default=None)
        fit = sorted(version for version in homes if version >= 17)
        if old is None or not fit:
            self.skipTest("needs a JVM older than 17 and a JDK 17+")
        # the kit's ArchUnit test is compiled as the project's classes are and runs on the gate JVM: a gate of Java 17
        # loads them when the project compiles for 17
        self.project(build_extra="tasks.withType(JavaCompile).configureEach { options.release = 17 }")
        report = kit.write(os.path.join(self.tmp, "report-jvm.gradle"), REPORT_JVM)    # integrityCheck reads build.gradle
        gate_tasks = ("integrityCheck", "checkstyleGate", "archTest", "gauntletInfo", "-Pgauntlet.scope=all", "-I", report)
        for version in sorted({fit[0], fit[-1]}):                  # the oldest one the gate takes, and the newest
            with self.subTest(gate=version):
                r = self.gradle(*gate_tasks, env={"GAUNTLET_GATE_JAVA_HOME": homes[version]})
                self.assert_build(r, True)
                self.assert_jvm(r, "gate executable: ", homes[version])
                self.assert_ran_on(r, homes[version], "checkstyleGate", "archTest")
        env = {"GAUNTLET_GATE_JAVA_HOME": homes[old]}
        self.assert_build(self.gradle("classes", "test", env=env), True)
        r = self.gradle(*gate_tasks, "--continue", env=env)
        self.assert_build(r, False)
        for task in gate_tasks[:4]:                                # a tool (Exec), JavaExec, Test, gauntletInfo
            self.assertIn(f"Execution failed for task ':{task}'.\n> gauntlet: GAUNTLET_GATE_JAVA_HOME '{homes[old]}' is "
                          f"Java {old}: the gate JVM runs the gauntlet's own tools, which need Java 17 or newer.", r.out)
        r = self.gradle("integrityCheck", f"-Pgauntlet.gateJavaHome={homes[old]}", env={"GAUNTLET_GATE_JAVA_HOME": ""})
        self.assert_build(r, False)
        self.assertIn(f"> gauntlet: gauntlet.gateJavaHome '{homes[old]}' is Java {old}: the gate JVM", r.out)
        # a home without a java that names its version
        missing = os.path.join(self.tmp, "no-jdk")
        r = self.gradle("integrityCheck", "gauntletInfo", "--continue", env={"GAUNTLET_GATE_JAVA_HOME": missing})
        self.assert_build(r, False)
        for task in ("integrityCheck", "gauntletInfo"):
            self.assertIn(f"Execution failed for task ':{task}'.\n> gauntlet: GAUNTLET_GATE_JAVA_HOME '{missing}' names "
                          "no Java the gate can run on", r.out)

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


CENSUS_DEPENDENCIES = """dependencies {
    testImplementation 'junit:junit:4.13.2'
    testRuntimeOnly 'org.junit.vintage:junit-vintage-engine'
}
"""
# A realistic set of test classes next to OrdersTest: every one runs and leaves a testcase in the JUnit XML - also the
# disabled, the conditional and the assuming one (skipped), the one inherited from an abstract contract or a test
# interface, the @Nested and the static nested one, JUnit 4 through the vintage engine.
CENSUS_TESTS = {
    "SlowOrdersTest": '@Tag("slow")\nclass SlowOrdersTest {\n    @Test\n    void slow() {\n        assertEquals(0, new Orders().total(1, 1));\n    }\n}\n',
    "NestedOrdersTest": "class NestedOrdersTest {\n    @Nested\n    class WhenEmpty {\n        @Test\n        void zero() {\n"
                        "            assertEquals(0, new Orders().total(0, 0));\n        }\n    }\n}\n",
    "AbstractOrdersContract": "abstract class AbstractOrdersContract {\n    @Test\n    void inherited() {\n"
                              "        assertEquals(1, new Orders().total(2, 1));\n    }\n}\n",
    "InheritedOrdersTest": "class InheritedOrdersTest extends AbstractOrdersContract {\n}\n",
    "OrdersContract": "interface OrdersContract {\n    @Test\n    default void fromTheInterface() {\n"
                      "        assertEquals(2, new Orders().total(3, 1));\n    }\n}\n",
    "ContractOrdersTest": "class ContractOrdersTest implements OrdersContract {\n}\n",
    "DisabledOrdersTest": '@Disabled("waits for the new tariff")\nclass DisabledOrdersTest {\n    @Test\n    void later() {\n    }\n}\n',
    "WindowsOrdersTest": "@EnabledOnOs(OS.WINDOWS)\nclass WindowsOrdersTest {\n    @Test\n    void onWindows() {\n    }\n}\n",
    "AssumingOrdersTest": "class AssumingOrdersTest {\n    @BeforeAll\n    static void stand() {\n"
                          '        Assumptions.assumeTrue(false, "no stand here");\n    }\n\n    @Test\n    void withTheStand() {\n    }\n}\n',
    "ParameterizedOrdersTest": "class ParameterizedOrdersTest {\n    @ParameterizedTest\n    @ValueSource(ints = {1, 2})\n"
                               "    void keepsTheSum(int sum) {\n        assertEquals(sum, new Orders().total(sum, 0));\n    }\n}\n",
    "OrdersFactoryTest": "class OrdersFactoryTest {\n    @TestFactory\n    Stream<DynamicTest> totals() {\n"
                         '        return Stream.of(DynamicTest.dynamicTest("one", () -> assertEquals(1, new Orders().total(1, 0))));\n'
                         "    }\n}\n",
    "RoundingHolder": "class RoundingHolder {\n    static class Rounding {\n        @Test\n        void rounds() {\n"
                      "            assertEquals(3, new Orders().total(3, 0));\n        }\n    }\n}\n",
    "TestData": "final class TestData {\n    static final int SUM = 100;\n\n    private TestData() {\n    }\n}\n",
}
CENSUS_HEAD = ("package com.example.service.domain;\n\nimport static org.junit.jupiter.api.Assertions.assertEquals;\n\n"
               "import java.util.stream.Stream;\nimport org.junit.jupiter.api.*;\nimport org.junit.jupiter.api.condition.*;\n"
               "import org.junit.jupiter.params.ParameterizedTest;\nimport org.junit.jupiter.params.provider.ValueSource;\n\n")
LEGACY_TEST = ("package com.example.service.domain;\n\nimport static org.junit.Assert.assertEquals;\n\nimport org.junit.Test;\n\n"
               "public class LegacyOrdersTest {\n    @Test\n    public void legacy() {\n        assertEquals(5, new Orders().total(6, 1));\n"
               "    }\n}\n")
CENSUS_COUNTED = 12     # OrdersTest and the classes above that JUnit runs: not the contracts, the outer classes, TestData
DOMAIN_PACKAGE = "com.example.service.domain."
NO_SLOW_TESTS = """package com.example.service.domain;

import org.junit.platform.engine.FilterResult;
import org.junit.platform.engine.TestDescriptor;
import org.junit.platform.launcher.PostDiscoveryFilter;

public class NoSlowTests implements PostDiscoveryFilter {
    @Override
    public FilterResult apply(TestDescriptor descriptor) {
        boolean slow = descriptor.getTags().stream().anyMatch(tag -> tag.getName().equals("slow"));
        return FilterResult.includedIf(!slow, () -> "fast", () -> "slow");
    }
}
"""


class Census(GradleCase):
    """testCensus: every test class test and archTest compiled must be in their JUnit XML results (finding T6) - judged
    by what ran, whatever kept a class out: the build-script forms B2 does not read, a filter of the test platform."""

    def census_project(self, extra=""):
        self.project(build_extra=CENSUS_DEPENDENCIES + extra, example=False)
        for name, body in CENSUS_TESTS.items():
            self.file(DOMAIN_TEST + name + ".java", CENSUS_HEAD + body)
        self.file(DOMAIN_TEST + "LegacyOrdersTest.java", LEGACY_TEST)

    def build(self, extra):
        self.file("build.gradle", BUILD.format(junit=JUNIT, extra=CENSUS_DEPENDENCIES + extra))

    @staticmethod
    def not_run(result, task="test"):
        """{class name: path} of the T6 findings for the task."""
        found = {}
        for m in re.finditer(rf"(?m)^INTEGRITY T6 (\S+)  compiled but not run by {task}  \|  (\S+)$", result.out):
            found[m.group(2).replace(DOMAIN_PACKAGE, "")] = m.group(1)
        return found

    def assert_census_ok(self, result, ran=CENSUS_COUNTED):
        self.assert_build(result, True)
        self.assertIn(f"Test census: OK - test classes run (ran/compiled): test {ran}/{ran}, archTest 1/1", result.out)

    def test_every_test_class_ran_and_each_filter_names_the_class_it_kept_out(self):
        self.census_project()
        self.assert_census_ok(self.gradle("testCensus"))
        slow = {"SlowOrdersTest": DOMAIN_TEST + "SlowOrdersTest.java"}
        forms = {   # the first five are forms B2 does not read (README section 9); the tag filter is one it does
            "a variable": "def t = tasks.test\nt.exclude '**/SlowOrdersTest*'",
            "a key of the task container": "tasks['test'].exclude '**/SlowOrdersTest*'",
            "matching { }": "tasks.matching { it.name == 'test' }.all { exclude '**/SlowOrdersTest*' }",
            "a closure parameter in doFirst": "test { doFirst { t -> t.exclude '**/SlowOrdersTest*' } }",
            "a case branch": "test { switch (1) { case 1: exclude '**/SlowOrdersTest*' } }",
            "excludeTags": "test { useJUnitPlatform { excludeTags 'slow' } }",
        }
        for form, extra in forms.items():
            with self.subTest(form):
                self.build(extra)
                r = self.gradle("testCensus")
                self.assert_build(r, False)
                self.assertEqual(self.not_run(r), slow)
                self.assertIn(f"Test census: FAILED - 1 test class(es) compiled but not run; test classes run (ran/compiled): "
                              f"test {CENSUS_COUNTED - 1}/{CENSUS_COUNTED}, archTest 1/1.", r.out)
        with self.subTest("a PostDiscoveryFilter of the test platform, outside the build script"):
            self.build("dependencies { testImplementation 'org.junit.platform:junit-platform-launcher' }")
            self.file(DOMAIN_TEST + "NoSlowTests.java", NO_SLOW_TESTS)
            self.file("src/test/resources/META-INF/services/org.junit.platform.launcher.PostDiscoveryFilter",
                      "com.example.service.domain.NoSlowTests\n")
            r = self.gradle("testCensus")
            self.assert_build(r, False)
            self.assertEqual(self.not_run(r), slow)
            os.remove(os.path.join(self.lab, "src/test/resources/META-INF/services/org.junit.platform.launcher.PostDiscoveryFilter"))
        with self.subTest("junit.jupiter.conditions.deactivate runs the disabled class: nothing is missing"):
            self.file("src/test/resources/junit-platform.properties", "junit.jupiter.conditions.deactivate=org.junit.*DisabledCondition\n")
            self.assert_census_ok(self.gradle("testCensus"))
            self.assertNotIn("<skipped", kit.read(os.path.join(
                self.lab, "build/test-results/test/TEST-com.example.service.domain.DisabledOrdersTest.xml")))

    def test_a_test_class_kept_from_the_task_or_from_compilation(self):
        # review of 4.4: the census judged task.testClassesDirs, which the build controls - a narrowed one ran fewer
        # test classes and the census judged only what was left ("test 0/0"); a test source the compile task left out
        # had no class to miss; one results directory for test and archTest lost test's results to archTest's run
        self.census_project()
        self.assert_census_ok(self.gradle("testCensus"))
        narrowed = "not the classes its source set compiles"
        for case, extra, after_the_kit, task in (
                ("a filtered file tree", "test { testClassesDirs = testClassesDirs.asFileTree.matching { "
                                         "getExcludes().add('**/SlowOrdersTest*') } }", "", ":test"),
                ("an empty collection", "test { testClassesDirs = files() }", "", ":test"),
                ("archTest emptied after the kit", "", "archTest { testClassesDirs = files() }\n", ":archTest"),
                ("the source set's classes directories emptied", "sourceSets.test.output.classesDirs.setFrom(files())",
                 "", ":test"),
                ("archTest's source set emptied after the kit", "",
                 "sourceSets.archTest.output.classesDirs.setFrom(files())\n", ":archTest")):
            with self.subTest(case):
                self.build(extra)
                kit.write(os.path.join(self.lab, "build.gradle"), kit.read(os.path.join(self.lab, "build.gradle")) + after_the_kit)
                r = self.gradle("testCensus")
                self.assert_build(r, False)
                self.assertIn(f"gauntlet: {task} runs the test classes in ", r.out)
                self.assertIn(narrowed, r.out)
        for case, extra in (("a source-set exclude", "sourceSets { test { java { exclude '**/SlowOrdersTest.java' } } }"),
                            ("a compile-task exclude", "compileTestJava { exclude '**/SlowOrdersTest.java' }")):
            with self.subTest(case):
                self.build(extra)
                r = self.gradle("testCensus")
                self.assert_build(r, False)
                self.assertIn(f"INTEGRITY T6 {DOMAIN_TEST}SlowOrdersTest.java  not compiled for test  |  the build leaves "
                              "this test source out of the compilation", r.out)
                self.assertIn("Test census: FAILED - 0 test class(es) compiled but not run, 1 test source(s) not compiled; "
                              f"test classes run (ran/compiled): test {CENSUS_COUNTED - 1}/{CENSUS_COUNTED - 1}", r.out)
        with self.subTest("the source set's directories moved away from src/test/java"):
            self.build("sourceSets { test { java { srcDirs = [] } } }")
            r = self.gradle("testCensus")
            self.assert_build(r, False)
            self.assertIn(f"INTEGRITY T6 {DOMAIN_TEST}SlowOrdersTest.java  not compiled for test", r.out)
            self.build("compileTestJava { exclude '**/SlowOrdersTest.java' }")
        with self.subTest("an allowlist line accepts a source left out"):
            allowlist = os.path.join(self.lab, "gauntlet/config/integrity-allowlist.txt")
            shipped = kit.read(allowlist)
            kit.write(allowlist, shipped + f"{DOMAIN_TEST}SlowOrdersTest.java T6 # moved to a separate suite\n")
            r = self.gradle("testCensus")
            self.assertIn("(1 allowlisted)", r.out)
            self.assert_build(r, True)
            kit.write(allowlist, shipped)
        with self.subTest("one JUnit XML directory for test and archTest"):
            self.build("tasks.withType(Test).configureEach { reports.junitXml.outputLocation = "
                       "layout.buildDirectory.dir('junit-xml') }")
            r = self.gradle("testCensus")
            self.assert_build(r, False)
            self.assertIn("gauntlet: test and archTest write their JUnit XML into one directory", r.out)

    def test_the_results_of_an_up_to_date_or_cached_test_run_are_judged(self):
        # an UP-TO-DATE or FROM-CACHE test task leaves the results of the very same inputs - the filter is one of them
        self.census_project("test { exclude '**/SlowOrdersTest*' }")
        cache = os.path.join(self.tmp, "build-cache")
        self.file("settings.gradle", f"rootProject.name = 'lab'\nbuildCache {{ local {{ directory = '{cache}' }} }}\n")
        for outcome, before in (("", ()), (" UP-TO-DATE", ()), (" FROM-CACHE", ("clean",))):
            with self.subTest(outcome or "executed"):
                r = self.gradle(*before, "testCensus", "--build-cache")
                self.assertRegex(r.out, rf"(?m)^> Task :test{outcome}$")
                self.assertEqual(set(self.not_run(r)), {"SlowOrdersTest"})
        self.build("")
        for outcome, before in (("", ()), (" FROM-CACHE", ("clean",))):
            with self.subTest("no filter: " + (outcome or "executed")):
                r = self.gradle(*before, "testCensus", "--build-cache")
                self.assertRegex(r.out, rf"(?m)^> Task :test{outcome}$")
                self.assert_census_ok(r)

    def test_only_a_test_run_of_this_build_is_judged(self):
        # the results directory keeps what an earlier run wrote: a test task that ran nothing in this build must not be
        # judged by it - nor must a later census take a person's run filtered on the command line for the gate's
        self.census_project()
        self.assert_census_ok(self.gradle("testCensus"))
        with self.subTest("SKIPPED"):
            self.build("test { onlyIf { false } }")
            r = self.gradle("testCensus")
            self.assertRegex(r.out, r"(?m)^> Task :test SKIPPED$")
            self.assertIn(f"Test census: test was SKIPPED in this build, so none of its {CENSUS_COUNTED} test class(es) ran", r.out)
            self.assertEqual(len(self.not_run(r)), CENSUS_COUNTED)
        left_out = "gauntlet: :test is not part of this build (left out with -x, or by the build itself)"
        for case, extra, args in (("-x test", "", ("-x", "test")),
                                  ("excludedTaskNames", "gradle.startParameter.excludedTaskNames << 'test'", ())):
            with self.subTest(case):
                self.build(extra)
                r = self.gradle("testCensus", *args)
                self.assert_build(r, False)
                self.assertIn(left_out, r.out)
        with self.subTest("no JUnit XML"):
            self.build("test { reports.junitXml.required = false }")
            r = self.gradle("testCensus")
            self.assert_build(r, False)
            self.assertIn("switches them off (reports.junitXml.required = false)", r.out)
        self.build("")
        with self.subTest("--tests by a person, outside the gauntlet"):
            r = self.gradle("test", "--tests", "*.OrdersTest")
            self.assert_build(r, True)
            self.assertNotIn("Test census", r.out)
            r = self.gradle("testCensus")
            self.assertRegex(r.out, r"(?m)^> Task :test$")         # the filter is an input: test runs whole again
            self.assert_census_ok(r)
        with self.subTest("--tests in the census's own build is judged"):
            r = self.gradle("test", "--tests", "*.OrdersTest", "testCensus")
            self.assert_build(r, False)
            self.assertEqual(len(self.not_run(r)), CENSUS_COUNTED - 1)
            self.assertNotIn("OrdersTest", self.not_run(r))

    def test_testng_and_junit_4_runners(self):
        self.project(example=False)
        os.remove(os.path.join(self.lab, DOMAIN_TEST + "OrdersTest.java"))
        head = "package com.example.service.domain;\n\nimport org.testng.annotations.Test;\n\n"
        testng = {"OrdersNgTest": "public class OrdersNgTest {\n    @Test\n    public void works() {\n    }\n}\n",
                  "SlowOrdersNgTest": 'public class SlowOrdersNgTest {\n    @Test(groups = "slow")\n    public void slow() {\n    }\n}\n',
                  "ClassLevelNgTest": "@Test\npublic class ClassLevelNgTest {\n    public void one() {\n    }\n}\n",
                  "IgnoredNgTest": "@org.testng.annotations.Ignore\npublic class IgnoredNgTest {\n    @Test\n"
                                   "    public void ignored() {\n    }\n}\n"}
        for name, body in testng.items():
            self.file(DOMAIN_TEST + name + ".java", head + body)
        runner = "dependencies { testImplementation 'org.testng:testng:7.10.2' }\n"
        build = lambda framework: BUILD.format(junit=JUNIT, extra=runner).replace("test { useJUnitPlatform() }", framework)
        with self.subTest("TestNG"):
            self.file("build.gradle", build("test { useTestNG() }"))
            self.assert_census_ok(self.gradle("testCensus"), ran=3)        # @Ignore: nothing reported, T3 judges it
            self.file("build.gradle", build("test { useTestNG { excludeGroups 'slow' } }"))
            self.assertEqual(set(self.not_run(self.gradle("testCensus"))), {"SlowOrdersNgTest"})
        for name in testng:
            os.remove(os.path.join(self.lab, DOMAIN_TEST + name + ".java"))
        head = "package com.example.service.domain;\n\nimport org.junit.Test;\n\n"
        self.file(DOMAIN_TEST + "Slow.java", "package com.example.service.domain;\n\npublic interface Slow {\n}\n")
        self.file(DOMAIN_TEST + "OrdersJ4Test.java", head + "public class OrdersJ4Test {\n    @Test\n    public void works() {\n    }\n}\n")
        self.file(DOMAIN_TEST + "SlowOrdersJ4Test.java", head + "@org.junit.experimental.categories.Category(Slow.class)\n"
                  "public class SlowOrdersJ4Test {\n    @Test\n    public void slow() {\n    }\n}\n")
        runner = "dependencies { testImplementation 'junit:junit:4.13.2' }\n"
        with self.subTest("JUnit 4"):
            self.file("build.gradle", build("test { useJUnit() }"))
            self.assert_census_ok(self.gradle("testCensus"), ran=2)
            self.file("build.gradle", build("test { useJUnit { excludeCategories 'com.example.service.domain.Slow' } }"))
            self.assertEqual(set(self.not_run(self.gradle("testCensus"))), {"SlowOrdersJ4Test"})

    def test_kotlin_test_classes_in_a_module_build(self):
        java = os.path.join(os.environ["JAVA_HOME"], "bin", "java") if os.environ.get("JAVA_HOME") else shutil.which("java")
        if (java_major(java) or 0) > 24:
            self.skipTest("the Kotlin Gradle plugin 2.0.21 does not run on a JDK newer than 24")
        shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(self.lab, "gauntlet"))
        for key, value in (("module", "core"), ("acceptance.spring", "false"), ("cucumber.version", CUCUMBER)):
            kit.set_property(self.lab, key, value)
        arch = os.path.join(self.lab, "gauntlet/config/architecture.properties")
        kit.write(arch, re.sub(r"(?m)^(allowed\.(application|api|infrastructure)|forbidden\.application)=.*\n", "",
                               kit.read(arch)))
        self.file("core/settings.gradle", "rootProject.name = 'core'\n")
        self.file("core/build.gradle", BUILD.format(junit=JUNIT, extra="").replace("'gauntlet/", "'../gauntlet/").replace(
            "    id 'info.solidsoft.pitest' version '1.19.0'", "    id 'org.jetbrains.kotlin.jvm' version '2.0.21'"))
        self.file("core/" + DOMAIN + "Orders.java", ORDERS)
        self.file("core/src/test/kotlin/com/example/service/domain/OrdersKtTest.kt", """package com.example.service.domain

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Nested
import org.junit.jupiter.api.Test

class OrdersKtTest {
    @Test
    fun subtractsTheDiscount() {
        assertEquals(9900, Orders().total(10000, 100))
    }

    @Nested
    inner class WhenEmpty {
        @Test
        fun zero() {
            assertEquals(0, Orders().total(0, 0))
        }
    }

    class Rounding {
        @Test
        fun rounds() {
            assertEquals(3, Orders().total(3, 0))
        }
    }

    companion object {
        const val SUM = 100
    }
}
""")
        # Kotlin does not tie a file to its package directory
        self.file("core/src/test/kotlin/misplaced/ElsewhereKtTest.kt", "package com.example.service.domain\n\n"
                  "import org.junit.jupiter.api.Test\n\nclass ElsewhereKtTest {\n    @Test\n    fun runs() {\n"
                  "        val square = { x: Int -> x * x }\n        check(square(2) == 4)\n    }\n}\n")
        self.lab = os.path.join(self.lab, "core")
        self.assert_census_ok(self.gradle("testCensus"), ran=4)
        self.file("build.gradle", kit.read(os.path.join(self.lab, "build.gradle")).replace(
            "apply from:", "tasks['test'].exclude '**/ElsewhereKtTest*'\napply from:"))
        r = self.gradle("testCensus")
        self.assert_build(r, False)
        self.assertEqual(self.not_run(r), {"ElsewhereKtTest": "src/test/kotlin/misplaced/ElsewhereKtTest.kt"})
        kit.write(os.path.join(self.lab, "../gauntlet/config/core/integrity-allowlist.txt"),
                  "src/test/kotlin/**/ElsewhereKtTest.kt T6   # the module's own allowlist\n")
        r = self.gradle("testCensus")
        self.assert_build(r, True)
        self.assertIn("Test census: OK - test classes run (ran/compiled): test 3/4, archTest 1/1 (1 allowlisted)", r.out)

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
    over from the hardener's last run (pitest UP-TO-DATE). CI starts without the default history (review of efa4c50);
    a history the project configures itself did the same, from the checkout as well (review of 7061885)."""

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

    def test_a_history_the_project_configures_stops_the_hardener(self):
        # the plugin hands PIT the project's own history files with enableDefaultIncrementalAnalysis off as well, and
        # the project can turn the flag on again: "Incremental analysis reduced number of mutations by 3", the weakened
        # test kept its kills, mutationGate and the hook passed - also with the files in the checkout and build/ wiped,
        # as in a fresh clone (review of 7061885). Each form gets a project, a session and a hook state of its own.
        history = ("    historyInputLocation = layout.buildDirectory.file('application-pit.history')\n"
                   "    historyOutputLocation = layout.buildDirectory.file('application-pit.history')\n")
        in_checkout = history.replace("layout.buildDirectory", "layout.projectDirectory")
        apply = "apply from: 'gauntlet/gauntlet.gradle'"
        forms = {   # what build.gradle adds before the kit / after it, build/ wiped before the second run
            "pitest {} before the kit": ("pitest {\n" + history + "}\n", "", False),
            "pitest {} after the kit": ("", "pitest {\n" + history + "}\n", False),
            "files in the checkout, build/ wiped": ("pitest {\n" + in_checkout + "}\n", "", True),
            "on the task": ("", "tasks.named('pitest') {\n" + history + "}\n", False),
            "the flag turned on after the kit": ("", "pitest {\n    enableDefaultIncrementalAnalysis = true\n}\n",
                                                 False),
        }
        refused = "gauntlet: PIT incremental analysis is configured for this build"
        base = self.tmp
        for n, (form, (before, after, wipe)) in enumerate(forms.items()):
            with self.subTest(form):
                self.tmp = os.path.join(base, str(n))
                self.lab = os.path.join(self.tmp, "lab")
                self.start_session()
                build = os.path.join(self.lab, "build.gradle")
                kit.write(build, kit.read(build).replace(apply, before + apply, 1) + after)
                self.prices(boundary=0)
                self.commit("prices")
                r = self.gradle("mutationGate", "--continue")
                self.assert_build(r, False)
                self.assertIn(refused, r.out)
                self.prices(boundary=-1)
                if wipe:
                    shutil.rmtree(os.path.join(self.lab, "build"))
                r = self.gradle("mutationGate", "--continue")
                self.assert_build(r, False)
                self.assertIn(refused, r.out)
                r = self.hardener_stops()
                self.assertEqual(r.code, 2, r)
                self.assertIn(refused, r.out)



class GateRan(GradleCase):
    """A green exit is judged by what Gradle ran (issue #4): one line of a build script took the gates out of the task
    graph, Gradle printed BUILD SUCCESSFUL, and the Stop hook let the agent stop."""

    hook = HardenerStop.hook

    def start_session(self):
        self.project(example=False)
        self.file(FEATURES + ".gitkeep", "")                    # the features directory as the install leaves it
        self.commit("features")
        r = self.hook({"session_id": "s1", "hook_event_name": "SessionStart"},
                      'python3 "$CLAUDE_PROJECT_DIR/gauntlet/hooks/stop_gate.py" --record-start')
        self.assertEqual(r.code, 0, r)

    def stops(self):
        """The Stop hook, run as Claude Code runs it: the command of .claude/settings.json."""
        settings = json.loads(kit.read(os.path.join(kit.kit(), ".claude", "settings.json")))
        command, = [h["command"] for entry in settings["hooks"]["Stop"] for h in entry["hooks"]]
        return self.hook({"session_id": "s1", "hook_event_name": "Stop", "stop_hook_active": False}, command)

    def test_a_build_script_that_leaves_gate_tasks_out_of_the_build(self):
        self.start_session()
        build = kit.read(os.path.join(self.lab, "build.gradle"))
        for left_out, named in ((["gauntletFast", "gauntlet"], "gauntletFast, gauntletScope, integrityCheck"),
                                (["integrityCheck"], "integrityCheck - no")):
            with self.subTest(left_out):
                names = ", ".join(f"'{n}'" for n in left_out)
                self.file("build.gradle", build + f"gradle.startParameter.excludedTaskNames.addAll([{names}])\n")
                r = self.gradle("gauntletFast", "--continue")
                self.assert_build(r, True)                                      # all the exit code knows
                self.assertNotIn("> Task :integrityCheck", r.out)
                r = self.stops()
                self.assertEqual(r.code, 2, r)
                self.assertIn(f"gauntlet: Gradle finished gauntletFast without running {named}", r.out)

    def test_a_build_script_that_switches_a_gate_off_or_ignores_its_verdict(self):
        # review of 4.4: a SKIPPED gate counted as run - and a skipped integrityCheck cannot name the line that skipped
        # it; ignoreExitValue on every Exec task let each gate pass on its own findings
        self.start_session()
        skipped = DOMAIN_TEST + "SkippedTest.java"
        build = kit.read(os.path.join(self.lab, "build.gradle"))
        for what, before, after, finding, named in (
                ("integrityCheck disabled after the kit", "", "tasks.named('integrityCheck') { enabled = false }\n", True,
                 "without running integrityCheck - no"),
                ("integrityCheck skipped by an onlyIf of the project's", "",
                 "tasks.named('integrityCheck') { onlyIf { false } }\n", True, "without running integrityCheck - no"),
                ("crapGate switched off in a form B1 does not read",
                 "tasks.configureEach { if (name == 'crapGate') { enabled false } }\n", "", False,
                 "without running crapGate - no"),
                ("every Exec gate ignores its exit value", "tasks.withType(Exec).configureEach { ignoreExitValue = true }\n",
                 "", True, "ended with exit value 1, and the build ignores exit values")):
            with self.subTest(what):
                if finding:     # a test the agent switched off: finding T1, which only a running integrityCheck reports
                    self.file(skipped, "package com.example.service.domain;\n\nimport org.junit.jupiter.api.Disabled;\n"
                              "import org.junit.jupiter.api.Test;\n\nclass SkippedTest {\n    @Disabled(\"later\")\n"
                              "    @Test\n    void later() {\n    }\n}\n")
                elif os.path.exists(os.path.join(self.lab, skipped)):
                    os.remove(os.path.join(self.lab, skipped))
                self.file("build.gradle", build.replace("apply from: 'gauntlet/gauntlet.gradle'\n",
                                                        before + "apply from: 'gauntlet/gauntlet.gradle'\n" + after))
                r = self.stops()
                self.assertEqual(r.code, 2, r)
                self.assertIn(named, r.out)

    def test_the_whole_fast_gate_is_green_for_the_stop_hook(self):
        self.start_session()
        self.file("src/main/resources/service.properties", "greeting=hello\n")     # a change under src/: the hook runs
        r = self.stops()
        self.assertEqual(r.code, 0, r)


if __name__ == "__main__":
    unittest.main()
