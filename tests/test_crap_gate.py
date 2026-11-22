"""CrapGate.java on synthetic JaCoCo reports: thresholds, the allowlist, and the changed-file scope."""
import os
import tempfile
import unittest

import kit

HEADER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">\n<report name="lab">\n')


def method(name, desc="()V", line=1, cc=1, covered=True):
    """A method with `cc` decision paths, fully covered or not covered at all."""
    missed, hit = (0, 10) if covered else (10, 0)
    return (f'<method name="{name}" desc="{desc}" line="{line}">'
            f'<counter type="INSTRUCTION" missed="{missed}" covered="{hit}"/>'
            f'<counter type="COMPLEXITY" missed="{0 if covered else cc}" covered="{cc if covered else 0}"/></method>')


def report(*classes):
    """classes: (binary/class/Name, source file name or None for debug=false, [methods])"""
    by_package = {}
    for name, source, methods in classes:
        package = name.rsplit("/", 1)[0] if "/" in name else ""
        attr = f' sourcefilename="{source}"' if source else ""
        by_package.setdefault(package, []).append(f'<class name="{name}"{attr}>{"".join(methods)}</class>')
    body = "".join(f'<package name="{p}">{"".join(c)}</package>' for p, c in by_package.items())
    return HEADER + body + "</report>\n"


COMPLEX = dict(cc=3, covered=False)       # CRAP = 3^2 * 1^3 + 3 = 12 > 8


class CrapCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def gate(self, xml, *args, allow=None):
        path = kit.write(os.path.join(self.dir, "jacoco.xml"), xml)
        extra = list(args)
        if allow is not None:
            extra += ["--allowlist", kit.write(os.path.join(self.dir, "allow.txt"), allow)]
        return kit.tool("CrapGate", "--report", path, *extra, cwd=self.dir)

    def source(self, rel, text, encoding="utf-8"):
        kit.write(os.path.join(self.dir, rel), text, encoding)
        return rel


class Threshold(CrapCase):

    def test_uncovered_complex_method_fails(self):
        r = self.gate(report(("a/Orders", "Orders.java", [method("total", **COMPLEX)])))
        self.assertEqual(r.code, 1, r)
        self.assertRegex(r.out, r"CRAP FAIL +12\.0 +3 +0\.0% +a\.Orders#total \(Orders\.java:1\)")

    def test_covered_method_scores_its_complexity(self):
        r = self.gate(report(("a/Orders", "Orders.java", [method("total", cc=8)])))
        self.assertEqual(r.code, 0, r)
        self.assertIn("CRAP gate: OK", r.out)

    def test_threshold_option(self):
        r = self.gate(report(("a/Orders", "Orders.java", [method("total", cc=5)])), "--threshold", "4")
        self.assertEqual(r.code, 1, r)

    def test_excluded_class_globs_cover_nested_classes(self):
        xml = report(("a/AppConfig", "AppConfig.java", [method("x", **COMPLEX)]),
                     ("a/AppConfig$Inner", "AppConfig.java", [method("y", **COMPLEX)]))
        self.assertEqual(self.gate(xml, "--exclude", "*Config").code, 0)
        self.assertEqual(self.gate(xml).code, 1)

    def test_report_with_a_doctype_is_read_offline(self):
        r = self.gate(report(("a/Orders", "Orders.java", [method("total")])))
        self.assertEqual(r.code, 0, r)

    def test_missing_report_and_bad_usage_are_input_errors(self):
        self.assertEqual(kit.tool("CrapGate", "--report", os.path.join(self.dir, "none.xml")).code, 2)
        self.assertEqual(kit.tool("CrapGate", "--nonsense", "1").code, 2)
        self.assertEqual(kit.tool("CrapGate").code, 2)


class Allowlist(CrapCase):
    ONE = report(("a/Zone", "Zone.java", [method("forCode", "(I)I", **COMPLEX)]))
    OVERLOADS = report(("a/Price", "Price.java", [method("quote", "(I)D", **COMPLEX),
                                                  method("quote", "(Ljava/lang/String;)D", line=9, **COMPLEX)]))
    LAMBDAS = report(("a/Selection", "Selection.java", [method("lambda$rules$0", "(I)Z", **COMPLEX),
                                                        method("lambda$rules$1", "(I)Z", line=7, **COMPLEX)]))

    def test_entry_is_not_cut_at_the_hash_inside_class_method(self):
        r = self.gate(self.ONE, allow="a.Zone#forCode   # one switch over the region codes\n")
        self.assertEqual(r.code, 0, r)
        self.assertIn("CRAP ALLOW", r.out)

    def test_comment_only_and_blank_lines_exempt_nothing(self):
        self.assertEqual(self.gate(self.ONE, allow="# a.Zone#forCode\n\n").code, 1)

    def test_class_wildcard(self):
        self.assertEqual(self.gate(self.OVERLOADS, allow="a.Price#*\n").code, 0)

    def test_name_only_entry_exempts_no_overload(self):
        r = self.gate(self.OVERLOADS, allow="a.Price#quote\n")
        self.assertEqual(r.code, 1, r)
        self.assertEqual(r.out.count("CRAP FAIL"), 2)
        self.assertIn("matches 2 overloads", r.out)

    def test_signature_entry_exempts_exactly_one_overload(self):
        r = self.gate(self.OVERLOADS, allow="a.Price#quote(I)D\n")
        self.assertEqual(r.code, 1, r)
        self.assertEqual(r.out.count("CRAP FAIL"), 1)
        self.assertEqual(r.out.count("CRAP ALLOW"), 1)

    def test_display_name_shared_by_sibling_lambdas_exempts_neither(self):
        r = self.gate(self.LAMBDAS, allow="a.Selection#rules::lambda\n")
        self.assertEqual(r.code, 1, r)
        self.assertEqual(r.out.count("CRAP FAIL"), 2)
        self.assertIn("sharing that display name", r.out)


