"""DryGate.java on synthetic CPD reports (the XML shape PMD 7.27.0 writes): the changed-file scope, the report."""
import os
import pathlib
import tempfile
import unittest
from xml.sax.saxutils import quoteattr

import kit

ORIGINAL = "src/main/java/a/Ledger.java"


def cpd(directory, *duplications):
    """duplications: [(path, path), ...] relative to `directory`, each one 18 lines / 82 tokens long."""
    xml = ['<?xml version="1.0" encoding="UTF-8"?>\n<pmd-cpd xmlns="https://pmd-code.org/schema/cpd-report" '
           'pmdVersion="7.27.0" version="1.0.0">\n']
    for paths in duplications:
        xml.append('   <duplication lines="18" tokens="82">\n')
        xml += [f'      <file line="3" endline="20" column="5" endcolumn="6" path={quoteattr(os.path.join(directory, p))}/>\n'
                for p in paths]
        xml.append("      <codefragment><![CDATA[int balance() {]]></codefragment>\n   </duplication>\n")
    return "".join(xml) + "</pmd-cpd>\n"


class ChangedScope(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def gate(self, xml, *args):
        report = kit.write(os.path.join(self.dir, "build/reports/cpd/cpd.xml"), xml)
        return kit.tool("DryGate", "--report", report, "--project-dir", self.dir, *args, cwd=self.dir)

    def only(self, *paths):
        """--only-file with these changed sources: each path ended by a NUL, as gauntlet.gradle writes the list."""
        return ["--only-file", kit.write(os.path.join(self.dir, "changed-sources"), "".join(p + "\0" for p in paths))]

    def source(self, rel):
        kit.write(os.path.join(self.dir, rel), "package a;\n")
        return rel

    def test_a_duplication_that_touches_a_changed_file_named_with_a_comma_counts(self):
        # gauntlet.gradle joined the changed sources with commas: "Ledger,Copy.java" came apart into two names of
        # nothing, the duplication was out of scope and the gate passed (review of 2c1cd0b)
        changed = self.source("src/main/java/a/Ledger,Copy.java")
        r = self.gate(cpd(self.dir, (ORIGINAL, changed)), *self.only(changed))
        self.assertEqual(r.code, 1, r)
        self.assertIn("1 duplication(s) found by CPD, 1 in scope (1 changed file(s))", r.out)

    def test_a_duplication_between_unchanged_files_is_out_of_scope(self):
        changed = self.source("src/main/java/a/Ledger,Copy.java")
        r = self.gate(cpd(self.dir, (ORIGINAL, "src/main/java/a/Other.java")), *self.only(changed))
        self.assertEqual(r.code, 0, r)
        self.assertIn("1 duplication(s) found by CPD, 0 in scope", r.out)

    def test_a_listed_path_that_names_no_file_is_an_input_error(self):
        # a list that lost its paths on the way matches no duplication: it must not pass on nothing
        self.source("src/main/java/a/Ledger,Copy.java")
        r = self.gate(cpd(self.dir, (ORIGINAL, "src/main/java/a/Ledger,Copy.java")),
                      *self.only("src/main/java/a/Ledger", "Copy.java"))
        self.assertEqual(r.code, 2, r)
        self.assertIn("the scope names no file under", r.out)

    def test_no_changed_sources_is_an_explicit_empty_scope(self):
        r = self.gate(cpd(self.dir, (ORIGINAL, "src/main/java/a/Other.java")), *self.only())
        self.assertEqual(r.code, 0, r)
        self.assertIn("nothing to check", r.out)

    def test_whole_codebase_without_a_list(self):
        r = self.gate(cpd(self.dir, (ORIGINAL, "src/main/java/a/Other.java")))
        self.assertEqual(r.code, 1, r)
        self.assertIn("1 in scope (all sources)", r.out)

    def test_a_report_with_a_doctype_is_not_read(self):
        # CPD writes its report without a DOCTYPE. The gate skipped only an external DTD: an external parameter
        # entity declared in the DOCTYPE defined an entity with a file's content, and the gate printed that as the
        # path of a duplicated file (XXE, issue #3).
        secret = kit.write(os.path.join(self.dir, "secret.txt"), "TOP-SECRET-4711")
        dtd = kit.write(os.path.join(self.dir, "evil.dtd"),
                        f'<!ENTITY % file SYSTEM "{pathlib.Path(secret).as_uri()}">\n'
                        "<!ENTITY % define \"<!ENTITY content '%file;'>\">\n%define;\n")
        xml = cpd(self.dir, ("&content;", "src/main/java/a/Other.java")).replace(
            quoteattr(os.path.join(self.dir, "&content;")), '"&content;"').replace(
            "<pmd-cpd ", f'<!DOCTYPE pmd-cpd [<!ENTITY % ext SYSTEM "{pathlib.Path(dtd).as_uri()}"> %ext;]>\n<pmd-cpd ', 1)
        r = self.gate(xml)
        self.assertEqual(r.code, 2, r)
        self.assertIn("cannot read", r.out)
        self.assertIn("DOCTYPE", r.out)
        self.assertNotIn("TOP-SECRET-4711", r.out)


if __name__ == "__main__":
    unittest.main()
