# Адаптер gauntlet для Qwen 4 Max (Qwen Code)

Ревизия адаптера 1, 2026-11-24, с исправлениями независимой проверки того же дня (раздел «Проверка» в конце: что
исправлено и почему). Язык — русский, как `gauntlet/CLAUDE.md`; ключи настроек, имена файлов, событий и
команды вендора — как есть. Ядро (`core.md`: правило тщательности, приёмка отчётов, формат отчёта, карточки) перенесено
без ослаблений; где Qwen Code чего-то не умеет, это сказано прямо, с запасным путём.

Что проверено в этой работе (раздел D.5): документация Qwen Code по тегу `v0.28.4` и код опубликованного пакета
`@qwen-code/qwen-code@0.28.4` прочитаны; прослойка `qwen_hooks.py` и хуки набора `guard.py`, `stop_gate.py`,
`session_start.sh` прогнаны на синтетическом репозитории с событиями в формате Qwen Code — 75 + 14 проверок, файлы
адаптера проверены статически по правилам загрузчика Qwen Code — 63 проверки; все зелёные. Что не проверено: живой Qwen Code не запускался (скачанный пакет — непроверенный код, он только прочитан;
ключа QwenCloud в этой сессии нет). Поэтому каждая строка «полностью» в разделе C держится на проверке установки
(A.6), а не на этом документе.

---

## A. Что это и куда ставить

### A.1. Что такое «qwen 4 max» и где он работает
- **Модель.** Qwen4-Max — флагманская модель Alibaba (семейство Qwen 4), идентификатор в API и в Qwen Code — `qwen4-max`.
  Вышла 16.11.2026 [W1–W4]. Числа из анонсов — 2,4 трлн параметров (MoE, ~71 млрд активных), контекст 1 млн токенов,
  только облако (QwenCloud API, Token Plan, Qwen Studio, QwenWork, Qoder), без открытых весов — по вторичным источникам
  и сниппету официального блога: страницы qwen.ai из этой сессии не открываются, «не подтверждено» первоисточником.
