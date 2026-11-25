"""Render qwen.template.md into ../qwen.md, embedding the files from files/ verbatim.

{{file:<path>}}  the file's text (trailing newlines stripped)
{{size:<path>}}  its size in bytes, grouped by thin spaces
"""
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "qwen.template.md"), encoding="utf-8").read()


def path(rel):
    return os.path.join(here, "files", rel)


def body(rel):
    text = open(path(rel), encoding="utf-8").read().rstrip("\n")
    return text


def size(rel):
    return f"{os.path.getsize(path(rel)):,}".replace(",", " ")


out = re.sub(r"\{\{file:([^}]+)\}\}", lambda m: body(m.group(1)), src)
out = re.sub(r"\{\{size:([^}]+)\}\}", lambda m: size(m.group(1)), out)
left = re.findall(r"\{\{[^}]+\}\}", out)
if left:
    sys.exit(f"unresolved placeholders: {left}")
target = os.path.join(here, "..", "qwen.md")
open(target, "w", encoding="utf-8").write(out)
print("written", os.path.realpath(target), len(out.encode()), "bytes", out.count("\n"), "lines")
