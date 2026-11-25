#!/usr/bin/env python3
"""Прослойка между хуками Codex и хуками набора gauntlet (предложение для PR владельца набора).

Место в наборе: gauntlet/adapters/codex/codex_hooks.py. Вызывается из .codex/hooks.json:

  codex_hooks.py guard    PreToolUse (Bash, apply_patch, spawn_agent): приводит событие Codex к виду, который
                          понимает gauntlet/hooks/guard.py, и печатает его решение. Патч разбирается на файлы
                          (*** Add/Update/Delete File, *** Move to) так же, как его читает парсер Codex (строка
                          обрезается с обеих сторон), - каждый файл судится как Write. Это касается и инструмента
                          apply_patch, и вызова apply_patch из оболочки (heredoc, который Codex перехватывает,
                          и исполняемый файл apply_patch в PATH): хук видит такой вызов как Bash, а guard.py тело
                          heredoc считает данными. apply_patch из оболочки без текста патча в команде (файл,
                          переменная, stdin) отклоняется: его файлы хуку не видны. Карточки пред-проверки
                          (precheck_*, review_repro) судятся с правами reviewer (только чтение). spawn_agent:
                          роль или карточка набора запускается только без истории родителя, а сами роли и карточки
                          своих субагентов не запускают.
  codex_hooks.py context  SessionStart / SubagentStart: печатает gauntlet/CLAUDE.md, а субагенту-роли ещё и
                          .claude/agents/<agent_type>.md - тексты набора попадают в контекст без копии.
  codex_hooks.py report   SubagentStop карточек и reviewer: проверяет форму отчёта (core.md, разделы 3 и 4.5).
                          Форма не та - возвращает субагента с перечнем недостающего (exit 2), не больше двух
                          раз на агента; дальше отпускает с предупреждением, а координатор ставит «не проверено».

Хук только проверяет. Как и guard.py, при испорченном входе он ничего не запрещает (fail open): опора - CI.
Исключение одно: apply_patch из оболочки без видимого текста патча (см. выше). GAUNTLET_GUARD=off выключает
guard и здесь (админ-окружение человека).
"""
import json
import os
import re
import subprocess
import sys

READ_ONLY_AGENTS = re.compile(r"^(precheck_[a-z_]+|review_repro)$")
KIT_AGENTS = re.compile(r"^(specifier|hardener|reviewer|precheck_[a-z_]+|review_repro)$")
# Маркеры codex-rs/apply-patch/src/parser.rs; парсер сравнивает их с обрезанной строкой (streaming_parser.rs).
PATCH_MARKERS = ("*** Add File: ", "*** Update File: ", "*** Delete File: ", "*** Move to: ")
APPLY_PATCH_WORD = re.compile(r"(?<![\w.-])(?:apply_patch|applypatch)(?![\w.-])")
# apply_patch на месте команды: в начале, после ; & | ( ` $( или -c '...', в том числе через env/xargs/exec и т. п.
APPLY_PATCH_CALL = re.compile(
    r"(?:^|[;&|(\n`]|\$\(|-[a-z]*c\s+['\"])\s*(?:\w+=\S*\s+)*"
    r"(?:(?:sudo|env|command|exec|nohup|time|xargs)(?:\s+-\S+)*\s+(?:\w+=\S*\s+)*)*"
    r"(?:\S*/)?(?:apply_patch|applypatch)(?![\w.-])")
# Перехват Codex принимает только `cd <слово> && apply_patch <<...` (codex-rs/apply-patch/src/invocation.rs).
CD_PREFIX = re.compile(r"\A\s*cd\s+([^\s;&|<>'\"]+)\s*&&")
# spawn_agent v1 - "spawn_agent"; v2 - то же имя в пространстве имён (по умолчанию collaboration): ищем по концу.
SPAWN_TOOL = re.compile(r"spawn_agent$")
INTERACTIVE = {"bash", "sh", "zsh", "dash", "ksh", "fish", "python", "python3", "node", "perl", "ruby", "irb"}
CARD_SECTIONS = ("## Итог", "## Проверено (покрытие:", "## Не проверено", "## Вопросы и риски для координатора")
MAX_RETURNS = 2


