#!/usr/bin/env python3
"""Regression suite of the Gauntlet distribution itself (it is not part of the bundle).

    python3 tests/run.py              # everything that needs only python3, git, bash and a JDK 21+ (about 2 min)
    python3 tests/run.py --fast       # skip the hooks' own selftest (the slow part)
    python3 tests/run.py --gradle     # also the real-Gradle scenarios (Gradle 8.14+, Maven Central; several minutes)
    python3 tests/run.py -k crap      # only the tests whose id contains "crap"

The suite never tests a working copy: it unpacks gauntlet-kit-bundle.md with the script published in the
bundle's own header and tests that copy, so what is green here is what a user of the bundle gets.
Exit code 0 = all green.
"""
import argparse
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402  (after the path is set)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fast", action="store_true", help="skip gauntlet/hooks/selftest.py")
    ap.add_argument("--gradle", action="store_true", help="run the real-Gradle scenarios too")
    ap.add_argument("-k", dest="pattern", default="", help="run only tests whose id contains this text")
    ap.add_argument("-v", "--verbose", action="store_true")
    opts = ap.parse_args()

    root = tempfile.mkdtemp(prefix="gauntlet-kit-tests-")
    try:
        unpacked = kit.unpack(kit.BUNDLE, os.path.join(root, "kit"))
        classes = kit.compile_tools(unpacked, os.path.join(root, "classes"))
        os.environ.update(GAUNTLET_REPO=kit.REPO, GAUNTLET_KIT=unpacked, GAUNTLET_CLASSES=classes)
        os.environ.setdefault("LC_ALL", "C.UTF-8")
        if opts.fast:
            os.environ["GAUNTLET_SKIP_SELFTEST"] = "1"
        if opts.gradle:
            os.environ["GAUNTLET_E2E"] = "1"
        suite = unittest.defaultTestLoader.discover(HERE, pattern="test_*.py", top_level_dir=HERE)
        if opts.pattern:
            suite = unittest.TestSuite(t for t in flatten(suite) if opts.pattern.lower() in t.id().lower())
        result = unittest.TextTestRunner(verbosity=2 if opts.verbose else 1).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


if __name__ == "__main__":
    sys.exit(main())
