# Адаптер gauntlet для Grok Build (xAI) с моделью Grok 4.7

Состояние на 2026-11-24. Сверено с документацией Grok Build на docs.x.ai (страницы `build/*`, прочитаны 2026-11-24),
с пакетом npm `@xai-official/grok@1.0.92` (встроенное в бинарник руководство пользователя прочитано как текст, бинарник
не запускался), с исходниками `xai-org/grok-build` (синхронизация 2026-09-29, версия крейтов 1.0.45) и с официальным
плагином `xai-org/grok-build-plugin-cc`. Источники с датами — D.5. Адаптер переносит ядро (`round23/core.md`: правило
тщательности, приёмка отчётов, формат отчёта, карточки) и механизмы набора в форматы Grok Build, ничего из них не
ослабляя. Где Grok чего-то не умеет, это сказано прямо и назван запасной путь.

## A. Что это и куда ставить

### A.1. Продукт и версия

- **«grok 4.7 build» — это Grok Build с моделью Grok 4.7.** Grok Build — официальный агент xAI для терминала
  (команда `grok`): интерактивный интерфейс, запуск без интерфейса (`grok -p`), режим агента по Agent Client Protocol
  (`grok agent stdio`). Бета — май 2026 (заметки о выпусках docs.x.ai). Установка: `curl -fsSL https://x.ai/cli/install.sh | bash`
  или `npm install -g @xai-official/grok`. Текущая версия на npm — **1.0.92** (опубликована 2026-11-20; канал alpha —
  1.0.93); пакет — обёртка над бинарником на Rust, сопровождающий `xai-security <security@x.ai>`, лицензия Apache-2.0.
  Исходники — `github.com/xai-org/grok-build` (синхронизируются из монорепозитория xAI, внешние правки не принимаются);
  последняя синхронизация — 2026-09-29, версия 1.0.45, то есть исходники отстают от бинарника на два месяца. Поэтому
  каждое поведение, на которое опирается адаптер, сверено ещё и с руководством, встроенным в бинарник 1.0.92.
- **Grok 4.7** (`grok-4.7`, сентябрь 2026) — модель xAI для кода и агентной работы: контекст 500 000 токенов, знания до
  мая 2026, уровни рассуждений `low`, `medium`, `high` (по умолчанию), `xhigh`; модель по умолчанию в Grok Build
  (docs.x.ai/developers/grok-4-7). Grok 4.7 Fast — та же модель на более быстрой инфраструктуре, вдвое дороже, только в
  Cursor и Grok Build. Прежняя кодовая модель `grok-build-0.1` снята с API 2026-11-19.
- **Не путать с неофициальными CLI:** `@vibe-kit/grok-cli` (сообщество, 0.0.34, 2025) и `grok-cli` (обёртка, которая
  запускает Claude Code через прокси к модели Grok, 1.0.5, 2025) — не продукт xAI; адаптер их не касается.
- В документации компания называется SpaceXSI, в README репозитория — SpaceXAI; это тот же поставщик (`x.ai`, `docs.x.ai`).

### A.2. Главное

1. **Grok Build читает артефакты Claude Code, и это ловушка.** Он сам подхватывает корневой `CLAUDE.md`,
   `.claude/agents/*.md` (как своих сабагентов) и `.claude/settings.json` (хуки и правила разрешений). Но хуки набора
   на событиях Grok работают не так, как в Claude Code (проверено на синтетических событиях, D.3):
   - `guard.py` не охраняет ничего: Grok называет инструменты по-своему (`run_terminal_command`, `search_replace`,
     `write`, `hashline_edit`, `apply_patch`), а guard судит только `Bash`, `Edit`, `Write`, `MultiEdit`, `NotebookEdit`
     и всё прочее пропускает. Правки набора, push с `--force`, запись ревьюера — всё проходит;
   - роль сабагента Grok передаёт полем `subagentType`, а не `agent_type`: права ролей в guard не действуют;
   - `stop_gate.py` из `.claude/settings.json` сам по себе работает: Grok шлёт псевдонимы `session_id` и
     `stop_hook_active`, а сабагент приходит в хуки со своим id сессии, поэтому отметка hardener'а с отметкой основного
     агента не смешивается (исходники 1.0.45; проверено, D.3). Ловушка в другом: если рядом с прослойкой оставить хуки
     `.claude/settings.json` включёнными, на каждый Stop `stop_gate.py` идёт дважды и попытки красного гейта
     считаются вдвое (проверено, D.3);
   - строка `@gauntlet/CLAUDE.md` в корневом `CLAUDE.md` не раскрывается: импорта `@` нет ни в документации, ни в
     загрузчике правил (исходники 1.0.45), строки `@import` нет и в бинарнике 1.0.92 — правил набора в контексте нет;
   - вывод SessionStart до модели не доходит: строки статуса хуков нет.
   Закрывает это прослойка `gauntlet/adapters/grok/grok_hooks.py` (A.8; вносит владелец набора своим PR): она переводит
   события Grok в форму, которую читают `guard.py` и `stop_gate.py`, и запускает их без правки. Хуки из
   `.claude/settings.json` для Grok выключаются (`[compat.claude] hooks = false`), правила набора подключает ссылка
   `.grok/rules/10-gauntlet-kit.md` → `gauntlet/CLAUDE.md`.
2. **Что Grok держит средой.** `PreToolUse` — отказ инструменту (как у Claude). `Stop` и `SubagentStop` — блокировка
   конца хода с причиной; Grok продлевает ход не больше 8 раз за ход. Правила разрешений `[permission]` (`deny` сильнее
   `allow` и режима always-approve; по правилам `Edit(...)` Grok проверяет и shell-команды записи). Песочница уровня ОС
   (Landlock, bubblewrap, Seatbelt) защищает настройки Grok и файлы хуков проекта от записи, но **не может сделать
   файлы набора внутри рабочей копии только читаемыми**: ядро не вычитает каталог из разрешения на запись родителя.
3. **Где Grok слабее Claude Code для набора.** Сабагенты по умолчанию идут в фоне, и ход родителя может кончиться,
   пока они работают: так Grok задуман (завершение сабагента будит родителя новым ходом с результатом), но вывод,
   сделанный в закончившемся ходе, будет без их отчётов (D.2); итог сабагента приходит обрезанным до 16 000 байт, а
   опрос без `timeout_ms` даёт снимок, а не итог; хуки и правила проекта действуют только в доверенной папке
   (`--trust`; для самих определений агентов проекта — не подтверждено); сбой хука (таймаут по умолчанию 5 с,
   падение) пропускает действие, если у обработчика нет `failClosed` (у guard он есть, A.7); вход хука больше
   128 КиБ Grok обрезает (`toolInputTruncated`, A.8); нет инструмента, которым координатор открыл бы сессию владельцу
   или написал в чужую сессию; нет подписки на события PR. Для каждого пункта ниже есть замена или прямо сказано, что
   её нет.
4. **Тщательность в Grok.** Правило тщательности и формат отчёта лежат в `.grok/rules/00-gauntlet-grok.md` и доходят до
   каждого сабагента (правила проекта Grok подмешивает и в контекст сабагентов). Форму отчёта держит хук
   `SubagentStop` (не больше двух возвратов), ожидание всех сабагентов — хук `Stop`, истину — координатор по разделу 2
   ядра. Своя «проверка по доказательствам» у Grok есть (`/goal` с панелью проверяющих сабагентов), но в сессиях
   набора она не включается без решения владельца, как Ultracode.

Ответ на вопрос владельца для Grok: перенос выполним. Гейты, CI и процесс не меняются, хуки и роли набора
переиспользуются без копий, карточки становятся своими агентами Grok. Остаток — пункт 3 и раздел D.1: часть держат
инструкции, владелец и CI.

### A.3. Файлы в проекте

| Путь | Что это | Чей | Откуда |
|---|---|---|---|
| `.grok/rules/00-gauntlet-grok.md` | инструкция проекта для Grok: замены механизмов Claude, правило тщательности, формат отчёта, сбои Grok (B.1) | человека | этот адаптер |
| `.grok/rules/10-gauntlet-kit.md` | символическая ссылка на `../../gauntlet/CLAUDE.md`: правила набора целиком, без копии (A.5) | человека | `ln -s` (A.4) |
| `.grok/hooks/gauntlet.json` | хуки набора через прослойку (A.7) | человека | этот адаптер |
| `.grok/config.toml` | `[permission] deny` для путей человека — второй слой поверх guard (A.7; решение A.6, п. 3) | человека | этот адаптер |
| `.grok/agents/gauntlet-card-map.md`, `-framework.md`, `-critic.md`, `-refuter.md`, `-review-repro.md` | карточки ядра 4.1–4.4 и 4.6 как свои агенты Grok (B.4); 4.5 — роль `reviewer` | человека | этот адаптер |
| `gauntlet/adapters/grok/grok_hooks.py` | прослойка: `session-start`, `guard`, `stop`, `report` (A.8) | набор | PR владельца набора |
| `~/.grok/config.toml` (машина владельца) | выключить хуки Claude для Grok, глубина сабагентов 1, модель сабагента от родителя, таймаут shell (A.7) | человека | владелец сам |

Не копируются и не меняются: `gauntlet/CLAUDE.md`, `.claude/agents/*.md` (Grok берёт их как своих сабагентов),
`gauntlet/hooks/*`, оба workflow, корневой `CLAUDE.md`. Claude Code и Grok Build могут работать в одном репозитории:
Claude читает `.claude/`, Grok — `.grok/` и, по совместимости, `CLAUDE.md` и `.claude/agents/`.

### A.4. Установка

Всё ниже — правки набора и конфигурации агента, то есть файлы человека: их вносит владелец PR'ом (или админ-запуском
по своему решению), а не сессия шага.
1. Положить файлы A.3 одним PR (тексты — A.7, A.8, B.1, B.4) и ссылку:
   `ln -s ../../gauntlet/CLAUDE.md .grok/rules/10-gauntlet-kit.md`. Проверка `gauntlet kit unchanged` на нём красная
   намеренно: он меняет `gauntlet/`.
2. Решить пункты A.6 (прежде всего 1: охрана `.grok/` и `AGENTS.md` в guard и в CI).
3. В `~/.grok/config.toml` своей машины добавить строки A.7 (особенно `[compat.claude] hooks = false`).
4. Запускать `grok` из оболочки, где задано `ORG_GRADLE_PROJECT_publicRepositories=true` и не заданы `GAUNTLET_GUARD` и
   `GAUNTLET_STOP_HOOK`: хуки получают окружение сессии.
5. Первый запуск в репозитории — `grok --trust` (или `/hooks-trust` в сессии): без доверия папки Grok молча не
   загружает правила и хуки проекта (и хуки агентов; сами определения агентов — не подтверждено). Доверие хранится
   в `~/.grok/trusted_folders.toml`.
6. `grok inspect` в корне репозитория должен показать:
   - правила: `CLAUDE.md`, `.grok/rules/00-gauntlet-grok.md`, `.grok/rules/10-gauntlet-kit.md` (самый крупный из них —
     это текст `gauntlet/CLAUDE.md`; маленький размер у него значит, что ссылка не сработала);
   - хуки: только из `.grok/hooks/gauntlet.json` (SessionStart, PreToolUse, Stop, SubagentStop ×2) и ни одного из
     `.claude/settings.json`;
   - агентов: `specifier`, `hardener`, `reviewer` (из `.claude/agents/`) и пять `gauntlet-card-*`.
7. Живая проверка на одноразовой ветке:
   - первая строка ответа — строка статуса `[gauntlet] active … guard: on; stop hook: on …` из `grok-status.txt`;
   - «допиши строку в `gauntlet/README.md`» и «выполни `echo x >> gauntlet/config/gauntlet.properties`» — оба отклонены
     с `[gauntlet guard]`;
   - сабагенту `reviewer`: «выполни `touch src/x`» — отказ;
   - shell-команда длиннее 128 КиБ (например, `echo` с длинной строкой) — отказ `[gauntlet guard] Grok cut this call's
     input …`;
   - правка в `src/main` и конец хода — Stop-хук гоняет `gauntletFast` (строка состояния показывает работу stop-хука;
     при красном гейте ход продолжается с причинами). **Не продолжился — блокировка Stop в этой версии не работает**
     (D.4): сессии тогда работают по разделу 3 правил Grok, решает CI;
   - сабагент `gauntlet-card-map` в фоне и попытка закончить ход до его конца — ход продолжается с причиной
     «ещё работают …»;
   - сабагент-карточка, которому велено ответить одной фразой, — отчёт возвращён хуком с перечнем недостающих разделов.
8. По желанию (решение A.6, п. 4) — песочница: проверить `./gradlew gauntletFast` под выбранным профилем до того, как
   сделать его профилем по умолчанию.

`/import-claude` (перенос настроек Claude Code в Grok) для набора не использовать: перенесённые хуки встретят
инструменты Grok без прослойки.

### A.5. Как переиспользуются файлы набора, а не копируются

- `gauntlet/CLAUDE.md` целиком попадает в контекст каждой сессии и каждого сабагента через ссылку
  `.grok/rules/10-gauntlet-kit.md`: Grok загружает все `*.md` каталога `.grok/rules/` полностью, без предела размера, а
  символическую ссылку в каталоге правил читает как файл, на который она указывает (исходники 1.0.45, тест
  `canonical_named_rule_collision_is_normalized_once` в `prompt/agents_md.rs`; в 1.0.92 — только если цель ссылки
  внутри репозитория, руководство 1.0.92 «Project Rules», Auto-Loading Behavior: `gauntlet/CLAUDE.md` внутри).
  `00-gauntlet-grok.md` правил не дублирует: в нём замены механизмов, правило тщательности, формат отчёта и сбои Grok.
- Роли: Grok находит `.claude/agents/*.md` как агентов проекта (каталоги `.grok/agents` и `.claude/agents` от рабочего
  каталога до корня репозитория), понимает их заголовок (`tools: Read, Grep, Glob, Edit, Write, Bash` — имена Claude
  переводятся в виды инструментов Grok; `model: inherit`) и вызывает их `spawn_subagent` с `subagent_type` = имя роли.
  Текст роли становится системным промптом сабагента без копии (B.3).
- Хуки: `.grok/hooks/gauntlet.json` вызывает те же `gauntlet/hooks/session_start.sh`, `guard.py`, `stop_gate.py`,
  что `.claude/settings.json`, — через прослойку, которая только переводит событие.
- Ядро: правило тщательности и формат — в `00-gauntlet-grok.md` (разделы 4–5), карточки — в `.grok/agents/`,
  приёмка — в промпте координатора (B.2).

### A.6. Решения владельца

1. **Охрана `.grok/` и `AGENTS.md` в guard и в CI.** Их нет ни в `HUMAN_OWNED` (`gauntlet/hooks/guard.py`), ни в списке
   `.github/workflows/gauntlet-kit.yml`. Прослойка добавляет их к путям человека для агентов Grok (и для команд shell
   — тем же разбором guard), но PR с правкой `.grok/` проверка `gauntlet kit unchanged` не заметит, а агент Claude Code
   их не охраняет. Рекомендация: добавить `.grok/` и `AGENTS.md` в оба списка (и `~/.grok` — рядом с `~/.claude` в
   `user_config_violation` guard) — ответьте здесь.
2. **Прослойка `gauntlet/adapters/grok/grok_hooks.py` в наборе.** Без неё Grok-сессия работает без охраны путей и
   ролей, без проверки формы отчётов, без ожидания своих сабагентов и без строки статуса (A.2, п. 1). Рекомендация:
   внести PR'ом владельца набора вместе с проверками из D.3 — ответьте здесь.
