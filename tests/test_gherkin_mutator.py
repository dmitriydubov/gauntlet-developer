"""GherkinMutator.java: generate (mutants + controls), verdict on JUnit XML, no-skipped.

Every fixture is built in a temporary directory. The JUnit XML is synthetic but copies the shape Gradle 8.14
writes for the Cucumber JUnit Platform engine with cucumber.junit-platform.naming-strategy=long (taken from
real runs on Cucumber 7.23.0 and 8.0.1): a failed scenario is a <failure type="..."> whose text is the stack
trace, and an exception thrown by a step definition carries Cucumber's own frame "at ✽.<step text>(feature:line)".
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from xml.sax.saxutils import escape, quoteattr

import kit

KIT = kit.kit()
CLASSES = kit.classes()
TOOL = os.path.join(KIT, "gauntlet", "tools", "GherkinMutator.java")

HEADER = "id\tfeature\tline\tscenario\tkey\toriginal\tmutated"                    # a manifest as older generators wrote it
GENERATED_HEADER = HEADER + "\tuses"     # + the line of the first step that uses the mutated column
FEATURE = "features/doubling.feature"
SCENARIO = "The price is doubled"
ENGINE = "io.cucumber.junit.platform.engine.CucumberTestEngine"
STEP_FRAME = "✽.the result table is:(file:///lab/build/gherkin-mutation/mutants/m1.feature:5)"
GLUE_FRAME = "app//com.example.service.acceptance.DoublingSteps.resultTable(DoublingSteps.java:18)"
HOOK_FRAME = "com.example.service.acceptance.HarnessHooks.connect(HarnessHooks.java:12)"
ASSERTION = "org.opentest4j.AssertionFailedError"
TABLE_DIFF = "io.cucumber.datatable.TableDiffException"
UNDEFINED = "io.cucumber.junit.platform.engine.UndefinedStepException"


def tool(*args, cwd):
    """Runs GherkinMutator; returns (exit code, stdout). stderr only carries JVM notices and usage errors."""
    cmd = ["java", "-cp", CLASSES, "GherkinMutator"] if CLASSES else ["java", TOOL]
    r = subprocess.run(cmd + [str(a) for a in args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       encoding="utf-8", env=kit.java_env())
    return r.returncode, r.stdout


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n")


# ----------------------------------------------------------------------------- JUnit XML in Gradle's shape

def mutant_name(n, scenario=SCENARIO, change="price: 5 -> 9"):
    return f"MUTANT m{n} | Doubling - MUTANT m{n} | {scenario} | {change} - Examples - Example #1.1"


def control_name(n, scenario=SCENARIO):
    cid = n if isinstance(n, str) else f"c{n}"          # c1 runs before the mutants, z1 after them
    return f"CONTROL {cid} | Doubling - CONTROL {cid} | {scenario} - Examples - Example #1.1"


def thrown(exc_type, message="boom", frames=(GLUE_FRAME, STEP_FRAME), tag="failure"):
    text = f"{exc_type}: {message}\n" + "".join(f"\tat {frame}\n" for frame in frames)
    return f"    <{tag} message={quoteattr(exc_type + ': ' + message)} type={quoteattr(exc_type)}>{escape(text)}</{tag}>\n"


def in_step(exc_type=ASSERTION, message="expected: <10> but was: <18>", tag="failure"):
    """An exception thrown by a step definition: Cucumber appends the step frame."""
    return thrown(exc_type, message, (GLUE_FRAME, STEP_FRAME), tag)


def outside_step(exc_type, message="Database fixture unavailable", tag="failure"):
    """A @Before/@After hook or fixture failure: the user's frame only, no step frame (as Gradle writes it)."""
    return thrown(exc_type, message, (HOOK_FRAME,), tag)


SKIPPED = "    <skipped/>\n"
PASSED = ""


def write_results(directory, cases):
    """cases: [(testcase name, body)], body = '' for a passed scenario."""
    failures = sum(1 for _, body in cases if "<failure" in body or "<error" in body)
    skipped = sum(1 for _, body in cases if "<skipped" in body)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>\n',
           f'<testsuite name="Cucumber" tests="{len(cases)}" skipped="{skipped}" failures="{failures}" errors="0" '
           'timestamp="2026-11-22T00:00:00.000Z" hostname="vm" time="0.1">\n', "  <properties/>\n"]
    for name, body in cases:
        head = f'  <testcase name={quoteattr(name)} classname="{ENGINE}" time="0.004"'
        xml.append(head + "/>\n" if not body else head + ">\n" + body + "  </testcase>\n")
    xml += ["  <system-out><![CDATA[]]></system-out>\n", "  <system-err><![CDATA[]]></system-err>\n", "</testsuite>\n"]
    write(os.path.join(directory, f"TEST-{ENGINE}.xml"), "".join(xml))


