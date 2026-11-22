"""The guard reads a command line the way bash does (gauntlet/hooks/guard.py, shell_code and the scanners).

Every command of the corpus uses two programs: `M <n>` is a command the guard must see whenever bash runs it,
`D <n>` is text that bash never runs - a comment, a heredoc body, a quoted word - and that the guard must never
take for a command. Each command is executed by the real bash and read by the hook; the two sets are compared.
Known residual, not in the corpus: a shell function defined in the same command that runs its arguments
(`f() { "$@"; }; f bash <<EOF ...`) - the hook cannot know what the function does.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import kit

CORPUS = (
    # comments
    'M 1 # D 2\nM 3',
    "# don't D 1\nM 2",
    "M 1 # it's D 2\nM 3; echo 'x'",
    'echo a#b; M 1',
    'echo "a # b"; M 1',
    'echo $# ; M 1',
    'x=abc; echo ${#x}; M 1',
    'x=abc; echo ${x#a}; M 1',
    'M 1;# D 2\nM 3',
    '(M 1 # D 2\n)\nM 3',
    'echo $(M 1 # D 2\n)\nM 3',
    'echo \\# D 1; M 2',
    "echo '#' x; M 2",
    'echo a; #!/bin/bash D 1\nM 2',
    'M 1 2>&1 | cat #D 2',
    'echo a >/dev/null # D 1\nM 2',
    # heredocs
    'cat <<EOF\nD 1\nEOF\nM 2',
    "cat <<'EOF'\nD 1 don't\nEOF\nM 2",
    'cat <<-EOF\n\tD 1\n\tEOF\nM 2',
    'cat <<EOF; M 1\nD 2\nEOF\nM 3',
    'cat <<A; cat <<B\nD 1\nA\nD 2\nB\nM 3',
    'cat <<EOF\n$(M 1)\nEOF',
    "cat <<'EOF'\n$(D 1)\nEOF\nM 2",
    'cat <<EOF\n`M 1`\nEOF',
    'bash <<EOF\nM 1\nEOF',
    "bash <<'EOF'\nM 1 # D 2\nM 3\nEOF",
    'bash -s <<EOF\nM 1\nEOF',
    'cat <<EOF | bash\nM 1\nEOF',
    "cat <<'EOF' |\nM 1\nEOF\nbash",
    'x=$(cat <<EOF\nD 1\nEOF\n); M 2',
    'echo "$(cat <<\'EOF\'\nD 1 "quote\nEOF\n)"; M 2',
    'echo "$(cat <<\'EOF\'\nD 1 )paren\nEOF\n)" && M 2',
    "cat <<EOF\nD 1\nEOF\n# don't D 2\nM 3",
    'echo "x << y"\nM 1',
    'echo $((1<<2))\nM 1',
    '(( x = 1 << 2 ))\nM 1',
    'cat <<"EOF"\nD 1 $(D 2)\nEOF\nM 3',
    'cat <<\\EOF\nD 1 $(D 2)\nEOF\nM 3',
    "python3 - <<'EOF'\nimport subprocess\nsubprocess.run(['M','1'])\nEOF",
    "python3 <<'EOF'\nimport os\nos.system('M 1')\nEOF",
    '(cat <<EOF)\nD 1\nEOF\nM 2',
    'cat <<EOF >/dev/null\nD 1\nEOF\nM 2',
    'cat <<EOF\nD 1\nEOF',
    'bash <<EOF\nM 1\nEOF\nM 2',
    'if true; then cat <<EOF\nD 1\nEOF\nfi; M 2',
    'while read l; do M 1; done <<EOF\nD 2\nEOF',
    'cat <<EOF1 <<EOF2\nD 1\nEOF1\nD 2\nEOF2\nM 3',
    "cat <<EOF | python3\nimport os\nos.system('M 1')\nEOF",
    'x=$(cat <<EOF)\nD 1\nEOF\nM 2',
    "cat <<EOF\nit's D 1\nEOF\nM 2; echo 'x'",
    "cat > /dev/null <<EOF\ndon't D 1\nEOF\nM 2",
    'env X=1 bash <<EOF\nM 1\nEOF',
    # continuations
    'M \\\n1',
    'echo a \\\n; M 1',
    'echo "a\\\nb"; M 1',
    "echo 'a\\\nD 9'; M 1",
    'echo x \\\n# D 1\nM 2',
    'M 1 \\\n  && M 2',
    'echo a\\\\\nM 1',
    # case
    'case a in a) M 1 ;; b) M 2 ;; esac; M 3',
    'case a in (a) M 1 ;; esac; M 2',
    'case a in a|b) M 1 ;; *) M 2 ;; esac',
    'case a in\n  a)\n    M 1\n    ;;\n  *)\n    M 2\n    ;;\nesac\nM 3',
    'x=$(case a in a) M 1 ;; esac); M 2',
    'echo "$(case a in a) M 1; echo \')\' ;; esac)"; M 2',
    'case a in a) (cd /tmp; M 1) ;; esac; M 2',
    'case a in a) case b in b) M 1 ;; esac ;; esac; M 2',
    'f() { case $1 in a) M 1 ;; esac; }; f a; M 2',
    'for x in a b; do case $x in a) M 1 ;; b) M 2 ;; esac; done',
    'case a in a) M 1 ;& b) M 2 ;; esac',
    'echo case in point; M 1',
    'case "a b" in "a b") M 1 ;; esac',
    'case a in a) M 1 # D 2\n;; esac',
    'case a in a) cat <<EOF\nD 1\nEOF\n;; esac; M 2',
    'case a in a) echo ")" ; M 1 ;; esac',
    'case a in esac; M 1',
    'case a in a) M 1; esac; M 2',
    'case a in [ab]) M 1 ;; esac',
    'case $(M 1) in *) M 2 ;; esac',
    'case x in $(M 1)) M 2 ;; *) M 3 ;; esac',
    'case a in\n# D 1\n a) M 2 ;;\nesac',
    'if true; then case a in a) M 1 ;; esac; fi; M 2',
    'true && case a in a) M 1 ;; esac',
    'case a in a) M 1 ;; esac | cat; M 2',
    '( case a in a) M 1 ;; esac ); M 2',
    'case a in b) M 1 ;; a) ( case c in c) M 2 ;; esac ) ;; esac; M 3',
    # others
    'echo `M 1`',
    'echo $(echo $(M 1))',
    'echo "$(M 1)" \'$(D 2)\'',
    'M 1 | cat; M 2 || M 3; M 4 && M 5',
    '{ M 1; }; (M 2); M 3 &\nwait',
    'diff <(M 1) <(M 2) >/dev/null; M 3',
    "bash -c 'M 1; M 2 # D 3'",
    'bash -c "M 1 # D 2\nM 3"',
    'eval "M 1; M 2"',
    "echo 'M 1' | bash",
    'echo "it\'s"; M 1',
    "echo $'it\\'s D 1'; M 2",
    'arr=(a b); M 1',
    'echo ${x:-$(M 1)}',
    '[[ a == a ]] && M 1',
    "x='multi\nline # D 1'; M 2",
    "sh -c 'M 1' # D 2",
    "bash <<< 'M 1'",
    'bash <<< "M 1; M 2"',
    "cat <<< 'M 1' | bash",
    'python3 -c "import os; os.system(\'M 1\')"',
    'echo "print(1)" | python3; M 1',
    'printf \'import os\\nos.system("M 1")\\n\' | python3',
    'time M 1',
    '! M 1',
    'if M 1; then M 2; else M 3; fi',
    'wc -l <<< "D 1"; M 2',
    'cat <<< "$(M 1)"',
    "bash -c 'cat <<EOF\nD 1\nEOF\nM 2'",
    "bash -c 'bash <<EOF\nM 1\nEOF'",
    'echo "a"#b; M 1',
    'echo a # b \\\nM 1',
    # ANSI-C strings: bash decodes them before anything runs
    "bash -c $'M 1\\nM 2'",
    "$'M' 1",
    "bash <<< $'M 1'",
    "eval $'M 1; M 2'",
    "bash -c $'M\\x201'",
    "bash -c $'\\115 1'",
    "echo $'D 1\\x27'; M 2",
    "echo $'a\\\\'; M 1",
    "echo $'\\'D 1\\''; M 2",
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


def seen(guard, text, found, depth=0):
    """Markers the hook takes for commands: in the line itself and in every piece of code it descends into."""
    if depth > 8:
        return found
    code = guard.shell_code(text)
    for segment in guard.split_shell(code):
        if segment in ("(", ")"):
            continue
        words = guard.words_of(segment)
        if len(words) > 1 and words[0] in ("M", "D"):
            found.add(words[0] + words[1])
        nested = guard.shell_payloads(words) + guard.stdin_programs(segment)
        if words:
            nested += guard.inline_code_strings(os.path.basename(words[0]), words[1:])
        for inner in nested:
            if inner != text:
                seen(guard, inner, found, depth + 1)
    for inner in guard.piped_shell_code(code) + guard.command_substitutions(code):
        if inner != text:
            seen(guard, inner, found, depth + 1)
    return found


@unittest.skipUnless(shutil.which("bash") and shutil.which("python3"), "needs bash and python3")
class ReaderAgainstBash(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.guard = load_guard()
        cls.root = tempfile.mkdtemp(prefix="gauntlet-reader-")
        os.makedirs(os.path.join(cls.root, "bin"))
        os.makedirs(os.path.join(cls.root, "work"))
        for name in ("M", "D"):
            path = os.path.join(cls.root, "bin", name)
            kit.write(path, "#!/bin/sh\nprintf '%s%s\\n' " + name + ' "$1" >> "$GAUNTLET_MARKERS"\n')
            os.chmod(path, 0o755)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def executed(self, command):
        log = os.path.join(self.root, "markers")
        open(log, "w").close()
        env = dict(os.environ, PATH=os.path.join(self.root, "bin") + os.pathsep + os.environ["PATH"],
                   GAUNTLET_MARKERS=log)
        subprocess.run(["bash", "-c", command], cwd=os.path.join(self.root, "work"), env=env, timeout=60,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return set(kit.read(log).split())

    def test_whatever_bash_runs_the_guard_sees_and_data_is_never_a_command(self):
        for command in CORPUS:
            with self.subTest(command=command):
                ran, found = self.executed(command), seen(self.guard, command, set())
                self.assertEqual(sorted(m for m in ran if m.startswith("D")), [], "the corpus is wrong: bash ran data")
                self.assertEqual(sorted(ran - found), [], "bash ran it, the guard did not see it")
                self.assertEqual(sorted(m for m in found if m.startswith("D")), [], "data taken for a command")

    def test_the_corpus_exercises_bash(self):
        ran = set()
        for command in CORPUS:
            ran |= self.executed(command)
        self.assertGreater(len(ran), 4)

    def test_reading_its_own_output_changes_nothing(self):
        for command in CORPUS:
            with self.subTest(command=command):
                once = self.guard.shell_code(command)
                self.assertEqual(self.guard.shell_code(once), once)

    def test_a_reader_failure_leaves_the_raw_command(self):
        self.assertEqual(self.guard.shell_code(None), None)

    def test_an_ansi_c_string_that_is_never_closed_stays_as_written(self):
        # bash runs nothing of it; the reader keeps every character instead of guessing a word
        for command in ("echo $'abc", "echo $'ab\\'", "ls; echo $'x\\'"):
            with self.subTest(command=command):
                self.assertEqual(self.guard.shell_code(command), command)


if __name__ == "__main__":
    unittest.main()
