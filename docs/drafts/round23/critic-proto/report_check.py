#!/usr/bin/env python3
"""Prototype (not part of the kit): mechanical check of a subagent report's evidence.

  python3 -I report_check.py --repo <git dir> [--rerun] <report.md>

Evidence lines it understands (the grammar proposed in core-critique.md, section "Формат отчёта"):
  `path/File.java:120` «exact quote»          quote must occur at that line (+-2) on the report's revision
  `path:120-124` «exact quote»                 same, for a range
  `cmd args | cmd2 args` (код 0) → «out … out» a read-only command; with --rerun it is re-run and every
                                                 «…»-separated piece of the claimed output must appear in order
The revision is the line "Ревизия: <sha>" of the report (default HEAD). Files are read with `git show
<rev>:<path>`, so the working tree is never touched. Commands are re-run only when the repository HEAD is that
revision, only from an allowlist of read-only programs, without a shell (pipes are chained by hand), and any
other shell syntax is refused. Exit code: 0 all checked evidence matches, 1 a mismatch, 2 usage error.
"""
import argparse
import re
import shlex
import subprocess
import sys

QUOTE = re.compile(r"`([^`\s:]+):(\d+)(?:-(\d+))?`\s*:?\s*«([^»]+)»")
COMMAND = re.compile(r"`([^`]+)`\s*(?:\(код\s+(-?\d+)\))?\s*→\s*«([^»]*)»")
REVISION = re.compile(r"^Ревизия:\s*([0-9a-f]{7,40})\b", re.M)
READ_ONLY = {"grep", "rg", "wc", "head", "tail", "cat", "ls", "sort", "uniq", "cut", "tr", "nl"}
GIT_READ_ONLY = {"grep", "log", "show", "ls-files", "rev-parse", "blame", "cat-file", "ls-tree"}


def norm(text):
    return " ".join(text.split())


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def check_quote(repo, rev, path, first, last, quote):
    shown = git(repo, "show", f"{rev}:{path}")
    if shown.returncode != 0:
        return "MISMATCH", f"нет файла {path} на ревизии {rev[:12]}"
    lines = shown.stdout.splitlines()
    lo, hi = max(first - 3, 0), min((last or first) + 2, len(lines))
    if norm(quote) in norm(" ".join(lines[lo:hi])):
        return "OK", f"{path}:{first}"
    span = (last or first) - first + 3
    hits = [i for i in range(len(lines)) if norm(quote) in norm(lines[i])] or \
           [i for i in range(len(lines)) if norm(quote) in norm(" ".join(lines[i:i + span]))]
    if hits:
        return "MISMATCH", f"цитата есть, но на строке {hits[0] + 1}, а не {first}"
    return "MISMATCH", f"цитаты нет в {path} на ревизии {rev[:12]}"


def pipeline(command):
    """argv lists of a pipeline of allowlisted read-only programs, or a reason to refuse."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>()")
    lexer.whitespace_split = True
    stages, argv = [], []
    for token in lexer:
        if token == "|":
            stages.append(argv)
            argv = []
        elif token and set(token) <= set("|&;<>()"):
            return None, f"синтаксис оболочки «{token}» не перезапускается"
        else:
            argv.append(token)
    stages.append(argv)
    for argv in stages:
        if not argv:
            return None, "пустая стадия конвейера"
        if any("$" in a or "`" in a for a in argv):
            return None, "подстановка не перезапускается"
        prog = argv[0]
        if prog == "git":
            if len(argv) < 2 or argv[1] not in GIT_READ_ONLY:
                return None, f"git {argv[1] if len(argv) > 1 else ''} вне списка чтения"
            if any(a.startswith(("-O", "--open-files-in-pager", "--ext-diff", "--textconv", "--output")) for a in argv):
                return None, "опция git, которая пишет файл или запускает программу"
        elif prog == "sed":
            # only `sed -n '<N>p'` / `'<N>,<M>p'`: the sed commands w, W and e write files or run programs
            if len(argv) < 3 or argv[1] != "-n" or not re.fullmatch(r"\d+(,\d+)?p", argv[2]):
                return None, "sed только в форме sed -n 'N,Mp' файл"
        elif prog == "find":
            if any(a in ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls")
                   for a in argv):
                return None, "find с действием записи или запуска"
        elif prog not in READ_ONLY:
            return None, f"{prog} вне списка программ только для чтения"
        if prog == "rg" and any(a.startswith("--pre") for a in argv):
            return None, "rg --pre запускает программу"
        if prog == "sort" and any(a.startswith(("-o", "--output", "--compress-program")) for a in argv):
            return None, "sort с файлом вывода или программой сжатия"
        if prog == "uniq" and len([a for a in argv[1:] if not a.startswith("-")]) > 1:
            return None, "uniq со вторым операндом пишет файл"
    return stages, None


def run(repo, stages):
    data, code = None, 0
    for argv in stages:
        done = subprocess.run(argv, cwd=repo, input=data, capture_output=True, text=True, timeout=60)
        data, code = done.stdout, done.returncode
    return code, data


def check_command(repo, command, code, claimed, rerun, at_rev):
    if not rerun:
        return "SKIPPED", "перезапуск выключен (--rerun)"
    if not at_rev:
        return "SKIPPED", "HEAD репозитория не равен ревизии отчёта"
    stages, reason = pipeline(command)
    if reason:
        return "SKIPPED", reason
    actual_code, out = run(repo, stages)
    if code is not None and int(code) != actual_code:
        return "MISMATCH", f"код выхода {actual_code}, в отчёте {code}"
    position, flat = 0, norm(out)
    for piece in [norm(p) for p in claimed.split("…") if norm(p)]:
        found = flat.find(piece, position)
        if found < 0:
            return "MISMATCH", f"в выводе нет «{piece[:60]}»; фактически: «{flat[:120]}»"
        position = found + len(piece)
    return "OK", f"код {actual_code}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("report")
    opts = ap.parse_args()
    text = open(opts.report, encoding="utf-8").read()
    found = REVISION.search(text)
    rev = git(opts.repo, "rev-parse", found.group(1) if found else "HEAD").stdout.strip()
    if not rev:
        print("ревизия отчёта не найдена в репозитории", file=sys.stderr)
        return 2
    at_rev = git(opts.repo, "rev-parse", "HEAD").stdout.strip() == rev
    results = []
    for m in QUOTE.finditer(text):
        path, first, last, quote = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        results.append((f"{path}:{first}", *check_quote(opts.repo, rev, path, first, int(last) if last else None, quote)))
    for m in COMMAND.finditer(text):
        results.append((m.group(1), *check_command(opts.repo, m.group(1), m.group(2), m.group(3), opts.rerun, at_rev)))
    for what, verdict, note in results:
        print(f"{verdict:9} {what[:70]:70} {note}")
    bad = sum(1 for _, v, _ in results if v == "MISMATCH")
    print(f"итого: {len(results)} доказательств, расхождений {bad}, пропущено "
          f"{sum(1 for _, v, _ in results if v == 'SKIPPED')}; ревизия {rev[:12]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