def project():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def ask_guard(event):
    """Решение guard.py набора на одно событие: пустая строка - разрешено."""
    try:
        done = subprocess.run([sys.executable, "-I", os.path.join(project(), "gauntlet", "hooks", "guard.py")],
                              input=json.dumps(event), capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip()


def deny(reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                              "permissionDecisionReason": "[gauntlet codex] " + reason}})


def patch_targets(text):
    """Пути из текста патча так, как их находит парсер Codex: строка обрезается с обеих сторон, затем сравнивается
    с маркером. Лишний найденный путь безопасен: он только добавляет проверку."""
    targets = []
    for line in text.split("\n"):
        line = line.strip()
        for marker in PATCH_MARKERS:
            if line.startswith(marker) and line[len(marker):].strip():
                targets.append(line[len(marker):].strip())
    return targets


def judge_patch(event, text, cwd):
    for target in patch_targets(text):
        path = target if os.path.isabs(target) else os.path.join(cwd, target)
        verdict = ask_guard(dict(event, tool_name="Write", tool_input={"file_path": path}))
        if verdict:
            return verdict
    return ""


def spawn_inherits_history(args):
    """v1: история родителя только при fork_context = true. v2 (у вызова есть обязательный task_name): fork_turns
    по умолчанию "all" - вся история родителя (codex-rs/core/src/tools/handlers/multi_agents_spec.rs)."""
    if args.get("fork_context") is True:
        return True
    turns = args.get("fork_turns")
    if turns is None:
        return "task_name" in args
    return str(turns).strip().lower() != "none"


def guard_spawn(caller, args):
    if KIT_AGENTS.match(caller):
        return deny(f"Роль или карточка набора ({caller}) своих субагентов не запускает: её работа - её чек-лист.")
    role = str(args.get("agent_type") or "")
    if KIT_AGENTS.match(role) and spawn_inherits_history(args):
        return deny(f"{role} запускается без истории родителя: передайте fork_turns: \"none\" (в инструменте v1 - "
                    f"fork_context: false или без него). Опровергатель не должен видеть чужой вывод, роль - работать "
                    f"в чужом контексте; всё нужное - в сообщении задачи.")
    return ""


def guard(event):
    if os.environ.get("GAUNTLET_GUARD", "").lower() == "off":
        return ""
    caller = event.get("agent_type") or ""
    if READ_ONLY_AGENTS.match(caller):
        event = dict(event, agent_type="reviewer")
    tool = event.get("tool_name") or ""
    params = event.get("tool_input")
    if SPAWN_TOOL.search(tool):
        return guard_spawn(caller, params) if isinstance(params, dict) else ""
    command = params.get("command") if isinstance(params, dict) else None
    if not isinstance(command, str):
        return ""
    cwd = event.get("cwd") or project()
    if tool == "apply_patch":
        return judge_patch(event, command, cwd)
    if tool == "Bash":
        words = command.split()
        if words and os.path.basename(words[0]) in INTERACTIVE and all(w in ("-i", "-l", "-il", "-li") for w in words[1:]):
            return deny("Интерактивная оболочка: команды, которые потом уйдут в неё через write_stdin, хуки Codex не "
                        "видят. Запускайте каждую команду отдельным вызовом.")
        if APPLY_PATCH_WORD.search(command):
            if patch_targets(command):
                cd = CD_PREFIX.match(command)
                verdict = judge_patch(event, command, os.path.join(cwd, os.path.expanduser(cd.group(1))) if cd else cwd)
                if verdict:
                    return verdict
            elif APPLY_PATCH_CALL.search(command):
                return deny("apply_patch из оболочки без текста патча в самой команде (файл, переменная, stdin): хук "
                            "не видит, какие файлы он меняет. Правьте файлы инструментом apply_patch или heredoc с "
                            "патчем прямо в команде.")
        return ask_guard(event)
    return ""


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def context(event):
    parts = []
    role = event.get("agent_type") or ""
    if event.get("hook_event_name") == "SubagentStart" and re.fullmatch(r"[a-z_]+", role):
        text = read_text(os.path.join(project(), ".claude", "agents", role + ".md"))
        if text:
            text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)   # frontmatter - настройка Claude Code
            parts.append(f"# Роль набора gauntlet: {role} (текст .claude/agents/{role}.md; поправки для Codex - "
                         f"в developer_instructions роли, они главнее там, где расходятся)\n\n{text}")
    rules = read_text(os.path.join(project(), "gauntlet", "CLAUDE.md"))
    if rules:
        parts.append("# gauntlet/CLAUDE.md (процесс и жёсткие правила набора; поправки для Codex - в AGENTS.md)\n\n"
                     + rules)
    return "\n\n".join(parts)