3. **Правила `[permission] deny` в `.grok/config.toml`.** Второй слой поверх guard, держит его и при сбое хука. Цена:
   админ-правку набора через Grok они не пропустят (deny сильнее allow): для неё владелец на время снимает строки сам
   или правит файл на GitHub. Возможны лишние вопросы разрешения у shell-команд записи после `cd` (Grok не всегда
   определяет путь; D.4). Рекомендация: включить и проверить шагом A.4 п. 7; при частых вопросах — убрать, охрану
   держат guard и CI — ответьте здесь.
4. **Песочница для сессий шага.** `--sandbox workspace` (или свой профиль с `extends = "workspace"`) запрещает агенту и
   его командам писать `~/.grok/config.toml`, `trusted_folders.toml`, `~/.grok/hooks/` и файлы хуков проекта
   (`.grok/hooks/*`, `.claude/settings.json`), а запись вне репозитория и временных каталогов закрывает. Gradle нужен
   записываемый `~/.gradle` (`read_write = ["~/.gradle"]` в своём профиле), Testcontainers — сокет Docker (под
   `workspace` он открыт, под профилями без сети — закрыт). Файлы набора внутри репозитория песочница не защищает.
   Рекомендация: включить свой профиль после проверки A.4 п. 8; до проверки — без песочницы — ответьте здесь.
5. **Строка ответа внешнему ревьюеру:** «Ответ Grok Build на комментарий <ревьюер>» вместо «Ответ Claude Code …»
   (метод, п. 19; `gauntlet/CLAUDE.md`, «Правила владельца»). Рекомендация: да — ответьте здесь.
6. **Модели и уровни для Grok** в «Правилах владельца» (метод, п. 17): координатор — `grok-4.7` `xhigh`; сессия шага —
   `grok-4.7` `high`; тонкая семантика фреймворка — `grok-4.7` `xhigh`; роли и карточки наследуют. Fast — по желанию
   ради скорости (та же модель, вдвое дороже). Закреплять ли модель отдельных типов сабагентов
   (`[subagents.models]`) — ответьте здесь.
7. **`failClosed` у guard.** В Grok 1.0.92 обработчик `PreToolUse` с `"failClosed": true` при сбое (таймаут, падение,
   нечитаемый ответ) отклоняет вызов, а не пропускает его (руководство 1.0.92, Hooks: Key Fields). В Claude Code сбой
   guard пропускает вызов; здесь можно строже, и адаптер это ставит (A.7): прослойка на событии, которое не может
   прочитать, по-прежнему отвечает «разрешено» (это не сбой), а падение Python или зависание станет отказом с
   причиной вместо тихой дыры. Цена: сломанная прослойка блокирует правки и shell, пока владелец её не починит или не
   выключит хук в `/hooks`. На `Stop`/`SubagentStop` Grok `failClosed` не поддерживает — там сбой пропускает
   остановку, держит CI. Рекомендация: оставить — ответьте здесь.

### A.7. Тексты конфигурации

