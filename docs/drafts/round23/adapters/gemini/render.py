"""Render gemini.template.md into ../gemini.md, embedding the files from files/ verbatim."""
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "gemini.template.md"), encoding="utf-8").read()


def body(rel):
    return open(os.path.join(here, "files", rel), encoding="utf-8").read().rstrip("\n")


def size(rel):
    return f"{os.path.getsize(os.path.join(here, 'files', rel)):,}".replace(",", " ")


out = re.sub(r"\{\{file:([^}]+)\}\}", lambda m: body(m.group(1)), src)
out = re.sub(r"\{\{size:([^}]+)\}\}", lambda m: size(m.group(1)), out)
left = re.findall(r"\{\{[^}]+\}\}", out)
if left:
    sys.exit(f"unresolved placeholders: {left}")
target = os.path.join(here, "..", "gemini.md")
open(target, "w", encoding="utf-8").write(out)
print("written", os.path.realpath(target), len(out.encode()), "bytes", out.count("\n"), "lines")
