# Адаптер gauntlet для OpenAI Codex

Состояние на 2026-11-24. Сверено с Codex CLI 0.172.0 (npm `@openai/codex`, опубликован 2026-11-24), документацией
Codex (адреса `developers.openai.com/codex/…` с ноября 2026 переадресуют на `learn.chatgpt.com/docs/…`) и исходниками
репозитория `openai/codex` по тегу `rust-v0.172.0`. Источники с датами — раздел D.5. Адаптер переносит ядро
(`round23/core.md`: правило тщательности, приёмка отчётов, формат отчёта, карточки) и механизмы набора в форматы Codex,
ничего из них не ослабляя. Где Codex чего-то не умеет, это сказано прямо и назван запасной путь.

## A. Что это и куда ставить

### A.1. Продукт и версия

- **Codex CLI** — `codex` (npm `@openai/codex@0.172.0`; пакет — обёртка над бинарником на Rust). Хуки, свои агенты,
  песочница и `config.toml` в документации описаны общими для CLI, расширения IDE и настольного приложения (доверие
  хукам — `/hooks` в CLI или Settings > Hooks в приложении). Адаптер рассчитан на локальный запуск.
- **Codex Cloud** — облачные задачи в своих виртуальных машинах. Работают ли там хуки проекта, документация не
  говорит (D.4). Для облака адаптер считает, что хуков нет, и действует запасной путь (AGENTS.md, раздел 3; CI).
- **Модели** (страница Models на 2026-11-24): `gpt-6.2-astra` (сложная работа), `gpt-6.2-sol` (повседневная),
  `gpt-6.1-terra`, `gpt-6-luna` (быстрая узкая работа) и др.; уровень рассуждений `model_reasoning_effort` — `low`,
  `medium`, `high`, `xhigh`, `max`, `ultra`, смотря что объявляет модель. `ultra` — аналог «Ultracode»: максимум
  рассуждений и делегирование субагентам по собственному решению модели.

### A.2. Главное

1. **Хуки Codex совместимы с хуками набора по контракту.** События `SessionStart`, `PreToolUse`, `Stop`,
   `SubagentStart`, `SubagentStop`; на stdin — JSON, где есть все поля, которые читают скрипты набора (`session_id`,
   `cwd`, `tool_name`, `tool_input.command`, `agent_type`, `stop_hook_active`); exit 2 с причиной в stderr и
   `hookSpecificOutput.permissionDecision = "deny"` значат то же, что у Claude Code. Скрипты набора (`session_start.sh`, `guard.py`, `stop_gate.py`)
   работают на событиях Codex без правки кода: это проверено прогоном на синтетических событиях по схемам Codex 0.172.0
   (D.3). Нужен `CLAUDE_PROJECT_DIR` в команде хука: Codex его не задаёт. И одна поправка в команде: строку статуса
   `session_start.sh` («[gauntlet] active - …») Codex принимает за испорченный JSON — вывод `SessionStart`, который
   начинается с «[» или «{», он разбирает как JSON, а не как текст, — и в контекст её не кладёт; поэтому команда хука
   ставит перед ней приставку `gauntlet status: ` («Проверка», п. 1).
2. **Одна дыра в охране: правки файлов.** Codex правит файлы инструментом `apply_patch`; хук видит его как
   `tool_name: "apply_patch"` с текстом патча в `tool_input.command`. `guard.py` такого инструмента не знает и
   пропускает любой патч — в том числе в `gauntlet/` (проверено, D.3). Тот же патч Codex применяет и из оболочки:
   heredoc `apply_patch <<'EOF' … EOF` в `exec_command` он перехватывает сам, а `apply_patch` лежит в `PATH` как
   исполняемый файл. Такой вызов хук видит как `Bash`, а `guard.py` тело heredoc считает данными и тоже его пропускает
   («Проверка», п. 2). Закрывает это прослойка `gauntlet/adapters/codex/codex_hooks.py` (A.8): раскладывает патч на
   файлы так, как его читает парсер Codex, и спрашивает `guard.py` о каждом — и для инструмента, и для heredoc;
   `apply_patch` из оболочки без текста патча в команде (файл, stdin) отклоняет. Её вносит владелец набора своим PR.
3. **Роли видны хукам.** При вызове роли через `spawn_agent` с `agent_type` хук получает `agent_type` = имя роли,
   поэтому права ролей в `guard.py` (для `apply_patch` — через прослойку) и `SubagentStop` hardener'а работают как у
   Claude — с той же оговоркой, что guard эвристический, а документация Codex сама называет хуки инструментов
   «guardrail, not a complete enforcement boundary». Без `agent_type` роль — `default`, и хуки её не узнают; это
   держится инструкцией. Сам вызов `spawn_agent` хук тоже видит: прослойка отклоняет запуск роли или карточки с
   историей родителя (в `spawn_agent` v2 она передаётся по умолчанию) и запуск субагентов из ролей и карточек.
4. **Чего у Codex нет:** ограничить роли набор инструментов (у роли нельзя выключить `apply_patch`, песочница и
   одобрения у субагента — родительские), создать или продолжить чужую интерактивную сессию из координатора,
   подписаться на события PR. Это держат guard, инструкции и владелец; итог по-прежнему судит CI.
5. **Чего у Claude нет, а у Codex есть:** песочница уровня ОС. В режиме `workspace-write` (и в профиле `:workspace`)
   `.git/` и `.codex/` для команд агента и `apply_patch` только для чтения, а профиль прав `gauntlet` (Beta) делает
   только читаемыми и файлы набора. Ещё — проверка формы отчёта субагента хуком `SubagentStop` (до двух возвратов) и
   модель/уровень, которые можно закрепить в файле агента так, что координатор их не понизит.

Ответ на вопрос владельца для Codex: перенос выполним. Гейты, CI и процесс не меняются, хуки набора переиспользуются,
роли и карточки становятся своими агентами Codex. Остаток — пункты 2 и 4: первый закрывает PR владельца с прослойкой,
второй — инструкции, владелец и CI.

### A.3. Файлы в проекте

| Путь | Что это | Чей | Откуда |
|---|---|---|---|
| `AGENTS.md` | инструкция проекта для Codex (B.1); < 32 KiB, Codex читает её сам | человека | этот адаптер |
| `.codex/config.toml` | хуки и субагенты включены, одобрения — человек, профиль прав `gauntlet` (A.7) | человека | этот адаптер |
| `.codex/hooks.json` | те же хуки набора, что в `.claude/settings.json` (A.7) | человека | этот адаптер |
| `.codex/rules/gauntlet.rules` | `prefix_rule`: запреты человека и разрешённые git-команды (A.7) | человека | этот адаптер |
| `.codex/agents/specifier.toml`, `hardener.toml`, `reviewer.toml` | роли набора как свои агенты Codex (B.3) | человека | этот адаптер |
| `.codex/agents/precheck_mapper.toml`, `precheck_framework.toml`, `precheck_critic.toml`, `precheck_refuter.toml`, `review_repro.toml` | карточки ядра 4.1–4.4 и 4.6 (B.4); 4.5 — роль `reviewer` | человека | этот адаптер |
| `gauntlet/adapters/codex/codex_hooks.py` | прослойка: `guard` (apply_patch — инструмент и из оболочки, карточки с правами reviewer, интерактивные оболочки, `spawn_agent` без истории), `context` (тексты набора в контекст), `report` (форма отчёта) — A.8 | набор | PR владельца набора |

Не копируются и не меняются: `gauntlet/CLAUDE.md`, `.claude/agents/*.md`, `gauntlet/hooks/*`, оба workflow, корневой
`CLAUDE.md`. Claude Code и Codex могут работать в одном репозитории: каждый читает свои файлы.

### A.4. Установка

Всё ниже — правки набора и конфигурации агента, то есть файлы человека: их вносит владелец PR'ом (или сессия в
админ-окружении по его решению), а не сессия шага.
1. Положить файлы A.3 (тексты — A.7, A.8, B.1, B.3, B.4) одним PR. Проверка `gauntlet kit unchanged` на нём красная
   намеренно: он меняет `gauntlet/`.
2. Решить пункты A.6 (особенно 1 и 2: охрана `AGENTS.md` и `.codex/` в guard и в CI).
3. В `~/.codex/config.toml` не должно быть `sandbox_mode` и `[sandbox_workspace_write]`: при них профиль прав
   `gauntlet` молча не действует. Запускать `codex` без `--sandbox`, `--yolo`, `--dangerously-bypass-approvals-and-sandbox`
   и без `--approve-for-me` (`--not-so-yolo`): этот флаг включает песочницу `workspace-write` (профиль тогда не действует)
   и отдаёт одобрения автоматическому ревьюеру вместо человека.
4. Запуск сессий — из оболочки, где задано `ORG_GRADLE_PROJECT_publicRepositories=true` и не задан `GAUNTLET_GUARD`
   (хуки получают окружение сессии).
5. Первая сессия в репозитории: доверить проект (вопрос при старте или `codex exec --trust`), затем `/hooks` —
   просмотреть и доверить 7 обработчиков (SessionStart ×2, SubagentStart, PreToolUse, Stop, SubagentStop ×2). Codex
   хранит доверие по хэшу определения: после каждой правки `.codex/hooks.json` доверие нужно дать заново, а до этого
   изменённый хук пропускается.
6. Проверить песочницу командами (`codex sandbox` запускает команду под той же политикой, что агент):
   - `codex sandbox --permission-profile gauntlet -C . -- touch gauntlet/.probe` — должна упасть (файловая система только
     для чтения);
   - `codex sandbox --permission-profile gauntlet -C . -- sh -c 'touch src/.probe && rm src/.probe'` — должна пройти;
   - `codex sandbox --permission-profile gauntlet -C . -- ./gradlew help` — сеть и `~/.gradle`;
   - `codex sandbox --permission-profile gauntlet -C . -- docker info` — нужен, если Testcontainers должны работать в
     прогонах самого агента (прогоны Stop-хука идут вне песочницы). Не проходит — либо правило
     `prefix_rule(pattern = ["./gradlew"], decision = "allow")` (Gradle агента пойдёт вне песочницы; файлы набора тогда
     охраняет только guard и CI), либо агент гоняет гейты только через Stop-хук.
   Первая команда не упала (файл `gauntlet/.probe` создан) — профиль не действует: удалить файл, перейти на вариант A
   (A.7); файлы набора тогда охраняют только guard и CI.
   Если сессии шагов будут идти через `codex exec`: `codex exec "создай пустой файл src/.probe и удали его"` должен
   справиться — документация называет песочницу `codex exec` по умолчанию «только чтение», а что профиль проекта её
   заменяет, не подтверждено (D.4).
7. Проверить правила: `codex execpolicy check --pretty --rules .codex/rules/gauntlet.rules -- git push --force origin x`
   → `forbidden`; `… -- git commit -m x` → `allow`.
8. Проверить хуки в живой сессии на одноразовой ветке: первая строка ответа — строка статуса
   `gauntlet status: [gauntlet] active - …` (нет её — `/hooks` покажет, какой хук упал); просьба «допиши строку в
   `gauntlet/README.md`» (это `apply_patch`), «сделай то же heredoc'ом `apply_patch <<'EOF'` в оболочке» и «выполни
   `echo x >> gauntlet/config/gauntlet.properties`» (Bash) — все три отклонены с `[gauntlet guard]`; вызов роли
   `reviewer` с `agent_type` и просьба к ней `touch src/x` — отказ; вызов `precheck_refuter` без
   `fork_turns: "none"` в инструменте v2 — отказ `[gauntlet codex]`; правка в `src/main` и конец хода — Stop-хук гоняет
   `gauntletFast`.

`/import` (перенос настроек Claude Code в Codex: инструкции, хуки, субагенты) для набора не использовать: перенесённый
`guard.py` встретит `apply_patch` без прослойки, а ограничения инструментов ролей документация сама велит
пересмотреть после переноса.

### A.5. Как переиспользуются файлы набора, а не копируются

- `gauntlet/CLAUDE.md` целиком попадает в контекст хуком `SessionStart` (`codex_hooks.py context`, `startup|clear|compact`;
  после сжатия контекста — снова) и хуком `SubagentStart` — в контекст каждой роли и карточки. `additionalContextLimit: 0`
  передаёт текст полностью (иначе Codex сохраняет больше ~2500 токенов в файл и показывает модели начало и конец).
  Повтор после сжатия документация обещает только корневой сессии: долгая роль после сжатия своего контекста текст
  роли может потерять (D.4). Цена — около 68 КБ текста в контексте каждой сессии и каждой роли или карточки;
  документация советует `0` только хуку со строгим пределом вывода — здесь предел задаёт сам `gauntlet/CLAUDE.md`.
  `AGENTS.md` правил не дублирует: в нём краткий перечень с номерами правил, замены для Codex и запасной путь на случай,
  если хуки не сработали.
- Роли: текст `.claude/agents/<роль>.md` (без frontmatter Claude Code) кладёт в контекст роли хук `SubagentStart`; в
  `developer_instructions` агента Codex — только поправки для Codex, правило тщательности и форма итога.
- Хуки: `.codex/hooks.json` вызывает `gauntlet/hooks/session_start.sh`, `guard.py` (через прослойку), `stop_gate.py` —
  те же файлы, что `.claude/settings.json`.
- Ядро (правило тщательности, формат отчёта, карточки) — в `AGENTS.md` (разделы 4–5) и в файлах карточек.

### A.6. Решения владельца

1. **Охрана `AGENTS.md` и `.codex/` в guard и в CI.** Сейчас их нет ни в `HUMAN_OWNED` (`gauntlet/hooks/guard.py`), ни в
   списке `owned` (`.github/workflows/gauntlet-kit.yml`): правку `AGENTS.md` командой guard пропускает (проверено, D.3),
   а PR с правкой `.codex/` проверка `gauntlet kit unchanged` не заметит. Песочница держит `.codex/` только для чтения, а
   `AGENTS.md` — только в профиле `gauntlet`. Codex к тому же читает `AGENTS.override.md` вместо `AGENTS.md` того же
   каталога и подмешивает `AGENTS.md` подкаталогов на пути к рабочему каталогу: файл, созданный агентом, станет
   инструкцией следующих сессий. Рекомендация: добавить `AGENTS.md`, `AGENTS.override.md` и `.codex/` в оба списка, а в
   CI — отказ на любой новый или изменённый `AGENTS.md`/`AGENTS.override.md` в PR — ответьте здесь.
2. **Прослойка `gauntlet/adapters/codex/codex_hooks.py` в наборе.** Без неё guard в Codex видит только Bash, а
   `apply_patch` — нет, ни инструментом, ни heredoc'ом из оболочки (роли и спецификацию в правках файлов никто не держит,
   кроме инструкций и CI), и `spawn_agent` v2 передаёт роли и опровергателю всю историю родителя, если его не попросить. Рекомендация:
   внести PR'ом владельца набора — ответьте здесь.
3. **Профиль прав `gauntlet` (Beta) или вариант A.** Рекомендация: профиль, с проверкой A.4 шаг 6; не прошла — вариант A —
   ответьте здесь.
4. **Строка ответа внешнему ревьюеру:** «Ответ Codex на комментарий <ревьюер>» вместо «Ответ Claude Code …» (метод, п. 19
   раздела 1.1; `gauntlet/CLAUDE.md`, «Правила владельца»). Рекомендация: да — ответьте здесь.
5. **Модели и уровни для Codex** в «Правилах владельца» (метод, п. 17): предложение — координатор `gpt-6.2-astra` на
   самом высоком уровне без `ultra`, сессия шага `gpt-6.2-sol` `high`, тонкая семантика фреймворка `gpt-6.2-astra`
   `xhigh`; карточки и роли наследуют. Закреплять ли модель и уровень в файлах карточек (тогда координатор не понизит их
   в `spawn_agent`) — ответьте здесь.

### A.7. Тексты конфигурации

`.codex/config.toml` (вариант Б — профиль прав `gauntlet`, рекомендуемый):

