"""PitSummary.java on synthetic PIT reports (the XML shape PIT 1.22.1 writes): the report it reads."""
import os
import pathlib
import tempfile
import unittest

import kit

SURVIVOR = ("<mutation detected='false' status='SURVIVED' numberOfTestsRun='1'><sourceFile>Orders.java</sourceFile>"
            "<mutatedClass>com.example.service.domain.Orders</mutatedClass><mutatedMethod>total</mutatedMethod>"
            "<methodDescription>(II)I</methodDescription><lineNumber>5</lineNumber>"
            "<mutator>org.pitest.mutationtest.engine.gregor.mutators.MathMutator</mutator><indexes><index>5</index></indexes>"
            "<blocks><block>0</block></blocks><killingTest/><description>%s</description></mutation>\n")


def mutations(*descriptions, doctype=""):
    """A mutations.xml with one surviving mutant per description; `doctype` goes where PIT writes none."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + doctype + '<mutations partial="true">\n'
            + "".join(SURVIVOR % d for d in descriptions) + "</mutations>\n")


class Report(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def summary(self, xml):
        report = kit.write(os.path.join(self.dir, "build/reports/pitest/mutations.xml"), xml)
        return kit.tool("PitSummary", "--report", report, "--max-per-file", "100",
                        "--allowlist", os.path.join(self.dir, "gauntlet/config/pit-runerror-allowlist.txt"), cwd=self.dir)

    def test_a_report_with_a_doctype_is_not_read(self):
        # PIT writes mutations.xml without a DOCTYPE. One in the report declared an external entity, and the summary
        # printed the file it named as the description of a surviving mutant (XXE, issue #3).
        secret = kit.write(os.path.join(self.dir, "secret.txt"), "TOP-SECRET-4711")
        doctype = f'<!DOCTYPE mutations [<!ENTITY leak SYSTEM "{pathlib.Path(secret).as_uri()}">]>\n'
        r = self.summary(mutations("&leak;", doctype=doctype))
        self.assertEqual(r.code, 2, r)
        self.assertIn("cannot read", r.out)
        self.assertIn("DOCTYPE", r.out)
        self.assertNotIn("TOP-SECRET-4711", r.out)
        # the report as PIT writes it is read as before
        r = self.summary(mutations("replaced integer addition with subtraction"))
        self.assertEqual(r.code, 0, r)
        self.assertIn("SURVIVED    com.example.service.domain.Orders:5 total() - replaced integer addition with "
                      "subtraction [MathMutator]", r.out)


if __name__ == "__main__":
    unittest.main()
