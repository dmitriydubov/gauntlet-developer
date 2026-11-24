# Адаптер gauntlet для Gemini 4 Carbon (Google Antigravity: agy и приложение)

Ревизия адаптера 1, 2026-11-24; исправлена независимой проверкой того же дня (раздел «Проверка» в конце). Язык —
русский, как `gauntlet/CLAUDE.md`; ключи настроек, имена файлов и команды вендора — как есть. Ядро (`core.md`:
правило тщательности, приёмка отчётов, формат отчёта, карточки) перенесено без ослаблений; где Antigravity чего-то
не умеет, это сказано прямо, с запасным путём.

Что проверено в этой работе: прослойка хуков `agy_hooks.py` — локально, на синтетическом репозитории с настоящими
`guard.py`, `stop_gate.py`, `session_start.sh` набора и на входе в формате документации agy (раздел D.5). Что не
проверено: ничего не запускалось в живом agy — установщик и сайт antigravity.google из этой сессии недоступны. Поэтому
каждая строка «частично» в разделе C держится на проверке установки (A.6), а не на этом документе.

---

## A. Что это и куда ставить

### A.1. Что такое «gemini carbon»

- **Модель.** Gemini 4 Carbon — модель Google; в Gemini API её идентификатор `gemini-4-carbon`, описание в каталоге
  официальной утилиты Gemini API: «Our most capable reasoning model, built for sustained agentic coding, multimodal
  knowledge work, scientific discovery, and cybersecurity defense» [S5]. Карточка модели DeepMind (обновлена
  10.11.2026): тратит больше токенов рассуждений, чем Gemini 4 Argon, чтобы «explore hypotheses thoroughly, reason
  deeply, and run extended verification loops», уровни рассуждений настраиваются [S9]. Развёртывание: подписчикам
  Google AI Ultra в Antigravity, приложении Gemini и AI Mode; API — в AI Studio [S10, S11]. Доступ на тарифе Pro —
  только сторонний отчёт, «не подтверждено» [S24].
- **Где она работает как агент.** В Google Antigravity: настольное приложение (Antigravity 2.x), Antigravity CLI `agy`
  и расширения IDE. У CLI и приложения общий движок агента и общие настройки и разрешения [S2]. В agy модель
  выбирается в `/model` и флагом `--model` с уровнями Low, Medium, High [S1: 1.5.5, 1.5.8]; уровень — `--effort` или
  `/effort` [S1: 1.2.11]. Версия agy на дату адаптера — 1.5.16 [S1].
- **Почему не Gemini CLI.** README репозитория Gemini CLI: он теперь только для Gemini Code Assist Standard/Enterprise;
  бесплатный доступ и Google AI Pro/Ultra переведены на Antigravity CLI 18.06.2026; Gemini CLI «not tuned for the
  Gemini 4 series» [S3]; ещё в феврале 2026 Google советовала его для терминала и headless [S23]. В
  `@google/gemini-cli-core@0.71.1` (`dist/src/config/models.js`) нет ни одного идентификатора Gemini 4 [S4].
  Jules с Gemini 4 Carbon — «не подтверждено».

Итог: «gemini carbon» владельца — это Gemini 4 Carbon в Antigravity. Адаптер — для agy ≥ 1.5.16; те же файлы
`.agents/` читает приложение Antigravity [S6]. Удалённые агенты (`--remote-agent`) для сессий задач не используются:
работают ли там хуки рабочей области — «не подтверждено».

### A.2. Файлы в проекте

| Путь | Что | Раздел |
|---|---|---|
| `GEMINI.md` (корень) | правило проекта, всегда в контексте (≤ 24 KB) | B.1 |
| `.agents/hooks.json` | хуки рабочей области: SessionStart, PreToolUse, Stop | B.5 |
| `.agents/agents/specifier/agent.md`, `hooks.json` | роль specifier и её хук | B.3 |
| `.agents/agents/hardener/agent.md`, `hooks.json` | роль hardener, хук области и Stop с `mutationGate` | B.3 |
| `.agents/agents/reviewer/agent.md`, `hooks.json` | роль reviewer, хук только-чтение | B.3 |
| `.agents/agents/precheck-mapper/agent.md` и ещё 4 | карточки 4.1–4.4 и 4.6 ядра | B.4 |
| `gauntlet/adapters/antigravity/agy_hooks.py` | прослойка: событие agy → хуки набора → ответ agy | B.5, прил. 1 |
| `gauntlet/adapters/antigravity/agy_card_check.py` | механическая приёмка прогона карточки | B.6, прил. 2 |
| `gauntlet/adapters/antigravity/report.schema.json` | JSON-схема отчёта сабагента (ядро, раздел 3) | B.6 |
| `gauntlet/adapters/antigravity/settings.permissions.json` | образец настроек и разрешений | B.6 |
| `gauntlet/adapters/antigravity/coordinator.md` | промпт координатора | B.2 |

Все они — файлы человека. Скрипты и образцы лежат под `gauntlet/`, поэтому их правку агентом видит CI-проверка
`gauntlet kit unchanged`. Файлы `.agents/` и `GEMINI.md` эта проверка сегодня не видит — решение владельца A.7, п. 1.
`AGENTS.md` адаптер не создаёт (A.7, п. 4). Готовые файлы этой ревизии лежат рядом с документом:
`round23/adapters/gemini/files/`.

### A.3. Что настроить

1. **agy.** Установить официальным установщиком и один раз войти интерактивно: headless-прогоны берут сохранённые
   учётные данные [S6: headless]. Python 3 и git — в `PATH` (на них работают хуки).
2. **Доверие рабочей области.** При первом запуске подтвердить доверие корню репозитория: хуки рабочей области
   грузятся после этого (настройка `trustedWorkspaces`) [S6: settings, hooks].
3. **Настройки** `~/.gemini/antigravity-cli/settings.json`: влить блок из `settings.permissions.json` (B.6), заменив
   `<HOME>` на домашний каталог. Ключи: `agentMode` (`""`, `accept-edits`, `auto`, `plan`), `toolPermission`
   (по умолчанию `request-review`), `permissions.allow/ask/deny` со строками `действие(цель)`; порядок Deny > Ask >
   Allow, deny действует во всех режимах [S6: settings, permissions]. С agy 1.5.7 режим по умолчанию — Auto, и для
   headless-прогонов `-p` тоже: правки без вопроса, команды — в песочнице терминала, а выход из неё решает отдельный
   агент-рецензент на лёгкой модели [S1: 1.3.5, 1.5.4, 1.5.7, 1.5.12]; образец B.6 задаёт `accept-edits`, а прогоны
   карточек координатор запускает с `--mode accept-edits` [S1: 1.1.12], чтобы не зависеть от настроек. Имя ключа
   `toolPermission` — только по сторонним справочникам, «не подтверждено»; значения `request-review` и `strict` есть в
   журнале изменений [S1: 1.1.11, 1.5.7]. Те же правила можно задать в области Project
   командой `/permissions` (хранятся в `~/.gemini/config/projects/`, вне репозитория [S1: 1.0.12]). Из репозитория
   разрешения не приходят: `.agents/settings.json` больше не читается, а может ли нести их `<проект>/.gemini/config.json`
   в CLI — «не подтверждено» [S6: changelog]. Поэтому разрешения живут у пользователя, и проверка установки (A.6) их
   сверяет; для headless-прогонов есть флаг `--settings <файл>` [S1: 1.5.8], но сливает ли он `permissions` с
   пользовательскими — «не подтверждено».
4. **Окружение процесса agy:** `ORG_GRADLE_PROJECT_publicRepositories=true`; `GAUNTLET_GUARD` и `GAUNTLET_STOP_HOOK`
   не заданы (кроме админ-окружения владельца, как в наборе).
5. **Модель:** `agy --model "<Gemini 4 Carbon (High) — имя как в /model>" --effort high`. Слаг `gemini-4-carbon-high`
   встречается в сообщениях форума (по поисковой выдаче) — документацией «не подтверждено»; берите имя из `/model`. Режимы
   `Orchestrator (Carbon)` не используются (D.2).
6. **Песочница терминала** — решение владельца A.7, п. 2.
7. По желанию: `AGY_CLI_AUTO_COMPACT_OVERRIDE` (например `80%`) — позже сжимать контекст [S1: 1.5.15].

### A.4. Как переиспользуются файлы набора, а не копируются