`.grok/hooks/gauntlet.json` — хуки набора через прослойку. Таймауты `SessionStart`, `Stop` и `SubagentStop` — как в
`.claude/settings.json`, у `PreToolUse` — 30 с: у Grok по умолчанию 5 с для `SessionStart` и `PreToolUse` и 600 с для
`Stop`/`SubagentStop`, а сбой по таймауту пропускает действие — кроме guard: у него `"failClosed": true` (A.6, п. 7),
и его сбой отклоняет вызов.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 -B \"$CLAUDE_PROJECT_DIR/gauntlet/adapters/grok/grok_hooks.py\" session-start",
            "timeout": 180
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "^(Bash|Edit|Write|MultiEdit|NotebookEdit|run_terminal_command|run_terminal_cmd|search_replace|write|hashline_edit|apply_patch)$",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -B \"$CLAUDE_PROJECT_DIR/gauntlet/adapters/grok/grok_hooks.py\" guard",
            "timeout": 30,
            "failClosed": true
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 -B \"$CLAUDE_PROJECT_DIR/gauntlet/adapters/grok/grok_hooks.py\" stop --task gauntletFast --max-attempts 3 --timeout 1700",
            "timeout": 1800
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
            "command": "python3 -B \"$CLAUDE_PROJECT_DIR/gauntlet/adapters/grok/grok_hooks.py\" stop --task mutationGate --max-attempts 2 --timeout 3300",
            "timeout": 7200
          }
        ]
      },
      {
        "matcher": "^(reviewer|gauntlet-card-[a-z0-9-]+)$",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -B \"$CLAUDE_PROJECT_DIR/gauntlet/adapters/grok/grok_hooks.py\" report",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

`.grok/config.toml` — правила разрешений проекта (решение A.6, п. 3). `.claude/settings.json` набора Grok тоже читает:
его `permissions.allow`/`deny` (git, gh, `./gradlew`; синтаксис `Bash(cmd:*)` Grok понимает) действуют и здесь.

```toml
# .grok/config.toml — Grok Build в репозитории под набором gauntlet. Файл человека, как .claude/settings.json.
# Проект может задать здесь только [mcp_servers], [plugins] и [permission]; остальное — в ~/.grok/config.toml.
# Читается только в доверенной папке (grok --trust или /hooks-trust).

[permission]
# Пути человека (gauntlet/CLAUDE.md, правило 1). Правило Edit(...) закрывает правку и запись файлов инструментами
# Grok (в правилах Grok Edit(...) и Write(...) — один фильтр), а при таком правиле Grok проверяет и shell-команды
# записи (перенаправления, cp, mv, tee…). Второй слой поверх guard.py: deny сильнее allow и always-approve.
# Цена: админ-правку набора через Grok эти строки тоже не пропустят (A.6, п. 3).
deny = [
  "Edit(gauntlet/**)",
  "Edit(.claude/**)",
  "Edit(.grok/**)",
  "Edit(CLAUDE.md)",
  "Edit(AGENTS.md)",
  "Edit(.github/workflows/gauntlet.yml)",
  "Edit(.github/workflows/gauntlet-kit.yml)",
  "Edit(CODEOWNERS)",
  "Edit(.github/CODEOWNERS)",
  "Edit(.gitlab/CODEOWNERS)",
]
```

`~/.grok/config.toml` машины владельца — добавить к своему (ключи из справочника настроек 1.0.92):

```toml
# ~/.grok/config.toml — машина владельца (файл человека). Дополнить, а не заменить свой файл.

[compat.claude]
# Хуки набора Grok берёт только из .grok/hooks/gauntlet.json (через прослойку). Без этой строки он запускает
# ещё и .claude/settings.json напрямую: guard.py там не видит инструментов Grok и ничего не охраняет, а stop_gate.py
# идёт на каждый Stop вторым экземпляром, и попытки красного гейта считаются вдвое (D.3).
hooks = false

[subagents]
# Сабагенты не порождают своих (как в Claude Code). По умолчанию на маршруте демона глубина 5.
max_depth = 1

[features]
# Модель сабагента — модель родителя; агент не выбирает сабагенту другую (п. 17 метода: решает владелец).
subagent_model_inheritance = true

# По желанию владельца: выключить /goal и воркфлоу (/workflow, /deep-research) средой, а не только инструкцией, —
# аналог «ультракод выключен». Действует на все сессии Grok этой машины; включает обратно владелец.
# [goal]
# enabled = false
# [workflows]
# enabled = false

[models]
# Модель и уровень по умолчанию; для координатора и тонких шагов — --effort xhigh при запуске (B.2, B.5).
default = "grok-4.7"
default_reasoning_effort = "high"

[toolset.bash]
# Gradle-гейты в переднем плане идут дольше 2 минут по умолчанию. Предел таймаута, который модель запрашивает сама
# (max_timeout_secs), по умолчанию 36000 с — его не трогать: строка с меньшим значением только урезала бы его.
timeout_secs = 1800
```

Для автоматизации (координатор запускает Grok без интерфейса) — `--always-approve` вместе с правилами `deny` и хуками
(они действуют и в этом режиме) или `--permission-mode dontAsk` с явными `--allow`. Запрет always-approve для всей
машины — `[ui] disable_bypass_permissions_mode = true` в `/etc/grok/requirements.toml` (только корневой файл).

### A.8. Прослойка `gauntlet/adapters/grok/grok_hooks.py` (для PR владельца набора)

Только стандартная библиотека Python 3. `guard.py` загружается как модуль по пути (байткод в `gauntlet/` не пишется),
к его `HUMAN_OWNED` добавляются `AGENTS.md` и `.grok/`, к проверке `~/.claude` — настройки Grok в `$GROK_HOME`
(кроме каталогов сессий, рабочих копий и памяти: там файл плана Grok). Не загрузился модуль — `guard.py` запускается
как есть; не запустился и он — прослойка завершается с ошибкой (а не молча разрешает), и `failClosed` отклоняет
вызов. Вход больше 128 КиБ Grok передаёт хуку обрезанным (`toolInputTruncated`; в 1.0.45 весь вход — одной
строкой, в 1.0.92 — с обрезанными длинными строками): shell-команду и `apply_patch` с обрезанным текстом и вход не
объектом прослойка отклоняет (того же требует руководство Grok к охранным хукам), а путь файловых инструментов Grok не
обрезает — его guard судит как обычно. Сбой прослойки на `Stop`/`SubagentStop`, как и сбой хуков набора, пропускает
остановку (держит CI); на `PreToolUse` из-за `failClosed` сбой отклоняет вызов (A.6, п. 7).

```python
#!/usr/bin/env python3
"""Grok Build -> gauntlet hooks bridge (gauntlet/adapters/grok/grok_hooks.py).

Grok Build (xAI's `grok` CLI) loads Claude-format hook files and also sends Claude's snake_case spelling of the
common keys (session_id, tool_name, tool_input, stop_hook_active ...). What the kit's hooks read still differs:
  - tool names are Grok's own: run_terminal_command, search_replace, write, hashline_edit, apply_patch. guard.py
    judges Bash, Edit, Write, MultiEdit and NotebookEdit and lets every other name through, so on its own it allows
    every edit and every command a Grok agent makes;
  - a subagent is named by subagentType and identified by subagentId; agent_type and agent_id are absent, so the
    role scopes in guard.py never apply (a subagent's events carry its own session id, so stop marks stay apart);
  - a hook input over 128 KiB arrives cut (toolInputTruncated): guard.py must not judge a command or a patch it
    cannot read whole;
  - SessionStart output never reaches the model, so the hook status line has to travel another way.
This bridge rewrites each event into the shape the kit's hooks read and runs those hooks unchanged.

  grok_hooks.py session-start        SessionStart: session_start.sh; its status line is written to
                                     $(git rev-parse --git-path gauntlet-hook)/grok-status.txt, which the agent
                                     prints first (per working copy, like stop_gate.py's own state)
  grok_hooks.py guard                PreToolUse: guard.py on the rewritten event; AGENTS.md, .grok/ and Grok's user
                                     configuration count as human-owned too; a cut shell command or patch, or an
                                     input that is not an object, is refused
  grok_hooks.py stop ARGS...         Stop / SubagentStop: stop_gate.py ARGS on the rewritten event. On Stop it first
                                     keeps the agent working while its own subagents or a Gradle run still go on
  grok_hooks.py report               SubagentStop of the reviewer or a read-only card: the final message has the
                                     sections of the report format; at most two returns, then it lets the agent go

Like the kit's hooks it fails open on input it cannot read: a broken hook must not brick a session. CI stays the
judge. Humans switch it off with the kit's own variables (GAUNTLET_GUARD=off, GAUNTLET_STOP_HOOK=off).
"""
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True          # importing guard.py must not leave __pycache__ inside gauntlet/

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("GROK_WORKSPACE_ROOT") or os.getcwd()
HOOKS = os.path.join(ROOT, "gauntlet", "hooks")
# Grok tool -> the Claude tool guard.py judges. The input fields guard.py reads (file_path, command) are the same.
TOOLS = {"run_terminal_command": "Bash", "run_terminal_cmd": "Bash", "search_replace": "Edit",
         "hashline_edit": "Edit", "write": "Write"}
PATCH_PATH = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.M)
ROLES = {"specifier", "hardener", "reviewer"}
# Subagent types that may not change files or git state: guard.py gives them the reviewer's rights.
READ_ONLY = re.compile(r"^(?:gauntlet-card-[a-z0-9-]+|explore|plan)$")
# Paths a Grok agent must not change on top of guard.py's HUMAN_OWNED: its project instructions and configuration.
GROK_OWNED = ("AGENTS.md", ".grok/")
# Grok's user configuration (GROK_HOME, default ~/.grok): what could switch hooks, trust or rules off.
GROK_USER = ("config.toml", "managed_config.toml", "requirements.toml", "sandbox.toml", "trusted_folders.toml",
             "hooks", "hooks-paths", "disabled-hooks", "agents", "rules", "personas", "roles", "plugins", "skills")
REPORT_SECTIONS = ("## Итог", "## Проверено", "## Не проверено", "## Вопросы и риски")
COVERAGE = re.compile(r"покрытие:[^\n]*?\d+\s*из\s*\d+", re.I)
EVIDENCE = re.compile(r"доказательство:", re.I)
CLIPPED = re.compile(r"\[\+\d+ chars\]\s*$")
MAX_RETURNS = 2
# Grok cuts a tool input whose JSON passes 128 KiB (toolInputTruncated): 1.0.45 sends the whole input as one string,
# 1.0.92 keeps the keys and cuts long strings. Its hooks guide: a guard that checks a string's text should deny then.
CUT = ("[gauntlet guard] Grok cut this call's input for the hooks (over 128 KiB), so the guard cannot read all of it. "
       "Split the command into shorter ones, or write long text to a file with the file tools first.")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        return 0
    if not isinstance(event, dict):
        return 0
    if mode == "session-start":
        return session_start(event, raw)
    if mode == "guard":
        return guard(event)
    if mode == "stop":
        return stop(event, sys.argv[2:])
    if mode == "report":
        return report(event)
    sys.stderr.write(f"grok_hooks.py: unknown mode {mode!r}\n")
    return 0


# ----------------------------------------------------------------------------- shared

def role(event):
    """The agent_type guard.py and stop_gate.py read: the kit's role, reviewer rights for a read-only card, or None."""
    kind = event.get("subagentType") or event.get("agent_type")
    if not kind:
        return None
    if kind in ROLES:
        return kind
    return "reviewer" if READ_ONLY.match(kind) else kind


def claude_event(event, **changes):
    out = dict(event)
    out.setdefault("session_id", event.get("sessionId"))
    out.setdefault("stop_hook_active", bool(event.get("stopHookActive")))
    out.setdefault("last_assistant_message", event.get("lastAssistantMessage"))
    if event.get("subagentId"):
        out["agent_id"] = event["subagentId"]
    agent = role(event)
    if agent:
        out["agent_type"] = agent
    else:
        out.pop("agent_type", None)
    out.update(changes)
    return out


def state_dir():
    """The folder stop_gate.py keeps its state in: per working copy, so parallel Grok worktrees do not share it."""
    try:
        path = subprocess.run(["git", "rev-parse", "--git-path", "gauntlet-hook"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not path:
        return None
    path = path if os.path.isabs(path) else os.path.join(ROOT, path)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    return path


def safe(text):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(text))[:120]


# ----------------------------------------------------------------------------- SessionStart

def session_start(event, raw):
    try:
        proc = subprocess.run(["bash", os.path.join(HOOKS, "session_start.sh")], input=raw.encode(), cwd=ROOT,
                              capture_output=True, timeout=170)
        lines = proc.stdout.decode("utf-8", "replace").strip().splitlines()
        status = lines[-1] if lines else "[gauntlet] WARNING: session_start.sh printed nothing"
    except (OSError, subprocess.SubprocessError) as e:
        status = f"[gauntlet] WARNING: session_start.sh did not run: {e}"
    folder = state_dir()
    if folder:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        try:
            with open(os.path.join(folder, "grok-status.txt"), "w", encoding="utf-8") as f:
                f.write(f"{stamp} session {event.get('sessionId') or event.get('session_id')}: {status}\n")
        except OSError:
            pass                                     # a read-only sandbox: no status line, the agent says so
    return 0


# ----------------------------------------------------------------------------- PreToolUse

def guard(event):
    tool = event.get("toolName") or event.get("tool_name") or ""
    params = event.get("toolInput") or event.get("tool_input") or {}
    if tool not in TOOLS and tool != "apply_patch":
        return 0
    if event.get("toolInputTruncated") and os.environ.get("GAUNTLET_GUARD", "").lower() != "off" and (
            not isinstance(params, dict) or tool == "apply_patch" or TOOLS[tool] == "Bash"):
        sys.stdout.write(json.dumps({"hookSpecificOutput": {      # a file tool's path is never cut: judged below
            "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": CUT}}))
        return 0
    if not isinstance(params, dict):
        return 0
    if tool in TOOLS:
        calls = [(TOOLS[tool], params)]
    else:                                                # apply_patch: every file the patch names
        text = params.get("patch") or params.get("input") or ""
        calls = [("Edit", {"file_path": p}) for p in PATCH_PATH.findall(text if isinstance(text, str) else "")]
    for claude_tool, tool_input in calls:
        verdict = judge(claude_event(event, tool_name=claude_tool, tool_input=tool_input, hook_event_name="PreToolUse"))
        if verdict:
            sys.stdout.write(verdict)
            return 0
    return 0


def load_guard():
    spec = importlib.util.spec_from_file_location("gauntlet_guard", os.path.join(HOOKS, "guard.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HUMAN_OWNED = tuple(module.HUMAN_OWNED) + GROK_OWNED
    kit_check = module.user_config_violation

    def user_config_violation(path):
        return kit_check(path) or grok_user_violation(path)

    module.user_config_violation = user_config_violation
    return module


def grok_user_violation(path):
    if not path:
        return None
    home = os.path.realpath(os.path.expanduser(os.environ.get("GROK_HOME") or "~/.grok"))
    target = os.path.expanduser(path)
    if not os.path.isabs(target):
        return None
    target = os.path.realpath(target)
    for name in GROK_USER:
        owned = os.path.join(home, name)
        if target == owned or target.startswith(owned + os.sep):
            return (f"{owned} is Grok Build's user configuration (it could switch hooks, trust or rules off). "
                    f"Do not touch it.")
    return None


def judge(claude):
    """guard.py's verdict on one rewritten event: its JSON output, or '' when it allows the call."""
    try:
        module = load_guard()
    except Exception:                                    # the kit changed or is missing: run guard.py as it is
        proc = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, "guard.py")], input=json.dumps(claude),
                              capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0 and not proc.stdout.strip():   # guard.py did not run: a hook failure (failClosed)
            raise SystemExit(f"grok_hooks.py: guard.py failed (exit {proc.returncode}): {proc.stderr.strip()[-300:]}")
        return proc.stdout.strip()
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


# ----------------------------------------------------------------------------- Stop / SubagentStop

def stop(event, args):
    name = event.get("hook_event_name")
    if name == "Stop":
        if event.get("reason") not in (None, "end_turn"):
            return 0                                     # the observe-only Stop at session end: nothing to gate
        waiting = still_running(event)
        if waiting:
            sys.stdout.write(json.dumps({"decision": "block", "reason": (
                "[gauntlet] Не заканчивай ход: ещё работают " + "; ".join(waiting) + ". Дождись каждого "
                "(wait_commands_or_subagents или get_command_or_subagent_output), прочитай отчёт сабагента целиком "
                "(если он обрезан - запроси полный вывод) и прими его по правилам приёмки; затем заканчивай.")},
                ensure_ascii=False))
            return 0
    claude = claude_event(event)
    proc = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, "stop_gate.py")] + list(args),
                          input=json.dumps(claude), capture_output=True, text=True, cwd=ROOT)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def still_running(event):
    found = []
    for task in event.get("backgroundTasks") or []:
        if not isinstance(task, dict) or task.get("status") != "running":
            continue
        if task.get("type") == "subagent":
            found.append(f"сабагент {task.get('agentType') or ''} {task.get('id')} «{task.get('description') or ''}»")
        elif task.get("type") == "shell" and re.search(r"\bgradlew?\b", task.get("command") or ""):
            found.append(f"фоновый прогон Gradle {task.get('id')} «{task.get('command')}»")
    return found


# ----------------------------------------------------------------------------- report form

def report(event):
    if event.get("hook_event_name") != "SubagentStop":
        return 0
    text = event.get("lastAssistantMessage") or event.get("last_assistant_message") or ""
    missing = reviewer_gaps(text) if event.get("subagentType") == "reviewer" else card_gaps(text)
    if not missing:
        return 0
    folder = state_dir()
    counter = os.path.join(folder, "grok-report-" + safe(event.get("subagentId") or "unknown")) if folder else None
    returns = 0
    if counter and os.path.exists(counter):
        try:
            returns = int(open(counter, encoding="utf-8").read().strip() or 0)
        except (OSError, ValueError):
            returns = 0
    if returns >= MAX_RETURNS:
        sys.stdout.write(json.dumps({"systemMessage": (
            f"[gauntlet] Отчёт сабагента {event.get('subagentType')} всё ещё не по форме после {MAX_RETURNS} возвратов "
            f"(нет: {', '.join(missing)}). Координатор не принимает его: пометка «не проверено» и вопрос владельцу.")},
            ensure_ascii=False))
        return 0
    if counter:
        try:
            with open(counter, "w", encoding="utf-8") as f:
                f.write(str(returns + 1))
        except OSError:
            pass
    sys.stdout.write(json.dumps({"decision": "block", "reason": (
        f"[gauntlet] Отчёт не по форме (возврат {returns + 1} из {MAX_RETURNS}): нет " + "; ".join(missing) + ". "
        "Это доработка отчёта, не новый раунд работы: каждое утверждение - с доказательством (команда и вывод, "
        "файл:строка с цитатой или источник нужной версии), непроверенное - в «Не проверено». Верни отчёт целиком.")},
        ensure_ascii=False))
    return 0


def card_gaps(text):
    clipped = bool(CLIPPED.search(text))          # Grok clips the field at 32 768 characters: the tail may be cut
    required = REPORT_SECTIONS[:2] if clipped else REPORT_SECTIONS
    missing = [f"раздела «{s}»" for s in required if s not in text]
    if "## Проверено" in text:
        if not COVERAGE.search(text):
            missing.append("числа покрытия «покрытие: N из M»")
        if not EVIDENCE.search(text):
            missing.append("ни одного утверждения с «доказательство: …»")
    return missing


def reviewer_gaps(text):
    missing = []
    if not re.search(r"^VERDICT: (APPROVED|CHANGES REQUESTED)\s*$", text, re.M):
        missing.append("строки «VERDICT: APPROVED | CHANGES REQUESTED»")
    if not COVERAGE.search(text):
        missing.append("строки «Покрытие: файлы диффа N из M»")
    if "## Не проверено" not in text and not CLIPPED.search(text):
        missing.append("раздела «## Не проверено»")
    return missing


if __name__ == "__main__":
    sys.exit(main())
```

## B. Промпты

### B.1. `.grok/rules/00-gauntlet-grok.md` (инструкция проекта)

Грузится в каждую сессию и в каждого сабагента (у агентов Grok подмешивание правил проекта включено по умолчанию).

````markdown
# Gauntlet в Grok Build: что здесь иначе, чем в Claude Code

Разработка в этом репозитории идёт по методу gauntlet. Процесс, гейты, роли и жёсткие правила — в
`gauntlet/CLAUDE.md`: Grok загружает его рядом с этим файлом (`.grok/rules/10-gauntlet-kit.md` — ссылка на него,
потому что строку `@gauntlet/CLAUDE.md` в корневом `CLAUDE.md` Grok не раскрывает). Этот файл говорит, чем Grok
Build заменяет механизмы Claude Code, и задаёт правило тщательности. По процессу и правилам главный
`gauntlet/CLAUDE.md`, по механике Grok — этот файл. Корневой `AGENTS.md`, если он есть, написан для другого агента
(Codex): где он расходится с этим файлом, в Grok действует этот файл.

## 0. Начало каждой сессии (сабагенты этот раздел пропускают)

1. Первой командой выполни `cat "$(git rev-parse --git-path gauntlet-hook/grok-status.txt)"` и приведи эту
   строку первым сообщением. Это строка статуса хуков набора: в Claude Code её печатает хук SessionStart, а вывод
   SessionStart в Grok до модели не доходит, поэтому прослойка набора пишет её в файл.
   - Файла нет или время в строке раньше начала этой сессии — хуки набора в этой сессии не работают (папка не
     доверена, хуки выключены, Grok запущен не в той копии). Скажи об этом первым сообщением и работай по
     разделу 3 «Без хуков», пока владелец не ответит.
   - В строке `guard: off` или `stop hook: off` — скажи об этом и не правь набор (раздел 1), пока владелец не
     разрешит.
2. Текст `gauntlet/CLAUDE.md` должен быть у тебя в контексте целиком. Если его нет (ссылка не загрузилась) —
   прочитай файл сам от начала до конца, прежде чем что-то делать.

## 1. Жёсткие правила (кратко; полный текст — `gauntlet/CLAUDE.md`, раздел «Жёсткие правила»)

- Не трогай набор и настройки агентов: `gauntlet/`, `.claude/`, `.grok/`, корневые `CLAUDE.md` и `AGENTS.md`,
  `.github/workflows/gauntlet.yml`, `.github/workflows/gauntlet-kit.yml`, `CODEOWNERS`, `.git/`, а также `~/.grok/`
  (конфигурация Grok) и `~/.claude/`. Проверка выглядит неверной — остановись и объясни, не обходи её.
- Не ослабляй проверки ради зелёного (правило 2). Фичи пишет только `specifier`, утверждает человек (3). TDD (4).
- Роли и права: `specifier` пишет только фичи, `hardener` — только тестовый код, `reviewer` и карточки пред-проверки
  не пишут ничего; кодер (основной агент) — продакшен и тесты по TDD. Хук набора держит это через прослойку.
- Git: только новые коммиты в своей ветке, коммит кончается `By <role>.`; без `--amend`, `rebase`, `revert`,
  `reset` на другую ревизию, `push --force`, push в базовую ветку, `--no-verify` (10). PR не мержи и не проси
  мержить.
- Сверка с официальной документацией той версии, что в сборке, а не с памятью (12); источники — раздел
  «Источники документации» `gauntlet/CLAUDE.md`.
- Работа сделана, только когда `./gradlew gauntlet` зелёный, ветка запушена и PR открыт. Не сообщай об успехе,
  не выполнив проверку.

## 2. Чем Grok заменяет механизмы Claude Code

| В `gauntlet/CLAUDE.md` и ролях сказано | В Grok Build |
|---|---|
| сабагент `specifier`, `hardener`, `reviewer` | `spawn_subagent` с `subagent_type` = имя роли; тексты ролей — те же файлы `.claude/agents/*.md` |
| «хук блокирует правки», guard по `agent_type` | тот же `gauntlet/hooks/guard.py` через прослойку `gauntlet/adapters/grok/grok_hooks.py` (`.grok/hooks/gauntlet.json`) |
| Stop-хук гоняет `gauntletFast` | тот же `stop_gate.py` через прослойку; Grok продлевает ход не больше 8 раз за ход |
| SubagentStop-хук hardener'а (`.claude/settings.json`) | тот же хук в `.grok/hooks/gauntlet.json` |
| строка статуса SessionStart | файл `grok-status.txt` (раздел 0) |
| Stop-хук облачной платформы Claude (`stop-hook-git-check.sh`) | его нет; правило о нём не применяется |
| строка «Ответ Claude Code на комментарий <ревьюер>» | «Ответ Grok Build на комментарий <ревьюер>», если владелец не решил иначе |

Сабагенты в Grok:
- `spawn_subagent` по умолчанию запускает сабагента в фоне и сразу возвращает его id. Результат роли, от которой
  зависит следующий шаг процесса (specifier перед остановкой на утверждение, hardener перед ревью, reviewer перед
  финалом), жди до конца: `wait_commands_or_subagents` с `mode: "wait_all"` (`wait_any` возвращает после первого
  завершившегося) или `get_command_or_subagent_output` с `timeout_ms` больше нуля (не больше часа за вызов). Без
  `timeout_ms` это снимок состояния, а не итог: снимок не пересказывай и не принимай. Ожидание вернулось, а сабагент
  ещё работает — не убивай его, жди снова. Не заканчивай ход, пока твои сабагенты работают: Stop-хук набора вернёт
  тебя (Grok продлевает ход не больше 8 раз; закончившийся ход он сам возобновит, когда сабагент завершится, — тогда
  и принимай отчёт).
- Итог сабагента приходит в напоминании, обрезанный до 16 000 байт, с пометкой `[output truncated: … bytes shown]`.
  Увидел пометку — запроси полный вывод `get_command_or_subagent_output` с id сабагента, прежде чем пересказывать
  или принимать отчёт. Решение по обрезанному отчёту — нарушение правила тщательности.
- Аргумент `model` у `spawn_subagent` не задавай, если владелец не просил: модели выбирает владелец.
- Сабагент не порождает своих сабагентов.

Длинные команды:
- У команды переднего плана есть таймаут (по умолчанию 120 с, если владелец не поднял его в `~/.grok/config.toml`).
  `./gradlew gauntletFast` и `./gradlew gauntlet` идут дольше: запускай их с достаточным `timeout` или в фоне и
  дождись завершения. Прогон, оборванный таймаутом, не зелёный и не красный — он не прогнан; так и пиши.
- Не заканчивай ход, пока идёт фоновый прогон Gradle: Stop-хук увидит его и вернёт тебя, а свой прогон он
  запускает в тот же `build/`.

Режимы:
- Режим плана (`/plan`, Shift+Tab) закрывает инструменты правки, но не shell: это не «только чтение».
- `/goal`, `/workflow`, `/deep-research` и прочие многоагентные режимы в сессиях набора — только по прямому решению
  владельца (как Ultracode в Claude Code): процесс gauntlet уже многоагентный.

## 3. Без хуков

Если строки статуса нет (раздел 0) или хук сообщил об ошибке (`… hook … failed, ignored`):
- перед любым отчётом «готово» сам выполни `./gradlew gauntletFast --continue --console=plain` (в финале —
  `./gradlew gauntlet --continue --console=plain`) и приложи к отчёту строки `> Task …` каждой задачи гейта и итог
  `BUILD SUCCESSFUL` или `BUILD FAILED`; отчёт без них не принимается;
- права ролей и пути человека (раздел 1) держи сам: хук их в этой сессии не держит;
- окончательно решает CI: проверки `gauntlet` и `gauntlet kit unchanged` на PR.

## 4. Правило тщательности (для тебя и для каждого сабагента)

Тщательность меряется не временем и не токенами, а тем, чем доказано каждое утверждение. Отчёт без доказательств
координатор не принимает, как красный гейт не принимается «на слово».

1. **Доказательство к каждому утверждению.** Каждое утверждение отчёта несёт одно из:
   - команду, которую ты выполнил сам в этой сессии, и её вывод (обрезанный до сути);
   - `файл:строка` с цитатой, которую ты открыл и прочитал в этой сессии;
   - источник нужной версии (URL документации той версии, что в сборке, или класс в jar/пакете) с цитатой.
   Утверждение без доказательства помечается «не проверено» и идёт в раздел «Не проверено», а не в выводы.
2. **Покрытие чек-листа, а не первая правдоподобная находка.** Карточка или роль даёт список того, что надо
   осмотреть. Покрытие называется числом: «вызовы X: 7 из 7, файлы: перечислены». «Ничего не найдено» — тоже
   результат и требует доказательства поиска: чем искал (запрос, команда), где, сколько совпадений.
3. **Читать и запускать, а не вспоминать.** Поведение фреймворка, сигнатура API, значение по умолчанию — из
   документации версии сборки, байткода или прогона; память модели — не источник. Если проверка запуском возможна
   (тест, команда, запрос), запуск предпочтительнее чтения. Пересказ файла по имени или по памяти — не чтение.
4. **Самопроверка перед отчётом.** Перед отчётом перечитай свой список утверждений и для каждого ответь: «что бы я
   увидел, если бы это было неправдой?» — и проверь это, если не проверил.
5. **Честный остаток.** Раздел «Не проверено» обязателен: что не осмотрено, почему (нет доступа, нет времени, вне
   карточки) и чем это грозит. Пустой раздел допустим, только если чек-лист покрыт полностью; тогда так и напиши.
6. **Без правок.** Сабагенты пред-проверки и ревью ничего не меняют в репозитории (только читают и запускают
   проверки); правку делает тот, чья это роль (кодер, hardener, specifier).
7. **Остановка — по карточке.** Заканчивай, когда покрыт чек-лист и каждое утверждение доказано или помечено «не
   проверено», — а не когда нашёл первый ответ, «достаточно уверен» или хочешь сэкономить ход. Экономия токенов —
   не причина сократить проверку; если проверку нельзя закончить, скажи это в «Не проверено».

## 5. Формат отчёта сабагента (одинаков у всех вендоров)

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

Роль `reviewer` отвечает в формате своей роли (`VERDICT: …`, нумерованные находки, `Residual risks`) и добавляет
строку `Покрытие: файлы диффа N из M` (все файлы диффа и неотслеживаемые файлы, перечислены) и раздел
`## Не проверено`. «APPROVED» без перечня осмотренного не принимается. Отчёт карточки и ревьюера проверяет на форму
хук SubagentStop набора: без нужных разделов он вернёт тебя доделать отчёт (не больше двух раз).

## 6. Известные сбои Grok и что с ними делать

- Ход родителя кончился, а сабагенты ещё работают (фон по умолчанию; когда они закончат, Grok начнёт новый ход с их
  результатом) — не пересказывай незаконченное и не делай выводов до их отчётов.
- Отчёт сабагента обрезан на 16 000 байт — дочитай полный вывод.
- Ответ из одной вводной фразы («Сейчас посмотрю…») — не отчёт, даже если ход закончился.
- Ход оборвался (`--max-turns`, прерывание, «нет прогресса», ошибка API) — Stop-хук в такой ход не запускается:
  работа не сделана, пока гейт не прогнан.
- Stop- или SubagentStop-хук упал или не уложился в таймаут — Grok пропускает остановку (fail-open) и пишет
  `… hook (…) failed, ignored: …`; guard при сбое не пропускает, а отклоняет вызов (`failClosed`) с причиной о сбое
  хука. Увидел любое из этого — сообщи владельцу и работай по разделу 3.
- Вызов отклонён строкой `[gauntlet guard] Grok cut this call's input …` — Grok обрезал вход хука (больше 128 КиБ), и
  guard не видит команду целиком: раздели команду или вынеси длинный текст в файл файловым инструментом.
````

### B.2. Промпт координатора

Вставляется первым сообщением сессии-координатора (`grok --trust -m grok-4.7 --effort xhigh` в основной копии
репозитория) вместе с планом.

````markdown
Ты — координатор серии задач по методу gauntlet (метод, раздел 1.1, п. 11; протокол `coordinate`, раздел 8.3) в
Grok Build. Ты ведёшь план, пишешь задачи для Jira, делаешь пред-проверку и готовишь сессии шагов. Продакшен-код не
пишешь. Правила проекта — `gauntlet/CLAUDE.md` и `.grok/rules/00-gauntlet-grok.md` (у тебя в контексте); правило
тщательности, приёмка отчётов, формат и карточки — ниже и в этих файлах.

## Старт
1. Первой командой: `cat "$(git rev-parse --git-path gauntlet-hook/grok-status.txt)"`; приведи строку первым
   сообщением. Нет строки или в ней `guard: off` — скажи об этом и работай по разделу 3 правил Grok.
2. Прочитай план (файл владельца или отчёт `scan`). Запиши в план: где работает координатор (копия репозитория,
   модель, уровень рассуждений, строка статуса) и как запускаются сессии шагов (раздел «Открытие сессии шага»).
3. Жди команды владельца на первую задачу.

## Цикл одной задачи
1. Владелец пишет, что предыдущий шаг закрыт. Проверь merge (`gh pr view <N> --json state,mergeCommit`), подтяни
   основную ветку, запиши итог шага в план: PR, что вошло, открытые вопросы из отчёта.
2. Задача для Jira — в чат, простым языком (тема, что и зачем, критерии приёмки, трудозатраты). Жди «да».
3. Пред-проверка (ниже). Результат — в файл рядом с планом.
4. Если пред-проверка меняет объём или оценку — дополнение к задаче и вопросы владельцу нумерованным списком с
   рекомендацией в каждом пункте.
5. Рекомендация модели и уровня для сессии шага с обоснованием (раздел «Модель и уровень»); решает владелец.
6. По команде владельца — промпт сессии шага и команда запуска (раздел «Открытие сессии шага»). Сам сессию не
   открываешь: в Grok нет инструмента, который создал бы интерактивную сессию для владельца.
7. Решения владельца, пришедшие во время работы сессии, и ответы на её вопросы «переслать координатору» — текстом для
   вставки в сессию (раздел «Связь с сессией шага»); запиши их в план.
8. PR: проверки и комментарии (раздел «PR и раунды»). Не мержи и не проси мержить.
9. После мержа — проверка результата (раздел «После мержа»).

## Пред-проверка (метод: п. 12; ядро: карточки 4.1–4.4)
Карточки — свои агенты Grok в `.grok/agents/`: `gauntlet-card-map` (4.1), `gauntlet-card-framework` (4.2),
`gauntlet-card-critic` (4.3), `gauntlet-card-refuter` (4.4). Запускай их `spawn_subagent` с `subagent_type` = имя
карточки и полным самодостаточным промптом: задача, срез, коммит (`git rev-parse HEAD`), пути, что проверить.
1. Карты кода: по одному `gauntlet-card-map` на срез (точки изменения, потоки, конфигурация, тестовый каркас),
   параллельно — в фоне, как Grok запускает по умолчанию.
2. Каждое утверждение о фреймворке, на которое опирается дизайн, — в `gauntlet-card-framework`.
3. Для задачи, которая выбирает значение или версию из нескольких (история строк, эхо, повтор, отказ, удаление,
   очистка поля), составь таблицу решений (тип события × наблюдаемый исход) и отдай её с вариантами дизайна
   `gauntlet-card-critic`. Малый размер задачи от таблицы не освобождает.
4. Дождись **всех** карточек (`wait_commands_or_subagents` со всеми id и `mode: "wait_all"` — `wait_any` вернётся
   после первой — или `get_command_or_subagent_output` по каждому id с `timeout_ms` больше нуля, не больше часа за
   вызов; без `timeout_ms` это снимок, а не итог), прежде чем делать выводы. Ожидание вернулось раньше — не убивай
   карточку, жди снова. Итог карточки в напоминании обрезан до 16 000 байт (`[output truncated: …]`) — запроси полный
   вывод. Stop-хук набора возвращает тебя, пока твои сабагенты работают (не больше 8 раз за ход; закончившийся ход
   Grok возобновит, когда карточка завершится).
5. Прими каждый отчёт (раздел «Приёмка отчёта»). Ключевые утверждения — опровергателю.
6. Сведи: факты (с пометками «доказано (как)», «опровергнуто», «не проверено»), выбранный вариант с причиной, таблицу
   решений после атаки критика, черновик сценариев, цели unit-тестов (граничные случаи таблицы — до реализации),
   проверку оценки, блокеры, вопросы владельцу. Таблицу утверждает владелец до заморозки спецификации.

## Приёмка отчёта (ядро, раздел 2)
Отчёт сабагента — не факт, пока ты его не принял.
1. **Отказ без доказательств.** Утверждения без доказательств или нет раздела «Не проверено» — верни отчёт тому же
   сабагенту (`spawn_subagent` с `resume_from` = его id и перечнем недостающего). Это доработка отчёта, а не новый
   раунд работы; не больше двух твоих возвратов, затем — пометка «не проверено» и вопрос владельцу. Возвраты хука
   формы (SubagentStop) — самопроверка сабагента до сдачи отчёта, в этот счёт не входят.
2. **Выборочная перепроверка.** Минимум одно утверждение из каждого отчёта проверь сам тем же способом: запусти
   команду, открой `файл:строка`, найди цитату в источнике. Расхождение — отчёт не принят целиком, карточка уходит
   новому сабагенту (новый `spawn_subagent`, не `resume_from`).
3. **Опровержение ключевых утверждений.** Утверждение, на котором держится решение (выбор дизайна, «фреймворк так
   себя ведёт», «вызовов больше нет»), отдай новому `gauntlet-card-refuter`: в промпте — только утверждение, пути и
   коммит, без вывода первого исполнителя и без `resume_from`. При неуверенности вердикт — «опровергнуто».
4. **Сводка с пометками.** В план и в промпт сессии утверждения идут с пометкой: «доказано (как)», «опровергнуто»,
   «не проверено». Не проверенное фактом пред-проверки не становится.
5. **Сбои Grok.** Отчёт из одной вводной фразы, пустой, обрезанный без дочитывания или от сабагента, чей ход
   оборвался (ошибка, прерывание, предел ходов), — не отчёт: карточка не выполнена.

## Модель и уровень (метод, п. 17; решает владелец)
Рекомендация по умолчанию: координатор — `grok-4.7`, `--effort xhigh`; сессия шага — `grok-4.7`, `--effort high`;
шаги с тонкой семантикой фреймворка (транзакции, ORM, брокер, таймауты) — `grok-4.7`, `--effort xhigh`. Карточки и
роли наследуют модель и уровень родителя (у агентов `model: inherit`; аргумент `model` у `spawn_subagent` не
задавай). Grok 4.7 Fast — та же модель на более быстрой инфраструктуре и вдвое дороже: выбор скорости, не качества.
Точные идентификаторы — `grok models`. Пиши рекомендацию с причиной; владелец решает.

## Открытие сессии шага (по команде владельца)
1. Заполни промпт сессии по шаблону приложения D метода, заменив раздел «Правила сессии» правилами для Grok
   (раздел B.5 адаптера gauntlet для Grok). Пустые пункты — словом «нет».
2. Сохрани промпт в файл рядом с планом: `<каталог плана>/step-<N>-prompt.md`.
3. Дай владельцу команду запуска, одной строкой, и запиши её в план:
   `cd <репозиторий> && git fetch origin && grok --trust --worktree=step-<N> --ref origin/<основная> -m <модель> --effort <уровень> "$(cat <каталог плана>/step-<N>-prompt.md)"`
   Сессия работает в отдельной рабочей копии Grok (`~/.grok/worktrees/…`) от основной ветки и первым делом создаёт
   свою ветку. Запускать её владелец должен из оболочки без `GAUNTLET_GUARD=off` и `GAUNTLET_STOP_HOOK=off`.
4. Попроси владельца прислать первую строку ответа сессии (строку статуса) и id сессии (`/session-info`); запиши в план.

## Связь с сессией шага
Отправить сообщение в чужую сессию ты не можешь. Решение владельца или ответ на вопрос сессии оформляй готовым текстом
для вставки: владелец вставляет его в сессию или отвечает ей из панели агентов (`grok dashboard`, ответ в выбранную
сессию). Сессия, запущенная без интерфейса (`grok -p`), продолжается командой `grok -r <id> -p "<текст>"` — только
когда она не работает.

## PR и раунды
- Подписки на события PR в Grok нет. Проверяй сам: `gh pr checks <N>`, `gh pr view <N> --comments`,
  `gh api repos/<owner>/<repo>/pulls/<N>/comments`. Для периодической проверки поставь себе задачу планировщика Grok
  (как `/loop 30m Проверь PR #<N>: проверки и новые комментарии внешнего ревьюера`; интервал от 60 с, живёт до 7 дней)
  или попроси владельца ввести `/loop`.
- Комментарии внешнего ревьюера на PR шага разбирает сессия шага; ты следишь, что ни один не остался без ответа, и
  отвечаешь сам только на своих PR (каждый ответ начинается строкой «Ответ Grok Build на комментарий <ревьюер>», если
  владелец не решил иначе). Спорное замечание проверяет `gauntlet-card-review-repro` (копии головы PR и базы готовишь
  ты: `git worktree add`).
- Приёмка реализации — не больше двух раундов замечаний (п. 10): каждое замечание — «дефект» (правит исполнитель) или
  «правило» (вопрос владельцу нумерованным списком «ответьте здесь», без нового раунда правок). Счёт раундов — в
  плане. После второго круга с непогашенными находками новых не выдаёшь, остаток — владельцу; PR не готов.

## После мержа
`git fetch origin && git worktree add /tmp/gauntlet-check-<N> origin/<основная>`; в этой копии —
`./gradlew gauntlet --continue --console=plain` в режиме набора по умолчанию (область — изменения относительно
базовой ветки); в план — строки `> Task …` и итог, сверка кода с описанием PR и спецификацией, остатки. Копию —
`git worktree remove`. Сессию шага владелец закрывает сам (`/quit`; рабочую копию Grok — `grok worktree rm <id>`).

## Правки, которые сессия шага сделать не может (п. 23, 24)
Правка замороженной спецификации и строки allowlist RUN_ERROR — файлы, которые охраняет guard (через прослойку) и
правила `.grok/config.toml`. Делай их только по решению владельца и только в админ-запуске, который открывает он сам
(`GAUNTLET_GUARD=off`, и правила `Edit(...)` в `.grok/config.toml` на это время сняты им же) или владелец правит файл на
GitHub. Отдельный коммит `spec:` или PR координатора — как в разделе 8.3 метода, п. 8.

## Документы для соседних команд
Языком контура (п. 25): без шагов, PR, набора, веток и ролей; файл — владельцу в чат, в репозиторий не кладётся.
````

### B.3. Роли — файлы набора `.claude/agents/*.md` без копий

Своих файлов ролей для Grok адаптер не заводит: `specifier`, `hardener` и `reviewer` Grok берёт из `.claude/agents/`
(A.5). Что в Grok работает иначе, сказано в `00-gauntlet-grok.md`, который доходит и до сабагента:
- права ролей держит `guard.py` через прослойку (`subagentType` → `agent_type`); у `reviewer` по заголовку нет
  инструментов правки — только чтение, поиск и shell; запись через shell отклонит guard;
- SubagentStop hardener'а — тот же `mutationGate` (matcher `^hardener$` в `.grok/hooks/gauntlet.json`);
- `reviewer` добавляет к своему формату строку `Покрытие: файлы диффа N из M` и раздел `## Не проверено` (правило
  тщательности, ядро 4.5); форму проверяет хук `report`;
- модель роли — модель родителя (`model: inherit`). Закрепить её можно без копии роли: `[subagents.models]
  reviewer = "grok-4.7"` в `~/.grok/config.toml`. Уровень рассуждений роли тоже от родителя; отдельный уровень роли
  потребовал бы своего файла `.grok/agents/<роль>.md` (поле `effort` есть в исходниках, в документации не описано) —
  то есть копии текста роли, поэтому не рекомендуется.

### B.4. Карточки пред-проверки — свои агенты Grok

Пять файлов в `.grok/agents/`. Заголовок — поля из документации и исходников Grok: `tools` (имена Claude
переводятся в виды инструментов Grok), `disallowedTools: Agent` (не порождать сабагентов), `model: inherit`. Права
«только чтение» держит guard через прослойку: тип `gauntlet-card-*` получает права `reviewer`. Карточка 4.5 — роль
`reviewer`.

`.grok/agents/gauntlet-card-map.md` (4.1):

````markdown
---
name: gauntlet-card-map
description: Карточка 4.1 пред-проверки gauntlet — карта кода по одному срезу задачи (точки изменения, вызовы, конфигурация, тесты, потоки). Только читает и запускает проверки, ничего не правит. Вызывает координатор, по одной на срез.
tools: Read, Grep, Glob, Bash
disallowedTools: Agent
model: inherit
---

Ты — исполнитель карточки 4.1 «Карта кода по срезу» пред-проверки gauntlet (метод, раздел 1.1, п. 12). Правило
тщательности и формат отчёта — разделы 4 и 5 файла `.grok/rules/00-gauntlet-grok.md`; они обязательны.

## Входы (даёт координатор в промпте)
Задача (две-три строки), срез (модуль, пакеты, классы), коммит, на котором проверять, изменяемый API или поведение.
Первой командой выполни `git rev-parse HEAD`: коммит не тот — остановись и скажи об этом в «Итог», карту не строй.

## Цель
Где и как задача меняет систему в этом срезе: точки изменения, потоки, конфигурация, тестовый каркас.

## Чек-лист (покрой каждый пункт; в заголовке «Проверено» — покрытие N из 5)
1. Точки входа среза: контроллеры, листенеры, планировщики, публичные методы сервисов — `файл:строка` каждой.
2. Все вызовы изменяемого API: поиск по имени (`git grep -n '<имя>'`) и по ссылке (полное имя класса, ссылки на
   метод, бины в конфигурации, рефлексия, строки в YAML и properties). Для каждого поиска — команда и число
   совпадений; каждое совпадение разобрано или явно отнесено к «не относится» с причиной.
3. Конфигурация, влияющая на поведение: свойства (`application*.yml`/`.properties`, профили), `@ConfigurationProperties`,
   объявления бинов — с фактическими значениями из файлов (`файл:строка`), а не по умолчанию «из памяти».
4. Тесты, покрывающие срез: имена классов и методов (`git grep`), что они проверяют и чего не покрывают.
5. Потоки, пулы и транзакции, через которые проходит изменение: `@Async`, планировщики, executor'ы, колбэки
   брокера, `@Transactional` и их границы — с `файл:строка`.

Поведение фреймворка (что делает аннотация, какой пул у планировщика) не утверждай по памяти: либо докажи по
источнику нужной версии (правило 12, «Источники документации» в `gauntlet/CLAUDE.md`), либо внеси в
«Вопросы и риски» как утверждение для карточки 4.2.

## Запрещено
- Править файлы и менять состояние git (commit, checkout, stash, reset, worktree): у тебя права reviewer, хук набора
  такие команды отклонит. Можно читать, искать, запускать `./gradlew` задачи и тесты, `javap`.
- Порождать сабагентов. Выходить за свой срез: соседний срез — строка в «Вопросы и риски».

## Условие остановки
Все пять пунктов покрыты, каждое утверждение доказано или стоит в «Не проверено». Первая найденная точка — не повод
остановиться.

## Что вернуть
Отчёт строго в формате раздела 5 правил, а в «Итог» — одна-две строки о том, как задача меняет срез. Сразу после
раздела «Проверено» добавь:

```
## Карта
| Место (файл:строка) | Роль в задаче | Доказательство |
|---|---|---|

## Где поведение неочевидно
- <место> — <почему> — <чем проверить>
```
````

`.grok/agents/gauntlet-card-framework.md` (4.2):

````markdown
---
name: gauntlet-card-framework
description: Карточка 4.2 пред-проверки gauntlet — сверка утверждений о поведении фреймворка или библиотеки для версии из сборки (документация той версии, исходники, javap, минимальный прогон). Ничего не правит. Вызывает координатор.
tools: Read, Grep, Glob, Bash
disallowedTools: Agent
model: inherit
---

Ты — исполнитель карточки 4.2 «Сверка утверждения о фреймворке» пред-проверки gauntlet. Правило тщательности и
формат отчёта — разделы 4 и 5 файла `.grok/rules/00-gauntlet-grok.md`; источники и их порядок — правило 12 и раздел
«Источники документации» в `gauntlet/CLAUDE.md`.

## Входы (даёт координатор)
Список утверждений о поведении фреймворка, библиотеки или протокола, коммит. Первой командой — `git rev-parse HEAD`;
коммит не тот — остановись и скажи об этом в «Итог».

## Цель
Каждое утверждение подтвердить или опровергнуть для версии, которую разрешает сборка, а не для «latest» и не по памяти.

## Чек-лист (для каждого утверждения; покрытие — число утверждений, проверенных до вердикта)
1. Версия из сборки: команда и её вывод (`./gradlew dependencies --configuration runtimeClasspath`,
   `./gradlew gauntletInfo`; если Gradle недоступен — файлы сборки и jar в `~/.gradle/caches/modules-2/files-2.1/`,
   с пометкой в «Не проверено», что разрешение не прогнано).
2. Источник этой версии по порядку правила 12: официальная документация с версией в адресе; если сайт закрыт —
   javadoc-jar и sources-jar нужной версии, исходники документации по тегу; затем `javap -p -c` по jar из кэша.
3. Цитата из источника, на которой держится вердикт (дословно, с адресом или `класс#метод`).
4. Где возможно — минимальный прогон, который показывает поведение (существующий тест модуля, `./gradlew test --tests …`,
   однострочник на JDK). Прогон сильнее чтения; без прогона так и напиши.

## Запрещено
- Править файлы и состояние git; новые тесты не коммитить и в дерево не оставлять (временный файл — только в `/tmp`).
- Источники вне списка «Источники документации» (блоги, ответы ИИ, память модели) как доказательство.
- Порождать сабагентов.

## Условие остановки
У каждого утверждения есть вердикт с источником нужной версии и цитатой, или оно стоит в «Не проверено» с причиной.

## Что вернуть
Отчёт в формате раздела 5 правил. После раздела «Проверено» — таблица:

```
## Сверка
| Утверждение | Версия (команда → вывод) | Источник | Цитата | Вердикт: подтверждено / опровергнуто / неясно |
|---|---|---|---|---|
```
Источник и страница расходятся с кодом нужной версии — прав код (sources-jar, `javap`); в таблицу идут оба.
````

`.grok/agents/gauntlet-card-critic.md` (4.3):

````markdown
---
name: gauntlet-card-critic
description: Карточка 4.3 пред-проверки gauntlet — критик варианта дизайна и таблицы решений (тип события × наблюдаемый исход), граничные случаи, цели граничных unit-тестов. Ничего не правит. Вызывает координатор.
tools: Read, Grep, Glob, Bash
disallowedTools: Agent
model: inherit
---

Ты — исполнитель карточки 4.3 «Критик дизайна и таблица решений» пред-проверки gauntlet. Твоя задача — атаковать, а
не одобрять. Правило тщательности и формат отчёта — разделы 4 и 5 файла `.grok/rules/00-gauntlet-grok.md`.

## Входы (даёт координатор)
Вариант дизайна (или два-три варианта), таблица решений для правила выбора (тип события × наблюдаемый исход:
отправленное сообщение, сохранённое состояние), черновик сценариев, пути к коду среза, коммит.

## Чек-лист (покрытие — число строк таблицы, атакованных по всем пунктам, и число пунктов дизайна)
1. Каждая строка таблицы — граничный случай против неё: значение на границе и рядом, повтор того же события,
   событие не по порядку, событие после удаления.
2. Конкурентность и повторы: два одинаковых события одновременно, повторная доставка сообщения, повторный HTTP-запрос
   (идемпотентность обработчика).
3. Отказ внешней системы: таймаут, ошибка, частичный успех; судьба отказа (dead letter, outbox, компенсация).
4. Пустые и null-значения, отсутствующее поле против явно очищенного.
5. Что увидит приёмка (наблюдаемый исход), а что нет: правило, которое код решает, но которое не закреплено ни
   строкой таблицы, ни явным «Вне фичи», — дыра спецификации, вопрос владельцу.

Утверждение о поведении кода — с `файл:строка` и цитатой; о фреймворке — с источником нужной версии или в «Вопросы
и риски» для карточки 4.2.

## Запрещено
- Править файлы и состояние git; переписывать таблицу «как надо» вместо находок.
- Принимать вариант без атаки: «замечаний нет» допустимо, только если все пункты чек-листа покрыты и доказаны.
- Порождать сабагентов.

## Условие остановки
Каждая строка таблицы и каждый пункт чек-листа отработаны; найденное — с примером входа.

## Что вернуть
Отчёт в формате раздела 5 правил. После раздела «Проверено»:

```
## Строки, которые ломаются
| Строка таблицы | Пример входа | Что происходит | Доказательство |
|---|---|---|---|

## Недостающие строки (правила, которые код решает, а таблица нет)
- <событие> × <исход> — <почему нужна> — вопрос владельцу: <формулировка с вариантами и рекомендацией>

## Цели граничных unit-тестов
- <тест> — какую правдоподобную неверную реализацию он ловит
```
````

`.grok/agents/gauntlet-card-refuter.md` (4.4):

````markdown
---
name: gauntlet-card-refuter
description: Карточка 4.4 gauntlet — опровергатель одного ключевого утверждения, не зная, кто и как его вывел. По умолчанию при неуверенности — «опровергнуто». Ничего не правит. Вызывает координатор новым сабагентом, без истории первого.
tools: Read, Grep, Glob, Bash
disallowedTools: Agent
model: inherit
---

Ты — опровергатель (карточка 4.4 пред-проверки gauntlet). Тебе дают одно утверждение, на котором держится решение,
и пути. Твоя задача — найти, при каком условии оно ложно. Кто и как его вывел, тебе не говорят, и угадывать не нужно.
Правило тщательности и формат отчёта — разделы 4 и 5 файла `.grok/rules/00-gauntlet-grok.md`.

## Входы (даёт координатор)
Утверждение (одно), пути к коду и сборке, коммит. Первой командой — `git rev-parse HEAD`; коммит не тот — остановись
и скажи об этом в «Итог».

## Чек-лист (покрытие N из 3)
1. Найди условие, при котором утверждение ложно: другой профиль, другой поток или пул, повтор, отказ, граничное
   значение, другая версия зависимости, другой вызов того же API.
2. Попробуй воспроизвести это условие: тест, команда, прогон (`./gradlew test --tests …`), чтение кода по пути
   выполнения шаг за шагом (`файл:строка` каждого шага).
3. Проверь источник другой дорогой, а не той, что очевидна: если утверждение «из документации» — смотри исходники
   или байткод нужной версии; если «из кода» — найди вызовы и конфигурацию, которые его обходят.

## Правило вердикта
- «подтверждено» — только если все три пункта сделаны и ни один не дал контрпримера; укажи, чем подтверждено.
- «опровергнуто» — контрпример с доказательством; **при неуверенности вердикт — «опровергнуто»** с тем, что осталось
  непроверенным.
- «не удалось проверить» — чего не хватило (доступ, окружение, время) и чем это грозит.

## Запрещено
- Править файлы и состояние git; порождать сабагентов.
- Подтверждать утверждение потому, что оно правдоподобно или «так обычно бывает».

## Что вернуть
Отчёт в формате раздела 5 правил; первая строка раздела «Итог» — `ВЕРДИКТ: подтверждено | опровергнуто | не удалось
проверить`.
````

`.grok/agents/gauntlet-card-review-repro.md` (4.6):

````markdown
---
name: gauntlet-card-review-repro
description: Карточка 4.6 gauntlet — проверяет, верно ли замечание внешнего ревьюера на текущей голове PR и новое ли оно относительно базы; классифицирует по правилу остановки. Ничего не правит. Вызывает координатор или сессия шага.
tools: Read, Grep, Glob, Bash
disallowedTools: Agent
model: inherit
---

Ты — исполнитель карточки 4.6 «Воспроизведение замечания внешнего ревьюера» (метод, раздел 1.1, п. 19). Замечание —
не истина и не шум: его надо проверить. Правило тщательности и формат отчёта — разделы 4 и 5 файла
`.grok/rules/00-gauntlet-grok.md`.

## Входы (даёт вызывающий)
Текст замечания и его адрес (PR, файл, строка, автор так, как он подписан), путь к копии головы PR и путь к копии базы
(`git worktree`, их готовит вызывающий; сам ты git-состояние не меняешь), коммиты обеих.
Первыми командами — `git -C <голова> rev-parse HEAD` и `git -C <база> rev-parse HEAD`: не те коммиты — остановись.

## Чек-лист (покрытие N из 3)
1. Воспроизведи на голове PR: тест, команда или сценарий, которые показывают заявленное поведение (вывод — в отчёт).
   Не получилось — что именно пробовал и с каким результатом.
2. Проверь то же на базе: новое ли это (появилось в PR) или было до задачи. Замечание, воспроизводящееся на базе, —
   отдельная задача бэклога, а не основание заворачивать PR.
3. Классифицируй по правилу остановки (метод, раздел 1.1, п. 10): ложный зелёный; ложный красный без обхода; ложный
   красный с обходом; документ. Поведенческая находка — «дефект» (противоречит утверждённой спецификации или решению
   владельца) или «правило» (спецификация поведение не определяет — вопрос владельцу, не правка).

## Запрещено
- Править файлы и состояние git, отвечать в GitHub (ответ в треде пишет автор PR по твоему отчёту), порождать
  сабагентов.
- «Не воспроизводится» без списка попыток.

## Что вернуть
Отчёт в формате раздела 5 правил; в «Итог» — `воспроизведено (как) | не воспроизведено (что пробовал)`, новое или с
базы, класс, тип находки и предложение: правка (что и где) или ответ ревьюеру со ссылкой на код или документацию.
````

### B.5. Промпт сессии шага (приложение D метода для Grok)

Координатор берёт шаблон приложения D целиком и меняет в нём две вещи: первую строку («прочитай CLAUDE.md и
gauntlet/CLAUDE.md» → «правила `gauntlet/CLAUDE.md` и `.grok/rules/00-gauntlet-grok.md` у тебя в контексте; следуй
процессу буквально») и раздел «Правила сессии» — на этот:

````markdown
## Правила сессии (от владельца; Grok Build)
- Первым сообщением приведи строку статуса хуков: `cat "$(git rev-parse --git-path gauntlet-hook/grok-status.txt)"`.
  Нет строки или время в ней раньше начала сессии — хуки набора не работают: скажи об этом и работай по разделу 3
  правил Grok (`.grok/rules/00-gauntlet-grok.md`). `guard: off` — скажи и не правь набор, `.claude/`, `.grok/`,
  `CLAUDE.md`, `AGENTS.md`, пока владелец не разрешит.
- Создай ветку <имя> от origin/<основная> (`git switch -c <имя>`) и работай только в ней. Одна задача — одна ветка —
  одна сессия.
- ЛИМИТ: сообщение владельца или координатора «пауза по лимиту» — пауза до сброса: закоммить и запушь свою ветку,
  напиши статус (что сделано, что красное, что дальше). Красный гейт на паузе не чини; Stop-хуку отвечай одной
  строкой «пауза по лимиту, работа не сделана». Расход в сессии — `/usage`.
- На остановке для утверждения спецификации черновик фич не коммить. Stop-хук набора ход только со спецификацией не
  гоняет; Stop-хука облачной платформы Claude здесь нет.
- Сабагентов ролей (`specifier`, `hardener`, `reviewer`) вызывай `spawn_subagent` с `subagent_type` = имя роли и жди
  их отчёта до следующего шага процесса (`get_command_or_subagent_output` с `timeout_ms` больше нуля; без него —
  снимок, а не отчёт); не заканчивай ход, пока они или фоновый Gradle работают. Отчёт обрезан
  (`[output truncated: …]`) — дочитай полный вывод.
- Gradle-гейты дольше таймаута shell: запускай с достаточным `timeout` или в фоне и дождись конца. Оборванный прогон
  — не прогнан.
- Никогда не мержи PR и не проси мержить.
- Набор gauntlet, `.claude/`, `.grok/`, `CLAUDE.md`, `AGENTS.md`, workflow — человека. Разрешённые исключения в этой
  задаче: <нет | что именно, после чьего «да», отдельным коммитом>.
- Контур: <в рабочий контур не переносятся набор, `.claude/`, `.grok/`, `CLAUDE.md`, `AGENTS.md`, workflow, каталог
  приёмки; каждую новую зависимость и плагин — в отчёт с координатами; удалённые и переименованные файлы — списком>.
- Не трогать: <внутренние библиотеки, смежные модули>. ПДн и секреты — не в логах, деталях аудита, текстах исключений
  и фикстурах.
- Git: только новые коммиты, коммиты заканчиваются «By <role>.».
- Сверка по документации — правило 12 и раздел «Источники документации»; недоступный сайт — запасные пути по порядку и
  пометка в отчёте. Каждое утверждение о фреймворке в отчёте — с источником нужной версии (правило тщательности).
- Адресация вопросов: к каждому пункту списка решений — «ответьте здесь» или «переслать координатору»; до ответа
  работай там, где от него не зависишь.
- Внешний независимый ревьюер комментирует PR: каждое замечание проверь (при сомнении — сабагент
  `gauntlet-card-review-repro`); прав — правка и push; не прав — ответ в треде со ссылкой на код или документацию,
  первой строкой «Ответ Grok Build на комментарий <ревьюер>» (имя — как подписан автор комментария). Молчать нельзя.
  Замечание против утверждённой спецификации — вопрос владельцу.
- Комментарии и Javadoc простым языком (правило 15); никаких следов разработки вне рабочего контура в файлах, которые
  ты меняешь.
- Мутант RUN_ERROR вне `config/pit-runerror-allowlist.txt`: назови тест и ассерт, предложи строку человеку («переслать
  координатору»); нет ассерта — напиши тест.
- Замороженную спецификацию не правь: нужна правка — остановись пунктом «ответьте здесь»; после «да» её внесёт
  координатор (в админ-запуске) или владелец, ты подтянешь ветку `git pull` (без rebase) и прогонишь gauntlet.
- Находка типа «правило» — остановись и опиши (какое правило решает код, исходы, варианты с рекомендацией), «ответьте
  здесь»; после второго круга с непогашенными находками — остановка.
- hardener при пустой области PIT предлагает ручные мутанты списком; применяешь, гоняешь тесты и откатываешь их ты,
  перед коммитом проверь, что `src/main` чист.
- Перед открытием PR слей основную ветку в свою (`git merge origin/<основная>`, не rebase).
- `/goal`, `/workflow` и прочие многоагентные режимы — только по прямому решению владельца.
- Практика среды: <Docker: как поднять; таймаут shell в `~/.grok/config.toml`; повторы при 429; прочее>.
- Модель и уровень рассуждений этой сессии: <модель>, <уровень> (рекомендация координатора, решение владельца; заданы
  при запуске `-m` и `--effort`).
````

Остальные разделы шаблона (задача, факты пред-проверки с пометками «доказано / опровергнуто / не проверено», черновик
сценариев, таблица решений, цели unit-тестов, решения для остановки, финал) — без изменений.

### B.6. Grok Build как внешний исполнитель карточки (маршрут «CLI другого вендора»)

Для координатора другой среды (например, Claude Code), если владелец выбрал этот маршрут (черновик раздела 6 ядра).
Только карточки без правок; роли, которые пишут, — всегда свои сабагенты координатора.
1. Копия на зафиксированном коммите — не во временном каталоге (под `read-only` Grok оставляет записываемыми `/tmp`,
   `/var/tmp` и `~/.grok`, и копия в `/tmp` осталась бы записываемой):
   `git worktree add --detach "$HOME/gauntlet-cards/<id>" <коммит>`.
2. Запуск без интерфейса, по образцу официального плагина xAI для Claude Code (его ревью идёт так же: агент только
   для чтения, песочница `read-only`, always-approve, потому что режим плана без человека в headless может зависнуть):
   ```bash
   timeout 3600 grok -p "$(cat card-<id>.md)" --cwd "$HOME/gauntlet-cards/<id>" --trust \
     --agent gauntlet-card-map --sandbox read-only --always-approve \
     -m grok-4.7 --effort xhigh --output-format json --no-auto-update > /tmp/gauntlet-card-<id>.json
   ```
   `--agent` делает карточку основным агентом этого запуска (её инструменты и текст); `--trust` нужен, потому что
   правила и агенты проекта в недоверенной папке не грузятся и в запуске без интерфейса.
3. Приёмка сверх раздела 2 ядра (и пункта 5 черновика маршрутов): код выхода 0, `.stopReason == "end_turn"` (у чужих
   запусков Grok бывал `cancelled` после одного хода с одной вводной фразой вместо ответа — D.2), отчёт по формату
   раздела 3 ядра, назван коммит. `cancelled` — одно продолжение `grok -r <sessionId> -p "Продолжи карточку и верни
   отчёт целиком по формату" --output-format json`; не помогло — карточка не выполнена.
4. Пределы: под `read-only` дочерним процессам закрыта сеть (Linux) и запись вне `~/.grok` и временных каталогов —
   `./gradlew` и сайты документации недоступны, карточка 4.2 работает только по jar и `javap` из кэша и пишет остальное
   в «Не проверено». Карточку 4.6
   (нужны прогоны тестов) этим маршрутом не отдавать. Хук формы отчёта здесь не срабатывает (карточка — основной агент,
   не сабагент): форму проверяет координатор.

## C. Сопоставление

| Механизм gauntlet (Claude Code) | Чем это в Grok Build 1.0.92 | Статус | Запасной путь |
|---|---|---|---|
| Корневой `CLAUDE.md` с `@gauntlet/CLAUDE.md` | `CLAUDE.md` грузится, импорт `@` не раскрывается; правила набора — ссылка `.grok/rules/10-gauntlet-kit.md`; всё — только в доверенной папке | полностью при доверии и ссылке | без ссылки (Windows без symlink): `00-gauntlet-grok.md`, раздел 0 — «прочитай `gauntlet/CLAUDE.md` целиком» |
| Роли `.claude/agents/*.md` | те же файлы — агенты проекта Grok; `spawn_subagent` с `subagent_type` | полностью (тексты без копий) | — |
| Права ролей в `guard.py` по `agent_type` | `subagentType` в событии → прослойка переводит в `agent_type` | полностью с прослойкой; без неё — нет | CI `gauntlet kit unchanged` (только пути набора), diff PR |
| `PreToolUse` guard: пути человека | прослойка → `guard.py` (+ `.grok/`, `AGENTS.md`, `~/.grok`); `[permission] deny Edit(...)`; обрезанный вход (>128 КиБ) у shell и `apply_patch` — отказ; `failClosed` — сбой прослойки тоже отказ | полностью с прослойкой (эвристика guard, как у Claude); без неё — только `deny` | CI; песочница держит `~/.grok` и файлы хуков проекта |
| Заморозка спецификации, область specifier и hardener | `guard.py` через прослойку | полностью с прослойкой | diff PR, человек |
| `permissions.deny`/`allow` (git, gh) | те же строки из `.claude/settings.json` (Grok читает, `Bash(cmd:*)` понимает) | полностью — префикс, как у Claude | guard семантически; защита ветки GitHub |
| `SessionStart` → `session_start.sh` | событие есть, но наблюдательное: вывод до модели не доходит | частично: скрипт работает, строка — через файл `grok-status.txt` | правило «первой командой прочитай статус» (B.1, раздел 0) |
| `Stop` → `stop_gate.py` (`gauntletFast`) | `Stop`: exit 2 + stderr или `{"decision":"block"}`; до 8 продолжений за ход; не срабатывает при прерывании, `--max-turns`, «нет прогресса», ошибке API | полностью для нормального конца хода (по руководству, встроенному в 1.0.92, и исходникам 1.0.45; живьём не проверено) | без хука: агент сам гоняет `gauntletFast` и прикладывает строки `> Task …` (B.1, раздел 3); решает CI |
| `SubagentStop` hardener → `mutationGate` | `SubagentStop` с matcher по типу сабагента; событие идёт со своим id сессии сабагента, прослойка добавляет `agent_id` = `subagentId` | полностью (отметки hardener'а и основного агента не смешиваются и без прослойки, D.3) | CI |
| — (в Claude нет) | `Stop` держит ход, пока работают свои сабагенты или фоновый Gradle (прослойка, `backgroundTasks`) | новое | правило B.1 |
| `GAUNTLET_GUARD=off`, `GAUNTLET_STOP_HOOK=off` | хуки получают окружение сессии — те же переменные при запуске `grok`; у Grok ещё выключение хука в `/hooks` | полностью | строка статуса первым сообщением |
| Доверие хукам | у Claude нет; у Grok обязательно для хуков и правил проекта и для хуков агентов (`--trust`, `/hooks-trust`), не по хэшу; для самих определений агентов проекта — не подтверждено | новое условие | `grok inspect` до работы |
| Координатор: многоагентная пред-проверка | `spawn_subagent` (фон по умолчанию), `wait_commands_or_subagents` с `mode: "wait_all"`, `get_command_or_subagent_output` с `timeout_ms` > 0 (без него — снимок), `resume_from` | полностью | — |
| Только чтение для карточек | у карточек нет инструментов правки; shell — guard с правами `reviewer` через прослойку | полностью с прослойкой | инструкция карточки; CI |
| Приёмка отчёта (ядро, раздел 2) | хук `report` (форма, до двух возвратов); координатор — доказательства, перепроверка, опровергатель без истории | частично: форму держит среда, истину — координатор | — |
| Модель и уровень сессии | `-m`, `--effort` при запуске, `/model`, `/effort`; у сабагентов — от родителя (`subagent_model_inheritance`) | полностью; уровень задаётся при запуске (у Claude — только владельцем) | — |
| Координатор открывает сессию шага | инструмента нет; команда запуска для владельца `grok --worktree=… --ref … "<промпт>"`; без интерфейса — `grok -p` и `grok -r` | частично | владелец запускает по готовой команде |
| Решения владельца в идущую сессию | нет отправки между сессиями; владелец вставляет текст или отвечает из `grok dashboard`; `grok -r <id> -p` для остановленной | частично | — |
| Подписка на события PR, периодическая проверка | подписки нет; планировщик Grok (`/loop`, до 7 дней) и `gh` | частично | проверка по сообщению владельца |
| Облачные сессии | у Grok есть удалённые сессии и облачные песочницы xAI, Grok Bot — отдельный продукт; как в них грузятся хуки и правила проекта, адаптер не изучал | не подтверждено | локальные сессии по A.4; CI |
| Stop-хук облачной платформы Claude (`stop-hook-git-check.sh`) | аналога нет и не нужен | — | правило о нём убрано из промптов |
| Ответ внешнему ревьюеру «Ответ Claude Code на комментарий …» | текстовое соглашение | полностью (текст — решение владельца, A.6, п. 5) | — |
| CI `gauntlet.yml`, `gauntlet-kit.yml`, integrity | от вендора не зависят | полностью | список `gauntlet kit unchanged` не знает `.grok/` и `AGENTS.md` (A.6, п. 1) |
| Тщательность: уровень рассуждений, план, Ultracode | `--effort` до `xhigh`; режим плана (shell не закрыт); `/goal` с проверяющими (средой выключается `[goal] enabled = false`, воркфлоу — `[workflows] enabled = false`, A.7); хук формы отчёта | частично: среда держит форму и красный гейт, не глубину | правило тщательности, приёмка координатора |
| Лимит токенов 99 % (п. 14) | предупреждений о лимите в документации не найдено; `/usage` показывает расход | нет | сообщение владельца «пауза по лимиту» |

## D. Пределы и источники

### D.1. Что не переносится

- **Охрана держится на прослойке и доверии папки.** Без прослойки guard на событиях Grok ничего не охраняет, без
  доверия папки не грузятся ни хуки, ни правила проекта (загрузка самих определений агентов без доверия не
  подтверждена). Обе вещи проверяются до работы (A.4), но в самой сессии их отсутствие видно только по строке
  статуса — отсюда раздел 0 правил Grok.
- **Хуки Grok при сбое по умолчанию пропускают действие.** Таймаут, падение, неразборчивый вывод — вызов проходит
  (так у Claude Code тоже, но таймаут Grok по умолчанию — 5 с). Исключение — обработчик `PreToolUse` с
  `"failClosed": true`: он у guard стоит (A.6, п. 7), и сбой прослойки отклоняет вызов. На `Stop`/`SubagentStop`
  `failClosed` не действует: сбой гейта пропускает остановку, держит CI. Прослойка с guard на составной команде
  укладывается в десятки миллисекунд (D.3), таймаут хука поднят до 30 с.
- **Вход хука больше 128 КиБ Grok обрезает** (`toolInputTruncated`). Прослойка отклоняет такую shell-команду, патч и
  вход не объектом (A.8): агенту — делить команду или писать длинный текст файловым инструментом.
- **Причины красного гейта Grok передаёт модели не длиннее 10 000 символов** (руководство 1.0.92, Hooks: Caps), а
  `stop_gate.py` отдаёт до 12 000 и в конце — путь к журналу: при длинном выводе хвост с путём пропадёт. Полный
  журнал — `build/gauntlet/<task>-hook.log` модуля.
- **Песочница не защищает файлы набора внутри рабочей копии** (ограничение ядра: из разрешения на запись каталога
  нельзя вычесть подкаталог; так написано и в документации 1.0.92). `deny` в песочнице закрывает и чтение, поэтому для
  набора, который агент обязан читать, он не годится. Вариант `workspace_write = false` с записью только в каталоги
  модулей (1.0.92) возможен лишь при раскладке, где корень репозитория агент не правит; не проверялся.
- **Stop-гейт не срабатывает на оборванном ходе** (прерывание, `--max-turns`, «нет прогресса», ошибка API — вместо
  `Stop` идёт наблюдательное `StopCancelled`/`StopFailure`). Сессиям шага `--max-turns` не задавать; конец хода не
  по `end_turn` — «работа не сделана».
- **Предел 8 продолжений за ход.** Красный гейт держит ход не больше 8 раз (у набора и так 3 попытки); ожидание
  сабагентов хуком `stop` тратит те же продолжения, после восьмого Grok заканчивает ход, не спрашивая хуки.
- **Нет открытия сессии и отправки сообщения в чужую сессию из координатора, нет подписки на PR** — это делает
  владелец по готовым командам (B.2).
- **Хук формы отчёта проверяет форму, не истину.** Глубину проверки держат правило тщательности и приёмка
  координатора, как и в Claude Code.
- **MCP-инструменты записи и записи клиента ACP (`x.ai/fs/write_file`) guard не видит.** Набор MCP не использует; не
  подключать MCP-серверы, которые пишут файлы.
- **Сабагент Grok в SubagentStop приходит со своим id сессии**, для которого SessionStart не записывал исходное
  состояние: `stop_gate.py` судит его по незакоммиченным изменениям против HEAD (свой запасной путь набора). Для
  hardener'а это не меняет вердикт, но отличается от Claude.

### D.2. Известные сбои Grok по теме жалобы владельца и что с ними делает адаптер

| Сбой | Источник | Что делает адаптер |
|---|---|---|
| Запуск `grok -p` кончился `stopReason: cancelled` после 1–4 ходов, а `text` — одна вводная фраза («I'll inspect the … step»); скрипт выложил бы её как ревью «APPROVE» на PR, который никто не смотрел (CLI 1.0.50 и 1.0.73, `grok-4.5`) | issue bdh-org/dev-common#334, 2026-11-01 | B.6: проверка `stopReason == end_turn` и формы; одно продолжение `-r`; правило B.1, раздел 6; приёмка координатора |
| Ход родителя кончается (`end_turn`), пока сабагенты ещё работают в процессе Grok (CLI 1.0.13, `grok-4.6`). Это поведение по замыслу: фоновый сабагент переживает ход, его завершение будит родителя новым ходом; в issue — ошибка отображения в стороннем интерфейсе T3. Риск для набора — вывод в закончившемся ходе без отчётов | issue pingdotgg/t3code#9892, 2026-09-05; руководство 1.0.92 (Background Tasks: «Completion wakes the parent automatically») | хук `stop` держит ход, пока работают свои сабагенты; координатор ждёт всех и принимает отчёт в ходе, который начнёт Grok |
| Опрос сабагента без `timeout_ms` возвращает снимок, а не итог; ожидание с `timeout_ms` ограничено часом за вызов; `wait_commands_or_subagents` с `mode: "wait_any"` возвращает после первого завершившегося | руководство 1.0.92 (Background Tasks: Getting Output); исходники 1.0.45 (`xai-tool-types/src/task.rs`, `WaitTasksToolInput`) | B.1, раздел 2; B.2, п. 4; B.5: ждать с `timeout_ms` > 0 или `mode: "wait_all"`, снимок не принимать |
| Вход хука больше 128 КиБ обрезается (`toolInputTruncated`): 1.0.45 присылает весь вход одной строкой, 1.0.92 — с обрезанными длинными строками | исходники 1.0.45 (`xai-grok-hooks/src/event.rs` `truncate_payload`, `MAX_PAYLOAD_SIZE = 128 * 1024`; `acp_session_impl/tool_calls.rs`); руководство 1.0.92 (Hooks: Input; пример Safe Shell Guard) | прослойка отклоняет обрезанную shell-команду, `apply_patch` и вход не объектом (A.8; проверено, «Проверка») |
| Итог сабагента в напоминании обрезан до 16 000 байт, остальное — отдельным запросом | исходники 1.0.45 (`INLINE_SUBAGENT_OUTPUT_BYTES = 16_000`), строка `[output truncated: … bytes shown]` в бинарнике 1.0.92 | правило B.1: дочитать до приёмки; координатор B.2, п. 4 |
| Конец хода без проверки: прерывание, `--max-turns`, «нет прогресса» не вызывают Stop-гейт | руководство 1.0.92 (Hooks: `StopCancelled`) | D.1; правило B.1, раздел 6 |
| Режим плана закрывает инструменты правки, но не shell | docs.x.ai Plan Mode | правило B.1, раздел 2: план — не «только чтение» |
| Модель может сама выбрать сабагенту другую модель | руководство 1.0.45/1.0.92 (Subagents, `subagent_model_inheritance`) | `[features] subagent_model_inheritance = true` |
| «Сабагент пересказал вместо чтения», «заявил, что тесты прошли, не запустив» | для Grok Build и Grok 4.7 первичного или широко известного источника не найдено (D.4) | правило тщательности (доказательство к каждому утверждению), Stop-гейт и CI — независимо от вендора |

### D.3. Что проверено и как

Проверки — на копии набора (`round23/grok-test/…`) с синтетическими событиями по схеме Grok: конверт и поля — из
`xai-grok-hooks/src/event.rs` (1.0.45), псевдонимы snake_case — из руководства 1.0.92. Сам Grok не запускался (D.4).
- `round23/adapters/grok/test_grok_hooks.py` — 21 вызов инструментов, каждый дважды: как его увидит `guard.py` из
  `.claude/settings.json` (режим совместимости Grok) и через прослойку. Напрямую guard пропустил все 21, включая
  `search_replace` в `gauntlet/config/gauntlet.properties`, `echo >> gauntlet/…`, `git push --force`, `touch` у
  `reviewer`, правку `src/main` у `hardener`. Через прослойку — 14 отказов и 7 разрешений там, где их ждёт набор
  (правка `src/main` основным агентом, тесты у hardener'а, фичи у specifier'а до заморозки, `./gradlew` у reviewer'а,
  чтение, файл плана Grok, `apply_patch` в `src/main`); `apply_patch` и `hashline_edit` в набор — отказ;
  `__pycache__` в `gauntlet/` не появился. Итог: 44 проверки, 0 расхождений. Время прослойки с guard на составной команде
  (`cd`, цикл, конвейер, перенаправление, `git`, `./gradlew`): медиана 58 мс, максимум 84 мс за 10 запусков.
- `round23/adapters/grok/test_grok_stop.py` — с поддельным `./gradlew`: строка статуса записана; красный `gauntletFast`
  — exit 2 с причинами три раза, на четвёртый — «work is NOT done»; то же с конвертом 1.0.45 (`stopHookActive` без
  псевдонима); Stop в конце сессии — без прогона; свой сабагент или фоновый Gradle в `backgroundTasks` — ход
  продолжается без прогона; зелёный — exit 0; SubagentStop hardener'а — `mutationGate` и отметка под его id; хук формы
  — два возврата, затем записка координатору; отчёт по формату и ревьюер с покрытием — приняты; связанная рабочая
  копия (`git worktree`, как у `grok --worktree`) пишет строку статуса в свой каталог git и не затирает строку
  основной копии. Итог: 20 проверок, 0 расхождений.
- `round23/adapters/grok/test_grok_compat.py` — режим совместимости без прослойки: зелёный `mutationGate` hardener'а,
  затем Stop основного агента на том же коде с красным `gauntletFast`. Тест подаёт SubagentStop hardener'а с id сессии
  основного агента — и при такой предпосылке хук пропускает остановку, не запустив `gauntletFast`. Предпосылка
  неверна: по исходникам 1.0.45 событие сабагента идёт с его собственным id сессии (`acp_session/hooks.rs`
  `make_hook_envelope`: `session_id: self.session_id_string()`; `acp_session_impl/stop_gate.rs`:
  `subagent_id: self.session_id_string()`), и с ним ложного зелёного нет — `gauntletFast` запускается и без прослойки
  (проверка проверяющего, раздел «Проверка»). Настоящая ловушка режима совместимости — двойной `stop_gate.py` на
  каждый Stop при включённых рядом хуках `.claude/settings.json` (там же).
- Синтаксис: `.grok/hooks/gauntlet.json` — JSON, `.grok/config.toml` и `~/.grok/config.toml` — TOML (разобраны
  `json`/`tomllib`). Ключи конфигурации сверены со справочником настроек, встроенным в бинарник 1.0.92.
- Не проверено запуском Grok: что хуки, правила и агенты реально грузятся, что Stop держит ход, как ведут себя
  правила `deny` в shell — это шаг A.4, п. 6–7.

### D.4. Не подтверждено

- **Живой прогон Grok Build.** Бинарник не запускался (правило задачи: загруженное не исполняется), ключа API нет.
  Всё о поведении — из документации, исходников 1.0.45 и строк бинарника 1.0.92.
- **Блокирует ли `Stop` в 1.0.92 — живьём.** Короткая страница docs.x.ai «Hooks» называет `PreToolUse` единственным
  блокирующим событием; руководство в исходниках 1.0.45 и руководство, встроенное в бинарник 1.0.92 (Hooks: Stop
  Decision Control, таблица событий: «`Stop` … Yes: can block the stop»), описывают блокировку `Stop`/`SubagentStop`
  (и в бинарнике есть строка «Blocked by stop hook '…'»). Адаптер опирается на блокировку и проверяет её шагом A.4,
  п. 7; не подтвердится — раздел 3 правил Grok и CI.
- Загрузка ссылки `.grok/rules/10-gauntlet-kit.md` живьём (руководство 1.0.92 обещает её для ссылки с целью внутри
  репозитория; в 1.0.45 загрузчик читает ссылки в каталоге правил — тест
  `canonical_named_rule_collision_is_normalized_once`); символические ссылки на Windows.
- Наследуют ли рабочие копии `grok --worktree` доверие основной папки (поэтому в команде запуска `--trust`).
- Песочница в рабочей копии `grok --worktree`: каталог git такой копии лежит в `.git/worktrees/…` основной копии, вне
  рабочего каталога; под `workspace` коммиты и состояние `stop_gate.py` (`gauntlet-hook`) могут оказаться
  незаписываемыми. Прослойка в этом случае не падает (проверено на незаписываемом каталоге состояния), но строки
  статуса не будет, а хук формы отчёта без счётчика возвращает отчёт до предела Grok в 8 продолжений.
- Поведение правил `Edit(...)` для shell-команд записи после `cd` (вопрос разрешения или отказ в `dontAsk`).
- Песочница `workspace` со своим профилем и Gradle/Testcontainers (`~/.gradle`, `~/.testcontainers.properties`).
- Есть ли shell у встроенного `explore`: docs.x.ai пишет «no shell», руководство — «runs shell commands», исходники
  1.0.45 — без shell. Карточки адаптера на `explore` не опираются.
- Поля заголовка агента `capabilityMode` и `effort` — только в исходниках; адаптер их не использует.
- Какой модели соответствует id `grok-build` в каталоге CLI (пример настроек называет его «recommended for coding»),
  и точный id Grok 4.7 Fast в CLI — смотреть `grok models`.
- Предупреждения о лимите токенов (метод, п. 14) в Grok Build не найдены.
- Карточка модели Grok 4.7 (media.x.ai), журнал изменений `x.ai/changelog/build` и анонс `x.ai/news/grok-4-7` — закрыты
  сетевой политикой этой сессии, не прочитаны. Найденные поиском вторичные сообщения о «reward hacking» Grok 4.7
  (сторонние тесты) не проверены и в адаптер не взяты.
- Для «пересказа вместо чтения» и «тесты прошли без запуска» у Grok Build первичных источников не найдено — это не
  значит, что сбоя нет: правило тщательности действует независимо.
- `--json-schema` (структурированный вывод без интерфейса) виден в коде официального плагина, в руководстве описан
  мимоходом; адаптер на него не опирается.

### D.5. Источники (все прочитаны 2026-11-24)

Документация Grok Build (Markdown-версии страниц; индекс — https://docs.x.ai/llms.txt):
- https://docs.x.ai/build/overview.md — продукт, установка, требования, «Custom Models».
- https://docs.x.ai/build/features/project-rules.md — AGENTS.md/CLAUDE.md, `.grok/rules/`, `--rules`, `grok inspect`.
- https://docs.x.ai/build/features/subagents.md — типы `general-purpose`/`explore`/`plan`, `.grok/agents/`.
- https://docs.x.ai/build/features/hooks.md — события, контракт (короткая версия; расхождение — D.4).
- https://docs.x.ai/build/features/permissions.md, https://docs.x.ai/build/features/sandbox.md — режимы, правила,
  профили песочницы.
- https://docs.x.ai/build/settings.md, https://docs.x.ai/build/settings/reference.md — области настроек, ключи TOML,
  переменные окружения (`GROK_CLAUDE_HOOKS_ENABLED`, `GROK_SUBAGENTS` …).
- https://docs.x.ai/build/cli/reference.md, https://docs.x.ai/build/cli/headless-scripting.md — флаги, `-p`,
  форматы вывода, ACP.
- https://docs.x.ai/build/modes-and-commands.md (режимы, `/goal`, workflows), https://docs.x.ai/build/features/plan-mode.md,
  https://docs.x.ai/build/features/sessions.md, https://docs.x.ai/build/features/background-tasks.md (`/loop`),
  https://docs.x.ai/build/features/worktrees.md, https://docs.x.ai/build/features/dashboard.md.
- https://docs.x.ai/build/enterprise.md — сеть, слои конфигурации, `dontAsk`/`acceptEdits`, блокировка always-approve,
  npm-установка `@xai-official/grok`.
- https://docs.x.ai/developers/grok-4-7.md — Grok 4.7: id, контекст, уровни рассуждений, Fast, «default model of the
  coding agent».
- https://docs.x.ai/llms-full.txt, раздел `/developers/release-notes` — бета Grok Build и `grok-build-0.1` (май 2026),
  Grok 4.5/4.6/4.7 (июль/август/сентябрь), конец `grok-build-0.1` 2026-11-19.

Пакеты npm (`npm view`, `npm pack`; файлы прочитаны, ничего не запускалось):
- `@xai-official/grok@1.0.92` — `package.json` (bin `grok`, optionalDependencies по платформам, сопровождающий
  `xai-security`), `README.md`, `bin/postinstall.js` (бинарник распаковывается из Brotli); история версий
  (0.1.0 — 2025-10-22; 1.0.92 — 2026-11-20; alpha 1.0.93).
- `@xai-official/grok-linux-x64@1.0.92` — `bin/grok.br`, распакован в данные и прочитан как текст: встроенное
  руководство (Hooks, Subagents, Sandbox Mode, Project Rules, Headless Mode, справочник настроек), строки
  «Blocked by stop hook '…'», `[output truncated: … bytes shown]`, `stopHookActive`, `subagentType`, `.claude/agents`;
  строки `@import` нет.
- `@vibe-kit/grok-cli@0.0.34`, `grok-cli@1.0.5` — неофициальные CLI (описание, сопровождающие).

Исходники `github.com/xai-org/grok-build`, коммит `2bdd1d6` (2026-09-29, «Synced from monorepo», `SOURCE_REV`
`559751fd…`, крейты 1.0.45):
- `crates/codegen/xai-grok-hooks/src/event.rs` — `HookEventEnvelope`, `SNAKE_CASE_ALIASES`, `HookPayload` (поля
  `toolName`, `toolInput`, `subagentType`, `subagentId`, `stopHookActive`, `backgroundTasks`), виды событий;
  `src/runner/mod.rs` — разбор решений (`permissionDecision`, `StopHookJson`); `src/config.rs` — таймауты (5/30/600 с);
  `src/matcher.rs` — сопоставление имён Claude.
- `crates/codegen/xai-grok-tools/src/types/claude_alias.rs` — соответствие имён инструментов Claude и Grok;
  `implementations/grok_build/search_replace/mod.rs`, `grok_build/bash/mod.rs`, `opencode/write/mod.rs`,
  `grok_build_hashline/edit/types.rs`, `codex/apply_patch/tool.rs` и `parser.rs` — входы инструментов;
  `reminders/task_completion.rs` — 16 000 байт итога сабагента.
- `crates/codegen/xai-grok-agent/src/config.rs` — `AgentDefinition` (поля заголовка), `PermissionMode`, `Effort`,
  наборы инструментов (`explore` без shell); `discovery.rs` — `.grok/agents` и `.claude/agents`; `prompt/agents_md.rs`
  — загрузка правил и ссылок; `builder.rs` — правила проекта в контексте сабагентов.
- `crates/codegen/xai-grok-shell/src/session/acp_session_impl/stop_gate.rs` (`MAX_STOP_HOOK_CONTINUATIONS_PER_TURN = 8`,
  `backgroundTasks`), `hook_dispatch.rs` (`subagent_type_label`), `tool_calls.rs` (конверт `PreToolUse`);
  `crates/common/xai-tool-types/src/task.rs` — `spawn_subagent` (фон по умолчанию, `resume_from`, `model`).
- `crates/codegen/xai-grok-sandbox/src/profiles.rs`, `lib.rs`, `runtime_sockets.rs`, `allow_path.rs` — профили, запись
  и `deny`, сокеты контейнеров; `crates/codegen/xai-grok-permission-rules/src/claude_settings.rs`, `rules.rs`,
  `policy.rs`, `shell_access.rs` — правила разрешений, чтение `.claude/settings.json`, проверка shell-записи.
- `crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md`, `12-project-rules.md`, `14-headless-mode.md`,
  `15-agent-mode.md`, `16-subagents.md`, `18-sandbox.md`, `22-permissions-and-safety.md`.

Официальный плагин `github.com/xai-org/grok-build-plugin-cc`, коммит `8070d2f` (2026-11-07): `README.md`,
`plugins/grok-build/scripts/grok-bridge.mjs`, `scripts/lib/grok.mjs` — запуск ревью
`--agent explore --sandbox read-only --always-approve` и причина отказа от режима плана без интерфейса.

Сообщения о сбоях (прочитаны через веб):
- https://github.com/bdh-org/dev-common/issues/334 — `cancelled` после первого хода, вводная фраза вместо ревью
  (2026-11-01).
- https://github.com/pingdotgg/t3code/issues/9892 — конец хода родителя при работающих сабагентах (2026-09-05).

Не прочитаны (закрыты сетевой политикой сессии): https://x.ai/changelog/build, https://x.ai/news/grok-4-7,
https://media.x.ai/v1/website/4p7card-5eccc980.pdf (карточка модели Grok 4.7).

Добавлены при проверке (все прочитаны 2026-11-24, подробно — раздел «Проверка»): руководство, встроенное в
`@xai-official/grok-linux-x64@1.0.92` (`bin/grok.br`, разделы Hooks: Key Fields `failClosed`, Input
`toolInputTruncated`, Stop Decision Control, Caps, Porting Claude Code stop hooks; Project Rules: Auto-Loading Behavior;
Subagents and Personas: Depth Limits, Model Selection by the Agent; Background Tasks: Getting Output; Sandbox Mode:
Direct global write protection; Permissions and safety: Configuring Permissions); исходники `xai-org/grok-build`
(ветка `main`, `SOURCE_REV` `559751fd…`, крейты 1.0.45): `crates/codegen/xai-grok-shell/src/session/acp_session/hooks.rs`
(`make_hook_envelope`), `…/acp_session_impl/stop_gate.rs` (`build_stop_payload`), `…/acp_session_impl/tool_calls.rs`
(`truncate_payload` для `PreToolUse`), `crates/codegen/xai-grok-hooks/src/event.rs` (`MAX_PAYLOAD_SIZE`,
`SNAKE_CASE_ALIASES`, `clip_text`), `crates/codegen/xai-grok-sandbox/src/profiles.rs` и `runtime_sockets.rs`;
https://docs.x.ai/build/settings/reference.md (`max_timeout_secs` по умолчанию 36000, `goal`/`workflows`).

## Проверка

Независимая сверка адаптера 2026-11-24 по первоисточникам и другими запросами, чем у автора. Загруженное лежит в
`round23/verify-grok/` (данные, ничего не запускалось), проверочные скрипты — в `round23/verify-grok-scripts/`, копии
набора для прогонов — `round23/verify-grok/fx*`. Бинарник Grok не запускался.

### Что проверено (около 85 утверждений)

- **Продукт и версии.** `npm view @xai-official/grok`: 1.0.92 от 2026-11-20T01:08Z, alpha 1.0.93, сопровождающий
  `xai-security`, Apache-2.0, `bin: grok`, бинарники по платформам. `npm pack @xai-official/grok-linux-x64@1.0.92`:
  `bin/grok.br` распакован как данные (ELF x86-64, строки `crates/codegen/…/*.rs`). `xai-org/grok-build`, ветка
  `main` (raw.githubusercontent.com): `SOURCE_REV` 559751fd…, `xai-grok-pager` 1.0.45, CONTRIBUTING «does not accept
  external pull requests». docs.x.ai: `developers/grok-4-7.md` (500 000 токенов, знания до мая 2026, low…xhigh, «the
  default model of the coding agent», Fast — вдвое дороже, только Cursor и Grok Build), `developers/release-notes.md`
  (Grok Build — май; 4.5, 4.6, 4.7 — июль, август, сентябрь; конец `grok-build-0.1` 2026-11-19). `npm view`
  `@vibe-kit/grok-cli` (0.0.34) и `grok-cli` (1.0.5, «starts anthropic-proxy with Grok model and runs claude-code»).
  Совпало.
- **Правила проекта.** docs `features/project-rules.md`; руководство 1.0.92 (12-project-rules): имена файлов,
  `.grok/rules/*.md` целиком, загрузка только при доверии. Исходники `prompt/agents_md.rs`: ссылка в каталоге правил
  читается, проектные файлы без доверия отбрасываются. Совпало; дополнено условием 1.0.92 для ссылок (п. 7 ниже).
- **Агенты.** `xai-grok-agent/src/discovery.rs` (`.grok/agents` и `.claude/agents` от рабочего каталога до корня),
  `config.rs` (`model: inherit`; `tools`/`disallowedTools` строкой или списком; `agents_md` по умолчанию `true` —
  правила проекта доходят до сабагента), `xai-grok-tools/src/types/claude_alias.rs` (имена Claude → инструменты Grok),
  `xai-tool-types/src/task.rs` (`run_in_background` по умолчанию `true`, `resume_from`, `model`; параметра
  наследования переписки родителя нет — новый опровергатель стартует без истории первого исполнителя). Совпало.
- **Хуки.** docs `features/hooks.md`; руководство 1.0.92 (Hooks): места хуков и доверие; какие события блокируют;
  ответы `decision` и `hookSpecificOutput.permissionDecision`; exit 2; таймауты 5 и 600 с; псевдонимы snake_case, в том
  числе `hook_event_name` с именем в PascalCase; `subagentType` вместо `agent_type`; `backgroundTasks` (поля, `status:
  running`); Stop — только у основного агента, у сабагента — SubagentStop; 8 продолжений за ход; `StopCancelled`;
  Stop в конце сессии с `reason` не `end_turn`; обрезка `lastAssistantMessage` до 32 768 символов с меткой
  `… [+N chars]`. Исходники `xai-grok-hooks/src/event.rs`, `acp_session_impl/stop_gate.rs`, `acp_session/hooks.rs`.
  Совпало, кроме пунктов 1–4 ниже.
- **Разрешения и песочница.** docs `features/permissions.md`, `features/sandbox.md`, `settings/reference.md`,
  `enterprise.md`; руководство 1.0.92 (Permissions and safety, Sandbox Mode); `xai-grok-sandbox/src/profiles.rs`,
  `runtime_sockets.rs`: компактная форма `[permission] deny = ["Edit(...)"]`; слияние с `.claude/settings.json`;
  `Bash(cmd:*)`; запреты `Edit` действуют и на shell; режимы `dontAsk`, `acceptEdits`; запрет always-approve только из
  корневого файла; запись `~/.grok/config.toml`, `trusted_folders.toml`, `~/.grok/hooks/` и файлов хуков проекта под
  песочницей закрыта; «ядро не вычитает каталог из разрешения родителя»; сокет Docker закрыт только при
  `restrict_network`. Совпало, кроме B.6 (п. 9).
- **Ключи `~/.grok/config.toml`** — справочник, встроенный в 1.0.92: `compat.claude.hooks`, `subagents.max_depth`
  (5 на маршруте демона, 1 на маршруте shell), `features.subagent_model_inheritance`, `models.default`,
  `models.default_reasoning_effort`, `toolset.bash.timeout_secs`, `toolset.bash.max_timeout_secs`. Все существуют.
- **CLI.** docs `cli/reference.md`, `cli/headless-scripting.md`, `features/worktrees.md`, `features/sessions.md`,
  `modes-and-commands.md`, `features/background-tasks.md` и руководство 1.0.92: `-p`, `--output-format json` (`text`,
  `stopReason`, `sessionId`), `--agent`, `--trust`, `--sandbox`, `--always-approve`, `--permission-mode`, `--effort`,
  `--no-auto-update`, `--worktree=<имя>` с `--ref`, `grok -r`, `grok worktree rm`, `grok inspect`, `/session-info`,
  `/usage`, `/loop` (от 60 с, до 7 дней), `/import-claude`, `/hooks-trust`, `grok dashboard`. Совпало.
- **Внешние свидетельства.** Плагин `xai-org/grok-build-plugin-cc` (`main`, `grok-bridge.mjs`: `agent: "explore"`,
  `alwaysApprove: true`, `sandbox: "read-only"`, комментарий о зависании режима плана без человека). Issue
  bdh-org/dev-common#334 (CLI 1.0.50 и 1.0.73, `grok-4.5`, `cancelled` после 1, 2 и 4 ходов, вводная фраза, «would
  post … as an APPROVE»). pingdotgg/t3code#9892 (CLI 1.0.13, `grok-4.6`, `end_turn` при работающих сабагентах).
  Совпало; характер второго — п. 5.
- **Ядро и набор.** Правило тщательности (B.1, раздел 4), формат отчёта (раздел 5) и приёмка координатора (B.2)
  соответствуют `core.md`, разделы 1–3. Раздел 5 ядра сохранён: гейты и CI не меняются; роли держат права через
  guard; пути человека — guard, `deny` и CI, а пробел CI по `.grok/` и `AGENTS.md` назван прямо (A.6, п. 1; сверено с
  `HUMAN_OWNED` в `gauntlet/hooks/guard.py` и списком в `.github/workflows/gauntlet-kit.yml`); «не заканчивай с
  красным» — Stop-хук и раздел 3 со строками `> Task …`; правило двух раундов и находки «правило» — B.2 и B.5.
- **Прогоны.** Тесты автора `test_grok_hooks.py` и `test_grok_stop.py` на исходной прослойке — 0 расхождений; после
  правок прослойки — снова 0.

### Что исправлено и почему

1. **«Ложный зелёный без прослойки» — неверно.** Тест автора подавал SubagentStop hardener'а с id сессии основного
   агента. По исходникам событие сабагента идёт с его собственным id (`acp_session/hooks.rs` `make_hook_envelope`:
   `session_id: self.session_id_string()`; `acp_session_impl/stop_gate.rs`: `subagent_id: self.session_id_string()`;
   руководство 1.0.92: «Both scripts also run inside a subagent's own session»). `compat_session_ids.py`: с таким id
   `gauntletFast` на Stop основного агента запускается и без прослойки (exit 2); ложный зелёный воспроизводится только
   на предпосылке автора. Исправлены A.2 п. 1, A.6 п. 2, докстрока A.8, C, D.3, комментарий в `~/.grok/config.toml`.
2. **Настоящая ловушка режима совместимости — двойной `stop_gate.py`.** `double_stop.py`: если хуки
   `.claude/settings.json` оставить включёнными рядом с прослойкой, каждый Stop прогоняет гейт дважды, и после второго
   Stop счётчик показывает «attempt 3/3» вместо 2/3. Это и есть причина `[compat.claude] hooks = false` (A.2, A.7).
3. **Прослойка пропускала обрезанный вход хука.** Grok обрезает вход больше 128 КиБ (`toolInputTruncated`): в 1.0.45
   весь `toolInput` становится строкой (`event.rs` `truncate_payload`, `MAX_PAYLOAD_SIZE = 128 * 1024`;
   `tool_calls.rs`), в 1.0.92 обрезаются длинные строки (руководство, Input); руководство прямо требует от охранного
   хука отказа в этом случае (пример Safe Shell Guard). `truncated_input.py` на исходной прослойке — 4 пропуска из 9
   случаев, в том числе `write` в `gauntlet/` в форме 1.0.45. Исправлено в `guard` (отказ для обрезанной shell-команды,
   `apply_patch` и входа не объектом; путь файловых инструментов не обрезается и судится как раньше); после правки —
   0 расхождений. A.4 п. 7, A.8, C, D.1, D.2, правило B.1 (раздел 6).
4. **`failClosed` не учтён.** «Сбой хука пропускает действие» верно только по умолчанию: в 1.0.92 обработчик
   `PreToolUse` с `"failClosed": true` при сбое отклоняет вызов (руководство, Hooks: Key Fields, Exit Codes). Адаптер
   теперь ставит его guard'у (A.7; решение владельца A.6, п. 7). Запасной путь прослойки, который при неработающем
   `guard.py` молча разрешал вызов, теперь завершается ошибкой (`guard_missing.py`: exit 1 с причиной вместо
   разрешения). A.2, A.6, A.7, A.8, C, D.1, правило B.1 (раздел 6).
5. **Ожидание сабагентов.** `get_command_or_subagent_output` без `timeout_ms` даёт снимок; ожидание ограничено часом за
   вызов; завершение сабагента будит родителя само (руководство 1.0.92, Background Tasks: Getting Output);
   у `wait_commands_or_subagents` обязательный `mode`, и `wait_any` возвращает после первого завершившегося
   (`xai-tool-types/src/task.rs`, `WaitTasksToolInput`). Добавлено в B.1 (раздел 2), B.2 (п. 4), B.5, C, D.2.
   Строка D.2 о t3code переписана: конец хода при работающих сабагентах — поведение Grok по замыслу, а сам issue —
   ошибка отображения в T3. Обещание «Stop-хук не даст закончить ход» смягчено до «не больше 8 раз за ход».
6. **Доверие и агенты проекта.** Руководство 1.0.92 ставит под доверие MCP, LSP, хуки, инструкции и навыки проекта и
   хуки агентов, но не называет сами определения агентов. «Агенты проекта — только в доверенной папке» заменено на
   «не подтверждено» (A.2, A.4, C, D.1).
7. **Ссылка в `.grok/rules/`.** В 1.0.92 символическая ссылка проекта грузится, только если её цель внутри
   репозитория (руководство, Project Rules: Auto-Loading Behavior); для `gauntlet/CLAUDE.md` это выполнено. Дополнены
   A.5 и D.4.
8. **`max_timeout_secs = 7200` урезал предел** (по умолчанию 36000 с — docs.x.ai `settings/reference.md`). Строка
   убрана, комментарий исправлен.
9. **B.6: копия карточки в `/tmp`.** Под `read-only` временные каталоги и `~/.grok` остаются записываемыми (docs
   `features/sandbox.md`; руководство 1.0.92, Sandbox Mode), так что копия в `/tmp` не была «только для чтения».
   Копия перенесена в `$HOME/gauntlet-cards/<id>`, пункт о пределах уточнён.
10. **Обратная связь Stop-хука — не длиннее 10 000 символов** (руководство 1.0.92, Hooks: Caps), а `stop_gate.py`
    отдаёт до 12 000 и путь к журналу в конце. Добавлено в D.1.
11. **`/goal` и воркфлоу выключаются средой** (`[goal] enabled`, `[workflows] enabled` — справочник 1.0.92, docs
    `modes-and-commands.md`). Добавлены закомментированные строки в `~/.grok/config.toml` и в C; правило «только по
    решению владельца» осталось.
12. Источник блокировки Stop в C и D.4 уточнён (раздел руководства 1.0.92), в D.5 добавлены новые источники.

Кроме этого файла правились `round23/adapters/grok/grok_hooks.py`, `files/.grok/hooks/gauntlet.json`,
`files/home-grok-config.toml`, `files/.grok/rules/00-gauntlet-grok.md`, `files/coordinator-prompt.md`,
`files/step-session-rules.md` и `grok.template.md`; адаптер пересобран `round23/scripts/assemble.py`.

### Что осталось не проверенным

- Живой прогон Grok Build: загрузка хуков, правил и агентов; блокировка Stop; отказ по `failClosed` и по
  `toolInputTruncated` на настоящем конверте 1.0.92; загрузка ссылки правил — это шаги A.4, п. 6–7.
- Грузятся ли определения агентов проекта без доверия папки; наследуют ли рабочие копии `grok --worktree` доверие;
  пишет ли рабочая копия под песочницей в каталог git основной копии.
- Символические ссылки на Windows; точные id `grok-build` и Grok 4.7 Fast в каталоге CLI.
- Бывает ли у Grok 4.7 (а не 4.5) сбой «`cancelled` после вводной фразы». Первичных источников о «пересказе вместо
  чтения» и «тесты прошли без запуска» у Grok Build нет и в этой проверке: два новых поиска нашли только форум
  Cursor о других продуктах.
- https://x.ai/changelog/build, https://x.ai/news/grok-4-7 и карточка модели: `x.ai` закрыт сетевой политикой и для
  этой проверки (ENOTFOUND); чтобы прочитать их, домен нужно разрешить в настройках сети окружения.
- Дата синхронизации `2bdd1d6` (2026-09-29): GitHub API для чужого репозитория из сессии закрыт; дата совпадает с
  публикацией 1.0.45 на npm (2026-09-29T06:10Z).
