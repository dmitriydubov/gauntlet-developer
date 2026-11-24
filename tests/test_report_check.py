"""gauntlet/tools/report_check.py: the mechanical check of a subagent report (gauntlet/subagents.md, 2.2 and 3).

A coordinator that spot-checks one claim of a report catches a faked one with probability about 1/k. The tool checks
every quote against the file at the report's revision and, with --run, re-runs every command it can prove read-only
and compares the exit code and the quoted output lines; anything it cannot prove read-only it refuses to re-run and
says why. These tests build a small git repository, write reports against it and check that genuine evidence passes,
fabricated evidence fails, the shape of section 3 is enforced, the allowlist accepts and rejects what it should, a
re-run leaves the repository byte for byte as it was, and the SubagentStop hook sends a bad report back twice and
then lets the subagent stop.
"""
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

import kit

ORDER = """package shop;

class Order {
    int total(int a, int b) {
        return a + b;
    }
}
"""
# a line that itself holds "» «": the groups of a quote are split there and merged back when only that matches
RULE = "Причины: «нет доступа» «вне карточки» и «исчерпан бюджет».\nДругих нет.\n"
LIST = "b\na\nb\nb\n"
GENUINE_FILE = ("   - файл: `src/Order.java:4` «int total(int a, int b) {» «return a + b;»")
REFUTED = "   - опровергло бы: другой метод считает сумму; проверено: `src/Order.java:5` → «return a + b;»"


def tool():
    path = os.path.join(kit.kit(), "gauntlet", "tools", "report_check.py")
    assert os.path.isfile(path), f"the kit has no gauntlet/tools/report_check.py: {path}"
    return path


_module = {}


def module():
    """report_check.py imported (for the allowlist table) without leaving bytecode in the kit."""
    if "m" not in _module:
        spec = importlib.util.spec_from_file_location("report_check", tool())
        m = importlib.util.module_from_spec(spec)
        saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(m)
        finally:
            sys.dont_write_bytecode = saved
        _module["m"] = m
    return _module["m"]


def report(rev, claims, unchecked=("- Живой прогон сборки — вне карточки — сборку гоняет сессия задачи",),
           coverage="2 из 2", tail=("- вопросов нет",), header=None, sections=None):
    """A section-3 report: the header, the five sections, the given claims and «Не проверено» items."""
    header = header or f"## Карточка 4.1, карта кода; ревизия {rev}; модель test-model, max; лимит среды: не достигнут"
    parts = {"Итог": ["Сумма считается в одном месте."],
             "Проверено": list(claims),
             "Найдено сверх карточки": [],
             "Не проверено": list(unchecked),
             "Вопросы и риски для координатора": list(tail)}
    lines = [header]
    for name in sections or ["Итог", "Проверено", "Найдено сверх карточки", "Не проверено",
                             "Вопросы и риски для координатора"]:
        title = f"Проверено (покрытие: {coverage} по чек-листу; сверх карточки: 0)" if name == "Проверено" else name
        lines.append("## " + title)
        lines += parts[name]
    return "\n".join(lines) + "\n"