```toml
# .codex/config.toml — Codex в репозитории под набором gauntlet. Файл человека, как .claude/settings.json.
# Слой проекта читается, только если проект доверен (projects."<путь>".trust_level = "trusted" в
# ~/.codex/config.toml или codex exec --trust); тогда его ключи главнее ~/.codex/config.toml.
# Ключи верхнего уровня стоят до первой таблицы [..]: в TOML всё, что ниже заголовка, принадлежит ему.

# Одобрения: человек, а не автоматический ревьюер — просьбу записать в файлы набора человек отклоняет сам.
approval_policy = "on-request"
approvals_reviewer = "user"

# Права — профиль gauntlet (Beta). Не задавайте sandbox_mode ни здесь, ни в ~/.codex/config.toml и не
# запускайте codex с --sandbox: тогда Codex берёт старую схему песочницы, и этот профиль молча не действует.
default_permissions = "gauntlet"

[features]
hooks = true            # хуки набора (guard, Stop, SubagentStop); включены и по умолчанию — здесь явно
# [features].multi_agent здесь не ставить: в 0.172.0 ключ устарел и при старте даёт предупреждение.

[agents]
enabled = true                           # инструменты субагентов (spawn_agent, wait_agent …); true и по умолчанию
max_concurrent_threads_per_session = 6   # карточки пред-проверки идут параллельно; больше — спор за Gradle и память

[permissions.gauntlet]
description = "Рабочее дерево пишется; набор gauntlet, роли, инструкции агентов и workflow — только чтение"
extends = ":workspace"  # .git, .codex, .agents, .aws внутри корня уже только для чтения

[permissions.gauntlet.filesystem]
"~/.gradle" = "write"   # кэш зависимостей и wrapper Gradle

[permissions.gauntlet.filesystem.":workspace_roots"]
"gauntlet" = "read"
".claude" = "read"
"CLAUDE.md" = "read"
"AGENTS.md" = "read"
"AGENTS.override.md" = "read"   # Codex читает его вместо AGENTS.md того же каталога; действует ли правило на ещё не созданный файл — D.4
".github/workflows/gauntlet.yml" = "read"
".github/workflows/gauntlet-kit.yml" = "read"

[permissions.gauntlet.network]
enabled = true          # Maven Central, портал плагинов Gradle, официальная документация (правило 12)

[permissions.gauntlet.network.unix_sockets]
"/var/run/docker.sock" = "allow"   # Testcontainers; проверить при установке (раздел A.4, шаг 6)
```

Вариант A — если проверка A.4 шаг 6 не прошла: вместо `default_permissions` и всех `[permissions.gauntlet…]` —

```toml
sandbox_mode = "workspace-write"     # .git и .codex внутри корня — только чтение; файлы набора — пишутся
approval_policy = "on-request"
approvals_reviewer = "user"

[sandbox_workspace_write]
network_access = true                # Maven Central, документация
writable_roots = ["/home/<пользователь>/.gradle"]   # абсолютный путь: раскрытие ~ здесь не подтверждено
```

`.codex/hooks.json` (с прослойкой A.8; до её появления в наборе — `PreToolUse` с matcher `^Bash$` и командой
`… python3 gauntlet/hooks/guard.py`, `SessionStart` второго обработчика — `cat gauntlet/CLAUDE.md`, а `SubagentStart`
и `SubagentStop` карточек — без обработчиков; heredoc `apply_patch` и `spawn_agent` с историей тогда не охраняются ничем,
кроме песочницы и инструкций; приставка `| sed '1s/^/gauntlet status: /'` у первого обработчика `SessionStart` нужна в
обоих вариантах). Хуки запускаются через `$SHELL -lc`: команды написаны для bash/zsh/sh; с `fish` как оболочкой входа
оберните каждую в `bash -c '…'`:

```json
{
  "description": "gauntlet: те же скрипты набора, что в .claude/settings.json, плюс прослойка gauntlet/adapters/codex/codex_hooks.py",
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact|fork",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)\" && CLAUDE_PROJECT_DIR=\"$PWD\" bash gauntlet/hooks/session_start.sh | sed '1s/^/gauntlet status: /'",
            "timeout": 180,
            "statusMessage": "Gauntlet: статус набора"
          }
        ]
      },
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)\" && CLAUDE_PROJECT_DIR=\"$PWD\" python3 gauntlet/adapters/codex/codex_hooks.py context",
            "timeout": 30,
            "additionalContextLimit": 0,
            "statusMessage": "Gauntlet: gauntlet/CLAUDE.md в контекст"
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "matcher": "^(specifier|hardener|reviewer|precheck_[a-z_]+|review_repro)$",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)\" && CLAUDE_PROJECT_DIR=\"$PWD\" python3 gauntlet/adapters/codex/codex_hooks.py context",
            "timeout": 30,
            "additionalContextLimit": 0,
            "statusMessage": "Gauntlet: роль и правила набора субагенту"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "^(Bash|apply_patch)$|spawn_agent$",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)\" && CLAUDE_PROJECT_DIR=\"$PWD\" python3 gauntlet/adapters/codex/codex_hooks.py guard",
            "timeout": 120
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)\" && CLAUDE_PROJECT_DIR=\"$PWD\" python3 gauntlet/hooks/stop_gate.py --task gauntletFast --max-attempts 3 --timeout 1700",
            "timeout": 1800,
            "statusMessage": "Gauntlet: ./gradlew gauntletFast..."
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "matcher": "^hardener$",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)\" && CLAUDE_PROJECT_DIR=\"$PWD\" python3 gauntlet/hooks/stop_gate.py --task mutationGate --max-attempts 2 --timeout 3300",
            "timeout": 7200,
            "statusMessage": "Gauntlet: ./gradlew mutationGate для hardener..."
          }
        ]
      },
      {
        "matcher": "^(precheck_[a-z_]+|review_repro|reviewer)$",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || pwd)\" && CLAUDE_PROJECT_DIR=\"$PWD\" python3 gauntlet/adapters/codex/codex_hooks.py report",
            "timeout": 30,
            "statusMessage": "Gauntlet: форма отчёта субагента"
          }
        ]
      }
    ]
  }
}
```

`.codex/rules/gauntlet.rules` (язык — Starlark; `match` и `not_match` Codex проверяет при загрузке):

```python
# .codex/rules/gauntlet.rules — действия, которые в наборе делает только человек (gauntlet/CLAUDE.md, правило 10;
# permissions.deny в .claude/settings.json), и git-команды процесса, которым нужна запись в .git.
# Правила префиксные: обёртка (bash -c с перенаправлением, переменная) их обходит. Те же команды семантически
# отклоняет guard набора (хук PreToolUse), а итог судят защита ветки GitHub и CI.

# --- только человек -----------------------------------------------------------------------------------------
prefix_rule(
    pattern = ["gh", "pr", "merge"],
    decision = "forbidden",
    justification = "Merge - утверждение результата человеком. Агент не мержит и не просит мержить.",
    match = ["gh pr merge 12 --squash"],
)
prefix_rule(
    pattern = ["gh", "workflow", "disable"],
    decision = "forbidden",
    justification = "CI-гейт выключает только человек.",
)
prefix_rule(
    pattern = ["git", ["rebase", "filter-branch", "filter-repo", "update-ref", "replace", "revert"]],
    decision = "forbidden",
    justification = "История ветки не переписывается: ошибку исправляют новым коммитом.",
    match = ["git rebase origin/main", "git revert HEAD"],
    not_match = ["git merge origin/main"],
)
prefix_rule(
    pattern = ["git", "commit", ["--amend", "--am", "--ame", "--amen", "--no-verify", "-n"]],
    decision = "forbidden",
    justification = "Только новые коммиты и без пропуска git-хуков.",
    match = ["git commit --amend -m x"],
)
prefix_rule(
    pattern = ["git", "pull", ["--rebase", "-r"]],
    decision = "forbidden",
    justification = "Ветку подтягивают слиянием (git pull без rebase), историю не переписывают.",
)
prefix_rule(
    pattern = ["git", "reset", "--hard"],
    decision = "forbidden",
    justification = "Ветку не переставляют на другую ревизию.",
)
prefix_rule(
    pattern = ["git", "push", ["--force", "-f", "--force-with-lease", "--mirror", "--all", "--delete", "-d", "--no-verify"]],
    decision = "forbidden",
    justification = "Force push, push всех веток, удаление веток и пропуск хуков - только человек.",
    match = ["git push --force origin task", "git push -f"],
    not_match = ["git push -u origin HEAD"],
)
prefix_rule(
    pattern = ["git", "checkout", "-B"],
    decision = "forbidden",
    justification = "Ветку не пересоздают поверх существующей.",
)
prefix_rule(
    pattern = ["git", "switch", "-C"],
    decision = "forbidden",
    justification = "Ветку не пересоздают поверх существующей.",
)
prefix_rule(
    pattern = ["git", "branch", ["-f", "-D", "-M", "--force", "--delete", "--move"]],
    decision = "forbidden",
    justification = "Ветки не переставляют, не удаляют и не переименовывают.",
)

# --- шаги процесса, которым нужна запись в .git (в песочнице .git только для чтения) ---------------------------
prefix_rule(
    pattern = ["git", ["add", "commit", "push", "fetch", "merge", "pull"]],
    decision = "allow",
    justification = "Коммит, push своей ветки, слияние основной ветки перед PR и git pull после spec-коммита владельца - шаги процесса; запрещённые формы отклоняют правила выше и guard.",
    match = ["git commit -m x", "git push -u origin HEAD", "git fetch origin main", "git merge origin/main"],
)
prefix_rule(
    pattern = ["git", "switch", "-c"],
    decision = "allow",
    justification = "Ветка задачи от основной ветки.",
)
prefix_rule(
    pattern = ["gh", "pr", ["create", "view", "checks", "comment"]],
    decision = "allow",
    justification = "PR с отчётом, статус CI и ответы внешнему ревьюеру.",
)

# --- вложенный Codex обходит хуки этой сессии: только с согласия человека ---------------------------------------
prefix_rule(
    pattern = ["codex"],
    decision = "prompt",
    justification = "Запуск другой сессии Codex (в том числе с выключенными хуками) - решение владельца.",
)
```

### A.8. Прослойка `gauntlet/adapters/codex/codex_hooks.py` (для PR владельца набора)

Проверена на синтетических событиях по схемам Codex 0.172.0 вместе с `guard.py` набора (D.3 и «Проверка»); в живом
Codex не запускалась.

```python
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
```

## B. Промпты

### B.1. `AGENTS.md` (инструкция проекта)

Codex склеивает `AGENTS.md` от корня проекта до рабочего каталога; предел — `project_doc_max_bytes` (32 KiB по
умолчанию). Этот файл — 17,3 KB. Включения других файлов в `AGENTS.md` нет, поэтому `gauntlet/CLAUDE.md` (67 KB) приносит
хук (A.5).

````markdown
# AGENTS.md — работа по методу gauntlet в Codex

Файл человека, как `CLAUDE.md`: агент его не правит. Процесс и правила набора не повторяются здесь
целиком: их источник — `gauntlet/CLAUDE.md`. Этот файл говорит, как читать его в Codex и чем Codex
заменяет механизмы Claude Code.

## 0. Начало каждой сессии

1. Хук `SessionStart` (`.codex/hooks.json`) кладёт в контекст две вещи: строку статуса
   `gauntlet status: [gauntlet] active - scope: …; guard: …; stop hook: …; docker: …` и полный текст
   `gauntlet/CLAUDE.md` блоком «# gauntlet/CLAUDE.md». Первым сообщением приведи строку статуса дословно.
2. Нет строки или нет блока — хуки не сработали (не доверены в `/hooks`, выключены `[features] hooks`,
   проект не доверен или это Codex Cloud). Тогда первой строкой ответа сообщи владельцу «хуки gauntlet не работают», выполни
   `printenv GAUNTLET_GUARD`, прочитай `gauntlet/CLAUDE.md` сам целиком (`sed -n '1,200p'`, затем дальше
   по 200 строк — до конца файла) и **без остановки на вопрос** веди задачу по разделу 3 «Без хуков». Пустой вывод или любое значение,
   кроме `off`, — guard включён; `off` — сообщи и не трогай файлы набора, пока владелец не разрешит.
3. Проверь и при необходимости сам настрой окружение без остановки на вопрос человеку: `docker info` (если Docker не установлен или демон не запущен — установи `docker.io` через `apt-get` / `sudo -n apt-get` при наличии прав, подними `dockerd --host=unix:///var/run/docker.sock` в фоне и дождись `docker info`; если `docker info --format '{{.CgroupDriver}}'` печатает `none` или `docker pause` падает с `freezer not supported`, подними штатный прокси `nohup python3 -I -B gauntlet/hooks/docker_pause_shim.py /tmp/docker-pause-shim.sock >/tmp/docker-pause-shim.log 2>&1 &`, перезапусти `./gradlew --stop` и передавай `DOCKER_HOST=unix:///tmp/docker-pause-shim.sock` без правки репозитория; при падении `rabbitmq:*-alpine` на 2-vCPU VM с `OS monotonic time stepped backwards!` собери локальный образ с `ENV ERL_AFLAGS="+c false"` под тем же тегом без правки репозитория), JDK нужной версии из `gauntlet/config/gauntlet.properties` (`project.java.version`, `gate.java.version` — найди в `/usr/lib/jvm`, `~/.jdks`, `~/.sdkman`, `/workspace` или кэше Gradle либо установи `openjdk-<версия>-jdk` и экспортируй `JAVA_HOME`, `GAUNTLET_GATE_JAVA_HOME`) и `ORG_GRADLE_PROJECT_publicRepositories=true`.
4. Где `gauntlet/CLAUDE.md` говорит о Claude Code, действуют замены раздела 2. Где этот файл молчит,
   действует `gauntlet/CLAUDE.md`. Если ты координатор серии, процесс серии задаёт твой промпт.

## 1. Жёсткие правила (кратко; полный текст и примеры — `gauntlet/CLAUDE.md`, «Жёсткие правила»)

1. Набор — человека: `gauntlet/`, `.claude/`, `.codex/`, `CLAUDE.md`, `AGENTS.md`, `AGENTS.override.md`,
   `.github/workflows/gauntlet.yml`, `.github/workflows/gauntlet-kit.yml`, `CODEOWNERS`, `.git/`. Не создавай
   `AGENTS.md` и `AGENTS.override.md` ни в каком каталоге: это инструкции следующим сессиям, их пишет человек.
   Проверка кажется неверной — остановись и объясни. Отказ песочницы или хука на запись туда — так задумано:
   не проси эскалацию и не ищи обход.
