"""The guard reads perl's program the way perl does (gauntlet/hooks/guard.py, perl_writes and perl_without_patterns).

Every command of WRITES makes the real perl write - a file W appears in the scratch directory, or the file V there
changes - and the read-only reviewer must be refused it. Every command of READS only reads, and the reviewer may run
it: a match pattern is data, whatever it holds (review of 2c1cd0b: `perl -ne 'print if /`/' README.md` was refused
as a write). WRITES holds the forms that could make a pattern reader lose its place - a / after a number, a variable,
a word or a }, a / inside a string or a quote-like operator, a sigil before a quote-like word, a comment, a heredoc,
POD, two -e joined by perl - each written so that perl really runs the write.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import kit

WRITES = (
    # what writes
    "perl -e '`touch W`'",
    "perl -e 'print `touch W`'",
    'perl -e \'system("touch W")\'',
    'perl -e \'system "touch W"\'',
    "perl -e 'qx(touch W)'",
    "perl -e 'qx{touch W}'",
    'perl -e \'exec("touch W")\'',
    'perl -e \'open(F, ">", "W")\'',
    'perl -e \'open F, ">W"\'',
    'perl -e \'unlink "V"\'',
    'perl -e \'rename "V", "W"\'',
    'perl -e \'mkdir "W"\'',
    'perl -E \'system("touch W")\'',
    'perl -le \'system("touch W")\'',
    'perl -ne \'system("touch W")\' V',
    'perl \'-esystem("touch W")\'',
    'perl -e \'print 1;\' -e \'system("touch W")\'',
    # -M and -m put their text into a use line: perl runs it
    "perl '-MPOSIX;link(q{V},q{W})' /dev/null",
    "perl '-MPOSIX;unlink(q{V})' /dev/null",
    # in place: -i anywhere among the switches, also after the program or a value of -I
    "perl -pi -e 's/x/y/' V",
    "perl -i.bak -pe 's/x/y/' V",
    "perl -wpi -e 's/x/y/' V",
    "perl -Si -pe 's/x/y/' V",
    "perl -I lib -i -pe 's/x/y/' V",
    "perl -pe 's/x/y/' -i V",
    # next to a pattern, or inside one where it runs
    'perl -e \'"x" =~ /(?{ system("touch W") })/\'',
    'perl -e \'"x" =~ /(??{ system("touch W") })/\'',
    'perl -e \'"x" =~ m{(?{ system("touch W") })}\'',
    'perl -e \'"x" =~ /@{[ system("touch W") ]}/\'',
    'perl -e \'"x" =~ /${\\ system("touch W") }/\'',
    'perl -e \'"x" =~ /$x{ system("touch W") }/\'',
    'perl -e \'"x" =~ /$x[ system("touch W") ]/\'',
    'perl -e \'$_ = "x"; s/x/system("touch W")/e\'',
    'perl -e \'$_ = "x"; s{x}{system("touch W")}e\'',
    'perl -e \'$_ = "x"; s/x/q{system("touch W")}/ee\'',
    'perl -e \'$_ = "x"; s/x/@{[ system("touch W") ]}/\'',
    'perl -e \'$_ = "x"; s/x/system("touch W")/; eval\'',
    'perl -ne \'print if /x/; system("touch W")\' V',
    'perl -ne \'system("touch W") if /x/\' V',
    'perl -ne \'print if /x/ and system("touch W")\' V',
    # a division before or after the write
    'perl -e \'$a = 1 / 2; system("touch W")\'',
    'perl -e \'system("touch W"); $a = 1 / 2\'',
    'perl -e \'$a = 1 / 2; system("touch W"); $b = 3 / 4\'',
    'perl -e \'print 1 / 2; system("touch W"); print 3 / 4\'',
    'perl -e \'$a = (4) / 2; system("touch W"); print 3 / 4\'',
    'perl -e \'$b = 4; $a = $b / 2; system("touch W"); $c = $a / 4\'',
    'perl -e \'$x = 4; print $x / 2; system("touch W")\'',
    'perl -e \'$h{a} = 4; $x = $h{a} / 2; system("touch W"); /x/\'',
    'perl -e \'%if = (); print %if / 1; system("touch W"); /x/\'',
    # a / that is no pattern: inside a string, a quote-like operator, a comment, a heredoc, POD, a glob
    'perl -e \'print "x, / "; system("touch W"); print " / "\'',
    'perl -e "print \'x, / \'; system(\'touch W\'); print \' / \'"',
    'perl -e \'tr/a/(/; system("touch W"); /z/\'',
    'perl -e \'y/a/(/; system("touch W"); /z/\'',
    'perl -e \'q/(/; system("touch W"); /z/\'',
    'perl -e \'qw/(/; system("touch W"); /z/\'',
    'perl -e \'qq/(/; system("touch W"); /z/\'',
    'perl -e \'s/a/(/; system("touch W"); /z/\'',
    'perl -e \'print <( /x>; system("touch W"); print "/"\'',
    'perl -e \'print 1 # ( /\n; system("touch W"); print "/"\'',
    'perl -e \'print <<E;\n( /\nE\nsystem("touch W"); print "/"\'',
    'perl -e \'print 1;\n=pod\n( /\n=cut\nsystem("touch W"); print "/"\'',
    'perl -e \'print "( \' -e \' /"; system("touch W"); print "/"\'',
    # a word that is a name, not an operator or a keyword
    'perl -e \'sub m { system("touch W") } &m\'',
    'perl -e \'sub s {1} $x = & s/ 1; system("touch W"); //\'',
    'perl -e \'print ${/}; system("touch W"); print "/"\'',
    'perl -e \'print $$\'"\'"\' ( /\'"\'"\'; system("touch W"); print "/"\'',
    'perl -e \'print $/ ; system("touch W")\'',
    'perl -e \'$h{s} = 1; system("touch W")\'',
    'perl -e \'%h = (y => 1); system("touch W")\'',
    'perl -e \'print -s ( /x/ ); system("touch W")\'',
    # wrappers
    'env perl -e \'system("touch W")\'',
    "command perl -e '`touch W`'",
    "nice -n 5 perl -e 'qx(touch W)'",
    'echo x | xargs perl -e \'system("touch W")\'',
    'bash -c "perl -e \'system(\\"touch W\\")\'"',
    'find . -name V -exec perl -e \'system("touch W")\' \\;',
)

READS = (
    "perl -ne 'print if /`/' V",
    "perl -nle 'print if /`/' V",
    "perl -lne 'print if /`/' V",
    "perl -n -e 'print if /`/' V",
    "perl -n -l -e 'print if /`/' V",
    "perl -ne 'print unless /`/' V",
    "perl -ne 'print if m{`}' V",
    "perl -ne 'print if m/`/' V",
    "perl -ne 'print if $_ =~ /`/' V",
    "perl -lne 'print $1 if /`([^`]+)`/' V",
    "perl -pe 's/`//g' V",
    "perl -pe 's{`}{}g' V",
    "perl -pe 's/system/SYSTEM/' V",
    "perl -ne 'print if /open/' V",
    "perl -ne 'print if /system/' V",
    "perl -ne 'print if /\\bexec\\b/' V",
    "perl -ne 'print unless /link/' V",
    "perl -00 -ne 'print if /mkdir/' V",
    "perl -ne 'print if /`/ && /system/' V",
    "perl -ne 'print if /^\\s*$/ || /`/' V",
    "perl -ne 'print if !/`/' V",
    "perl -ne 'print if not /`/' V",
    "perl -E 'while (<>) { say if /`/ }' V",
    "perl -ne 'print \"$.: $_\" if /`/' V",
    "perl -lne 'print for /`(\\w+)`/g' V",
    "perl -nE 'say for grep /`/, split /\\s+/' V",
    "perl -ne 'print if /`/' V | head -5",
    "perl '-neprint if /`/' V",
    "perl -Mstrict -ne 'print if /`/' V",
    "perl -Mwarnings -lne 'print if /open/' V",
    "perl -I/usr/lib -ne 'print if /`/' V",
    "perl -e 'print \"ok\\n\"'",
)


def load_guard():
    """guard.py of the unpacked kit as a module (no bytecode is left behind in the kit)."""
    path = os.path.join(kit.kit(), "gauntlet", "hooks", "guard.py")
    spec = importlib.util.spec_from_file_location("gauntlet_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    before, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


@unittest.skipUnless(shutil.which("perl") and shutil.which("bash"), "needs perl and bash")
class PerlAgainstPerl(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.guard = load_guard()
        cls.root = tempfile.mkdtemp(prefix="gauntlet-perl-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def wrote(self, command):
        """True when the real perl changed the scratch directory: W appeared, or V changed or went away."""
        work = os.path.join(self.root, "work")
        shutil.rmtree(work, ignore_errors=True)
        kit.write(os.path.join(work, "V"), "x `code` system open\n")
        subprocess.run(["bash", "-c", command], cwd=work, timeout=60, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        v = os.path.join(work, "V")
        return os.listdir(work) != ["V"] or kit.read(v) != "x `code` system open\n"

    def refused(self, command):
        work = os.path.join(self.root, "work")
        return self.guard.command_violation("reviewer", command, self.guard.Context(work), work)

    def test_every_write_perl_makes_is_refused(self):
        for command in WRITES:
            with self.subTest(command=command):
                self.assertTrue(self.wrote(command), "the corpus is wrong: perl wrote nothing")
                self.assertIsNotNone(self.refused(command), "perl wrote, the guard let the reviewer run it")

    def test_a_match_pattern_is_data(self):
        for command in READS:
            with self.subTest(command=command):
                self.assertFalse(self.wrote(command), "the corpus is wrong: perl wrote")
                self.assertIsNone(self.refused(command), "perl only read, the guard refused it")


if __name__ == "__main__":
    unittest.main()
