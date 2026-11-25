#!/usr/bin/env python3
"""Kimi Code CLI -> gauntlet hooks bridge (gauntlet/adapters/kimi/kimi_hooks.py).

Kimi Code CLI (npm @moonshot-ai/kimi-code; written against 2.7.3) runs hooks only from the user's config.toml or a
local plugin: there is no project hook file. Its events differ from what the kit's hooks read:
  - Write and Edit name the file in tool_input.path, not file_path, and Bash may carry its own cwd: guard.py alone
    sees no path and lets every edit through;
  - no event names the agent (no agent_type, no agent_id): PreToolUse and Stop run for the main agent and for every
    subagent alike, so the role scopes of guard.py cannot apply and a subagent's Stop looks like the main agent's;
  - Stop always sends stop_hook_active=false, and Kimi itself does not run the Stop hook again for the turn a block
    continued: one forced continuation per turn of the user. A hook may run at most 600 s;
  - SessionStart output never reaches the model.
This bridge rewrites each event into the shape the kit's hooks read and runs those hooks unchanged.

  kimi_hooks.py session-start    SessionStart: session_start.sh; its status line is saved next to stop_gate.py's state
                                 (git-path gauntlet-hook, file kimi-status-<session>.txt)
  kimi_hooks.py prompt           UserPromptSubmit: prints that status line once per session (Kimi adds a hook's plain
                                 stdout to the context)
  kimi_hooks.py turn             TurnStarted: remembers which turns belong to subagents, for the Stop hook (only a
                                 subagent's first turn is marked as such; see turn())
  kimi_hooks.py guard            PreToolUse: guard.py on the rewritten event; Kimi's instructions, agents, configuration
                                 (including the project-root .mcp.json Kimi loads) and the user's Kimi data directory
                                 count as human-owned too
  kimi_hooks.py stop ARGS...     Stop: stop_gate.py ARGS for a turn of the main agent; a subagent's turn passes, and so
                                 does a turn that ends while a gauntlet Gradle run holds the build lock (the run's
                                 completion starts a new turn). The Gradle timeout is kept under Kimi's 600 s limit
  kimi_hooks.py report [--commit SHA] [FILE]
                                 not a hook: checks a subagent's report against the form of core.md section 3
                                 (four sections, coverage "N из M", evidence on every claim); exit 1 lists the gaps

The hooks live in the user's configuration and would run the guard of ANY repository Kimi opens, so the bridge acts only
in checkouts listed in $KIMI_CODE_HOME/gauntlet-projects.txt (default ~/.kimi-code/gauntlet-projects.txt; one absolute
directory per line; a listed directory covers everything under it, worktrees included). Everywhere else it exits 0.
Like the kit's hooks it fails open on input it cannot read: a broken hook must not brick a session; CI stays the judge.
Humans switch it off with the kit's own variables (GAUNTLET_GUARD=off, GAUNTLET_STOP_HOOK=off) or by removing the hooks.
"""
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time

try:
    import fcntl
except ImportError:                      # Windows: no POSIX locks, the build-lock check is skipped
    fcntl = None

sys.dont_write_bytecode = True          # importing guard.py must not leave __pycache__ inside gauntlet/