class ChangedScopeWithDebugInfo(CrapCase):

    def test_only_the_changed_file_is_judged(self):
        changed = self.source("src/main/java/a/Orders.java", "package a;\nclass Orders { }\n")
        xml = report(("a/Orders", "Orders.java", [method("total")]), ("a/Legacy", "Legacy.java", [method("old", **COMPLEX)]))
        r = self.gate(xml, "--only", changed)
        self.assertEqual(r.code, 0, r)
        self.assertIn("1 method(s) analysed", r.out)

    def test_same_file_name_in_another_package_is_not_pulled_in(self):
        changed = self.source("src/main/java/com/example/prices/Catalog.java", "package com.example.prices;\nclass Catalog { }\n")
        xml = report(("com/example/prices/Catalog", "Catalog.java", [method("list")]),
                     ("prices/Catalog", "Catalog.java", [method("old", **COMPLEX)]))
        r = self.gate(xml, "--only", changed)
        self.assertEqual(r.code, 0, r)
        self.assertIn("1 method(s) analysed", r.out)

    def test_declared_package_decides_not_the_directory(self):
        changed = self.source("src/main/java/com/example/legacy/Prices.java",
                              "package com.example.domain;\nclass Prices { }\n")
        xml = report(("com/example/domain/Prices", "Prices.java", [method("fee", **COMPLEX)]))
        self.assertEqual(self.gate(xml, "--only", changed).code, 1)

    def test_unchanged_namesake_in_another_source_root_is_left_out(self):
        changed = self.source("src/main/java/a/Rules.java", "package a;\nclass CurrentRules { }\n")
        self.source("src/compat/java/a/Rules.java", "package a;\nclass CompatRules { }\n")
        xml = report(("a/CurrentRules", "Rules.java", [method("fee")]), ("a/CompatRules", "Rules.java", [method("old", **COMPLEX)]))
        r = self.gate(xml, "--only", changed, "--sources", "src/main/java,src/compat/java")
        self.assertEqual(r.code, 0, r)
        self.assertIn("1 method(s) analysed", r.out)

    def test_class_the_scan_cannot_name_stays_in_scope_without_a_namesake(self):
        # a Unicode escape in the name: the scan reads "Tarif", the class is Tarifé - never dropped on silence
        changed = self.source("src/main/java/a/Tarifs.java", "package a;\nclass Tarif\\u00e9 { }\n")
        xml = report(("a/Tarifé", "Tarifs.java", [method("fee", **COMPLEX)]))
        r = self.gate(xml, "--only", changed, "--sources", "src/main/java")
        self.assertEqual(r.code, 1, r)

    def test_nested_and_anonymous_classes_follow_their_top_level_type(self):
        changed = self.source("src/main/java/a/Outer.java", "package a;\nclass Outer { class Inner { } }\n")
        xml = report(("a/Outer$Inner", "Outer.java", [method("deep", **COMPLEX)]), ("a/Outer$1", "Outer.java", [method("run")]))
        r = self.gate(xml, "--only", changed, "--sources", "src/main/java")
        self.assertEqual(r.code, 1, r)
        self.assertIn("2 method(s) analysed", r.out)

    def test_no_changed_sources_is_an_explicit_empty_scope(self):
        r = self.gate(report(("a/Orders", "Orders.java", [method("total", **COMPLEX)])), "--only", "")
        self.assertEqual(r.code, 0, r)
        self.assertIn("nothing to check", r.out)