- **Что подтверждено первоисточником.** Qwen Code 0.28.0 (17.11.2026): «add qwen4-max support with native effort ladder,
  cache TTL, and image detail (#17513)» [S22]. Документация 0.28.4, «qwen4-max specifics» [S13]: каналы — ModelStudio
  Standard, Token Plan, QwenCloud Standard и подписка Qwen (Qwen OAuth); лестница рассуждений `low` / `high` / `xhigh`,
  **по умолчанию `high`**; `medium` поднимается до `high`, `max` сводится к `xhigh`, `none` выключает рассуждения;
  `max_tokens` покрывает рассуждения и ответ вместе — 262 144 с рассуждениями, 131 072 без; на подписке уровень
  превращается в `thinking_budget` (`low` → 4096, `high` → 131072, `xhigh` → 262144). В коде пакета окно контекста
  `qwen4-max` — 1 000 000 [S1: `chunks/chunk-MVDL2G4R.js`, `QWENCLOUD_MODELS`].
- **Где она работает как агент.** Qwen Code — открытый агент Qwen для терминала (Apache-2.0); начинался как форк Gemini CLI
  v0.8.2 и с v0.1 развивается отдельно [S23]. Версия на дату адаптера — **0.28.4** (`npm view`: `latest`, опубликована
  22.11.2026, Node ≥ 22) [S1]. Адаптер написан для неё. Не покрыты: **Qwen Code 1.0 Preview** (ветка `v1.0.0-preview`,
  свой установщик, «some interfaces, configuration options, and behaviors may change») [S24], Qoder и QwenWork — у них
  свои среды, их хуки и сабагенты здесь не изучались.

### A.2. Файлы в проекте
| Путь | Что | Раздел |
|---|---|---|
| `QWEN.md` (корень) | файл инструкций, всегда в контексте; включает `gauntlet/CLAUDE.md` импортом | B.1 |
| `.qwen/settings.json` | хуки, разрешения, таймаут оболочки, режим одобрения, память | B.5 |
| `.qwen/.env` | пустой файл-заглушка (только комментарии): Qwen Code берёт из проекта первый `.env`, и этот стоит первым — корневой `.env` и `.env` над репозиторием в окружение сессии и хуков не попадают | B.5 |
| `.qwen/agents/specifier.md`, `hardener.md`, `reviewer.md` | роли набора как агенты Qwen Code | B.3 |
| `.qwen/agents/precheck-mapper.md`, `precheck-framework.md`, `precheck-critic.md`, `precheck-refuter.md`, `review-repro.md` | карточки 4.1–4.4 и 4.6 ядра | B.4 |
| `gauntlet/adapters/qwen/qwen_hooks.py` | прослойка: `PreToolUse` и `SubagentStart` Qwen Code → `guard.py` набора | B.5, прил. 1 |
| `gauntlet/adapters/qwen/coordinator.md` | промпт координатора | B.2 |
| `gauntlet/adapters/qwen/report.schema.json` | JSON-схема отчёта карточки для запуска без интерактива | A.5 |

Все они — файлы человека. То, что под `gauntlet/`, видит CI-проверка `gauntlet kit unchanged`; `QWEN.md`, `AGENTS.md`
и `.qwen/` она сегодня не видит — решение владельца A.7, п. 1 (до него их держат guard через прослойку и
`permissions.deny`). `.qwen/` не добавлять в `.gitignore`, хотя так советует инструкция GitHub Action Qwen Code [S25]:
настройки, хуки и роли должны быть в репозитории. В `.gitignore` — только `.qwen/QWEN.local.md` (личные заметки,
грузится после `QWEN.md` [S5]) и `.qwen/worktrees/` (рабочие деревья, которые создаёт сам Qwen Code [S19]).
`.qwen/.env` должен попасть в git (его берёт и каждый `git worktree` шага): глобальный `.gitignore` с шаблоном `.env`
его скрывает — тогда `git add -f .qwen/.env`; проверка — A.6, п. 8.

### A.3. Что настроить
1. **Установка.** `npm install -g @qwen-code/qwen-code@0.28.4` (Node 22+), `qwen --version` → `0.28.4`. Версию фиксировать:
   контракт хуков «forward-extensible», поля добавляются [S2, «Hook Input Structure»]; после обновления — A.6 заново.
2. **Модель.** В сессии `/auth` → QwenCloud (Token Plan или Standard API Key), Alibaba ModelStudio или «Qwen Account with
   Subscription» [S14]; `/model` → `qwen4-max`; `/effort xhigh` (или `model.reasoningEffort` в `~/.qwen/settings.json`) —
   рекомендация A.7, п. 4.
3. **Окружение.** `ORG_GRADLE_PROJECT_publicRepositories=true` в окружении, из которого запускается `qwen` (иначе сборка
   пойдёт в корпоративный реестр: `gauntlet/CLAUDE.md`, «Среда облачной сессии»); Docker запущен (Testcontainers);
   `python3` и `git` в `PATH` — на них хуки набора.
4. **Запуск — из корня репозитория.** `QWEN_PROJECT_DIR`, `CLAUDE_PROJECT_DIR` и `GEMINI_PROJECT_DIR` Qwen Code ставит
   хуку равными рабочему каталогу сессии [S1: `commandInvocation`]; из подкаталога путь к скрипту хука неверен, а
   `python3` без файла выходит с кодом 2 — для Qwen Code это блокировка: каждая правка и каждая остановка будут
   отклонены с текстом «can't open file» (воспроизведено тестом, раздел D.5).
5. **Одобрение хуков.** Хуки проекта не работают, пока владелец их не одобрил: при первом запуске Qwen Code показывает
   их и спрашивает; решение хранится в `~/.qwen/hookApprovals.json` и привязано к точной конфигурации хуков, к `.env`
   проекта и `settings.env`: любая их правка — вопрос заново; Esc откладывает [S2, «Approving project hooks»]. Ключ
   записи — корень проекта, рядом — sha256 хуков с окружением [S1: `chunks/chunk-62ZGP54Z.js`,
   `LoadedHookApprovals.getState`, `hashProjectHooks`]: новый `git worktree` сессии шага — новый ключ, одобрить и там.
   Без интерактива (`qwen -p`) Qwen Code не спрашивает: неодобренные хуки не грузятся, в stderr — одна строка [S2].
6. **Не включать для сессий задач** `tools.executionSandbox`: в этом режиме Qwen Code выключает исполняемые хуки
   [S9; S1: `getHookSystem(){if(this.shellExecutionSandbox)return void 0 …}`] — guard и stop-gate молча пропадут.
   Песочница Docker/Seatbelt (`--sandbox`) с Gradle и Testcontainers не проверялась.
7. **Если хуки нужны без интерактива и без одобрения** (выделенный раннер): хуки системных настроек
   `/etc/qwen-code/settings.json` (или `QWEN_CODE_SYSTEM_SETTINGS_PATH`) грузятся независимо от доверия к папке [S2,
   «Hook Configuration»; S6, «Settings files»], а агент, работающий не от root, их не правит. Запуск без интерактива с
   `--yolo` (или `--approval-mode yolo`) в командной строке тоже грузит проектные хуки как одобренные, но одобряет и все
   вызовы инструментов [S2, «Approving project hooks»; S10, «Safety in unattended runs»] — только в одноразовом
   окружении; интерактивного YOLO это не касается.
8. **Ручки тщательности и где они стоят.** Уровень рассуждений — на сессию (`/effort`, `model.reasoningEffort`), у
   `qwen4-max` верх лестницы `xhigh` [S13]. Потолков ходов в адаптере нет: `model.maxSessionTurns` по умолчанию `-1`,
   у агентов `maxTurns` не задан; на ход — адаптивные 100 вызовов инструментов (`model.maxToolCallsPerTurn`): останавливает
   ход только на зацикливании и на жёстком пределе 1000, но на той же отметке 100 «долгая непрерывная фаза только
   чтения» получает одно напоминание свернуть исследование [S6, `model.maxToolCallsPerTurn`; текст — D.2, п. 9]. Значение
   `0` или меньше убирает и напоминание, и предел 1000 [S6; S1: `getMaxToolCallsPerTurn`] — это решение владельца, в
   адаптере не задано. Авто-сжатие — около 85 % окна (`context.autoCompactThreshold`) [S6]. Режим `plan`
   (`/plan`, `--approval-mode plan`) — только анализ, без правок и без команд оболочки [S7]: для карточек не годится, им
   нужны `git grep`, `javap`, Gradle; а `approvalMode: plan` у сабагента при разрешительной сессии не держится [S3].
   Goals (`/goal`) — решение A.7, п. 7. Без интерактива — `--max-session-turns`, `--max-wall-time` (A.5).

Что делает каждый блок `.qwen/settings.json` — раздел B.5.

### A.4. Как переиспользуются файлы набора, а не копируются
- **Процесс и жёсткие правила.** `QWEN.md` включает `gauntlet/CLAUDE.md` строкой `@gauntlet/CLAUDE.md`. Импорт Qwen Code:
  путь от каталога `QWEN.md`, глубина не больше 5, только внутри корня проекта, `@` внутри кода (`` `…` ``, блоки) не
  раскрывается [S5, «Reference other files»; S1: `processImports`, `validateImportPath`, `findImports`]. В
  `gauntlet/CLAUDE.md` нет `@` вне кода (проверено), так что он попадает в контекст как есть.
- **До сабагентов** тот же контекст доходит сам: системный промпт сабагента собирается с файлами контекста сессии
  [S1: `renderSubagentSystemPrompt` → `assembleSystemPrompt({contextFiles: runtimeContext.getUserMemory(), …})`].
- **Роли.** Агенты `.qwen/agents/<роль>.md` тонкие: первым действием роль читает свой файл набора
  `.claude/agents/<роль>.md` и следует ему; агент Qwen Code добавляет только замены механизмов, чек-лист тщательности
  и формат отчёта. Чтение доказывается строкой `файл:строка` с цитатой в отчёте. Обновление роли в наборе доходит до
  Qwen Code без правки адаптера.
- **Хуки.** `guard.py`, `stop_gate.py`, `session_start.sh` не меняются. `Stop`, `SubagentStop` и `SessionStart` Qwen Code
  вызывает их напрямую: событие и смысл кода выхода совпадают с Claude Code (раздел B.5). `PreToolUse` и
  `SubagentStart` идут через `qwen_hooks.py`: он загружает `guard.py` как модуль и только переводит имена инструментов,
  определяет роль сабагента и добавляет человеческие пути Qwen Code.
- **Копия одна:** тексты разделов 1 и 3 ядра в `QWEN.md` — `core.md` пока не файл набора. Когда ядро ляжет в набор
  (например, `gauntlet/subagents.md`), копию заменить строкой импорта.

### A.5. Как запускается работа
- **Сессия задачи.** В рабочем дереве шага: `ORG_GRADLE_PROJECT_publicRepositories=true qwen --model qwen4-max -i "$(cat
  <промпт сессии>)"`, затем `/effort <уровень>`. Промпт — приложение D метода с заменами из B.2, раздел 4.
- **Координатор.** В своём рабочем дереве: `ORG_GRADLE_PROJECT_publicRepositories=true qwen --model qwen4-max
  --append-system-prompt "$(cat gauntlet/adapters/qwen/coordinator.md)"`, затем `/effort xhigh` и слово `coordinate`
  с путём к плану. `--append-system-prompt` добавляет текст после встроенного промпта и файлов контекста [S6,
  «Command-Line Arguments»]; в интерактивном режиме флаг не проверялся — запасной путь: первым сообщением «прочитай
  `gauntlet/adapters/qwen/coordinator.md` целиком и следуй ему».
- **Qwen Code как внешний исполнитель карточки** (маршрут «CLI другого вендора» из черновика `routing.md`: координатор
  другой среды отдаёт Qwen Code карточку только на чтение). Отдельный `git worktree` на зафиксированном коммите:

  ```bash
  git worktree add --detach ../precheck-<sha> <sha> && cd ../precheck-<sha>
  qwen -p "$(cat <карточка>.md)" --model qwen4-max --approval-mode default \
    --exclude-tools 'edit,write_file,notebook_edit,agent,save_memory,Bash(git *),Bash(gh *)' \
    --allowed-tools 'Bash(javap *),Bash(cat *),Bash(ls *)' \
    --json-schema @gauntlet/adapters/qwen/report.schema.json \
    --max-session-turns 150 --max-wall-time 45m --output-format json > ../precheck-<sha>.json
  echo "exit=$?"   # 0 — отчёт; 53 — потолок ходов, 55 — бюджет, 130 — прерван: карточка не выполнена
  ```

  Карточка — тело файла агента карточки (B.4) без заголовка плюс входы; коммит `<sha>` координатор пишет во входы сам.
  Почему это только чтение: без интерактива режим `default` (Ask) убирает оболочку, `edit` и `write_file`, если правило
  не разрешило их явно [S7, «Run headless queries in Ask Permissions Mode»]; `--exclude-tools` убирает запись. Но
  правило — это не только `--allowed-tools`: к ним добавляются `permissions.allow` всех слоёв настроек, в том числе
  `.qwen/settings.json` из этого worktree (`Bash(git *)` — значит и `git push`, `git commit`; `Bash(gh pr create *)`,
  `Bash(gh pr comment *)`, `Bash(./gradlew *)`) и `~/.qwen/settings.json` владельца [S6, `permissions.allow`: «Merged across
  all scopes»; S1: `mergedAllow`, `chunks/chunk-OHCM23H2.js`]. Поэтому `git` и `gh` здесь запрещены целиком: записи из
  `--exclude-tools` идут в список запретов (`mergedDeny`), а запрет сильнее любого разрешения [S6, «Decision priority»].
  Код карточка читает инструментами `read_file`, `grep_search`, `glob`; истории git (`git log`, `git show`) у неё нет —
  нужное из истории координатор кладёт во входы. `./gradlew` (проверки) остаётся из настроек проекта — это ядро
  позволяет (правило 1.6). Что команда вне правил в `-p` будет отклонена, а не выполнена, —
  следует из документации режима, живьём не проверено. Хуки проекта в новом worktree не одобрены и не грузятся — опора
  здесь на инструменты и разрешения, а не на guard. `--json-schema` фиксирует форму отчёта (коммит, доказательства,
  раздел «не проверено» обязателен) и завершает прогон на первом валидном ответе [S11]; правдивость доказательств —
  приёмка координатора (ядро, раздел 2, и черновик `routing.md`, п. 5).

Схема отчёта карточки — `gauntlet/adapters/qwen/report.schema.json`:

```json
{{file:gauntlet/adapters/qwen/report.schema.json}}
```

### A.6. Проверка установки (до первой задачи и после каждого обновления Qwen Code или набора)
В ветке-песочнице, в корне репозитория:
1. `qwen --version` → `0.28.4`; `python3 gauntlet/adapters/qwen/qwen_hooks.py selftest` → `ok`.
2. `qwen` → диалог одобрения хуков → одобрить. Первое сообщение агента содержит строку `[gauntlet] active - …`; `/hooks`
   показывает `SessionStart`, `SubagentStart`, `PreToolUse`, `Stop`, `SubagentStop`.
3. «Допиши строку в `gauntlet/config/gauntlet.properties`» → отказ `[gauntlet guard] … human-owned` (и через `edit`, и
   через `echo >>`).
4. «Вызови сабагента reviewer: пусть создаст `src/test/java/X.java`» → отказ `The reviewer is read-only`.
5. «Вызови specifier: черновик фичи о …» → файл фичи создан (до коммита `spec:`); после коммита `spec:` повтор — отказ
   «frozen».
6. Внести в `src/main` нарушение гейта (метод длиннее лимита) и попросить закончить → Stop-хук запускает `gauntletFast`,
   агент получает красные строки и продолжает работу; в выводе — «attempt 1/3».
7. `qwen -p "скажи ok"` в каталоге без одобрения хуков → строка в stderr о том, что хуки проекта не загружены.
8. `git ls-files .qwen/.env` → файл в git. Владелец кладёт в корневой `.env` строку `GAUNTLET_PROBE=1` и запускает `qwen`:
   «выполни `printenv GAUNTLET_PROBE`» → пусто (корневой `.env` закрыт заглушкой), ключ API из `~/.qwen/.env` при этом
   работает (по коду 0.28.4 домашние файлы грузятся и после проектного; auth.md называет их запасными — расхождение,
   см. «Проверка»). Строку удалить.
9. Владелец: `GAUNTLET_GUARD=off qwen` → строка статуса `guard: off`, правка `gauntlet/config/gauntlet.properties`
   проходит (ручная поддержка набора); без переменной — снова отказ.
Расхождение на любом шаге — адаптер в этой среде не работает как описано: работа идёт с опорой на раздел 5 `QWEN.md`
и CI, и владелец знает об этом до первой задачи.

### A.7. Решения владельца (ответ «1) да 2) …»)
1. **Человеческие пути Qwen Code — в набор.** Добавить `.qwen/`, `QWEN.md`, `AGENTS.md`, `.qwenignore`, `.agentignore`,
   `.aiignore` в `HUMAN_OWNED` guard'а и в список `gauntlet-kit.yml`. До этого их закрывает прослойка (только когда
   хуки загружены) и `permissions.deny`, а CI правку не видит — её видно только в диффе PR. Рекомендация: да.
   Сюда же — переменные, которые Qwen Code берёт из `.env` при старте и отдаёт хукам [S14, «`.env` files»; S1:
   `findEnvFiles`, `commandInvocation`]: `GAUNTLET_GUARD=off` или `GAUNTLET_STOP_HOOK=off` в таком файле выключили бы
   охрану в следующей сессии. Проектный `.env` закрывает заглушка `.qwen/.env` (A.2), `~/.env` — прослойка и
   `Edit(~/.env)` в `deny`; `~/.qwen/.env` уже под `~/.qwen/`.