HOOK_LIMIT_S = 600                       # Kimi: [[hooks]] timeout is 1..600 s
GRADLE_BUDGET_S = 560                    # what stop_gate.py may spend on Gradle in all modules together
MIN_MODULE_TIMEOUT_S = 60
# Paths a Kimi agent must not change on top of guard.py's HUMAN_OWNED: its instructions and project configuration.
# .mcp.json: Kimi Code 2.7.3 loads the project-root .mcp.json as a project MCP layer once the folder is trusted
# (app/mcpConfig/configLoader.ts), and its stdio servers start with every new session, outside any tool hook.
KIMI_OWNED = ("AGENTS.md", "agents.md", ".kimi-code/", ".agents/", ".mcp.json")
# Inside the user's Kimi data directory only session data is the agent's (plan files, saved tool output).
KIMI_HOME_WRITABLE = ("sessions",)
REPORT_SECTIONS = ("## Итог", "## Проверено", "## Не проверено", "## Вопросы и риски")
COVERAGE = re.compile(r"покрытие:\s*(\d+)\s*из\s*(\d+)", re.I)
EVIDENCE = re.compile(r"доказательство\s*[:—-]", re.I)
NOTHING_FOUND = re.compile(r"ничего не найдено|не найдено|нет вызовов|вызовов (больше )?нет|0 совпадений", re.I)
SEARCH_COMMAND = re.compile(r"`[^`]*\b(rg|grep|git grep|find|fd|Grep|Glob|git log|javap|jar)\b[^`]*`")
STOP_NOTE = ("\n[gauntlet/Kimi] Kimi продолжает ход по этому сообщению один раз и после продолжения Stop-хук не "
             "проверяет его снова. Поэтому перед отчётом сам прогони ./gradlew gauntletFast --continue (долгий прогон — "
             "фоновой задачей Bash без тайм-аута) и приложи к отчёту строки «> Task …» каждой задачи гейта и итог "
             "BUILD SUCCESSFUL/FAILED. Красное — так и напиши: работа НЕ сделана. Если ты сабагент (роль или карточка "
             "gauntlet), это сообщение про всю рабочую копию: правь только в пределах своей роли (карточки и reviewer "
             "не правят ничего), остальное — в итог для вызывающего.\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "report":
        return report(sys.argv[2:])
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        return 0
    if not isinstance(event, dict):
        return 0
    root = project_root(event.get("cwd") or os.getcwd())
    if root is None or not listed(root) or not os.path.isfile(os.path.join(root, "gauntlet", "hooks", "guard.py")):
        return 0
    os.environ["CLAUDE_PROJECT_DIR"] = root          # the kit's hooks read the project from it
    handlers = {"session-start": session_start, "prompt": prompt, "turn": turn, "guard": guard}
    if mode in handlers:
        return handlers[mode](event, root)
    if mode == "stop":
        return stop(event, root, sys.argv[2:])
    sys.stderr.write(f"kimi_hooks.py: unknown mode {mode!r}\n")
    return 0


# ----------------------------------------------------------------------------- shared

def git(cwd, *args):
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def project_root(cwd):
    if not cwd or not os.path.isdir(cwd):
        return None
    top = git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(top) if top else None


def kimi_home():
    return os.path.realpath(os.path.expanduser(os.environ.get("KIMI_CODE_HOME") or "~/.kimi-code"))


def listed(root):
    try:
        with open(os.path.join(kimi_home(), "gauntlet-projects.txt"), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return False
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        base = os.path.realpath(os.path.expanduser(entry))
        if root == base or root.startswith(base.rstrip(os.sep) + os.sep):
            return True
    return False


def state_dir(root):
    """stop_gate.py's state folder (per working copy): git-path gauntlet-hook."""
    path = git(root, "rev-parse", "--git-path", "gauntlet-hook")
    if not path:
        return None
    path = path if os.path.isabs(path) else os.path.join(root, path)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    return path


def safe(text):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(text))[:120] or "unknown"


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def write(path, text):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


# ----------------------------------------------------------------------------- SessionStart / UserPromptSubmit

def session_start(event, root):
    claude = {"hook_event_name": "SessionStart", "session_id": event.get("session_id"), "cwd": root,
              "source": event.get("source")}
    try:
        proc = subprocess.run(["bash", os.path.join(root, "gauntlet", "hooks", "session_start.sh")],
                              input=json.dumps(claude).encode(), cwd=root, capture_output=True, timeout=170)
        lines = [l for l in proc.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
        status = lines[-1] if lines else "[gauntlet] WARNING: session_start.sh printed nothing"
    except (OSError, subprocess.SubprocessError) as e:
        status = f"[gauntlet] WARNING: session_start.sh did not run: {e}"
    folder = state_dir(root)
    if folder:
        write(os.path.join(folder, f"kimi-status-{safe(event.get('session_id'))}.txt"), status + "\n")
    return 0


def prompt(event, root):
    folder = state_dir(root)
    if not folder:
        return 0
    session = safe(event.get("session_id"))
    shown = os.path.join(folder, f"kimi-status-{session}.shown")
    if os.path.exists(shown):
        return 0
    status = read(os.path.join(folder, f"kimi-status-{session}.txt")).strip()
    if not status:
        status = ("[gauntlet] WARNING: SessionStart hook of the Kimi bridge left no status line - the SessionStart hook "
                  "is missing or failed, so the guard and the Stop gate may not work either. Say so in your first "
                  "message.")
    sys.stdout.write(status + "\n")
    write(shown, time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")
    return 0


# ----------------------------------------------------------------------------- TurnStarted / turn origins

def turns_file(root, session):
    folder = state_dir(root)
    return os.path.join(folder, f"kimi-turns-{safe(session)}.jsonl") if folder else None


def locked(path, update):
    """Read, change and rewrite the JSON-lines file under an exclusive lock; update(records) returns the result."""
    try:
        f = open(path, "a+", encoding="utf-8")
    except OSError:
        return None
    with f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        records = []
        for line in f.read().splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
        result = update(records)
        f.seek(0)
        f.truncate()
        f.write("".join(json.dumps(r) + "\n" for r in records[-200:]))
        return result


def turn(event, root):
    """Record a TurnStarted. Only a subagent's first turn says so (origin system_trigger/subagent); a turn that a
    finished background task starts (origin `task`) names no agent, so a subagent's such turn is gated like the main
    agent's: erring towards one gate run too many, never towards a main turn let through red."""
    path = turns_file(root, event.get("session_id"))
    if path:
        record = {"turn": str(event.get("turn_id")), "kind": event.get("origin_kind"), "name": event.get("origin_name"),
                  "t": time.time()}
        locked(path, lambda records: records.append(record))
    return 0


def turn_origin(root, event):
    """The origin recorded for the turn that is stopping: the latest unclaimed TurnStarted with the same turn id.
    Turn ids count per agent, so the main agent and a subagent share small numbers; claiming the latest record first
    matches nested foreground subagents, whose turns start after and end before the turn that called them."""
    path = turns_file(root, event.get("session_id"))
    if not path or not os.path.exists(path):
        return None
    wanted = str(event.get("turn_id"))

    def claim(records):
        for i in range(len(records) - 1, -1, -1):
            if records[i].get("turn") == wanted:
                return records.pop(i).get("name")
        return None
    return locked(path, claim)


# ----------------------------------------------------------------------------- PreToolUse

def guard(event, root):
    tool = event.get("tool_name") or ""
    params = event.get("tool_input") or {}
    if not isinstance(params, dict):
        return 0
    base = event.get("cwd") or root
    if tool in ("Write", "Edit"):
        path = params.get("path") or params.get("file_path") or ""
        if not isinstance(path, str) or not path:
            return 0
        path = os.path.expanduser(path)
        claude_input = {"file_path": path if os.path.isabs(path) else os.path.join(base, path)}
        cwd = base
    elif tool == "Bash":
        command = params.get("command")
        if not isinstance(command, str):
            return 0
        claude_input = {"command": command}
        cwd = params.get("cwd") if isinstance(params.get("cwd"), str) and params.get("cwd") else base
        cwd = os.path.join(base, os.path.expanduser(cwd)) if not os.path.isabs(os.path.expanduser(cwd)) else cwd
    else:
        return 0
    claude = {"hook_event_name": "PreToolUse", "session_id": event.get("session_id"), "cwd": cwd,
              "tool_name": tool, "tool_input": claude_input}
    verdict = judge(claude, root)
    if verdict:
        sys.stdout.write(verdict)
    return 0


def load_guard(root):
    spec = importlib.util.spec_from_file_location("gauntlet_guard", os.path.join(root, "gauntlet", "hooks", "guard.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HUMAN_OWNED = tuple(module.HUMAN_OWNED) + tuple(p for p in KIMI_OWNED if p not in module.HUMAN_OWNED)
    kit_check = module.user_config_violation

    def user_config_violation(path):
        return kit_check(path) or kimi_user_violation(path)

    module.user_config_violation = user_config_violation
    return module


def kimi_user_violation(path):
    if not path:
        return None
    target = os.path.expanduser(path)
    if not os.path.isabs(target):
        return None
    target = os.path.realpath(target)
    home = kimi_home()
    if target == home or target.startswith(home + os.sep):
        inner = os.path.relpath(target, home).split(os.sep)[0]
        if inner not in KIMI_HOME_WRITABLE:
            return (f"{home} is the user's Kimi Code configuration (hooks, permission rules, SYSTEM.md, agents, "
                    f"plugins): it could switch the guard off. Do not touch it.")
    agents_home = os.path.realpath(os.path.expanduser("~/.agents"))
    if target == agents_home or target.startswith(agents_home + os.sep):
        return f"{agents_home} holds the user's instructions, agents and skills for every agent tool. Do not touch it."
    return None


def judge(claude, root):
    """guard.py's verdict on one rewritten event: its JSON output, or '' when it allows the call. A Write or Edit in a
    feature directory is judged as the specifier's: Kimi does not name the calling agent, so before the spec commit
    any agent may write the draft, and after it the spec is frozen for everyone."""
    try:
        module = load_guard(root)
    except Exception:                                    # the kit changed or is broken: run guard.py as it is
        proc = subprocess.run([sys.executable, "-I", "-B", os.path.join(root, "gauntlet", "hooks", "guard.py")],
                              input=json.dumps(claude), capture_output=True, text=True, cwd=root)
        return proc.stdout.strip()
    if claude["tool_name"] in ("Write", "Edit"):
        try:
            ctx = module.Context(root)
            rel = ctx.relative(claude["tool_input"]["file_path"])
            if rel is not None and module.is_under(rel, ctx.features_dirs):
                claude["agent_type"] = "specifier"
        except Exception:
            pass
    stdin, stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(json.dumps(claude)), io.StringIO()
    try:
        module.main()
        out = sys.stdout.getvalue()
    except SystemExit:
        out = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = stdin, stdout
    return out.strip()


# ----------------------------------------------------------------------------- Stop

def stop(event, root, args):
    if event.get("hook_event_name") not in (None, "Stop"):
        return 0
    if turn_origin(root, event) == "subagent":
        return 0                         # a subagent's turn: its caller's own turn end is gated
    if gradle_running(root):
        return 0                         # a gauntlet Gradle run is in progress; its completion starts a new turn
    claude = {"hook_event_name": "Stop", "session_id": event.get("session_id"), "cwd": root,
              "stop_hook_active": False}
    try:
        proc = subprocess.run([sys.executable, "-I", "-B", os.path.join(root, "gauntlet", "hooks", "stop_gate.py")]
                              + capped(args, root), input=json.dumps(claude), capture_output=True, text=True, cwd=root,
                              timeout=HOOK_LIMIT_S - 15)
    except (OSError, subprocess.SubprocessError):
        return 0
    if proc.returncode == 2:
        sys.stderr.write(proc.stderr.rstrip("\n") + "\n" + STOP_NOTE)
        return 2
    return 0                             # green, nothing to check, or a reminder Kimi would not show anyway


def modules(root):
    """The Gradle build directories of gauntlet.properties' `module` (comma-separated; empty = the repository root)."""
    props = {}
    for line in read(os.path.join(root, "gauntlet", "config", "gauntlet.properties")).splitlines():
        m = re.match(r"\s*([^#!\s=:][^=:\s]*)\s*[=:\s]\s*(.*)$", line)
        if m:
            props[m.group(1)] = m.group(2).strip()
    found = []
    for entry in props.get("module", "").split(","):
        d = os.path.normpath(entry.strip()).strip("/") if entry.strip() else ""
        if d and d != "." and d not in found:
            found.append(d)
    return found


def capped(args, root):
    """stop_gate.py runs Gradle in every affected module one after another, each up to --timeout: keep the sum under
    Kimi's hook limit, or Kimi kills the hook and lets the agent stop without a verdict."""
    per_module = max(MIN_MODULE_TIMEOUT_S, GRADLE_BUDGET_S // max(1, len(modules(root))))
    out, i, asked = [], 0, None
    while i < len(args):
        if args[i] == "--timeout" and i + 1 < len(args):
            try:
                asked = int(args[i + 1])
            except ValueError:
                asked = None
            i += 2
            continue
        out.append(args[i])
        i += 1
    return out + ["--timeout", str(min(asked, per_module) if asked else per_module)]


def gradle_running(root):
    """Is any module's .gradle/gauntlet-build.lock held? gauntlet.gradle holds it (FileChannel.lock, a POSIX record lock
    on Linux) from the first gate task until the build ends."""
    if fcntl is None:
        return False
    dirs = [root] + [os.path.join(root, m) for m in modules(root)]
    for d in dirs:
        path = os.path.join(d, ".gradle", "gauntlet-build.lock")
        if not os.path.isfile(path):
            continue
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError:
            continue
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.lockf(fd, fcntl.LOCK_UN)
        except OSError:
            return True
        finally:
            os.close(fd)
    return False


# ----------------------------------------------------------------------------- report form (core.md, section 3)

def report(argv):
    commit, path, i = None, None, 0
    while i < len(argv):
        if argv[i] == "--commit" and i + 1 < len(argv):
            commit, i = argv[i + 1], i + 2
        else:
            path, i = argv[i], i + 1
    try:
        text = read(path) if path else sys.stdin.read()
    except OSError:
        text = ""
    gaps = report_gaps(text, commit)
    if gaps:
        sys.stdout.write("Отчёт не по форме (ядро, раздел 3) — вернуть сабагенту с перечнем:\n"
                         + "".join(f"- {g}\n" for g in gaps))
        return 1
    sys.stdout.write("Форма отчёта соблюдена. Содержание проверяет координатор: выборочная перепроверка и "
                     "опровержение ключевых утверждений (ядро, раздел 2).\n")
    return 0


def sections(text):
    found, current = {}, None
    for line in text.splitlines():
        head = next((s for s in REPORT_SECTIONS if line.strip().startswith(s)), None)
        if head:
            current = head
            found[current] = [line]
        elif current:
            found[current].append(line)
    return found


def report_gaps(text, commit=None):
    gaps = []
    if not text.strip():
        return ["отчёт пуст"]
    found = sections(text)
    for s in REPORT_SECTIONS:
        if s not in found:
            gaps.append(f"нет раздела «{s}»")
    checked = found.get("## Проверено", [])
    m = COVERAGE.search(checked[0] if checked else "") or COVERAGE.search("\n".join(checked))
    covered = total = None
    if not m:
        gaps.append("в «## Проверено» нет покрытия числом: «покрытие: N из M»")
    else:
        covered, total = int(m.group(1)), int(m.group(2))
        if covered > total:
            gaps.append(f"покрытие {covered} из {total}: N больше M")
    items = []                                   # a numbered claim and the lines that continue it
    for line in checked[1:]:
        if re.match(r"\s*\d+[.)]\s", line):
            items.append(line)
        elif items and line.strip():
            items[-1] += "\n" + line
    if checked and not items:
        gaps.append("в «## Проверено» нет ни одного пронумерованного утверждения")
    for line in items:
        number = re.match(r"\s*(\d+)", line).group(1)
        if not EVIDENCE.search(line):
            gaps.append(f"утверждение {number} без «доказательство:» (команда и вывод, файл:строка с цитатой или "
                        f"источник версии с цитатой) — либо в «Не проверено»")
        elif NOTHING_FOUND.search(line) and not SEARCH_COMMAND.search(line):
            gaps.append(f"утверждение {number}: «ничего не найдено» без команды поиска (чем, где, сколько совпадений)")
    unchecked = [l for l in found.get("## Не проверено", [])[1:] if l.strip() and l.strip() not in ("-", "—")]
    if "## Не проверено" in found and not unchecked and covered is not None and covered < total:
        gaps.append(f"покрытие {covered} из {total}, а «## Не проверено» пуст: назови, что не осмотрено, почему и чем грозит")
    if commit and commit[:7] not in text:
        gaps.append(f"отчёт не называет коммит, на котором проверял ({commit[:12]})")
    return gaps


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:                       # fail open: a broken bridge must not brick the session
        sys.stderr.write(f"kimi_hooks.py: {type(e).__name__}: {e}\n")
        sys.exit(0)