def write_manifest(directory, mutants, controls):
    rows = [HEADER]
    rows += ["\t".join([f"m{n}", FEATURE, "11", SCENARIO, "price", "5", "9"]) for n in range(1, mutants + 1)]
    rows += ["\t".join([f"c{n}", FEATURE, "11", SCENARIO, "(control)", "", ""]) for n in range(1, controls + 1)]
    write(os.path.join(directory, "manifest.tsv"), "\n".join(rows) + "\n")


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gherkin-mutator-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.mutants = os.path.join(self.dir, "mutants")
        self.results = os.path.join(self.dir, "results")

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def verdict(self, mutants, controls, cases):
        write_manifest(self.mutants, mutants, controls)
        write_results(self.results, cases)
        return tool("verdict", "--mutants", "mutants", "--results", "results", cwd=self.dir)

    def generate(self, *extra):
        return tool("generate", "--features", "features", "--out", "mutants", *extra, cwd=self.dir)

    def manifest(self):
        return [line.split("\t") for line in read_lines(os.path.join(self.mutants, "manifest.tsv"))[1:] if line]

    def summary(self, out):
        lines = [line for line in out.splitlines() if line.startswith("Gherkin mutation: ") and "mutant(s) -" in line]
        self.assertEqual(1, len(lines), out)
        return lines[0]


# ----------------------------------------------------------------------------- verdict