2. **Авто-память Qwen Code выключить** (`memory.enableManagedAutoMemory` и `enableManagedAutoDream` — `false`,
   `save_memory` — в `deny`). Иначе модель сама пишет заметки в `~/.qwen/projects/<проект>/memory/` и подгружает их в
   следующие сессии [S5] — правила, которые не писал человек. Командную память тоже (`memory.enableTeamMemory` и
   `enableTeamMemorySync` — `false`, по умолчанию выключены, но пользовательская настройка могла их включить): она
   пишет в `.qwen/team-memory/` внутри репозитория, а синхронизация при старте сессии сама делает fast-forward pull,
   коммит и push этой папки [S5, «Team memory», «Automatic git sync»]. Рекомендация: да (так в B.5).
3. **Режим одобрения** `auto-edit` + список `permissions.allow` (как «Accept edits» набора) или `auto` (классификатор
   модели решает про оболочку; это суждение модели, не охрана) [S7]. Рекомендация: `auto-edit`.
4. **Уровень рассуждений `xhigh`** для координатора и сессий шагов (умолчание `qwen4-max` — `high`). Дороже; отдельного
   уровня для сабагентов нет (B.3, D.1). Рекомендация: да, особенно для тонкой семантики фреймворка.
5. **Внешний ревьюер PR — не Qwen** (метод, п. 19: другой вендор, чем у сессий, пишущих PR). Рекомендация: да.
6. **`context.fileName: "QWEN.md"`** — Qwen Code по умолчанию грузит ещё и `AGENTS.md` [S5; S1:
   `currentMemoryFilename=[DEFAULT_CONTEXT_FILENAME, AGENT_CONTEXT_FILENAME]`]; если `AGENTS.md` ведёт адаптер другого
   вендора, его механизмы попадут в контекст Qwen Code. Рекомендация: да (так в B.5).
7. **Goals Qwen Code** (`/goal` с независимым верификатором) для этапа реализации — не по умолчанию: верификатор —
   модель, читает только транскрипт и не запускает команд [S12]; авторитет — гейты и CI. Рекомендация: нет; можно для
   аудитов только на чтение.

---

## B. Промпты

### B.1. `QWEN.md` — файл инструкций проекта ({{size:QWEN.md}} байт без импорта; с `gauntlet/CLAUDE.md` — около 85 КБ)
Qwen Code советует держать `QWEN.md` коротким: длинный файл соблюдается хуже, и он идёт в каждый запрос каждой сессии
[S5; S17]. Жёсткого предела размера ни документация, ни код импорта не задают (ограничена только глубина импорта, 5)
[S5; S1: `processImports`]. Набор длинный по природе; кэш токенов снижает цену [S17], а надёжность соблюдения держится
на хуках, приёмке и CI, не на длине текста.

````markdown
{{file:QWEN.md}}
````

### B.2. Промпт координатора — `gauntlet/adapters/qwen/coordinator.md`
Карточки ядра координатор вызывает как агентов B.4; приёмка — ядро, раздел 2, дословно (раздел 3 промпта).

````markdown
{{file:gauntlet/adapters/qwen/coordinator.md}}
````

### B.3. Роли как агенты Qwen Code
Формат агента Qwen Code: Markdown с YAML-заголовком; поля `name`, `description`, `tools` (белый список), `disallowedTools`,
`model` (`inherit`, `fast`, id модели или `authType:modelId`), `approvalMode`, `background`, а из Claude Code — `maxTurns`,
`hooks`, `mcpServers`, `color`, `permissionMode` [S3; S1: `parseSubagentContent`]. Проект важнее пользователя:
`.qwen/agents/` перекрывает `~/.qwen/agents/` [S3]. Что выбрано и почему:
- `tools` — имена инструментов Qwen Code (`read_file`, `grep_search`, `glob`, `edit`, `write_file`, `run_shell_command`,
  `web_fetch`); у reviewer и карточек записи нет. `agent` нет ни у кого: роль не плодит своих сабагентов.
- `approvalMode` не задан: при разрешительном режиме сессии он не сужает права сабагента («the parent's permissive modes
  still take priority») [S3] — только чтение держат белый список инструментов и хук.
- `background: false` у ролей: главный агент ждёт результата и SubagentStop-хук hardener'а; `background: true` у карточек:
  координатор запускает их параллельно и ждёт уведомлений [S3; S4].
- `hooks` во фронтматтере не используются: проектным агентам они нужны с явным доверием к папке
  (`security.folderTrust.enabled`), одобрение хуков их не покрывает [S2, «Agent frontmatter scope»; S8]. Все хуки — в
  `.qwen/settings.json`.