class ChangedScopeWithoutDebugInfo(CrapCase):
    """JavaCompile options.debug=false: JaCoCo has no sourcefilename, the changed sources name their types."""

    def test_package_private_type_in_a_file_of_another_name(self):
        changed = self.source("src/main/java/a/Selectors.java", "package a;\n@Deprecated final class Selection { }\n")
        xml = report(("a/Selection", None, [method("pick", **COMPLEX)]), ("a/Other", None, [method("x", **COMPLEX)]))
        r = self.gate(xml, "--only", changed)
        self.assertEqual(r.code, 1, r)
        self.assertIn("1 method(s) analysed", r.out)

    def test_annotation_arguments_indentation_and_unicode_names(self):
        changed = self.source("src/main/java/a/Prices.java",
                              'package a;\n  @Deprecated(since = "1.0 (preview)") final class StandardPrices { }\n'
                              "class Тариф { }\n")
        xml = report(("a/StandardPrices", None, [method("a", **COMPLEX)]),
                     ("a/Тариф", None, [method("b", **COMPLEX)]))
        r = self.gate(xml, "--only", changed)
        self.assertEqual(r.out.count("CRAP FAIL"), 2, r)

    def test_type_names_inside_comments_strings_and_bodies_are_not_declarations(self):
        changed = self.source("src/main/java/a/Real.java",
                              'package a;\n// class Ghost { }\n/* interface Phantom { } */\n'
                              'class Real { String s = "class Fake { }"; class Inner { } }\n')
        xml = report(("a/Real", None, [method("ok")]), ("a/Ghost", None, [method("x", **COMPLEX)]),
                     ("a/Fake", None, [method("y", **COMPLEX)]), ("a/Inner", None, [method("z", **COMPLEX)]))
        r = self.gate(xml, "--only", changed)
        self.assertEqual(r.code, 0, r)
        self.assertIn("1 method(s) analysed", r.out)

    def test_exact_package_and_nested_versus_top_level(self):
        changed = [self.source("src/main/java/service/Selection.java", "package service;\nclass Selection { class Legacy { } }\n"),
                   self.source("src/main/java/service/v2/Selection.java", "package service.v2;\nclass Selection { }\n")]
        xml = report(("service/Selection", None, [method("a", **COMPLEX)]),
                     ("service/Selection$Legacy", None, [method("b", **COMPLEX)]),
                     ("service/v2/Selection", None, [method("c", **COMPLEX)]),
                     ("service/Legacy", None, [method("unchanged", **COMPLEX)]))
        r = self.gate(xml, "--only", ",".join(changed))
        self.assertEqual(r.out.count("CRAP FAIL"), 3, r)
        self.assertNotIn("unchanged", r.out)

    def test_foreign_type_named_like_the_changed_file_is_not_bound(self):
        changed = self.source("src/main/java/a/Rules.java", "package a;\nclass CurrentRules { }\n")
        xml = report(("a/CurrentRules", None, [method("fee")]), ("a/Rules", None, [method("old", **COMPLEX)]))
        r = self.gate(xml, "--only", changed)
        self.assertEqual(r.code, 0, r)
        self.assertIn("1 method(s) analysed", r.out)

    def test_two_changed_files_with_one_name_and_one_declared_package(self):
        # domain/Rules.java and domain/variant/Rules.java both say `package a.domain`: neither may hide the other
        changed = [self.source("src/main/java/a/domain/Rules.java", "package a.domain;\nclass CurrentRules { }\n"),
                   self.source("src/main/java/a/domain/variant/Rules.java", "package a.domain;\nclass LegacyRules { }\n")]
        xml = report(("a/domain/CurrentRules", None, [method("fee")]), ("a/domain/LegacyRules", None, [method("quote", **COMPLEX)]))
        r = self.gate(xml, "--only", ",".join(changed))
        self.assertEqual(r.code, 1, r)
        self.assertIn("2 method(s) analysed", r.out)
        self.assertIn("a.domain.LegacyRules#quote", r.out)

    def test_zero_analysed_methods_is_called_out(self):
        changed = self.source("src/main/java/a/Empty.java", "package a;\ninterface Empty { }\n")
        r = self.gate(report(("a/Other", None, [method("x", **COMPLEX)])), "--only", changed)
        self.assertEqual(r.code, 0, r)
        self.assertIn("no source filenames (debug=false)", r.out)


class SourceEncoding(CrapCase):
    LATIN = "package a;\n/** réduit */\nclass Tarifé { }\n"

    def test_sources_are_read_with_the_given_charset(self):
        changed = self.source("src/main/java/a/Tarifs.java", self.LATIN, "iso-8859-1")
        xml = report(("a/Tarifé", None, [method("fee", **COMPLEX)]))
        r = self.gate(xml, "--only", changed, "--encoding", "ISO-8859-1")
        self.assertEqual(r.code, 1, r)
        self.assertIn("a.Tarifé#fee", r.out)

    def test_undecodable_source_is_an_input_error_that_names_the_source(self):
        changed = self.source("src/main/java/a/Tarifs.java", self.LATIN, "iso-8859-1")
        r = self.gate(report(("a/Tarifé", None, [method("fee", **COMPLEX)])), "--only", changed)
        self.assertEqual(r.code, 2, r)
        self.assertIn("cannot read the changed source", r.out)
        self.assertIn("Tarifs.java", r.out)
        self.assertNotIn("jacoco.xml", r.out)


if __name__ == "__main__":
    unittest.main()