def card_gaps(text):
    gaps = [f"нет раздела «{s}»" for s in CARD_SECTIONS if s not in text]
    head = re.search(r"^## Проверено \(покрытие: (\d+) из (\d+)", text, re.M)
    if "## Проверено (покрытие:" in text and not head:
        gaps.append("покрытие не числом: нужно «## Проверено (покрытие: N из M по чек-листу)»")
    checked = re.search(r"^## Проверено.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if checked:
        claims = re.split(r"^(?=\d+\. )", checked.group(1), flags=re.M)
        for claim in claims:
            number = re.match(r"(\d+)\. ", claim)
            if number and "доказательство:" not in claim:
                gaps.append(f"утверждение {number.group(1)} без «доказательство:» (команда и вывод, файл:строка с "
                            f"цитатой или источник с версией) - докажите или перенесите в «Не проверено»")
    unchecked = re.search(r"^## Не проверено[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if head and int(head.group(1)) < int(head.group(2)) and not (unchecked and re.search(r"^\s*- \S", unchecked.group(1), re.M)):
        gaps.append(f"покрытие {head.group(1)} из {head.group(2)}, а раздел «Не проверено» пуст: назовите, что не "
                    f"осмотрено, почему и чем это грозит")
    return gaps


def reviewer_gaps(text):
    gaps = []
    if not re.search(r"^VERDICT: (APPROVED|CHANGES REQUESTED)[ \t]*$", text, re.M):
        gaps.append("нет строки «VERDICT: APPROVED | CHANGES REQUESTED»")
    if not re.search(r"^Осмотрено: .*?\b\d+ из \d+", text, re.M):
        gaps.append("нет строки «Осмотрено: файлы диффа N из M, …» (что именно осмотрено)")
    if not re.search(r"^Residual risks:", text, re.M):
        gaps.append("нет строки «Residual risks: …»")
    return gaps


def state_file(agent_id):
    try:
        git_dir = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=project(), capture_output=True,
                                 text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not git_dir:
        return None
    folder = os.path.join(project(), git_dir, "gauntlet-hook")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "report-" + re.sub(r"[^A-Za-z0-9_.-]", "_", agent_id or "unknown"))


def report(event):
    text = event.get("last_assistant_message")
    if not text:
        print(json.dumps({"systemMessage": "[gauntlet codex] итоговое сообщение субагента хуку не видно: форму "
                                           "отчёта проверит координатор"}))
        return 0
    gaps = reviewer_gaps(text) if event.get("agent_type") == "reviewer" else card_gaps(text)
    if not gaps:
        return 0
    path = state_file(event.get("agent_id"))
    returns = int(read_text(path).strip() or 0) if path else 0
    if returns >= MAX_RETURNS:
        print(json.dumps({"systemMessage": f"[gauntlet codex] отчёт {event.get('agent_type')} не принят по форме после "
                                           f"{MAX_RETURNS} возвратов: координатор ставит его утверждениям «не проверено»"}))
        return 0
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(returns + 1))
    sys.stderr.write(f"[gauntlet] Отчёт не принят по форме (возврат {returns + 1} из {MAX_RETURNS}). Это доработка "
                     f"отчёта, а не новый круг работы: допишите недостающее и пришлите отчёт целиком заново.\n- "
                     + "\n- ".join(gaps) + "\n")
    return 2


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if mode == "guard":
        verdict = guard(event)
        if verdict:
            print(verdict)
        return 0
    if mode == "context":
        text = context(event)
        if text:
            print(text)
        return 0
    if mode == "report":
        return report(event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