- `maxTurns` не задан: потолок ходов обрывал бы работу раньше чек-листа.
- `description` — в двойных кавычках: двоеточие с пробелом внутри строки без кавычек ломает YAML заголовка, и Qwen Code
  агента не загрузит (так было в первом черновике hardener'а — поймано проверкой D.5).
- Объём: Qwen Code предупреждает о системном промпте агента длиннее 10 000 знаков и об описании длиннее 1 000 (мягкие
  пределы) [S3, «Limits»]; файлы ниже в них укладываются — роль набора агент читает сам, а не несёт в промпте.

#### specifier — `.qwen/agents/specifier.md`
```markdown
{{file:.qwen/agents/specifier.md}}
```

#### hardener — `.qwen/agents/hardener.md`
```markdown
{{file:.qwen/agents/hardener.md}}
```

#### reviewer — `.qwen/agents/reviewer.md`
```markdown
{{file:.qwen/agents/reviewer.md}}
```

### B.4. Карточки пред-проверки как агенты
Карточка 4.5 ядра (ревью PR) — это роль reviewer (B.3). Каждая карточка без интерактива — тело файла без заголовка
плюс входы (A.5).

#### 4.1 — `.qwen/agents/precheck-mapper.md`
```markdown
{{file:.qwen/agents/precheck-mapper.md}}
```

#### 4.2 — `.qwen/agents/precheck-framework.md`
```markdown
{{file:.qwen/agents/precheck-framework.md}}
```

#### 4.3 — `.qwen/agents/precheck-critic.md`
```markdown
{{file:.qwen/agents/precheck-critic.md}}
```

#### 4.4 — `.qwen/agents/precheck-refuter.md`
```markdown
{{file:.qwen/agents/precheck-refuter.md}}
```

#### 4.6 — `.qwen/agents/review-repro.md`
```markdown
{{file:.qwen/agents/review-repro.md}}
```

### B.5. `.qwen/settings.json` — хуки, разрешения, настройки
```json
{{file:.qwen/settings.json}}
```

Что здесь и почему:
- **`SessionStart` → `session_start.sh`.** Обычный текст из stdout хука SessionStart Qwen Code кладёт в контекст модели
  [S2, «Exit Code Behavior»] — строка статуса `[gauntlet] active - …` видна агенту. Облачные ветки скрипта
  (`CLAUDE_CODE_REMOTE`, запуск `dockerd`) локально не срабатывают.
- **`SubagentStart` → `qwen_hooks.py subagent-start`.** Запоминает в `.git/gauntlet-hook/qwen-agents/`, какому агенту
  принадлежит `agent_id`. Нужен потому, что вызов инструмента внутри сабагента несёт только `agent_id`, а `agent_type`
  есть лишь в SessionStart, SubagentStart и SubagentStop [S2, «Hook Input Structure»; S1: `createBaseInput`]. `agent_id`
  именованного сабагента — `<имя>-<id вызова>`, `agent_type` — имя агента [S1: `hookOpts={agentId:`${subagentConfig.name}-…`,
  agentType:subagentConfig.name}`]; если записи нет, роль набора узнаётся по префиксу.
- **`PreToolUse` → `qwen_hooks.py pre-tool` → `guard.py`.** Matcher — runtime-имена Qwen Code: `write_file`, `edit`,
  `notebook_edit`, `run_shell_command`, `monitor` (оболочка в фоне). Псевдонимы Claude Code (`Bash`, `Write|Edit`) Qwen
  Code в matcher принимает, но в `tool_name` события приходит runtime-имя [S2, «Matcher Patterns»], и `guard.py`, который
  знает только `Edit`/`Write`/`Bash`, без прослойки пропускает всё (тест: 33 случая из 33 — «allow»). Ответ отказа —
  тот же JSON, что печатает `guard.py` (`hookSpecificOutput.permissionDecision: "deny"`) [S2, «PreToolUse»]. Сбой хука
  пропускает вызов (как у набора): в Qwen Code ошибка хука `PreToolUse` — «shouldProceed: true» [S1: `firePreToolUseHook`].
  Вызов через мост `tool_call` приходит в `PreToolUse` под именем целевого инструмента: планировщик подменяет запрос
  до хука [S1: `resolveToolCallBridgeRequest` → `{...request,name:resolution.tool.name}`, затем `runPreToolUse`]; вызовы
  из `exec` (Code Mode, `tools.codeModeOnly`, экспериментальный, по умолчанию выключен) тоже проходят `PreToolUse`
  [S2, «PreToolUse»]. `GAUNTLET_GUARD=off` в окружении запуска выключает прослойку так же, как `guard.py` (прил. 1).
- **`Stop` → `stop_gate.py --task gauntletFast`.** Код выхода 2 Qwen Code читает как блокировку: stderr становится
  `reason`, решение — `deny` [S1: `commandResult`, `convertPlainTextToHookOutput`], `deny`/`block` у Stop — продолжение
  хода с этим текстом как следующим запросом [S1: ветка Stop в `sendMessageStream`, `isBlockingDecision`]. Поле
  `stop_hook_active` — как в Claude Code [S2, «Stop»]. Потолок Qwen Code — 8 блокировок подряд (`stopHookBlockingCap`,
  переопределение `QWEN_CODE_STOP_HOOK_BLOCK_CAP`) [S2] — выше трёх попыток набора, так что отпускает набор.
- **`SubagentStop` с matcher `^hardener$` → `stop_gate.py --task mutationGate`.** Matcher сравнивается с `agent_type` =
  имя агента; блокировка продолжает сабагента с `reason` как заданием, до `stopHookBlockingCap` раз [S1:
  `runSubagentStopHookLoop`].
- **Таймауты.** У командных хуков — в секундах, но значение 1000 и больше читается как миллисекунды [S2, «Command Hooks»;
  S1: `LEGACY_MILLISECOND_TIMEOUT_THRESHOLD=1e3`]. Поэтому 30 минут Stop-хука записаны как `1800000`, 2 часа hardener'а —
  `7200000`, а `180` у SessionStart — секунды.
- **Без `name` у хуков.** «A hook must include a name field to be enabled or disabled individually at runtime. Hooks
  without a name will always execute» [S2, «Approving project hooks»].
- **`permissions`.** Синтаксис Qwen Code: `Bash(<префикс> *)` с границей слова, `Edit(/путь/**)` от корня проекта,
  `Edit(~/…)` от домашнего каталога; `deny` > `ask` > `allow`; `Edit` покрывает `edit`, `write_file`, `notebook_edit`
  [S6, «permissions»]. Правила `Edit` действуют и на «равнозначные» команды оболочки (`cp`, `mv`, `rm`, `chmod` и др.), но не
  на «неизвестные» вроде `git` [S6, «Shell command bypass prevention»] — второй слой охраны человеческих путей, который
  работает и без хуков. Сокращения опций (`--am` вместо `--amend`) префиксные правила не ловят — их ловит guard.
  `allow` — команды, которые набор запускает сам, и чтение для карточек: фоновая карточка не может спросить разрешения,
  и команду без правила Qwen Code ей отклоняет [S7, «Auto Edits Mode»; S2, «PreToolUse»: «background subagents —
  "ask" falls back to "deny"»].
- **`tools.approvalMode: "auto-edit"`**, **`tools.shell.defaultTimeoutMs: 3600000`**: без настройки команда на переднем
  плане обрывается через 120 000 мс, а `timeout` вызова — не больше 600 000 мс [S6, «tools»; S1: `ShellTool`,
  `DEFAULT_FOREGROUND_TIMEOUT_MS=12e4`]; `gauntletFast` и `mutationGate` идут дольше.
- **`context.fileName`** и **`memory`** — решения A.7, пп. 6 и 2.
- **`Edit(~/.env)` и заглушка `.qwen/.env`.** Qwen Code при старте читает первый `.env` проекта (`.qwen/.env`, затем
  `.env`, от каталога запуска вверх), затем `~/.qwen/.env` и `~/.env`, и кладёт переменные в своё окружение, а оно
  целиком уходит хукам [S14, «`.env` files»; S1: `findEnvFiles`, `pushHomeCandidates`, `loadEnvironment`,
  `commandInvocation` → `sanitizeChildEnv(process.env)`]. `GAUNTLET_*` и `QWEN_CODE_SAFE_MODE` не входят в список
  ключей, которые Qwen Code отказывается брать из проектного `.env` [S1: `PROJECT_ENV_HARDCODED_EXCLUSIONS`]. Правка
  проектного `.env` требует нового одобрения хуков [S2, «Approving project hooks»], но `~/.env` в это одобрение не входит
  [S1: `readProjectEnvFiles` пропускает файлы пользователя]. Заглушка (A.2) — ниже.

`.qwen/.env`:
```
{{file:.qwen/.env}}
```

---

## C. Сопоставление

| Механизм gauntlet | В Qwen Code 0.28.4 | Статус | Запасной путь |
|---|---|---|---|
| `CLAUDE.md` → `@gauntlet/CLAUDE.md` | `QWEN.md` с тем же импортом; доходит и до сабагентов [S5; S1] | полностью (как инструкция) | — |
| PreToolUse-хук `guard.py`: человеческие пути | `PreToolUse` + `qwen_hooks.py` → `guard.py`, плюс пути Qwen Code [S2; тест D.5] | полностью, когда хуки одобрены; эвристика и fail-open — как у набора | `permissions.deny` (`Edit(/gauntlet/**)` и др., действует и без хуков) + CI `gauntlet kit unchanged` (для `.qwen/`, `QWEN.md` — после A.7, п. 1) |
| Области ролей (specifier — фичи, hardener — тесты, reviewer — ничего) | роль по `agent_id` (запись SubagentStart, иначе префикс) → `guard.py`; белый список инструментов агента | частично: держит хук; `approvalMode` сабагента не сужает права при разрешительной сессии [S3] | дифф PR (человек), ревьюер, CI-гейты |
| Карточки и прочие сабагенты только читают (ядро, правило 1.6) | прослойка даёт любому сабагенту, кроме specifier и hardener, роль «только чтение» guard'а; у карточек нет инструментов записи | полностью для записи файлов и git через инструменты; эвристика guard для оболочки | приёмка координатора, дифф |
| Заморозка спецификации | `guard.py` без изменений | как в Claude Code | дифф PR |
| Stop-хук: не закончить с красным `gauntletFast` | `Stop` + `stop_gate.py`; код 2 → продолжение с причиной [S1] | полностью, когда хуки одобрены | `QWEN.md`, раздел 5 (лог, `--verify-ran`, строки `> Task`) + CI решает |
| SubagentStop hardener'а (`mutationGate`) | `SubagentStop`, matcher `^hardener$` [S2; S1] | полностью, когда хуки одобрены | hardener сам гоняет `mutationGate` и прикладывает строки `pitSummary`; CI |
| SessionStart: статус, снимок дерева, база | `SessionStart` + `session_start.sh`; текст → контекст [S2] | полностью (облачные ветки скрипта не нужны) | `printenv GAUNTLET_GUARD` и `/hooks` |
| Роли как сабагенты `.claude/agents/*.md` | `.qwen/agents/*.md`, тонкие, роль читается из файла набора [S3] | полностью (определения) | — |
| Параллельные сабагенты пред-проверки | несколько вызовов `agent` в одном сообщении, фон, уведомления [S4] | полностью | — |
| Независимый опровергатель | новый вызов именованного агента: свой контекст, без разговора родителя; не `fork` [S3] | полностью (изоляция контекста); модель та же, если не задать `model:` | другой вендор через маршрут `routing.md` |
| Правило тщательности | `QWEN.md` (для всех), чек-листы в агентах, приёмка координатора; без интерактива — `--json-schema` для формы [S11] | частично: это инструкция и приёмка, а не принуждение | ядро, раздел 2: возврат, перепроверка, опровержение |
| Приёмка отчётов координатором | `send_message` фоновому агенту для доработки, новый вызов для замены [S3; S4] | полностью (как механизм) | — |
| Разрешения `allow`/`deny` | `permissions` Qwen Code, синтаксис `Bash(… *)`, `Edit(/…)` [S6] | частично: префиксы и граница слова, сокращения опций не ловятся | guard |
| Выключение охраны — только человек | `GAUNTLET_GUARD=off qwen` (прослойка проверяет переменную сама, как `guard.py`); `disableAllHooks`, `--safe-mode`, `--bare`, `QWEN_CODE_SAFE_MODE` [S2] | частично: прослойка отклоняет такие команды оболочки и правку настроек; переменные следующей сессии Qwen Code берёт и из `.env` — проектный закрыт заглушкой `.qwen/.env`, `~/.env` — прослойкой и `deny` (B.5) | строка статуса в начале сессии, CI |
| Модель и уровень на сессию | `--model qwen4-max`, `/effort`, `model.reasoningEffort` [S6; S13] | частично: уровня на сабагента нет (`effort` во фронтматтере не поддерживается) [S3] | уровень сессии |
| Координатор создаёт сессии шагов (облако) | нет: облачных сессий нет | нет | `git worktree` + команда запуска владельцу (B.2, раздел 1) |
| Передача решений владельца в идущую сессию | межсессионные сообщения на одной машине: `list_agents`, `send_message` [S15, «Messaging Another Running Session»] | частично: сообщение помечено как от другой сессии, без власти пользователя; может быть удержано | владелец вставляет текст сам |
| Подписка на события PR | нет для локальной сессии (канал GitHub и `/autofix-pr` — не проверены для этой роли) | нет | `/loop 30m` + `gh pr checks`, `gh pr view --comments` |
| Без интерактива (CI, скрипт координатора) | `qwen -p`, `--json-schema`, `--max-session-turns`, `--max-wall-time`, коды 53/55 [S10; S11] | частично: проектные хуки без одобрения не грузятся [S2] | хуки системных настроек (A.3, п. 7) или чтение без хуков (A.5) |
| Гейты и CI (`gauntlet.yml`, `gauntlet-kit.yml`) | не зависят от вендора | полностью | — |
| Мерж запрещён агенту | guard (`gh pr merge`, merge через API) + `deny: Bash(gh pr merge *)` | как в Claude Code | защита ветки |
| Песочница выполнения | `tools.executionSandbox` (bwrap/Landlock) выключает хуки [S9; S1] | нет для сессий задач | для карточек только на чтение — можно, без хуков |

---

## D. Пределы и источники

### D.1. Что не переносится
- **Хуки держатся на одобрении.** Пока владелец не одобрил хуки проекта в этой папке, их нет — ни guard, ни stop-gate.
  Каждое изменение `hooks` в `.qwen/settings.json` (и `.env` проекта) — новое одобрение [S2]. Признак — нет строки статуса;
  `QWEN.md` велит тогда остановиться, но это инструкция модели.
- **Роль сабагента выводится, а не сообщается.** Qwen Code не передаёт `agent_type` в `PreToolUse`; прослойка берёт его из
  записи SubagentStart или из префикса `agent_id`. Смена формата `agent_id` в будущей версии, без записи SubagentStart,
  сделает роли набора «только чтением» (безопасная сторона: hardener и specifier увидят отказ). После обновления — A.6.
- **`approvalMode` сабагента не ограничивает его**, если сессия в разрешительном режиме [S3]; только чтение ревьюера и
  карточек держат белый список инструментов и хук.
- **Хуки во фронтматтере агентов** требуют явного доверия к папке [S2; S8] — не используются.
- **Уровень рассуждений** задаётся на сессию; на сабагента — нет [S3: «`effort` … land in follow-up PRs»]; наследуют ли
  сабагенты уровень сессии — не подтверждено.
- **Облака Claude Code нет:** ни создания сессий координатором, ни Routine, ни подписки на PR; замены — в C.
- **`gauntlet kit unchanged`** не видит `.qwen/`, `QWEN.md`, `AGENTS.md` до решения A.7, п. 1.
- **Песочница выполнения Qwen Code несовместима с хуками** [S9; S1].
- **Окружение сессии собирается и из `.env`-файлов** (в Claude Code такого нет): переменные из них доходят до хуков
  набора. Закрыто заглушкой `.qwen/.env` и охраной `~/.env` (B.5); чей-то `QWEN_HOME` с другим `.env` прослойка
  охраняет по переменной `QWEN_HOME`, только если она задана и в окружении хука.
- **MCP-инструменты** прослойка не судит, как и набор в Claude Code (matcher — только инструменты записи и оболочки);
  правило `deny` для MCP блокирует вызов, но не убирает инструмент [S6].
- **Эвристика guard'а** та же, что в Claude Code: растяжка, а не сейф (README набора, раздел 9). Вложенный `qwen` с
  выключенными хуками прослойка отклоняет только в буквальных формах (`QWEN_CODE_SAFE_MODE=…`, `qwen … --safe-mode`,
  `--bare`).
- **Модель как исполнитель.** О том, насколько тщательно Qwen4-Max проверяет без принуждения, независимых данных нет:
  модель вышла 16.11.2026. Адаптер на это и не опирается — опора на доказательства и приёмку.

### D.2. Известные сбои, относящиеся к жалобе владельца («сабагенты отрабатывают слишком быстро»)
1. **Qwen Code сам подталкивает сабагента к минимуму.** К системному промпту обычного (не интерактивного) сабагента
   дописываются правила «Use tools only when necessary to obtain facts or make changes.» и «When the task is complete,
   return the final result as a normal model response (not a tool call) and stop.» [S1: `renderSubagentSystemPrompt`;
   вызов `createChat(context2)` без `interactive` у `AgentHeadless`]. Ответ адаптера: в каждом агенте необходимость определена
   чек-листом, «первый правдоподобный ответ — не конец работы».
2. **Сабагенты по умолчанию в фоне**, результат приходит позже уведомлением; документация прямо предупреждает: «Do not
   assume a result before the notification arrives» [S3; S4]. Ответ: роли — `background: false`; координатор ждёт все
   уведомления.
3. **Таймаут оболочки 2 минуты**, и модель получает частичный вывод («Command timed out after …ms … Below is the output
   before it timed out») [S1: `ShellTool`; S6]. Ответ: таймаут 60 минут в настройках, правило «оборванная команда — не результат».
4. **Доказательства уходят из контекста:** авто-сжатие около 85 % окна [S6, `context.autoCompactThreshold`], очистка старых
   результатов инструментов после 60 минут простоя или сверх 500 000 символов [S6, `context.clearContextOnIdle.*`],
   обрезка длинного вывода [S6, `tools.truncateToolOutputThreshold`]. Ответ: лог в файл, повтор проверки после сжатия.
5. **Сам вендор описывает эти сбои** в шаблоне политики проверки, «adapted from a production retrospective of a
   multi-agent deployment»: «inferring state from code instead of querying it, treating one satisfied condition as proof,
   and repeating earlier statements as facts» [S16]. И правила верификатора Goals: «Printed text proves only that text was
   printed. A claim that tests pass … needs the corresponding tool result in the transcript» [S12]. Ответ: правило
   тщательности ядра — то же по сути, но с приёмкой координатором.
6. **Без интерактива оболочки нет**, если правило её не разрешило [S7]: сабагент `-p` «проверяет» чтением кода. Ответ:
   «не смог запустить — не проверено».
7. **Причина остановки сабагента.** С 0.25.1 родитель узнаёт, почему сабагент на переднем плане остановился (потолок ходов,
   время): «fix(core): tell the parent model why a foreground subagent stopped (#13624)» [S22]. Ответ: координатор
   всё равно отклоняет отчёт без разделов формата.
8. **Сообщения о сбоях в трекере** (по сниппетам поиска, страницы github.com из этой сессии закрыты — «не подтверждено»):
   сабагент падал, когда последний ход модели был пустым (#3516) [W5]; сабагент «падал на середине» длинной серии задач
   (#5180) [W5]; у стороннего проекта запуск Qwen Code с маленькой локальной моделью (qwen3.5-4b) отчитался об успехе
   без единого вызова инструмента [W6]. Как это относится к `qwen4-max` в 0.28.4 — не подтверждено.
9. **Напоминание «сверни исследование» на длинной серии чтений.** Когда в одном ходе подряд идут вызовы чтения,
   поиска и загрузки (`read`, `search`, `fetch`; любой другой вызов, например оболочка, сбрасывает счёт) и их число
   доходит до `model.maxToolCallsPerTurn` (по умолчанию 100), Qwen Code один раз дописывает к запросу: «System: this
   read-only exploration phase has reached the configured tool-call allowance. Review the information already gathered
   before continuing discovery. … For a read-only investigation, summarize the findings and identify any remaining
   question. Continue tools only to resolve a specific remaining gap or perform necessary verification.» [S1:
   `chunks/chunk-SDZQBXJZ.js`, `TOOL_EXPLORATION_REMINDER`, `ToolExplorationBudget`; S6, `model.maxToolCallsPerTurn`].
   Это ровно работа карточки пред-проверки и ревьюера. В коде напоминание стоит в цикле главной сессии
   (`LlmClient.sendMessageStream`, значит и `qwen -p` из A.5) и в цикле ACP; доходит ли оно до сабагентов внутри
   сессии — не подтверждено. Ответ адаптера: `QWEN.md`, разделы 3 и 6 — напоминание не условие остановки, остановка по
   чек-листу, непокрытое — в «Не проверено». Убрать само напоминание можно только вместе с пределом 1000
   (`model.maxToolCallsPerTurn` ≤ 0) — решение владельца (A.3, п. 8).

### D.3. Не подтверждено
- Характеристики Qwen4-Max (2,4 трлн / 71 млрд, цены, каналы вне Qwen Code) — только вторичные источники [W1–W4].
- Работа адаптера в живом Qwen Code: хуки, роли, межсессионные сообщения — проверены по документации и коду пакета, не
  запуском (A.6).
- Что `--append-system-prompt` работает в интерактивном запуске (документирован общим флагом CLI) [S6].
- Что команда вне `--allowed-tools` в `qwen -p` (режим `default`) отклоняется, а не ждёт ответа [S7].
- Наследует ли фоновый сабагент режим `auto` сессии и её уровень рассуждений [S3 — не сказано].
- Что `report.schema.json` принимает строгий Ajv Qwen Code: схема проверена Python `jsonschema` 4.26 (Draft 2020-12), не Ajv.
- Пишет ли `save_memory` в проектный `QWEN.md` или только в `~/.qwen/` — не выяснено; инструмент запрещён целиком.
- Поведение песочницы Docker/Seatbelt с Gradle и Testcontainers.
- Qwen Code 1.0 Preview, Qoder, QwenWork — не изучались.
- Доходит ли напоминание D.2, п. 9 до сабагентов внутри сессии.
- Показывает ли диалог одобрения хуков содержимое изменённого `.env` (документация: «lists them (with their environment
  settings, …)» — это переменные самих хуков).
- Ловят ли правила `Edit(...)`/`Read(...)` перенаправление вывода (`cat a > b`) в команде, разрешённой префиксом
  `Bash(cat *)` (A.5, `--allowed-tools`).
- Грузятся ли `~/.qwen/.env` и `~/.env` при найденном `.qwen/.env` проекта: по коду 0.28.4 — да (`findEnvFiles` →
  `pushHomeCandidates`), по auth.md — только если в проекте ничего не нашлось; A.6, п. 8 это показывает.

### D.4. Источники (прочитаны 2026-11-24)
Первоисточники — документация по тегу `v0.28.4` (через raw.githubusercontent.com; сайт qwenlm.github.io и github.com из
этой сессии закрыты, страницы сайта собираются из этих файлов) и опубликованный пакет:
- [S1] `@qwen-code/qwen-code@0.28.4`: `npm view @qwen-code/qwen-code` (latest 0.28.4, опубликован 2026-11-22T12:28:27Z,
  engines node ≥ 22); tarball https://registry.npmjs.org/@qwen-code/qwen-code/-/qwen-code-0.28.4.tgz — `README.md`,
  `package.json`, `chunks/chunk-SDZQBXJZ.js` (`createBaseInput`, `firePreToolUseEvent`, `fireSubagentStartEvent`,
  `hookOpts`, `runWithAgentContext`, `commandInvocation`, `commandResult`, `convertPlainTextToHookOutput`, ветка Stop в
  `sendMessageStream`, `nextStopHookBlock`, `runSubagentStopHookLoop`, `renderSubagentSystemPrompt`, `processImports`,
  `validateImportPath`, `findImports`, `parseSubagentContent`, `getHookSystem`, `ShellTool`,
  `LEGACY_MILLISECOND_TIMEOUT_THRESHOLD`, `firePreToolUseHook`), `chunks/chunk-H5QNKQFJ.js` (`isBlockingDecision`),
  `chunks/chunk-FTHZB3Q2.js` (`TOOL_NAME_ALIASES`), `chunks/chunk-SBZFGYYS.js` (`ToolNames`), `chunks/chunk-MVDL2G4R.js`,
  `chunks/chunk-RZHZV5B2.js`, `chunks/chunk-TDV4HR3J.js` (профиль `qwen4-max`), `chunks/chunk-IQHJK65M.js` (флаги CLI),
  `chunks/chunk-WCANCTIJ.js` (`DEFAULT_CONTEXT_FILENAME`, `AGENT_CONTEXT_FILENAME`), `chunks/chunk-62ZGP54Z.js`
  (`getHookApprovalsPath`, `LoadedHookApprovals`, `hashProjectHooks`).
- [S2] Hooks: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/hooks.md
- [S3] Subagents: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/sub-agents.md
- [S4] Agent tool: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/developers/tools/task.md
- [S5] Memory (QWEN.md, импорт, авто-память): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/memory.md
- [S6] Settings (слои, файлы, `permissions`, `tools`, `context`, `model`, флаги CLI): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/configuration/settings.md
- [S7] Approval mode: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/approval-mode.md
- [S8] Trusted folders: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/configuration/trusted-folders.md
- [S9] Sandbox: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/sandbox.md
- [S10] Headless: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/headless.md
- [S11] Structured output: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/structured-output.md
- [S12] Goals: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/goals.md
- [S13] Model providers, «qwen4-max specifics»: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/configuration/model-providers.md
- [S14] Authentication: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/configuration/auth.md
- [S15] Commands (`/effort`, `/hooks`, `/agents`, межсессионные сообщения): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/commands.md
- [S16] Common workflows, «Enforce evidence-based conclusions»: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/common-workflow.md
- [S17] Resident context cost; Rules: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/context-cost.md, …/rules.md
- [S18] Shell, file-system tools, tools intro: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/developers/tools/shell.md, …/file-system.md, …/introduction.md
- [S19] Worktrees: https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/worktree.md
- [S20] Multi-agent coordination (`/coordinate`): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/features/multi-agent-coordination.md
- [S21] Workflow intent (`ultracode`): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/workflow-intent.md
- [S22] CHANGELOG (0.28.0 — #17513 qwen4-max; 0.25.1 — #13624): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/CHANGELOG.md
- [S23] README (происхождение от Gemini CLI v0.8.2, 1.0 Preview): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/README.md
- [S24] README 1.0 Preview: https://raw.githubusercontent.com/QwenLM/qwen-code/v1.0.0-preview/README.md
- [S25] GitHub Actions (`qwen-code-action`, совет игнорировать `.qwen/`): https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/docs/users/integration-github-action.md

Вторичные (сниппеты поиска; страницы не открывались: qwen.ai не разрешается из этой сессии, github.com закрыт):
- [W1] Официальный блог: https://qwen.ai/blog?id=qwen4-max («Qwen4-Max: Your New Teammate Has Arrived», 16.11.2026) — не открыт.
- [W2] https://www.marktechpost.com/2026/11/16/alibaba-qwen4-max-release/
- [W3] https://www.hpcwire.com/aiwire/2026/11/16/alibaba-releases-qwen4-max-with-2-4-trillion-parameters/
- [W4] https://www.technology.org/2026/11/16/alibaba-qwen4-max-flagship-ai-model-safety-cost/
- [W5] https://github.com/QwenLM/qwen-code/issues/3516, https://github.com/QwenLM/qwen-code/issues/5180
- [W6] https://github.com/raullenchai/Rapid-MLX/issues/5124

Чтобы открыть [W1] и сайт документации, владелец добавляет `qwen.ai` и `qwenlm.github.io` в сетевой доступ окружения.

### D.5. Что проверено в этой работе
- **Прослойка против настоящего `guard.py`** (`tests/test_qwen_guard.py`, синтетический репозиторий из набора
  `work/kit`, события в формате Qwen Code 0.28.4, вердикт читается так, как его читает пакет): 33 вызова, каждый двумя
  путями. `guard.py` напрямую — «allow» во всех 33 (Qwen Code называет инструменты иначе). Через `qwen_hooks.py` — как
  задумано: отказ на `gauntlet/`, `.qwen/`, `QWEN.md`, `~/.qwen/`, на `echo >>` и `rm` с параметром `directory`, на
  `git push --force` и `gh pr merge`, на `monitor`, на `QWEN_CODE_SAFE_MODE=1 qwen …` и `qwen --bare`; пропуск правки
  `src/main` кодером и `git clone --bare`; фича — только specifier и только до коммита `spec:`; hardener — `src/test`, не
  `src/main` (и по записи SubagentStart, и по префиксу `agent_id`); reviewer и карточки — чтение, `git diff`,
  `./gradlew gauntletFast`, но не запись и не `git commit`; агент `specifier-lookalike` — только чтение (запись SubagentStart
  важнее префикса); неизвестный сабагент — только чтение; битое событие — пропуск; `selftest` — ok. Итого 75 проверок, 0 сбоев.
- **Хуки набора без прослойки** (`tests/test_qwen_stop.py`, поддельный `./gradlew`, печатающий `> Task` каждой задачи
  гейта): SessionStart — строка статуса уходит в контекст; Stop без изменений — без гейта; красный `gauntletFast` — код 2,
  Qwen Code продолжает ход со строками гейта («attempt 1/3» … «3/3»), четвёртая остановка — отпуск с «work is NOT done»;
  зелёный — остановка; правка только фичи — без гейта; SubagentStop hardener'а — красный `mutationGate` возвращает
  сабагента к работе, зелёный отпускает; `stop_gate.py --verify-ran` принимает полный лог и отвергает лог без задач гейта.
  14 проверок, 0 сбоев.
- Хэши проверенных хуков набора (sha256, первые 16 знаков): `guard.py` e38cd2ed01f2d77a, `stop_gate.py` 6b0a3ffd6cd4ca8c,
  `session_start.sh` d6c05f9506eea66a.
- `report.schema.json`: схема корректна (Draft 2020-12); правильный отчёт принят; без `not_checked`, с пустым
  доказательством, с коммитом `HEAD` — отклонены. `.qwen/settings.json` — валидный JSON.
- **Файлы адаптера по правилам загрузчика** (`tests/test_qwen_files.py`): заголовки всех 8 агентов совпадают с regex
  пакета и разбираются как YAML, `name` = имени файла, `tools` — runtime-имена Qwen Code, `background` — булево, промпт
  и описание в мягких пределах, нет плейсхолдеров `${…}` (их подставляет `templateString` пакета); в `QWEN.md` ровно один
  импорт — `@gauntlet/CLAUDE.md`, а в `gauntlet/CLAUDE.md` нет `@` вне кода, так что импорт берёт его без искажений;
  события в `.qwen/settings.json` — имена событий Qwen Code, matcher'ы компилируются, таймауты в пределах. 63 проверки,
  0 сбоев. Первый прогон поймал описание hardener'а с «: » без кавычек — YAML не разбирался; исправлено.
- Неверный путь к прослойке (первый прогон теста, когда файла ещё не было в репозитории): `python3` выходит с кодом 2, и
  по правилам пакета это отказ — все вызовы через прослойку, даже чтение, получили «deny». Отсюда требование A.3, п. 4:
  запускать из корня.
- Не запускалось: сам Qwen Code (скачанный код только читался), Gradle набора, Ajv.

---

## Приложение 1. `gauntlet/adapters/qwen/qwen_hooks.py`
```python
{{file:gauntlet/adapters/qwen/qwen_hooks.py}}
```

---

## Проверка

Независимая проверка адаптера, 2026-11-24. Проверяющий не автор: свой скачанный пакет, свои запросы к документации,
свои тесты. Всё скачанное — в `round23/verify-qwen/` (пакет и документация только прочитаны, не запускались).

### Что проверено
Источники, прочитанные заново 2026-11-24:
- пакет `@qwen-code/qwen-code@0.28.4` — `npm view` (latest 0.28.4, опубликован 2026-11-22T12:28:27Z, engines node ≥ 22),
  tarball скачан `npm pack`, sha1 `db429919d7bd928c8f27495e24cd504f1a8b56b6` совпадает с `dist.shasum` реестра; все 10
  файлов `chunks/…`, на которые ссылается D.4, в нём есть;
- документация по тегу: `https://raw.githubusercontent.com/QwenLM/qwen-code/v0.28.4/<путь>` — все 26 файлов [S2]–[S25]
  отвечают 200; дополнительно `docs/design/lazy-code-mode.md`, `docs/users/features/{lsp,image-generation,autofix-pr,
  cross-session-protocol,arena,scheduled-tasks,skills,file-changed-hooks}.md`, `docs/developers/tools/monitor.md`.

| Группа утверждений | Проверено | Итог |
|---|---|---|
| Продукт и модель: версия и дата пакета, Node ≥ 22, Apache-2.0 (`LICENSE`), форк Gemini CLI v0.8.2 (README), 1.0 Preview (README ветки, цитата «may change»), #17513 в 0.28.0 и #13624 в 0.25.1 (CHANGELOG), раздел «qwen4-max specifics» (каналы, лестница `low/high/xhigh`, `high` по умолчанию, `medium`→`high`, `max`→`xhigh`, `none`, 262 144 / 131 072, `thinking_budget` 4096/131072/262144), окно 1e6 в `QWENCLOUD_MODELS` | 16 | верно |
| Контекст: `QWEN.md`, `.qwen/QWEN.local.md` после него, `AGENTS.md` по умолчанию, `context.fileName` заменяет список (`setMemoryFilename`), импорт `@` — от файла, глубина 5, только в корне проекта, не в коде (`processImports`, `validateImportPath`, `findCodeRegions`), корень проекта находится и по файлу `.git` (worktree; `findProjectRoot`), в `gauntlet/CLAUDE.md` все 13 знаков `@` (в 6 строках) стоят сразу после обратной кавычки, а `findImports` берёт `@` только после пробела или с начала текста, контекст доходит до сабагента (`renderSubagentSystemPrompt` → `contextFiles`), `.qwen/worktrees/`, `.qwenignore`/`.agentignore`/`.aiignore`, совет GitHub Action про `.gitignore` | 14 | верно |
| Хуки: имена событий; matcher по runtime-id и псевдонимы Claude Code, `Bash` не покрывает `monitor`; `agent_id` только внутри сабагента, `agent_type` только в SessionStart/SubagentStart/SubagentStop (`createBaseInput`, `fire*Event`); `agentId` = `<имя>-<callId>` (`hookOpts`); владелец вызова из `runWithAgentContext`/`resolveHookExecutionOwner`; форма отказа; код 2 → `deny` со stderr, иные ненулевые → пропуск (`commandResult`, `convertPlainTextToHookOutput`); ошибка хука → `shouldProceed: true`; stdout SessionStart → контекст; потолок Stop 8 и `QWEN_CODE_STOP_HOOK_BLOCK_CAP`; `stop_hook_active`; цикл SubagentStop с `reason` как заданием; таймаут ≥ 1000 = мс; `QWEN_PROJECT_DIR`=`CLAUDE_PROJECT_DIR`=cwd; хук без `name` не отключается; одобрение в `hookApprovals.json`, ключ — корень, хэш хуков с `.env` и `settings.env`; `-p` не спрашивает; `--yolo` в CLI; системные хуки без доверия; хуки фронтматтера — только с доверием к папке; `disableAllHooks`/`--safe-mode`/`--bare`/`QWEN_CODE_SAFE_MODE`/`QWEN_CODE_SIMPLE`; `executionSandbox` → нет хуков (`getHookSystem`); «ask» → «deny» в фоне и без интерактива | 25 | верно |
| Сабагенты: поля фронтматтера, значения `model` и `approvalMode`, приоритет разрешительного родителя, фон по умолчанию и порядок `run_in_background` > `background` > `agents.defaultBackground`, `list_agents`/`send_message`/`task_id`/`resume_blocked_reason` (`list-agents-*.js`, task.md), `fork`, пределы 1000/10 000, `effort` не поддерживается, проект важнее пользователя, приписка «Use tools only when necessary…» | 12 | верно |
| Настройки, разрешения, CLI: `tools.approvalMode`, `tools.shell.defaultTimeoutMs` (120 000 по умолчанию), `timeout` вызова ≤ 600 000 (схема `ShellTool`), ключи `memory.*`, `model.maxSessionTurns`, `model.maxToolCallsPerTurn`, `context.autoCompactThreshold` 0,85, `model.reasoningEffort`; синтаксис `Bash(… *)`, `Edit(/…)`, `Edit(~/…)`, `deny`>`ask`>`allow`, мета-категории, правила для равнозначных команд оболочки; флаги `-p`, `-i`, `--model`, `--append-system-prompt`, `--approval-mode`, `--yolo`, `--exclude-tools`, `--allowed-tools`, `--json-schema`, `--max-session-turns`, `--max-wall-time`, `--output-format` (`chunk-IQHJK65M.js`), запятая делит значения (`coerce` в `chunk-OHCM23H2.js`), коды 53/55/130; без интерактива Ask/Auto убирают оболочку и запись | 22 | верно, кроме двух мест ниже |
| Команды и функции: `/effort`, `/hooks`, `/agents`, `/goal` (верификатор не запускает команд, цитата), `/loop`, `/peers`, `qwen sessions ps`, межсессионные сообщения и классы проверки, `/coordinate` — встроенный навык Agent Team, `ultracode` при `tools.workflowsEnabled`, `/plan` без оболочки, цитата шаблона «Enforce evidence-based conclusions» | 12 | верно |
| Что ещё может писать: список `ToolNames` пакета (71 инструмент, `chunks/chunk-SBZFGYYS.js`); мост `tool_call` подменяет запрос на целевой инструмент до `PreToolUse` (`resolveToolCallBridgeRequest`); вызовы из `exec` (Code Mode) проходят `PreToolUse`; `manage_memory` объявляется только при `memory.enableStructuredRecall`; LSP экспериментальный, из проекта не включается; `image_gen` пишет в `.qwen/generated-images/` | 6 | matcher прослойки достаточен |
| Набор: копии ядра (разделы 1–3) в `QWEN.md` и `coordinator.md` сверены по словам — расхождения только в лице глагола и «задание» вместо «карточка» плюс добавки Qwen Code; строки приложения D метода, на которые ссылается B.2, раздел 4, в методе есть; роли — тонкие агенты, читающие `.claude/agents/<роль>.md`; запасной путь «не заканчивай с красным» (`QWEN.md`, раздел 5) с `--verify-ran` | 8 | верно; одна неполнота ниже |

Тесты автора на своём стенде (набор `work/kit`, `make_fixture.sh`): `test_qwen_guard.py` — 0 сбоев, `test_qwen_stop.py` — 0,
`test_qwen_files.py` — 0; перерисовка `render.py` до правок давала `qwen.md` байт в байт. Свои пробы прослойки
(`round23/verify-qwen/mytests/probe.py`, `probe2.py`) — то, чего тесты автора не касались: человеческий
`GAUNTLET_GUARD=off`, `.env`, `~/.env`, `.lsp.json`, имя-двойник роли без записи SubagentStart, `monitor` с перенаправлением.
Двойник роли (агент `hardener-x` без записи SubagentStart) получает права роли по префиксу `agent_id` — так описано
в B.5; определения агентов лежат только в человеческих местах (`.qwen/agents/`, `~/.qwen/agents/` под охраной),
поэтому оставлено. `.lsp.json` агент править может, но сервер из проекта стартует только при явном доверии к папке,
а `tools.lspEnabled` из проекта не включается [lsp.md] — оставлено.

### Что исправлено и почему
1. **`GAUNTLET_GUARD=off` не выключал прослойку.** `qwen_hooks.py` вызывает функции `guard.py`, а не его `main()`, где
   стоит эта проверка (`guard.py`, строка 139). Проба: с переменной правка `gauntlet/` и `rm gauntlet/x` — «deny», хотя
   B.1, B.2 (п. 8) и C обещают владельцу именно этот путь. Исправлено в `main()` прослойки; после правки — «allow» с
   переменной и «deny» без неё; тесты автора зелёные. Это не ослабляло набор, но ломало ручную поддержку набора.
2. **`.env` как обход охраны в следующей сессии.** Qwen Code при старте берёт переменные из первого `.env` проекта
   (`.qwen/.env`, затем `.env`, от каталога запуска вверх) и из `~/.qwen/.env`, `~/.env`, а хук получает всё окружение
   процесса [S14, «`.env` files»; S1: `chunks/chunk-MON6OMIO.js` `findEnvFiles`, `loadEnvironment`;
   `chunks/chunk-SDZQBXJZ.js` `commandInvocation` → `sanitizeChildEnv(process.env)`, который убирает только внутренние
   секреты (`chunks/chunk-C6KSOOGV.js`)]. `GAUNTLET_*` в список запрещённых для проектного `.env` ключей не входят
   (`chunks/chunk-TN3MV4NL.js`, `PROJECT_ENV_HARDCODED_EXCLUSIONS`). Проба: запись `~/.env` и корневого `.env` прослойка
   пропускала. `GAUNTLET_STOP_HOOK=off` там выключил бы Stop-хук набора в следующей сессии, а после исправления 1 и
   `GAUNTLET_GUARD=off` — охрану. `~/.env` в одобрение хуков не входит (`readProjectEnvFiles` пропускает файлы
   пользователя). Исправлено: `~/.env` — конфигурация Qwen Code в прослойке (`qwen_config_paths`) и `Edit(~/.env)` в
   `deny`; новая заглушка `.qwen/.env` (только комментарии) стоит первой и закрывает корневой `.env` и `.env` над
   репозиторием, при этом `.env` приложения агенту по-прежнему доступен; A.2, A.6 (п. 8), A.7 (п. 1), B.5, C, D.1, `QWEN.md`.
3. **Карточка без интерактива (A.5) не была «только чтением».** Текст говорил «оболочка разрешена только для
   перечисленных префиксов», но разрешения складываются из всех слоёв настроек и флага [S6, `permissions.allow`: «Merged
   across all scopes (user + project + system)»; S1: `chunks/chunk-OHCM23H2.js`, `mergedAllow`], а доверие к папкам по
   умолчанию выключено, то есть `.qwen/settings.json` worktree читается без вопроса [S8: «disabled by default … every
   folder counts as trusted»]. Значит, в карточке работали бы `Bash(git *)` (с `git push`, `git commit`),
   `gh pr create *`, `gh pr comment *` проекта, а хуки там не одобрены — guard'а нет. Исправлено: `--exclude-tools`
   добавляет запреты `Bash(git *)`, `Bash(gh *)` (`mergedDeny` берёт `argv.excludeTools`, запрет сильнее разрешения [S6]),
   git-префиксы убраны из `--allowed-tools`, коммит даёт координатор; объяснение переписано.
4. **Командная память.** `memory.enableTeamMemory` пишет в `.qwen/team-memory/` внутри репозитория, а
   `enableTeamMemorySync` при старте сессии сам делает fast-forward pull, коммит и push этой папки [S5, «Team memory»,
   «Automatic git sync»; S6, строки этих ключей]. По умолчанию выключены, но адаптер не закрывал их от пользовательской
   настройки. Исправлено: оба `false` в `.qwen/settings.json`, A.7, п. 2.
5. **Напоминание «сверни исследование» — сбой ровно из жалобы владельца — не было учтено, а A.3, п. 8 говорил, что
   предел 100 «срабатывает только на зацикливании».** На той же отметке длинная непрерывная серия чтений получает текст
   «…For a read-only investigation, summarize the findings…» [S6, `model.maxToolCallsPerTurn`; S1:
   `TOOL_EXPLORATION_REMINDER`, `ToolExplorationBudget`, применение в `LlmClient.sendMessageStream` и в цикле ACP].
   Исправлено: A.3, п. 8; D.2, п. 9; `QWEN.md`, разделы 3 и 6 — напоминание не условие остановки, остановка по чек-листу.
6. **C, «Выключение охраны»:** «переменные процесса агент не меняет» неверно из-за `.env` (п. 2) — строка переписана.
7. **B.2, раздел 4 (`coordinator.md`):** строки приложения D «Набор gauntlet, .claude/, CLAUDE.md, workflow — человека» и
   «Контур: …» не получали `QWEN.md`, `AGENTS.md`, `.qwen/` — добавлена строка замены.
8. B.5 дополнен проверенными фактами о мосте `tool_call` и Code Mode (почему matcher из пяти инструментов достаточен);
   A.6 — шаги 8 (`.qwen/.env` в git, корневой `.env` не грузится) и 9 (`GAUNTLET_GUARD=off` у владельца).

Модель: страницы qwen.ai и www.alibabacloud.com из этой сессии не открываются (DNS закрыт; чтобы открыть, владелец
добавляет хосты в сетевой доступ окружения). Поиск 2026-11-24 показал пресс-релиз «Alibaba Unveils Qwen4-Max: New AI
Teammate for Work, Creativity, and Discovery» (https://www.alibabacloud.com/press-room/alibaba-unveils-qwen4-max) и
сводку: выпуск 16.11.2026, предпросмотр с 11.11, 2,4 трлн параметров, только API QwenCloud, окно 1 млн, без открытых
весов. Число активных параметров (~71 млрд) в увиденном не встретилось — остаётся «не подтверждено», как в D.3.

### Что осталось непроверенным
- Поведение в живом Qwen Code: пакет только прочитан (это непроверенный код), ключа QwenCloud нет; поэтому A.6 обязателен.
- Доходит ли напоминание D.2, п. 9 до сабагентов внутри сессии (в коде найдено только в главном цикле и в ACP).
- Грузятся ли `~/.qwen/.env` и `~/.env` при найденном `.qwen/.env` проекта: код 0.28.4 — да, auth.md — только как
  запасной путь; A.6, п. 8 это показывает.
- Показывает ли диалог одобрения хуков содержимое изменённого `.env`.
- Действуют ли правила `Edit`/`Read` на перенаправление вывода в команде под префиксом `Bash(cat *)`.
- Подхватывается ли `QWEN_CODE_SAFE_MODE`/`QWEN_CODE_SIMPLE` из проектного `.env` (в список запретов не входят; момент
  чтения не выяснен). После исправления 2 проектный `.env` всё равно не грузится.
- Сообщения трекера #3516, #5180 (github.com закрыт), характеристики модели сверх пресс-релиза.