class VerdictTest(Sandbox):

    def test_all_killed_and_controls_passed_is_ok(self):
        code, out = self.verdict(2, 1, [(control_name(1), PASSED), (mutant_name(1), in_step()), (mutant_name(2), in_step())])
        self.assertEqual("Gherkin mutation: 2 mutant(s) - 2 killed, 0 survived, 0 error(s); 1 control(s) - 1 passed",
                         self.summary(out))
        self.assertIn("Gherkin mutation: OK", out)
        self.assertEqual(0, code, out)

    def test_cucumbers_own_table_diff_in_a_step_is_a_kill(self):
        code, out = self.verdict(2, 1, [(control_name(1), PASSED),
                                        (mutant_name(1), in_step(TABLE_DIFF, "tables were different:")),
                                        (mutant_name(2), in_step())])
        self.assertEqual("Gherkin mutation: 2 mutant(s) - 2 killed (1 by a non-assertion exception thrown in a step),"
                         " 0 survived, 0 error(s); 1 control(s) - 1 passed", self.summary(out))
        self.assertNotIn("MUTANT ERROR", out)
        self.assertEqual(0, code, out)

    def test_any_exception_type_thrown_in_a_step_is_a_kill(self):
        for exc_type in ("org.mockito.exceptions.verification.WantedButNotInvoked",
                         "com.github.tomakehurst.wiremock.client.VerificationException",
                         "org.awaitility.core.ConditionTimeoutException",
                         "java.lang.IllegalArgumentException"):
            with self.subTest(exc_type):
                code, out = self.verdict(1, 1, [(control_name(1), PASSED), (mutant_name(1), in_step(exc_type))])
                self.assertEqual("Gherkin mutation: 1 mutant(s) - 1 killed (1 by a non-assertion exception thrown in a"
                                 " step), 0 survived, 0 error(s); 1 control(s) - 1 passed", self.summary(out))
                self.assertEqual(0, code, out)

    def test_assertion_types_are_not_in_the_non_assertion_note(self):
        for exc_type in ("java.lang.AssertionError", ASSERTION, "org.junit.ComparisonFailure",
                         "com.google.common.truth.ComparisonFailureWithFacts",
                         "com.google.common.truth.AssertionErrorWithFacts", "org.opentest4j.MultipleFailuresError"):
            with self.subTest(exc_type):
                code, out = self.verdict(1, 1, [(control_name(1), PASSED), (mutant_name(1), in_step(exc_type))])
                self.assertEqual("Gherkin mutation: 1 mutant(s) - 1 killed, 0 survived, 0 error(s); 1 control(s) - 1 passed",
                                 self.summary(out))
                self.assertEqual(0, code, out)

    def test_assertion_in_a_hook_is_an_error_not_a_kill(self):
        code, out = self.verdict(2, 1, [(control_name(1), PASSED),
                                        (mutant_name(1), outside_step("java.lang.AssertionError")),
                                        (mutant_name(2), in_step())])
        self.assertIn("1 killed, 0 survived, 1 error(s); 1 control(s) - 1 passed", self.summary(out))
        self.assertRegex(out, r"(?m)^MUTANT ERROR    m1 failed outside a step \(java\.lang\.AssertionError - hook, fixture"
                              r" or context\), not a kill  features/doubling\.feature:11 \"The price is doubled\" price: 5 -> 9$")
        self.assertNotIn("Gherkin mutation: OK", out)
        self.assertEqual(1, code, out)

    def test_io_exception_in_a_hook_is_an_error_even_when_its_message_says_undefined(self):
        code, out = self.verdict(1, 1, [(control_name(1), PASSED),
                                        (mutant_name(1), outside_step("java.io.IOException", "Database URL is undefined"))])
        self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("m1 failed outside a step (java.io.IOException - hook, fixture or context), not a kill", out)
        self.assertNotIn("no step definition matched", out)
        self.assertEqual(1, code, out)

    def test_undefined_step_is_a_kill_counted_separately(self):
        message = "The step 'a customer with status goli' is undefined.\nYou can implement this step using the snippet(s) below:"
        code, out = self.verdict(2, 1, [(control_name(1), PASSED),
                                        (mutant_name(1), thrown(UNDEFINED, message, (STEP_FRAME,))),
                                        (mutant_name(2), in_step())])
        self.assertEqual("Gherkin mutation: 2 mutant(s) - 2 killed (1 only because no step definition matched the new"
                         " value), 0 survived, 0 error(s); 1 control(s) - 1 passed", self.summary(out))
        self.assertEqual(0, code, out)

    def test_both_notes_can_appear_together(self):
        code, out = self.verdict(3, 1, [(control_name(1), PASSED),
                                        (mutant_name(1), thrown(UNDEFINED, "The step 'x' is undefined.", (STEP_FRAME,))),
                                        (mutant_name(2), in_step(TABLE_DIFF)),
                                        (mutant_name(3), in_step())])
        self.assertEqual("Gherkin mutation: 3 mutant(s) - 3 killed (1 only because no step definition matched the new"
                         " value) (1 by a non-assertion exception thrown in a step), 0 survived, 0 error(s);"
                         " 1 control(s) - 1 passed", self.summary(out))
        self.assertEqual(0, code, out)

    def test_skipped_mutant_is_an_error(self):
        code, out = self.verdict(2, 1, [(control_name(1), PASSED), (mutant_name(1), SKIPPED), (mutant_name(2), in_step())])
        self.assertIn("1 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("MUTANT ERROR    m1 skipped/aborted, not a kill", out)
        self.assertEqual(1, code, out)

    def test_missing_mutant_result_is_an_error(self):
        code, out = self.verdict(2, 1, [(control_name(1), PASSED), (mutant_name(2), in_step())])
        self.assertIn("1 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("MUTANT ERROR    m1 not executed", out)
        self.assertEqual(1, code, out)

    def test_survivor_fails_the_verdict(self):
        code, out = self.verdict(2, 1, [(control_name(1), PASSED), (mutant_name(1), PASSED), (mutant_name(2), in_step())])
        self.assertIn("1 killed, 1 survived, 0 error(s); 1 control(s) - 1 passed", self.summary(out))
        self.assertRegex(out, r"(?m)^MUTANT SURVIVED m1  features/doubling\.feature:11 \"The price is doubled\" price: 5 -> 9$")
        self.assertIn("A survivor means the scenario still passes", out)
        self.assertNotIn("Gherkin mutation: OK", out)
        self.assertEqual(1, code, out)

    def test_control_failed_in_a_step_fails_the_verdict_although_every_mutant_was_killed(self):
        code, out = self.verdict(2, 1, [(control_name(1), in_step(message="no base rate - scenario A must run first")),
                                        (mutant_name(1), in_step()), (mutant_name(2), in_step())])
        self.assertEqual("Gherkin mutation: 2 mutant(s) - 2 killed, 0 survived, 0 error(s); 1 control(s) - 0 passed",
                         self.summary(out))
        # the "MUTANT ERROR" prefix is what the Stop hook's INTERESTING pattern hands back to the agent
        self.assertRegex(out, r"(?m)^MUTANT ERROR    c1 control \(unmutated scenario\) failed in a step with "
                              r"org\.opentest4j\.AssertionFailedError  features/doubling\.feature:11 \"The price is doubled\"$")
        self.assertIn("Controls: a control is the original Examples row run in the mutant harness with nothing changed.", out)
        self.assertIn("so failing mutants prove nothing", out)
        self.assertNotIn("Gherkin mutation: OK", out)
        self.assertEqual(1, code, out)

    def test_control_failed_outside_a_step(self):
        code, out = self.verdict(1, 1, [(control_name(1), outside_step("java.io.IOException", "Database URL is undefined")),
                                        (mutant_name(1), outside_step("java.io.IOException", "Database URL is undefined"))])
        self.assertIn("0 killed, 0 survived, 1 error(s); 1 control(s) - 0 passed", self.summary(out))
        self.assertIn("MUTANT ERROR    c1 control (unmutated scenario) failed outside a step (java.io.IOException - hook,"
                      " fixture or context)  features/doubling.feature:11", out)
        self.assertEqual(1, code, out)

    def test_control_skipped_or_undefined(self):
        code, out = self.verdict(1, 2, [(control_name(1), SKIPPED),
                                        (control_name(2), thrown(UNDEFINED, "The step 'x' is undefined.", (STEP_FRAME,))),
                                        (mutant_name(1), in_step())])
        self.assertIn("; 2 control(s) - 0 passed", self.summary(out))
        self.assertIn("MUTANT ERROR    c1 control (unmutated scenario) was skipped/aborted  ", out)
        self.assertIn("MUTANT ERROR    c2 control (unmutated scenario) has a step without a matching step definition  ", out)
        self.assertEqual(1, code, out)

    def test_control_not_executed_fails_the_verdict(self):
        code, out = self.verdict(1, 2, [(control_name(1), PASSED), (mutant_name(1), in_step())])
        self.assertIn("1 killed, 0 survived, 0 error(s); 2 control(s) - 1 passed", self.summary(out))
        self.assertIn("MUTANT ERROR    c2 control (unmutated scenario) was not executed  features/doubling.feature:11", out)
        self.assertNotIn("Gherkin mutation: OK", out)
        self.assertEqual(1, code, out)

    def test_manifest_without_controls_from_an_older_generator_still_works(self):
        code, out = self.verdict(2, 0, [(mutant_name(1), in_step()), (mutant_name(2), in_step())])
        self.assertEqual("Gherkin mutation: 2 mutant(s) - 2 killed, 0 survived, 0 error(s)", self.summary(out))
        self.assertIn("Gherkin mutation: OK", out)
        self.assertEqual(0, code, out)
        code, out = self.verdict(2, 0, [(mutant_name(1), PASSED), (mutant_name(2), in_step())])
        self.assertEqual("Gherkin mutation: 2 mutant(s) - 1 killed, 1 survived, 0 error(s)", self.summary(out))
        self.assertEqual(1, code, out)

    def test_error_element_is_judged_by_its_stage_like_a_failure(self):
        code, out = self.verdict(3, 1, [(control_name(1), PASSED),
                                        (mutant_name(1), in_step("java.lang.IllegalStateException", tag="error")),
                                        (mutant_name(2), outside_step("java.lang.IllegalStateException", tag="error")),
                                        (mutant_name(3), thrown(UNDEFINED, "The step 'x' is undefined.", (STEP_FRAME,), "error"))])
        self.assertEqual("Gherkin mutation: 3 mutant(s) - 2 killed (1 only because no step definition matched the new"
                         " value) (1 by a non-assertion exception thrown in a step), 0 survived, 1 error(s);"
                         " 1 control(s) - 1 passed", self.summary(out))
        self.assertIn("MUTANT ERROR    m2 failed outside a step (java.lang.IllegalStateException - hook, fixture or"
                      " context), not a kill", out)
        self.assertEqual(1, code, out)

    def test_ids_come_from_the_title_prefix_not_from_the_scenario_text(self):
        # a scenario whose own name mentions another id must not be booked on that id
        code, out = self.verdict(1, 1, [
            (control_name(1, scenario="MUTANT m1 was once flaky"), PASSED),
            (mutant_name(1, scenario="CONTROL c1 looks odd"), in_step())])
        self.assertIn("1 killed, 0 survived, 0 error(s); 1 control(s) - 1 passed", self.summary(out))
        self.assertEqual(0, code, out)

    def test_without_manifest_or_without_mutants_there_is_nothing_to_judge(self):
        os.makedirs(self.mutants)
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", cwd=self.dir)
        self.assertIn("no manifest at", out)
        self.assertEqual(0, code, out)
        write(os.path.join(self.mutants, "manifest.tsv"), HEADER + "\n")
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", cwd=self.dir)
        self.assertIn("Gherkin mutation: no mutants (no Examples values in scope) - OK.", out)
        self.assertEqual(0, code, out)


class WhereItFailed(Sandbox):
    """A kill is a failure the changed value caused: thrown by a step definition, on the first step that uses the
    value or a later one, in a row that can be repeated in one run."""

    def manifest_with_uses(self, uses, controls=("c1",)):
        rows = [GENERATED_HEADER, "\t".join(["m1", FEATURE, "11", SCENARIO, "price", "5", "9", str(uses)])]
        rows += ["\t".join([c, FEATURE, "11", SCENARIO, "(control)", "", "", ""]) for c in controls]
        write(os.path.join(self.mutants, "manifest.tsv"), "\n".join(rows) + "\n")

    def run_verdict(self, *extra):
        return tool("verdict", "--mutants", "mutants", "--results", "results", *extra, cwd=self.dir)

    def test_a_step_that_fails_before_the_value_is_used_kills_nothing(self):
        # the shared-state harness: the row's first step ("a new account ACC-1") fails on every repetition
        self.manifest_with_uses(7)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step())])     # step frame: line 5
        code, out = self.run_verdict()
        self.assertEqual(1, code, out)
        self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("MUTANT ERROR    m1 failed on line 5, before the first step that uses <price> (line 7) - the changed"
                      " value did not cause it, not a kill", out)

    def test_a_step_that_fails_where_the_value_is_used_kills(self):
        for uses in (5, 4):
            with self.subTest(uses=uses):
                self.manifest_with_uses(uses)
                write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step())])
                code, out = self.run_verdict()
                self.assertEqual(0, code, out)
                self.assertIn("1 killed, 0 survived, 0 error(s)", self.summary(out))

    def test_a_control_after_the_mutants_that_fails_means_the_row_cannot_be_repeated(self):
        self.manifest_with_uses(5, controls=("c1", "z1"))
        write_results(self.results, [(control_name("c1"), PASSED), (mutant_name(1), in_step()),
                                     (control_name("z1"), in_step(message="account ACC-1 already exists"))])
        code, out = self.run_verdict()
        self.assertEqual(1, code, out)
        self.assertIn("1 killed, 0 survived, 0 error(s); 2 control(s) - 1 passed", self.summary(out))
        self.assertIn("MUTANT ERROR    z1 control (unmutated scenario, after the mutants) failed in a step with", out)
        self.assertIn("the row cannot be repeated in one run", out)

    def test_a_value_cucumber_rejected_before_any_step_definition_ran_kills_nothing(self):
        convert = ("io.cucumber.core.exception.CucumberException", "Could not convert arguments for step [the order is in "
                   "status {}] defined at 'com.example.OrderSteps.inStatus(Status)'.",
                   ("io.cucumber.core.runner.PickleStepDefinitionMatch.couldNotConvertArguments(PickleStepDefinitionMatch.java:111)",
                    "io.cucumber.core.runner.PickleStepDefinitionMatch.runStep(PickleStepDefinitionMatch.java:56)"))
        glue_object = ("io.cucumber.core.exception.CucumberException", "Failed to instantiate class com.example.Steps",
                       ("io.cucumber.core.backend.DefaultObjectFactory.cacheNewInstance(DefaultObjectFactory.java:53)",
                        "io.cucumber.core.runner.PickleStepDefinitionMatch.runStep(PickleStepDefinitionMatch.java:63)",
                        STEP_FRAME))
        ambiguous = ("io.cucumber.core.runner.AmbiguousStepDefinitionsException", "\"the price 9 is doubled\" matches more"
                     " than one step definition", ("io.cucumber.core.runner.CachingGlue.findStepDefinitionMatch(CachingGlue.java:388)",))
        for name, (exc, message, frames) in {"conversion": convert, "glue object": glue_object, "ambiguous": ambiguous}.items():
            with self.subTest(name):
                self.manifest_with_uses(5)
                write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), thrown(exc, message, frames))])
                code, out = self.run_verdict()
                self.assertEqual(1, code, out)
                self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
                self.assertIn("MUTANT ERROR    m1 the value never reached a step definition (" + exc, out)

    def test_a_transformer_that_rejects_the_value_kills_nothing(self):
        # Cucumber cuts a transformer's stack at the transformer and appends the step frame - like a step's
        write(self.path("glue/com/example/Types.java"), "package com.example;\n\nclass Types {\n"
              "    @ParameterType(\".*\")\n    public Status status(String value) {\n        return Status.valueOf(value);\n    }\n}\n")
        enum = ("java.lang.IllegalArgumentException", "No enum constant com.example.Status.STIPPED")
        transformer = thrown(*enum, frames=("java.base/java.lang.Enum.valueOf(Enum.java:293)",
                                            "app//com.example.Types.status(Types.java:6)", STEP_FRAME))
        step_body = thrown(*enum, frames=("java.base/java.lang.Enum.valueOf(Enum.java:293)", GLUE_FRAME, STEP_FRAME))
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), transformer)])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    m1 the value never reached a step definition (java.lang.IllegalArgumentException", out)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), step_body)])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(0, code, out)          # the same exception from the step's own code is a kill
        self.assertIn("1 killed (1 by a non-assertion exception thrown in a step), 0 survived", self.summary(out))


# ----------------------------------------------------------------------------- generate

DOUBLING = """Feature: Doubling

  Scenario Outline: The price is doubled
    When the price <price> is doubled
    Then the result table is:
      | value    |
      | <result> |

    Examples:
      | price | result |
      | 5     | 10     |
      | 7     | 14     |
"""

RICH = """@billing
Feature: Addresses
  Free text under the feature.

  Background:
    Given the shop is open

  Rule: Deliveries need an address
    Background:
      Given the courier is free

    @slow
    Scenario Outline: A parcel is addressed
      When a parcel goes to <address> with note <note>
      Then the label reads:
        \"\"\"
        To: <address>
        \"\"\"

      @eu
      Examples: Europe
        | address        | note  |
        | line1\\nline2   | a\\|b  |

      Examples: Elsewhere
        | address | note |
        | Lima    | none |
"""

RUSSIAN = """# language: ru
Функция: Расчёт скидки по заказу

  Структура сценария: Фиксированная скидка уменьшает сумму заказа
    Дано клиент со скидкой <скидка> руб.
    Тогда итог заказа составляет <итог> руб.

    Примеры:
      | скидка | итог |
      | 100    | 9900 |
"""


def cells(row_line):
    """Raw cells of a rendered table row (escapes kept as written)."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", row_line.strip())[1:-1]]


class GenerateTest(Sandbox):

    def test_two_controls_per_mutated_row(self):
        # cN runs before every mutant, zN after them: Cucumber runs the files in the order of their names
        write(self.path("features/doubling.feature"), DOUBLING)
        code, out = self.generate()
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: 4 mutant(s) + 4 control(s) from 1 feature file(s) in scope -> mutants", out)
        self.assertEqual(sorted(["c1.feature", "c2.feature", "m1.feature", "m2.feature", "m3.feature", "m4.feature",
                                 "z1.feature", "z2.feature", "manifest.tsv"]), sorted(os.listdir(self.mutants)))
        self.assertEqual(["c1.feature", "c2.feature"], sorted(f for f in os.listdir(self.mutants) if f < "m"))
        rows = self.manifest()
        self.assertEqual(["m1", "m2", "m3", "m4", "c1", "z1", "c2", "z2"], [r[0] for r in rows])
        self.assertEqual(["c1", FEATURE, "11", SCENARIO, "(control)", "", "", ""], rows[4])
        self.assertEqual(["z1", FEATURE, "11", SCENARIO, "(control)", "", "", ""], rows[5])
        self.assertEqual(["c2", FEATURE, "12", SCENARIO, "(control)", "", "", ""], rows[6])
        # the line of the first step that uses the column: <price> in a step's text, <result> in its data table
        self.assertEqual([("price", "4"), ("result", "5"), ("price", "4"), ("result", "5")], [(r[4], r[7]) for r in rows[:4]])
        self.assertEqual(GENERATED_HEADER, read_lines(os.path.join(self.mutants, "manifest.tsv"))[0])
        z2 = read_lines(os.path.join(self.mutants, "z2.feature"))
        c2 = read_lines(os.path.join(self.mutants, "c2.feature"))
        self.assertEqual("# Gherkin control z2 (runs after the mutants) of features/doubling.feature - generated, do not edit", z2[0])
        self.assertEqual([line.replace("c2", "z2") for line in c2[1:]], z2[1:])
        self.assertEqual(["# Gherkin control c2 of features/doubling.feature - generated, do not edit",
                          "Feature: CONTROL c2 | Doubling",
                          "  Scenario Outline: CONTROL c2 | The price is doubled",
                          "    When the price <price> is doubled",
                          "    Then the result table is:",
                          "      | value    |",
                          "      | <result> |",
                          "    Examples:",
                          "      | price | result |",
                          "      | 7 | 14 |",
                          ""], read_lines(os.path.join(self.mutants, "c2.feature")))

    def test_mutant_of_a_repeated_header_changes_its_own_column(self):
        # Cucumber feeds the FIRST column of a repeated header to the steps; the mutant of the second (dead)
        # column must change that second cell - changing the first would report a kill it did not earn
        write(self.path("features/twice.feature"),
              "Feature: Twice\n\n  Scenario Outline: Repeated header\n    When the value <n> is used\n\n"
              "    Examples:\n      | n | n  |\n      | 5 | 70 |\n")
        code, out = self.generate()
        self.assertEqual(0, code, out)
        mutants = [r for r in self.manifest() if r[4] != "(control)"]
        self.assertEqual([("n", "5"), ("n", "70")], [(r[4], r[5]) for r in mutants])
        first = read_lines(os.path.join(self.mutants, mutants[0][0] + ".feature"))[-2]
        second = read_lines(os.path.join(self.mutants, mutants[1][0] + ".feature"))[-2]
        self.assertRegex(first, r"^      \| (?!5 )\S+ \| 70 \|$")
        self.assertRegex(second, r"^      \| 5 \| (?!70 )\S+ \|$")

    def test_control_is_the_mutant_rendering_with_no_cell_changed(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        self.generate()
        rows = self.manifest()
        controls = {r[2]: r[0] for r in rows if r[4] == "(control)"}          # row line -> control id
        for mutant in [r for r in rows if r[4] != "(control)"]:
            with self.subTest(mutant[0]):
                m = read_lines(os.path.join(self.mutants, mutant[0] + ".feature"))
                c = read_lines(os.path.join(self.mutants, controls[mutant[2]] + ".feature"))
                self.assertEqual(len(c), len(m))
                differing = [i for i in range(len(c)) if c[i] != m[i]]
                self.assertEqual([0, 1, 2, len(c) - 2], differing)                 # comment, 2 titles, the Examples row
                changed = [i for i, (a, b) in enumerate(zip(cells(c[-2]), cells(m[-2]))) if a != b]
                self.assertEqual(1, len(changed))                                  # exactly the mutated cell
                self.assertEqual(mutant[6], cells(m[-2])[changed[0]])
                self.assertEqual(mutant[5], cells(c[-2])[changed[0]])

    def test_control_keeps_background_rule_tags_docstring_and_raw_cells(self):
        write(self.path("features/addresses.feature"), RICH)
        code, out = self.generate()
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: 4 mutant(s) + 4 control(s) from 1 feature file(s)", out)
        self.assertEqual(["# Gherkin control c1 of features/addresses.feature - generated, do not edit",
                          "@billing",
                          "Feature: CONTROL c1 | Addresses",
                          "  Background:",
                          "    Given the shop is open",
                          "  Rule: Deliveries need an address",
                          "    Background:",
                          "      Given the courier is free",
                          "    @slow",
                          "      @eu",
                          "  Scenario Outline: CONTROL c1 | A parcel is addressed",
                          "      When a parcel goes to <address> with note <note>",
                          "      Then the label reads:",
                          '        """',
                          "        To: <address>",
                          '        """',
                          "    Examples:",
                          "      | address | note |",
                          "      | line1\\nline2 | a\\|b |",        # escapes stay exactly as written in the feature
                          ""], read_lines(os.path.join(self.mutants, "c1.feature")))
        c2 = read_lines(os.path.join(self.mutants, "c2.feature"))
        self.assertNotIn("      @eu", c2)                             # the second Examples table has no tag
        self.assertEqual("      | Lima | none |", c2[-2])
        self.assertEqual(["23", "23", "27", "27"], [r[2] for r in self.manifest() if r[4] == "(control)"])
        # <address> and <note> are first used by the When step - line 12 of the generated feature, line 11 for the
        # second table, which has no tag line; the doc string with <address> belongs to the later Then step
        self.assertEqual(["12", "12", "11", "11"], [r[7] for r in self.manifest() if r[4] != "(control)"])

    def test_russian_keywords(self):
        write(self.path("features/discount.feature"), RUSSIAN)
        code, out = self.generate()
        self.assertEqual(0, code, out)
        self.assertIn("2 mutant(s) + 2 control(s)", out)
        self.assertEqual(["# language: ru",
                          "# Gherkin control c1 of features/discount.feature - generated, do not edit",
                          "Функция: CONTROL c1 | Расчёт скидки по заказу",
                          "  Структура сценария: CONTROL c1 | Фиксированная скидка уменьшает сумму заказа",
                          "    Дано клиент со скидкой <скидка> руб.",
                          "    Тогда итог заказа составляет <итог> руб.",
                          "    Примеры:",
                          "      | скидка | итог |",
                          "      | 100 | 9900 |",
                          ""], read_lines(os.path.join(self.mutants, "c1.feature")))
        m1 = read_lines(os.path.join(self.mutants, "m1.feature"))
        self.assertEqual("# Gherkin mutant m1 of features/discount.feature - generated, do not edit", m1[1])
        self.assertTrue(m1[2].startswith("Функция: MUTANT m1 | Расчёт скидки по заказу"), m1[2])
        self.assertRegex(m1[3], r"^  Структура сценария: MUTANT m1 \| Фиксированная скидка уменьшает сумму заказа \| скидка: 100 -> \d+$")

    def test_only_limits_mutants_and_controls_to_the_named_features(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        write(self.path("features/discount.feature"), RUSSIAN)
        code, out = self.generate("--only", "features/discount.feature")
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: 2 mutant(s) + 2 control(s) from 1 feature file(s) in scope", out)
        self.assertEqual({"features/discount.feature"}, {r[1] for r in self.manifest()})

    def test_generated_run_judged_end_to_end(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        self.generate()
        cases = [(control_name(r[0]), PASSED) if r[4] == "(control)"
                 else (mutant_name(int(r[0][1:]), change=f"{r[4]}: {r[5]} -> {r[6]}"), in_step(TABLE_DIFF)) for r in self.manifest()]
        write_results(self.results, cases)
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", cwd=self.dir)
        self.assertEqual("Gherkin mutation: 4 mutant(s) - 4 killed (4 by a non-assertion exception thrown in a step),"
                         " 0 survived, 0 error(s); 4 control(s) - 4 passed", self.summary(out))
        self.assertEqual(0, code, out)

    def test_emoji_cells_are_mutated_as_whole_characters(self):
        # a mutation that split a surrogate pair wrote no file and ended generate with exit 2
        rows = "".join(f"      | Hi {i} \U0001F600 | {i} |\n" for i in range(30))
        write(self.path("features/emoji.feature"), "Feature: Emoji\n\n  Scenario Outline: Reaction\n"
              "    When <text> is sent\n    Then <n> reactions are counted\n\n    Examples:\n      | text | n |\n" + rows)
        code, out = self.generate()
        self.assertEqual(0, code, out)
        for row in self.manifest():
            if row[4] != "(control)":
                read_lines(os.path.join(self.mutants, row[0] + ".feature"))       # valid UTF-8, or this raises

    # ---- behaviour that must not change

    def test_scenario_without_steps_gives_no_mutant_no_control_and_is_not_vacuous(self):
        write(self.path("features/reserved.feature"), """Feature: Reserved
  Background:
    Given the shop is open

  Scenario: Reserved for later
    Only a description, no steps of its own.

  Scenario Outline: Empty outline
    Examples:
      | price |
      | 5     |
""")
        code, out = self.generate()
        self.assertIn("Gherkin mutation: 0 mutant(s) + 0 control(s) from 1 feature file(s) in scope", out)
        self.assertNotIn("GHERKIN VACUOUS", out)
        self.assertEqual(0, code, out)
        self.assertEqual(["manifest.tsv"], os.listdir(self.mutants))

    def test_scenario_with_steps_but_no_examples_is_vacuous(self):
        write(self.path("features/plain.feature"), """Feature: Plain

  Scenario: No Examples value to mutate
    Given the shop is open
    Then the total is 10
""")
        code, out = self.generate()
        self.assertRegex(out, r'GHERKIN VACUOUS features/plain\.feature:3 scenario "No Examples value to mutate"')
        self.assertIn("Gherkin mutation: 0 mutant(s) + 0 control(s)", out)
        self.assertEqual(1, code, out)

    def test_vacuous_scenario_next_to_a_mutated_one_still_fails(self):
        write(self.path("features/mixed.feature"), DOUBLING + """
  Scenario: Plain neighbour
    Given the shop is open
""")
        code, out = self.generate()
        self.assertIn('GHERKIN VACUOUS features/mixed.feature:14 scenario "Plain neighbour"', out)
        self.assertIn("Gherkin mutation: 4 mutant(s) + 4 control(s)", out)
        self.assertEqual(1, code, out)

    def test_missing_features_directory_is_an_error(self):
        code, out = self.generate()
        self.assertIn("GHERKIN ERROR features directory features does not exist", out)
        self.assertEqual(1, code, out)

    def test_stale_output_is_wiped(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        write(os.path.join(self.mutants, "c9.feature"), "stale")
        write(os.path.join(self.mutants, "m9.feature"), "stale")
        self.generate()
        self.assertNotIn("c9.feature", os.listdir(self.mutants))
        self.assertNotIn("m9.feature", os.listdir(self.mutants))


# ----------------------------------------------------------------------------- no-skipped (unchanged behaviour)

class NoSkippedTest(Sandbox):

    def no_skipped(self):
        return tool("no-skipped", "--results", "results", "--features", "features", cwd=self.dir)

    def test_missing_features_directory_fails(self):
        code, out = self.no_skipped()
        self.assertIn("Acceptance: FAILED - features directory features does not exist", out)
        self.assertEqual(1, code, out)

    def test_directory_without_feature_files_passes(self):
        write(self.path("features/.gitkeep"), "")
        code, out = self.no_skipped()
        self.assertIn("Acceptance: no feature files in features", out)
        self.assertEqual(0, code, out)

    def test_skipped_scenario_fails(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        write_results(self.results, [("Example #1.1", PASSED), ("Example #1.2", SKIPPED)])
        code, out = self.no_skipped()
        self.assertIn(f"ACCEPTANCE SKIPPED {ENGINE} > Example #1.2", out)
        self.assertIn("Acceptance: FAILED - 1 scenario(s) skipped.", out)
        self.assertEqual(1, code, out)

    def test_feature_files_without_any_result_fail(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        code, out = self.no_skipped()
        self.assertIn("but no scenario ran", out)
        self.assertEqual(1, code, out)

    def test_all_scenarios_ran(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        write_results(self.results, [("Example #1.1", PASSED), ("Example #1.2", PASSED)])
        code, out = self.no_skipped()
        self.assertIn("Acceptance: 2 scenario(s), none skipped - OK", out)
        self.assertEqual(0, code, out)


if __name__ == "__main__":
    unittest.main()
