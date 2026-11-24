#!/usr/bin/env python3
"""Mechanical pre-acceptance of a pre-check card run (core, section 2, items 1-2) for Antigravity CLI headless runs.

  agy -p "<card task>" --agent precheck-mapper --output-format stream-json \
      --json-schema gauntlet/adapters/antigravity/report.schema.json > run.ndjson
  python3 -I gauntlet/adapters/antigravity/agy_card_check.py run.ndjson [<project>]

It judges the report by its evidence, not by the time or tokens the run spent:
  - the run finished normally: no ERROR status, no finished_reason, no denied_actions (a headless run that could not get
    an approval is soft-denied and still exits 0);
  - the structured report has every section of the core's format; coverage N of M, and N < M needs "not checked" items;
  - every "command" evidence names a command that appears among this run's tool calls (a claim of a run without the run
    is the failure seen in google-antigravity/antigravity-cli#1613);
  - every "file_line" evidence points at an existing file whose lines near that number contain the quote.
Exit 0: nothing flagged. Exit 1: flags, listed. The coordinator still re-checks at least one claim of every report itself.
The event layout of stream-json beyond these names (init, step_update, result, tool_info, status, finished_reason,
denied_actions; antigravity-cli CHANGELOG 1.1.8, 1.1.27, 1.4.11, 1.5.13) is not confirmed, so the search is structural.
"""
import json
import os
import re
import sys

REPORT_KEYS = ("card", "revision", "model", "summary", "coverage", "checked", "not_checked", "questions")
FILE_LINE = re.compile(r"`?([\w./-]+\.[\w]+):(\d+)`?")
QUOTE = re.compile(r"«([^»]{8,})»|\"([^\"]{8,})\"")
OUTPUT_KEY = re.compile(r"output|result|stdout|stderr|response|content", re.I)


def objects(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    try:
        return [json.loads(text)]
    except ValueError:
        out = []
        for line in text.splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out


def walk(node, found):
    if isinstance(node, dict):
        found.append(node)
        for value in node.values():
            walk(value, found)
    elif isinstance(node, list):
        for value in node:
            walk(value, found)
    elif isinstance(node, str) and node.strip().startswith("{"):
        try:
            walk(json.loads(node), found)       # a structured result may arrive as a JSON string
        except ValueError:
            pass


def strings(node):
    """The strings of a tool call without what the call returned: a command quoted in a file the agent read (its
    output) is not a command the agent ran."""
    if isinstance(node, dict):
        return [s for k, v in node.items() if not OUTPUT_KEY.search(str(k)) for s in strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in strings(v)]
    return [node] if isinstance(node, str) else []


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def command_of(evidence):
    ticked = re.search(r"`([^`]+)`", evidence)
    head = ticked.group(1) if ticked else re.split(r"→|->", evidence)[0]
    return squash(head)[:60]


def quote_near(project, rel, line, quote):
    path = os.path.join(project, rel)
    if not os.path.isfile(path):
        return False
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    window = squash(" ".join(lines[max(0, line - 4): line + 3]))
    return squash(quote)[:80] in window


def main(argv):
    run, project = argv[0], (argv[1] if len(argv) > 1 else os.getcwd())
    found = []
    for obj in objects(run):
        walk(obj, found)
    flags = []
    reports = [d for d in found if all(k in d for k in ("card", "checked", "not_checked"))]
    report = reports[-1] if reports else None
    status = [d["status"] for d in found if isinstance(d.get("status"), str)]
    if status and status[-1].upper() == "ERROR":
        flags.append(f"run status {status[-1]}")
    for d in found:
        if d.get("finished_reason"):
            flags.append(f"finished_reason: {d['finished_reason']} (the answer may be partial)")
        if d.get("denied_actions"):
            flags.append(f"denied_actions: {json.dumps(d['denied_actions'], ensure_ascii=False)[:300]}")
    if report is None:
        flags.append("no structured report (card/checked/not_checked) in the run output")
        return finish(flags)
    missing = [k for k in REPORT_KEYS if k not in report]
    if missing:
        flags.append(f"report misses: {', '.join(missing)}")
    cov = report.get("coverage") or {}
    covered, total = cov.get("covered"), cov.get("total")
    if not isinstance(covered, int) or not isinstance(total, int) or covered > total:
        flags.append(f"coverage is not N of M: {cov}")
    elif covered < total and not report.get("not_checked"):
        flags.append(f"coverage {covered} of {total} but the «not checked» section is empty")
    tools = [squash(s) for d in found for key in ("tool_info", "toolCall", "tool_call") if key in d
             for s in strings(d[key])]
    if not tools:
        flags.append("no tool calls found in the output: run with --output-format stream-json to check command evidence")
    for i, item in enumerate(report.get("checked") or [], 1):
        evidence = str(item.get("evidence") or "")
        if not evidence.strip():
            flags.append(f"checked #{i}: no evidence")
            continue
        if item.get("kind") == "command" and tools:
            command = command_of(evidence)
            if not any(command in t for t in tools):
                flags.append(f"checked #{i}: command not among this run's tool calls: {command!r}")
        if item.get("kind") == "file_line":
            where, said = FILE_LINE.search(evidence), QUOTE.search(evidence)
            if not where:
                flags.append(f"checked #{i}: no path:line in the evidence")
            elif said and not quote_near(project, where.group(1), int(where.group(2)), said.group(1) or said.group(2)):
                flags.append(f"checked #{i}: quote not found near {where.group(1)}:{where.group(2)}")
    print(f"report {report.get('card')!r}: {len(report.get('checked') or [])} checked, "
          f"{len(report.get('not_checked') or [])} not checked, coverage {covered} of {total}")
    return finish(flags)


def finish(flags):
    for flag in flags:
        print("FLAG " + flag)
    print("card check: " + ("nothing flagged" if not flags else f"{len(flags)} flag(s) - return the report or re-check"))
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) if len(sys.argv) > 1 else 2)