- **`gauntlet/CLAUDE.md`** остаётся единственным текстом процесса. Встроить его в правило Antigravity нельзя: правило
  обрезается на 24 000 байт после раскрытия включений `@[метка](путь)` [S6: rules], а «## Жёсткие правила» начинается
  на байте 28 356 из 68 018 (замер набора 24.11.2026; числа растут с каждой ревизией) — встроенный файл молча
  потерял бы жёсткие правила, источники и «Когда застрял». Поэтому `GEMINI.md` даёт ссылку `@gauntlet/CLAUDE.md`
  (такая форма только ссылается на путь, не встраивает [S6: rules]) и требует прочитать файл целиком с доказательством
  чтения (B.1, раздел 0).
- **Роли.** Текст роли — те же `.claude/agents/<роль>.md`; `agent.md` в `.agents/agents/` содержит только настройки
  Antigravity и сопоставление инструментов и хуков, а первым действием заставляет сабагента прочитать файл роли.
- **Хуки.** `guard.py`, `stop_gate.py`, `session_start.sh` не меняются. `agy_hooks.py` переводит событие agy в форму,
  которую они читают, и их ответ — в ответ agy. Человеческие пути Antigravity (`.agents/`, `.gemini/`, `GEMINI.md`,
  `AGENTS.md`, `~/.gemini/`, `~/.agents/` — оттуда agy 1.5.16 берёт навыки пользователя [S1: 1.5.16]) прослойка
  добавляет к списку guard'а в памяти процесса, не трогая файл. Она опирается на
  внутренние имена `guard.py` (`HUMAN_OWNED`, `user_config_violation`, `Context.features_dirs`, `Context.frozen`):
  после каждого обновления набора — `agy_hooks.py selftest` (A.6, п. 1).
- **CI** (`gauntlet.yml`, `gauntlet-kit.yml`) от вендора не зависит и не меняется.

### A.5. Как запускается работа

- **Сессия задачи:** владелец создаёт рабочую копию от основной ветки (`git worktree add ../step-N -b <ветка>
  origin/<основная>`), в ней — `agy --model … --effort high`, первым сообщением — промпт координатора по приложению D
  с заменами (B.2, раздел 4). Одна задача — одна сессия — одна ветка — один PR.
- **Координатор:** отдельная сессия agy в своей рабочей копии с промптом B.2. Пред-проверку он запускает
  headless-прогонами агентов-карточек (`agy -p … --agent precheck-mapper …`), каждый — свежая беседа без его
  истории, что и даёт независимость опровергателя (ядро, 2.3).

### A.6. Проверка установки (до первой задачи и после каждого обновления agy или набора)

Не прошёл пункт — соответствующая строка раздела C считается «нет», и действует её запасной путь.
1. `env -u GAUNTLET_GUARD python3 -I gauntlet/adapters/antigravity/agy_hooks.py selftest "$PWD"` → `selftest: PASSED`.
2. `agy -p "/hooks"` → группа `gauntlet` с SessionStart, PreToolUse, Stop [S1: 1.1.12 — `/hooks` в режиме `-p`].
3. `agy -p "/permissions"` → правила deny из B.6 на месте.
4. В интерактивном agy попросить: «создай файл gauntlet/x.txt», затем «выполни `echo x >> GEMINI.md`» → оба отказа
   с `[gauntlet guard] …` или отказ правила разрешений. Файл появился — хуки не работают (строки 4–6 раздела C — «нет»).
5. Попросить главного агента вызвать `hardener` с заданием «создай src/main/java/Tmp.java» и `reviewer` с заданием
   «создай файл build.txt в корне» → оба отказа. Прошло — хуки из frontmatter роли не работают (строка 3 — «нет»).
6. Сделать гейт красным (например, `@Disabled` на тесте в ветке-песочнице) и попросить закончить → агент получает
   строки падения и продолжает; в `.git/gauntlet-hook/` появляются файлы попыток. После 3 попыток — файл
   `agy-last-stop.txt`.
7. `/agents` → роли и карточки в списке; в карточке сабагента модель Carbon и уровень High (наследование).
8. `/context` → `GEMINI.md` загружен целиком, не заменён указателем (бюджет правил — 20 000 токенов [S6: rules]).
9. Одна карточка headless с `--json-schema` и `agy_card_check.py` на простом вопросе → «nothing flagged».
10. В новой рабочей копии, как их создаёт координатор (`git worktree add ../pc-test HEAD`), — `agy -p "/hooks"` → та же
    группа `gauntlet`. Её нет — папка не доверена, хуки рабочей области там не грузятся [S1: 1.1.1], и карточки в таких
    копиях шли бы без guard'а: доверьте родительский каталог рабочих копий или каждую копию.
11. Поведение при сбое хука (документация и трекер расходятся, B.5): в копии репозитория-песочницы замените команду
    PreToolUse на `exit 1` и попросите записать файл. Запись прошла — fail-open (как в документации); отказ — fail-closed,
    и тогда сломанная прослойка (нет `python3`, каталог не в git) остановит любой вызов инструмента. Итог — в план.

### A.7. Решения владельца (ответ «1) да 2) …»)

1. **Человеческие пути Antigravity в наборе.** Добавить `.agents/`, `.gemini/`, `GEMINI.md`, `AGENTS.md` в
   `HUMAN_OWNED` (`gauntlet/hooks/guard.py`) и в `owned=(…)` (`.github/workflows/gauntlet-kit.yml`, строки 56–57) своим
   PR. Рекомендация: да — иначе CI не видит, как агент правит свои правила и хуки, а держат их только хук и deny, оба
   эвристические. — ответьте здесь
2. **Песочница терминала** для сессий задач. Рекомендация: `agentMode: "accept-edits"`, `enableTerminalSandbox: false`,
   agy — в отдельной VM или контейнере. Причина: в песочнице нет сети по умолчанию, а немонтированное невидимо
   [S6: sandbox]; Gradle (Maven Central) и Testcontainers (сокет Docker) там не работают, а как выпустить из неё
   `./gradlew`, «не подтверждено». Имя ключа `enableTerminalSandbox` — по стороннему справочнику, «не подтверждено»:
   берите переключатель из `/config`. Набор на песочницу не опирается. — ответьте здесь
3. **Строка ответа внешнему ревьюеру:** «Ответ Antigravity (<модель>) на комментарий <ревьюер>» вместо «Ответ Claude
   Code …». Рекомендация: да — иначе подпись неправдива. — ответьте здесь
4. **`AGENTS.md`.** Antigravity читает и `AGENTS.md`, и `GEMINI.md` [S6: rules]. Если адаптер другого вендора (Codex)
   положит свой `AGENTS.md`, сессия Gemini получит его инструкции. Рекомендация: в репозитории один вендорский файл
   инструкций, либо `AGENTS.md` только вендорно-нейтральный. — ответьте здесь
5. **Модели.** Координатор и пред-проверка — Gemini 4 Carbon (High); сессии шагов — Carbon (High) для тонкой
   семантики фреймворка, иначе Carbon или Argon (High); никогда Low/Medium и не `Orchestrator`. — ответьте здесь
6. **`/learn` в этом репозитории не использовать:** он дописывает `GEMINI.md`/`AGENTS.md` [S1: 1.5.8]; хук и deny его
   всё равно остановят. — ответьте здесь

---

## B. Промпты

### B.1. `GEMINI.md` — файл инструкций проекта ({{size:GEMINI.md}} байт, предел правила 24 000)

Несёт жёсткие правила набора по ссылке и кратко, правило тщательности и формат отчёта ядра (разделы 4–5),
замены механизмов Claude Code и меры против сбоев Antigravity (разделы 2, 3, 6).

````markdown
{{file:GEMINI.md}}
````

### B.2. Промпт координатора (`gauntlet/adapters/antigravity/coordinator.md`)

Вставляется первым сообщением сессии координатора. Пред-проверка — карточками ядра; приёмка — по разделу 2 ядра.

````markdown
{{file:coordinator-prompt.md}}
````

### B.3. Роли как агенты Antigravity

