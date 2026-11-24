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
{{FILE:files/.codex/config.toml}}
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
{{FILE:files/.codex/hooks.json}}
```

`.codex/rules/gauntlet.rules` (язык — Starlark; `match` и `not_match` Codex проверяет при загрузке):

```python
{{FILE:files/.codex/rules/gauntlet.rules}}
```

### A.8. Прослойка `gauntlet/adapters/codex/codex_hooks.py` (для PR владельца набора)

Проверена на синтетических событиях по схемам Codex 0.172.0 вместе с `guard.py` набора (D.3 и «Проверка»); в живом
Codex не запускалась.

```python
{{FILE:codex_hooks.py}}
```

## B. Промпты

### B.1. `AGENTS.md` (инструкция проекта)

Codex склеивает `AGENTS.md` от корня проекта до рабочего каталога; предел — `project_doc_max_bytes` (32 KiB по
умолчанию). Этот файл — 17,3 KB. Включения других файлов в `AGENTS.md` нет, поэтому `gauntlet/CLAUDE.md` (67 KB) приносит
хук (A.5).

````markdown
{{FILE:files/AGENTS.md}}
````

### B.2. Промпт координатора

Вставляется первым сообщением сессии координатора (CLI: `codex --add-dir <каталог плана> -m <модель> -c
model_reasoning_effort=<уровень> "$(cat coordinator-prompt.md)"`). Угловые скобки заполняет владелец.

```markdown
{{FILE:files/coordinator-prompt.md}}
```

### B.3. Роли — свои агенты Codex

Обязательные поля файла агента — `name`, `description`, `developer_instructions`; `model` и `model_reasoning_effort`
главнее значений при вызове. `sandbox_mode`, `approval_policy`, `mcp_servers` в файле агента не действуют: всё это у
субагента родительское.

`.codex/agents/specifier.toml`:

```toml
{{FILE:files/.codex/agents/specifier.toml}}
```

`.codex/agents/hardener.toml`:

```toml
{{FILE:files/.codex/agents/hardener.toml}}
```

`.codex/agents/reviewer.toml`:

```toml
{{FILE:files/.codex/agents/reviewer.toml}}
```

### B.4. Карточки пред-проверки — свои агенты Codex

Карточка 4.5 (ревью PR) — роль `reviewer` (B.3) с правилом тщательности. Общая часть у карточек одна и та же
(границы, правило тщательности, форма отчёта) — она повторяется в каждом файле, потому что файл агента
самодостаточен.

`.codex/agents/precheck_mapper.toml` (4.1):

```toml
{{FILE:files/.codex/agents/precheck_mapper.toml}}
```

`.codex/agents/precheck_framework.toml` (4.2):

```toml
{{FILE:files/.codex/agents/precheck_framework.toml}}
```

`.codex/agents/precheck_critic.toml` (4.3):

```toml
{{FILE:files/.codex/agents/precheck_critic.toml}}
```

`.codex/agents/precheck_refuter.toml` (4.4):

```toml
{{FILE:files/.codex/agents/precheck_refuter.toml}}
```

`.codex/agents/review_repro.toml` (4.6):

```toml
{{FILE:files/.codex/agents/review_repro.toml}}
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
