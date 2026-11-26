"""GherkinMutator.java: generate (mutants + controls), verdict on JUnit XML, no-skipped.

Every fixture is built in a temporary directory. The JUnit XML is synthetic but copies the shape Gradle 8.14
writes for the Cucumber JUnit Platform engine with cucumber.junit-platform.naming-strategy=long (taken from
real runs on Cucumber 7.23.0 and 8.0.1): a failed scenario is a <failure type="..."> whose text is the stack
trace, and an exception thrown by a step definition carries Cucumber's own frame "at ✽.<step text>(feature:line)".
A retried scenario (the test-retry plugin 1.6.2) is a <testcase> per attempt, or - with reports.junitXml.mergeReruns -
one <testcase> holding <flakyFailure> or <failure> + <rerunFailure>, with the trace in a <stackTrace> child.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
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

# Cucumber's annotations as the glue is compiled against them: same names, runtime retention - the class files
# name them exactly as with cucumber-java on the classpath
CUCUMBER_STUBS = {
    "io/cucumber/java/ParameterType.java": "package io.cucumber.java;\n\nimport java.lang.annotation.*;\n\n"
    "@Retention(RetentionPolicy.RUNTIME)\n@Target(ElementType.METHOD)\npublic @interface ParameterType {\n"
    "    String value();\n\n    String name() default \"\";\n}\n",
    "io/cucumber/java/en/Then.java": "package io.cucumber.java.en;\n\nimport java.lang.annotation.*;\n\n"
    "@Retention(RetentionPolicy.RUNTIME)\n@Target(ElementType.METHOD)\npublic @interface Then {\n    String value();\n}\n",
}
STATUS = "package com.example;\n\npublic enum Status { NEW, PAID, SHIPPED }\n"
TYPES = ("package com.example;\n\nimport io.cucumber.java.ParameterType;\n\npublic class Types {\n"
         "    @ParameterType(\".*\")\n    public Status status(String value) {\n        return Status.valueOf(value);\n    }\n}\n")
DOUBLING_STEPS = ("package com.example.service.acceptance;\n\nimport io.cucumber.java.en.Then;\n\npublic class DoublingSteps {\n"
                  "    @Then(\"the result table is:\")\n    public void resultTable(Object table) {\n"
                  "        throw new IllegalArgumentException(\"No enum constant\");\n    }\n}\n")


def enum_rejected(*glue_frames):
    """Enum.valueOf failing in the glue method Cucumber called: the stack is cut right behind its frame."""
    return thrown("java.lang.IllegalArgumentException", "No enum constant com.example.Status.STIPPED",
                  frames=("java.base/java.lang.Enum.valueOf(Enum.java:293)",) + glue_frames + (STEP_FRAME,))


def step_frame(line):
    """The step frame of a step on another line of the generated feature."""
    return STEP_FRAME.replace(".feature:5)", f".feature:{line})")


def merged(exc_type=ASSERTION, message="expected: <10> but was: <18>", frames=(GLUE_FRAME, STEP_FRAME),
           tag="flakyFailure"):
    """A failed attempt inside a merged <testcase> (reports.junitXml.mergeReruns, Surefire's shape): <flakyFailure> when
    the scenario passed in the end, <rerunFailure> for a later attempt of one that failed every time. Gradle 8.14
    writes the stack trace into a <stackTrace> child, not as the element's text."""
    text = f"{exc_type}: {message}\n" + "".join(f"\tat {frame}\n" for frame in frames)
    return (f"    <{tag} message={quoteattr(exc_type + ': ' + message)} type={quoteattr(exc_type)}>\n"
            f"      <stackTrace>{escape(text)}</stackTrace>\n    </{tag}>\n")


def attempts(name, runs, merge):
    """[(testcase name, body)] for the attempts of one scenario - each a failure (exc_type, message, frames), PASSED or
    SKIPPED - as Gradle 8.14 writes them: a <testcase> per attempt; with reports.junitXml.mergeReruns, failed attempts
    and the attempt that ends them share one <testcase>: <flakyFailure> per failure when the last one passed (no
    element) or was skipped (<skipped>), else <failure> for the first and <rerunFailure> for each later one."""
    if not merge:
        return [(name, thrown(*a) if isinstance(a, tuple) else a) for a in runs]
    cases, group = [], []
    for i, a in enumerate(runs):
        group.append(a)
        if isinstance(a, tuple) and i + 1 < len(runs):
            continue                                            # a failure: the next attempt joins its <testcase>
        failures = [g for g in group if isinstance(g, tuple)]
        if isinstance(a, tuple):                                # failed on every attempt
            body = thrown(*failures[0]) + "".join(merged(*f, tag="rerunFailure") for f in failures[1:])
        else:
            body = "".join(merged(*f, tag="flakyFailure") for f in failures) + a
        cases.append((name, body))
        group = []
    return cases


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


# ----------------------------------------------------------------------------- Cucumber's message stream

MUTANTS_URI = "file:///lab/build/gherkin-mutation/mutants/"
RUN_START_MS = 1_795_469_163_000          # 2026-11-23, when the synthetic runs start


def stamp(ms):
    """A Cucumber timestamp {seconds, nanos}, ms milliseconds (a float: to the nanosecond) after the run started."""
    ns = RUN_START_MS * 1_000_000 + round(ms * 1_000_000)
    return {"seconds": ns // 1_000_000_000, "nanos": ns % 1_000_000_000}


def envelopes(cases, compiled=()):
    """The envelopes of Cucumber's message stream that the tool reads, in the shape Cucumber 7.23.0 and 8.0.1 write them
    (taken from real runs): cases = [(uri, line, name, started ms, finished ms or None: never finished)], a test case
    each, in the order given; compiled = [(uri, line, name)], pickles the run compiled but did not run (a filter dropped
    them). A line is a Scenario's line, or (Scenario line, Examples row line) for an outline's row."""
    out = [{"meta": {"protocolVersion": "27.2.0", "implementation": {"name": "cucumber-jvm", "version": "7.23.0"}}},
           {"testRunStarted": {"timestamp": stamp(0)}}]
    nodes = {}                                  # uri -> {(scenario line, row line or None): (scenario id, row id)}
    pickles = []
    for uri, line, name, *_ in list(cases) + [c + (None, None) for c in compiled]:
        scenario, row = line if isinstance(line, tuple) else (line, None)
        ids = nodes.setdefault(uri, {}).setdefault((scenario, row), (f"s{len(pickles)}", f"r{len(pickles)}"))
        pickles.append((uri, (scenario, row), name, ids))
    for uri, scenarios in nodes.items():
        children = [{"scenario": {"id": sid, "location": {"line": scenario, "column": 3}, "keyword": "Scenario Outline",
                                  "name": "", "steps": [],
                                  "examples": [] if row is None else [{"id": "e" + sid, "location": {"line": row - 2, "column": 5},
                                                                        "tableHeader": {"id": "h" + sid, "location": {"line": row - 1, "column": 7}, "cells": []},
                                                                        "tableBody": [{"id": rid, "location": {"line": row, "column": 7}, "cells": []}]}]}}
                    for (scenario, row), (sid, rid) in scenarios.items()]
        out.append({"source": {"uri": uri, "data": "Feature: \"quoted\" \\ back\\slash and a line\nбreak", "mediaType": "text/x.cucumber.gherkin+plain"}})
        out.append({"gherkinDocument": {"uri": uri, "feature": {"location": {"line": 1, "column": 1}, "tags": [],
                                                                "language": "en", "keyword": "Feature", "name": "Ф",
                                                                "description": "", "children": children}}})
    for n, (uri, (scenario, row), name, (sid, rid)) in enumerate(pickles):
        out.append({"pickle": {"id": f"p{n}", "uri": uri, "name": name, "language": "en", "steps": [], "tags": [],
                               "astNodeIds": [sid] if row is None else [sid, rid]}})
    for n, case in enumerate(cases):
        out.append({"testCase": {"id": f"tc{n}", "pickleId": f"p{n}", "testSteps": []}})
    for n, (uri, line, name, started, finished) in enumerate(cases):
        out.append({"testCaseStarted": {"attempt": 0, "id": f"run{n}", "testCaseId": f"tc{n}", "workerId": "Test worker",
                                        "timestamp": stamp(started)}})
        if finished is not None:
            out.append({"testCaseFinished": {"testCaseStartedId": f"run{n}", "timestamp": stamp(finished),
                                             "willBeRetried": False}})
    out.append({"testRunFinished": {"success": False, "timestamp": stamp(10_000)}})
    return out


def write_messages(path, cases, compiled=()):
    write(path, "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in envelopes(cases, compiled)))


def without_timestamp(envelope):
    """A testCaseStarted envelope without its timestamp; any other envelope as it is."""
    envelope.get("testCaseStarted", {}).pop("timestamp", None)
    return envelope


def generated(scenario_id, started, finished):
    """A test case of a generated scenario: Cucumber names its feature file <id>.feature."""
    return MUTANTS_URI + scenario_id + ".feature", 3, f"{scenario_id.upper()} | {SCENARIO}", started, finished


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

    def compile_glue(self, sources, encoding="utf-8", options=(), glue="glue"):
        """Writes the glue sources under `glue` and compiles them there, as `javac -d glue` leaves them: the verdict
        reads the class files (--glue is the classpath of the mutant run), the sources only lie next to them."""
        stubs = self.path("cucumber-stubs")
        if not os.path.isdir(stubs):
            for rel, text in CUCUMBER_STUBS.items():
                write(self.path("cucumber-stubs-src", rel), text)
            self.javac("-d", stubs, *[self.path("cucumber-stubs-src", rel) for rel in CUCUMBER_STUBS])
        for rel, text in sources.items():
            os.makedirs(os.path.dirname(self.path(glue, rel)), exist_ok=True)
            with open(self.path(glue, rel), "wb") as f:
                f.write(text.encode(encoding))
        self.javac("-encoding", {"utf-8": "UTF-8", "utf-16-le": "UTF-16LE"}[encoding], "-cp", stubs, *options,
                   "-d", self.path(glue), *[self.path(glue, rel) for rel in sources])
        return self.path(glue)

    def javac(self, *args):
        r = subprocess.run(["javac", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8",
                           env=kit.java_env())
        self.assertEqual(0, r.returncode, r.stdout)

    def test_a_step_that_fails_before_the_value_is_used_kills_nothing(self):
        # the shared-state harness: the row's first step ("a new account ACC-1") fails on every repetition
        self.manifest_with_uses(7)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step())])     # step frame: line 5
        code, out = self.run_verdict()
        self.assertEqual(1, code, out)
        self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("MUTANT ERROR    m1 failed on line 5, before the first step that uses <price> (line 7) - the changed"
                      " value did not cause it, not a kill", out)

    def test_a_failure_of_a_mutant_whose_column_no_step_uses_kills_nothing(self):
        # review of 7061885: uses=0 (a Then with a literal, a column only in the scenario title) read as "unknown", so a
        # stand failure that hit only the mutant's run was a kill and the survivor that flags the spec went green
        self.manifest_with_uses(0)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step())])
        code, out = self.run_verdict()
        self.assertEqual(1, code, out)
        self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("MUTANT ERROR    m1 failed, but no step uses <price> (the scenario title at most) - the changed"
                      " value did not cause it, not a kill", out)

    def test_a_mutant_whose_column_no_step_uses_survives(self):
        self.manifest_with_uses(0)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), PASSED)])
        code, out = self.run_verdict()
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT SURVIVED m1", out)

    def test_a_step_that_fails_where_the_value_is_used_kills(self):
        for uses in (5, 4):
            with self.subTest(uses=uses):
                self.manifest_with_uses(uses)
                write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step())])
                code, out = self.run_verdict()
                self.assertEqual(0, code, out)
                self.assertIn("1 killed, 0 survived, 0 error(s)", self.summary(out))

    def test_a_line_break_in_the_step_text_hides_no_line(self):
        # An Examples value with \n is part of the step text, and Cucumber 7.23.0 and 8.0.1 print it in the step frame:
        # 'at ✽.the parcel goes to "line1<LF>line2"(file:///.../m1.feature:4)'. Read to the end of the line the frame
        # starts on, it named no line - a stand failure before the first use of the value counted as a kill - or the
        # ":2)" of "(floor:2)" in the value (review of efa4c50). What follows the frame differs: nothing, "Caused by:",
        # and Gradle's "Cause 1:" for a MultipleFailuresError without suppressed exceptions.
        uri = "file:///lab/build/gherkin-mutation/mutants/m1.feature"
        glue = "com.example.service.acceptance.LabelSteps.address(LabelSteps.java:14)"
        after = {"nothing": "",
                 "a cause": "Caused by: java.io.IOException: refused\n\tat com.example.Stand.call(Stand.java:3)\n"
                            "\t... 1 more\n",
                 "Gradle's causes": "Cause 1: java.lang.AssertionError: count 4\n"
                                    "\tat com.example.Stand.call(Stand.java:3)\n"}

        def failed(step, line, tail):
            trace = f"java.lang.IllegalStateException: stand unavailable\n\tat {glue}\n\tat ✽.{step}({uri}:{line})\n"
            return (f'    <failure message="stand unavailable" type="java.lang.IllegalStateException">'
                    f'{escape(trace + tail)}</failure>\n')

        # a line of the value that itself ends like a frame ("see a.feature:3)") is no location either: the frame is
        # known by the generated file's own name (review of the merged fixes)
        for text in ('the parcel goes to "line1\nline2"', 'the parcel goes to "Office (floor:2)\nLondon"',
                     'the parcel goes to "line1 line2"', 'the parcel goes to "x\nsee a.feature:3)\nb"',
                     'the report reads "Undefined step\nat login.feature:12)\nSkipped"'):
            for name, tail in after.items():
                with self.subTest(text=text, after=name):
                    self.manifest_with_uses(5)
                    write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), failed(text, 4, tail))])
                    code, out = self.run_verdict()
                    self.assertEqual(1, code, out)
                    self.assertIn("MUTANT ERROR    m1 failed on line 4, before the first step that uses <price>"
                                  " (line 5)", out)
                    write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), failed(text, 6, tail))])
                    code, out = self.run_verdict()
                    self.assertEqual(0, code, out)      # on line 6, after the first use: a kill
                    self.assertIn("1 killed (1 by a non-assertion exception thrown in a step), 0 survived, 0 error(s)",
                                  self.summary(out))

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
        self.compile_glue({"com/example/Types.java": TYPES, "com/example/Status.java": STATUS,
                           "com/example/service/acceptance/DoublingSteps.java": DOUBLING_STEPS})
        transformer = enum_rejected("app//com.example.Types.status(Types.java:8)")
        step_body = enum_rejected(GLUE_FRAME)
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), transformer)])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    m1 the value never reached a step definition (java.lang.IllegalArgumentException", out)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), step_body)])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(0, code, out)          # the same exception from the step's own code is a kill
        self.assertIn("1 killed (1 by a non-assertion exception thrown in a step), 0 survived", self.summary(out))

    def test_every_glue_directory_is_read_whole(self):
        # --glue went joined with commas: a root under "acme, inc" came apart, its transformers were never read and
        # the rejected value counted as a kill (review of 2c1cd0b); one entry per --glue is never split
        self.compile_glue({"com/example/Types.java": TYPES, "com/example/Status.java": STATUS}, glue="acme, inc/glue")
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), PASSED),
                                     (mutant_name(1), enum_rejected("app//com.example.Types.status(Types.java:7)"))])
        for glue in (["--glue", "acme, inc/glue"], ["--glue", "acme, inc/glue", "--glue", "src/acceptanceTest/kotlin"],
                     ["--glue", "src/acceptanceTest/kotlin", "--glue", "acme, inc/glue"]):
            with self.subTest(glue=glue):
                code, out = self.run_verdict(*glue)
                self.assertEqual(1, code, out)
                self.assertIn("MUTANT ERROR    m1 the value never reached a step definition", out)

    def test_a_transformer_named_in_any_alphabet_is_found(self):
        # a Java or Kotlin name is any letter, not only ASCII (review of 65c03da): the method's and the class's
        status = "package com.example;\n\npublic enum Статус { НОВЫЙ, ОТГРУЖЕН }\n"
        for cls in ("Types", "Типы"):
            with self.subTest(cls):
                self.compile_glue({"com/example/Статус.java": status, f"com/example/{cls}.java":
                                   f"package com.example;\n\nimport io.cucumber.java.ParameterType;\n\npublic class {cls} {{\n"
                                   "    @ParameterType(\".*\")\n    public Статус статус(String value) {\n"
                                   "        return Статус.valueOf(value);\n    }\n}\n"})
                transformer = thrown("java.lang.IllegalArgumentException", "No enum constant com.example.Статус.ОТГРУЖЕНЕ",
                                     frames=("java.base/java.lang.Enum.valueOf(Enum.java:293)",
                                             f"app//com.example.{cls}.статус({cls}.java:8)", STEP_FRAME))
                self.manifest_with_uses(5)
                write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), transformer)])
                code, out = self.run_verdict("--glue", "glue")
                self.assertEqual(1, code, out)
                self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
                self.assertIn("MUTANT ERROR    m1 the value never reached a step definition (java.lang.IllegalArgumentException",
                              out)

    def test_a_transformer_is_found_whatever_the_encoding_of_its_source(self):
        # glue sources in UTF-16LE (JavaCompile.options.encoding = 'UTF-16LE'): read as UTF-8 they named no
        # transformer, and a value the transformer rejected counted as a kill (review of 2c1cd0b)
        self.compile_glue({"com/example/Types.java": TYPES, "com/example/Status.java": STATUS}, encoding="utf-16-le")
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), PASSED),
                                     (mutant_name(1), enum_rejected("app//com.example.Types.status(Types.java:8)"))])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(1, code, out)
        self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("MUTANT ERROR    m1 the value never reached a step definition (java.lang.IllegalArgumentException", out)

    def test_a_namesake_transformer_in_another_class_takes_no_kill(self):
        # Cucumber knows a glue method by its class and its name: a @ParameterType `result` in another package's
        # DiscountSteps.java is not the step definition DiscountSteps.result that asserted (review of 2c1cd0b)
        steps = ("package com.example.service.acceptance;\n\nimport io.cucumber.java.en.Then;\n\npublic class DiscountSteps {\n"
                 "    @Then(\"the total is {int}\")\n    public void result(int expected) {\n"
                 "        throw new AssertionError(\"expected: <9900> but was: <9894>\");\n    }\n}\n")
        namesake = ("package com.example.service.reporting;\n\nimport io.cucumber.java.ParameterType;\n\n"
                    "public class DiscountSteps {\n    @ParameterType(\"summary|report\")\n"
                    "    public String result(String value) {\n        return value;\n    }\n}\n")
        self.compile_glue({"com/example/service/acceptance/DiscountSteps.java": steps,
                           "com/example/service/reporting/DiscountSteps.java": namesake})
        kill = thrown(ASSERTION, "expected: <9900> but was: <9894>",
                      frames=("app//com.example.service.acceptance.DiscountSteps.result(DiscountSteps.java:8)", STEP_FRAME))
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), kill)])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(0, code, out)
        self.assertIn("1 killed, 0 survived, 0 error(s)", self.summary(out))

    def test_a_step_definition_with_a_transformer_s_name_is_told_apart_only_by_its_line(self):
        # one class, one name: the transformer status(String) and the step definition status(Status). A line of the
        # step definition is the evidence of a kill; compiled without line numbers the name decides - no kill
        steps = ("package com.example;\n\nimport io.cucumber.java.ParameterType;\nimport io.cucumber.java.en.Then;\n\n"
                 "public class OrderSteps {\n    @ParameterType(\"[A-Z]+\")\n    public Status status(String name) {\n"
                 "        return Status.valueOf(name);\n    }\n\n    @Then(\"the order is in status {status}\")\n"
                 "    public void status(Status expected) {\n        throw new AssertionError(\"expected: <\" + expected + \">\");\n"
                 "    }\n}\n")
        for options, location, killed in (((), "OrderSteps.java:{}", True), (("-g:none",), "Unknown Source", False)):
            with self.subTest(options=options):
                self.compile_glue({"com/example/OrderSteps.java": steps, "com/example/Status.java": STATUS}, options=options)
                self.manifest_with_uses(5)
                frame = "app//com.example.OrderSteps.status(" + location + ")"
                write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), enum_rejected(frame.format(9)))])
                code, out = self.run_verdict("--glue", "glue")
                self.assertEqual(1, code, out)
                self.assertIn("MUTANT ERROR    m1 the value never reached a step definition", out)
                in_step_definition = thrown(ASSERTION, "expected: <PAID>", frames=(frame.format(14), STEP_FRAME))
                write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step_definition)])
                code, out = self.run_verdict("--glue", "glue")
                self.assertEqual(0 if killed else 1, code, out)
                self.assertIn("1 killed, 0 survived, 0 error(s)" if killed else "0 killed, 0 survived, 1 error(s)",
                              self.summary(out))

    def renamed(self, class_file, old, new):
        """The class file with one method renamed to a name javac cannot write - same length, so the constant pool stays valid."""
        with open(class_file, "rb") as f:
            data = f.read()
        self.assertEqual(1, data.count(old.encode()))
        with open(class_file, "wb") as f:
            f.write(data.replace(old.encode(), new.encode()))

    def test_a_glue_method_named_with_spaces_is_still_its_frame(self):
        # Kotlin's `order status` (backticks, allowed in test code): its frame "Types.order status(Types.kt:8)" was
        # skipped, and the frame before it decided - Status.valueOf (no transformer: the rejected value was a kill), or
        # java.util.Optional (not on the glue classpath: exit 2 on a kill) (review of the 2c1cd0b fixes)
        types = TYPES.replace("public Status status(", "public Status orderXstatus(")
        steps = ("package com.example;\n\npublic class OrderSteps {\n    public void theXorderXisXfound(String id) {\n"
                 "        java.util.Optional.empty().orElseThrow();\n    }\n}\n")
        glue = self.compile_glue({"com/example/Types.java": types, "com/example/Status.java": STATUS,
                                  "com/example/OrderSteps.java": steps})
        self.renamed(os.path.join(glue, "com/example/Types.class"), "orderXstatus", "order status")
        self.renamed(os.path.join(glue, "com/example/OrderSteps.class"), "theXorderXisXfound", "the order is found")
        self.manifest_with_uses(5)
        rejected = enum_rejected("app//com.example.Status.valueOf(Status.kt)", "app//com.example.Types.order status(Types.kt:8)")
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), rejected)])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    m1 the value never reached a step definition", out)
        kill = thrown("java.util.NoSuchElementException", "No value present",
                      frames=("java.base/java.util.Optional.orElseThrow(Optional.java:377)",
                              "app//com.example.OrderSteps.the order is found(OrderSteps.kt:16)", STEP_FRAME))
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), kill)])
        code, out = self.run_verdict("--glue", "glue")
        self.assertEqual(0, code, out)
        self.assertIn("1 killed (1 by a non-assertion exception thrown in a step), 0 survived, 0 error(s)", self.summary(out))

    def test_the_glue_classpath_is_read_like_a_class_loader_reads_it(self):
        # --glue is the classpath of the mutant run: class directories and jars (shared glue) in its order, one entry
        # per --glue or one per line of --glue-file (NUL-ended, as Gradle writes it) - a comma or a colon belongs to a
        # directory name; a nested class is Outer$Inner
        nested = ("package com.example;\n\nimport io.cucumber.java.ParameterType;\n\npublic class Steps {\n"
                  "    public static class Types {\n        @ParameterType(\".*\")\n"
                  "        public Status status(String value) {\n            return Status.valueOf(value);\n        }\n"
                  "    }\n}\n")
        classes = self.compile_glue({"com/example/Steps.java": nested, "com/example/Status.java": STATUS}, glue="shared")
        jar = self.path("shared-glue.jar")
        with zipfile.ZipFile(jar, "w") as z:
            for root, _, files in os.walk(classes):
                for name in files:
                    if name.endswith(".class"):
                        z.write(os.path.join(root, name), os.path.relpath(os.path.join(root, name), classes))
        shutil.rmtree(classes)
        os.makedirs(self.path("Скидка, рубли", "classes"))
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), PASSED),
                                     (mutant_name(1), enum_rejected("app//com.example.Steps$Types.status(Steps.java:9)"))])
        entries = [self.path("Скидка, рубли", "classes"), self.path("missing"), jar]
        write(self.path("glue-classpath"), "".join(e + "\0" for e in entries))
        for how, options in (("--glue", [o for e in entries for o in ("--glue", e)]),
                             ("--glue-file", ["--glue-file", "glue-classpath"])):
            with self.subTest(how):
                code, out = self.run_verdict(*options)
                self.assertEqual(1, code, out)
                self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
                self.assertIn("MUTANT ERROR    m1 the value never reached a step definition", out)

    def test_a_step_frame_whose_class_is_not_on_the_glue_classpath_is_no_guess(self):
        # whether its method was a transformer is unknown: counting the failure as a kill could pass a rejected value
        self.compile_glue({"com/example/Types.java": TYPES, "com/example/Status.java": STATUS})
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step())])      # DoublingSteps
        r = kit.tool("GherkinMutator", "verdict", "--mutants", "mutants", "--results", "results", "--glue", "glue",
                     cwd=self.dir)
        self.assertEqual(2, r.code, r)
        self.assertIn("class com.example.service.acceptance.DoublingSteps of a step frame is not on the glue classpath"
                      " (--glue)", r.out)

    def test_a_scenario_that_ran_twice_with_different_results_proves_nothing(self):
        # a retry plugin or a rerun reports every attempt: a failure and a pass is no stable detection (review of 65c03da)
        for order, attempts in {"failed, then passed": (in_step(), PASSED),
                                "passed, then failed": (PASSED, in_step())}.items():
            with self.subTest(order):
                self.manifest_with_uses(5)
                write_results(self.results, [(control_name(1), PASSED)] + [(mutant_name(1), a) for a in attempts])
                code, out = self.run_verdict()
                self.assertEqual(1, code, out)
                self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
                self.assertIn("MUTANT ERROR    m1 ran more than once with different results", out)
                write_results(self.results, [(control_name(1), a) for a in attempts] + [(mutant_name(1), in_step())])
                code, out = self.run_verdict()
                self.assertEqual(1, code, out)
                self.assertIn("1 killed, 0 survived, 0 error(s); 1 control(s) - 0 passed", self.summary(out))
                self.assertIn("MUTANT ERROR    c1 control (unmutated scenario) ran more than once with different results",
                              out)
        # the same result on every attempt is one result: a retried kill is a kill
        write_results(self.results, [(control_name(1), PASSED), (control_name(1), PASSED),
                                     (mutant_name(1), in_step()), (mutant_name(1), in_step())])
        code, out = self.run_verdict()
        self.assertEqual(0, code, out)
        self.assertIn("1 killed, 0 survived, 0 error(s); 1 control(s) - 1 passed", self.summary(out))

    def test_every_attempt_is_judged_against_the_first_step_that_uses_the_value(self):
        # two attempts of one mutant fail in a step: on line 8, after the first use of the value (line 7) - a kill -,
        # and on line 5, before it - no kill. Keeping one failure of the two made the verdict depend on the order of
        # the attempts (review of 2c1cd0b)
        line = {n: (ASSERTION, f"failed on line {n}", (GLUE_FRAME, step_frame(n))) for n in (5, 6, 8, 9)}
        self.manifest_with_uses(7)
        for order in ((8, 5), (5, 8)):
            for merge in (False, True):
                with self.subTest(lines=order, mergeReruns=merge):
                    write_results(self.results, [(control_name(1), PASSED)]
                                  + attempts(mutant_name(1), [line[n] for n in order], merge))
                    code, out = self.run_verdict()
                    self.assertEqual(1, code, out)
                    self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
                    self.assertIn("MUTANT ERROR    m1 ran more than once with different results", out)
        # the same verdict on every attempt is that verdict: two kills are a kill, two early failures one error
        same = {(8, 9): "1 killed, 0 survived, 0 error(s)", (5, 6): "0 killed, 0 survived, 1 error(s)"}
        for order, summary in same.items():
            for merge in (False, True):
                with self.subTest(lines=order, mergeReruns=merge):
                    write_results(self.results, [(control_name(1), PASSED)]
                                  + attempts(mutant_name(1), [line[n] for n in order], merge))
                    code, out = self.run_verdict()
                    self.assertIn(summary, self.summary(out))
                    self.assertNotIn("ran more than once", out)
                    if order == (5, 6):
                        self.assertIn("MUTANT ERROR    m1 failed on line 5, before the first step that uses <price>"
                                      " (line 7)", out)

    def test_merged_and_separate_attempts_give_the_same_verdict(self):
        # with reports.junitXml.mergeReruns Gradle merges the attempts of a test that failed into one <testcase>; a
        # control that failed and then passed has only a <flakyFailure> there - read as passed, it let the gate pass
        # (review of 2c1cd0b). Both shapes of the same attempts are one run and give one verdict.
        kill = (ASSERTION, "expected: <10> but was: <18>", (GLUE_FRAME, STEP_FRAME))
        early = (ASSERTION, "account ACC-1 already exists", (GLUE_FRAME, step_frame(4)))
        hook = ("java.io.IOException", "Database fixture unavailable", (HOOK_FRAME,))
        unstable = "ran more than once with different results"
        mutants = {
            "killed, killed": ((kill, kill), "1 killed, 0 survived, 0 error(s)", None),
            "killed, killed, killed": ((kill, kill, kill), "1 killed, 0 survived, 0 error(s)", None),
            "passed, passed": ((PASSED, PASSED), "0 killed, 1 survived, 0 error(s)", "MUTANT SURVIVED m1"),
            "hook, hook": ((hook, hook), "0 killed, 0 survived, 1 error(s)", "m1 failed outside a step"),
            "killed, passed": ((kill, PASSED), "0 killed, 0 survived, 1 error(s)", "m1 " + unstable),
            "killed, killed, passed": ((kill, kill, PASSED), "0 killed, 0 survived, 1 error(s)", "m1 " + unstable),
            "passed, killed": ((PASSED, kill), "0 killed, 0 survived, 1 error(s)", "m1 " + unstable),
            "killed, skipped": ((kill, SKIPPED), "0 killed, 0 survived, 1 error(s)", "m1 " + unstable),
            "hook, killed": ((hook, kill), "0 killed, 0 survived, 1 error(s)", "m1 " + unstable),
            "killed, early": ((kill, early), "0 killed, 0 survived, 1 error(s)", "m1 " + unstable),
        }
        broken = "c1 control (unmutated scenario) "
        controls = {
            "passed, passed": ((PASSED, PASSED), "1 control(s) - 1 passed", None),
            "failed, failed": ((kill, kill), "1 control(s) - 0 passed", broken + "failed in a step"),
            "failed, passed": ((kill, PASSED), "1 control(s) - 0 passed", broken + unstable),
            "failed, skipped": ((kill, SKIPPED), "1 control(s) - 0 passed", broken + unstable),
            "hook, passed": ((hook, PASSED), "1 control(s) - 0 passed", broken + unstable),
        }
        for merge in (False, True):
            for name, (runs, summary, message) in mutants.items():
                with self.subTest("mutant: " + name, mergeReruns=merge):
                    self.manifest_with_uses(5)
                    write_results(self.results, [(control_name(1), PASSED)] + attempts(mutant_name(1), runs, merge))
                    code, out = self.run_verdict()
                    self.assertIn(summary + "; 1 control(s) - 1 passed", self.summary(out))
                    self.assertEqual(0 if message is None else 1, code, out)
                    if message:
                        self.assertIn(message, out)
            for name, (runs, summary, message) in controls.items():
                with self.subTest("control: " + name, mergeReruns=merge):
                    self.manifest_with_uses(5)
                    write_results(self.results, attempts(control_name(1), runs, merge) + [(mutant_name(1), in_step())])
                    code, out = self.run_verdict()
                    self.assertIn("1 killed, 0 survived, 0 error(s); " + summary, self.summary(out))
                    self.assertEqual(0 if message is None else 1, code, out)
                    if message:
                        self.assertIn("MUTANT ERROR    " + message, out)

    def test_surefire_s_flaky_and_rerun_errors_are_attempts_as_well(self):
        # Surefire-style writers merge a non-assertion exception as <flakyError> / <rerunError>
        self.manifest_with_uses(5)
        write_results(self.results, [(control_name(1), merged("java.lang.IllegalStateException", tag="flakyError")),
                                     (mutant_name(1), in_step(tag="error") + merged(tag="rerunError"))])
        code, out = self.run_verdict()
        self.assertEqual(1, code, out)
        self.assertIn("1 killed, 0 survived, 0 error(s); 1 control(s) - 0 passed", self.summary(out))
        self.assertIn("MUTANT ERROR    c1 control (unmutated scenario) ran more than once with different results",
                      out)

    def test_a_rerun_attempt_is_judged_on_its_stack_trace_not_its_output(self):
        # first attempt a kill; the rerun a hook failure whose output (<system-out>, a sibling of <stackTrace>) holds a
        # step frame: read as the element's text, the rerun was one more kill
        self.manifest_with_uses(5)
        rerun = merged("java.io.IOException", "Database fixture unavailable", (HOOK_FRAME,), tag="rerunFailure")
        rerun = rerun.replace("</stackTrace>\n", "</stackTrace>\n      <system-out>" + escape("\tat " + STEP_FRAME + "\n")
                              + "</system-out>\n")
        write_results(self.results, [(control_name(1), PASSED), (mutant_name(1), in_step() + rerun)])
        code, out = self.run_verdict()
        self.assertEqual(1, code, out)
        self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
        self.assertIn("MUTANT ERROR    m1 ran more than once with different results", out)

    def test_the_stage_of_a_merged_attempt_is_read_from_its_stack_trace(self):
        # the trace of a flaky or rerun attempt is the <stackTrace> child: its step frame, transformer and runner
        # frames decide exactly as in a <failure>
        self.compile_glue({"com/example/Types.java": TYPES, "com/example/Status.java": STATUS})
        rejected = ("java.lang.IllegalArgumentException", "No enum constant com.example.Status.STIPPED",
                    ("java.base/java.lang.Enum.valueOf(Enum.java:293)", "app//com.example.Types.status(Types.java:7)",
                     STEP_FRAME))
        self.manifest_with_uses(5)
        for merge in (False, True):
            with self.subTest(mergeReruns=merge):
                write_results(self.results, [(control_name(1), PASSED)]
                              + attempts(mutant_name(1), (rejected, rejected), merge))
                code, out = self.run_verdict("--glue", "glue")
                self.assertEqual(1, code, out)
                self.assertIn("0 killed, 0 survived, 1 error(s)", self.summary(out))
                self.assertIn("MUTANT ERROR    m1 the value never reached a step definition"
                              " (java.lang.IllegalArgumentException", out)