Формат: Markdown с YAML frontmatter; поля `name`, `description` обязательны; `model` (`inherit` — модель родителя),
`subagent`, `mainAgent`, `tools` (список-разрешение), `commandExecutionPolicy` (`off`, `auto`, `eager`, `sandbox`;
по умолчанию `sandbox`), `hooks` (пути к файлам хуков, относительно файла агента) [S1: 1.1.5, 1.1.6, 1.3.1;
S6: subagents]. Режим Orchestrator ролям не нужен: `model: inherit` даёт роли модель сессии. Для пишущих ролей
`tools` не задан — у них инструменты по умолчанию, область записи держит хук роли. Если ваша версия трактует
пустой `tools` как «ничего» (документация противоречива, [S6: subagents] против [S6: build-plugins]), добавьте
`write_to_file`, `replace_file_content`, `multi_replace_file_content`, `view_file`, `run_command`. `commandExecutionPolicy:
auto` — потому что при `sandbox` команды, по всей видимости, идут в песочнице терминала, где по умолчанию нет сети
[S6: sandbox], и Gradle не скачает зависимости; блог Antigravity о custom agents описывает `auto` как самостоятельный
запуск обычных команд тестов и сборки, а смысл `off` и `eager` — «не подтверждено» [S6: subagents, поиск]. `mainAgent` и
`subagent` по умолчанию `true` [S6: subagents, поиск]: у ролей `mainAgent: false` стоит намеренно — их нельзя выбрать
агентом всей сессии. Поле `inheritCustomizations` (навыки, правила, плагины, сабагенты, MCP; хуки в нём не названы)
есть и у Markdown-агентов CLI, наследование по умолчанию включено [S1: 1.1.14, 1.1.25].

#### specifier — `.agents/agents/specifier/agent.md`

````markdown
{{file:.agents/agents/specifier/agent.md}}
````

`.agents/agents/specifier/hooks.json`:

```json
{{file:.agents/agents/specifier/hooks.json}}
```

#### hardener — `.agents/agents/hardener/agent.md`

````markdown
{{file:.agents/agents/hardener/agent.md}}
````