def tree_digest(root):
    """Every byte and every name under the directory, .git included: a re-run must change nothing."""
    h = hashlib.sha256()
    for base, dirs, files in sorted(os.walk(root)):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            h.update(os.path.relpath(path, root).encode())
            st = os.lstat(path)
            h.update(str(st.st_mtime_ns).encode())
            with open(path, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="report-check-test-")
        self.repo = os.path.join(self.tmp, "repo")
        kit.write(os.path.join(self.repo, "src", "Order.java"), ORDER)
        kit.write(os.path.join(self.repo, "docs", "rule.md"), RULE)
        kit.write(os.path.join(self.repo, "data", "list.txt"), LIST)
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.commit("base")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.counter = 0

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        r = subprocess.run(["git", *args], cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout

    def commit(self, message):
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", message)

    def check(self, text, *args, cwd=None):
        """(exit code, stdout, stderr) of report_check.py on the report text (written outside the repository)."""
        self.counter += 1
        path = kit.write(os.path.join(self.tmp, f"report-{self.counter}.md"), text)
        r = subprocess.run([sys.executable, tool(), "--repo", self.repo, *args, path], cwd=cwd or self.tmp,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        return r.returncode, r.stdout, r.stderr

    def assert_code(self, result, code, *needles):
        self.assertEqual(result[0], code, result[1] + result[2])
        for needle in needles:
            self.assertIn(needle, result[1] + result[2])

    def claim(self, number, body, cls="гарантия", evidence=(GENUINE_FILE,)):
        return [f"{number}. {body} [{cls}]", *evidence]


class QuoteTest(Base):
    def test_genuine_quotes_pass(self):
        claims = self.claim(1, "Сумма считается в total", "гарантия, несущее", (GENUINE_FILE, REFUTED)) + \
            self.claim(2, "Правило называет три причины", "гарантия",
                       ("   - файл: `docs/rule.md:1` «Причины: «нет доступа» «вне карточки» и «исчерпан бюджет».» "
                        "«Других нет.»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 3", "расхождений нет")

    def test_fabricated_quote_fails(self):
        claims = self.claim(1, "Сумма считается с налогом", evidence=(
            "   - файл: `src/Order.java:5` «return a + b + tax;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "РАСХОЖДЕНИЕ src/Order.java:5", "цитаты нет")

    def test_quote_of_two_lines_in_one_group_fails(self):
        # each group is one source line: two lines glued into one group are not a quote of any line
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:4` «int total(int a, int b) { return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "РАСХОЖДЕНИЕ")

    def test_shift_of_two_lines_is_a_correction(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:3` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "ПОПРАВКА src/Order.java:3",
                         "цитата на строке 5, а не 3")

    def test_shift_of_three_lines_is_a_mismatch(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:2` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "цитата есть на строке 5, а не 2")

    def test_groups_must_be_consecutive_lines(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:3` «class Order {» «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "РАСХОЖДЕНИЕ")

    def test_quote_is_read_at_the_revision_not_from_the_working_tree(self):
        kit.write(os.path.join(self.repo, "src", "Order.java"), ORDER.replace("a + b", "a - b"))
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:5` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")
        self.assert_code(self.check(report("«рабочее дерево»", claims)), 1, "цитаты нет в файле")

    def test_missing_file_is_a_mismatch(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Missing.java:1` «class Missing»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "нет файла src/Missing.java")

    def test_omission_inside_a_group_and_whitespace_do_not_count(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:4` «int   total(int a, … {»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")

    def test_file_outside_the_repository_is_read_on_disk(self):
        outside = kit.write(os.path.join(self.tmp, "vendor", "CHANGELOG.md"), "# 1.2\n- Added auto mode\n")
        claims = self.claim(1, "Режим добавлен в 1.2", evidence=(f"   - файл: `{outside}:2` «- Added auto mode»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")
        claims = self.claim(1, "Режим добавлен в 1.2", evidence=(f"   - файл: `{outside}:2` «- Added manual mode»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "вне репозитория, прочитан с диска")

    def test_fenced_examples_are_not_evidence_or_sections(self):
        tail = ("Пример формата:", "```", "## Итог", "   - файл: `src/Order.java:1` «выдумано»", "```")
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), tail=tail)), 0, "Цитаты: 1;")

    def test_refutation_quote_is_checked_too(self):
        claims = self.claim(1, "Сумма", "гарантия, несущее", (GENUINE_FILE, REFUTED.replace("a + b", "a * b")))
        self.assert_code(self.check(report(self.sha, claims)), 1, "опровергло бы", "РАСХОЖДЕНИЕ src/Order.java:5")

    def test_rev_option_checks_another_revision(self):
        kit.write(os.path.join(self.repo, "src", "Order.java"), ORDER.replace("a + b", "b + a"))
        self.git("add", "-A")
        self.commit("swap")
        moved = self.git("rev-parse", "HEAD").strip()
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:5` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0)
        self.assert_code(self.check(report(self.sha, claims), "--rev", moved), 1, "цитаты нет")
        self.assert_code(self.check(report(self.sha, claims), "--rev", "no-such-revision"), 2, "--rev no-such-revision")

    def test_unknown_revision_in_the_header_fails(self):
        claims = self.claim(1, "Сумма")
        self.assert_code(self.check(report("0123456789abcdef0123456789abcdef01234567", claims)), 1,
                         "ревизии 0123456789abcdef0123456789abcdef01234567 нет")


class ShapeTest(Base):
    def test_missing_header_fails(self):
        text = report(self.sha, self.claim(1, "Сумма")).split("\n", 1)[1]
        self.assert_code(self.check(text), 1, "нет шапки")

    def test_header_without_revision_fails(self):
        header = "## Карточка 4.1, карта кода; модель test-model, max; лимит среды: не достигнут"
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), header=header)), 1, "нет ревизии")

    def test_missing_section_fails(self):
        text = report(self.sha, self.claim(1, "Сумма"), sections=["Итог", "Проверено", "Найдено сверх карточки",
                                                                 "Вопросы и риски для координатора"])
        self.assert_code(self.check(text), 1, "нет раздела «## Не проверено»")

    def test_sections_out_of_order_fail(self):
        text = report(self.sha, self.claim(1, "Сумма"), sections=["Итог", "Не проверено", "Проверено",
                                                                 "Найдено сверх карточки",
                                                                 "Вопросы и риски для координатора"])
        self.assert_code(self.check(text), 1, "не на своём месте")

    def test_extra_section_fails(self):
        text = report(self.sha, self.claim(1, "Сумма")).replace("## Найдено сверх карточки",
                                                                "## Таблица\n## Найдено сверх карточки")
        self.assert_code(self.check(text), 1, "лишний раздел «## Таблица»")

    def test_claim_without_class_fails(self):
        text = report(self.sha, ["1. Сумма считается в total", GENUINE_FILE])
        self.assert_code(self.check(text), 1, "у утверждения 1 нет класса")

    def test_claim_without_evidence_fails(self):
        text = report(self.sha, ["1. Сумма считается в total [гарантия]"])
        self.assert_code(self.check(text), 1, "у утверждения 1 нет доказательства")

    def test_load_bearing_claim_without_refutation_fails(self):
        text = report(self.sha, self.claim(1, "Сумма", "гарантия, несущее"))
        self.assert_code(self.check(text), 1, "утверждение 1 несущее, а строки «- опровергло бы")

    def test_refutation_without_checked_part_fails(self):
        text = report(self.sha, self.claim(1, "Сумма", "риск, несущее",
                                           (GENUINE_FILE, "   - опровергло бы: другой метод")))
        self.assert_code(self.check(text), 1, "без «; проверено:")

    def test_no_time_is_not_a_reason(self):
        text = report(self.sha, self.claim(1, "Сумма"), unchecked=("- Прогон сборки — нет времени — сборка",))
        self.assert_code(self.check(text), 1, "«нет времени» - не причина")

    def test_obvious_is_not_a_reason(self):
        text = report(self.sha, self.claim(1, "Сумма"), unchecked=("- Остальные вызовы — и так ясно — ничем",))
        self.assert_code(self.check(text), 1, "«и так ясно» - не причина")

    def test_allowed_reasons_pass(self):
        unchecked = ("- Прогон сборки — нет доступа: команда gradle не найдена — сборка не проверена",
                     "- Кэш — вне карточки — без риска", "- Пункт 7 — исчерпан бюджет (1 пункт) — вызовы")
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), unchecked=unchecked,
                                           coverage="1 из 2")), 0)

    def test_coverage_numbers(self):
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), coverage="3 из 2")), 1,
                         "N больше M")
        text = report(self.sha, self.claim(1, "Сумма")).replace("(покрытие: 2 из 2 по чек-листу; сверх карточки: 0)",
                                                               "(все пункты)")
        self.assert_code(self.check(text), 1, "нет «покрытие: N из M")
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), coverage="1 из 2", unchecked=())), 1,
                         "покрытие 1 из 2 неполное, а «Не проверено» пусто")

    def test_text_outside_claims_fails(self):
        text = report(self.sha, ["Все вызовы найдены.", *self.claim(1, "Сумма")])
        self.assert_code(self.check(text), 1, "текст в «Проверено» вне утверждений")

    def test_command_without_exit_code_fails(self):
        text = report(self.sha, self.claim(1, "Сумма", evidence=("   - команда: `wc -l src/Order.java` → «7»",)))
        self.assert_code(self.check(text), 1, "без кода выхода")


class AllowlistTest(unittest.TestCase):
    """runnable(): which reported commands may be re-run, and why the others may not."""

    ACCEPTED = [
        "git grep -n total", "git show HEAD:src/Order.java", "git log --oneline -3", "git ls-files",
        "git rev-parse HEAD", "git rev-parse --git-dir", "git cat-file -p HEAD", "git blame -L 5,5 src/Order.java", "git status --porcelain",
        "git grep --text -c x", "grep -rn 'a + b' src", "egrep -c 'a|b' data/list.txt", "fgrep -c b data/list.txt",
        "rg -n --pretty total src", "find . -name Order.java", "wc -l src/Order.java", "ls -la src",
        "cat data/list.txt", "head -n 3 src/Order.java", "tail -n 2 src/Order.java", "sed -n '4,5p' src/Order.java",
        "sed -n 4p src/Order.java", "sort -r data/list.txt", "uniq -c data/list.txt", "javap -p -cp build Order",
        "grep -c '$x' data/list.txt", "git log '@{u}'"]
    REJECTED = {
        # git: only the read-only subcommands, no global options, nothing that writes, runs a program or a pager
        "git grep -O total": "-O открывает пейджер",
        "git grep -nOless total": "-O открывает пейджер",
        "git grep --open-files-in-pager total": "пишет файл или запускает",
        "git grep --open total": "пишет файл или запускает",
        "git log -p --output=/tmp/x": "пишет файл или запускает",
        "git log -p --outp=/tmp/x": "пишет файл или запускает",
        "git show --ext-diff HEAD": "пишет файл или запускает",
        "git grep --textconv x": "пишет файл или запускает",
        "git cat-file --filters HEAD:x": "пишет файл или запускает",
        "git log --show-signature": "пишет файл или запускает",
        "git log --format=%GS": "gpg",
        "git log '--format=%G?'": "gpg",
        "git log --format=%G?": "шаблон имён файлов «?»",
        "git log --exec=x": "пишет файл или запускает",
        "git -c core.pager=x log": "глобальная опция git",
        "git -C /tmp log": "глобальная опция git",
        "git --exec-path=/tmp log": "глобальная опция git",
        "git commit -m x": "не из списка подкоманд",
        "git checkout -- src": "не из списка подкоманд",
        "git config core.pager x": "не из списка подкоманд",
        # rg: a preprocessor, decompression programs, a hostname program
        "rg --pre cat total": "запускает программу",
        "rg --pre=cat total": "запускает программу",
        "rg --pre-glob '*' total": "запускает программу",
        "rg --search-zip total": "запускает программу",
        "rg -z total": "запускает программу",
        "rg -nz total": "запускает программу",
        "rg --hostname-bin=x total": "запускает программу",
        # find: actions that run, delete or write
        "find . -exec rm {} ;": "оператор оболочки «;»",
        "find . -exec rm {} \\;": "действие find «-exec»",
        "find . -execdir ls \\;": "действие find «-execdir»",
        "find . -ok rm \\;": "действие find «-ok»",
        "find . -okdir rm \\;": "действие find «-okdir»",
        "find . -delete": "действие find «-delete»",
        "find . -fprint out": "действие find «-fprint»",
        "find . -fprint0 out": "действие find «-fprint0»",
        "find . -fprintf out %p": "действие find «-fprintf»",
        "find . -fls out": "действие find «-fls»",
        # sed: only -n '<a>,<b>p' <file>
        "sed -n '1p;w x' src/Order.java": "sed повторяется только",
        "sed -n '1w x' src/Order.java": "sed повторяется только",
        "sed -n 1e src/Order.java": "sed повторяется только",
        "sed -i 1d src/Order.java": "sed повторяется только",
        "sed -ni 1p src/Order.java": "sed повторяется только",
        "sed -n 1p -i": "sed повторяется только",
        "sed -n 1p src/Order.java data/list.txt": "sed повторяется только",
        # sort: an output file, a temporary directory, a compression program (GNU accepts abbreviations)
        "sort -o out data/list.txt": "опция sort",
        "sort -ro out data/list.txt": "опция sort",
        "sort --output=out data/list.txt": "опция sort",
        "sort --out=out data/list.txt": "опция sort",
        "sort -T /tmp data/list.txt": "опция sort",
        "sort --temporary-directory=/tmp data/list.txt": "опция sort",
        "sort --compress-program=gzip data/list.txt": "опция sort",
        # uniq: a second operand is the output file
        "uniq data/list.txt out": "uniq со вторым аргументом",
        "uniq -c - out": "uniq со вторым аргументом",
        # tail that never ends, javap that runs JVM agents or reads argument files or the network
        "tail -f src/Order.java": "не кончается",
        "tail --follow=name src/Order.java": "не кончается",
        "javap -J-javaagent:x.jar Order": "передаёт флаг JVM",
        "javap @args": "файл аргументов",
        "javap http://example.com/X.class": "ходит в сеть",
        # the shell: operators, redirections, substitutions, globs, comments, expansions
        "grep -c x data/list.txt | wc -l": "оператор оболочки «|»",
        "grep -c x data/list.txt > out": "оператор оболочки «>»",
        "grep -c x data/list.txt >> out": "оператор оболочки «>»",
        "grep -c x < data/list.txt": "оператор оболочки «<»",
        "grep -c x data/list.txt; rm -rf src": "оператор оболочки «;»",
        "grep -c x data/list.txt && rm src": "оператор оболочки «&»",
        "grep -c x data/list.txt || rm src": "оператор оболочки «|»",
        "grep -c x data/list.txt &": "оператор оболочки «&»",
        "grep -c x data/list.txt 2>&1": "оператор оболочки «>»",
        "grep -c $(rm -rf src) data/list.txt": "подстановка оболочки «$»",
        "grep -c \"$(rm src)\" data/list.txt": "подстановка «$» в кавычках",
        "grep -c `rm src` data/list.txt": "подстановка оболочки «`»",
        "grep -c $HOME data/list.txt": "подстановка оболочки «$»",
        "(grep -c x data/list.txt)": "оператор оболочки «(»",
        "grep -c x src/*.java": "шаблон имён файлов «*»",
        "grep -c x data/{list,other}.txt": "раскрытие скобок",
        "grep -c x data/list.txt # comment": "комментарий оболочки",
        "grep -c x ~root/list.txt": "раскрытие «~имя»",
        "grep -c x data/list.txt\nrm -rf src": "перевод строки",
        "grep -c 'x data/list.txt": "незакрытая кавычка",
        # programs outside the list, programs by path, devices
        "./gradlew gauntletFast": "программа с путём",
        "/usr/bin/grep -c x data/list.txt": "программа с путём",
        "python3 -c 'print(1)'": "не из списка программ",
        "rm -rf src": "не из списка программ",
        "xargs grep x": "не из списка программ",
        "env grep x": "не из списка программ",
        "LC_ALL=C grep x data/list.txt": "не из списка программ",
        "cat /dev/zero": "устройство или файл ядра",
        "grep --file=/dev/zero x": "устройство или файл ядра",
        "head -c 10 /proc/self/environ": "устройство или файл ядра",
    }

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="report-check-allow-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_accepted(self):
        for command in self.ACCEPTED:
            with self.subTest(command=command):
                argv, reason = module().runnable(command, self.root)
                program = command.split()[0]
                if shutil.which(program) is None:     # not installed here: refused as not found, never run
                    self.assertIn("не найдена", reason or "")
                    continue
                self.assertIsNone(reason, command)
                self.assertTrue(os.path.isabs(argv[0]), argv)

    def test_rejected(self):
        for command, why in self.REJECTED.items():
            with self.subTest(command=command):
                argv, reason = module().runnable(command, self.root)
                self.assertIsNone(argv, command)
                self.assertIn(why, reason)

    def test_words_agree_with_shlex_on_accepted_commands(self):
        # the splitter is POSIX quoting that remembers what was quoted (a quoted '*' or '$' is data, an unquoted one
        # is refused); on every form it accepts it must give exactly the words shlex gives
        for command in self.ACCEPTED:
            with self.subTest(command=command):
                words, reason = module().split_words(command)
                self.assertIsNone(reason, command)
                self.assertEqual(words, shlex.split(command))

    def test_git_runs_without_pager_fsmonitor_and_signatures(self):
        if shutil.which("git") is None:
            self.skipTest("no git")
        argv, _ = module().runnable("git log -1", self.root)
        self.assertEqual(argv[1:6], ["--no-pager", "-c", "core.fsmonitor=false", "-c", "log.showSignature=false"])

    def test_rg_runs_without_config(self):
        if shutil.which("rg") is None:
            self.skipTest("no rg")
        argv, _ = module().runnable("rg -n x", self.root)
        self.assertEqual(argv[1], "--no-config")

    def test_planted_program_in_the_repository_is_not_run(self):
        planted = os.path.join(self.root, "bin")
        os.makedirs(planted)
        fake = kit.write(os.path.join(planted, "grep"), "#!/bin/sh\necho planted\n")
        os.chmod(fake, 0o755)
        saved = os.environ["PATH"]
        os.environ["PATH"] = planted + os.pathsep + "." + os.pathsep + saved
        try:
            argv, reason = module().runnable("grep -c x data/list.txt", self.root)
        finally:
            os.environ["PATH"] = saved
        self.assertTrue(reason or not argv[0].startswith(planted), argv)


