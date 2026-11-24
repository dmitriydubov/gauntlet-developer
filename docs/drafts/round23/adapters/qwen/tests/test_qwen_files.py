"""Static checks of the adapter's files against what Qwen Code 0.28.4 reads (docs at tag v0.28.4 and the package).

- agents: the frontmatter matches the package's regex (^---\\n…\\n---\\n) and parses as YAML; name = file name; tools
  are runtime tool ids (ToolNames in the package); background is a boolean; the prompt stays under the soft limits
  (system prompt 10 000 characters, description 1 000 - sub-agents.md, "Limits"); no ${name} placeholder that the
  package's templateString would replace;
- QWEN.md: one import, @gauntlet/CLAUDE.md, and no other bare @token outside code (findImports would try it);
- settings.json: valid JSON, the hook events are Qwen Code event names, command hook timeouts of 1000 or more are meant
  as milliseconds (hooks.md, "Command Hooks"), matchers compile.
Usage: python3 -I test_qwen_files.py <adapter files dir> <kit dir>
"""
import glob
import json
import os
import re
import sys

import yaml

FILES, KIT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
TOOL_IDS = {"exec", "edit", "write_file", "read_file", "zoom_image", "grep_search", "glob", "run_shell_command",
            "todo_write", "save_memory", "manage_memory", "search_memory", "agent", "skill", "exit_plan_mode",
            "enter_plan_mode", "web_fetch", "web_search", "image_gen", "list_directory", "lsp", "ask_user_question",
            "monitor", "notebook_edit", "tool_call", "tool_search", "send_message", "list_agents", "task_stop"}
EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch", "UserPromptSubmit", "UserPromptExpansion",
          "SessionStart", "SessionEnd", "SessionDelete", "MessageDisplay", "Stop", "StopFailure", "SubagentStart",
          "SubagentStop", "PreCompact", "PostCompact", "Notification", "PermissionRequest", "PermissionDenied",
          "TodoCreated", "TodoCompleted", "InstructionsLoaded", "FileChanged"}
failures = 0


def check(label, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f": {detail}"))


for path in sorted(glob.glob(os.path.join(FILES, ".qwen", "agents", "*.md"))):
    name = os.path.basename(path)[:-3]
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$", text)
    check(f"{name}: frontmatter block", bool(m))
    if not m:
        continue
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as error:
        check(f"{name}: frontmatter YAML", False, str(error).splitlines()[0])
        continue
    check(f"{name}: name = file name", fm.get("name") == name, fm.get("name"))
    tools = fm.get("tools") or []
    check(f"{name}: tools are runtime ids", isinstance(tools, list) and set(tools) <= TOOL_IDS, tools)
    check(f"{name}: background is boolean", isinstance(fm.get("background"), bool), fm.get("background"))
    check(f"{name}: prompt < 10000, description < 1000",
          len(m.group(2)) < 10000 and len(str(fm.get("description", ""))) < 1000)
    check(f"{name}: no ${{name}} placeholder", not re.search(r"\$\{[A-Za-z_]\w*\}", m.group(2)))

qwen = open(os.path.join(FILES, "QWEN.md"), encoding="utf-8").read()
no_code = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", qwen, flags=re.S))
imports = re.findall(r"(?:(?<=\s)|^)@([A-Za-z./][^\s]*)", no_code, flags=re.M)
check("QWEN.md: exactly one import, @gauntlet/CLAUDE.md", imports == ["gauntlet/CLAUDE.md"], imports)
kit_md = open(os.path.join(KIT, "gauntlet", "CLAUDE.md"), encoding="utf-8").read()
kit_no_code = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", kit_md, flags=re.S))
check("gauntlet/CLAUDE.md: no bare @token outside code",
      not re.findall(r"(?:(?<=\s)|^)@[A-Za-z./][^\s]*", kit_no_code, flags=re.M))

settings = json.load(open(os.path.join(FILES, ".qwen", "settings.json"), encoding="utf-8"))
check("settings.json: hook events are Qwen Code events", set(settings["hooks"]) <= EVENTS, set(settings["hooks"]) - EVENTS)
for event, groups in settings["hooks"].items():
    for group in groups:
        if "matcher" in group:
            try:
                re.compile(group["matcher"])
                check(f"settings.json: {event} matcher compiles", True)
            except re.error as error:
                check(f"settings.json: {event} matcher compiles", False, error)
        for hook in group["hooks"]:
            t = hook.get("timeout")
            seconds = t / 1000 if t and t >= 1000 else t
            check(f"settings.json: {event} timeout {t} = {seconds} s", seconds is None or 0 < seconds <= 7200)
            check(f"settings.json: {event} hook has no name (cannot be disabled one by one)", "name" not in hook)
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
