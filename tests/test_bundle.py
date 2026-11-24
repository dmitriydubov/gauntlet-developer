"""The bundle as a container: manifest, byte-exact round trip, well-formed files, consistent revision marks."""
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import unittest
import xml.dom.minidom

import kit


def manifest(bundle_text):
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"^- `(.+?)` \((\d+) байт\)$", bundle_text, re.M)}


def unpacked_files(root):
    found = {}
    for directory, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            path = os.path.join(directory, name)
            found[os.path.relpath(path, root).replace(os.sep, "/")] = path
    return found


class BundleContainer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = kit.read(kit.BUNDLE)
        cls.manifest = manifest(cls.text)
        cls.files = unpacked_files(kit.kit())

    def test_manifest_lists_exactly_the_unpacked_files(self):
        self.assertEqual(sorted(self.manifest), sorted(self.files))
        self.assertEqual(len(self.manifest), 35)

    def test_manifest_sizes_are_the_sizes_on_disk(self):
        wrong = {p: (size, os.path.getsize(self.files[p])) for p, size in self.manifest.items()
                 if os.path.getsize(self.files[p]) != size}
        self.assertEqual(wrong, {}, "manifest size vs unpacked size")

    def test_bundle_has_unix_newlines_only(self):
        with open(kit.BUNDLE, "rb") as f:
            self.assertNotIn(b"\r", f.read())

    def test_builder_of_the_method_document_reproduces_the_bundle_byte_for_byte(self):
        # section 8.4 publishes the builder; rebuilding from the unpacked copy with the bundle's own header must
        # give the same bytes - a hand-edited bundle, a stale manifest or a drifted unpacker would not.
        builder = re.search(r"<<'PY'\n(import os, sys, subprocess, tempfile\n.*?)\nPY\n```", kit.read(kit.METHOD), re.S)
        self.assertIsNotNone(builder, "section 8.4 of the method document has no builder script")
        with tempfile.TemporaryDirectory() as tmp:
            script = kit.write(os.path.join(tmp, "build_bundle.py"), builder.group(1) + "\n")
            rebuilt = os.path.join(tmp, "rebuilt.md")
            first_line = self.text.split("\n", 1)[0]
            r = kit.run([sys.executable, "-I", script, kit.kit(), kit.BUNDLE, rebuilt, first_line])
            self.assertEqual(r.code, 0, r)
            with open(kit.BUNDLE, "rb") as a, open(rebuilt, "rb") as b:
                self.assertEqual(a.read(), b.read(), "the bundle is not what its own builder produces")

    def test_unpack_script_in_the_bundle_is_the_builder_s_canonical_one(self):
        builder = re.search(r"EXTRACTOR = r'''(.*?)'''", kit.read(kit.METHOD), re.S)
        self.assertEqual(kit.bundle_extractor(self.text), builder.group(1))

    def test_every_file_is_well_formed(self):
        for rel, path in sorted(self.files.items()):
            with self.subTest(file=rel):
                if rel.endswith(".py"):
                    with tempfile.TemporaryDirectory() as tmp:
                        py_compile.compile(path, cfile=os.path.join(tmp, "x.pyc"), doraise=True)
                elif rel.endswith(".sh"):
                    self.assertEqual(kit.run(["bash", "-n", path]).code, 0)
                elif rel.endswith(".json"):
                    json.loads(kit.read(path))
                elif rel.endswith(".xml"):
                    xml.dom.minidom.parseString(kit.read(path).encode("utf-8"))
                elif rel.endswith((".yml", ".yaml")):
                    self.assertNotIn("\t", kit.read(path), "a tab in YAML")
                with open(path, "rb") as f:
                    data = f.read()
                self.assertTrue(data.endswith(b"\n"), "no trailing newline")
                data.decode("utf-8")

    def test_java_tools_compile_for_the_oldest_supported_gate_jvm(self):
        # the tools run as single-file programs on the gate JVM; --release 21 is the reference stack
        with tempfile.TemporaryDirectory() as tmp:
            sources = [os.path.join(kit.kit(), "gauntlet", "tools", t + ".java") for t in kit.TOOLS]
            r = subprocess.run(["javac", "--release", "21", "-Xlint:all", "-Werror", "-d", tmp, *sources],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=kit.java_env())
            self.assertEqual(r.returncode, 0, r.stdout)


class RevisionMarks(unittest.TestCase):
    """The same revision in every document, and the changelog's size table equal to the manifest."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = kit.read(kit.BUNDLE)
        cls.method = kit.read(kit.METHOD)
        cls.readme = kit.read(os.path.join(kit.REPO, "README.md"))
        cls.changelog = kit.read(os.path.join(kit.REPO, "CHANGELOG.md"))
        cls.revision = re.match(r"# Бандл эталонного набора gauntlet \(ревизия ([\d.]+) от ([\d-]+)\)", cls.bundle)

    def test_bundle_states_its_revision(self):
        self.assertIsNotNone(self.revision, self.bundle.split("\n", 1)[0])

    def test_all_documents_name_the_same_revision(self):
        number, date = self.revision.groups()
        self.assertIn(f"Ревизия {number}, {date}", self.method)
        self.assertIn(f"**{number} ({date})**", self.readme)
        self.assertRegex(self.changelog, rf"(?m)^## Ревизия {re.escape(number)} — {date}$")

    def test_changelog_size_table_matches_the_manifest(self):
        number = self.revision.group(1)
        section = self.changelog.split(f"## Ревизия {number} ", 1)[1].split("\n## Ревизия ", 1)[0]
        table = re.findall(r"^\| `(.+?)` \| (\d+|—) \| (\d+) \|$", section, re.M)     # — : a new file
        self.assertTrue(table, "the changelog entry has no size table")
        sizes = manifest(self.bundle)
        wrong = {path: (int(new), sizes.get(path)) for path, _, new in table if sizes.get(path) != int(new)}
        self.assertEqual(wrong, {}, "changelog size vs manifest size")


if __name__ == "__main__":
    unittest.main()