# ----------------------------------------------------------------------------- run order

class RunOrderTest(Sandbox):
    """The controls of a row prove the harness only for the mutants that ran between them, one scenario at a time: the
    verdict judges that by Cucumber's message stream of the run (--messages), not by the settings the run had."""

    def setUp(self):
        super().setUp()
        rows = [GENERATED_HEADER] + ["\t".join([m, FEATURE, "11", SCENARIO, "price", "5", "9", "4"]) for m in ("m1", "m2")]
        rows += ["\t".join([c, FEATURE, "11", SCENARIO, "(control)", "", "", ""]) for c in ("c1", "z1")]
        write(os.path.join(self.mutants, "manifest.tsv"), "\n".join(rows) + "\n")

    def judge(self, *streams, attempts=1):
        """streams: the test cases of each test JVM's stream. The JUnit XML: every scenario passed or killed, as often
        as `attempts` says."""
        for n, cases in enumerate(streams, 1):
            write_messages(self.path("messages", f"jvm-{n}.ndjson"), cases)
        write_results(self.results, [(control_name(c), PASSED) for c in ("c1", "z1") for _ in range(attempts)]
                      + [(mutant_name(m), in_step()) for m in (1, 2) for _ in range(attempts)])
        return tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages", cwd=self.dir)

    IN_ORDER = [generated("c1", 0, 10), generated("m1", 11, 20), generated("m2", 21, 30), generated("z1", 31, 40)]

    def test_a_run_one_scenario_at_a_time_in_the_order_of_the_names_passes(self):
        # behaviour that must not change; at the same instant is not at the same time (a coarse clock gives that)
        for cases in (self.IN_ORDER, [generated("c1", 0, 10), generated("m1", 10, 20), generated("m2", 20, 30),
                                      generated("z1", 30, 40)]):
            with self.subTest(cases=[c[3:] for c in cases]):
                code, out = self.judge(cases)
                self.assertEqual("Gherkin mutation: 2 mutant(s) - 2 killed, 0 survived, 0 error(s); 2 control(s) - 2 passed",
                                 self.summary(out))
                self.assertNotIn("run order", out)
                self.assertEqual(0, code, out)

    def test_scenarios_that_ran_at_the_same_time_prove_nothing(self):
        # parallel Cucumber through _JAVA_OPTIONS, an argument file or a provider the kit's check of the arguments did
        # not see (review of 7061885): both controls ran at once, then the mutants - every one "killed" by a stand
        # that wore out (issue #4)
        code, out = self.judge([generated("c1", 0, 10), generated("z1", 2, 12), generated("m1", 13, 20),
                                generated("m2", 13.5, 21)])
        self.assertEqual(1, code, out)
        self.assertIn("2 killed, 0 survived, 0 error(s); 2 control(s) - 2 passed", self.summary(out))
        self.assertIn("MUTANT ERROR    run order: c1 and z1 ran at the same time (jvm-1.ndjson: z1 started 8.000 ms before"
                      " c1 finished)", out)
        self.assertIn("MUTANT ERROR    run order: m1 and m2 ran at the same time (jvm-1.ndjson: m2 started 6.500 ms before"
                      " m1 finished)", out)
        self.assertIn("MUTANT ERROR    run order: m1 did not run between its controls c1 and z1 - z1 started before it"
                      " finished (jvm-1.ndjson)", out)
        self.assertIn("  Run order: the controls prove the harness only for the mutants that ran between them", out)
        self.assertNotIn("Gherkin mutation: OK", out)

    def test_a_mutant_outside_its_controls_proves_nothing(self):
        # one at a time, but not in the order of the names: a random order on Cucumber 8, a reversed one
        cases = {
            "z1 first": ([generated("z1", 0, 10), generated("c1", 11, 20), generated("m1", 21, 30), generated("m2", 31, 40)],
                         "m1 did not run between its controls c1 and z1 - z1 started before it finished"),
            "a mutant first": ([generated("m1", 0, 10), generated("c1", 11, 20), generated("m2", 21, 30),
                                generated("z1", 31, 40)], "m1 did not run between its controls c1 and z1 - it started"
                                                          " before c1 finished"),
        }
        for what, (stream, problem) in cases.items():
            with self.subTest(what):
                code, out = self.judge(stream)
                self.assertEqual(1, code, out)
                self.assertIn("MUTANT ERROR    run order: " + problem + " (jvm-1.ndjson)", out)
                self.assertNotIn("ran at the same time", out)

    def test_a_mutant_and_its_controls_in_different_test_jvms_prove_nothing(self):
        # forks or mid-run OOM restart: each JVM is a stream of its own
        code, out = self.judge([generated("c1", 0, 10), generated("z1", 31, 40)],
                               [generated("m1", 11, 20), generated("m2", 21, 30)])
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    run order: worker JVM restarted or split scenarios across 2 Cucumber message"
                      " streams (jvm-1.ndjson, jvm-2.ndjson) - check OutOfMemoryError / gherkin.maxHeapSize", out)
        self.assertIn("MUTANT ERROR    run order: m1 did not run between its controls c1 and z1 - c1 did not run in the"
                      " same test JVM (jvm-2.ndjson)", out)

    def test_every_attempt_of_a_retry_is_judged(self):
        # the test-retry plugin runs each round in a new JVM, a stream each: both rounds in order pass, a round out of
        # order fails - and an attempt the JUnit XML reports without a test case in a stream has an unknown order
        code, out = self.judge(self.IN_ORDER, self.IN_ORDER, attempts=2)
        self.assertEqual(0, code, out)
        self.assertIn("2 killed, 0 survived, 0 error(s); 2 control(s) - 2 passed", self.summary(out))
        code, out = self.judge(self.IN_ORDER, [generated("c1", 0, 10), generated("z1", 5, 15), generated("m1", 16, 20),
                                               generated("m2", 21, 30)], attempts=2)
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    run order: c1 and z1 ran at the same time (jvm-2.ndjson: ", out)
        os.remove(self.path("messages", "jvm-2.ndjson"))
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages", cwd=self.dir)
        self.assertEqual(1, code, out)
        for scenario in ("m1", "m2", "c1", "z1"):
            self.assertIn(f"MUTANT ERROR    run order: {scenario} ran 2 time(s) by the JUnit XML and 1 by the message"
                          " stream - the order of an attempt is unknown", out)

    def test_a_missing_or_unreadable_stream_is_an_error(self):
        code, out = self.judge(self.IN_ORDER)
        self.assertEqual(0, code, out)
        shutil.rmtree(self.path("messages"))
        for what, prepare, problem in (
                ("no directory", lambda: None, "no Cucumber message stream in messages - what the run did is unknown"),
                ("an empty directory", lambda: os.makedirs(self.path("messages")),
                 "no Cucumber message stream in messages"),
                ("not JSON", lambda: write(self.path("messages", "jvm-1.ndjson"), '{"meta": {}}\n{"testCaseStarted": {\n'),
                 "cannot read the message stream messages/jvm-1.ndjson: line 2: not JSON at column 22"),
                ("no timestamp", lambda: write(self.path("messages", "jvm-1.ndjson"), "\n".join(
                    json.dumps(without_timestamp(e)) for e in envelopes(self.IN_ORDER)) + "\n"),
                 "cannot read the message stream messages/jvm-1.ndjson: timestamp is not a JSON object"),
                ("a test case of no pickle", lambda: write(self.path("messages", "jvm-1.ndjson"), "\n".join(
                    json.dumps(e) for e in envelopes(self.IN_ORDER) if "testCase" not in e) + "\n"),
                 "cannot read the message stream messages/jvm-1.ndjson: test case run0 started for a test case or pickle"
                 " the stream does not define"),
                ("an empty stream", lambda: write(self.path("messages", "jvm-1.ndjson"), ""),
                 "cannot read the message stream messages/jvm-1.ndjson: it holds no message - Cucumber did not start its"
                 " run")):
            with self.subTest(what):
                shutil.rmtree(self.path("messages"), ignore_errors=True)
                prepare()
                code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages",
                                 cwd=self.dir)
                self.assertEqual(1, code, out)
                self.assertIn("MUTANT ERROR    run order: " + problem, out)
                self.assertNotIn("Gherkin mutation: OK", out)

    def test_a_test_case_that_never_finished_is_an_error(self):
        # the JVM died in the middle of z1: whether anything ran beside it is unknown
        code, out = self.judge(self.IN_ORDER[:3] + [generated("z1", 31, None)])
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    run order: z1 started and never finished (jvm-1.ndjson)", out)

    def test_a_single_stream_file_is_read_as_well(self):
        write_results(self.results, [(control_name(c), PASSED) for c in ("c1", "z1")]
                      + [(mutant_name(m), in_step()) for m in (1, 2)])
        write_messages(self.path("run.ndjson"), [generated("c1", 0, 10), generated("z1", 5, 15), generated("m1", 16, 20),
                                                 generated("m2", 21, 30)])
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "run.ndjson", cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    run order: c1 and z1 ran at the same time (run.ndjson: ", out)
        write_messages(self.path("run.ndjson"), self.IN_ORDER)
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "run.ndjson", cwd=self.dir)
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: OK", out)

    def test_worker_thread_and_unwrapped_step_failures_resolved_from_message_stream(self):
        # Awaitility.untilAsserted builds AssertionError on a pool thread (no step method on its stack, so Cucumber
        # appends no "✽."), and Gradle 8.14's DefaultThrowableToTestFailureMapper unwraps ConditionTimeoutException to
        # that inner AssertionError cause when writing TEST-*.xml. Cucumber's NDJSON stream still records
        # testStepFinished(FAILED) with testStepId -> pickleStepId -> AST step line.
        worker_frames = ("com.example.service.acceptance.DoublingSteps.lambda$result$0(DoublingSteps.java:20)",
                         "java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1144)")

        def stream_with_step(m1_step_line, in_hook=False, msg_trace=""):
            uri_c1 = MUTANTS_URI + "c1.feature"
            uri_m1 = MUTANTS_URI + "m1.feature"
            uri_z1 = MUTANTS_URI + "z1.feature"
            evs = []
            for idx, (uri, cid) in enumerate(((uri_c1, "c1"), (uri_m1, "m1"), (uri_z1, "z1"))):
                evs.append({"gherkinDocument": {
                    "uri": uri,
                    "feature": {
                        "location": {"line": 1, "column": 1}, "language": "en", "keyword": "Feature", "name": "D",
                        "children": [{"scenario": {
                            "id": f"sc-{idx}", "location": {"line": 3, "column": 3}, "keyword": "Scenario Outline",
                            "name": SCENARIO,
                            "steps": [
                                {"id": f"ast-s1-{idx}", "location": {"line": 3, "column": 5}, "keyword": "Given ", "text": "setup"},
                                {"id": f"ast-s2-{idx}", "location": {"line": 5, "column": 5}, "keyword": "Then ", "text": "check"},
                            ],
                            "examples": [{"id": f"ex-{idx}", "location": {"line": 9, "column": 5},
                                          "tableBody": [{"id": f"row-{idx}", "location": {"line": 11, "column": 7}}]}],
                        }}],
                    },
                }})
                evs.append({"pickle": {
                    "id": f"p-{cid}", "uri": uri, "name": f"{cid.upper()} | {SCENARIO}", "language": "en",
                    "astNodeIds": [f"sc-{idx}", f"row-{idx}"],
                    "steps": [
                        {"id": f"ps1-{cid}", "text": "setup", "astNodeIds": [f"ast-s1-{idx}", f"row-{idx}"]},
                        {"id": f"ps2-{cid}", "text": "check", "astNodeIds": [f"ast-s2-{idx}", f"row-{idx}"]},
                    ],
                }})
                test_steps = [
                    {"id": f"hook-{cid}", "hookId": "h-before"},
                    {"id": f"ts1-{cid}", "pickleStepId": f"ps1-{cid}"},
                    {"id": f"ts2-{cid}", "pickleStepId": f"ps2-{cid}"},
                ]
                evs.append({"testCase": {"id": f"tc-{cid}", "pickleId": f"p-{cid}", "testSteps": test_steps}})
            for idx, (cid, st, fin) in enumerate((("c1", 0, 10), ("m1", 11, 20), ("z1", 21, 30))):
                evs.append({"testCaseStarted": {"id": f"run-{cid}", "testCaseId": f"tc-{cid}", "timestamp": stamp(st)}})
                if cid == "m1":
                    failed_ts = "hook-m1" if in_hook else ("ts1-m1" if m1_step_line == 3 else "ts2-m1")
                    res = {"status": "FAILED", "duration": {"seconds": 0, "nanos": 1000}}
                    if msg_trace:
                        res["message"] = msg_trace
                    evs.append({"testStepFinished": {"testCaseStartedId": "run-m1", "testStepId": failed_ts,
                                                     "testStepResult": res, "timestamp": stamp(st + 5)}})
                evs.append({"testCaseFinished": {"testCaseStartedId": f"run-{cid}", "timestamp": stamp(fin)}})
            return "".join(json.dumps(e) + "\n" for e in evs)

        # Single-mutant manifest (firstUse = line 4)
        rows = [GENERATED_HEADER,
                "\t".join(["m1", FEATURE, "11", SCENARIO, "price", "5", "9", "4"]),
                "\t".join(["c1", FEATURE, "11", SCENARIO, "(control)", "", "", ""]),
                "\t".join(["z1", FEATURE, "11", SCENARIO, "(control)", "", "", ""])]
        write(os.path.join(self.mutants, "manifest.tsv"), "\n".join(rows) + "\n")

        # 1. Worker-thread AssertionError in step at line 5 (>= firstUse 4) -> KILLED
        write_results(self.results, [(control_name("c1"), PASSED), (control_name("z1"), PASSED),
                                     (mutant_name(1), thrown(ASSERTION, "expected 10", worker_frames))])
        write(self.path("messages", "jvm-1.ndjson"), stream_with_step(5))
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages", cwd=self.dir)
        self.assertEqual(0, code, out)
        self.assertIn("1 mutant(s) - 1 killed, 0 survived, 0 error(s); 2 control(s) - 2 passed", self.summary(out))

        # 2. Worker-thread AssertionError in step at line 3 (< firstUse 4) -> early error, not a kill
        write(self.path("messages", "jvm-1.ndjson"), stream_with_step(3))
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages", cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    m1 failed on line 3, before the first step that uses <price> (line 4)", out)

        # 3. Worker-thread AssertionError in @Before hook -> failed outside a step, not a kill
        write(self.path("messages", "jvm-1.ndjson"), stream_with_step(5, in_hook=True))
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages", cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    m1 failed outside a step", out)

        # 4. Worker-thread exception inside a @ParameterType lambda -> rejected, not a kill
        glue_dir = self.path("glue-classes")
        src_dir = self.path("glue-src")
        for rel, content in CUCUMBER_STUBS.items():
            write(os.path.join(src_dir, rel), content)
        write(os.path.join(src_dir, "com/example/Status.java"), STATUS)
        write(os.path.join(src_dir, "com/example/Types.java"), TYPES)
        os.makedirs(glue_dir, exist_ok=True)
        sources = [os.path.join(dp, f) for dp, _, fs in os.walk(src_dir) for f in fs if f.endswith(".java")]
        subprocess.run(["javac", "--release", "21", "-g", "-d", glue_dir, *sources], check=True, env=kit.java_env())
        transformer_lambda_frames = ("com.example.Types.lambda$status$0(Types.java:5)",
                                     "java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1144)")
        write_results(self.results, [(control_name("c1"), PASSED), (control_name("z1"), PASSED),
                                     (mutant_name(1), thrown("java.lang.IllegalArgumentException", "bad",
                                                             transformer_lambda_frames))])
        write(self.path("messages", "jvm-1.ndjson"), stream_with_step(5))
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages",
                         "--glue", glue_dir, cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT ERROR    m1 the value never reached a step definition", out)


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

    def only_file(self, *paths):
        """--only-file with these features: each path ended by a NUL, as gauntlet.gradle writes the list."""
        write(self.path("changed-features"), "".join(p + "\0" for p in paths))
        return "--only-file", "changed-features"

    def test_only_limits_mutants_and_controls_to_the_named_features(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        write(self.path("features/discount.feature"), RUSSIAN)
        code, out = self.generate(*self.only_file("features/discount.feature"))
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: 2 mutant(s) + 2 control(s) from 1 feature file(s) in scope", out)
        self.assertEqual({"features/discount.feature"}, {r[1] for r in self.manifest()})

    def test_only_file_keeps_a_comma_quote_and_line_break_inside_a_name(self):
        # gauntlet.gradle joined the changed features with commas: "Скидка, рубли.feature" came apart into two
        # names of nothing, and gherkinMutation passed on 0 mutants (review of 2c1cd0b)
        names = ["features/Скидка, рубли.feature", 'features/Скидка "VIP".feature', "features/Скидка\nрубли.feature"]
        for name in names + ["features/doubling.feature"]:
            write(self.path(name), RUSSIAN)
        code, out = self.generate(*self.only_file(*names))
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: 6 mutant(s) + 6 control(s) from 3 feature file(s) in scope", out)

    def test_an_empty_list_puts_no_feature_in_scope(self):
        write(self.path("features/doubling.feature"), DOUBLING)
        code, out = self.generate(*self.only_file())
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: 0 mutant(s) + 0 control(s) from 0 feature file(s) in scope", out)

    def test_a_listed_path_that_names_no_feature_file_is_an_error(self):
        # a list that lost its paths on the way must not mutate nothing and pass
        write(self.path("features/Скидка, рубли.feature"), RUSSIAN)
        code, out = self.generate(*self.only_file("features/Скидка", " рубли.feature"))
        self.assertEqual(2, code, out)
        self.assertIn("GHERKIN ERROR the scope names no feature file under features", out)

    def test_a_line_break_in_a_feature_name_ends_no_line_of_the_output(self):
        # the path went into the header comment and manifest.tsv as it was: the comment's second half became a
        # line of Gherkin, and verdict cut the manifest row in two (ArrayIndexOutOfBoundsException, exit 2)
        for brk in ("\n", "\r"):
            with self.subTest(line_break=repr(brk)):
                shutil.rmtree(self.path("features"), ignore_errors=True)
                write(self.path("features/Скидка" + brk + "рубли.feature"), RUSSIAN)
                code, out = self.generate()
                self.assertEqual(0, code, out)
                self.assertEqual({"features/Скидка рубли.feature"}, {r[1] for r in self.manifest()})
                m1 = read_lines(os.path.join(self.mutants, "m1.feature"))
                self.assertEqual("# Gherkin mutant m1 of features/Скидка рубли.feature - generated, do not edit", m1[1])
                self.assertTrue(m1[2].startswith("Функция: MUTANT m1 | "), m1[2])
                code, out = tool("verdict", "--mutants", "mutants", "--results", "results", cwd=self.dir)
                self.assertEqual(1, code, out)                  # nothing ran: every mutant is "not executed"
                self.assertIn("MUTANT ERROR    m1 not executed  features/Скидка рубли.feature:", out)

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

    def test_a_retried_scenario_is_skipped_or_not_in_either_shape(self):
        # the test-retry plugin: a scenario that failed and was skipped on the retry is a skipped scenario whether
        # Gradle merged the attempts (reports.junitXml.mergeReruns: <flakyFailure> + <skipped>) or not; one that
        # failed and then passed is not - the acceptance task itself judges failures
        write(self.path("features/doubling.feature"), DOUBLING)
        failed = (ASSERTION, "the ledger is not open yet", (GLUE_FRAME, STEP_FRAME))
        other = ("Example #1.2", PASSED)
        for merge in (False, True):
            with self.subTest(mergeReruns=merge):
                write_results(self.results, attempts("Example #1.1", (failed, SKIPPED), merge) + [other])
                code, out = self.no_skipped()
                self.assertIn(f"ACCEPTANCE SKIPPED {ENGINE} > Example #1.1", out)
                self.assertIn("Acceptance: FAILED - 1 scenario(s) skipped.", out)
                self.assertEqual(1, code, out)
                write_results(self.results, attempts("Example #1.1", (failed, PASSED), merge) + [other])
                code, out = self.no_skipped()
                self.assertIn("none skipped - OK", out)
                self.assertEqual(0, code, out)

    def test_an_external_entity_in_a_results_file_is_not_read(self):
        # issue #3: the JUnit XML reader expanded a DOCTYPE's external entity - a file anywhere on the machine became
        # part of the results it judged, and its text part of the output. Gradle's JUnit XML declares no DOCTYPE (checked
        # on 7.23.0 and 8.0.1 runs): one that does is not read - and, a result file of Gradle's own name that does not
        # read, it is no verdict at all (review of 4.4: skipped silently, it took its scenarios out of the judgement)
        write(self.path("features/doubling.feature"), DOUBLING)
        write(self.path("elsewhere/secret.xml"), '<testcase name="TOP-SECRET-7" classname="planted"><skipped/></testcase>')
        write(os.path.join(self.results, "TEST-planted.xml"),
              '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE testsuite [<!ENTITY leak SYSTEM "'
              + pathlib.Path(self.path("elsewhere/secret.xml")).resolve().as_uri() + '">]>\n'
              '<testsuite name="Cucumber" tests="1">&leak;</testsuite>\n')
        code, out = self.no_skipped()
        self.assertNotIn("TOP-SECRET-7", out)
        self.assertEqual(2, code, out)                          # "cannot read the test results ..." on stderr
        write_results(self.results, [("Example #1.1", PASSED), ("Example #1.2", PASSED)])    # next to Gradle's own
        code, out = self.no_skipped()
        self.assertNotIn("TOP-SECRET-7", out)
        self.assertEqual(2, code, out)
        os.remove(os.path.join(self.results, "TEST-planted.xml"))
        write(os.path.join(self.results, "notes.xml"), "not xml at all")      # not a result file of Gradle's name
        code, out = self.no_skipped()
        self.assertIn("Acceptance: 2 scenario(s), none skipped - OK", out)
        self.assertEqual(0, code, out)


# ----------------------------------------------------------------------------- the census of an acceptance run

CENSUS = """Feature: Census

  Background:
    Given the shop is open

  Scenario: Plain
    Given step one

  Scenario: Reserved for later

  Scenario Outline: Without examples
    Given step <a>

  Scenario Outline: Header only
    Given step <a>

    Examples:
      | a |

  Rule: A rule
    Background:
      Given the rule holds

    Scenario Outline: Two tables
      Given step <a>

      Examples: first
        | a |
        | 1 |
        | 2 |

      @slow
      Examples: second
        | a |
        | 3 |
"""
# what Cucumber 7.23.0 and 8.0.1 compile CENSUS into (checked against their message streams): a scenario without steps
# and an outline without Examples are one pickle each, Examples with a header only none, a Background none
CENSUS_PICKLES = [(6, "Plain"), (9, "Reserved for later"), (11, "Without examples"), ((24, 29), "Two tables"),
                  ((24, 30), "Two tables"), ((24, 35), "Two tables")]


class CensusTest(Sandbox):
    """acceptanceCheck: every scenario the feature files define must have run - a filter that drops scenarios silently
    (includeTags/excludeTags of the test platform, a narrower cucumber.features) is finding F2 (issue #4)."""

    def uri(self, rel):
        return pathlib.Path(self.path(rel)).resolve().as_uri()

    def run_census(self, *streams, allowlist=None, results=2):
        """streams: per test JVM, the pickles of CENSUS that ran [(line, name)] and those compiled but not run."""
        for n, (ran, compiled) in enumerate(streams, 1):
            write_messages(self.path("messages", f"jvm-{n}.ndjson"),
                           [(uri, line, name, 10 * i, 10 * i + 5) for i, (uri, line, name) in enumerate(ran)], compiled)
        write_results(self.results, [(f"Example #1.{i}", PASSED) for i in range(1, results + 1)])
        if allowlist is not None:
            write(self.path("allowlist.txt"), allowlist)
        return tool("no-skipped", "--results", "results", "--features", "features", "--messages", "messages", "--root", ".",
                    "--allowlist", "allowlist.txt", cwd=self.dir)

    def census_pickles(self, rel="features/census.feature"):
        return [(self.uri(rel), line, name) for line, name in CENSUS_PICKLES]

    def test_every_scenario_of_the_feature_files_ran(self):
        write(self.path("features/census.feature"), CENSUS)
        code, out = self.run_census((self.census_pickles(), []), results=6)
        self.assertIn("Acceptance census: 6 of 6 scenario(s) in 1 feature file(s) ran", out)
        self.assertIn("Acceptance: 6 scenario(s), none skipped - OK", out)
        self.assertEqual(0, code, out)

    def test_a_scenario_a_filter_dropped_is_finding_f2(self):
        # useJUnitPlatform { excludeTags 'slow' }: Cucumber compiles the row of the @slow table and never runs it, and
        # neither the JUnit XML nor the skipped count shows it
        write(self.path("features/census.feature"), CENSUS)
        pickles = self.census_pickles()
        code, out = self.run_census((pickles[:5], [pickles[5]]), results=5)
        self.assertEqual(1, code, out)
        self.assertIn("ACCEPTANCE F2 features/census.feature  5 of 6 scenario(s) ran", out)
        self.assertIn("ACCEPTANCE F2 features/census.feature:35  did not run  |  Two tables", out)
        self.assertIn("Acceptance census: 5 of 6 scenario(s) in 1 feature file(s) ran", out)
        self.assertIn("Acceptance: FAILED - scenarios the feature files define did not run (finding F2)", out)
        self.assertNotIn("none skipped - OK", out)

    def test_a_feature_file_cucumber_never_loaded_is_finding_f2(self):
        # a narrower cucumber.features: Cucumber never parses the other files, and the run looks complete
        write(self.path("features/census.feature"), CENSUS)
        write(self.path("features/sub/doubling.feature"), DOUBLING)
        code, out = self.run_census((self.census_pickles(), []), results=6)
        self.assertEqual(1, code, out)
        self.assertIn("ACCEPTANCE F2 features/sub/doubling.feature  0 of 2 scenario(s) ran - Cucumber did not load the file",
                      out)
        self.assertIn("ACCEPTANCE F2 features/sub/doubling.feature:11  did not run  |  The price is doubled", out)
        self.assertIn("ACCEPTANCE F2 features/sub/doubling.feature:12  did not run  |  The price is doubled", out)
        self.assertIn("Acceptance census: 6 of 8 scenario(s) in 2 feature file(s) ran", out)

    def test_only_the_integrity_allowlist_accepts_f2_for_a_feature_file(self):
        write(self.path("features/census.feature"), CENSUS)
        write(self.path("features/sub/doubling.feature"), DOUBLING)
        streams = (self.census_pickles(), [])
        for allowlist, accepted in (("features/sub/doubling.feature  F2   # nightly only\n", True),
                                    ("features/**/*.feature  F2\n", True),
                                    ("features/sub/doubling.feature  F1\n", False),
                                    ("features/census.feature  F2\n", False),
                                    ("# features/sub/doubling.feature  F2\n", False)):
            with self.subTest(allowlist=allowlist):
                code, out = self.run_census(streams, allowlist=allowlist, results=6)
                if accepted:
                    self.assertIn("Acceptance census: 6 of 8 scenario(s) in 2 feature file(s) ran; 2 did not run, accepted"
                                  " by the integrity allowlist (F2)", out)
                    self.assertIn("none skipped - OK", out)
                    self.assertEqual(0, code, out)
                else:
                    self.assertIn("ACCEPTANCE F2 features/sub/doubling.feature  0 of 2", out)
                    self.assertEqual(1, code, out)

    def test_without_the_message_stream_which_scenarios_ran_is_unknown(self):
        write(self.path("features/census.feature"), CENSUS)
        write_results(self.results, [("Example #1.1", PASSED)])
        code, out = tool("no-skipped", "--results", "results", "--features", "features", "--messages", "messages",
                         "--root", ".", cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertIn("ACCEPTANCE ERROR no Cucumber message stream in messages", out)
        self.assertIn("Acceptance: FAILED - which scenarios ran is unknown without Cucumber's message stream", out)
        # Cucumber 8 without Jackson: the file is there, the run never started
        write(self.path("messages", "jvm-1.ndjson"), "")
        code, out = tool("no-skipped", "--results", "results", "--features", "features", "--messages", "messages",
                         "--root", ".", cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertIn("ACCEPTANCE ERROR cannot read the message stream messages/jvm-1.ndjson: it holds no message -"
                      " Cucumber did not start its run (Cucumber 8 writes the stream only with Jackson", out)
        self.assertNotIn("ACCEPTANCE F2", out)

    def test_a_scenario_that_ran_in_any_test_jvm_ran(self):
        # retry rounds and forks: a stream per JVM
        write(self.path("features/census.feature"), CENSUS)
        pickles = self.census_pickles()
        code, out = self.run_census((pickles[:3], pickles[3:]), (pickles[3:], pickles[:3]), results=6)
        self.assertIn("Acceptance census: 6 of 6 scenario(s) in 1 feature file(s) ran", out)
        self.assertEqual(0, code, out)

    def test_cucumber_s_own_pickles_count_where_the_tool_cannot_read_the_language(self):
        # the census reads en and ru; Cucumber knows every dialect. A file it loaded counts by its pickles; a file in
        # another language that it never loaded has unknown scenarios - finding F2, which the allowlist can accept
        write(self.path("features/rabatt.feature"), "# language: de\nFunktionalität: Rabatt\n\n  Szenario: Eins\n"
                                                    "    Angenommen ein Schritt\n")
        loaded = [(self.uri("features/rabatt.feature"), 4, "Eins")]
        code, out = self.run_census((loaded, []), results=1)
        self.assertIn("Acceptance census: 1 of 1 scenario(s) in 1 feature file(s) ran", out)
        self.assertEqual(0, code, out)
        code, out = self.run_census(([], []), results=1)
        self.assertIn("ACCEPTANCE F2 features/rabatt.feature  Cucumber listed no scenario of it (it did not load the"
                      " file, or the file defines none), and its language is not one GherkinMutator reads: which"
                      " scenarios it defines is unknown", out)
        self.assertEqual(1, code, out)

    def test_the_stop_hook_hands_the_findings_back_to_the_agent(self):
        # the hook passes on the lines of the gate it knows, then the tail of the output: the census and the run order
        # must be among the former - in gauntletFast, crapGate and dryGate still print after acceptanceCheck
        findings = ["ACCEPTANCE F2 src/acceptanceTest/resources/features/a.feature  1 of 2 scenario(s) ran",
                    "ACCEPTANCE F2 src/acceptanceTest/resources/features/a.feature:12  did not run  |  Plain one",
                    "ACCEPTANCE ERROR no Cucumber message stream in build/cucumber-messages/acceptanceTest",
                    "MUTANT ERROR    run order: c1 and z1 ran at the same time (jvm-1.ndjson: z1 started 2.000 ms before"
                    " c1 finished)"]
        output = "\n".join(["> Task :acceptanceCheck"] + findings + [f"> Task :later{n}" for n in range(40)])
        relayed = kit.stop_gate().summarize(output).split("--- end of the Gradle output ---")[0]
        for line in findings:
            self.assertIn(line, relayed)

    def test_russian_keywords_and_a_byte_order_mark(self):
        write(self.path("features/discount.feature"), "﻿" + RUSSIAN)
        code, out = self.run_census(([(self.uri("features/discount.feature"), (4, 10), "Фиксированная скидка")], []),
                                    results=1)
        self.assertIn("Acceptance census: 1 of 1 scenario(s) in 1 feature file(s) ran", out)
        self.assertEqual(0, code, out)


GLUE_IMPACT_STUBS = {
    **CUCUMBER_STUBS,
    "io/cucumber/java/Before.java": "package io.cucumber.java;\nimport java.lang.annotation.*;\n"
    "@Retention(RetentionPolicy.RUNTIME)\n@Target(ElementType.METHOD)\npublic @interface Before {\n"
    "    String value() default \"\";\n}\n",
    "io/cucumber/java/DataTableType.java": "package io.cucumber.java;\nimport java.lang.annotation.*;\n"
    "@Retention(RetentionPolicy.RUNTIME)\n@Target(ElementType.METHOD)\npublic @interface DataTableType {}\n",
    "io/cucumber/java/en/When.java": "package io.cucumber.java.en;\nimport java.lang.annotation.*;\n"
    "@Retention(RetentionPolicy.RUNTIME)\n@Target(ElementType.METHOD)\npublic @interface When {\n    String value();\n}\n",
    "io/cucumber/spring/CucumberContextConfiguration.java": "package io.cucumber.spring;\nimport java.lang.annotation.*;\n"
    "@Retention(RetentionPolicy.RUNTIME)\n@Target(ElementType.TYPE)\npublic @interface CucumberContextConfiguration {}\n",
}


class GlueImpactScope(Sandbox):
    """--glue-impact narrows scope by resolved method/field bytecode + acceptanceTest Cucumber NDJSON stream."""

    FEATURE_TEXT = (
        "Feature: {title}\n\n  Scenario Outline: Check {title}\n    When step {step} gets <val>\n"
        "    Then result is <val>\n\n    Examples:\n      | val |\n      | 10  |\n"
    )

    def compile_glue(self, out_name, sources):
        src_dir = self.path(out_name + "-src")
        cls_dir = self.path(out_name + "-classes")
        os.makedirs(cls_dir, exist_ok=True)
        java_files = []
        for rel, code in {**GLUE_IMPACT_STUBS, **sources}.items():
            p = os.path.join(src_dir, rel)
            write(p, code)
            java_files.append(p)
        r = subprocess.run(["javac", "--release", "21", "-nowarn", "-d", cls_dir, *sorted(java_files)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=kit.java_env())
        self.assertEqual(0, r.returncode, r.stdout)
        return cls_dir

    def write_acceptance_stream(self, stream_path, step_defs, hooks, param_types, feature_cases):
        lines = [{"meta": {"protocolVersion": "34.2.1"}}, {"testRunStarted": {"timestamp": stamp(0)}}]
        for sd_id, cls_name, method, params in step_defs:
            lines.append({"stepDefinition": {
                "id": sd_id,
                "pattern": {"source": method, "type": "CUCUMBER_EXPRESSION"},
                "sourceReference": {"javaMethod": {"className": cls_name, "methodName": method,
                                                   "methodParameterTypes": list(params)}},
            }})
        for h_id, cls_name, method, params in hooks:
            lines.append({"hook": {
                "id": h_id,
                "sourceReference": {"javaMethod": {"className": cls_name, "methodName": method,
                                                   "methodParameterTypes": list(params)}},
            }})
        for pt_name, ref in param_types:
            body = {"id": "pt-" + pt_name, "name": pt_name, "regularExpressions": [".*"],
                    "preferForRegularExpressionMatch": False, "useForSnippets": True}
            if ref is not None:
                cls_name, method, params = ref
                body["sourceReference"] = {"javaMethod": {"className": cls_name, "methodName": method,
                                                          "methodParameterTypes": list(params)}}
            lines.append({"parameterType": body})
        for idx, (rel_feature, step_ids, hook_ids, used_params) in enumerate(feature_cases):
            uri = pathlib.Path(self.path(rel_feature)).resolve().as_uri()
            lines.append({"pickle": {"id": f"p{idx}", "uri": uri, "name": f"sc{idx}", "steps": [], "astNodeIds": ["s1"]}})
            test_steps = [{"id": f"h-{idx}-{h}", "hookId": h,
                           "stepDefinitionIds": [], "stepMatchArgumentsLists": []} for h in hook_ids]
            arg_lists = [{"stepMatchArguments": [{"parameterTypeName": p, "group": {}} for p in used_params]}] if used_params else []
            for s in step_ids:
                ts = {"id": f"ts-{idx}-{s}", "pickleStepId": "ps1", "stepDefinitionIds": [s],
                      "stepMatchArgumentsLists": arg_lists}
                test_steps.append(ts)
            lines.append({"testCase": {"id": f"tc{idx}", "pickleId": f"p{idx}", "testSteps": test_steps}})
        write(stream_path, "".join(json.dumps(e) + "\n" for e in lines))

    def run_impact(self, base_sources, head_sources, changed_features, step_defs, hooks, param_types, feature_cases):
        for suffix, step in (("a", "A"), ("b", "B"), ("c", "C")):
            write(self.path(f"features/f_{suffix}.feature"), self.FEATURE_TEXT.format(title=suffix.upper(), step=step))
        base_cls = self.compile_glue("base", base_sources)
        head_cls = self.compile_glue("head", head_sources)
        msg_dir = self.path("acc-messages")
        self.write_acceptance_stream(os.path.join(msg_dir, "jvm-1.ndjson"), step_defs, hooks, param_types, feature_cases)
        only_file = self.path("only.nul")
        write(only_file, "".join(f + "\0" for f in changed_features))
        impact_file = self.path("impact.nul")
        write(impact_file, "\0".join([msg_dir, "--base", base_cls, "--head", head_cls]) + "\0")
        return tool("generate", "--features", "features", "--out", "mutants",
                    "--only-file", only_file, "--glue-impact", impact_file, cwd=self.dir)

    def mutated_features(self):
        manifest = read_lines(self.path("mutants", "manifest.tsv"))
        return sorted({row.split("\t")[1] for row in manifest[1:] if row and row.startswith("m")})

    def test_adding_steps_static_fields_lambdas_and_relaxing_helper_visibility_keeps_untouched_features_out(self):
        base = {
            "p/Helper.java": "package p;\npublic class Helper {\n    public int calcA(int x) { return x + 1; }\n"
                             "    public int calcB(int x) { return x + 2; }\n}\n",
            "p/SharedSteps.java": (
                "package p;\nimport io.cucumber.java.*;\nimport io.cucumber.java.en.*;\nimport java.util.*;\n"
                "public class SharedSteps {\n"
                "    private static final List<String> EXISTING = List.of(\"x\", \"y\");\n"
                "    private final Helper helper;\n"
                "    public SharedSteps(Helper helper) { this.helper = helper; }\n"
                "    @Before public void reset() {}\n"
                "    @DataTableType public Map<String, String> row(Map<String, String> r) { return r; }\n"
                "    private void publish(int v) { EXISTING.forEach(s -> { if (s.length() == v) helper.calcA(v); }); }\n"
                "    @When(\"step A gets {int}\") public void stepA(int v) { publish(helper.calcA(v)); }\n"
                "    @When(\"step B gets {int}\") public void stepB(int v) { publish(helper.calcB(v)); }\n"
                "    @Then(\"result is {int}\") public void result(int v) {}\n}\n"
            ),
        }
        head = {
            **base,
            "p/SharedSteps.java": (
                "package p;\nimport io.cucumber.java.*;\nimport io.cucumber.java.en.*;\nimport java.util.*;\n"
                "public class SharedSteps {\n"
                "    private static final Set<String> NEW_FIELDS = Set.of(\"p1\", \"p2\");\n"
                "    private static final List<String> EXISTING = List.of(\"x\", \"y\");\n"
                "    private final Helper helper;\n"
                "    public SharedSteps(Helper helper) { this.helper = helper; }\n"
                "    @Before public void reset() {}\n"
                "    @DataTableType public Map<String, String> row(Map<String, String> r) { return r; }\n"
                "    @When(\"step C gets {int}\") public void stepC(int v) {\n"
                "        NEW_FIELDS.forEach(f -> publish(v + f.length()));\n"
                "    }\n"
                "    void publish(int v) { EXISTING.forEach(s -> { if (s.length() == v) helper.calcA(v); }); }\n"
                "    @When(\"step A gets {int}\") public void stepA(int v) { publish(helper.calcA(v)); }\n"
                "    @When(\"step B gets {int}\") public void stepB(int v) { publish(helper.calcB(v)); }\n"
                "    @Then(\"result is {int}\") public void result(int v) {}\n}\n"
            ),
        }
        step_defs = [
            ("sdA", "p.SharedSteps", "stepA", ["int"]),
            ("sdB", "p.SharedSteps", "stepB", ["int"]),
            ("sdC", "p.SharedSteps", "stepC", ["int"]),
            ("sdR", "p.SharedSteps", "result", ["int"]),
        ]
        hooks = [("hReset", "p.SharedSteps", "reset", [])]
        cases = [
            ("features/f_a.feature", ["sdA", "sdR"], ["hReset"], ["int"]),
            ("features/f_b.feature", ["sdB", "sdR"], ["hReset"], ["int"]),
            ("features/f_c.feature", ["sdC", "sdR"], ["hReset"], ["int"]),
        ]
        code, out = self.run_impact(base, head, ["features/f_c.feature"], step_defs, hooks, [], cases)
        self.assertEqual(0, code, out)
        self.assertIn("glue impact narrowed scope to 1 of 3 feature file(s)", out)
        self.assertEqual(["features/f_c.feature"], self.mutated_features())
        # A changed tagged @Before hook impacts only the feature whose scenarios execute that hook
        base_tagged = {
            **base,
            "p/TaggedHooks.java": "package p;\nimport io.cucumber.java.Before;\n"
                                  "public class TaggedHooks { @Before(\"@b\") public void onlyB() { int x = 1; } }\n",
        }
        head_tagged = {
            **base_tagged,
            "p/TaggedHooks.java": "package p;\nimport io.cucumber.java.Before;\n"
                                  "public class TaggedHooks { @Before(\"@b\") public void onlyB() { int x = 2; } }\n",
        }
        hooks_tagged = hooks + [("hOnlyB", "p.TaggedHooks", "onlyB", [])]
        cases_tagged = [
            ("features/f_a.feature", ["sdA", "sdR"], ["hReset"], ["int"]),
            ("features/f_b.feature", ["sdB", "sdR"], ["hReset", "hOnlyB"], ["int"]),
            ("features/f_c.feature", ["sdA", "sdR"], ["hReset"], ["int"]),
        ]
        code2, out2 = self.run_impact(base_tagged, head_tagged, [], step_defs[:2] + [step_defs[3]],
                                      hooks_tagged, [], cases_tagged)
        self.assertEqual(0, code2, out2)
        self.assertIn("glue impact narrowed scope to 1 of 3 feature file(s)", out2)
        self.assertEqual(["features/f_b.feature"], self.mutated_features())

    def test_transitive_helper_and_polymorphic_override_include_impacted_features_only(self):
        base = {
            "p/Verifier.java": "package p;\npublic class Verifier { public int check(int x) { return x; } }\n",
            "p/StrictVerifier.java": "package p;\npublic class StrictVerifier extends Verifier {\n"
                                     "    @Override public int check(int x) { return x + 1; }\n}\n",
            "p/Steps.java": (
                "package p;\nimport io.cucumber.java.en.*;\npublic class Steps {\n"
                "    private final Verifier v = new StrictVerifier();\n"
                "    @When(\"step A gets {int}\") public void stepA(int x) {}\n"
                "    @When(\"step B gets {int}\") public void stepB(int x) { v.check(x); }\n"
                "    @When(\"step C gets {int}\") public void stepC(int x) {}\n"
                "    @Then(\"result is {int}\") public void result(int x) {}\n}\n"
            ),
        }
        head = {
            **base,
            "p/StrictVerifier.java": "package p;\npublic class StrictVerifier extends Verifier {\n"
                                     "    @Override public int check(int x) { return x + 99; }\n}\n",
        }
        step_defs = [
            ("sdA", "p.Steps", "stepA", ["int"]),
            ("sdB", "p.Steps", "stepB", ["int"]),
            ("sdC", "p.Steps", "stepC", ["int"]),
            ("sdR", "p.Steps", "result", ["int"]),
        ]
        cases = [
            ("features/f_a.feature", ["sdA", "sdR"], [], ["int"]),
            ("features/f_b.feature", ["sdB", "sdR"], [], ["int"]),
            ("features/f_c.feature", ["sdC", "sdR"], [], ["int"]),
        ]
        code, out = self.run_impact(base, head, [], step_defs, [], [], cases)
        self.assertEqual(0, code, out)
        self.assertIn("glue impact narrowed scope to 1 of 3 feature file(s)", out)
        self.assertEqual(["features/f_b.feature"], self.mutated_features())

    def test_global_context_or_removed_hook_or_changed_datatable_falls_back_to_all_features(self):
        base = {
            "p/StandConfig.java": "package p;\nimport io.cucumber.spring.CucumberContextConfiguration;\n"
                                  "@CucumberContextConfiguration\npublic class StandConfig { int port = 8080; }\n",
            "p/Steps.java": (
                "package p;\nimport io.cucumber.java.*;\nimport io.cucumber.java.en.*;\nimport java.util.*;\n"
                "public class Steps {\n"
                "    @Before public void reset() {}\n"
                "    @DataTableType public Map<String, String> row(Map<String, String> r) { return r; }\n"
                "    @When(\"step A gets {int}\") public void stepA(int x) {}\n"
                "    @Then(\"result is {int}\") public void result(int x) {}\n}\n"
            ),
        }
        step_defs = [("sdA", "p.Steps", "stepA", ["int"]), ("sdR", "p.Steps", "result", ["int"])]
        cases = [(f"features/f_{s}.feature", ["sdA", "sdR"], [], ["int"]) for s in ("a", "b", "c")]
        # 1. Context configuration changed -> all 3 features
        head_ctx = {**base, "p/StandConfig.java": base["p/StandConfig.java"].replace("8080", "9090")}
        code, out = self.run_impact(base, head_ctx, [], step_defs, [], [], cases)
        self.assertEqual(0, code, out)
        self.assertIn("glue impact affects global glue (context configuration p/StandConfig) - every feature is mutated", out)
        self.assertEqual(["features/f_a.feature", "features/f_b.feature", "features/f_c.feature"], self.mutated_features())
        # 2. Removed @Before hook -> all 3 features
        head_no_hook = {**base, "p/Steps.java": base["p/Steps.java"].replace("@Before public void reset() {}\n", "")}
        code, out = self.run_impact(base, head_no_hook, [], step_defs, [], [], cases)
        self.assertEqual(0, code, out)
        self.assertIn("removed or re-scoped hook p/Steps#reset", out)
        self.assertEqual(3, len(self.mutated_features()))


class VerifiedCache(Sandbox):
    """Per-feature verified cache (--verified-cache): saves green features even when another feature fails, skips them
    on the next run if their bytes match, and never caches kills from a broken run-order stream."""

    def write_feature(self, name, val):
        return write(
            os.path.join(self.dir, "features", name),
            f"Feature: {name}\n  Scenario Outline: S\n    When x is <v>\n    Examples:\n      | v |\n      | {val} |\n",
        )

    def test_passing_feature_is_cached_across_sibling_survivor_and_broken_order_never_caches(self):
        self.write_feature("a.feature", "10")
        self.write_feature("b.feature", "20")
        cache = os.path.join(self.dir, "cache", "env1.tsv")

        # 1. Broken run order must NOT populate verified cache even if XML says killed
        code, out = tool("generate", "--features", "features", "--out", "mutants", "--verified-cache", cache, cwd=self.dir)
        self.assertEqual(0, code, out)
        write_results(self.results, [(control_name(c), PASSED) for c in ("c1", "z1", "c2", "z2")]
                      + [(mutant_name(m), thrown(ASSERTION, "boom", (GLUE_FRAME, step_frame(4)))) for m in (1, 2)])
        # Empty messages directory -> runOrder error -> cache must remain absent
        os.makedirs(self.path("messages"), exist_ok=True)
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages",
                         "--verified-cache", cache, cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertFalse(os.path.exists(cache))

        # 2. Valid run order where a.feature (m1, c1, z1) is killed, but b.feature (m2) SURVIVES:
        #    verdict fails (exit 1), yet a.feature IS recorded in cache and b.feature is NOT
        write_results(self.results, [(control_name(c), PASSED) for c in ("c1", "z1", "c2", "z2")]
                      + [(mutant_name(1), thrown(ASSERTION, "boom", (GLUE_FRAME, step_frame(4)))), (mutant_name(2), PASSED)])
        write_messages(self.path("messages", "jvm-1.ndjson"), [
            generated("c1", 0, 5), generated("m1", 6, 10), generated("z1", 11, 15),
            generated("c2", 16, 20), generated("m2", 21, 25), generated("z2", 26, 30),
        ])
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages",
                         "--verified-cache", cache, cwd=self.dir)
        self.assertEqual(1, code, out)
        self.assertIn("MUTANT SURVIVED m2", out)
        self.assertTrue(os.path.isfile(cache))
        cached_text = kit.read(cache)
        self.assertIn("features/a.feature\t", cached_text)
        self.assertNotIn("features/b.feature\t", cached_text)

        # 3. Edit b.feature -> generate skips a.feature via cache and emits ONLY b.feature (1 mutant + 2 controls)
        self.write_feature("b.feature", "30")
        code, out = tool("generate", "--features", "features", "--out", "mutants", "--verified-cache", cache, cwd=self.dir)
        self.assertEqual(0, code, out)
        self.assertIn("verified cache matched 1 of 2 feature file(s) in scope (1 mutant(s) + 2 control(s) already verified on current runtime) - mutating 1 remaining", out)
        self.assertIn("1 mutant(s) + 2 control(s) from 1 feature file(s) in scope", out)

        # 4. Kill b.feature's mutant (now m1, c1, z1) -> verdict exits 0 and caches b.feature too
        shutil.rmtree(self.results)
        shutil.rmtree(self.path("messages"))
        write_results(self.results, [(control_name(c), PASSED) for c in ("c1", "z1")]
                      + [(mutant_name(1), thrown(ASSERTION, "boom", (GLUE_FRAME, step_frame(4))))])
        write_messages(self.path("messages", "jvm-1.ndjson"), [
            generated("c1", 0, 5), generated("m1", 6, 10), generated("z1", 11, 15),
        ])
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages",
                         "--verified-cache", cache, cwd=self.dir)
        self.assertEqual(0, code, out)
        self.assertIn("Gherkin mutation: OK", out)

        # 5. Next generate with zero edits hits all-cached.tsv (0 remaining) and verdict passes immediately
        code, out = tool("generate", "--features", "features", "--out", "mutants", "--verified-cache", cache, cwd=self.dir)
        self.assertEqual(0, code, out)
        self.assertIn("verified cache matched all 2 feature file(s) in scope (2 mutant(s) + 4 control(s) already verified on current runtime) - 0 remaining", out)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "mutants", "all-cached.tsv")))
        code, out = tool("verdict", "--mutants", "mutants", "--results", "results", "--messages", "messages",
                         "--verified-cache", cache, cwd=self.dir)
        self.assertEqual(0, code, out)
        self.assertIn("2 mutant(s) + 4 control(s) already verified on current runtime - OK", out)
        self.assertIn("Gherkin mutation: OK", out)


if __name__ == "__main__":
    unittest.main()