class RunnerLimitTest(unittest.TestCase):
    """run_capped(): a re-run that hangs or floods is stopped and reported as not re-run, never waited for."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="report-check-limit-")
        self.m = module()
        self.saved = (self.m.TIMEOUT, self.m.OUTPUT_LIMIT)

    def tearDown(self):
        self.m.TIMEOUT, self.m.OUTPUT_LIMIT = self.saved
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_command_that_hangs_is_stopped_after_the_timeout(self):
        fifo = os.path.join(self.root, "fifo")
        os.mkfifo(fifo)                         # cat blocks on a FIFO nobody writes to
        self.m.TIMEOUT = 1
        argv, reason = self.m.runnable("cat fifo", self.root)
        self.assertIsNone(reason)
        self.assertEqual(self.m.run_capped(argv, self.root, dict(os.environ)), (None, "не уложилась в 1 с"))

    def test_a_command_that_floods_is_stopped_at_the_output_limit(self):
        kit.write(os.path.join(self.root, "big.txt"), "x" * 5000 + "\n")
        self.m.OUTPUT_LIMIT = 1000
        argv, _ = self.m.runnable("cat big.txt", self.root)
        self.assertEqual(self.m.run_capped(argv, self.root, dict(os.environ)), (None, "вывод больше 1000 байт"))


class RunTest(Base):
    def genuine_commands(self):
        commands = [
            ("grep -n 'return a + b' src/Order.java", 0, ["5:        return a + b;"]),
            ("git grep -c total", 0, ["src/Order.java:1"]),
            ("git log --format=%s -1", 0, ["base"]),
            ("git show HEAD:src/Order.java", 0, ["class Order {", "… опущено 5 строк …"]),
            ("git rev-parse HEAD", 0, [self.sha]),
            ("git ls-files", 0, ["data/list.txt", "docs/rule.md", "src/Order.java"]),
            ("git cat-file -t HEAD", 0, ["commit"]),
            ("git blame -L 5,5 src/Order.java", 0, ["return a + b;"]),
            ("git status --porcelain", 0, []),
            ("wc -l src/Order.java", 0, ["7 src/Order.java"]),
            ("ls src", 0, ["Order.java"]),
            ("cat data/list.txt", 0, ["a"]),
            ("head -n 1 src/Order.java", 0, ["package shop;"]),
            ("tail -n 1 src/Order.java", 0, ["}"]),
            ("sed -n '4,5p' src/Order.java", 0, ["int total(int a, int b) {", "return a + b;"]),
            ("sort data/list.txt", 0, ["a", "b"]),
            ("uniq -c data/list.txt", 0, ["1 a", "2 b"]),
            ("find . -name Order.java", 0, ["./src/Order.java"]),
            ("grep -c missing src/Order.java", 1, ["0"]),
            ("ls no-such-file", 2, ["No such file or directory"]),
        ]
        if shutil.which("rg"):
            commands.append(("rg -n total src", 0, ["src/Order.java:4:    int total(int a, int b) {"]))
        return commands

    def evidence(self, commands):
        lines = []
        for command, code, out in commands:
            groups = " ".join(f"«{o}»" for o in out)
            lines.append(f"   - команда: `{command}` (код {code})" + (f" → {groups}" if groups else ""))
        return lines

    def test_genuine_commands_pass_and_change_nothing(self):
        commands = self.genuine_commands()
        # a file with a new mtime and the same content: `git status` would rewrite the index without optional locks
        os.utime(os.path.join(self.repo, "src", "Order.java"), (1, 1))
        before = tree_digest(self.repo)
        text = report(self.sha, self.claim(1, "Команды", evidence=self.evidence(commands)))
        result = self.check(text, "--run")
        self.assert_code(result, 0, f"совпало {len(commands)}", "расхождений 0")
        self.assertEqual(tree_digest(self.repo), before, "the re-run changed the repository")

    def test_wrong_exit_code_fails(self):
        text = report(self.sha, self.claim(1, "Вызова нет", evidence=(
            "   - команда: `grep -c missing src/Order.java` (код 0) → «0»",)))
        self.assert_code(self.check(text, "--run"), 1, "код выхода 1, в отчёте 0")

    def test_fabricated_output_fails(self):
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",)))
        self.assert_code(self.check(text, "--run"), 1, "в выводе нет: «src/Order.java:2»", "вывод: «src/Order.java:1»")

    def test_without_run_commands_are_listed_not_run(self):
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",)))
        self.assert_code(self.check(text), 0, "НЕ ПЕРЕЗАПУСКАЛАСЬ `git grep -c total`", "без --run")

    def test_refused_command_is_listed_with_the_reason(self):
        text = report(self.sha, self.claim(1, "Сборка зелёная", evidence=(
            "   - команда: `./gradlew gauntletFast` (код 0) → «BUILD SUCCESSFUL»",
            "   - команда: `grep -c x data/list.txt > out` (код 0) → «0»")))
        result = self.check(text, "--run")
        self.assert_code(result, 0, "программа с путём «./gradlew»", "оператор оболочки «>»")
        self.assertFalse(os.path.exists(os.path.join(self.repo, "out")))

    def test_revision_mismatch_skips_the_run(self):
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            GENUINE_FILE, "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»")))
        self.commit("moved on")
        self.assert_code(self.check(text, "--run"), 0, "совпало 1", "не равен ревизии отчёта")

    def test_dirty_tree_skips_the_run(self):
        kit.write(os.path.join(self.repo, "new.txt"), "x\n")
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",)))
        self.assert_code(self.check(text, "--run"), 0, "рабочее дерево не чистое (1 путей")

    def test_worktree_report_skips_the_run(self):
        text = report("«рабочее дерево»", self.claim(1, "Два вызова", evidence=(
            "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",)))
        self.assert_code(self.check(text, "--run"), 0, "ревизия отчёта - рабочее дерево")

    def test_json_shape(self):
        text = report(self.sha, self.claim(1, "Сумма", "гарантия, несущее", (
            GENUINE_FILE, REFUTED, "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",
            "   - источник: https://docs.oracle.com/javase/specs/jls/se21/html/jls-15.html «15.18.2»")))
        code, out, _ = self.check(text, "--run", "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual(data["revision"], self.sha)
        self.assertEqual(data["shape_errors"], [])
        self.assertEqual(data["claims"], [{"number": 1, "line": 5, "class": "гарантия", "load_bearing": True,
                                           "evidence": ["файл", "опровергло бы", "команда", "источник"]}])
        self.assertEqual(data["coverage"], [2, 2])
        self.assertEqual(data["evidence"], {"файл": 1, "команда": 1, "источник": 1, "опровергло бы": 1})
        self.assertEqual([(q["path"], q["stated"], q["status"], q["actual"], q["matched_lines"]) for q in data["quotes"]],
                         [("src/Order.java", 4, "ok", 4, [4, 5]), ("src/Order.java", 5, "ok", 5, [5])])
        command = data["commands"][0]
        self.assertEqual((command["command"], command["status"], command["expected_code"], command["actual_code"],
                          command["missing"]), ("git grep -c total", "mismatch", 0, 0, ["src/Order.java:2"]))
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(data["summary"], {"shape_errors": 0, "mismatches": 1, "corrections": 0, "checked": 3,
                                           "skipped": 0})

    def test_usage_errors_exit_2(self):
        r = subprocess.run([sys.executable, tool(), os.path.join(self.tmp, "none.md")], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        r = subprocess.run([sys.executable, tool(), "--repo", os.path.join(self.tmp, "nowhere"), tool()],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)


class HookTest(Base):
    """--hook: the SubagentStop event as Claude Code sends it (hooks reference: agent_transcript_path,
    last_assistant_message), the transcript in the layout of the real ones (~/.claude/projects/<p>/<session>/
    subagents/agent-<id>.jsonl: one JSON record per line, an assistant message split into records that share
    message.id, the report of a SubagentHandback agent in the call's input.message)."""

    def transcript(self, name, final=None, handback=None):
        records = [{"type": "user", "isSidechain": True, "agentId": name,
                    "message": {"role": "user", "content": "Карточка 4.1"}}]
        records.append({"type": "assistant", "agentId": name, "message": {
            "id": "msg_1", "role": "assistant", "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "git grep -c total"}}]}})
        if handback is not None:
            records.append({"type": "assistant", "agentId": name, "message": {
                "id": "msg_2", "role": "assistant", "stop_reason": "tool_use",
                "content": [{"type": "tool_use", "id": "t2", "name": "SubagentHandback",
                             "input": {"message": handback}}]}})
        if final is not None:
            records.append({"type": "assistant", "agentId": name, "message": {
                "id": "msg_3", "role": "assistant", "stop_reason": "end_turn",
                "content": [{"type": "thinking", "thinking": "..."}]}})
            records.append({"type": "assistant", "agentId": name, "message": {
                "id": "msg_3", "role": "assistant", "stop_reason": "end_turn",
                "content": [{"type": "text", "text": final}]}})
        path = os.path.join(self.tmp, "subagents", f"agent-{name}.jsonl")
        kit.write(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
        return path

    def hook(self, transcript, last=None, agent="checker"):
        event = {"session_id": "s", "transcript_path": os.path.join(self.tmp, "s.jsonl"), "cwd": self.repo,
                 "hook_event_name": "SubagentStop", "stop_hook_active": False, "agent_id": "a1",
                 "agent_type": agent, "agent_transcript_path": transcript}
        if last is not None:
            event["last_assistant_message"] = last
        r = subprocess.run([sys.executable, tool(), "--hook"], cwd=self.repo, input=json.dumps(event),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           env=dict(os.environ, CLAUDE_PROJECT_DIR=self.repo, PYTHONDONTWRITEBYTECODE="1"))
        return r

    def bad_report(self):
        return report(self.sha, self.claim(1, "Сумма с налогом", evidence=(
            "   - файл: `src/Order.java:5` «return a + b + tax;»",)))

    def test_bad_report_is_blocked_twice_then_released(self):
        path = self.transcript("a1", final=self.bad_report())
        for attempt in (1, 2):
            r = self.hook(path)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn(f"возврат {attempt} из 2", r.stderr)
            self.assertIn("цитата `src/Order.java:5` - цитаты нет", r.stderr)
            decision = json.loads(r.stdout)
            self.assertEqual(decision["decision"], "block")
            self.assertEqual(decision["reason"].strip(), r.stderr.strip())
        r = self.hook(path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("НЕ ПРИНЯТ механически после 2 возвратов", json.loads(r.stdout)["systemMessage"])
        state = os.path.join(self.repo, ".git", "gauntlet-hook")
        self.assertEqual(len([f for f in os.listdir(state) if f.startswith("report-check-")]), 1)
        # another subagent has its own count
        self.assertEqual(self.hook(self.transcript("a2", final=self.bad_report())).returncode, 2)

    def test_good_report_is_released_at_once(self):
        good = report(self.sha, self.claim(1, "Сумма"))
        r = self.hook(self.transcript("a1", final=good), last=good)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("расхождений нет", json.loads(r.stdout)["systemMessage"])

    def test_last_assistant_message_wins_over_a_stale_transcript(self):
        good = report(self.sha, self.claim(1, "Сумма"))
        r = self.hook(self.transcript("a1", final=self.bad_report()), last=good)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_final_message_that_is_not_a_report_is_blocked(self):
        r = self.hook(self.transcript("a1", final=self.bad_report()), last="Готово, отчёт выше.")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("последнее сообщение сабагента - не отчёт раздела 3", r.stderr)

    def test_handback_report_is_checked(self):
        path = self.transcript("a1", handback=self.bad_report())
        r = self.hook(path, last="")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("цитаты нет", r.stderr)
        good = report(self.sha, self.claim(1, "Сумма"))
        r = self.hook(self.transcript("a3", handback=good, final="Отчёт передан."), last="Отчёт передан.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_hook_never_runs_commands(self):
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            GENUINE_FILE, "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»")))
        r = self.hook(self.transcript("a1", final=text), last=text)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_report_at_all_is_blocked(self):
        r = self.hook(os.path.join(self.tmp, "subagents", "agent-none.jsonl"))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("отчёт не найден", r.stderr)

    def test_unreadable_event_lets_the_subagent_stop(self):
        r = subprocess.run([sys.executable, tool(), "--hook"], cwd=self.repo, input="not json",
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           env=dict(os.environ, CLAUDE_PROJECT_DIR=self.repo, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("не проверялся", json.loads(r.stdout)["systemMessage"])

    def test_outside_git_the_hook_does_not_hold_the_subagent(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        event = {"hook_event_name": "SubagentStop", "agent_type": "checker", "cwd": plain,
                 "last_assistant_message": self.bad_report()}
        r = subprocess.run([sys.executable, tool(), "--hook"], cwd=plain, input=json.dumps(event),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           env=dict(os.environ, CLAUDE_PROJECT_DIR=plain, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("не в git", json.loads(r.stdout)["systemMessage"])


if __name__ == "__main__":
    unittest.main()