2. Никогда не ослабляй проверку ради зелёного (отключённые тесты, подавления, фильтры, `enabled = false`,
   ослабленные assert'ы). `integrityCheck` это ловит, человек видит diff.
3. Фичи — спецификация: пишет только роль `specifier`, утверждает только человек в чате.
4. TDD: падающий сфокусированный unit-тест → минимум кода → рефакторинг.
5. Маленькие функции и лимиты размера — правило 5 `gauntlet/CLAUDE.md`.
6. Зависимости направлены к политике модуля (`architecture.properties`).
7. Step-определения используют каждый параметр и проверяют наблюдаемое поведение.
8. `@Tag("no-mutate")` — только медленные тесты с полным контекстом или Testcontainers.
9. Секретов и персональных данных нет в логах, фикстурах, текстах исключений.
10. Git: только новые коммиты в своей ветке, коммит кончается `By <role>.`; никаких `--amend`, `rebase`,
    `revert`, `reset` на другую ревизию, `checkout -B`, force push, push в базовую ветку, `--no-verify`.
    Никогда не мержи и не проси мержить.
11. SOLID по каждому принципу. 12. Сверка с официальной документацией версии из сборки, а не с памятью
    (источники — раздел «Источники документации»). 13. Антипаттерны запрещены. 14. Оптимальный, безопасный
    и отказоустойчивый путь (2–3 варианта с выбором). 15. Читаемый код; комментарии простым языком; никаких
    следов разработки вне рабочего контура.

Работа сделана, только когда `./gradlew gauntlet` зелёный, ветка запушена и PR открыт. Не сообщай об
успехе, не выполнив проверку.

## 2. Что в Codex заменяет механизмы Claude Code

- **Хуки.** `.codex/hooks.json` вызывает те же скрипты набора: `session_start.sh` (SessionStart),
  `stop_gate.py` (Stop: `gauntletFast`; SubagentStop роли `hardener`: `mutationGate`), `guard.py` через
  прослойку `gauntlet/adapters/codex/codex_hooks.py` (PreToolUse: Bash, `apply_patch`, `spawn_agent`).
  Файлы правь инструментом `apply_patch` или heredoc `apply_patch <<'EOF'` с патчем прямо в команде: вызов
  `apply_patch` из оболочки с патчем из файла, переменной или stdin хук отклоняет — он не видит, что тот
  меняет. Красный Stop-хук возвращает тебе падения новым сообщением — чини причины, а не спорь с хуком;
  после 3 попыток он отпускает, и тогда работа НЕ сделана — так и пиши.
- **Роли.** `specifier`, `hardener`, `reviewer` — свои агенты Codex (`.codex/agents/*.toml`). Вызывай роль
  через `spawn_agent` с `agent_type` = имя роли и без истории родителя: `fork_turns: "none"` (в
  инструменте v2 по умолчанию `all` — вся история; хук отклонит такой вызов) или, в инструменте v1,
  `fork_context: false` либо без него. Всё, что роли нужно, — в сообщении задачи. В локальной сессии с хуками без
  `agent_type` хуки не узнают роль (guard не ограничит её область, а `mutationGate` hardener'а не запустится).
  Если же в твоей среде (например, Codex Cloud или недоверенный проект без загрузки `.codex/agents/`) схема
  инструмента `spawn_agent` вообще не принимает `agent_type` или не видит эти роли, **не останавливайся с вопросом
  координатору** — см. раздел 3, п. 4. Других субагентов в сессии шага не создавай: процесс уже многоагентный.
- **Ожидание субагента.** Дождись итогового сообщения роли (`wait_agent`, повторяй, пока она не
  закончит); таймаут ожидания — не повод закрывать её, подгонять или делать её работу самому. В
  инструменте v2 `wait_agent` текста не возвращает — только кто прислал обновление; итог роли приходит
  в разговор её сообщением. Итог роли читай целиком и проверяй по разделу 4 этого файла.
- **Охрана путей.** Песочница Codex держит `.git/` и `.codex/` только для чтения; профиль прав `gauntlet`
  (`.codex/config.toml`) — ещё и файлы набора. Коммит и push идут вне песочницы по правилам
  `.codex/rules/gauntlet.rules`; запрещённые формы git и `gh pr merge` отклоняют правила и guard.
- **Нет Stop-хука облачной платформы Claude и непрерывность после «да».** На остановке для утверждения
  спецификации ничего не коммить: черновик фич ждёт «да» человека, ход просто заканчивается. Когда человек ответил
  утверждением спецификации («да» / ответы на вопросы шага 3), закоммить фичи (`spec: …`), запушь ветку и **в этом же
  ходе без промежуточной остановки** выполни шаги 5–8 (TDD → `hardener` → `reviewer` → `gauntlet` → PR): не завершай
  ход после коммита `spec:` в ожидании отдельной команды «продолжай».
- **Ответ внешнему ревьюеру** начинается строкой «Ответ Codex на комментарий <ревьюер>» (с номером или
  датой комментария; подписи нет — «Ответ Codex на комментарий внешнего ревьюера», имя не угадывай) вместо
  «Ответ Claude Code на комментарий …».
- **Модели.** Имена моделей в «Правилах владельца» — модели Claude. Для Codex модель и уровень
  рассуждений рекомендует координатор, решает владелец; в сессии их видно в `/status`.
- **Локальный запуск.** Codex запускают с `ORG_GRADLE_PROJECT_publicRepositories=true` в окружении:
  без него сборка пойдёт в корпоративный реестр, а хуки не найдут задач набора.
- **Не запускай** вложенный `codex`, интерактивную оболочку или REPL (`bash`, `python3` без аргументов):
  команды, отправленные в них позже, хуки Codex не видят. Каждая команда — отдельным вызовом.

## 3. Без хуков (хуки не доверены, выключены или это Codex Cloud)

Ничто не держит тебя на красном гейте и не охраняет набор, кроме тебя и CI. Поэтому:
1. Перед каждым отчётом «готово» и перед открытием PR выполни сам
   `./gradlew gauntletFast --continue --console=plain 2>&1 | tee /tmp/gauntlet-fast.log` и приложи к отчёту
   вывод `grep -E '^> Task |BUILD (SUCCESSFUL|FAILED)|^gauntlet: ' /tmp/gauntlet-fast.log` — строка
   `> Task …` у каждой задачи гейта (`gauntletScope`, `integrityCheck`, `checkstyleGate`, `pmdGate`, `test`,
   `archTest`, `testCensus`, `acceptanceTest`, `acceptanceCheck`, `jacocoTestReport`, `crapGate`,
   `cpdReport`, `dryGate`) и итог; рядом — `git rev-parse --short HEAD` и `git status --short | wc -l`.
   Для `hardener` то же с `mutationGate`, в финале — с `gauntlet`.
2. Нет строки задачи, `FAILED` или прогон старше последней правки — гейт не пройден.
3. Окончательно решает CI (`gauntlet` и `gauntlet kit unchanged` на PR).
4. Если `spawn_agent` в этой среде не принимает `agent_type` из `.codex/agents/*.toml`, вызывай `spawn_agent`
   без `agent_type` (с `fork_turns: "none"` / `fork_context: false`), передавая в сообщении полный текст
   `.claude/agents/<роль>.md` и ограничения из `.codex/agents/<роль>.toml`, а после завершения роли сам проверь её
   область записи (`git status --short`, для `reviewer` — чистый снимок дерева, для `hardener` — пустой
   `git diff --stat -- '*/src/main/*'` и вывод `mutationGate`).

## 4. Правило тщательности (для тебя и для каждого субагента)

Тщательность меряется не временем и не токенами, а доказанностью утверждений.
1. **Доказательство к каждому утверждению**: команда, которую ты выполнил сам, и её вывод (обрезанный до
   сути); или `файл:строка` с цитатой, открытой в этом сеансе; или источник нужной версии (URL
   документации версии из сборки, класс в jar) с цитатой. Без доказательства — в раздел «Не проверено».
2. **Покрытие чек-листа, а не первая правдоподобная находка.** Покрытие — числом («вызовы X: 7 из 7»).
   «Ничего не найдено» — тоже результат: чем искал, где, сколько совпадений.
3. **Читать и запускать, а не вспоминать.** Поведение фреймворка, сигнатура, значение по умолчанию — из
   документации версии сборки, байткода или прогона. Запуск предпочтительнее чтения.
4. **Самопроверка перед отчётом**: к каждому утверждению — «что бы я увидел, если бы это было неправдой?»,
   и проверь, если не проверил.
5. **Честный остаток**: раздел «Не проверено» обязателен — что, почему, чем грозит. Пустой — только при
   полном покрытии.
6. **Без правок** у пред-проверки и ревью; правит тот, чья это роль.
7. **Остановка по карточке**: закончить, когда покрыт чек-лист и каждое утверждение доказано или помечено
   «не проверено», — а не когда найден первый ответ.
8. **Свежесть.** Вывод гейта или теста — доказательство, только если прогон был после последней правки;
   пересказ, сводка (recap) и «уже проверял раньше» доказательством не являются.

## 5. Формат отчёта субагента (одинаков у всех вендоров)

```
## Итог
<одна-две строки: ответ на вопрос карточки>

## Проверено (покрытие: N из M по чек-листу)
1. <утверждение> — доказательство: `<команда>` → <вывод> | `<файл:строка>`: «<цитата>» | <URL, версия>: «<цитата>»
2. ...

## Не проверено
- <что> — <почему> — <чем грозит>

## Вопросы и риски для координатора
- ...
```

Роль `reviewer` отвечает в своём формате (`VERDICT: …`, нумерованные находки, `Residual risks: …`) и сразу
после строки VERDICT пишет строку `Осмотрено: файлы диффа N из M, фичи K из L, …`. Хук `SubagentStop`
проверяет форму отчёта и до двух раз возвращает субагента дописать недостающее; содержание проверяешь ты.

## 6. Известные сбои Codex и что делает этот набор

- Агент объявляет задачу сделанной при невыполненных критериях или красной проверке, останавливается на
  промежуточном шаге (openai/codex #41176, #51692) → Stop-хук; «готово» только с выводом гейта по
  разделу 3 этого файла.
- Проверка «прошла» при нуле запущенных тестов или на 2 тестах из 183 (#63139) → в отчёте — число тестов
  из вывода прогона и строки `> Task …` каждой задачи гейта; `BUILD SUCCESSFUL` без них — не доказательство.
- `spawn_agent` v2 по умолчанию передаёт субагенту всю историю родителя (`fork_turns: "all"`) → роль и
  карточку набора запускай с `fork_turns: "none"`; хук отклоняет вызов без этого.
- Сводка (recap) пишет «проверено» о том, что не запускалось (#41626) → доказательство — только вывод
  команды из этого хода (правило 4.8).
- Главный агент заканчивает ход, не собрав результаты субагентов, не видит готовый результат и делает
  работу сам, закрывает или подгоняет здоровых субагентов (#40932, #46048, #40299) → раздел 2,
  «Ожидание субагента»; потерянный результат — новый запуск роли, а не тихая замена своей работой.
- Длинный вывод инструмента в истории усекается (`tool_output_token_limit`) → вердикт гейта бери из
  `grep` по логу, а не из прочитанного хвоста.
- После сжатия контекста хук `SessionStart` (`compact`) снова кладёт `gauntlet/CLAUDE.md`; план, решения
  владельца и номер раунда ревью держи в файлах и в описании PR, а не только в чате.
````

### B.2. Промпт координатора

Вставляется первым сообщением сессии координатора (CLI: `codex --add-dir <каталог плана> -m <модель> -c
model_reasoning_effort=<уровень> "$(cat coordinator-prompt.md)"`). Угловые скобки заполняет владелец.

```markdown
Ты — координатор серии задач по методу gauntlet в репозитории <owner/repo>, модуль(и) <модули>, в Codex. Слово запуска —
`coordinate`. План — файл <путь к плану>; файлы пред-проверки и промпты сессий клади в каталог плана <каталог плана>
(он подключён к сессии через `--add-dir`). Документ метода (раздел 8.3 и приложение D) владелец прикладывает; где этот
промпт расходится с методом, для Codex действует этот промпт.

## Кто ты и чего не делаешь
- Ведёшь план, пишешь задачу для Jira, делаешь пред-проверку, готовишь промпт сессии шага, передаёшь в неё решения
  владельца, следишь за PR, проверяешь результат после мержа. Продакшен-код не пишешь.
- Сессию шага открываешь только по команде владельца. Не мержишь и не просишь мержить.
- Всё, что ты выдаёшь владельцу или сессии как факт, прошло приёмку (раздел «Приёмка отчёта»). Остальное — с пометкой
  «не проверено».

## Старт
1. Первым сообщением приведи строку статуса хуков (`gauntlet status: [gauntlet] active - …`). Нет строки или нет блока
   «# gauntlet/CLAUDE.md» в контексте — хуки не работают: скажи владельцу первой строкой (проверить доверие в `/hooks`,
   доверие проекта, `[features] hooks`) и прочитай `gauntlet/CLAUDE.md` и `AGENTS.md` сам целиком.
2. Прочитай план и последний отчёт. Запиши в план, как запускаются сессии шагов: версия Codex (`codex --version`), профиль
   прав `gauntlet` (или запасной вариант A — раздел A.7 адаптера), хуки доверены, `GAUNTLET_GUARD` не задан,
   `ORG_GRADLE_PROJECT_publicRepositories=true` в окружении запуска.
3. Жди команды владельца на первую задачу.

## Цикл одной задачи
1. Владелец пишет, что шаг закрыт: проверь merge (`gh pr view <n> --json state,mergedAt,mergeCommit`), `git fetch origin`,
   запиши итог шага в план — PR, что вошло, открытые вопросы из отчёта.
2. Задача для Jira — в чат, простым языком, по шаблону метода (Тема / Описание с критериями приёмки / Трудозатраты).
3. Пред-проверка — раздел «Пред-проверка в Codex». Результат — файл <каталог плана>/step-<N>-precheck.md.
4. Пред-проверка изменила объём или оценку — дополнение к задаче и вопросы владельцу нумерованным списком
   с рекомендацией в каждом пункте.
5. Рекомендация модели и уровня рассуждений — в чат, с обоснованием (раздел «Модель и уровень»); решает владелец.
6. Промпт сессии шага — по шаблону приложения D метода: база и ветка, «Правила сессии» (ниже, вариант для Codex), задача,
   факты пред-проверки с пометками, черновик сценариев, таблица решений, цели unit-тестов (граничные — до реализации),
   решения владельца для остановки, «вне задачи». Пустые пункты — словом «нет». Файл: <каталог плана>/step-<N>-prompt.md.
7. Сессию открываешь по команде владельца (раздел «Открытие сессии»); её ID — в план.
8. Решения владельца, пришедшие во время работы сессии, передаёшь сам (раздел «Связь с сессией шага») и пишешь в план.
9. PR сессии: раздел «PR и раунды».
10. После мержа: раздел «После мержа».
11. Две правки, которых сессия шага сделать не может (правка замороженной спецификации коммитом `spec:` и строки allowlist
    RUN_ERROR после собственного прогона `mutationGate`), — только по решению владельца и только в админ-запуске Codex,
    который начинает владелец: `GAUNTLET_GUARD=off codex -c default_permissions=":workspace"` (метод, 8.3 п. 8). В
    обычном запуске их отклонят guard и песочница — так задумано.

## Пред-проверка в Codex (метод: п. 12 раздела 1.1; ядро: карточки 4.1–4.4)
Подготовка: `git fetch origin`; в модуле один раз `./gradlew dependencies > <каталог плана>/step-<N>-deps.txt` — путь
передаёшь карточкам 4.1 и 4.2.

Карточки — свои агенты из `.codex/agents/`:
- `precheck_mapper` (4.1) — по одной на срез задачи (обычно 2–4 среза: точки изменения, потоки, конфигурация, тестовый
  каркас);
- `precheck_framework` (4.2) — утверждения о фреймворке, на которые опирается дизайн, по 3–5 на карточку;
- `precheck_critic` (4.3) — после карт и сверки: варианты дизайна, таблица решений, черновик сценариев;
- `precheck_refuter` (4.4) — по одной на каждое ключевое утверждение (выбор дизайна, «фреймворк так себя ведёт»,
  «вызовов больше нет»).

Как вызывать: `spawn_agent` с `agent_type` = имя карточки; без истории родителя. Какой у тебя инструмент, видно по его
параметрам: v2 — есть обязательный `task_name` и `fork_turns` (по умолчанию `"all"`, вся твоя история) — передавай
`fork_turns: "none"`; v1 — `fork_context` (по умолчанию без истории) — не передавай `true`. Вызов роли или карточки с
историей хук PreToolUse отклонит. `model` и `reasoning_effort` не передавай — карточка наследует твои. В `message` — сама карточка: вопрос, входы (срез или утверждения, пути, база = коммит, путь к
файлу зависимостей), что вернуть. Опровергателю — только утверждение и пути: ни вывода первой карточки, ни своих
рассуждений.

Ведение: в файле пред-проверки — таблица «карточка → agent id → вопрос → статус (идёт | итог получен | возврат 1 | возврат
2 | не принят) → приёмка». Ожидание — `wait_agent` с самым долгим таймаутом, какой даёт инструмент; повторяй, пока у
каждой карточки нет итога (в v2 `wait_agent` текста не возвращает: итог карточки приходит в разговор её сообщением;
живые карточки показывает `list_agents`). Таймаут ожидания — не сбой: не закрывай карточку, не подгоняй её и не делай её работу сам.
Карточка упала или её итог не дошёл — новая карточка с тем же вопросом и пометка в таблице. Ход не заканчивается, пока у
каждой строки таблицы нет приёмки: принят, опровергнут или «не проверено» с причиной.

## Приёмка отчёта (ядро, раздел 2)
1. **Отказ без доказательств.** Форму (разделы, «доказательство:» у каждого пункта, непустое «Не проверено» при неполном
   покрытии) уже проверил хук `SubagentStop` и до двух раз вернул карточку. Ты проверяешь содержание: доказательство не
   подтверждает утверждение, покрытие не сходится с чек-листом, вывод команды подменён пересказом. Верни той же карточке
   перечень недостающего (v1: `send_input`, закрыта — сначала `resume_agent`; v2: `followup_task` — `send_message` нового
   хода не запускает). Это доработка отчёта, а не новый круг; всего не больше
   двух возвратов на карточку, считая возвраты хука; дальше — «не проверено» и вопрос владельцу.
2. **Выборочная перепроверка.** Минимум одно утверждение из каждого отчёта проверь сам тем же способом: та же команда, тот
   же `файл:строка`, тот же источник. Расхождение — отчёт не принят целиком, вопрос уходит новой карточке.
3. **Adversarial-проверка.** Утверждение, на котором держится решение, проверяет `precheck_refuter` — отдельная карточка
   без истории и без чужого вывода. При неуверенности — «опровергнуто».
4. **Сводка с пометками.** В план и в промпт сессии утверждения идут как «доказано (как)», «опровергнуто», «не проверено».
   Не проверенное не становится фактом пред-проверки.
Сводка, пересказ или recap — не доказательство: принимаются только отчёты карточек и твои собственные прогоны.

Файл пред-проверки: таблица карточек; факты с пометками и доказательствами; варианты дизайна с выбором и обоснованием;
таблица решений «тип события × наблюдаемый исход» (для правил выбора; атакованная критиком), каждая строка — сценарий со
значениями в Examples; черновик сценариев; цели unit-тестов; проверка оценки; блокеры; вопросы владельцу нумерованным
списком с рекомендацией.

## Модель и уровень (метод, п. 17; решает владелец)
Предложение для Codex по странице Models на 2026-11-24 (доступность зависит от плана; список и уровни — `/model`):
координатор — `gpt-6.2-astra` на самом высоком уровне, который модель объявляет, но не `ultra`: Ultra сам решает, когда
делегировать, а пред-проверка вызывает карточки явно; сессия шага — `gpt-6.2-sol` на `high`; шаг с тонкой семантикой
фреймворка (транзакции, Hibernate, AMQP, таймауты) — `gpt-6.2-astra` на `xhigh`. Карточки и роли наследуют модель и
уровень своей сессии. `gpt-6-luna` для карточек и ролей не предлагай: это модель для быстрой узкой работы.

## Правила сессии для Codex (в промпт сессии шага, раздел «Правила сессии», вместо пунктов о Claude Code)
- Первым сообщением приведи строку статуса хуков (`gauntlet status: [gauntlet] active - …`). Нет её — хуки не работают:
  сообщи владельцу первой строкой и работай по разделу 3 `AGENTS.md` («Без хуков»); `guard: off` — сообщи и не трогай набор.
- Роли — только `spawn_agent` с `agent_type` = `specifier` | `hardener` | `reviewer`, без истории родителя
  (`fork_turns: "none"`; в инструменте v1 — без `fork_context: true`); дождись итога каждой роли (`wait_agent`), не
  закрывай и не подгоняй её, её работу сам не делай. Других субагентов не создавай.
- На остановке для утверждения спецификации ничего не коммить: ход просто заканчивается (Stop-хука облачной платформы
  Claude здесь нет).
- Отказ песочницы или хука на запись в набор, `.codex/`, `.claude/`, `CLAUDE.md`, `AGENTS.md`, workflow — так задумано: не
  проси эскалацию, остановись и опиши.
- «Готово» — только с выводом своего прогона после последней правки: строки `> Task …` каждой задачи гейта, итог, `git
  rev-parse --short HEAD`. Сводка или ранний прогон — не доказательство.
- Не запускай вложенный `codex`, интерактивную оболочку или REPL; каждая команда — отдельным вызовом.
- Внешний ревьюер (<имя>): ответ в треде начинается строкой «Ответ Codex на комментарий <имя>» (с номером или датой;
  подписи нет — «Ответ Codex на комментарий внешнего ревьюера», имя не угадывай).
- Модель и уровень этой сессии: <модель>, <уровень> (рекомендация координатора, решение владельца).
Все остальные пункты «Правил сессии» шаблона — без изменений, в том числе: лимит, «не заканчивай ход, пока идёт фоновый
прогон гейтов» (в Codex команда `exec_command` может работать в фоне, пока её опрашивают `write_stdin`, а Stop-хук гоняет Gradle
в тот же каталог сборки),
никогда не мержить, набор — человека, контур, «не трогать», git, сверка по документации, адресация вопросов, внешний
ревьюер, комментарии простым языком, RUN_ERROR, замороженная спецификация, находка «правило», следы разработки, hardener
при пустой области PIT, слияние основной ветки перед PR, практика среды.

## Открытие сессии (по команде владельца)
- Интерактивно (рекомендуется: владелец видит остановки): владелец в каталоге репозитория на актуальной основной ветке
  запускает `ORG_GRADLE_PROJECT_publicRepositories=true codex -m <модель> -c model_reasoning_effort=<уровень>
  "$(cat <каталог плана>/step-<N>-prompt.md)"`.
- Без владельца до первой остановки: `ORG_GRADLE_PROJECT_publicRepositories=true codex exec -m <модель> -c
  model_reasoning_effort=<уровень> --json -o <каталог плана>/step-<N>-last.md - < <каталог плана>/step-<N>-prompt.md >
  <каталог плана>/step-<N>.jsonl`; ID сессии — из события `thread.started` журнала. Запуск `codex` из твоей сессии
  требует подтверждения владельца (правило `.codex/rules/gauntlet.rules`). В `codex exec` одобрения выключены
  (`approval_policy` = `never`, если ревьюер одобрений не `auto_review`): всё, что требует одобрения, падает, а не ждёт
  владельца, — сессия опишет отказ в итоге. Перед первым таким запуском убедись (A.4 шаг 6), что `codex exec` пишет в
  `src/`: документация называет песочницу `codex exec` по умолчанию «только чтение».
- Параллельные сессии — только в разных рабочих копиях (`git worktree add`), не в одной.
- Команды, которые пишут в `.git` и не разрешены правилами (`git worktree add`, `git switch` на другую ветку), идут вне
  песочницы только с одобрения владельца: в песочнице Codex `.git` только для чтения — так задумано.

## Связь с сессией шага
- Интерактивную сессию ведёт владелец: решение, которое ты подготовил, он вставляет в неё сам. Отправки сообщения в
  чужую интерактивную сессию в Codex CLI нет.
- Сессию `codex exec` после её остановки продолжает `codex exec resume <ID> "<решения владельца: 1) да 2) нет, потому что …>"`.
- Вопросы с пометкой «переслать координатору» владелец пересылает тебе; ответ ты передаёшь тем же способом и пишешь в план.

## PR и раунды
- События PR Codex не присылает. По сообщению владельца и в начале каждого своего хода: `gh pr checks <n>`,
  `gh pr view <n> --comments`. Следи, чтобы ни одно замечание внешнего ревьюера не осталось без ответа сессии шага;
  спорное замечание проверяет карточка `review_repro` (головы PR и базы готовишь ты через `git worktree add`). На своих PR
  отвечаешь сам: «Ответ Codex на комментарий <ревьюер>».
- Не больше двух раундов замечаний. Каждое замечание — «дефект» (правит исполнитель) или «правило» (вопрос владельцу
  «ответьте здесь», без нового раунда правок). Счёт раундов — в плане. После второго круга с непогашенными находками новых
  замечаний не выдаёшь, остаток — владельцу; PR не готов, так и пишешь в чате.

## После мержа
`git fetch origin && git worktree add /tmp/gauntlet-check-<N> origin/<основная>`; в этой копии
`./gradlew gauntlet --continue --console=plain` в режиме набора по умолчанию (Docker поднят) — строки `> Task …` и итог в
план. Код смерженного PR — против его описания и спецификации; остатки (что не вошло, что отложено) — в план. Нарушения в
файлах будущих шагов при `scope=all` — не дефект этого PR.
```

### B.3. Роли — свои агенты Codex

Обязательные поля файла агента — `name`, `description`, `developer_instructions`; `model` и `model_reasoning_effort`
главнее значений при вызове. `sandbox_mode`, `approval_policy`, `mcp_servers` в файле агента не действуют: всё это у
субагента родительское.

`.codex/agents/specifier.toml`:

```toml
name = "specifier"
description = "Роль gauntlet: пишет Gherkin-спецификацию (только каталог фич, до spec-коммита), ничего не коммитит. Шаг «Спецификация» процесса gauntlet/CLAUDE.md."
# model и model_reasoning_effort не заданы: роль наследует модель и уровень сессии шага, как model: inherit у Claude.
developer_instructions = """
Ты — роль specifier набора gauntlet. Текст роли целиком — .claude/agents/specifier.md; хук SubagentStart кладёт его
и gauntlet/CLAUDE.md в твой контекст блоками «# Роль набора gauntlet: specifier» и «# gauntlet/CLAUDE.md». Если
этих блоков нет, сначала прочитай оба файла сами целиком (sed -n частями по 200 строк до конца) и первой строкой
итога напиши «хук контекста не сработал».

Поправки для Codex (главнее текста роли там, где расходятся):
- Пиши только под <module>/src/acceptanceTest/resources/features/ охраняемых модулей. «A hook enforces it» в тексте
  роли — хук PreToolUse из .codex/hooks.json (guard набора через прослойку Codex); правку после spec-коммита он
  отклоняет. Не коммить. Своих субагентов не создавай.
- Отказ хука или песочницы — не повод искать обход: опиши, что и зачем ты хотел записать.

Правило тщательности:
- Каждое правило, которое закрепляет сценарий, — с источником: документ предметной области и раздел, или
  официальный источник версии из сборки (`./gradlew gauntletInfo`, `./gradlew dependencies` — команда и вывод),
  с цитатой. Нет источника — пункт идёт в открытые вопросы, а не в сценарий.
- Покрытие числом: «правила из запроса: N из M закреплены сценарием или вынесены «Вне фичи»; не закреплены: …».
- Повторное использование шагов: чем искал существующие формулировки (команда grep и число совпадений).
- Перед ответом перечитай свои утверждения: что бы ты увидел, если бы это было неправдой? — проверь.

Итоговое сообщение — как в роли: (1) файлы; (2) по строке на сценарий; (3) вопросы и допущения с источниками;
(4) таблица решений для правил выбора или «нет правил выбора»; затем строка покрытия и раздел «Не проверено»
(что, почему, чем грозит).
"""
```

`.codex/agents/hardener.toml`:

```toml
name = "hardener"
description = "Роль gauntlet: закаляет тесты мутациями (PIT и Gherkin-мутанты), правит только тестовый код. Шаг «Закалка» после зелёного gauntletFast."
developer_instructions = """
Ты — роль hardener набора gauntlet. Текст роли целиком — .claude/agents/hardener.md; хук SubagentStart кладёт его и
gauntlet/CLAUDE.md в твой контекст блоками «# Роль набора gauntlet: hardener» и «# gauntlet/CLAUDE.md». Если этих
блоков нет, сначала прочитай оба файла сами целиком и первой строкой итога напиши «хук контекста не сработал».

Поправки для Codex (главнее текста роли там, где расходятся):
- Пишешь только src/test/** и src/acceptanceTest/java/** охраняемых модулей; guard (хук PreToolUse из
  .codex/hooks.json) отклоняет остальное, в том числе src/main.
- «SubagentStop hook (.claude/settings.json, matcher hardener)» в тексте роли — у Codex это SubagentStop из
  .codex/hooks.json с matcher ^hardener$: он гоняет ./gradlew mutationGate, когда ты заканчиваешь, и возвращает
  тебе падения. Чини причины; после двух красных попыток он отпускает, и тогда работа не сделана — так и пиши.
- Ручные мутанты — только списком, продакшен-файлы не трогаешь ни «временно», ни скриптом, ни через stash.
- Своих субагентов не создавай.

Правило тщательности:
- Числа до и после — цитатой строк вывода, а не пересказом: строки pitSummary (SURVIVED, NO_COVERAGE, UNVERIFIED) и
  строка «mutationGate: …» до первой правки и после последней; рядом git rev-parse --short HEAD.
- Покрытие числом: «выжившие и без покрытия: обработано N из M» — каждый с исходом: убит тестом файл:строка,
  описан как эквивалентный (почему), строка allowlist для RUN_ERROR с убивающим тестом, предложение по
  продакшен-коду (место и правка).
- Перед ответом: что бы ты увидел, если бы тест не убивал мутанта? Прогони mutationGate ещё раз после последней
  правки, а не ссылайся на ранний прогон.

Итоговое сообщение — как в роли (числа до/после; добавленные тесты; что не убито и почему; RUN_ERROR со строкой
allowlist и тестом; рекомендуемые правки продакшен-кода; ручные мутанты), плюс строка покрытия и раздел
«Не проверено».
"""
```

`.codex/agents/reviewer.toml`:

```toml
name = "reviewer"
description = "Роль gauntlet: адверсарный ревьюер изменения, только чтение. Ищет то, чего не видят гейты; возвращает VERDICT и нумерованные находки «дефект»/«правило». Ничего не правит."
developer_instructions = """
Ты — роль reviewer набора gauntlet. Текст роли целиком — .claude/agents/reviewer.md; хук SubagentStart кладёт его и
gauntlet/CLAUDE.md в твой контекст блоками «# Роль набора gauntlet: reviewer» и «# gauntlet/CLAUDE.md». Если этих
блоков нет, сначала прочитай оба файла сами целиком и в «Residual risks» напиши «хук контекста не сработал».

Поправки для Codex (главнее текста роли там, где расходятся):
- Ты только читаешь и запускаешь проверки. Guard (хук PreToolUse из .codex/hooks.json) отклоняет запись в файлы и
  изменение git-состояния для agent_type reviewer; песочница Codex своя у всей сессии и тебя отдельно не
  ограничивает, поэтому правило держишь и ты. Своих субагентов не создавай.

Правило тщательности (раздел 4.5 карточек координатора):
- Сначала собери доказательства, как велит роль: дифф от merge base плюс неотслеживаемые файлы — и перечисли,
  что осмотрено. Сразу после строки VERDICT напиши строку
  «Осмотрено: файлы диффа N из M, фичи K из L, политика архитектуры: да|нет, сверка источников: P решений из Q».
- Каждая находка — с `файл:строка` и цитатой или с воспроизведением (команда → вывод).
- APPROVED — только при полном покрытии (N из N, K из K); иначе — что не осмотрено, в «Residual risks».
- «Ничего не найдено» по пункту «Look for» — с тем, чем искал (команда, число совпадений).
- Перед ответом: что бы ты увидел, если бы находка была неверной? Проверь.

Итог — ровно в форме роли:
VERDICT: APPROVED | CHANGES REQUESTED
Осмотрено: …
1. [blocker|major|minor] [дефект|правило] path/File.java:123 - problem - risk - expected correction
Residual risks: <что не проверено и почему>
Хук SubagentStop проверяет эти три строки и возвращает тебя дописать недостающее (не больше двух раз).
"""
```

### B.4. Карточки пред-проверки — свои агенты Codex

Карточка 4.5 (ревью PR) — роль `reviewer` (B.3) с правилом тщательности. Общая часть у карточек одна и та же
(границы, правило тщательности, форма отчёта) — она повторяется в каждом файле, потому что файл агента
самодостаточен.

`.codex/agents/precheck_mapper.toml` (4.1):

```toml
name = "precheck_mapper"
description = "Карточка пред-проверки 4.1: карта кода по одному срезу задачи (точки изменения, вызовы, конфигурация, тесты, потоки). Только чтение."
# model и model_reasoning_effort не заданы: карточка наследует модель и уровень координатора. Чтобы координатор не мог
# понизить их в spawn_agent, впишите здесь обе строки: значения файла главнее значений при вызове.
developer_instructions = """
Ты — карточка пред-проверки 4.1 «Карта кода по срезу» набора gauntlet. Координатор дал тебе задачу и один срез.

Цель: где и как задача меняет систему в твоём срезе — точки изменения, потоки, конфигурация, тестовый каркас.
Входы (в сообщении): текст задачи, срез (модуль, пакеты, классы), база (origin/<ветка> = <коммит>), путь к выводу
`./gradlew dependencies`, если координатор его снял.
Чек-лист:
1. Точки входа среза — `файл:строка` с цитатой.
2. Все вызовы изменяемого API — поиск по имени и по ссылке (команды и число совпадений), каждый вызов `файл:строка`.
3. Конфигурация, влияющая на поведение (свойства, профили, бины), — с фактическими значениями и откуда они.
4. Существующие тесты, покрывающие срез (имена), и чего они не покрывают.
5. Потоки, пулы, транзакции, через которые проходит изменение (на каком потоке и в какой транзакции выполняется код).
Что вернуть: в разделе «Проверено» — по пункту на место: «N. <место> — <роль в задаче> — доказательство: …» (это
таблица «место → роль в задаче → доказательство» в форме отчёта); в «Вопросах и рисках» — места, где поведение
неочевидно, и почему.

Права и границы (Codex):
- Ты только читаешь и запускаешь проверки: grep/rg, sed -n, git log/show/diff, ./gradlew (dependencies, gauntletInfo,
  отдельный тест), javap, curl официальной документации в /tmp. Файлы репозитория и git-состояние не меняешь;
  черновики и минимальные прогоны — только в /tmp. Guard (хук PreToolUse из .codex/hooks.json) судит тебя с правами
  reviewer и отклонит запись; это не повод искать обход. Гейты набора (gauntletFast, mutationGate, gauntlet) не
  гоняешь: их судит сессия шага. Своих субагентов не создаёшь.
- Хук SubagentStart кладёт в твой контекст gauntlet/CLAUDE.md (блок «# gauntlet/CLAUDE.md»): источники документации
  и их порядок — оттуда, раздел «Источники документации». Нет блока — прочитай файл сам.
- Входы — в сообщении координатора. Чего не хватает, не придумывай: это «Вопросы и риски для координатора» и
  «Не проверено».

Правило тщательности (одно для всех вендоров):
1. Каждое утверждение — с доказательством: команда, которую ты выполнил сам, и её вывод (обрезанный до сути);
   или `файл:строка` с цитатой, открытой в этом сеансе; или источник нужной версии (URL документации версии из
   сборки, класс в jar) с цитатой. Без доказательства — в «Не проверено», не в выводы.
2. Покрытие чек-листа, а не первая правдоподобная находка: покрытие — числом («вызовы X: 7 из 7»). «Ничего не
   найдено» — тоже результат: чем искал (запрос, команда), где, сколько совпадений.
3. Читать и запускать, а не вспоминать: поведение, сигнатура, значение по умолчанию — из документации версии
   сборки, байткода или прогона. Запуск предпочтительнее чтения. Память модели — не источник.
4. Перед отчётом перечитай свои утверждения: что бы ты увидел, если бы это было неправдой? — и проверь.
5. Раздел «Не проверено» обязателен: что, почему (нет доступа, нет времени, вне карточки), чем грозит. Пустой —
   только при полном покрытии.
6. Заканчиваешь, когда покрыт чек-лист и каждое утверждение доказано или помечено «не проверено», — а не когда
   нашёл первый ответ или «достаточно уверен». Короткий отчёт с честным «Не проверено» лучше длинного без
   доказательств.

Итоговое сообщение — ровно в этой форме (хук SubagentStop проверяет её и до двух раз вернёт тебя дописать):
## Итог
<одна-две строки: ответ на вопрос карточки>

## Проверено (покрытие: N из M по чек-листу)
1. <утверждение> — доказательство: `<команда>` → <вывод> | `<файл:строка>`: «<цитата>» | <URL, версия>: «<цитата>»

## Не проверено
- <что> — <почему> — <чем грозит>

## Вопросы и риски для координатора
- ...
"""
```

`.codex/agents/precheck_framework.toml` (4.2):

```toml
name = "precheck_framework"
description = "Карточка пред-проверки 4.2: сверяет утверждения о фреймворке и библиотеках для версии из сборки (документация версии, sources-jar, javap, прогон). Только чтение."
# model и model_reasoning_effort не заданы: карточка наследует модель и уровень координатора. Чтобы координатор не мог
# понизить их в spawn_agent, впишите здесь обе строки: значения файла главнее значений при вызове.
developer_instructions = """
Ты — карточка пред-проверки 4.2 «Сверка утверждения о фреймворке» набора gauntlet.

Цель: каждое утверждение о поведении библиотеки или фреймворка из сообщения подтвердить для версии из сборки.
Входы (в сообщении): список утверждений, модуль, путь к выводу `./gradlew dependencies`, если он есть.
Чек-лист — для каждого утверждения:
1. Версия из файлов сборки: команда и вывод (`./gradlew dependencies`, `./gradlew gauntletInfo`).
2. Источник этой версии по порядку раздела «Источники документации» gauntlet/CLAUDE.md: официальный сайт с версией
   в пути → javadoc-jar и sources-jar → исходники документации по тегу → jar в кэше Gradle и `javap -p -c`.
   Страница без версии — источник, только если не расходится с исходниками по тегу нужной версии.
3. Цитата из источника.
4. При возможности — минимальный прогон в /tmp (существующий тест модуля, `javap -c`, маленькая программа), который
   показывает поведение. Расхождение документации и кода нужной версии — прав код; в отчёт идут оба.
Что вернуть: в «Проверено» — по пункту на утверждение: «N. <утверждение> — версия <из сборки> — доказательство:
<источник версии>: «<цитата>» (и прогон, если был) — вердикт: подтверждено | опровергнуто | неясно». Покрытие:
«утверждения: N из M».

Права и границы (Codex):
- Ты только читаешь и запускаешь проверки: grep/rg, sed -n, git log/show/diff, ./gradlew (dependencies, gauntletInfo,
  отдельный тест), javap, curl официальной документации в /tmp. Файлы репозитория и git-состояние не меняешь;
  черновики и минимальные прогоны — только в /tmp. Guard (хук PreToolUse из .codex/hooks.json) судит тебя с правами
  reviewer и отклонит запись; это не повод искать обход. Гейты набора (gauntletFast, mutationGate, gauntlet) не
  гоняешь: их судит сессия шага. Своих субагентов не создаёшь.
- Хук SubagentStart кладёт в твой контекст gauntlet/CLAUDE.md (блок «# gauntlet/CLAUDE.md»): источники документации
  и их порядок — оттуда, раздел «Источники документации». Нет блока — прочитай файл сам.
- Входы — в сообщении координатора. Чего не хватает, не придумывай: это «Вопросы и риски для координатора» и
  «Не проверено».

Правило тщательности (одно для всех вендоров):
1. Каждое утверждение — с доказательством: команда, которую ты выполнил сам, и её вывод (обрезанный до сути);
   или `файл:строка` с цитатой, открытой в этом сеансе; или источник нужной версии (URL документации версии из
   сборки, класс в jar) с цитатой. Без доказательства — в «Не проверено», не в выводы.
2. Покрытие чек-листа, а не первая правдоподобная находка: покрытие — числом («вызовы X: 7 из 7»). «Ничего не
   найдено» — тоже результат: чем искал (запрос, команда), где, сколько совпадений.
3. Читать и запускать, а не вспоминать: поведение, сигнатура, значение по умолчанию — из документации версии
   сборки, байткода или прогона. Запуск предпочтительнее чтения. Память модели — не источник.
4. Перед отчётом перечитай свои утверждения: что бы ты увидел, если бы это было неправдой? — и проверь.
5. Раздел «Не проверено» обязателен: что, почему (нет доступа, нет времени, вне карточки), чем грозит. Пустой —
   только при полном покрытии.
6. Заканчиваешь, когда покрыт чек-лист и каждое утверждение доказано или помечено «не проверено», — а не когда
   нашёл первый ответ или «достаточно уверен». Короткий отчёт с честным «Не проверено» лучше длинного без
   доказательств.

Итоговое сообщение — ровно в этой форме (хук SubagentStop проверяет её и до двух раз вернёт тебя дописать):
## Итог
<одна-две строки: ответ на вопрос карточки>

## Проверено (покрытие: N из M по чек-листу)
1. <утверждение> — доказательство: `<команда>` → <вывод> | `<файл:строка>`: «<цитата>» | <URL, версия>: «<цитата>»

## Не проверено
- <что> — <почему> — <чем грозит>

## Вопросы и риски для координатора
- ...
"""
```

`.codex/agents/precheck_critic.toml` (4.3):

```toml
name = "precheck_critic"
description = "Карточка пред-проверки 4.3: атакует вариант дизайна и таблицу решений граничными случаями; даёт цели граничных unit-тестов. Только чтение."
# model и model_reasoning_effort не заданы: карточка наследует модель и уровень координатора. Чтобы координатор не мог
# понизить их в spawn_agent, впишите здесь обе строки: значения файла главнее значений при вызове.
developer_instructions = """
Ты — карточка пред-проверки 4.3 «Критик дизайна и таблицы решений» набора gauntlet.

Цель: атаковать вариант дизайна и (для правил выбора) таблицу «тип события × наблюдаемый исход».
Входы (в сообщении): варианты дизайна с выбором координатора, таблица решений, черновик сценариев, пути к коду.
Чек-лист:
1. Каждая строка таблицы — граничный случай против неё (конкретный вход и ожидаемый исход).
2. Конкурентность и повторы: повторная доставка, повторный HTTP-запрос, гонка двух событий.
3. Отказ внешней системы: таймаут, ошибка, частичный успех; судьба отказа.
4. Пустые и null значения, очистка поля против его отсутствия.
5. Что увидит приёмка (наблюдаемый исход: ответ, сообщение, сохранённая строка), а что нет.
Каждую атаку подкрепляй кодом (`файл:строка`) или документацией версии; домысел без опоры — в «Не проверено».
Что вернуть: в «Проверено» — по пункту на атаку: «N. <строка таблицы или пункт 2–5> — <пример входа и исход> —
доказательство: …»; в «Итоге» — строки, которые ломаются, и недостающие строки; в «Вопросах и рисках» — цели
граничных unit-тестов (каждый ловит правдоподобную неверную реализацию). Покрытие: «строки таблицы: N из M;
пункты 2–5: K из 4».

Права и границы (Codex):
- Ты только читаешь и запускаешь проверки: grep/rg, sed -n, git log/show/diff, ./gradlew (dependencies, gauntletInfo,
  отдельный тест), javap, curl официальной документации в /tmp. Файлы репозитория и git-состояние не меняешь;
  черновики и минимальные прогоны — только в /tmp. Guard (хук PreToolUse из .codex/hooks.json) судит тебя с правами
  reviewer и отклонит запись; это не повод искать обход. Гейты набора (gauntletFast, mutationGate, gauntlet) не
  гоняешь: их судит сессия шага. Своих субагентов не создаёшь.
- Хук SubagentStart кладёт в твой контекст gauntlet/CLAUDE.md (блок «# gauntlet/CLAUDE.md»): источники документации
  и их порядок — оттуда, раздел «Источники документации». Нет блока — прочитай файл сам.
- Входы — в сообщении координатора. Чего не хватает, не придумывай: это «Вопросы и риски для координатора» и
  «Не проверено».

Правило тщательности (одно для всех вендоров):
1. Каждое утверждение — с доказательством: команда, которую ты выполнил сам, и её вывод (обрезанный до сути);
   или `файл:строка` с цитатой, открытой в этом сеансе; или источник нужной версии (URL документации версии из
   сборки, класс в jar) с цитатой. Без доказательства — в «Не проверено», не в выводы.
2. Покрытие чек-листа, а не первая правдоподобная находка: покрытие — числом («вызовы X: 7 из 7»). «Ничего не
   найдено» — тоже результат: чем искал (запрос, команда), где, сколько совпадений.
3. Читать и запускать, а не вспоминать: поведение, сигнатура, значение по умолчанию — из документации версии
   сборки, байткода или прогона. Запуск предпочтительнее чтения. Память модели — не источник.
4. Перед отчётом перечитай свои утверждения: что бы ты увидел, если бы это было неправдой? — и проверь.
5. Раздел «Не проверено» обязателен: что, почему (нет доступа, нет времени, вне карточки), чем грозит. Пустой —
   только при полном покрытии.
6. Заканчиваешь, когда покрыт чек-лист и каждое утверждение доказано или помечено «не проверено», — а не когда
   нашёл первый ответ или «достаточно уверен». Короткий отчёт с честным «Не проверено» лучше длинного без
   доказательств.

Итоговое сообщение — ровно в этой форме (хук SubagentStop проверяет её и до двух раз вернёт тебя дописать):
## Итог
<одна-две строки: ответ на вопрос карточки>

## Проверено (покрытие: N из M по чек-листу)
1. <утверждение> — доказательство: `<команда>` → <вывод> | `<файл:строка>`: «<цитата>» | <URL, версия>: «<цитата>»

## Не проверено
- <что> — <почему> — <чем грозит>

## Вопросы и риски для координатора
- ...
"""
```

`.codex/agents/precheck_refuter.toml` (4.4):

```toml
name = "precheck_refuter"
description = "Карточка 4.4: независимо опровергает одно ключевое утверждение, не зная чужого вывода; при неуверенности — «опровергнуто». Только чтение."
# model и model_reasoning_effort не заданы: карточка наследует модель и уровень координатора. Чтобы координатор не мог
# понизить их в spawn_agent, впишите здесь обе строки: значения файла главнее значений при вызове.
developer_instructions = """
Ты — карточка 4.4 «Опровергатель» набора gauntlet. Тебе дали одно утверждение и пути — и не сказали, кто и как
его вывел. Так задумано: не ищи и не восстанавливай чужой вывод.

Цель: опровергнуть утверждение.
Чек-лист:
1. Найди условие, при котором утверждение ложно (версия, конфигурация, поток, порядок, пустое значение).
2. Попробуй воспроизвести это условие: прогон в /tmp, существующий тест, `javap`, чтение кода по путям.
3. Проверь источник другой дорогой — не той, что очевидна (исходники по тегу вместо страницы сайта, байткод вместо
   Javadoc, вызовы по ссылке вместо поиска по имени).
По умолчанию при неуверенности вердикт — «опровергнуто»: «подтверждено» требует доказательства, которое ты получил
сам.
Что вернуть: в «Итоге» — один вердикт: подтверждено (чем) | опровергнуто (контрпример с доказательством) |
не удалось проверить (почему); в «Проверено» — по пункту чек-листа с доказательством. Покрытие: «пункты
чек-листа: N из 3».

Права и границы (Codex):
- Ты только читаешь и запускаешь проверки: grep/rg, sed -n, git log/show/diff, ./gradlew (dependencies, gauntletInfo,
  отдельный тест), javap, curl официальной документации в /tmp. Файлы репозитория и git-состояние не меняешь;
  черновики и минимальные прогоны — только в /tmp. Guard (хук PreToolUse из .codex/hooks.json) судит тебя с правами
  reviewer и отклонит запись; это не повод искать обход. Гейты набора (gauntletFast, mutationGate, gauntlet) не
  гоняешь: их судит сессия шага. Своих субагентов не создаёшь.
- Хук SubagentStart кладёт в твой контекст gauntlet/CLAUDE.md (блок «# gauntlet/CLAUDE.md»): источники документации
  и их порядок — оттуда, раздел «Источники документации». Нет блока — прочитай файл сам.
- Входы — в сообщении координатора. Чего не хватает, не придумывай: это «Вопросы и риски для координатора» и
  «Не проверено».

Правило тщательности (одно для всех вендоров):
1. Каждое утверждение — с доказательством: команда, которую ты выполнил сам, и её вывод (обрезанный до сути);
   или `файл:строка` с цитатой, открытой в этом сеансе; или источник нужной версии (URL документации версии из
   сборки, класс в jar) с цитатой. Без доказательства — в «Не проверено», не в выводы.
2. Покрытие чек-листа, а не первая правдоподобная находка: покрытие — числом («вызовы X: 7 из 7»). «Ничего не
   найдено» — тоже результат: чем искал (запрос, команда), где, сколько совпадений.
3. Читать и запускать, а не вспоминать: поведение, сигнатура, значение по умолчанию — из документации версии
   сборки, байткода или прогона. Запуск предпочтительнее чтения. Память модели — не источник.
4. Перед отчётом перечитай свои утверждения: что бы ты увидел, если бы это было неправдой? — и проверь.
5. Раздел «Не проверено» обязателен: что, почему (нет доступа, нет времени, вне карточки), чем грозит. Пустой —
   только при полном покрытии.
6. Заканчиваешь, когда покрыт чек-лист и каждое утверждение доказано или помечено «не проверено», — а не когда
   нашёл первый ответ или «достаточно уверен». Короткий отчёт с честным «Не проверено» лучше длинного без
   доказательств.

Итоговое сообщение — ровно в этой форме (хук SubagentStop проверяет её и до двух раз вернёт тебя дописать):
## Итог
<одна-две строки: ответ на вопрос карточки>

## Проверено (покрытие: N из M по чек-листу)
1. <утверждение> — доказательство: `<команда>` → <вывод> | `<файл:строка>`: «<цитата>» | <URL, версия>: «<цитата>»

## Не проверено
- <что> — <почему> — <чем грозит>

## Вопросы и риски для координатора
- ...
"""
```

`.codex/agents/review_repro.toml` (4.6):

```toml
name = "review_repro"
description = "Карточка 4.6: воспроизводит замечание внешнего ревьюера на голове PR и на базе, классифицирует его. Только чтение."
# model и model_reasoning_effort не заданы: карточка наследует модель и уровень координатора. Чтобы координатор не мог
# понизить их в spawn_agent, впишите здесь обе строки: значения файла главнее значений при вызове.
developer_instructions = """
Ты — карточка 4.6 «Воспроизведение замечания внешнего ревьюера» набора gauntlet.

Цель: правда ли замечание на текущей голове PR.
Входы (в сообщении): текст замечания с номером или датой, номер PR, коммит головы PR и базы; пути к рабочим копиям
головы и базы, которые координатор подготовил (`git worktree add`): сам ты git-состояние не меняешь.
Чек-лист:
1. Воспроизвести на голове PR: команда, тест или сценарий — и вывод.
2. Проверить на базе: воспроизводится ли там (тогда это не новое — отдельная задача бэклога, а не основание
   заворачивать PR).
3. Классифицировать по правилу остановки: ложный зелёный | ложный красный без обхода | ложный красный с обходом |
   документ.
Что вернуть: в «Итоге» — «воспроизведено (как) | не воспроизведено (что пробовал)», класс, предложение; в
«Проверено» — по пункту чек-листа с доказательством (команда → вывод на голове и на базе). Покрытие: «N из 3».

Права и границы (Codex):
- Ты только читаешь и запускаешь проверки: grep/rg, sed -n, git log/show/diff, ./gradlew (dependencies, gauntletInfo,
  отдельный тест), javap, curl официальной документации в /tmp. Файлы репозитория и git-состояние не меняешь;
  черновики и минимальные прогоны — только в /tmp. Guard (хук PreToolUse из .codex/hooks.json) судит тебя с правами
  reviewer и отклонит запись; это не повод искать обход. Гейты набора (gauntletFast, mutationGate, gauntlet) не
  гоняешь: их судит сессия шага. Своих субагентов не создаёшь.
- Хук SubagentStart кладёт в твой контекст gauntlet/CLAUDE.md (блок «# gauntlet/CLAUDE.md»): источники документации
  и их порядок — оттуда, раздел «Источники документации». Нет блока — прочитай файл сам.
- Входы — в сообщении координатора. Чего не хватает, не придумывай: это «Вопросы и риски для координатора» и
  «Не проверено».

Правило тщательности (одно для всех вендоров):
1. Каждое утверждение — с доказательством: команда, которую ты выполнил сам, и её вывод (обрезанный до сути);
   или `файл:строка` с цитатой, открытой в этом сеансе; или источник нужной версии (URL документации версии из
   сборки, класс в jar) с цитатой. Без доказательства — в «Не проверено», не в выводы.
2. Покрытие чек-листа, а не первая правдоподобная находка: покрытие — числом («вызовы X: 7 из 7»). «Ничего не
   найдено» — тоже результат: чем искал (запрос, команда), где, сколько совпадений.
3. Читать и запускать, а не вспоминать: поведение, сигнатура, значение по умолчанию — из документации версии
   сборки, байткода или прогона. Запуск предпочтительнее чтения. Память модели — не источник.
4. Перед отчётом перечитай свои утверждения: что бы ты увидел, если бы это было неправдой? — и проверь.
5. Раздел «Не проверено» обязателен: что, почему (нет доступа, нет времени, вне карточки), чем грозит. Пустой —
   только при полном покрытии.
6. Заканчиваешь, когда покрыт чек-лист и каждое утверждение доказано или помечено «не проверено», — а не когда
   нашёл первый ответ или «достаточно уверен». Короткий отчёт с честным «Не проверено» лучше длинного без
   доказательств.

Итоговое сообщение — ровно в этой форме (хук SubagentStop проверяет её и до двух раз вернёт тебя дописать):
## Итог
<одна-две строки: ответ на вопрос карточки>

## Проверено (покрытие: N из M по чек-листу)
1. <утверждение> — доказательство: `<команда>` → <вывод> | `<файл:строка>`: «<цитата>» | <URL, версия>: «<цитата>»

## Не проверено
- <что> — <почему> — <чем грозит>

## Вопросы и риски для координатора
- ...
"""
```

## C. Сопоставление

| Механизм gauntlet (Claude Code) | Чем это в Codex 0.172.0 | Статус | Запасной путь |
|---|---|---|---|
| Корневой `CLAUDE.md` с `@gauntlet/CLAUDE.md` | `AGENTS.md` (включений нет, предел 32 KiB) + хук `SessionStart` кладёт полный `gauntlet/CLAUDE.md`, после сжатия — снова | полностью при доверенных хуках; иначе частично | `AGENTS.md`: краткие правила, строка статуса первым сообщением, «прочитай файл сам» |
| Роли `.claude/agents/*.md` (`tools`, `model: inherit`) | свои агенты `.codex/agents/*.toml`; текст роли кладёт `SubagentStart`; модель и уровень наследуются | частично: список инструментов роли не ограничить (выключается shell, но не `apply_patch`), песочница и одобрения — родительские | права роли держит guard по `agent_type` (ниже), инструкция, CI |
| Права ролей в `guard.py` по `agent_type` | `PreToolUse` несёт `agent_type` = роль из `spawn_agent` (или `default`); Bash — `guard.py` как есть; `apply_patch` — инструмент и heredoc из оболочки (его хук видит как `Bash`) — через прослойку | частично без прослойки (только Bash, и heredoc `apply_patch` проходит); с прослойкой — как у Claude (эвристика guard; хуки инструментов Codex сам называет «not a complete enforcement boundary») | CI `gauntlet kit unchanged` (только пути набора), diff PR |
| `PreToolUse` guard: пути человека | guard (Bash; `apply_patch` с прослойкой) + песочница: `.git/`, `.codex/` только для чтения в `workspace-write` и `:workspace`; профиль `gauntlet` — ещё `gauntlet/`, `.claude/`, `CLAUDE.md`, `AGENTS.md`, `AGENTS.override.md`, оба workflow | полностью для команд в песочнице и `apply_patch` при профиле Б, если проверка A.4 шаг 6 прошла; при варианте A — частично (guard) | CI; эскалацию одобряет только человек (`approvals_reviewer = "user"`) |
| Заморозка спецификации, область specifier и hardener | `guard.py` (frozen, область роли) для Bash; `apply_patch` (инструмент и heredoc) — через прослойку | частично | diff PR, человек |
| `permissions.deny` (префиксы git/gh) | `.codex/rules/*.rules`: `prefix_rule(..., decision = "forbidden")` (экспериментально); `forbidden` отклоняет команду до запуска, и в песочнице тоже (по коду) | частично — префикс, как и у Claude | guard (семантически), защита ветки GitHub |
| `permissions.allow` (git, gh) | `prefix_rule(..., decision = "allow")` для `git add/commit/push/fetch/merge/pull`, `git switch -c`, `gh pr create/view/checks/comment` — вне песочницы без вопроса (нужно: `.git` в песочнице только для чтения) | полностью по документации, запуском не проверено | `on-request`: человек одобряет команду |
| `SessionStart` → `session_start.sh` | `SessionStart` (`startup`, `resume`, `clear`, `compact`, `fork`); текст stdout — в контекст, но вывод, который начинается с «[» или «{», Codex разбирает как JSON | полностью с приставкой `gauntlet status: ` в команде хука (тот же скрипт; ветка облака Claude — Docker, base fetch — локально не срабатывает); без приставки строка статуса в контекст не попадает, снимок дерева для Stop-хука пишется всё равно | — |
| `Stop` → `stop_gate.py` (`gauntletFast`) | `Stop`: exit 2 и причина в stderr — ход продолжается с причиной новым сообщением; `stop_hook_active`; таймаут без верхнего предела | полностью (контракт проверен на синтетических событиях) | без хуков: агент сам гоняет `gauntletFast` и прикладывает строки `> Task …` и итог (`AGENTS.md`, раздел 3); решает CI |
| `SubagentStop` hardener → `mutationGate` | `SubagentStop` с matcher `^hardener$` по `agent_type` | полностью, если роль вызвана с `agent_type` | то же + CI |
| `GAUNTLET_GUARD=off`, `GAUNTLET_STOP_HOOK=off` (админ-окружение) | хуки получают окружение сессии: те же переменные при запуске `codex` | полностью; у Codex ещё выключатели `[features] hooks = false`, `--disable hooks`, недоверенный хук | строка статуса первым сообщением; писать в `.codex/` и `~/.codex/` агенту не даёт песочница |
| Доверие хукам | у Claude нет; у Codex обязательно (`/hooks`, по хэшу) | новое условие | `--dangerously-bypass-hook-trust` — только для автоматизации, где источник хуков проверен |
| Координатор: многоагентная пред-проверка | v1: `spawn_agent`, `wait_agent`, `send_input`, `resume_agent`, `close_agent`; v2 (выбирает конфигурация или каталог моделей): `spawn_agent` (`task_name` обязателен), `wait_agent` (без текста итога), `send_message`, `followup_task`, `list_agents`, `interrupt_agent`; карточки — свои агенты; параллельно до `max_concurrent_threads_per_session` | полностью (запуск и ожидание); субагенты зовутся только по прямой просьбе или инструкции | — |
| Только чтение для карточек | guard с правами reviewer через прослойку (`precheck_*`, `review_repro`); своих субагентов карточке и роли не даёт запустить прослойка; песочница у карточки родительская | частично | инструкция карточки; CI |
| Приёмка отчёта (ядро, раздел 2) | `SubagentStop` `report`: форма, до двух возвратов; `PreToolUse` на `spawn_agent`: роль и карточка — только без истории родителя (в v2 по умолчанию история передаётся); координатор: содержание, выборочная перепроверка, опровергатель | частично: форму и «без истории» держит среда, истину — координатор | — |
| Модель и уровень сессии | `-m`, `-c model_reasoning_effort=…`, `/model`; в файле агента — главнее вызова | полностью; уровень задаётся и при запуске (у Claude — только владельцем в настройках) | — |
| Координатор открывает сессию шага (инструмент облака) | инструмента создать интерактивную сессию нет; `codex exec` (без интерфейса), `codex exec resume`, SDK и `app-server` | частично | владелец запускает сессию сам по готовому промпту |
| Решения владельца в идущую сессию | `codex exec resume <ID> "<текст>"` после остановки сессии | частично | владелец вставляет сам |
| Подписка на события PR, периодическая проверка | в Codex CLI не найдено | нет | `gh pr checks`, `gh pr view --comments` по сообщению владельца |
| Облачные сессии | Codex Cloud: хуки проекта не подтверждены документацией | нет (не подтверждено) | `AGENTS.md`, раздел 3; CI |
| Stop-хук облачной платформы Claude (`stop-hook-git-check.sh`) | аналога нет и не нужен | — | правило о нём убрано из промптов |
| Ответ внешнему ревьюеру «Ответ Claude Code на комментарий …» | текстовое соглашение | полностью (текст — решение владельца, A.6 п. 4) | — |
| CI `gauntlet.yml`, `gauntlet-kit.yml`, integrity | от вендора не зависят | полностью | список `gauntlet kit unchanged` не знает `AGENTS.md`, `AGENTS.override.md` и `.codex/` (A.6 п. 1) |
| Тщательность: уровень рассуждений, план, Ultracode | `model_reasoning_effort` (до `max`/`ultra`), `/plan` и `plan_mode_reasoning_effort`, `/goal` (продолжение до самооценки «сделано»), `SubagentStop` `report` | частично: среда держит форму и красный гейт, не глубину | правило тщательности, приёмка координатора |
| Лимит токенов 99 % (п. 14) | предупреждения Codex о лимите — не подтверждено | частично | сообщение владельца «пауза по лимиту» |

## D. Пределы и источники

### D.1. Что не переносится

1. **Права ролей на инструменты.** У Claude роль получает список инструментов (`tools:`). У Codex файл агента может
   выключить shell, приложения, плагины, память и `request_permissions`, но не `apply_patch`; песочницу и одобрения
   субагент берёт у родителя, и «агент только для чтения» документация называет инструкцией, а не песочницей. Только
   чтение у `reviewer` и карточек держат guard (через прослойку) и инструкция.
2. **`write_stdin` мимо `PreToolUse`.** Ввод в уже открытую интерактивную оболочку хук не видит (документировано).
   Прослойка отклоняет запуск голой оболочки или REPL (`bash`, `python3` без аргументов), но не всё, что ведёт себя
   так же; остаток держат песочница (профиль Б) и CI.
3. **Хук не доверен — хука нет.** Новый или изменённый хук Codex пропускает до доверия в `/hooks`, а при `[features]
   hooks = false`, `--disable hooks` или недоверенном проекте хуков нет совсем. Это fail open: признак — нет строки
   статуса в первом сообщении.
4. **Профиль прав — Beta и хрупок к соседним настройкам.** `sandbox_mode` в любом загруженном слое или `--sandbox`
   отключают профиль без ошибки. Сессия с `--yolo`/`danger-full-access` не защищает на уровне ОС ни файлы набора (остаётся
   guard), ни `~/.codex/config.toml`, где хуки выключаются одной строкой (guard знает `~/.claude`, а не `~/.codex`).
5. **Вложенный `codex`** может запустить сессию без хуков. Правило `prompt` префиксное; запись такой сессии в файлы
   набора остановит только профиль Б (вложенный процесс внутри песочницы) и CI.
6. **Хуки и Gradle вне песочницы.** Команды хуков Codex запускает обычным процессом пользователя (по коду
   `command_runner.rs`), поэтому Stop-хук гоняет Gradle — и тесты, написанные агентом, — без песочницы. У Claude так же.
7. **Оркестрация между сессиями.** Координатор Codex не создаёт интерактивную сессию, не пишет в чужую идущую сессию и
   не подписывается на события PR: это делает владелец или `codex exec` / `exec resume` (A.6, B.2).
8. **Форма — не истина.** Хук `report` проверяет разделы, «доказательство:» и покрытие, но не то, что команда
   действительно запускалась: это выборочная перепроверка координатора (ядро, 2.2) и опровергатель (2.3).
9. **Codex Cloud** — без подтверждённых хуков: только `AGENTS.md`, раздел 3, и CI.
10. **`apply_patch` из оболочки, если текста патча нет в команде.** Исполняемый файл `apply_patch` в `PATH` читает патч
    из аргумента или stdin, поэтому патч из файла или переменной хук не видит. Прослойка отклоняет такой вызов, когда
    `apply_patch` стоит на месте команды (в начале, после `;`, `&&`, `|`, `$(`, `-c '…'`, через `env`/`xargs`/`exec`);
    более хитрую обёртку (функция оболочки, `eval`, скрипт в файле) она не распознает. Пути набора тогда держит
    песочница (профиль Б), область ролей и заморозку спецификации — инструкция и CI, как и обход guard у Claude.
11. **Хуки инструментов — не полная граница.** Документация Codex прямо называет хуки инструментов «useful guardrail, not
    a complete enforcement boundary»: отдельные специальные пути инструментов могут идти мимо обычного пути хуков.
    Окончательно судят песочница, CI и человек, как и у Claude.

### D.2. Известные сбои Codex по теме жалобы владельца и что с ними делает адаптер

Все строки, кроме последней, — отчёты пользователей в трекере `openai/codex` (прочитаны 2026-11-24 через сводку
страницы); ответов сопровождающих на страницах нет.

| Сбой | Источник | Что делает адаптер |
|---|---|---|
| Агент останавливается на промежуточном шаге или объявляет задачу сделанной при невыполненных критериях и красной проверке (модели gpt-5.6-terra/sol, позже GPT-6 Luna, GPT-6.1 Terra) | #41176 (CLI 0.150.1, открыт 2026-08-27) | Stop-хук `gauntletFast`; «готово» только с выводом своего прогона после последней правки (`AGENTS.md`, разделы 3, 4.8) |
| Повторные заявления «готово» без проверки поставленного сценария; признание «не проверил» в конце | #51692 (CLI 0.160.0, gpt-6.1-sol, 2026-10-07) | то же; правило тщательности п. 4 (самопроверка) |
| Сводка (recap) отмечает как пройденный тест, который ждал одобрения и не запускался | #41626 (CLI 0.151.0, 2026-08-30) | сводка не доказательство (`AGENTS.md` 4.8; координатор, «Приёмка») |
| Аудит прогнал 2 теста из 183, «успех» при нуле запущенных тестов; делегированная цель продолжала работу | #63139 (GPT-6.2 Sol, 2026-11-22) | покрытие числом («N из M»); строки `> Task` каждой задачи гейта; `testCensus` и `acceptanceCheck` набора |
| Главный ход завершается, не собрав результаты обязательных субагентов | #40932 (CLI 0.149.1, 2026-08-26) | координатор не заканчивает ход, пока таблица карточек не закрыта |
| Субагент закончил, а главный поток «не видит» результат и делает работу сам | #46048 (CLI 0.154.0, 2026-09-16) | потерянный итог — новая карточка с пометкой, а не тихая замена своей работой |
| Главный агент закрывает субагентов раньше времени, опрашивает каждые 30 с, вмешивается в здоровых | #40299 (2026-08-24; CLI 0.151–0.153) | `wait_agent` с долгим таймаутом; таймаут ожидания — не сбой; не закрывать и не подгонять |
| Усечение длинного вывода инструмента в истории | настройка `tool_output_token_limit` (Configuration Reference) | вердикт гейта — `grep` по логу, а не прочитанный хвост |

Своя рекомендация OpenAI («Prompting GPT-6.2 in Codex»): более высокий уровень рассуждений помогает доводить долгую
задачу до финальных проверок; надо сказать модели, что считается «сделано» и где нужна исчерпывающая полнота; субагентов
модель зовёт, когда так велит запрос, `AGENTS.md` или skill. Адаптер так и делает: условие остановки и покрытие — в
каждой карточке, вызов карточек — явный.

### D.3. Что проверено и как

Codex здесь не запускался: нет учётной записи, а скачанное запускать нельзя. Проверено прогоном на копии набора (каталог
`round23/guardtest/`, отдельный git-репозиторий; `GAUNTLET_GUARD` снят только в этих прогонах):
- `guard.py` набора на событиях `PreToolUse` в форме Codex (`pre-tool-use.command.input.schema.json` тега
  `rust-v0.172.0`): Bash-запись в `gauntlet/` — отказ; `agent_type: reviewer` пишет в `src/main` — отказ; `hardener` в
  `src/main` — отказ; основной агент пишет фичу — отказ; specifier пишет фичу — разрешено; `git push --force` — отказ;
  **`apply_patch` в `gauntlet/` и `apply_patch` роли reviewer — разрешены** (дыра A.2 п. 2); Bash-запись в
  `.codex/hooks.json` и `AGENTS.md` — разрешены (A.6 п. 1).
- Прослойка `codex_hooks.py guard`: те же `apply_patch` — отказ (правка, добавление, удаление, `*** Move to:` в
  `src/main` у hardener'а, относительный путь `../gauntlet/…` из подкаталога); карточка `precheck_mapper` с `sed -i` —
  отказ с правами reviewer; `./gradlew dependencies`, `javap` карточки — разрешены; `bash -i` — отказ;
  `GAUNTLET_GUARD=off` — пропуск.
- `stop_gate.py` на событии `Stop` в форме Codex: красный прогон — exit 2, причина в stderr, stdout пуст (так Codex
  продолжает ход); попытки 1–3, четвёртая — exit 0 и JSON `{"systemMessage": …}` (допустимый ответ по
  `stop.command.output.schema.json`).
- `session_start.sh` на событии `SessionStart` — строка статуса, exit 0. (Этот прогон проверял вывод скрипта, а не то, как
  его разбирает Codex: строку «[gauntlet] …» Codex отбрасывает как неверный JSON — «Проверка», п. 1.)
- Команды `.codex/hooks.json` через `bash -lc` из подкаталога (так Codex запускает хуки): отказ на `apply_patch`, строка
  статуса, 67 KB контекста, возврат отчёта reviewer'а с exit 2.
- `codex_hooks.py report`: полный отчёт карточки — пропуск; тонкий — exit 2 с перечнем, второй раз — exit 2, третий —
  exit 0 с предупреждением; пустой «Не проверено» при неполном покрытии — возврат; reviewer без «Осмотрено» — возврат.
- Все `.toml` разобраны `tomllib`, `hooks.json` — `json`; `gauntlet.rules` разобран как Python (подмножество Starlark),
  примеры `match`/`not_match` (14 правил, ошибок 0) и решения для 13 команд посчитаны по документированной семантике
  собственным оценщиком, а не Codex: `git commit --amend …`, `git push --force …`, `git pull --rebase`, `git rebase …`,
  `gh pr merge …` — `forbidden`; `git commit -m …`, `git push -u origin HEAD`, `git merge origin/main`, `git pull`,
  `gh pr create` — `allow`; `codex exec …` — `prompt`; `git worktree add …`, `./gradlew …` — правила нет.

### D.4. Не подтверждено

- Работают ли хуки проекта и читается ли `AGENTS.md` в задачах Codex Cloud (текущие страницы облака об этом молчат).
- Что `[permissions.gauntlet.filesystem.":workspace_roots"]` с `read` на отдельный файл (`CLAUDE.md`, `AGENTS.md`)
  внутри записываемого корня держится на Linux (bubblewrap) и macOS — и тем более на файл, которого ещё нет
  (`AGENTS.override.md`); что `unix_sockets` для Docker нужен и работает без `features.network_proxy`; раскрывает ли
  `writable_roots` `~`.
- Загружается ли `.codex/agents/` недоверенного проекта (по описанию слоя `.codex/` — нет; отдельно не сказано).
- Какая версия инструмента `spawn_agent` включена у владельца: в коде есть v1 (`fork_context`, по умолчанию без истории)
  и v2 (`fork_turns`, по умолчанию `all` — вся история родителя); версию выбирает переопределение в конфигурации, затем
  каталог моделей, затем признаки `[features]`. Промпты и прослойка написаны для обеих. Имя инструмента v2 в хуке по
  коду — пространство имён и имя слитно (`collaborationspawn_agent` при пространстве по умолчанию); matcher
  `spawn_agent$` ловит оба, но в живом Codex это не проверено.
- Доходит ли `AGENTS.md` до субагента (документация не говорит; поэтому тексты набора кладёт хук `SubagentStart`).
- Повторяется ли `SubagentStart` после сжатия контекста самого субагента (документация обещает повтор `SessionStart`
  только корневой сессии).
- Что `codex exec` берёт профиль `gauntlet` из конфигурации проекта, а не песочницу «только чтение», которую страница
  Non-interactive mode называет умолчанием `codex exec` (проверка — A.4 шаг 6).
- Отчёт на форуме OpenAI о том, что субагент берёт модель родителя вместо модели из файла агента
  (`community.openai.com` из этой сессии недоступен); статья DEV Community о доле ложных «tests pass» у Codex и Claude
  Code (`dev.to` недоступен) — известны только по выдаче поиска.
- Предупреждает ли Codex о 99 % лимита (метод, п. 14).

### D.5. Источники (все прочитаны 2026-11-24)

Пакет и исходники:
- npm `@openai/codex@0.172.0` (опубликован 2026-11-24T00:09:39Z): `package/README.md`, `package/package.json`.
- `raw.githubusercontent.com/openai/codex/rust-v0.172.0/…`:
  `codex-rs/hooks/src/lib.rs` (14 событий `HOOK_EVENT_NAMES`); `codex-rs/hooks/src/schema.rs`;
  `codex-rs/hooks/schema/generated/pre-tool-use.command.input.schema.json` (необязательные `agent_id`, `agent_type`),
  `pre-tool-use.command.output.schema.json`, `stop.command.input.schema.json`, `stop.command.output.schema.json`,
  `subagent-stop.command.input.schema.json`, `session-start.command.input.schema.json`;
  `codex-rs/hooks/src/events/stop.rs` (exit 2 + stderr → продолжение; пустой stderr — ошибка хука);
  `codex-rs/hooks/src/events/session_start.rs` (текст stdout — контекст модели; `additional_context_limit`);
  `codex-rs/hooks/src/engine/discovery.rs` (таймаут по умолчанию 600 с, предел только у `SessionEnd`/`Interrupt`);
  `codex-rs/hooks/src/engine/command_runner.rs` (запуск `$SHELL -lc` в cwd сессии, окружение сессии, без песочницы);
  `codex-rs/core/src/hook_runtime.rs` (`subagent_hook_context`: `agent_type` = роль из вызова или `default`;
  `PreToolUse`/`PostToolUse`/`PermissionRequest` получают его);
  `codex-rs/core/src/tools/hook_names.rs` (`apply_patch` с псевдонимами `Write`/`Edit`, `spawn_agent` — `Agent`);
  `codex-rs/core/src/tools/handlers/apply_patch.rs` (`tool_input = {"command": <патч>}`);
  `codex-rs/apply-patch/src/parser.rs` (маркеры `*** Add File: `, `*** Delete File: `, `*** Update File: `,
  `*** Move to: `); `codex-rs/core/src/safety.rs` (`assess_patch_safety`: патч вне записываемых путей — отказ при
  `never`, вопрос при `on-request`); `codex-rs/core/src/agent/role.rs` (что переопределяет роль; выключаемые
  возможности); `codex-rs/core/src/agent/child_config.rs`; `codex-rs/core/src/tools/handlers/multi_agents.rs`
  (субагент наследует одобрения, песочницу, cwd); `codex-rs/core/src/tools/handlers/multi_agents_spec.rs`
  (`fork_context`, `fork_turns`, `agent_type`); `codex-rs/core/src/tools/handlers/multi_agents_common.rs` (ожидание по
  умолчанию 30 000 мс); `codex-rs/cli/src/main.rs` (`codex sandbox --permission-profile`).
Документация (адрес `developers.openai.com/codex/<страница>` переадресует на указанный):
- https://learn.chatgpt.com/docs/hooks — события, места `hooks.json`, доверие, контракт, `apply_patch`, `write_stdin`.
- https://learn.chatgpt.com/docs/agent-configuration/agents-md — поиск `AGENTS.md`, `project_doc_max_bytes` 32 KiB.
- https://learn.chatgpt.com/docs/agent-configuration/subagents — свои агенты, поля, наследование песочницы.
- https://learn.chatgpt.com/docs/agent-configuration/rules — `prefix_rule`, решения, разбор `bash -lc`.
- https://learn.chatgpt.com/docs/permissions — профили прав (Beta), `extends`, `:workspace_roots`, сеть, сокеты.
- https://learn.chatgpt.com/docs/sandboxing и https://learn.chatgpt.com/docs/agent-approvals-security — режимы,
  защищённые пути `.git`, `.codex`, `.agents`, `.aws`, `approvals_reviewer`, отказ от `untrusted`.
- https://learn.chatgpt.com/docs/config-file/config-reference, …/config-advanced, …/config-basic — ключи, слой проекта,
  доверие, порядок слоёв, ключи, которые проект не переопределяет.
- https://learn.chatgpt.com/docs/non-interactive-mode — `codex exec`, `--json`, `--output-schema`, `-o`, `resume`, `--trust`.
- https://learn.chatgpt.com/docs/developer-commands — флаги CLI (`--dangerously-bypass-hook-trust`, `--add-dir`,
  `codex sandbox`, `codex execpolicy`), команды `/hooks`, `/subagents`, `/plan`, `/goal`, `/import`.
- https://learn.chatgpt.com/docs/models — модели и уровни на дату.
- https://learn.chatgpt.com/guides/prompting-gpt-6-2-astra — уровень рассуждений, субагенты, `AGENTS.md`.
- https://learn.chatgpt.com/docs/long-running-work — Goal mode.
- https://learn.chatgpt.com/docs/github-action — `openai/codex-action@v1`.
- https://learn.chatgpt.com/docs/cloud, https://learn.chatgpt.com/docs/environments/cloud-environments — Codex Cloud.
- https://learn.chatgpt.com/docs/import — перенос из Claude Code.
- https://learn.chatgpt.com/docs/feature-maturity; https://learn.chatgpt.com/docs/changelog (общая доступность хуков —
  запись от 2026-05-14).
Отчёты пользователей: https://github.com/openai/codex/issues/41176, …/40932, …/46048, …/40299, …/41626, …/51692,
…/63139.
Дополнительные источники проверки — в разделе «Проверка» ниже.

## Проверка

Проверял независимый верификатор 2026-11-24, по свежим первоисточникам и своими запросами, а не по выпискам автора:
npm-реестр; тег `rust-v0.172.0` репозитория `openai/codex`, выкачанный заново (`git clone --depth 1 --filter=blob:none
--sparse`, коммит `3d86e43b075adeba2193ec5c22ac92f55afd82e6`; аннотированный тег `fc3036db…`) в
`round23/verify-codex/src`; 21 страница документации, скачанная заново в `round23/verify-codex/docs`; семь отчётов в
трекере. Скачанное только читалось. Пути `codex-rs/…` ниже — от корня этого тега; номера строк — по нему же.

### Что проверено

| Утверждение адаптера | Итог | Источник (прочитан 2026-11-24) |
|---|---|---|
| `@openai/codex` 0.172.0, опубликован 2026-11-24T00:09:39Z | подтверждено | `npm view @openai/codex time`: `"0.172.0": "2026-11-24T00:09:39.503Z"`; `dist-tags` и `version` → 0.172.0 |
| `developers.openai.com/codex/*` → `learn.chatgpt.com/docs/*` | подтверждено: `HTTP/2 308` | `curl -D -` на `/codex/hooks` и `/codex/subagents` |
| 14 событий хуков, среди них `SessionStart`, `PreToolUse`, `Stop`, `SubagentStart`, `SubagentStop` | подтверждено | `codex-rs/hooks/src/lib.rs:29-44` |
| Поля stdin: `session_id`, `cwd`, `tool_name`, `tool_input`, необязательные `agent_id`/`agent_type` у `PreToolUse`; `stop_hook_active`, `last_assistant_message` у `Stop`/`SubagentStop` | подтверждено | `codex-rs/hooks/schema/generated/*.command.input.schema.json` |
| У субагента тот же `session_id`, что у корня | подтверждено | `codex-rs/core/src/session/session.rs:673-676` («identity shared by the root thread and all descendant threads»); страница hooks: «Subagent hooks use the parent session id» |
| `agent_type` = роль из вызова или `default`; корень — `Stop`, субагент — `SubagentStop` | подтверждено | `codex-rs/core/src/hook_runtime.rs:1101-1108`, `:384-429`; `codex-rs/core/src/agent/role.rs:30` |
| `apply_patch` в хуке — `tool_name: "apply_patch"`, псевдонимы `Write`/`Edit`, патч в `tool_input.command` | подтверждено | `codex-rs/core/src/tools/hook_names.rs`; `codex-rs/core/src/tools/handlers/apply_patch.rs:370-375` |
| `write_stdin` не запускает `PreToolUse` заново | подтверждено | страница hooks, «Tool coverage»; тест `exec_command_pre_tool_use_payload_skips_write_stdin` (`codex-rs/core/src/tools/handlers/unified_exec_tests.rs:576`) |
| Отказ — `permissionDecision: "deny"` или exit 2 + stderr | подтверждено | страница hooks, раздел PreToolUse |
| `Stop`/`SubagentStop`: exit 2 + stderr — продолжение хода; пустой stderr — ошибка хука; при exit 0 нужен JSON или пусто | подтверждено | `codex-rs/hooks/src/events/stop.rs:263-360`; страница hooks |
| Таймаут по умолчанию 600 с, предел только у `SessionEnd`/`Interrupt` | подтверждено | `codex-rs/hooks/src/engine/discovery.rs:957-980` |
| Команды хуков — `$SHELL -lc` в cwd сессии, с окружением сессии, без песочницы | подтверждено; окружение без нескольких служебных переменных авторизации, `GAUNTLET_*` и `ORG_GRADLE_*` доходят | `codex-rs/hooks/src/engine/command_runner.rs:283-284, 448-500`; `codex-rs/protocol/src/shell_environment.rs:18-29` |
| `additionalContextLimit: 0` — текст целиком | подтверждено (и для `SubagentStart`) | страница hooks, «Large hook output»; `codex-rs/hooks/src/output_spill.rs:71`; `discovery.rs:695-713` |
| Matcher — регулярное выражение | уточнено: только буквы, цифры, `_`, `\|` — точное сравнение с вариантами; иначе поиск по регулярному выражению | `codex-rs/hooks/src/engine/matcher.rs` |
| Свои агенты `.codex/agents/*.toml`: `name`, `description`, `developer_instructions`; `model`/`model_reasoning_effort` главнее вызова; `sandbox_mode`, `approval_policy`, `mcp_servers` не действуют | подтверждено | страница subagents; `codex-rs/core/src/agent/role.rs:33-120` |
| Роль выключает только shell, apps, plugins, memories, `request_permissions`, но не `apply_patch`; неизвестный `agent_type` — ошибка | подтверждено | `role.rs:91-101`, `:52-56` («unknown agent_type») |
| `spawn_agent` v1 `fork_context` (по умолчанию без истории), v2 `fork_turns` (по умолчанию `all`); ожидание 30 000 мс | подтверждено; до 1 ч | `codex-rs/core/src/tools/handlers/multi_agents_spec.rs:609-682`; `multi_agents_common.rs:22-24`; `codex-rs/core/src/config/mod.rs:281-283` |
| Песочница: `.git`, `.agents`, `.codex`, `.aws` только для чтения в `workspace-write` и при `extends = ":workspace"` | подтверждено (`.agents`, `.codex`, `.aws` — когда это каталоги) | страницы agent-approvals-security («Protected paths in writable roots») и permissions |
| Профили прав: `default_permissions`, `[permissions.<имя>]`, `extends`, `:workspace_roots`, `network.enabled`, `unix_sockets`; `sandbox_mode` в любом слое или `--sandbox` молча выключает профиль | подтверждено | страница permissions («Permission profiles do not compose with the older sandbox settings…») |
| Проект может задавать `approval_policy`, `default_permissions`, `[permissions]`, `[features]`, `[agents]` | подтверждено: в списке игнорируемых ключей проекта их нет | страница config-advanced, «Project config files can't override…» |
| `assess_patch_safety`: патч вне записываемых путей — отказ при `never`, вопрос при `on-request` | подтверждено | `codex-rs/core/src/safety.rs:67-125` |
| `.codex/rules/*.rules`, `prefix_rule`, `allow`/`prompt`/`forbidden`, `match`/`not_match`, `codex execpolicy check --pretty --rules` | подтверждено | страница rules |
| `codex sandbox --permission-profile NAME -C DIR -- CMD` (Linux, macOS, Windows) | подтверждено | страница developer-commands; `codex-rs/cli/src/lib.rs:63-77` |
| `--dangerously-bypass-hook-trust`, `--add-dir`, `--disable <feature>`, `codex exec --trust`, `--json`, `-o`, `exec resume <SESSION_ID>`, `/hooks`, `/subagents`, `/plan`, `/goal`, `/import`, `/status`, `/model` | подтверждено | страницы developer-commands, non-interactive-mode, models, long-running-work, import |
| `AGENTS.md` склеивается от корня к cwd, предел `project_doc_max_bytes` 32 KiB | подтверждено | страница agents-md |
| Модели `gpt-6.2-astra`, `gpt-6.2-sol`, `gpt-6.1-terra`, `gpt-6-luna`; уровни до `max`/`ultra`; Ultra сам делегирует субагентам | подтверждено; у Luna нет Ultra | страницы models и subagents; гид «Prompting GPT-6.2 in Codex» («With Ultra, Codex decides on its own when to bring in subagents») |
| Хуки — общая доступность 2026-05-14 | подтверждено | changelog, запись 2026-05-14 («This launch also includes Hooks general availability») |
| `/import` переносит хуки и субагентов и велит пересмотреть ограничения инструментов | подтверждено | страница import |
| Отчёты #41176, #51692, #41626, #63139, #40932, #46048, #40299 | подтверждено: заголовки, даты, версии CLI и суть совпадают с D.2; ответов сопровождающих нет | страницы трекера через WebFetch (прямой `curl` к github.com для этого репозитория прокси сессии не пускает) |
| `ORG_GRADLE_PROJECT_publicRepositories=true` | подтверждено — это переключатель самого набора | `gauntlet/CLAUDE.md:43`; метод, приложение E |
| Ядро (core.md 1–5) в промптах: правило тщательности, формат отчёта, приёмка, карточки 4.1–4.6, сбои Codex по трекеру | подтверждено построчным сравнением | `core.md`; B.1–B.4 |

### Что исправлено и почему

1. **Строка статуса не доходила до модели.** Вывод `SessionStart`, который начинается с «[» или «{», Codex разбирает как
   JSON; не разобрался — хук помечается упавшим («hook returned invalid session start JSON output»), а текст в контекст
   не идёт (`codex-rs/hooks/src/engine/output_parser.rs:360-363`, `codex-rs/hooks/src/events/session_start.rs:245-298`,
   тест `invalid_json_like_stdout_fails_instead_of_becoming_model_context`). `session_start.sh` печатает
   «[gauntlet] active - …» (прогон в `round23/verify-codex/gt`). Утверждение A.2 п. 1 «работают без правки» и статус
   «полностью» в C для `session_start.sh` были неверны; признак «хуки работают» из `AGENTS.md` не срабатывал бы никогда.
   Исправлено: в `.codex/hooks.json` вывод идёт через `sed '1s/^/gauntlet status: /'`; тексты A.2, C, D.3, `AGENTS.md`
   (раздел 0) и промпт координатора — под новую строку. Снимок дерева для Stop-хука (`stop_gate.py --record-start`)
   писался и раньше.
2. **`apply_patch` из оболочки обходил guard и прослойку.** `exec_command` сам перехватывает
   `apply_patch <<'EOF' … EOF` и `cd <каталог> && apply_patch <<'EOF' … EOF` и применяет патч
   (`codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs:175-205`;
   `codex-rs/apply-patch/src/invocation.rs:120-147, 253-276`), а `apply_patch`/`applypatch` ещё и лежат в `PATH`
   исполняемым файлом (`codex-rs/arg0/src/lib.rs:21-22, 308-313`; патч — аргументом или из stdin,
   `codex-rs/apply-patch/src/standalone_executable.rs`). `PreToolUse` для такого вызова приходит до перехвата, как `Bash`
   с текстом команды (`exec_command.rs:331-339`, `codex-rs/core/src/tools/registry.rs:1176-1191`); второго события
   `apply_patch` нет. `guard.py` тело heredoc считает данными (метод, раздел 6). Прогон: `guard.py` и прежняя прослойка
   пропустили все шесть проб из оболочки — правку `gauntlet/README.md`, `cd gauntlet && …`, запись reviewer'а и карточки в `src/main`,
   правку hardener'а в `src/main`, правку фичи основным агентом. Без профиля Б это открывало и пути набора, с ним — область
   ролей и заморозку спецификации на обычном пути правки Codex. Исправлено в прослойке (`guard`): у команды с
   `apply_patch`/`applypatch` пути патча судятся как Write с учётом `cd <каталог> &&`; вызов на месте команды без текста
   патча — отказ. Остаток — D.1 п. 10.
3. **Заголовок патча с пробелами в начале обходил прослойку.** Парсер Codex обрезает строку с обеих сторон и только потом
   ищет маркер `*** Add File:` / `*** Delete File:` / `*** Update File:` (`codex-rs/apply-patch/src/streaming_parser.rs:175-176,
   107-131`), а регулярное выражение прослойки требовало маркер с начала строки. Исправлено: пути ищутся так же —
   по обрезанной строке (проверено и с табуляцией и неразрывным пробелом).
4. **`[features] multi_agent = true` — устаревший ключ.** В 0.172.0 он `Stage::Deprecated`
   (`codex-rs/features/src/lib.rs:1712-1716`), а при его наличии в слое пользователя или проекта Codex при старте
   печатает предупреждение (`codex-rs/config/src/loader/mod.rs:533-546`). Справочник конфигурации ещё называет его
   «stable» — документация отстаёт от кода. Исправлено: `[agents] enabled = true` (`codex-rs/config/src/config_toml.rs:807-810`;
   страница subagents: «agents.enabled defaults to true»).
5. **Инструменты субагентов v2.** Версию выбирает переопределение в конфигурации, затем каталог моделей, затем признаки
   (`codex-rs/core/src/config/mod.rs:1803-1810`), так что v2 может оказаться у владельца без его выбора. В v2 нет
   `send_input`, `resume_agent`, `close_agent`; есть `send_message` (без нового хода), `followup_task` (запускает ход),
   `wait_agent` без текста итога, `list_agents`, `interrupt_agent`, а `task_name` обязателен
   (`multi_agents_spec.rs:108-375`); итог ребёнка приходит родителю сообщением (`codex-rs/core/src/session/mod.rs:2838-2846`).
   Промпт координатора говорил только о v1. Исправлено: возврат отчёта, ожидание и вызов описаны для обеих версий
   (B.2, `AGENTS.md`, C).
6. **«Опровергатель без истории» держался только инструкцией, а в v2 умолчание обратное.** Без `fork_turns: "none"` v2
   передаёт субагенту всю историю родителя — с выводами первой карточки, против ядра 2.3. `PreToolUse` видит
   `spawn_agent` с аргументами в `tool_input` (страница hooks: «spawn_agent also matches Agent»;
   `registry.rs:1215-1234`); в v2 имя в хуке — пространство имён и имя слитно (`codex-rs/core/src/tools/multi_agent_tool.rs`,
   `codex-rs/core/src/tools/mod.rs:53-67`, пространство по умолчанию `collaboration` — `codex-rs/core/src/config/mod.rs:284`).
   Добавлено в прослойку: роль или карточка набора с историей родителя — отказ; запуск субагента из роли или карточки —
   отказ (их промпты и так велят «своих субагентов не создавай»; теперь это держит хук); matcher `PreToolUse` — `^(Bash|apply_patch)$|spawn_agent$`.
   В живом Codex не проверено (D.4).
7. **`codex exec` без владельца.** В `codex exec` политика одобрений принудительно `never`, если ревьюер одобрений не
   `auto_review` (`codex-rs/exec/src/lib.rs:641-646, 860-890`), а документация называет его песочницу по умолчанию «только
   чтение». Адаптер этого не говорил. Ослабления нет (всё, что требует одобрения, падает), но сессия может не суметь писать
   в `src/`. Дописано в B.2 и A.4 шаг 6, неподтверждённое — в D.4.
8. **`AGENTS.override.md`.** Codex в каждом каталоге берёт `AGENTS.override.md` раньше `AGENTS.md` (страница agents-md:
   «checks for AGENTS.override.md, then AGENTS.md … at most one file per directory»): файл, созданный агентом, подменил бы
   инструкции следующих сессий. Дописано: профиль `gauntlet` (строка `read`, с оговоркой в D.4), `AGENTS.md` (правило 1),
   рекомендация A.6 п. 1 и строка C.
9. **`--approve-for-me` (`--not-so-yolo`).** Флаг включает `workspace-write` (профиль тогда молча не действует) и отдаёт
   одобрения автоматическому ревьюеру (страница developer-commands). Добавлен в запреты A.4 шаг 3.
10. **Мелочи.** `fork` добавлен в matcher первого обработчика `SessionStart` (у Claude набор зовёт его на любом старте;
    `session_start.sh` идемпотентен); строка ответа внешнему ревьюеру без подписи — «… внешнего ревьюера» (метод, п. 19);
    «не заканчивай ход, пока идёт фоновый прогон гейтов» явно сохранён в правилах сессии (приложение D); цена
    `additionalContextLimit: 0` и повтор только для корневой сессии — в A.5; новые пункты D.1 (10, 11); размер `AGENTS.md`
    в B.1; оговорка про `$SHELL -lc` в A.7.
11. **Снято из D.4 как подтверждённое по коду.** `forbidden` отклоняет команду до запуска, внутри песочницы тоже:
    решение правил считается для каждой команды `exec_command`
    (`codex-rs/core/src/tools/handlers/unified_exec/preparation.rs:63-101`), а `Forbidden` возвращает отказ, не запуская
    (`codex-rs/core/src/exec_policy.rs:422-433`, `codex-rs/core/src/tools/orchestrator.rs:206-207`). `thread.started`
    несёт `thread_id` сессии (`codex-rs/exec/src/event_processor_with_jsonl_output.rs:407-411`), а `exec resume`
    принимает «Conversation/session id (UUID) or thread name» (`codex-rs/exec/src/cli.rs:228-235`) — запуском не проверено.

Файлы-источники исправлены вместе с этим документом: `adapters/codex/codex_hooks.py`, `adapters/codex/files/.codex/hooks.json`,
`adapters/codex/files/.codex/config.toml`, `adapters/codex/files/AGENTS.md`, `adapters/codex/files/coordinator-prompt.md`,
`adapters/codex/codex.template.md`. Этот документ из них и собран заново. Роли, карточки и правила
(`.codex/agents/*.toml`, `.codex/rules/gauntlet.rules`) проверены и не менялись.

### Как проверял исправления

Codex не запускался (нет учётной записи; скачанное не исполнялось). Прогоны — на своей копии набора в
`round23/verify-codex/gt/proj` (отдельный git-репозиторий, `GAUNTLET_GUARD` снят только в этих прогонах):
- исправленная прослойка на 38 событиях в форме схем 0.172.0: инструмент `apply_patch` (обычные заголовки, пробелы,
  табуляция с неразрывным пробелом, `*** Move to:`, `../gauntlet` из подкаталога), heredoc и `applypatch` из оболочки у
  основного агента, reviewer, hardener и карточки, `cd <каталог> &&`, `apply_patch < файл`, `cat … | apply_patch`,
  `apply_patch "$(cat …)"`, `bash -lc '…'`, `xargs`, поиск `rg apply_patch` и `git log -S apply_patch` (должны проходить),
  прежние пробы автора (`sed -i` карточки, `./gradlew dependencies`, `javap`, `bash -i`, `git push --force`), `spawn_agent`
  v1 и v2 с историей и без, из карточки и роли, встроенный `explorer`; `GAUNTLET_GUARD=off` — пропуск. Расхождений с
  ожидаемым — 0 из 38;
- команды нового `.codex/hooks.json` через `bash -lc` из подкаталога: строка статуса начинается с «gauntlet status:», под
  правило «похоже на JSON» не попадает; контекст — 68 150 байт, начинается с «#»; heredoc в `gauntlet/` и `spawn_agent` v2
  без `fork_turns` — отказ; matcher'ы проверены по правилам `matcher.rs` (точное сравнение или поиск) на `Bash`,
  `apply_patch` (с `Write`/`Edit`), `spawn_agent`, `collaborationspawn_agent`, `update_plan`, `write_stdin`, MCP;
- `codex_hooks.py report` после правки файла: полный отчёт — 0; тонкий — 2, 2, затем 0 с предупреждением; reviewer — 0.

### Что осталось не подтверждённым

- Всё из D.4 — в живом Codex ничего не запускалось; оценки форм команд — по коду и документации тега `rust-v0.172.0`.
- Имя инструмента v2 в хуке (`collaborationspawn_agent`) выведено из кода, не из события; если оно иное, но кончается на
  `spawn_agent`, matcher его поймает; иначе проверка `spawn_agent` молча не сработает — проверка A.4 шаг 8 это покажет.
- Отчёты в трекере прочитаны через сводку WebFetch: прямой доступ к github.com для `openai/codex` прокси этой сессии
  закрыт (ответ 403 с текстом политики).
- Станут ли субагенты Codex тщательнее — не мерилось: адаптер, как и ядро, судит отчёт по доказательствам и держит форму
  хуком, а «глубину» среда не измеряет.
