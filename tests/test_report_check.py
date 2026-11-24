"""gauntlet/tools/report_check.py: the mechanical check of a subagent report (gauntlet/subagents.md, 2.2 and 3).

A coordinator that spot-checks one claim of a report catches a faked one with probability about 1/k. The tool checks
every quote against the file at the report's revision and, with --run, re-runs every command it can prove read-only
and compares the exit code and the quoted output lines; anything it cannot prove read-only it refuses to re-run and
says why, and then its exit code is 3, not 0. These tests build a small git repository, write reports against it
and check that genuine evidence passes, fabricated evidence fails - a number that is only a part of the real one
too («1» of «12») - the shape of section 3 is enforced, the allowlist accepts and rejects what it should, a re-run
leaves the repository byte for byte as it was, the lines of a file outside the repository are never printed, and
the SubagentStop hook sends a bad report back twice and then lets the subagent stop.
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
SECRET = "nexusPassword=S3CR3T-TOKEN"


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
    header = header or (f"## Карточка 4.1, карта кода; ревизия {rev}; модель test-model, max; "
                        f"лимит среды: не достигнут")
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
        self.git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m",
                 message)

    def add(self, path, text):
        """Commits one more file; the new revision."""
        kit.write(os.path.join(self.repo, path), text)
        self.git("add", "-A")
        self.commit("add " + path)
        return self.git("rev-parse", "HEAD").strip()

    def check(self, text, *args, cwd=None, timeout=None):
        """(exit code, stdout, stderr) of report_check.py on the report text (written outside the repository)."""
        self.counter += 1
        path = kit.write(os.path.join(self.tmp, f"report-{self.counter}.md"), text)
        r = subprocess.run([sys.executable, tool(), "--repo", self.repo, *args, path], cwd=cwd or self.tmp,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout,
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
        claims = self.claim(1, "Сумма", evidence=(
            "   - файл: `src/Order.java:4` «int total(int a, int b) { return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "РАСХОЖДЕНИЕ")

    def test_shift_of_two_lines_is_a_correction(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:3` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "ПОПРАВКА src/Order.java:3",
                         "цитата на строке 5, а не 3")

    def test_shift_back_of_two_lines_is_a_correction_too(self):
        # the stated line is below the real one: a genuine quote with a miscounted line stays a correction
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:7` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "ПОПРАВКА src/Order.java:7",
                         "цитата на строке 5, а не 7")

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

    def test_absolute_path_inside_the_repository_is_read_at_the_revision(self):
        path = kit.write(os.path.join(self.repo, "src", "Order.java"), ORDER.replace("a + b", "a - b"))
        claims = self.claim(1, "Сумма", evidence=(f"   - файл: `{path}:5` «return a - b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "цитаты нет на ревизии")
        claims = self.claim(1, "Сумма", evidence=(f"   - файл: `{path}:5` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")

    def test_missing_file_is_a_mismatch(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Missing.java:1` «class Missing»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "нет файла src/Missing.java")

    def test_line_zero_is_a_shape_error(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:0` «package shop;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "номер строки 0 - строки считаются с 1")

    def test_omission_inside_a_group_and_whitespace_do_not_count(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:4` «int   total(int a, … {»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")

    def test_fragments_of_a_group_keep_their_order(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:4` «b) {… int total(»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "РАСХОЖДЕНИЕ src/Order.java:4")

    def test_part_of_a_line_does_not_cut_a_number_or_a_word(self):
        # «retries=3» is not a part of «retries=30»: a lost digit is "another number" (2.7), not a quote; a part
        # that ends where a word or a number ends is one, and "…" at an end says the cut is meant
        sha = self.add("conf/app.properties", "client.retries=30\nstarted 2026-11-24 12:30:01\nSpring Boot 4.0.7\n"
                                              "int subtotal(int a)\n")
        cases = [(1, "«client.retries=3»", 1), (1, "«retries=30»", 0), (1, "«client.retries=3…»", 0),
                 (1, "«client.…=3»", 1), (1, "«client.…=30»", 0), (2, "«12:30»", 0), (2, "«2026-11-2»", 1),
                 (3, "«Spring Boot 4.0»", 0), (3, "«Boot 4.0.7»", 0), (4, "«total(int a)»", 1),
                 (4, "«…total(int a)»", 0), (4, "«otal(int … a)»", 1), (4, "«int sub»", 1)]
        for line, quote, code in cases:
            with self.subTest(quote=quote):
                claims = self.claim(1, "Настройка", evidence=(f"   - файл: `conf/app.properties:{line}` {quote}",))
                self.assert_code(self.check(report(sha, claims)), code)

    def test_bare_ellipsis_groups_quote_nothing(self):
        for quote in ("«…»", "«…» «…»"):
            with self.subTest(quote=quote):
                claims = self.claim(1, "Сумма", evidence=(f"   - файл: `src/Order.java:4` {quote}",))
                self.assert_code(self.check(report(self.sha, claims)), 1, "группы «…» без текста")
        # «…» between two quoted lines skips one line, as before
        claims = self.claim(1, "Сумма", evidence=(
            "   - файл: `src/Order.java:4` «int total(int a, int b) {» «…» «}»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")

    def test_empty_group_quotes_only_an_empty_line(self):
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:2` «»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:5` «»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "РАСХОЖДЕНИЕ src/Order.java:5")
        # a trailing newline is a line terminator, not an extra empty line at EOF (nor within SHIFT of the last lines)
        sha = self.add("src/Tight.java", "alpha\x0cheader\nbeta\ngamma\n")
        for line in (1, 2, 3, 4):
            with self.subTest(line=line):
                claims = self.claim(1, "Плотное", evidence=(f"   - файл: `src/Tight.java:{line}` «»",))
                self.assert_code(self.check(report(sha, claims)), 1, f"РАСХОЖДЕНИЕ src/Tight.java:{line}")
        # form feed inside line 1 does not split it and shift line 2
        claims = self.claim(1, "Плотное", evidence=("   - файл: `src/Tight.java:2` «beta»",))
        self.assert_code(self.check(report(sha, claims)), 0, "совпало 1", "с поправкой 0")

    def test_file_outside_the_repository_is_read_on_disk(self):
        outside = kit.write(os.path.join(self.tmp, "vendor", "CHANGELOG.md"), "# 1.2\n- Added auto mode\n")
        claims = self.claim(1, "Режим добавлен в 1.2", evidence=(f"   - файл: `{outside}:2` «- Added auto mode»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")
        claims = self.claim(1, "Режим добавлен в 1.2", evidence=(f"   - файл: `{outside}:2` «- Added manual mode»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "вне репозитория, прочитан с диска")

    def test_lines_of_a_file_outside_the_repository_are_never_printed(self):
        outside = kit.write(os.path.join(self.tmp, "home", ".gradle", "gradle.properties"),
                            f"org.gradle.jvmargs=-Xmx2g\n{SECRET}\n")
        claims = self.claim(1, "Память сборки", evidence=(f"   - файл: `{outside}:2` «org.gradle.jvmargs=-Xmx4g»",))
        result = self.check(report(self.sha, claims))
        self.assert_code(result, 1, "цитаты нет в файле;",
                         f"на деле: {outside} - вне репозитория, содержимое не выводится")
        self.assertNotIn("S3CR3T", result[1] + result[2])
        code, out, err = self.check(report(self.sha, claims), "--json")
        self.assertNotIn("S3CR3T", out + err)
        quote = json.loads(out)["quotes"][0]
        self.assertEqual((code, quote["outside_repository"], quote["found"]), (1, True, []))

    def test_fifo_device_and_directory_are_mismatches_not_hangs(self):
        # a FIFO nobody writes to would hang the check, /dev/zero would eat the memory (/dev/null stands for the
        # devices here: reading it is harmless if the check regresses)
        fifo = os.path.join(self.tmp, "fifo")
        os.mkfifo(fifo)
        for path, why in ((fifo, "не обычный файл"), ("/dev/null", "устройство или файл ядра"),
                          (self.tmp, "не обычный файл")):
            with self.subTest(path=path):
                claims = self.claim(1, "Сумма", evidence=(f"   - файл: `{path}:1` «x»",))
                self.assert_code(self.check(report(self.sha, claims), timeout=30), 1, why)

    def test_big_file_on_disk_is_not_read_whole(self):
        m = module()
        saved, m.FILE_LIMIT = m.FILE_LIMIT, 10
        try:
            loaded = m.Repo(self.repo).load_disk(kit.write(os.path.join(self.tmp, "big.txt"), "x" * 20 + "\n"))
        finally:
            m.FILE_LIMIT = saved
        self.assertEqual((loaded.lines, loaded.why), (None, "файл больше 0 МБ - не читается"))

    def test_relative_path_out_of_the_repository_is_read_on_disk(self):
        kit.write(os.path.join(self.tmp, "sibling", "B.java"), "class B {}\n")
        claims = self.claim(1, "B пуст", evidence=("   - файл: `../sibling/B.java:1` «class B {}»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "вне репозитория (с диска, без ревизии) 1")
        claims = self.claim(1, "B пуст", evidence=("   - файл: `../sibling/B.java:1` «class C {}»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "цитаты нет в файле")

    def test_quote_in_a_worktree_copy_is_read_at_the_revision(self):
        # the external route's copy: git worktree add --detach <copy> <revision>
        copy = os.path.join(self.tmp, "copy")
        self.git("worktree", "add", "-q", "--detach", copy, self.sha)
        path = os.path.join(copy, "src", "Order.java")
        claims = self.claim(1, "Сумма", evidence=(f"   - файл: `{path}:5` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")
        kit.write(path, ORDER.replace("a + b", "a * b"))          # the copy edited after the revision
        claims = self.claim(1, "Сумма", evidence=(f"   - файл: `{path}:5` «return a * b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 1, "цитаты нет на ревизии")
        kit.write(os.path.join(copy, "build", "out.txt"), "BUILD OK\n")       # a file the revision does not have
        claims = self.claim(1, "Сборка", evidence=(f"   - файл: `{copy}/build/out.txt:1` «BUILD OK»",))
        self.assert_code(self.check(report(self.sha, claims)), 0, "совпало 1")

    def test_fenced_examples_are_not_evidence_or_sections(self):
        tail = ("Пример формата:", "```", "## Итог", "   - файл: `src/Order.java:1` «выдумано»", "```")
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), tail=tail)), 0, "Цитаты: 1;")

    def test_evidence_outside_the_claims_is_checked_too(self):
        text = report(self.sha, self.claim(1, "Сумма")).replace(
            "## Найдено сверх карточки\n",
            "## Найдено сверх карточки\n- Налог в total\n   - файл: `src/Order.java:5` «return a + b + tax;»\n")
        self.assert_code(self.check(text), 1, "РАСХОЖДЕНИЕ src/Order.java:5")

    def test_refutation_quote_is_checked_too(self):
        claims = self.claim(1, "Сумма", "гарантия, несущее", (GENUINE_FILE, REFUTED.replace("a + b", "a * b")))
        self.assert_code(self.check(report(self.sha, claims)), 1, "опровергло бы", "РАСХОЖДЕНИЕ src/Order.java:5")

    def test_refutation_result_in_words_goes_without_guillemets(self):
        refuted = "   - опровергло бы: налог в total; проверено: `src/Order.java:5` → «налога в сумме нет»"
        claims = self.claim(1, "Сумма", "гарантия, несущее", (GENUINE_FILE, refuted))
        self.assert_code(self.check(report(self.sha, claims)), 1, "пересказ результата - без «»")
        in_words = refuted.replace("«", "").replace("»", "")
        claims = self.claim(1, "Сумма", "гарантия, несущее", (GENUINE_FILE, in_words))
        self.assert_code(self.check(report(self.sha, claims)), 0, "в свободной форме (сверить вручную): 1")

    def test_rev_option_checks_another_revision(self):
        kit.write(os.path.join(self.repo, "src", "Order.java"), ORDER.replace("a + b", "b + a"))
        self.git("add", "-A")
        self.commit("swap")
        moved = self.git("rev-parse", "HEAD").strip()
        claims = self.claim(1, "Сумма", evidence=("   - файл: `src/Order.java:5` «return a + b;»",))
        self.assert_code(self.check(report(self.sha, claims)), 0)
        self.assert_code(self.check(report(self.sha, claims), "--rev", moved), 1, "цитаты нет")
        self.assert_code(self.check(report(self.sha, claims), "--rev", "no-such-revision"), 2,
                         "--rev no-such-revision")
        # an empty variable in the receiver's script is an error, not the header's revision
        self.assert_code(self.check(report(self.sha, claims), "--rev", ""), 2, "--rev пуст")

    def test_unknown_revision_in_the_header_fails(self):
        claims = self.claim(1, "Сумма")
        self.assert_code(self.check(report("0123456789abcdef0123456789abcdef01234567", claims)), 1,
                         "ревизии 0123456789abcdef0123456789abcdef01234567 нет")


class ShapeTest(Base):
    def test_missing_header_fails(self):
        text = report(self.sha, self.claim(1, "Сумма")).split("\n", 1)[1]
        self.assert_code(self.check(text), 1, "нет шапки")

    def test_text_before_the_header_fails(self):
        self.assert_code(self.check("Отчёт ниже.\n" + report(self.sha, self.claim(1, "Сумма"))), 1, "текст до шапки")

    def test_header_without_revision_fails(self):
        header = "## Карточка 4.1, карта кода; модель test-model, max; лимит среды: не достигнут"
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), header=header)), 1, "нет ревизии")

    def test_revision_is_a_commit_name(self):
        # a branch name moves: «ревизия main» is not the revision the quotes were read at
        self.assert_code(self.check(report("main", self.claim(1, "Сумма"))), 1, "ревизия «main» - не коммит")

    def test_header_without_model_or_limit_fails(self):
        header = f"## Карточка 4.1, карта кода; ревизия {self.sha}; модель test-model, max; лимит среды: не достигнут"
        for part, why in (("; модель test-model, max", "нет модели"), ("; лимит среды: не достигнут", "нет лимита")):
            with self.subTest(why=why):
                text = report(self.sha, self.claim(1, "Сумма"), header=header.replace(part, ""))
                self.assert_code(self.check(text), 1, why)

    def test_missing_section_fails(self):
        text = report(self.sha, self.claim(1, "Сумма"), sections=["Итог", "Проверено", "Найдено сверх карточки",
                                                                 "Вопросы и риски для координатора"])
        self.assert_code(self.check(text), 1, "нет раздела «## Не проверено»")

    def test_sections_out_of_order_fail(self):
        text = report(self.sha, self.claim(1, "Сумма"), sections=["Итог", "Не проверено", "Проверено",
                                                                 "Найдено сверх карточки",
                                                                 "Вопросы и риски для координатора"])
        self.assert_code(self.check(text), 1, "не на своём месте")

    def test_section_twice_and_empty_summary_fail(self):
        text = report(self.sha, self.claim(1, "Сумма")).replace("## Не проверено",
                                                               "## Итог\nЕщё итог.\n## Не проверено")
        self.assert_code(self.check(text), 1, "раздел «Итог» второй раз")
        text = report(self.sha, self.claim(1, "Сумма")).replace("Сумма считается в одном месте.\n", "")
        self.assert_code(self.check(text), 1, "раздел «Итог» пуст")

    def test_extra_section_fails(self):
        text = report(self.sha, self.claim(1, "Сумма")).replace("## Найдено сверх карточки",
                                                                "## Таблица\n## Найдено сверх карточки")
        self.assert_code(self.check(text), 1, "лишний раздел «## Таблица»")

    def test_heading_inside_checked_says_where_subheadings_go(self):
        # the advice must not lead to the next error: «###» inside «Проверено» is text outside the claims
        text = report(self.sha, ["## Расчёт суммы", *self.claim(1, "Сумма")])
        self.assert_code(self.check(text), 1, "лишний раздел «## Расчёт суммы»", "«###» - вне «Проверено»")
        text = report(self.sha, ["### Расчёт суммы", *self.claim(1, "Сумма")])
        self.assert_code(self.check(text), 1, "текст в «Проверено» вне утверждений", "[гарантия]» (или [риск]")

    def test_claim_without_class_fails(self):
        text = report(self.sha, ["1. Сумма считается в total", GENUINE_FILE])
        self.assert_code(self.check(text), 1, "у утверждения 1 нет класса")

    def test_class_is_one_of_the_four_literal_forms(self):
        for cls in ("[гарантия, риск]", "[важное]", "[гарантия][, несущее]", "[гарантия], несущее",
                    "[гарантия | риск]"):
            with self.subTest(cls=cls):
                text = report(self.sha, [f"1. Сумма считается в total {cls}", GENUINE_FILE])
                self.assert_code(self.check(text), 1, "у утверждения 1 нет класса")
        text = report(self.sha, ["1. Сумма считается в total [риск, несущее]", GENUINE_FILE, REFUTED])
        self.assert_code(self.check(text), 0)

    def test_claim_without_evidence_fails(self):
        text = report(self.sha, ["1. Сумма считается в total [гарантия]"])
        self.assert_code(self.check(text), 1, "у утверждения 1 нет доказательства")

    def test_claim_proved_by_a_source_alone_passes(self):
        text = report(self.sha, ["1. Оператор + складывает int [гарантия]",
                                 "   - источник: https://docs.oracle.com/javase/specs/jls/se21/html/jls-15.html "
                                 "«15.18.2 Additive Operators»"])
        self.assert_code(self.check(text), 0, "Источники (сверить вручную или выборочно): 1")

    def test_source_without_a_quote_fails(self):
        text = report(self.sha, self.claim(1, "Сумма", evidence=(
            GENUINE_FILE, "   - источник: https://docs.oracle.com/javase/specs/jls/se21/html/jls-15.html")))
        self.assert_code(self.check(text), 1, "строка «источник:» без цитаты")

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

    def test_reason_follows_a_dash(self):
        text = report(self.sha, self.claim(1, "Сумма"), unchecked=("- Прогон сборки вне карточки",),
                      coverage="1 из 2")
        self.assert_code(self.check(text), 1, "без допустимой причины")

    def test_reason_may_be_on_a_continuation_line(self):
        unchecked = ("- Прогон сборки и тестов модуля core", "  — вне карточки — сборку гоняет сессия задачи")
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), unchecked=unchecked,
                                           coverage="1 из 2")), 0)

    def test_nothing_unchecked_only_at_full_coverage(self):
        for item in ("- нет", "- Ничего: покрытие полное"):
            with self.subTest(item=item):
                text = report(self.sha, self.claim(1, "Сумма"), unchecked=(item,), coverage="2 из 2")
                self.assert_code(self.check(text), 0)
                text = report(self.sha, self.claim(1, "Сумма"), unchecked=(item,), coverage="1 из 2")
                self.assert_code(self.check(text), 1, "«- нет» - только при полном покрытии")
        # an item that only starts with «Нет» names what was not checked
        text = report(self.sha, self.claim(1, "Сумма"), coverage="1 из 2",
                      unchecked=("- Нет ответа Maven Central — нет доступа (curl: 403) — версия не сверена",))
        self.assert_code(self.check(text), 0)

    def test_unchecked_item_may_start_with_an_evidence_word(self):
        unchecked = ("- Источник: документация Spring Retry 2.0.5 — нет доступа (домен не разрешён) — не сверено",
                     "- Команда: `./gradlew dependencies` — вне карточки — версия не сверена")
        result = self.check(report(self.sha, self.claim(1, "Сумма"), unchecked=unchecked, coverage="1 из 3"))
        self.assert_code(result, 0, "файл 1, команда 0, источник 0, опровергло бы 0")
        # a quote in such an item is still a quote
        unchecked = ("- Файл: `src/Order.java:5` «return a * b;» — вне карточки — не сверено",)
        result = self.check(report(self.sha, self.claim(1, "Сумма"), unchecked=unchecked, coverage="1 из 2"))
        self.assert_code(result, 1, "РАСХОЖДЕНИЕ src/Order.java:5")

    def test_coverage_numbers(self):
        self.assert_code(self.check(report(self.sha, self.claim(1, "Сумма"), coverage="3 из 2")), 1,
                         "N больше M")
        self.assert_code(self.check(report(self.sha, (), coverage="0 из 0")), 1, "M >= 1")
        self.assert_code(self.check(report(self.sha, (), coverage="5 из 5")), 1, "ни одного утверждения")
        self.assert_code(self.check(report(self.sha, (), coverage="0 из 2",
                                           unchecked=("- Карточка — нет доступа (сеть закрыта) — не сверено",))), 0)
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

    def test_command_output_in_words_fails_with_the_form_for_no_output(self):
        text = report(self.sha, self.claim(1, "Вызова нет", evidence=(
            "   - команда: `git grep -n vat` (код 1) → совпадений нет",)))
        self.assert_code(self.check(text), 1, "вывода нет - «→ пусто» или «(код N)» без «→»")

    def test_command_quoting_only_omitted_marker_fails(self):
        for groups in ("«… опущено 5 строк …»", "«…» «… опущено 5 строк …»"):
            with self.subTest(groups=groups):
                text = report(self.sha, self.claim(1, "Сумма", evidence=(
                    f"   - команда: `cat src/Order.java` (код 0) → {groups}",)))
                self.assert_code(self.check(text), 1, "ничего не цитируют")
        refuted = "   - опровергло бы: вызов vat; проверено: `cat src/Order.java` (код 0) → «… опущено 5 строк …»"
        text = report(self.sha, self.claim(1, "Сумма", "гарантия, несущее", (GENUINE_FILE, refuted)))
        self.assert_code(self.check(text), 1, "ничего не цитируют")


class AllowlistTest(unittest.TestCase):
    """runnable(): which reported commands may be re-run, and why the others may not."""

    ACCEPTED = [
        "git grep -n total", "git show HEAD:src/Order.java", "git log --oneline -3", "git ls-files",
        "git rev-parse HEAD", "git rev-parse --git-dir", "git cat-file -p HEAD", "git blame -L 5,5 src/Order.java",
        "git status --porcelain",
        "git grep --text -c x", "grep -rn 'a + b' src", "egrep -c 'a|b' data/list.txt", "fgrep -c b data/list.txt",
        "rg -n --pretty total src", "find . -name Order.java", "wc -l src/Order.java", "ls -la src",
        "cat data/list.txt", "head -n 3 src/Order.java", "tail -n 2 src/Order.java", "sed -n '4,5p' src/Order.java",
        "sed -n 4p src/Order.java", "sort -r data/list.txt", "uniq -c data/list.txt", "javap -p -cp build Order",
        "grep -c '$x' data/list.txt", "git log '@{u}'", "git log --diff-merges=first-parent -1",
        "git log -m --stat -1",
        "javap -cp build:lib/x.jar Order", "javap jar:file:///x.jar!/X.class", "javap file:///x/X.class",
        "javap jrt:/java.base/java/lang/Object.class", "grep -ex/dev src/Order.java"]
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
        # remerge-diff writes temporary objects into .git/objects and leaves them when the re-run is stopped
        "git log --remerge-diff -1": "пишет файл или запускает",
        "git show --remerge-diff HEAD": "пишет файл или запускает",
        "git show --diff-merges=remerge HEAD": "временные объекты в .git/objects",
        "git log --diff-merges=r -1": "временные объекты в .git/objects",
        "git log --diff-merges r -1": "временные объекты в .git/objects",
        "git log --diff-merges remerge -1": "временные объекты в .git/objects",
        "git -c core.pager=x log": "глобальная опция git",
        "git -C /tmp log": "глобальная опция git",
        "git --exec-path=/tmp log": "глобальная опция git",
        "git commit -m x": "не из списка подкоманд",
        "git checkout -- src": "не из списка подкоманд",
        "git config core.pager x": "не из списка подкоманд",
        "git diff HEAD": "не из списка подкоманд",
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
        # javap that runs the code of another JDK (its lib/jrt-fs.jar) or reaches the network: a host in file: and
        # jar:file: is FTP, a class argument with any other scheme is a URL too
        "javap --system /x --module java.base java.lang.Object": "исполняет его код",
        "javap --system=/x -m java.base X": "исполняет его код",
        "javap file://h/X.class": "ходит в сеть",
        "javap jar:file://h/x.jar!/X.class": "ходит в сеть",
        "javap FILE://h/X.class": "ходит в сеть",
        "javap http:/h/X.class": "ходит в сеть",
        "javap jar:http:/h/x.jar!/X.class": "ходит в сеть",
        "javap jar:file:///dev/zero!/X.class": "устройство или файл ядра",
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
        "grep --file=~/patterns x data/list.txt": "тильда после «=»",
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
        "grep -nf/dev/zero x": "устройство или файл ядра",
        "javap -cp build:/dev/zero Order": "устройство или файл ядра",
        "head -c 10 /proc/self/environ": "устройство или файл ядра",
        "cat /sys/kernel/mm/transparent_hugepage/enabled": "устройство или файл ядра",
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

    def test_git_runs_without_pager_fsmonitor_signatures_and_remerge(self):
        # log.diffMerges=remerge in a config would make `git log -m` write temporary objects as --remerge-diff does;
        # diff.<driver>.textconv runs an external converter on show, log, blame and grep unless --no-textconv is passed
        if shutil.which("git") is None:
            self.skipTest("no git")
        argv, _ = module().runnable("git log -1", self.root)
        self.assertEqual(argv[1:8], ["--no-pager", "-c", "core.fsmonitor=false", "-c", "log.showSignature=false",
                                     "-c", "log.diffMerges=separate"])
        for sub in ("show", "log", "blame", "grep"):
            argv, _ = module().runnable(f"git {sub} x", self.root)
            self.assertEqual(argv[8:10], [sub, "--no-textconv"], sub)
        for sub in ("cat-file", "ls-files", "rev-parse", "status"):
            argv, _ = module().runnable(f"git {sub}", self.root)
            self.assertNotIn("--no-textconv", argv, sub)

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
        self.m = module()      # first: a kit without the tool fails here, before a directory tearDown never removes
        self.saved = (self.m.TIMEOUT, self.m.OUTPUT_LIMIT)
        self.root = tempfile.mkdtemp(prefix="report-check-limit-")

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
        self.assert_code(self.check(text, "--run"), 1, "в выводе нет: «src/Order.java:2»",
                         "вывод: «src/Order.java:1»")

    def test_number_that_is_a_part_of_the_real_one_fails(self):
        # 17 lines: «7», «1» and «:1» are parts of the real output, and each is another number (2.7)
        sha = self.add("data/big.txt", "".join(f"line {i}\n" for i in range(1, 18)))
        fake = [("wc -l data/big.txt", 0, ["7 data/big.txt"]), ("grep -c line data/big.txt", 0, ["1"]),
                ("git grep -c line", 0, ["data/big.txt:1"])]
        text = report(sha, self.claim(1, "Строк 17", evidence=self.evidence(fake)))
        self.assert_code(self.check(text, "--run"), 1, "расхождений 3", "в выводе нет: «7 data/big.txt»")
        real = [("wc -l data/big.txt", 0, ["17 data/big.txt"]), ("grep -c line data/big.txt", 0, ["17"]),
                ("git grep -c line", 0, ["data/big.txt:17"])]
        text = report(sha, self.claim(1, "Строк 17", evidence=self.evidence(real)))
        self.assert_code(self.check(text, "--run"), 0, "совпало 3")

    def test_no_output_is_checked(self):
        text = report(self.sha, self.claim(1, "Вызова нет", evidence=(
            "   - команда: `git grep -n vat` (код 1) → пусто",)))
        self.assert_code(self.check(text, "--run"), 0, "совпало 1")
        for form in (" → (вывода нет)", ""):
            with self.subTest(form=form):
                text = report(self.sha, self.claim(1, "Вызова нет", evidence=(
                    f"   - команда: `git grep -n total` (код 0){form}",)))
                self.assert_code(self.check(text, "--run"), 1, "вывод не пуст")
        refuted = "   - опровергло бы: вызов vat; проверено: `git grep -n vat` (код 1) → пусто, вызовов нет"
        text = report(self.sha, self.claim(1, "Вызова нет", "гарантия, несущее", (GENUINE_FILE, refuted)))
        self.assert_code(self.check(text, "--run"), 0, "перезапущено 1, совпало 1")
        for tail in ("пусто «нет такой строки»", "пусто «src/Order.java:4:vat»"):
            with self.subTest(tail=tail):
                mixed = f"   - опровергло бы: вызов vat; проверено: `git grep -n vat` (код 1) → {tail}"
                bad = report(self.sha, self.claim(1, "Вызова нет", "гарантия, несущее", (GENUINE_FILE, mixed)))
                self.assert_code(self.check(bad), 1, "после «пусто» - группы «…»")
                self.assert_code(self.check(bad, "--run"), 1, "после «пусто» - группы «…»")
        unchecked_mixed = report(
            self.sha, self.claim(1, "Сумма"), coverage="1 из 2",
            unchecked=("- команда: `git grep -n vat` (код 1) → пусто «src/Order.java:4:vat» — нет доступа — риск",))
        self.assert_code(self.check(unchecked_mixed, "--run"), 1, "в выводе нет: «src/Order.java:4:vat»")

    def test_empty_group_in_command_output_matches_only_real_blank_line(self):
        for cmd in ("wc -l src/Order.java", "git grep -c total"):
            for groups in ("«»", "«   »", "«» «… опущено 3 строк …»"):
                with self.subTest(cmd=cmd, groups=groups):
                    text = report(self.sha, self.claim(1, "Вывод", evidence=(
                        f"   - команда: `{cmd}` (код 0) → {groups}",)))
                    self.assert_code(self.check(text, "--run"), 1, "в выводе нет:")
        silent = report(self.sha, self.claim(1, "Чисто", evidence=(
            "   - команда: `git status --porcelain` (код 0) → «»",)))
        self.assert_code(self.check(silent, "--run"), 1, "в выводе нет: «»")
        # line 2 of src/Order.java is genuinely blank, so sed prints one empty line ("\n")
        blank = report(self.sha, self.claim(1, "Пустая строка", evidence=(
            "   - команда: `sed -n '2p' src/Order.java` (код 0) → «»",)))
        self.assert_code(self.check(blank, "--run"), 0, "совпало 1")

    def test_git_textconv_in_config_is_not_run(self):
        marker = os.path.join(self.tmp, "converter-ran")
        converter = kit.write(os.path.join(self.tmp, "conv.sh"),
                              f"#!/bin/sh\necho ran > {shlex.quote(marker)}\necho converted_line\n")
        os.chmod(converter, 0o755)
        kit.write(os.path.join(self.repo, ".gitattributes"), "*.bin diff=demo\n")
        with open(os.path.join(self.repo, "data.bin"), "wb") as f:
            f.write(b"raw_bytes_line\x00\n")
        self.git("add", ".gitattributes", "data.bin")
        self.commit("bin")
        sha = self.git("rev-parse", "HEAD").strip()
        self.git("config", "diff.demo.textconv", converter)
        self.git("config", "diff.demo.cachetextconv", "true")
        before = tree_digest(self.repo)
        evidence = ("   - команда: `git show HEAD` (код 0) → «Binary files»",
                    "   - команда: `git log -p -1` (код 0) → «Binary files»",
                    "   - команда: `git log -S converted_line -1` (код 0) → пусто",
                    "   - команда: `git blame data.bin` (код 0) → «raw_bytes_line»")
        result = self.check(report(sha, self.claim(1, "Бинарный", evidence=evidence)), "--run")
        self.assert_code(result, 0, "совпало 4")
        self.assertFalse(os.path.exists(marker), "diff.demo.textconv ran during --run")
        self.assertEqual(tree_digest(self.repo), before, "textconv wrote to the repository or .git")

    def test_ansi_colours_are_not_output(self):
        text = report(self.sha, self.claim(1, "Сумма", evidence=(
            "   - команда: `grep --color=always -n total src/Order.java` (код 0) → "
            "«4:    int total(int a, int b) {»",)))
        self.assert_code(self.check(text, "--run"), 0, "совпало 1")

    def test_output_of_a_command_that_reads_outside_the_repository_is_not_printed(self):
        # what matters: no line of the file in the output, text or JSON, and for each command the line that says why.
        # That line names the path as the command does, shortened with «…» when it is long (the tool shortens long
        # texts): the absolute path is as long as TMPDIR - checked whole or by its start; the relative one is short at
        # any TMPDIR - checked whole. The JSON has no output of commands at all.
        outside = kit.write(os.path.join(self.tmp, "home", ".gradle", "gradle.properties"),
                            f"nexusUser=DEPLOY-BOT\n{SECRET}\n")
        relative = "../home/.gradle/gradle.properties"         # from the repository root, where a command is re-run
        text = report(self.sha, self.claim(1, "Пользователь", evidence=tuple(
            f"   - команда: `cat {shlex.quote(path)}` (код 0) → «nexusUser=cdx»" for path in (outside, relative))))
        code, out, err = self.check(text, "--run")
        self.assert_code((code, out, err), 1, "в выводе нет: «nexusUser=cdx»")
        _, json_out, json_err = self.check(text, "--run", "--json")
        for printed in (out + err, json_out + json_err):
            for own in ("DEPLOY-BOT", "S3CR3T"):        # the text of each line of the file, and nothing else has it
                self.assertNotIn(own, printed)
        tail = " - вне репозитория, содержимое не выводится"
        shown = [s[len("вывод: "):-len(tail)] for s in map(str.strip, (out + "\n" + err).splitlines())
                 if s.startswith("вывод: ") and s.endswith(tail)]
        self.assertEqual(len(shown), 2, out + err)
        self.assertTrue(shown[0] == outside or len(shown[0]) > 1 and shown[0].endswith("…")
                        and outside.startswith(shown[0][:-1]), shown[0])
        self.assertEqual(shown[1], relative)
        data = json.loads(json_out)      # both re-run, and cat read the file: its lines were there to be printed
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual([(c["status"], c["actual_code"], c["missing"]) for c in data["commands"]],
                         [("mismatch", 0, ["nexusUser=cdx"])] * 2)

    def test_without_run_commands_are_listed_not_run(self):
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",)))
        result = self.check(text)
        self.assert_code(result, 0, "НЕ ПЕРЕЗАПУСКАЛАСЬ `git grep -c total`", "без --run")
        self.assertNotIn("НЕ ВСЁ ПЕРЕПРОВЕРЕНО", result[1])

    def test_refused_command_is_listed_with_the_reason(self):
        text = report(self.sha, self.claim(1, "Сборка зелёная", evidence=(
            "   - команда: `./gradlew gauntletFast` (код 0) → «BUILD SUCCESSFUL»",
            "   - команда: `grep -c x data/list.txt > out` (код 0) → «0»")))
        result = self.check(text, "--run")
        self.assert_code(result, 3, "программа с путём «./gradlew»", "оператор оболочки «>»",
                         "НЕ ВСЁ ПЕРЕПРОВЕРЕНО: не перезапускалось команд 2 из 2",
                         "не всё перепроверено; код выхода 3")
        self.assertFalse(os.path.exists(os.path.join(self.repo, "out")))
        code, out, _ = self.check(text, "--run", "--json")
        data = json.loads(out)
        self.assertEqual((code, data["exit_code"], data["summary"]["not_rerun"]), (3, 3, 2))

    def test_revision_mismatch_skips_the_run(self):
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            GENUINE_FILE, "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»")))
        self.commit("moved on")
        self.assert_code(self.check(text, "--run"), 3, "совпало 1", "не равен ревизии отчёта", "НЕ ВСЁ ПЕРЕПРОВЕРЕНО")

    def test_dirty_tree_skips_the_run(self):
        kit.write(os.path.join(self.repo, "new.txt"), "x\n")
        text = report(self.sha, self.claim(1, "Два вызова", evidence=(
            "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",)))
        self.assert_code(self.check(text, "--run"), 3, "рабочее дерево не чистое (1 путей", "НЕ ВСЁ ПЕРЕПРОВЕРЕНО")

    def test_worktree_report_skips_the_run(self):
        text = report("«рабочее дерево»", self.claim(1, "Два вызова", evidence=(
            "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",)))
        self.assert_code(self.check(text, "--run"), 3, "ревизия отчёта - рабочее дерево", "НЕ ВСЁ ПЕРЕПРОВЕРЕНО")

    def test_command_stopped_by_the_timeout_is_not_rerun(self):
        os.mkfifo(os.path.join(self.repo, "pipe"))     # git status does not list a FIFO: the tree stays clean
        m = module()
        saved, m.TIMEOUT = m.TIMEOUT, 1
        try:
            text = report(self.sha, self.claim(1, "Сумма", evidence=(
                GENUINE_FILE, "   - команда: `cat pipe` (код 0) → «x»")))
            checked = m.check_report(text, m.Repo(self.repo), run=True)
        finally:
            m.TIMEOUT = saved
        self.assertEqual(m.verdict(checked), 3)
        self.assertIn("не уложилась в 1 с", m.summary(checked))
        self.assertIn("НЕ ВСЁ ПЕРЕПРОВЕРЕНО", m.summary(checked))

    def test_json_shape(self):
        text = report(self.sha, self.claim(1, "Сумма", "гарантия, несущее", (
            GENUINE_FILE, REFUTED, "   - команда: `git grep -c total` (код 0) → «src/Order.java:2»",
            "   - источник: https://docs.oracle.com/javase/specs/jls/se21/html/jls-15.html «15.18.2»")))
        code, out, _ = self.check(text, "--run", "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual(data["revision"], self.sha)
        self.assertTrue(data["run"])
        self.assertEqual(data["shape_errors"], [])
        self.assertEqual(data["claims"], [{"number": 1, "line": 5, "class": "гарантия", "load_bearing": True,
                                           "evidence": ["файл", "опровергло бы", "команда", "источник"]}])
        self.assertEqual(data["coverage"], [2, 2])
        self.assertEqual(data["evidence"], {"файл": 1, "команда": 1, "источник": 1, "опровергло бы": 1})
        self.assertEqual([(q["path"], q["stated"], q["status"], q["actual"], q["matched_lines"])
                          for q in data["quotes"]],
                         [("src/Order.java", 4, "ok", 4, [4, 5]), ("src/Order.java", 5, "ok", 5, [5])])
        command = data["commands"][0]
        self.assertEqual((command["command"], command["status"], command["expected_code"], command["actual_code"],
                          command["missing"]), ("git grep -c total", "mismatch", 0, 0, ["src/Order.java:2"]))
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(data["summary"], {"shape_errors": 0, "mismatches": 1, "corrections": 0, "checked": 3,
                                           "skipped": 0, "not_rerun": 0})

    def test_usage_errors_exit_2(self):
        r = subprocess.run([sys.executable, tool(), os.path.join(self.tmp, "none.md")], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        r = subprocess.run([sys.executable, tool(), "--repo", os.path.join(self.tmp, "nowhere"), tool()],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        # a wrong option with --json answers in JSON too
        r = subprocess.run([sys.executable, tool(), "--json", "--no-such-option", tool()], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        self.assertEqual((r.returncode, json.loads(r.stdout)["exit_code"]), (2, 2), r.stdout + r.stderr)


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
            "content": [{"type": "tool_use", "id": "t1", "name": "Bash",
                         "input": {"command": "git grep -c total"}}]}})
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

    def test_wrong_arguments_let_the_subagent_stop(self):
        # exit 2 would block the stop, and on this path no count of returns would ever let the subagent go
        for args in (["--hook", "--run"], ["--hook", "--no-such-option"]):
            with self.subTest(args=args):
                r = subprocess.run([sys.executable, tool(), *args], cwd=self.repo, input="{}",
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   env=dict(os.environ, CLAUDE_PROJECT_DIR=self.repo, PYTHONDONTWRITEBYTECODE="1"))
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("хук вызван неверно", json.loads(r.stdout)["systemMessage"])

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