`.agents/agents/hardener/hooks.json` (область записи и Stop с `mutationGate`, как SubagentStop набора).
`--agent hardener` даёт этому Stop свой счётчик попыток и свою отметку последней остановки в `stop_gate.py`:
Stop-хуки срабатывают и для беседы сабагента (#1527), так что Stop рабочей области может сработать в той же
беседе, и без своего ключа зелёный `gauntletFast` давал `mutationGate` пропуститься (проверено локально, раздел
«Проверка»):

```json
{{file:.agents/agents/hardener/hooks.json}}
```

#### reviewer — `.agents/agents/reviewer/agent.md`

````markdown
{{file:.agents/agents/reviewer/agent.md}}
````

`.agents/agents/reviewer/hooks.json` (его же используют карточки пред-проверки):

```json
{{file:.agents/agents/reviewer/hooks.json}}
```

### B.4. Карточки пред-проверки как агенты

Карточки 4.1–4.4 и 4.6 ядра; 4.5 — роль reviewer. `mainAgent: true` нужен, чтобы координатор запускал карточку
headless-прогоном `agy -p … --agent <имя>`; `subagent: true` — чтобы её можно было вызвать и через `invoke_subagent`.
Только-чтение держат `tools` без инструментов записи и хук роли reviewer (`hooks: ../reviewer/hooks.json`).

#### 4.1 — `.agents/agents/precheck-mapper/agent.md`

````markdown
{{file:.agents/agents/precheck-mapper/agent.md}}
````

#### 4.2 — `.agents/agents/precheck-framework/agent.md`

````markdown
{{file:.agents/agents/precheck-framework/agent.md}}
````

#### 4.3 — `.agents/agents/precheck-critic/agent.md`

````markdown
{{file:.agents/agents/precheck-critic/agent.md}}
````

#### 4.4 — `.agents/agents/precheck-refuter/agent.md`

````markdown
{{file:.agents/agents/precheck-refuter/agent.md}}
````

#### 4.6 — `.agents/agents/review-repro/agent.md`

````markdown
{{file:.agents/agents/review-repro/agent.md}}
````

### B.5. Хуки рабочей области — `.agents/hooks.json`

Формат по документации: верхний ключ — имя группы; у PreToolUse и PostToolUse — `matcher` (регулярное выражение
по имени инструмента) и список `hooks`; у SessionStart, PreInvocation, PostInvocation и Stop — сразу список
обработчиков; обработчик — `type: "command"`, `command`, `timeout` в секундах (по умолчанию 30) [S6: hooks]. Команда
сначала переходит в корень репозитория: в каком каталоге agy запускает хуки, документация (в доступной мне части) не
говорит; сторонний разбор контракта agy 1.2.16 называет каталог, где лежит `hooks.json` [S28] — `git rev-parse` оттуда
тоже находит корень. Форма `sh -c '…'` — для Linux и macOS.

```json
{{file:.agents/hooks.json}}
```

Контракт, который переводит `agy_hooks.py` (полный текст — приложение 1):

| | Antigravity (вход и ответ хука) | Набор (что читают и отвечают его скрипты) |
|---|---|---|
| вход | JSON в stdin: `hookEventName`, `conversationId`, `cwd`, `workspacePaths`, `toolCall {name, args, id}`; у Stop — `continuation_active` [S1: 1.5.4, 1.5.6; S6: hooks]; ещё `transcriptPath`, `artifactDirectoryPath`, `modelName` [S7, S28]; имена `executionNum`, `terminationReason` — только по поисковой выдаче, «не подтверждено» | `hook_event_name`, `session_id`, `cwd`, `tool_name`, `tool_input`, `agent_type`, `stop_hook_active` |
| shell | `run_command`, аргументы `CommandLine` [S25], `Cwd` [S21] | `Bash`, `tool_input.command` |
| запись файла | `write_to_file`, `replace_file_content`, `multi_replace_file_content`, аргумент `TargetFile` [S6: hooks; S21; S25]; путь может прийти как URI `file:///…` — так пути идут по проводу Antigravity, и SDK вендора переводит их в обычные перед своими хуками [S25]; прослойка делает то же, иначе guard принял бы URI за относительный путь вне набора и пропустил | `Write`, `tool_input.file_path` |
| запрет | `{"decision":"deny","reason":…}`; `allow` передаёт вызов дальше обычной политике, ничего не одобряя [S6: hooks] | `hookSpecificOutput.permissionDecision: "deny"` |
| «не останавливайся» | `{"decision":"continue","reason":…}`, причина приходит агенту; `{}` отпускает [S6: hooks] | код выхода 2 и текст в stderr |
| сбой хука | по документации плагинов: ненулевой код, таймаут, неверный JSON — записывается в журнал и пропускается (fail-open) [S6: hooks, build-plugins]; но в трекере вендора (#1183, 07.10.2026) записано, что ненулевой код или пустое решение PreToolUse отклоняют вызов, и сторонний отчёт видел отказ «Tool call denied by pre-tool hook» при пропавшей команде хука [S26, S27] — противоречие, проверка A.6, п. 11 | guard тоже открыт при неверном входе |
| роль | во входе нет — запрос `isSubagent` открыт (#922), хуки сабагентов идут от процесса родителя (#1527) [S7, S8] | `agent_type` |

Отсюда два режима guard'а. Хук рабочей области (`--role shared`) роль не знает и может срабатывать и у сабагентов
(SessionStart, PreInvocation и Stop у них срабатывают — #1527; для PreToolUse «не подтверждено», хотя #922 перечисляет
PreToolUse среди событий, где сабагента не отличить от главного агента): он закрывает набор, `~/.gemini`, `~/.agents`,
запрещённые формы git и замороженную спецификацию для всех, а до заморозки не мешает писать фичи — иначе specifier не
смог бы работать. Ограничение области каждой роли — в её собственном хуке (`--role specifier|hardener|reviewer`).
Запреты складываются: `deny` любого хука побеждает.

### B.6. Разрешения, схема отчёта, проверка прогона карточки

`gauntlet/adapters/antigravity/settings.permissions.json` — влить в `~/.gemini/antigravity-cli/settings.json`
(или задать в `/permissions`, область Project); `<HOME>` заменить на домашний каталог. Список повторяет
`permissions` набора для Claude Code и его человеческие пути, включая сокращённые формы опций git (`git commit --am`,
`git push --m`, `git branch --forc` и др.: git принимает однозначный префикс длинной опции); правила команд —
префиксные, обёртка (`env git push --force`) их обходит, её ловит guard.

```json
{{file:gauntlet/adapters/antigravity/settings.permissions.json}}
```

`gauntlet/adapters/antigravity/report.schema.json` — форма отчёта ядра (раздел 3) для `--json-schema`: CLI требует от
модели структурированный ответ по схеме; корень схемы обязан быть `"type": "object"` [S1: 1.1.8, 1.2.14]. Требует
напоминаниями модели, до предела на сообщение [S1: 1.5.8]: ответ без структуры возможен, и `agy_card_check.py` его
отмечает («no structured report»). Схема
держит форму, не содержание: содержание проверяет приёмка. Поля — те же разделы ядра: `summary` — «Итог»,
`coverage` и `checked` — «Проверено (покрытие: N из M)», `not_checked` — «Не проверено», `questions` — «Вопросы и
риски»; в план и в промпт сессии координатор переносит их в Markdown-формате ядра. Сабагенты, вызванные через
`invoke_subagent`, отвечают сразу в Markdown-формате (`GEMINI.md`, раздел 5).

```json
{{file:gauntlet/adapters/antigravity/report.schema.json}}
```

`gauntlet/adapters/antigravity/agy_card_check.py` (приложение 2) — механическая часть приёмки (ядро, 2.1–2.2):
статус прогона, `finished_reason`, `denied_actions`, разделы формата, «N из M» и непустое «Не проверено» при N < M,
команда каждого доказательства среди вызовов инструментов этого прогона (`tool_info` в `stream-json` [S1: 1.1.8]; ищется
в имени и параметрах вызова, а не в его выводе: команда, процитированная в прочитанном файле, не запуск),
цитата каждого `файл:строка` рядом с указанной строкой. Выборочную и adversarial-перепроверку он не заменяет.

---

## C. Сопоставление

Статус: «полностью» — механизм среды делает то же; «частично» — делает, но слабее или не проверен вживую; «нет» —
механизма нет, работает запасной путь.

| # | Механизм gauntlet | Механизм Antigravity | Статус | Запасной путь |
|---|---|---|---|---|
| 1 | `CLAUDE.md` с импортом `@gauntlet/CLAUDE.md` | `GEMINI.md` (всегда в контексте, ≤ 24 000 байт) + обязательное чтение `gauntlet/CLAUDE.md` целиком | частично: чтение — инструкция | доказательство чтения (`wc -l`, заголовки) в первом сообщении; перечитать после сжатия |
| 2 | Роли `.claude/agents/*.md` | агенты `.agents/agents/<роль>/agent.md`, вызов `invoke_subagent` с `TypeName` | полностью (раскладку файлов проверяет A.6, п. 7) | раскладка `.agents/agents/<роль>.md` (D.3, п. 4) |
| 3 | Область роли по `agent_type` в guard | хук в frontmatter роли (`hooks:`) + `tools` без записи | частично, вживую не проверено | `tools`, текст роли, diff PR, CI |
| 4 | PreToolUse `guard.py`: набор, `~/.claude`, запрещённые формы git, `gh pr merge` | PreToolUse в `.agents/hooks.json` → `agy_hooks.py` → `guard.py` (+ пути Antigravity) | частично: при сбое — fail-open по документации, отказ по трекеру (B.5); вживую не проверено | deny в разрешениях + CI `gauntlet kit unchanged` + diff |
| 5 | `permissions.deny` Claude Code | `permissions.deny` agy: `write_file(…)`, `command(…)`; действует во всех режимах | частично: только файловые инструменты и префиксы команд; смысл относительного пути «не подтверждён» | запись через shell ловит guard (п. 4); A.6, пп. 3–4 |
| 6 | Заморозка спецификации | guard через прослойку: после коммита `spec:` фичи закрыты для всех | частично: до заморозки главный агент технически может писать фичи | человек утверждает фичи в чате; diff PR |
| 7 | Stop: нельзя закончить с красным `gauntletFast` | Stop-хук `{"decision":"continue"}` → `stop_gate.py` | частично: при сбое — fail-open по документации; предел таймаута хука и число допустимых продолжений подряд (настраиваемое, имя ключа «не подтверждено») | `GEMINI.md`, раздел 3: агент сам гоняет `gauntletFast` и прикладывает строки `> Task`; CI |
| 8 | SubagentStop hardener: `mutationGate` | Stop в `hooks.json` роли; прослойка (`--agent hardener`) судит его как SubagentStop набора, со своим счётчиком | «не подтверждено», что срабатывает при конце сабагента | hardener сам гоняет `mutationGate` и прикладывает строки; главный агент сверяет; CI `gauntlet` |
| 9 | SessionStart: базовая ветка, снимок дерева, Docker, строка статуса в контекст | SessionStart → `session_start.sh` | частично: попадает ли вывод в контекст, «не подтверждено» | статус — в `.git/gauntlet-hook/agy-session-status.txt`, агент читает сам |
| 10 | Stop-хук облачной платформы Claude (коммит и push) | — | нет и не нужен | на остановке для утверждения ничего не коммитить |
| 11 | Админ-окружение `GAUNTLET_GUARD=off` | та же переменная окружения процесса agy | полностью (как в наборе — растяжка, не сейф) | — |
| 12 | CI `gauntlet`, `gauntlet kit unchanged` | без изменений | полностью для путей набора | `.agents/`, `GEMINI.md` — после решения A.7, п. 1 |
| 13 | Координатор создаёт сессию задачи | — | нет | владелец открывает agy в новой рабочей копии с промптом координатора |
| 14 | Решения владельца в идущую сессию | вставка владельцем (терминал, Remote Control); `agy -p … --conversation <id>` | частично: рядом с открытой сессией «не подтверждено» | владелец вставляет сам |
| 15 | Подписка на события PR | — | нет | `gh pr checks`, `gh pr view --comments` по сообщениям владельца |
| 16 | Многоагентная пред-проверка | headless `agy -p --agent <карточка>` параллельно; или `invoke_subagent` | полностью (headless) — запуск; охрана карточки — строка 3, и только в доверенной папке (A.6, п. 10); рабочие копии `branch`/`share` у сабагентов есть [S1: 1.3.3, 1.5.5], имя параметра `Workspace` — «не подтверждено» | прогоны с Gradle — в отдельных рабочих копиях |
| 17 | Формат отчёта сабагента | `--json-schema report.schema.json` | частично: форму CLI требует напоминаниями до предела [S1: 1.5.8], ответ без структуры возможен | нет структуры — `agy_card_check.py` отмечает, отчёт возвращается; содержание — приёмка |
| 18 | Приёмка по доказательствам (ядро, 2) | промпт координатора + `agy_card_check.py` (вызовы из `stream-json`, цитаты) | частично: схема событий `stream-json` не подтверждена, поиск структурный | выборочная перепроверка координатором, опровергатель |
| 19 | Модель и уровень (п. 17) | `--model`, `--effort`; у сабагентов `model: inherit` | частично: уровень сабагента при вызове не задаётся (#1237), Orchestrator подменяет модель проверяющих (D.2) | `/agents` показывает модель и уровень; Orchestrator не использовать |
| 20 | Пауза по лимиту (п. 14) | `/usage`, `/quota` | частично: процент лимита как у Claude «не подтверждён» | сообщение владельца «пауза по лимиту» |
| 21 | Сжатие контекста | автосжатие, `/compact`, `AGY_CLI_AUTO_COMPACT_OVERRIDE` | полностью как механизм | перечитать `gauntlet/CLAUDE.md`; решения — в файлах и описании PR |
| 22 | Неинтерактивный запуск | `agy -p`, `--output-format json/stream-json`, коды 0/1/2/3, `denied_actions`, `finished_reason`, `--print-timeout` | полностью | код 0 при мягком отказе — смотреть `denied_actions` |
| 23 | Внешний ревьюер (п. 19) | тот же процесс через `gh` | полностью | подпись ответа — A.7, п. 3 |
| 24 | — (набору не нужно) | MCP (`mcp_config.json`, правила `mcp(server/tool)`), фоновые задачи и таймеры, удалённые агенты `--remote-agent`, Remote Control [S1: 1.5.8, 1.5.14, 1.5.16] | — | удалённые агенты для сессий задач не используются: хуки там «не подтверждены» |
| 25 | — (метод: утверждение спецификации в чате) | режим плана (`/plan`, `agentMode: "plan"`), цель `/goal` (работа идёт, пока цель не выполнена или не отменена; кто решает, что выполнена, — «не подтверждено») [S1: 1.0.14, 1.1.0] | не используются в сессии задачи | готовность решают гейт, CI и человек |

---

## D. Пределы и источники

### D.1. Что не переносится

- **Роль во входе хука.** У Claude Code guard знает `agent_type`; у agy во входе хука роли нет (#922 открыт, #1527
  закрыт как его дубль) [S7, S8]. Поэтому одно правило набора не держится механизмом: «до заморозки фичи пишет только
  specifier» — главный агент технически может написать их сам. Держат его инструкция, утверждение фич человеком и
  diff PR.
- **Хуки открыты при сбое — по документации.** Хук, который упал, превысил таймаут или вернул неверный JSON, agy
  пропускает [S6: hooks]; трекер вендора и сторонний отчёт видели обратное у PreToolUse — отказ вызова [S26, S27]
  (B.5, A.6, п. 11). Набор не опирается ни на то, ни на другое: прослойка всегда выходит с 0 и печатает JSON.
  В истории agy были случаи, когда хуки молча не применялись: команды хуков с кавычками в Windows (исправлено в
  1.5.8), `hooks.json` с BOM (1.5.8), `hooks.json` при усечении бюджета настроек (1.2.4), Stop-хуки, недостижимые за
  встроенными проверками (1.1.10) [S1]. Отсюда A.6 после каждого обновления и раздел 3 `GEMINI.md` всегда.
- **Таймаут Stop-хука.** Набор даёт `gauntletFast` до 1 800 с и `mutationGate` до 7 200 с; верхний предел `timeout`
  у agy «не подтверждён». Если agy оборвёт хук раньше, он пропустится — и агент остановится без гейта.
- **Только-чтение reviewer'а и карточек — эвристика.** `run_command` остаётся (Gradle, `git diff`), его запись guard
  разбирает эвристически, как и в наборе.
- **Обходные пути исполнения.** Сценарий `run_workflow` (Python внутри CLI) и сабагенты, созданные `define_subagent`
  на ходу: видит ли их файловые операции PreToolUse, «не подтверждено»; в сессиях задач они запрещены инструкцией.
- **Облачные сессии с охраняемым окружением, создание сессии координатором, отправка сообщения в сессию, подписка на
  PR** — эквивалентов нет (строки 13–15 раздела C).
- **CI не видит файлы Antigravity** (`.agents/`, `GEMINI.md`) до решения A.7, п. 1; README набора (раздел 9) это и
  говорит о целях ссылок и `AGENTS.md`. Как и `CLAUDE.md` модуля в наборе, вложенные `GEMINI.md`/`AGENTS.md` (сторонние
  разборы пишут, что Antigravity читает их и в подпапках) ни guard, ни CI не охраняют — только diff PR.

### D.2. Известные сбои Antigravity и Gemini 4, относящиеся к жалобе владельца

Все — сообщения пользователей, не признанные Google причины; меры адаптера от причин не зависят: отчёт без
доказательств не принимается.

| Сбой | Источник | Что делает адаптер |
|---|---|---|
| Агент пишет «назначено», «отправлено», «модель закреплена» без вызова инструмента, в том числе после отказа от своих слов; Orchestrator (Carbon), приложение 2.32.1 | antigravity-cli #1613, 17.11.2026 [S12] | `GEMINI.md` 4.9; `agy_card_check.py` ищет команду среди вызовов прогона |
| «Готово» с выдуманными процентами, заглушки как реализация, ноль тестов при 80 тестовых файлах в источнике | antigravity-cli #1193, 10.10.2026 [S13] | раздел 3 `GEMINI.md`, правило 4.1, гейты и CI |
| Агент «прогнал и прошёл» 20+ тестов, не запустив их; после «Accept all» — «проверено» без записанных файлов | форум [S14, S15] | правила 4.1, 4.8, 4.9; приёмка по выводу команд |
| Carbon Medium в сабагентах: 0 токенов рассуждений в ходах с вызовами инструментов («tool-aware minimal thinking») | форум, ~15.11.2026 [S16] | High для сессий и сабагентов; судим по доказательствам, а не по объёму |
| С вечера 18.11.2026 Gemini 4 думают в 3–4 раза меньше: 1,9–16 тыс. токенов вместо 27–100 тыс., 1–8 минут вместо 25–80; XHigh отвергался; к 19–22.11 нормализовалось | форум [S17] | то же; провал по доказательствам виден независимо от причины |
| Orchestrator (Carbon/Neon): проверяющие сабагенты (reviewer, critic, auditor) через `invoke_subagent` уходят на Hydrogen; ранее `pro` превращался во flash | форум, agy 1.5.13 [S18, S19] | Orchestrator не используется; `model: inherit`; `/agents` показывает модель |
| Orchestrator не отдаёт работу сабагентам, делает всё сам | форум [S20] | пред-проверка — отдельными headless-прогонами, а не по воле модели |
| Headless-ход заканчивается (SUCCESS), пока запущенная команда ещё идёт | antigravity-cli #1044 [S22] | гейты только на переднем плане; приёмка требует строк `> Task` и `BUILD …` |
| Раннее сжатие контекста (~250 тыс. при окне 1 млн) теряет точные символы | antigravity-cli #1245 [S22] | перечитать `gauntlet/CLAUDE.md`; решения в файлах |
| Агенты сами запускали `/swarm` (расход квоты) | исправлено в agy 1.5.13 [S1] | `/swarm` в сессиях задач запрещён |
| Подтверждение, которое headless-прогон получить не может, отклоняется, а код выхода 0 | документация headless [S6], agy 1.1.27 [S1] | `agy_card_check.py` смотрит `denied_actions`; отказ — в «Не проверено» |

Для сравнения: у Gemini CLI сабагент по умолчанию ограничен 30 ходами и 10 минутами (`max_turns`, `timeout_mins`,
`@google/gemini-cli-core@0.71.1`, `dist/docs/core/subagents.md`, строки 371–372) [S4]. Для agy такие пределы
сабагентов «не подтверждены».

### D.3. Не подтверждено

1. Поведение всего, что в разделе C помечено «частично», в живом agy — до проверки A.6.
2. Каталог, в котором agy запускает команды хуков (сторонний разбор agy 1.2.16 [S28]: каталог `hooks.json`); запуск
   через shell (поэтому команды обёрнуты в `sh -c` и `cd` в корень).
3. Срабатывают ли хуки из frontmatter агента для его вызовов инструментов и Stop при конце сабагента; наследуют ли
   сабагенты хуки рабочей области (`inheritCustomizations` Markdown-агентов CLI покрывает навыки, правила, плагины,
   сабагентов и MCP, хуки в нём не названы [S1: 1.1.14, 1.1.25]); выполняет ли agy хуки одного события
   параллельно — тогда Stop рабочей области и Stop hardener'а гоняли бы Gradle в одном каталоге одновременно.
4. Умолчание поля `tools` у агента: пустой список или все инструменты — документация противоречит сама себе.
   Раскладка агентов рабочей области: `.agents/agents/<имя>/agent.md` (описание CLI) или `.agents/agents/<имя>.md`
   (пример `code-auditor.md`) — в документации встречаются обе.
5. Верхний предел `timeout` хука; имя настройки числа продолжений подряд для Stop.
6. Попадает ли вывод SessionStart в контекст агента; есть ли у Stop поле сообщения при остановке.
7. Имя параметра `Workspace` у `invoke_subagent` и значение `inherit`; рабочие копии `branch` и `share` у сабагентов в
   CLI есть (копия включает незакоммиченные правки) [S1: 1.3.3, 1.5.5].
8. Семантика относительных путей в `write_file(…)` (от корня рабочей области — по примеру `write_file(.git/)`).
9. Как выпустить `./gradlew` из песочницы терминала правилом разрешений.
10. Точная схема событий `stream-json` (кроме имён `init`, `step_update`, `result`, `tool_info`, `status`,
    `finished_reason`, `denied_actions`); поле с id беседы в выводе.
11. Слаг модели `gemini-4-carbon-high` (форум); доступ к Carbon на тарифе Pro (сторонний отчёт).
12. Читает ли CLI разрешения из `<проект>/.gemini/config.json`; сливает ли `--settings <файл>` свои `permissions` с
    пользовательскими.
13. Хуки рабочей области в удалённых агентах (`--remote-agent`); Gemini 4 Carbon в Jules.
14. Грузятся ли хуки и агенты рабочей области в headless-прогоне в новой, ещё не доверенной рабочей копии (A.6, п. 10).
15. Приходят ли пути во входе хуков CLI как URI `file:///…` (в SDK вендора — да [S25]); прослойка переводит оба вида.
16. Формат значения `--print-timeout` (`60m` в B.2 — по аналогии); имена ключей `toolPermission` и
    `enableTerminalSandbox` (сторонние справочники; `agentMode` и `trustedWorkspaces` подтверждены [S1: 1.5.7; S6:
    settings]).

### D.4. Источники (прочитаны 2026-11-24)

Способ чтения: «прямо» — файл прочитан целиком в этой сессии; «поиск» — страница официального сайта прочитана через
поисковый движок, потому что antigravity.google, blog.google, deepmind.google, developers.googleblog.com и
discuss.ai.google.dev из этой сессии не открываются (для прямого чтения их нужно разрешить в сетевых настройках
окружения); такие утверждения перепроверены по журналу изменений agy или по независимому коду, где это было возможно.

| # | Источник | Что взято | Способ |
|---|---|---|---|
| S1 | github.com/google-antigravity/antigravity-cli, `CHANGELOG.md`, коммит `bb5c8da` (1.5.16, 24.11.2026) | события и вход хуков, Stop `continuation_active`, агенты Markdown и их поля, `hooks:` во frontmatter, `--json-schema`, `stream-json`/`tool_info`, `denied_actions`, `finished_reason`, коды выхода, Carbon Low/Medium/High, `--effort`, Orchestrator, `/swarm`, `run_workflow`, бюджет правил 20 000 токенов, лимит 24 KB, `/learn`, сбои хуков; версии указаны у ссылок | прямо |
| S2 | там же, `README.md` | общий движок и настройки CLI и приложения, установка, вход | прямо |
| S3 | github.com/google-gemini/gemini-cli, `README.md` ветки main | Gemini CLI только для Code Assist; переход на Antigravity CLI 18.06.2026; «not tuned for the Gemini 4 series» | прямо |
| S4 | npm `@google/gemini-cli-core@0.71.1`: `dist/src/config/models.js`, `dist/src/hooks/types.js`, `dist/docs/core/subagents.md` | нет Gemini 4 в списке моделей; события хуков Gemini CLI; `max_turns` 30, `timeout_mins` 10 | прямо |
| S5 | github.com/google-gemini/gemini-api-cli, коммит `52636d1`, `internal/cli/catalog.go` | id `gemini-4-carbon`, описание модели | прямо |
| S6 | antigravity.google/docs/: `hooks`, `rules`, `subagents`, `build-plugins`, `settings`, `permissions`, `sandbox`, `cli/headless`, `cli/reference`, `changelog` | формат и контракт хуков, fail-open; правила, 24 000 байт, бюджет, `@[метка](путь)` и `@путь`; поля агентов; ключи настроек, правила разрешений и их порядок; песочница; headless и мягкий отказ | поиск |
| S7 | github.com/google-antigravity/antigravity-cli/issues/1527 | хуки сабагентов от процесса родителя, поля происхождения вычищаются; дубль #922 | прямо (страница GitHub) |
| S8 | там же, issue #922 «Add isSubagent boolean field to lifecycle hook payloads» | роли во входе хука нет | по ссылке из #1527 |
| S9 | deepmind.google/models/model-cards/gemini-4-carbon/ | описание модели, уровни рассуждений | поиск |
| S10 | blog.google/…/gemini-4-carbon-now-available/ | развёртывание для Ultra, API | поиск |
| S11 | antigravity.google/blog/gemini-4-carbon-in-google-antigravity/ (10.11.2026); x.com/antigravity/status/2120188336056733746 | Carbon в приложении, CLI и расширениях для Ultra; `/swarm` | поиск |
| S12 | github.com/google-antigravity/antigravity-cli/issues/1613 | действия без вызова инструмента, Orchestrator (Carbon) | прямо (страница GitHub) |
| S13 | github.com/google-antigravity/antigravity-cli/issues/1193 | выдуманные метрики, заглушки, ноль тестов | прямо (страница GitHub) |
| S14 | discuss.ai.google.dev/t/…/198391 «Antigravity AI Agent fabricated test results and wasted 566M tokens» | заявленные, но не запущенные тесты | поиск |
| S15 | discuss.ai.google.dev/t/…/145034 «"Accept all" reports success without filesystem writes or real test execution» | «проверено» без записи файлов | поиск |
| S16 | discuss.ai.google.dev/t/…/200671 «Counter-data: "tool-aware minimal thinking"…» | 0 токенов рассуждений у сабагентов Carbon Medium | поиск |
| S17 | discuss.ai.google.dev/t/…/202317 «Gemini 4 … think 3-4x less since Nov 18…» | падение глубины рассуждений, XHigh | поиск |
| S18 | discuss.ai.google.dev/t/…/203336 «Orchestrator modes downgrade verification subagents to Hydrogen…» | подмена модели проверяющих сабагентов | поиск |
| S19 | discuss.ai.google.dev/t/…/200144 «Agy CLI subagents are completely useless — pro tier still maps to gemini-3.8-flash-tiered…» | подмена `pro` во flash | поиск |
| S20 | discuss.ai.google.dev/t/…/203532 «Orchestrator not eager to dispatch work to subagents» | оркестратор не делегирует работу сабагентам | поиск |
| S21 | сторонний код с контрактом хуков agy: gridctl/gridctl `docs/hooks.md`, AsiaOstrich/universal-dev-standards `core/mock-boundary.md`, onkarbadve/agy-auto `HARNESS-BEHAVIORS.md`, roundpilot/superpowers-antigravity (вызов `invoke_subagent TypeName`) | аргументы `CommandLine`, `Cwd`, `TargetFile`; перечень решений PreToolUse из бинарника; форма вызова роли | поиск кода GitHub (вторичный) |
| S22 | github.com/google-antigravity/antigravity-cli/issues?q=is:issue+subagent+early; там же #1044, #1245, #1237 | headless SUCCESS при идущей команде; раннее сжатие; нет выбора уровня сабагента | список задач трекера (прямо) |
| S23 | cloud.google.com/blog/topics/developers-practitioners/choosing-antigravity-or-gemini-cli (04.02.2026) | ранняя граница Antigravity и Gemini CLI | прямо |
| S24 | testingcatalog.com «Google adds task checklists to Antigravity and Carbon for Pro» | Carbon на тарифе Pro | поиск (сторонний) |
| S25 | github.com/google-antigravity/antigravity-sdk-python, коммит `97c5c53` (18.11.2026): `google/antigravity/connections/connection.py` (`normalize_wire_path`), `connections/local/local_connection_config.py` (`WIRE_PATH_ARGUMENT_KEYS`), `hooks/policy_test.py`, `proto/agent_tools.proto` | пути по проводу — URI `file:///…`, перед хуками SDK их нормализует; аргументы `CommandLine`, `TargetFile`; у `invoke_subagent` поле `type_name`; встроенные инструменты SDK `create_file`, `edit_file` | прямо (добавлено проверкой) |
| S26 | github.com/google-antigravity/antigravity-cli/issues/1183 (открыт 07.10.2026) | «a non-zero exit or an empty/invalid decision on PreToolUse denies the tool call» — со слов автора запроса | прямо (страница GitHub; добавлено проверкой) |
| S27 | github.com/Louis-CFM/coucou/issues/430 | «Tool call denied by pre-tool hook» при удалённой команде хука (сторонний) | поиск (добавлено проверкой) |
| S28 | github.com/RikaiDev/innen/issues/5 (agy 1.2.16) | вход хука: `conversationId`, `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, `modelName`; каталог запуска хука — каталог `hooks.json` (сторонний) | прямо (страница GitHub; добавлено проверкой) |

### D.5. Что проверено в этой работе

На синтетическом репозитории с копией набора (`gauntlet/` этой ревизии), базой `origin/main` и `GAUNTLET_GUARD`
не заданным:
- `agy_hooks.py selftest` — 20 случаев до заморозки и после коммита `spec:` (и отдельная проверка роли reviewer): запись в `gauntlet/`, `GEMINI.md`,
  `.agents/hooks.json`, `~/.gemini/…` — отказ; `sed -i` по `gauntlet.properties`, `echo > .agents/hooks.json`,
  `git push --force`, `gh pr merge` — отказ; `./gradlew gauntletFast` и запись в `src/main` главным агентом —
  разрешены; hardener — `src/main` отказ, `src/test` разрешено; reviewer — любая запись и `git commit`, `git worktree
  add`, `git checkout` — отказ, `git diff`, `rg`, `javap`, `./gradlew …` — разрешены; specifier — фичи до заморозки
  разрешены, после — отказ, как и для всех. `GAUNTLET_GUARD=off` — разрешено (админ-окружение); мусор на входе —
  `allow` с кодом 0.
- Команды хуков из `hooks.json` через `sh -c` из подкаталога — работают.
- Stop с поддельным красным `gradlew`: попытки 1–3 → `{"decision":"continue","reason":"[gauntlet] ./gradlew
  gauntletFast is RED (attempt N/3)…"}`, четвёртая → `{}` и `agy-last-stop.txt`; зелёный прогон со строками
  `> Task` всех задач гейта → `{}`; беседа без изменений → `{}`.
- SessionStart → `{}`, снимок дерева и `agy-session-status.txt` со строкой статуса набора.
- `agy_card_check.py` на синтетических выводах: хороший отчёт — без отметок; плохой — 4 отметки (`denied_actions`,
  пустое «Не проверено» при 2 из 3, команда не среди вызовов, цитата не у строки).
- JSON всех `hooks.json`, настроек и схемы разбирается; frontmatter агентов читается.

Ничего из этого не запускалось в живом agy.

---

## Приложение 1. `gauntlet/adapters/antigravity/agy_hooks.py`

```python
{{file:gauntlet/adapters/antigravity/agy_hooks.py}}
```

## Приложение 2. `gauntlet/adapters/antigravity/agy_card_check.py`

```python
{{file:gauntlet/adapters/antigravity/agy_card_check.py}}
```

---

## Проверка

Независимая состязательная проверка адаптера, 24.11.2026. Каждое утверждение о среде перепроверено свежим источником
и другой дорогой, чем у автора: свежий клон `google-antigravity/antigravity-cli` (`CHANGELOG.md`, коммит `bb5c8da`,
100 версий, поиск своими запросами по тексту), исходники SDK вендора `google-antigravity/antigravity-sdk-python@97c5c53`
[S25] (автор на них не ссылался), свежий клон `google-gemini/gemini-api-cli@52636d1`, `npm pack
@google/gemini-cli-core@0.71.1`, `README.md` Gemini CLI с `raw.githubusercontent.com` (ветка main), страницы задач
GitHub (#922, #1527, #1613, #1193, #1237, #1044, #1245, #1183, #770) через чтение страницы, документация
antigravity.google — только через поисковую выдачу: antigravity.google, gweb-jetski.appspot.com и
discuss.ai.google.dev из этой сессии не открываются (ENOTFOUND). Живого agy не было; хуки и проверка карточек
проверены локально на синтетическом репозитории с настоящими `guard.py`, `stop_gate.py`, `session_start.sh` набора и
поддельным `gradlew`.

### Что проверено (99 утверждений)

| Группа | Утв. | Подтверждено (источник) | Исправлено или «не подтверждено» |
|---|---|---|---|
| Хуки | 18 | `.agents/hooks.json` грузится после доверия папке [S1: 1.1.1]; глобальные — `~/.gemini/config/hooks.json` [S1: 1.0.8]; события PreToolUse, PostToolUse, Stop, SessionStart, PreInvocation, PostInvocation [S1: 1.5.5, 1.5.8, 1.4.11, 1.1.10]; `hookEventName`, `cwd`, `toolCall.id` [S1: 1.5.4]; `continuation_active` [S1: 1.5.6]; верхний ключ — имя хука [S1: 1.4.3; пример в #770]; `matcher` — регулярное выражение [S1: 1.4.3]; предел продолжений Stop [S1: 1.1.9]; `conversationId` сабагента и вычищенные поля происхождения [S7]; роли во входе нет, #922 открыт [S8]; `allow` передаёт дальше, `continue`/`{}` у Stop [S6, поиск; SDK: `StopDecision.CONTINUE`/`ALLOW_STOP`] | fail-open — противоречие с #1183 и coucou #430 (исправлено в B.5, C, D.1, A.6 п. 11); `executionNum`, `terminationReason` — «не подтверждено»; пути — возможно URI (исправлена прослойка); каталог запуска хука — по стороннему [S28] |
| Агенты | 14 | `agent.md` с frontmatter и полями `mainAgent`, `subagent`, `hidden`, `inheritMcp`, `commandExecutionPolicy` [S1: 1.1.6]; `model` с умолчанием `inherit` [S1: 1.1.5]; `hooks:` относительно файла агента [S1: 1.3.1]; `find_by_name`, `grep_search`, `list_dir` — только явным списком `tools` [S1: 1.2.7]; `.agents/agents/` в headless и с `--agent` [S1: 1.2.11]; `name` и `description` обязательны [S1: 1.4.1]; значения и умолчание `commandExecutionPolicy`, умолчания `mainAgent`/`subagent` [S6, поиск]; поле `type_name` у `invoke_subagent` [S25]; нет `Effort` у `invoke_subagent` (#1237); модель и уровень сабагента в `/agents` [S1: 1.5.3] | `inheritCustomizations` есть у агентов CLI [S1: 1.1.14] (исправлено D.3, п. 3); рабочие копии `branch`/`share` есть в CLI [S1: 1.3.3, 1.5.5] (исправлено D.3, п. 7, C, строка 16); раскладка `<имя>/agent.md` или `<имя>.md` — «не подтверждено» |
| Правила | 5 | бюджет правил 20 000 токенов [S1: 1.2.7]; предел размера правила документирован [S1: 1.5.8], 24 000 байт после раскрытия `@[метка](путь)` — по выдержкам из встроенной документации CLI в сторонних задачах (поиск); `@путь` не встраивается — сторонний отчёт; `GEMINI.md` и `AGENTS.md` читаются оба [S1: 1.4.4]; `/learn` дописывает их [S1: 1.5.8] | — |
| Разрешения и настройки | 16 | путь настроек и приоритет области Project в `~/.gemini/config/projects/` [S1: 1.0.12]; `/permissions` [S1: 1.0.5]; `command(…)` [S1: 1.1.11], `mcp(server/tool)` [S1: 1.5.8]; действия `read_file`, `write_file`, `read_url`, `execute_url`, `command`, `mcp` и порядок Deny > Ask > Allow [S6, поиск]; `agentMode`, значение `""` [S1: 1.5.7]; `--mode accept-edits`/`plan` в headless [S1: 1.1.12], `auto` [S1: 1.3.5]; `trustedWorkspaces` [S6, поиск]; `--settings` [S1: 1.5.8]; разрешения не коммитятся в репозиторий (поиск: документация и сторонняя вики) | режим по умолчанию — Auto и для `-p` [S1: 1.5.7] (добавлено в A.3 и в команду координатора); имена `toolPermission`, `enableTerminalSandbox` — «не подтверждено» (значения `request-review`, `strict` — [S1: 1.1.11, 1.5.7]); «`.agents/settings.json` больше не читается» — не перепроверено |
| Headless | 17 | `-p`, `--output-format json/stream-json`, события `init`, `step_update`, `result`, `tool_info`, `subagent_info` [S1: 1.1.8]; `--json-schema`, корень `object`, код 1 [S1: 1.1.8, 1.2.14]; `finished_reason` [S1: 1.4.11]; `denied_actions` и код 0 при отказах [S1: 1.1.20, 1.1.27]; `status` ERROR/SUCCESS [S1: 1.5.13]; коды 1/2/3 [S1: 1.2.6, 1.2.10, 1.3.4, 1.5.0, 1.5.11, 1.5.12]; `--print-timeout` [S1: 1.2.6, 1.5.0]; `--conversation` [S1: 1.0.9, 1.5.16]; неизвестный `--agent` → код 1 [S1: 1.3.4]; `--model`, `--effort` [S1: 1.1.5, 1.3.4]; `--dangerously-skip-permissions` [S1: 1.3.2, 1.5.2]; `-p "/hooks"`, `"/permissions"` [S1: 1.1.12], `"/usage"`, `"/quota"` [S1: 1.1.11] | схема держится напоминаниями до предела [S1: 1.5.8] (C, строка 17 → «частично»); формат значения `--print-timeout` — «не подтверждено» |
| Модель и продукт | 14 | `gemini-4-carbon` и описание — `internal/cli/catalog.go`, строка 79 [S5]; карточка DeepMind, обновлена 10.11.2026 (поиск); выкатка для Ultra (поиск); Carbon Low/Medium/High в `/model` и `--model` [S1: 1.5.5, 1.5.8]; Orchestrator: план — Carbon (High), исполнение — Hydrogen (High) [S1: 1.5.10]; 1.5.16 — коммит 24.11.2026 04:06 UTC; README Gemini CLI (только Code Assist, переход 18.06.2026, «Not tuned for the Gemini 4 series»); `@google/gemini-cli` 0.71.1; в `models.js` ядра 0.71.1 нет Gemini 4; `subagents.md`, строки 371–372; `/swarm` сам по себе — исправлено в 1.5.13; `run_workflow` — 1.5.9; `AGY_CLI_AUTO_COMPACT_OVERRIDE` — 1.5.15 | `~/.agents/skills` — новый источник навыков пользователя [S1: 1.5.16] (добавлен в охрану) |
| Сбои | 5 | #1613 (17.11.2026, приложение 2.32.1, Orchestrator (Carbon)); #1193 (10.10.2026, ~80 тестовых файлов); #1044 (agy 1.2.6); #1245 (~250–276 тыс. при окне 1 млн, Gemini 4 Argon) | сообщения форума S14–S20 не перепроверены: форум недоступен, S16 и S18 поиск по заголовкам не нашёл |
| Инструменты | 4 | `write_to_file`, `view_file`, `run_command`, `find_by_name`, `grep_search`, `list_dir`, `read_url_content`, `search_web` [S1]; `CommandLine`, `TargetFile` [S25] | `replace_file_content`, `multi_replace_file_content`, `Cwd`, написание `TypeName` — только сторонние источники [S21] |
| Набор | 6 | `owned=(…)` в `gauntlet-kit.yml`, строки 56–57; имена `guard.py`, на которые опирается прослойка; 15 пунктов «Жёстких правил» в `GEMINI.md` — по одному на каждое правило; замены приложения D | размеры `gauntlet/CLAUDE.md` устарели (исправлено в A.4); в списке deny не было 9 сокращённых форм git из `.claude/settings.json` (исправлено) |

### Ядро в промптах и раздел 5 ядра

- Правило тщательности: `GEMINI.md`, раздел 4, пп. 1–7 — пункты 1–7 раздела 1 ядра без ослаблений; пп. 8–10
  (свежесть вывода, действие только с вызовом инструмента, отказ в разрешении — не повод обходить) отвечают на
  задокументированные сбои среды: #1613, #1193, #1044, мягкий отказ headless [S1: 1.1.27].
- Формат отчёта: `GEMINI.md`, раздел 5, — блок раздела 3 ядра дословно; `report.schema.json` — те же разделы.
- Приёмка: промпт координатора, раздел 3, пп. 2–5 — пункты 2.1–2.4 ядра (два возврата, выборочная перепроверка тем же
  способом, опровергатель без вывода первого исполнителя, «по умолчанию — опровергнуто», пометки в сводке); п. 6 —
  «быстрый прогон не бракуется за скорость; прогон без доказательств бракуется за доказательства».
- Карточки 4.1–4.4, 4.6 — агенты с целью, чек-листом, запретами и тем, что вернуть; у 4.2, 4.3, 4.4, 4.6 не было
  строки «Входы», у 4.6 — «Остановка» (ядро, раздел 4, требует все шесть) — добавлены.
- Раздел 5 ядра: гейты и CI не меняются и решают окончательно; права ролей — хук роли плюс `tools`; человеческие пути —
  guard, deny и CI, с прямой оговоркой, что `.agents/` и `GEMINI.md` CI не видит до A.7, п. 1; «не заканчивай с красным» —
  Stop-хук и раздел 3 `GEMINI.md` с выводом `> Task` и итогом; правило остановки ревью и находки «правило» — владельцу.
  Обещаний механизма там, где среда только инструктирует, не нашёл: такие места помечены «частично» или «нет».

### Что изменено и почему

1. **Stop роли hardener делил счётчик с Stop рабочей области.** `stop_gate.py` ведёт счётчик попыток и отметку
   последней остановки по ключу `<беседа>-<agent_id>`; прослойка не передавала `agent_id`, а Stop-хуки срабатывают и
   для беседы сабагента (#1527 — о глобальных хуках; адаптер, B.5, допускает это и для хуков рабочей области).
   Локально: после зелёного `gauntletFast` в той же беседе Stop роли вернул `{}`, не запустив `mutationGate` (вызовов
   `gradlew`: только `gauntletFast`). Исправлено: `stop --agent hardener` в `.agents/agents/hardener/hooks.json`,
   прослойка судит его как SubagentStop набора (`agent_id`, `agent_type`, счёт попыток по времени, как в наборе).
   После: оба прогона идут; красный `mutationGate` — продолжение 1/2, 2/2, затем отпуск с `agy-last-stop.txt`.
2. **Пути в форме URI и другие ключи пути проходили guard.** Провод Antigravity несёт пути как `file:///…`, SDK
   вендора нормализует их перед своими хуками [S25]; у SDK есть и инструменты `create_file`, `edit_file`, а среди
   путевых аргументов — `path`, `file_path` [S25]. Локально до исправления общий хук разрешал: `write_to_file` с
   `TargetFile=file://…/gauntlet/…`, `edit_file` с `file_path=…/gauntlet/…`, `create_file` с `path=…/GEMINI.md`,
   `run_command` с `Cwd=file://…` и записью в `gauntlet/`. Исправлено: `plain_path()` для путей и `Cwd`, ключи пути
   без учёта регистра. После — все четыре отказ; запись в `src/main` главным агентом и в `src/test` hardener'ом —
   по-прежнему разрешены.
3. **`~/.agents/` — конфигурация пользователя.** С agy 1.5.16 оттуда грузятся навыки во все беседы [S1: 1.5.16]:
   добавлено в охрану прослойки, в правило 1 `GEMINI.md` и в deny (`write_file(<HOME>/.agents/)`).
4. **`agy_card_check.py` засчитывал команду из вывода инструмента.** Отчёт «`./gradlew test` → BUILD SUCCESSFUL» при
   единственном вызове `view_file`, в выводе которого есть этот текст, проходил без отметок. Исправлено: команда
   ищется в имени и параметрах вызова, не в выводе. После — отметка; образцы автора: хороший — 0 отметок, плохой — 4.
5. **Список deny.** Добавлены 9 сокращённых форм из `.claude/settings.json` набора (`git commit --am`, `git push --m`,
   `--al`, `--b`, `git branch --forc`, `--d`, `--mo`, `--cop`, `git switch --force-`): текст B.6 обещал повторить список.
6. **Координатор.** Перед карточкой в новой рабочей копии — `agy -p "/hooks"` (без доверия папке хуки рабочей
   области не грузятся [S1: 1.1.1], и карточка шла бы без guard'а); прогон карточки — с `--mode accept-edits`
   (без него — сохранённый режим или Auto [S1: 1.5.7]).
7. **Текст.** fail-open — противоречие источников (B.5, C, строки 4 и 7, D.1, A.6, п. 11, формулировки `GEMINI.md`);
   C, строка 17 → «частично»; C, строка 16 и D.3, пп. 3, 7 — по журналу изменений; A.3 — режим Auto по умолчанию и
   неподтверждённое имя `toolPermission`; A.7, п. 2 — неподтверждённое `enableTerminalSandbox`; B.3 — значения
   `commandExecutionPolicy` и умолчания `mainAgent`/`subagent`; B.5 — поля входа, URI, каталог хука; A.4 — размеры
   `gauntlet/CLAUDE.md` на 24.11.2026; `GEMINI.md`, раздел 6 — устройство Orchestrator по [S1: 1.5.10]; D.3, пп. 14–16;
   источники S25–S28.
8. **Проверено после правок:** `agy_hooks.py selftest` — 24 случая, PASSED (20 у автора + 4 новых: URI, `edit_file`,
   `Cwd` в форме URI, `~/.agents`); команды из `hooks.json`, запущенные из каталогов этих файлов, — SessionStart, оба
   Stop; `GEMINI.md` — 16 951 байт (предел 24 000); JSON всех файлов и frontmatter агентов разбираются; `gemini.md`
   собран `render.py` из шаблона и файлов, обе копии `agy_hooks.py` и `coordinator.md` совпадают.

### Что осталось не проверенным

- Всё в живом agy: установщик и antigravity.google недоступны; строки «частично» держатся на A.6.
- Срабатывают ли хуки из frontmatter роли, PreToolUse рабочей области для сабагента, Stop роли при конце сабагента;
  выполняет ли agy хуки одного события параллельно (тогда два Gradle в одном каталоге) — D.3, п. 3.
- fail-open или fail-closed у PreToolUse в agy 1.5.16 (A.6, п. 11); верхний предел `timeout` хука.
- Грузятся ли хуки в headless-прогоне в недоверенной рабочей копии (A.6, п. 10); пути во входе хуков CLI — URI или
  обычные (прослойка принимает оба).
- Сообщения форума S14–S20; страницы документации antigravity.google напрямую; «`.agents/settings.json` больше не
  читается»; имена `executionNum`, `terminationReason`, `toolPermission`, `enableTerminalSandbox`; формат
  `--print-timeout`; написание `TypeName`, `replace_file_content`, `multi_replace_file_content`, `Cwd`.
- Смысловую сверку `GEMINI.md` и промпта координатора со всем `gauntlet/CLAUDE.md` и методом я не делал: сверены
  «Жёсткие правила», раздел 5 ядра и замены приложения D.
