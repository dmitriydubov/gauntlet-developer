# Бандл эталонного набора gauntlet (ревизия 4.3 от 2026-11-20)

Этот файл — самодостаточный источник эталона для протокола `start` из инструкции «Метод Gauntlet». Он
содержит файлы набора после очистки от имён и примеров эталонного проекта (раздел 8.4 инструкции; ревизия 4 снята с ветки эталона, в которой смержены все правки набора по 2026-10-05): хуки
Claude Code, роли, настройки, `CLAUDE.md`, CI-workflow, конфиги гейтов, инструменты (single-file Java),
ArchUnit-тест, шаблоны, установку и документацию. Стек эталона: Java 21, Gradle, Spring Boot 4. Предметную
область, модули и пакеты нового проекта `start` определяет по его репозиторию.

**Что с чем делать при `start`.**
- Логика хуков (`gauntlet/hooks/`), `install.sh`, роли `.claude/agents/*.md`, `.claude/settings.json`,
  структура `config/` и процесс в `gauntlet/CLAUDE.md` переносятся в любой стек. В эталоне они привязаны к
  Gradle (`./gradlew`, пути `src/main`, `src/test`, `src/acceptanceTest`, `build/`); при `start` раннер и
  пути выносятся в `run.sh` и `paths.*` (раздел 8.1 инструкции).
- Java-часть — образец для порта: `gauntlet.gradle`, `checkstyle.xml`, `pmd-ruleset.xml`, `archtest/`,
  `tools/*.java`, `templates/acceptanceTest/java`.
- Значения `config/gauntlet.properties` (`module`, `basePackage`, `acceptance.glue`, версии инструментов) и
  корневой `CLAUDE.md` — шаблоны, их заполняют по репозиторию.

**Изменения против ревизии 1 (2026-09-26).**
- `gauntlet/CLAUDE.md`: правило 12 — строгая сверка с официальной документацией для всех ролей, документация
  той же версии, что в сборке; раздел «Источники документации» (версия major.minor в пути, запасные пути по
  тегу версии); в отчёте пункты «Сверка по документации», «Перенос в контур», «Оценка»; раздел «Правила
  владельца» (задача для Jira, нумерованные решения, пауза по лимиту токенов, рабочий контур); на остановке
  для утверждения черновик фич не коммитится, даже если Stop-хук платформы просит.
- `.claude/agents/`: reviewer считает решение без источника нужной версии находкой уровня major; specifier и
  hardener сверяют семантику и API по тем же источникам.
- `gauntlet/README.md`, `INSTALL.md`: охраняемое окружение определяется строкой статуса SessionStart; сеть —
  Custom с галкой списка менеджеров пакетов и доменами документации; Docker — `dockerd` напрямую.
- `gauntlet/CLAUDE.md`, правило 12: при недоступном сайте — запасные пути раздела «Источники документации» по
  порядку (javadoc-jar и sources-jar, исходники по тегу, jar в кэше); `README.md`: роли в `.claude/agents/`
  репозитория, потому что только они доходят до облачной сессии.
- Ревизия 2.1: `gauntlet/CLAUDE.md` — определения рабочего и внешнего контуров и поток правок (PR → merge →
  ручной перенос → прогон в рабочем контуре); правило 12 — строгий порядок источников: (1) разрешённые домены
  окружения, (2) запасные пути (javadoc/sources-jar, исходники по тегу, jar в кэше), (3) память модели только
  вместе с тестом в том же изменении и с пометкой «память + тест» в отчёте; в таблице источников — Tomcat,
  PgJDBC, JSpecify, Jakarta EE, Javadoc Hibernate; строки с доменами вне списка окружения идут сразу по
  запасному пути. `README.md` — список доменов для Network access. `reviewer` проверяет порядок источников.
- `gauntlet/gauntlet.gradle`: `gherkinMutantsRun` пересоздаёт каталог результатов после очистки (Gradle 8.14).
- Очистка при сборке: убраны оверлеи модулей эталона, корневой `CLAUDE.md` заменён шаблоном, имена пакетов,
  модулей и библиотек — на `com.example.service`, `adapter`, `shared-lib`, примеры и термины предметной
  области в правилах, ролях, комментариях конфигов, allowlist'ах, шаблонах фич и тестовых данных хуков — на
  нейтральные.

**Изменения против ревизии 2.1 (ревизия 3, 2026-10-04) — опыт серии задач в эталонном проекте.**
- `mutationGate` не засчитывает убитыми мутанты RUN_ERROR (JVM тестов упала на `redefineClasses`, обычно на
  record; PIT считает их обнаруженными): `tools/PitSummary.java` печатает их строкой `UNVERIFIED` и валит гейт,
  пока человек не впишет мутанта в `config/pit-runerror-allowlist.txt` (ключ — `Class#method Mutator # тест`,
  строку заносит человек, прочитав тесты). `mutationGate` зависит от `pitSummary`; `gauntletInfo` показывает
  действующие allowlist'ы. В бандле файл содержит только шапку и закомментированный пример.
- `gauntlet.gradle`: `acceptanceCheck` судит только результаты своего прогона (результаты стираются перед ним) и
  требует хотя бы один исполненный сценарий, если фичи есть; `gherkinMutants` помечает фичу без значений
  «Примеров» как `GHERKIN VACUOUS`; один прогон Gradle на `build/` (блокировка `.gradle/gauntlet-build.lock`,
  ожидание до 1500 с, `-Pgauntlet.lockWaitSeconds`); задачи набора объявлены несовместимыми с configuration
  cache (проект с включённым кэшем не падает); маски `exclude.classes` накрывают вложенные классы (`$*`);
  `dry.exclude` — пути вне поиска дублей.
- Хуки: guard разбирает команду после `do`, `then`, `else`, `{`, `!` (закрыт обход `for … do rm`,
  `if …; then git push --force`) и не срабатывает ложно на `build/gauntlet/` и `./gradlew gauntlet > …`;
  Stop-хук возвращает агенту строки RUN_ERROR и `mutationGate: …`; хук hardener'а переехал из frontmatter роли
  в `SubagentStop` файла `.claude/settings.json` (matcher `^hardener$`) — frontmatter-хуки сабагента в облаке не
  срабатывают; `session_start.sh` поднимает `dockerd` в облачной VM (`service docker start` там падает на ulimit),
  `GAUNTLET_DOCKER=off` отключает это в самопроверке; `selftest.py` — 574 проверки.
- `gauntlet/CLAUDE.md`: «Правила владельца» — задача для Jira (пишет координатор до начала работы, сессия её не
  переписывает), независимый ревьюер Grok AI (каждое замечание проверяется; ответ в треде начинается строкой
  «Ответ Claude Code на комментарий Grok AI»), модель и уровень рассуждений сессий (рекомендация при каждом
  старте; умолчания — в тексте), решения человека нумерованным списком, какие вопросы сессия шага адресует
  координатору (пометки «ответьте здесь» / «переслать координатору» у каждого пункта — и в шаге 3, и в отчёте),
  лимит токенов, рабочий контур; правило 15 — комментарии и Javadoc простым языком с постепенным переходом
  (файл целиком при касании); блок «Среда облачной сессии» (Docker, 429, `publicRepositories`, фоновый прогон);
  «Когда застрял» — RUN_ERROR. «Источники документации»: запасные пути по тегам для закрытых из облака сайтов
  (RabbitMQ, JUnit, Mockito, Docker, Git), грамматики Cucumber Expressions и Gherkin, HikariCP, Docker Compose и
  Dockerfile, хуки и сабагенты Claude Code; правило «страница с major.minor в пути может расходиться с кодом —
  прав код нужной версии, в отчёт идут оба источника». Таблица «Предметная область» — шаблон.
- Роли: hardener — RUN_ERROR и SubagentStop; reviewer — пункт 8 (перенос в контур) и пункт 10 (комментарии
  простым языком); specifier — источники предметной области и ПДн без привязки к проекту.
- `README.md`: строки гейтов (приёмка, `dry.exclude`, RUN_ERROR), таблица лазеек (пустая приёмка, пустая
  фича, два прогона, hardener, RUN_ERROR, ключевые слова shell), раздел 8 — что проверено в эталоне.
- Очистка ревизии 3 ведётся скриптом `clean_kit.py` владельца эталона (каждая замена обязана найтись ровно
  один раз): кроме прежнего — таблица предметной области заменена шаблоном, строки `pit-runerror-allowlist.txt`
  — примером, ссылки на PR и даты решений эталона убраны из ролей, самопроверки и правил.

**Изменения против ревизии 3 (ревизия 4, 2026-10-05) — ещё десять задач серии в эталонном проекте.**
- `gauntlet/CLAUDE.md`, шаг 6 процесса и роль `hardener`: если PIT нечего мутировать (правка только конфигурации
  или вне `src/main`), ручные мутанты hardener предлагает списком (`файл: что изменить → какой тест должен
  упасть`), а применяет, гоняет тесты и откатывает их основная сессия, проверяя перед коммитом, что `src/main`
  чист. Правка продакшен-файлов «временно», в том числе скриптом или патчем, роли запрещена: guard по
  `agent_type` — растяжка, а не сейф.
- `gauntlet/CLAUDE.md`, правило 15: никаких следов разработки вне рабочего контура в коде, комментариях,
  фикстурах, примерах и документах для контура (PR, GitHub, ветки, gauntlet и гейты, сессии и роли, «решение
  владельца», номера шагов и решений плана) — причина правила пишется словами.
- `gauntlet/CLAUDE.md`, «Источники документации»: ревизия доступности из облачной сессии 2026-10-05 — открылись
  www.rabbitmq.com (адреса с версией `/docs/4.1/…`), rabbitmq.github.io, docs.junit.org (`/6.0.3/`),
  site.mockito.org; закрылся docs.liquibase.com (исходники его документации заархивированы — javadoc.io и исходники
  по тегу); `reference/7.0/` Spring Framework перенаправляет на страницу без версии — сверять метатег; raw-вики
  Spring Boot отвечает 404. Новые строки: Actuator, кэш и Testcontainers в Boot; Prometheus (raw); Caffeine и Spring
  Cache; GitHub Actions (raw github/docs); образы контейнеров (API Docker Hub, mirror.gcr.io, adoptium/containers);
  Maven Central (maven-metadata.xml, javadoc.io); Kubernetes (raw). В шапке — список доменов для Network access.
  Патч-версии дописаны там, где их не было.
- `gauntlet/README.md`: список доменов для Network access обновлён по той же ревизии; таблица защит — строка про
  hardener и ручные мутанты.
- Правила процесса, закреплённые в инструкции (ревизия 4): замороженную спецификацию меняет только человек или его
  делегат-координатор отдельным коммитом `spec:` с пометкой о решении; строки allowlist RUN_ERROR вносит владелец
  набора своим PR после собственного прогона `mutationGate` на ветке шага и чтения тестов, а мёртвые строки (метод
  исчез после ревью) убираются следующим PR; контрольный прогон после мержа — в режиме набора по умолчанию
  (`scope=all` показывает долг ещё не пройденных шагов).

**Изменения против ревизии 4 (ревизия 4.1, 2026-10-06).**
- `gauntlet/CLAUDE.md`, правило 15: Javadoc — контракт, а не рассуждение (у класса резюме и 2–6 строк того, чего не
  видно из кода; у метода 1–3 строки; без Javadoc у геттеров и DTO; длинное обоснование — в документ); комментарии
  в файлах конфигурации — по тем же правилам, правка только комментариев доказывается сравнением конфигурации.
- `.claude/agents/reviewer.md`, пункт 10: то же для файлов конфигурации; правка только комментариев без
  доказательства неизменности — находка.
- `gauntlet/gauntlet.gradle`, `pmdGate`: подавления, объявленные в самом `pmd-ruleset.xml` (`violationSuppressXPath`,
  `violationSuppressRegex`, в отчёте PMD — типы `xpath` и `regex`), больше не считаются нарушениями: раньше gate
  считал все подавления, и путь, который шапка набора отводит человеку, не работал. Встроенные подавления (`//NOPMD`,
  `@SuppressWarnings`) — по-прежнему нарушения. Сверено по PMD 7.27.0 (`ViolationSuppressor`, `XMLRenderer`).

**Изменения против ревизии 4.1 (ревизия 4.2, 2026-11-19).**
- Защита от петли «пробел спецификации»: процесс, роли и отчёт различают находки «дефект» (поведение
  против утверждённой спецификации — правится в коде) и «правило» (спецификация не определяет поведение —
  вопрос владельцу, без нового раунда правок). Причина: правка одного случая неопределённого правила
  порождает следующий случай новым заворотом, а гейты его не ловят — мутации закаляют тесты против
  спецификации, а не против ненаписанных правил.
- `gauntlet/CLAUDE.md`: шаг 2 — таблица решений (тип события × наблюдаемый исход) для задач выбора
  значения или версии; шаг 3 — дыра-чек перед заморозкой (каждое правило закреплено сценарием или явно
  «Вне фичи»); шаг 7 — классификация находок и жёсткая остановка после 2 раундов; отчёт — раунды и список
  находок «правило»; «Когда застрял» — остановка на неопределённом правиле.
- `.claude/agents/specifier.md`: таблица решений и самопроверка полноты правил, новый пункт итога.
- `.claude/agents/reviewer.md`: классификация поведенческих находок, тип в формате вердикта.
- Синхронизировано с универсальной инструкцией ревизии 4.2 (разделы 1.1, 3, 4, 5, 8.3, приложение D).

**Изменения против ревизии 4.2 (ревизия 4.3, 2026-11-20) — ревью набора на ошибки и их правки.**
- `tools/IntegrityCheck.java` (B1): освобождение «безобидной» задачи больше не срабатывает, если безобидное
  имя встречается где угодно в строке: `test { dependsOn(jar); enabled = false }` раньше проходило как
  «безобидный jar». Теперь освобождение проверяется только по опенеру блока (текст до первой `{`, после последней `;`).
- `tools/CrapGate.java`: строка allowlist обрезалась по первому `#` — и разделитель `Class#method` тоже,
  из-за чего allowlist не работал. Комментарий теперь начинается с `#` после пробела или в начале строки
  (как в `PitSummary.java`); ключ `Class#method` сохраняется.
- `tools/GherkinMutator.java`: отсутствующий каталог фич — жёсткая ошибка конфигурации (установка создаёт
  его пустым с `.gitkeep`), а не молчаливый «no mutants OK»; пустота проверяется по каждому сценарию
  (`GHERKIN VACUOUS` для сценария без значений «Примеров»), а не по файлу; unescape ячеек атомарный
  (`\\|`, `\\n`, `\\\\` за один проход, без двойного декодирования); имя мутанта в манифесте пишется через `tsv`
  (перенос строки в имени не ломает TSV).
- `hooks/guard.py`: human-only правила действуют внутри обёрток (`sudo`/`env`/`exec`/`command`/`nohup`/`time`
  с их опциями и значениями), inline-кода (`bash -c`, `python3 -c`/`node -e`, включая вложенные
  `os.system`/`subprocess`/`execSync` в кавычках и многострочный `bash -c 'echo ok; git push --force'`),
  `eval`/`source` и текста, передаваемого интерпретатору через pipe. Сегментация внешней команды учитывает
  кавычки (`split_shell`): разделители внутри кавычек не режут команду, inline-payload доходит до рекурсивной
  проверки целым и режется уже по своим настоящим разделителям. `.git/` — зона человека (защита от
  снятия заморозки и подделки `last-green-*`). Закрыты `push --mirror`/`--all`, `push HEAD` на базовой ветке,
  сокращения `--no-verif`; `core.hooksPath` ловится только как реальный глобальный `-c`-конфиг до подкоманды
  git (текст `core.hooksPath` в сообщении коммита не блокируется); пути в другом регистре (`GAUNTLET/…`, `.Claude/…`).
- `hooks/stop_gate.py`: окно повторов SubagentStop теперь больше таймаута задачи (`timeout + 10 мин`):
  медленный `mutationGate` (до 3300 с) раньше сбрасывал счётчик попыток в 1 и петлял бесконечно.
- `.claude/settings.json`: `permissions.deny` дополнен прямыми формами human-only команд (`--amend`,
  `reset --hard`, `push --force`/`-f`/`--force-with-lease`/`--mirror`/`--all`, `checkout -B`, `switch -C`,
  `branch -f`/`-D`/`-M`, `revert`, `update-ref`, `replace`) — дубль хука префиксом.
- `templates/.../example_discount.feature`: пример переведён с процентной скидки на фиксированную
  (`итог = сумма − скидка`): у процентной были эквивалентные мутанты (`0%` и округление), у фиксированной
  изменение любой ячейки «Примеров» меняет исход — 9 мутантов, 0 эквивалентных.
- `tools/PitSummary.java`: в Javadoc зафиксировано, почему `TIMED_OUT` не входит в UNVERIFIED — тесты
  прогнались против мутанта и он их зависнул (бесконечный цикл), это настоящее обнаружение, а не crash.
- `README.md`: таблица лазеек и раздел 8 дополнены новым покрытием guard; счётчик самопроверки 574 → 682;
  честно описан остаток эвристики (подстановка команды `$(which git)`, разворачивание переменной,
  закодированные payload'ы; префиксный deny) и настоящая опора — branch protection + CI + diff PR.
- Универсальная инструкция, п. 10: «Blocker и major типа «дефект» исправляются всегда» — оговорка типа,
  как в шаге 7 процесса: находка типа «правило» уходит владельцу, а не в новый раунд правок.
- Остаток (не закрывается статическим разбором и не заявлен как закрытый): `$(which git) push --force`,
  `G=git; $G push --force`, base64-payload. Guard — растяжка; опора — `integrityCheck`, CI, GitHub branch
  protection базовой ветки и человек, читающий diff PR.

**Правки по ревью Kimi (продолжение ревизии 4.3) — шесть функциональных находок, подтверждены воспроизведением.**
- `hooks/guard.py`: тела подстановок `$(…)`/`` `…` `` вне одинарных кавычек рекурсивно проверяются human-only
  правилами (`command_substitutions`) — закрыт `"$(git push --force)"` (регрессия после правки Codex);
  `env -S`/`--split-string` расщепляется, и исполняемая строка проверяется; `git push` без refspec на базовой
  ветке блокируется (`push.default=simple`). В одинарных кавычках подстановка литеральна — не блокируется.
- `tools/GherkinMutator.java`: сценарий без собственных шагов при непустом Background фичи или правила не
  считался пустым (`hasBackgroundSteps`). **Отменено правкой G6 ревью Grok** (см. ниже): посылка оказалась
  неверной — Gherkin не подмешивает Background к сценарию без шагов, исполнять там нечего.
- `tools/IntegrityCheck.java`: однострочный «безобидный» блок освобождается, только если каждое отключение
  стоит внутри его скобок (`harmlessSingleLine`): `test.enabled = false; jar { }` и `jar { }; test.enabled = false`
  снова нарушение B1.
- `hooks/stop_gate.py`: окно повторов SubagentStop покрывает весь бюджет прогона (`timeout × число модулей`
  плюс запас) — медленный двухмодульный `mutationGate` не сбрасывает счётчик; `.claude/settings.json`: таймаут
  хука SubagentStop 3600 → 7200 с.
- `README.md`: счётчик самопроверки 682 → 733; таблица лазеек и раздел 8 — новое покрытие.
- Регрессии: +36 проверок guard (12 сценариев × 3 раскладки), +15 проверок окна stop_gate (5 × 3), целевая
  Java-регрессия IntegrityCheck (смешанные строки); регрессия GherkinMutator (Background) отменена вместе с K2
  (правкой G6). Пороги и правила гейтов не ослаблены.

**Правки по ревью Grok (продолжение ревизии 4.3) — семь находок, подтверждены воспроизведением на голове PR.**
- `hooks/guard.py` (G1): `piped_shell_code` смотрит весь текст слева от пайпа, когда левая команда — `echo`/`printf`
  (опции `-n`/`-e`/`-E` снимаются), а не только фрагменты в кавычках: закрыт некавыченный `echo git push --force | bash`
  и `printf %s git\ push\ --force | bash` (shell их исполняет).
- `hooks/guard.py` (G2): глубина `$(…)` в `command_substitutions` считается с учётом кавычек (одинарные/двойные,
  escape вне одинарных): `)` внутри кавычек не обрывает тело, хвост подстановки доходит до рекурсии. Закрыт
  `echo "$(python3 -c 'print(")")'; git push --force)"`; `echo "$(date)"` по-прежнему разрешён.
- `hooks/guard.py` (G3): `@` — синоним `HEAD` в refspec push; `push origin @`/`@:main` на базовой ветке блокируются,
  `HEAD:other`/`@:other` базовой веткой не считаются и разрешены (снят over-block на `HEAD:other`).
- `hooks/guard.py` (G4): текущая ветка для push берётся с учётом `-C`/`--git-dir` (`push_branch_dir`/`push_current_branch`):
  `git -C <worktree> push`/`push HEAD` из feature-сессии, когда worktree на базовой ветке, блокируются.
- `hooks/guard.py` (G5): `inline_code_strings` принимает версионные имена `python3.X`, длинные флаги node
  `--eval`/`--eval=`/`--print`/`--print=`, `perl -E` (и `-e`), собирает argv из отдельных кавычек
  (`subprocess.run(['git','push','--force'])`, `os.exec*`, `execSync`) в одну команду для рекурсивной проверки.
- `tools/GherkinMutator.java` (G6): **отмена K2.** Сценарий без собственных шагов всегда освобождён от проверки
  пустоты (`if (sc.body.isEmpty()) continue`); `hasBackgroundSteps` удалён. Посылка K2 («Background выполняется и
  для пустого сценария») неверна: в Gherkin 42.0.1 (cucumber-bom 8.0.1 — дефолт набора) `PickleCompiler.compilePickleSteps`
  при пустом списке шагов сценария возвращает пустой pickle (`if (scenarioSteps.isEmpty()) return new ArrayList<>(0)`),
  Background не подмешивается. Проверено на исходниках и прогоне: пустой сценарий с Background фичи/правила и с
  описанием под Background даёт steps=0. Ложный `GHERKIN VACUOUS` снят; сценарий со своими шагами без «Примеров»
  по-прежнему vacuous (exit 1), outline с «Примерами» по-прежнему даёт мутантов.
- `tools/IntegrityCheck.java` (G7): освобождение B1 проверяет получателя отключения (`receiverIsHarmless`/
  `disabledTargetsHarmless`): свободно только bare `enabled = false`/`setEnabled(false)` или `<безобидная-задача>.enabled`
  внутри её блока; `test.enabled`, `tasks.test.enabled`, `tasks.named("test").enabled` внутри `jar { }` — снова B1
  (замыкание задачи Gradle резолвит неизвестное имя на проект). Правило применено и к многострочному блоку.
  Легитимные `jar { enabled = false }`, `bootJar`/`javadoc`/`tasks.named("jar")` остаются свободными.
- `README.md`: счётчик самопроверки 733 → 808; таблица лазеек и раздел 8 — новое покрытие guard, исправлена строка
  GherkinMutator (пустой сценарий освобождён, а не «не считается пустым»).
- Регрессии: +25 проверок guard (16 на G1/G2/G5 + 9 на G3/G4) × 3 раскладки = +75; целевые Java-регрессии
  GherkinMutator (пустой сценарий + Background фичи/правила/описания → exit 0; свои шаги без «Примеров» → exit 1)
  и IntegrityCheck (17 форм получателя: `test`/`tasks.test` внутри `jar` → B1, легитимные packaging/doc → свободно).
  Итого 733 → 808 проверок. Пороги и правила гейтов не ослаблены.

**Правки по ревью Codex (продолжение ревизии 4.3) — находки V1–V7, подтверждены воспроизведением; полный прогон набора.**
- `install.sh` (V1, V7-3): слияние 4.2 → 4.3 обновляет поля уже установленных gauntlet-хуков на месте
  (command/type/timeout/statusMessage/matcher), а не только добавляет новые — таймаут `SubagentStop` не теряется.
  Внешний таймаут Gradle-хуков масштабируется по числу модулей: `Stop` ≥ `max(1800, timeout × модули + 100)`,
  `SubagentStop` ≥ `max(7200, timeout × модули + 600)`. Права объединяются, `disableAllHooks=false` пинится;
  чужие хуки (не `gauntlet/hooks/…`) не трогаются, дубли не плодятся (идемпотентно). Число модулей считается
  с защитой от пустого/некорректного значения (≥ 1).
- `tools/CrapGate.java` (V2, V6-d, V7-4): запись allowlist `Class#method(desc)` освобождает ровно одну перегрузку;
  `Class#method` без сигнатуры — только когда имя однозначно (`nameCounts == 1`), при перегрузках не освобождает
  ничего и печатает предупреждение с перечнем сигнатур. Пустой `sourcefilename` (JaCoCo debug=false) выводится из
  имени внешнего класса (`OuterSimpleName.java`), метод анализируется, а не пропускается молча. Область `--only`
  сравнивает точный package-relative путь (после `src/main/java/`), а не суффикс — чужой `prices/Catalog.java`
  не подтягивается.
- `tools/IntegrityCheck.java` (V3): получатель `delegate.enabled`/`this.enabled` внутри безобидного блока свободен
  (`receiverIsHarmless` принимает `delegate`/`this`); многострочная скобка (`close > open`) переносит проверку
  отключений на следующую строку, а не обрывает её по концу первой.
- `tools/GherkinMutator.java` (V4, V6-a, V7-1, V7-5): сценарий без собственных шагов (описание или пустой outline)
  не даёт мутантов и не помечается vacuous — проверка по `stepCount` (строки с ключевым словом шага), а не по
  непустому телу; vacuous только сценарий со своими шагами без «Примеров». В verdict `<error>` (исключение/crash)
  и `<skipped>` — ошибка (`MUTANT ERROR`), а не kill; `<failure>` — kill; `<error>` с `UndefinedStepException` —
  kill через undefined. `no-skipped` с отсутствующим каталогом `--features` — exit 1 (misconfigured), пустой
  каталог без фич — exit 0. Перенос строки в тексте шага экранируется в литерал `\n` (`escapeStepText`), в ячейке
  таблицы — `escapeCell`; реальный перенос не разрывает строку шага (без PARSE_ERROR).
- `hooks/guard.py` (V5): сняты over-block — push из worktree после `cd`/`pushd` на своей ветке разрешён
  (`follow_cd` ведёт cwd по сегментам), на базовой — блокируется; `print`/`console.log`/`perl print` с литералом
  `git push` разрешены (строка-литерал, не команда); pipe документа в `python3 script.py`/`node app.js`/
  `python3 -m json.tool`/`bash -c 'echo hi'` разрешён (`reads_stdin_program`), stdin-код `bash -s`/`python3 -`
  по-прежнему блокируется.
- `hooks/stop_gate.py` (V6-c, V7-2): негативный код Gradle (сигнал, например -15) считается красным
  (`worst = max(worst, code if code > 0 else 1)`); rename в `git status --porcelain` разбирается по обоим концам
  (`old -> new`, кавычки снимаются); общий `gauntlet/config/` (не оверлей модуля) затрагивает все модули,
  `gauntlet/config/<module>/` — только свой.
- `gauntlet.gradle` (V6-b, V6-e): `acceptanceTest` объявляет каталог фич входом
  (`inputs.dir(featuresDir).optional().withPathSensitivity(PathSensitivity.RELATIVE)`) — правка фичи запускает
  приёмку; `mutationGate` целит в скомпилированные типы: по каждому изменённому `src/main`-файлу сканируются
  объявления типов (включая package-private и вложенные `Name$*`), а не только имя файла; пустая область —
  `onlyIf { false }`, `scope=all` — `basePackage.*`. `gherkinMutantsRun` не кэшируется (`outputs.upToDateWhen { false }`).
- Сборщик/распаковщик бандла (V7-6): побайтный round-trip — тело файла пишется verbatim, без снятия (`rstrip`) или
  добавления переноса строки; манифест = байтовый размер на диске. Распаковка 30 файлов совпадает с исходниками
  побайтово (`diff -r` пуст).
- `README.md`: счётчик самопроверки 808 → 892; раздел 8 — новое покрытие Codex, обновлён пункт `install.sh`.
- Регрессии: guard print-литерал/stdin (+9) и cd-worktree push (+6) × 3 раскладки = +45; `stop_gate` — негативные
  коды и область модулей (rename/общий config) +13 × 3 = +39; целевые harness'ы `CrapGate` (14), `IntegrityCheck` (24),
  `GherkinMutator` (52), `install.sh` (29), симуляция `gauntlet.gradle` (V6-b/V6-e). Итого 808 → 892 проверки.
  Пороги и правила гейтов не ослаблены.

**Правки по второму раунду ревью Codex (продолжение ревизии 4.3) — находки F1–F14, подтверждены воспроизведением.**
- `tools/GherkinMutator.java` (F1, F2, F11): сбой подготовки сценария (`<failure>`/`<error>` в `@Before` до
  первого шага — недоступная БД, `IOException`/`AssertionError`) считается ошибкой мутанта (`MUTANT ERROR`), а не
  убийством; kill засчитывается только когда упал сам шаг. Замена одной ячейки «Примеров» сохраняет outline
  (интерполяцию Cucumber) и не портит соседнюю колонку: перенос строки в ячейке не превращается в два символа
  `\n`. Неразрывный пробел (U+00A0) в отступе шага не теряется при подсчёте (`stepCount`), outline с одним шагом
  даёт мутанта, а не ноль.
- `tools/CrapGate.java` (F4, F5): пустой/несовпадающий `sourcefilename` (JaCoCo debug=false) не пропускает метод
  молча — имя исходника выводится из имени класса; уникальность лямбд проверяется и по имени, принятому из
  allowlist (две лямбды `Class#method::lambda` не освобождаются одной записью).
- `gauntlet.gradle` (F3): regex поиска объявленных типов находит тип с аннотацией на той же строке
  (`@Deprecated final class StandardPrices` в `Prices.java`); `mutationGate` в режиме `changed` не даёт ложный
  «0 целей» там, где `all` выявляет выживших мутантов.
- `hooks/stop_gate.py` (F6, F7, F13): закоммиченный rename берёт оба пути из `git diff --name-status -M`
  (перенос `core` → `adapter` запускает оба модуля, а не только `adapter`); вложенные сборки
  (`module=core,core/adapter`) — самый длинный совпавший префикс, а не первый по порядку; возраст отчётов
  сравнивается по модулю (`module_report_dirs`), отчёт второго модуля не сбрасывает кэш первого; удалённый
  отслеживаемый файл не выпадает из области путей Git (`existing` сверяется с индексом и HEAD).
- `install.sh` (F8): gauntlet-хук узнаётся по команде запуска (интерпретатор + первый операнд-скрипт
  `gauntlet/hooks/X.py`), а не по пути в любом аргументе — пользовательский `sha256sum …/guard.py` не
  перезаписывается; `matcher` группы обновляется только когда все хуки в ней gauntlet'овские, соседний
  пользовательский хук в общей группе `SubagentStop` не перестаёт запускаться.
- `tools/IntegrityCheck.java` (F9): получатель отключения `it.enabled`/именованный параметр замыкания
  (`archive -> archive.enabled = false`) внутри безобидного блока свободен (`closureParam` опенера); `test.enabled`
  и чужое имя по-прежнему B1.
- `hooks/guard.py` (F10, F14): `cd` внутри подоболочки `( )`/`$( )` не утекает в родительскую оболочку (стек cwd в
  `human_only`/`command_violation`) — push своей ветки после `( cd ../main && git status )` разрешён, реальный `cd`
  в базовую ветку по-прежнему блокирует push; argv-список экранируется (`shlex.quote`), поэтому
  `subprocess.run(['echo', 'example; git rebase'])` — данные, а не команда (реальный `git push --force`/`gh pr merge`
  в argv по-прежнему блокируется).
- Сборщик бандла (универсальная инструкция, §8.4, F12): распаковщик поставляется вместе со сборщиком одной версии
  (канонический побайтный распаковщик вкладывается в заголовок, а не берётся из прежнего бандла — старый формат
  добавлял LF); встроенный round-trip сверяет результат побайтно и отвергает рассинхрон формата, пустой файл и
  0/1/2 завершающих LF.
- `README.md`: счётчик самопроверки 892 → 970; раздел 8 — покрытие второго раунда Codex (F1–F14).
- Регрессии: guard F10/F14 (+12 сценариев × 3 раскладки = +36) и `stop_gate` F6/F7/F13 (+42); целевые harness'ы
  `GherkinMutator` (12), `CrapGate` (8), `IntegrityCheck` (17), `stop_gate` (8), `install.sh` (19), guard (17),
  сборщик (14), regex PIT (15) — 110/110. Итого 892 → 970 проверок. Пороги и правила гейтов не ослаблены.

**Правки по третьему раунду ревью Codex (продолжение ревизии 4.3) — подтверждены реальными Gradle-прогонами.**
- `gauntlet.gradle`/`tools/GherkinMutator.java`: `gherkinMutantsRun` задаёт `cucumber.junit-platform.naming-strategy=long`,
  поэтому `MUTANT mN` сохраняется в JUnit XML и сопоставляется с манифестом. Kill требует assertion с кадром шага
  Cucumber: отсутствие hook-кадров больше не принимается за доказательство шага; Google Truth
  `ComparisonFailureWithFacts` поддержан. Только `UndefinedStepException` обозначает undefined step, а произвольное
  сообщение `IOException("… is undefined")` — ошибка. NBSP учитывается во всех заголовках, включая outline/Examples.
- `gauntlet.gradle`/`tools/CrapGate.java`: в changed-scope индексируются только реально объявленные top-level типы;
  lexer маскирует комментарии/строки, поддерживает аннотации со скобками в литерале, отступы и Unicode-идентификаторы.
  CRAP сопоставляет `debug=false` по точному каталогу пакета и не путает nested `Selection.Legacy` с top-level `Legacy`.
- `install.sh`: только полный сегмент пути `gauntlet/hooks/X` определяет штатный хук (`legacy-gauntlet` остаётся
  пользовательским). Штатный хук из смешанной группы с другим matcher переносится в отдельную группу с эталонным
  matcher; широкий matcher пользовательской группы сохраняется, `mutationGate` не запускается на `reviewer`.
- `tools/IntegrityCheck.java`: освобождение B1 понимает `final Jar archive ->` на строке опенера и `Jar archive ->`
  на следующей строке; `test.enabled = false` по-прежнему B1.
- `hooks/guard.py`: Git проверяется в `event.cwd`, даже если `CLAUDE_PROJECT_DIR` указывает на другое worktree;
  после программы `python -c` аргумент `-e 'git rebase'` — данные argv, а не вторая программа. Контроли base-push
  и настоящего exec по-прежнему блокируются.
- `hooks/stop_gate.py`: начальный dirty-список добавляется в кандидаты изменений — если за сессию файл вернули к
  HEAD, Stop-gate запускает сборку, хотя текущий `git status` уже чист.
- `README.md`: счётчик самопроверки 970 → 985; раздел 8 — покрытие третьего раунда. Java/XML harness 27/27,
  install 14/14; реальные Gradle 8.14.3/JDK 21: PIT 4/4 (`StandardPrices`, `Тариф`), CRAP 5 методов при
  debug=false, Cucumber 8.0.1/7.23.0 — 12/12 kill, `@Before` → errors, отдельный survivor. Пороги не ослаблены.

**Правки по четвёртому раунду ревью Codex (продолжение ревизии 4.3) — пять P2 и один P3.**
- `gauntlet.gradle`/`tools/CrapGate.java`: changed-scope читает объявленный `package` и только реально объявленные
  top-level типы. Каталог больше не определяет FQCN, имя файла не добавляется как тип: класс из `legacy/Prices.java`
  с `package …domain` проверяется, чужой `Rules` из неизменённого `LegacyTypes.java` не подключается. При
  `debug=false` отсутствие объявления не заменяется предположением по имени класса.
- `install.sh`: управляются только корневые `gauntlet/hooks/X` (через `$CLAUDE_PROJECT_DIR`, относительный или
  абсолютный путь проекта) и одиночные команды. `tools/gauntlet/hooks/guard.py` остаётся пользовательским;
  составной `guard.py && ./tools/record-reviewed-files` сохраняется целиком вместе с аудитором.
- `tools/GherkinMutator.java`: Google Truth `AssertionErrorWithFacts` из `assertThat(condition).isTrue()` признаётся
  assertion в шаге (kill), наряду с `ComparisonFailureWithFacts` из `isEqualTo`.
- `hooks/guard.py`: аргументы после Python-скрипта, stdin/`-m MODULE` — данные приложения, а не inline-код;
  опции интерпретатора со значениями (`-W`, `-X`, Node `--require` и др.) не скрывают настоящий `-c`/`-e`.
- `tools/IntegrityCheck.java`: `// comment` после `{` не мешает прочитать typed closure-параметр на следующей строке.
- `README.md`: selftest 985 → 994; Java/XML 32/32, installer 16/16. Реальные PIT: `domain.Prices` найден, чужой
  `Rules` исключён; CRAP: 4 метода в changed и 2 для `Rules.java`; Cucumber 7.23.0 + Truth `isTrue()` — 12/12 kill;
  Gradle-комментарий — только `jar`/`sourcesJar` выключены, `test` зелёный. Пороги не ослаблены.

**Управление версиями проекта и Gauntlet при `start`.**
- `config/gauntlet.properties`: `project.java.version`, `project.gradle.version`, `project.framework.*.version`,
  `project.test.*.version` — фактические версии целевого проекта (шаблон не наследуется); `gate.java.version`
  и локальный `gate.java.home` — независимая JVM инструментов. Версии Gauntlet выбираются по совместимости и
  фиксируются после реального прогона. Обновление зависимостей приложения — только отдельное решение владельца.
- `gauntlet.gradle`: gate JVM применяется к инструментам JavaExec/Exec и acceptance/arch/mutant Test-задачам,
  не меняя toolchain приложения; `gauntletInfo` показывает `project.*`, версии инструментов и executable гейта.
- `.github/workflows/gauntlet.yml`: CI читает `gate.java.version` (fallback `project.java.version`), вызывает
  wrapper обнаруженной версии Gradle, печатает `--version` и `gauntletInfo`.
- `.claude/agents/*`, `CLAUDE.md`, `INSTALL.md`, `README.md`: роли и источники используют `project.*` и фактически
  разрешённые зависимости; убрана автоматическая рекомендация обновлять JUnit приложения ради Cucumber.
- Проверено: Java 17 + Gradle 8.14.3 + JUnit 5.12.2 + Cucumber 7.23.0 с JVM 21 гейта — 12/12 kill, манифест
  приложения не изменился; второй проект — `gauntletInfo`/`integrityCheck` и PIT 8/8 OK; YAML workflow распарсен (7 шагов),
  чтение CI-версии проверено. GitHub Actions в этой среде не запускался.

## Как распаковать (Claude выполняет это на шаге 2 протокола `start`)

Каждый файл лежит между строками `===== BEGIN FILE <путь> =====` и `===== END FILE <путь> =====`.
Скрипт ниже пишет их на диск в текущий каталог, сохраняя пути. При `start` запускайте его во временном
каталоге вне репозитория: набор попадает в проект только после адаптации под стек.

```python
import re, os, sys
bundle = open(sys.argv[1], encoding="utf-8").read()
for m in re.finditer(r"^===== BEGIN FILE (.+?) =====\n(.*?)\n===== END FILE \1 =====$", bundle, re.S | re.M):
    path, body = m.group(1), m.group(2)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("wrote", path)
```

Запуск: `python3 extract_bundle.py gauntlet-kit-bundle.md`. После распаковки: `chmod +x gauntlet/hooks/*.sh
gauntlet/hooks/*.py gauntlet/install.sh`. Файлы `.claude/*`, `CLAUDE.md` и `.github/workflows/gauntlet.yml`
в эталоне уже установлены (`install.sh` их когда-то перенёс из `gauntlet/claude` и `gauntlet/ci`); для новой
установки положите их обратно в `gauntlet/claude/` и `gauntlet/ci/`: их переносит `install.sh` последним шагом
установки (раздел 8.1, шаг 3 инструкции). Корневой `CLAUDE.md` в бандле — шаблон: описание модулей заполняется по репозиторию.

## Манифест

- `.claude/agents/hardener.md` (4233 байт)
- `.claude/agents/reviewer.md` (7509 байт)
- `.claude/agents/specifier.md` (5026 байт)
- `.claude/settings.json` (2211 байт)
- `.github/workflows/gauntlet.yml` (2827 байт)
- `CLAUDE.md` (279 байт)
- `gauntlet/CLAUDE.md` (64492 байт)
- `gauntlet/INSTALL.md` (13962 байт)
- `gauntlet/README.md` (50708 байт)
- `gauntlet/archtest/gauntlet/architecture/ArchitectureTest.java` (7906 байт)
- `gauntlet/config/architecture.properties` (1420 байт)
- `gauntlet/config/checkstyle.xml` (4593 байт)
- `gauntlet/config/crap-allowlist.txt` (924 байт)
- `gauntlet/config/gauntlet.properties` (6379 байт)
- `gauntlet/config/integrity-allowlist.txt` (445 байт)
- `gauntlet/config/pit-runerror-allowlist.txt` (1485 байт)
- `gauntlet/config/pmd-ruleset.xml` (11398 байт)
- `gauntlet/gauntlet.gradle` (38557 байт)
- `gauntlet/hooks/guard.py` (44247 байт)
- `gauntlet/hooks/selftest.py` (69006 байт)
- `gauntlet/hooks/session_start.sh` (3116 байт)
- `gauntlet/hooks/stop_gate.py` (20644 байт)
- `gauntlet/install.sh` (9541 байт)
- `gauntlet/templates/acceptanceTest/java/com/example/service/acceptance/CucumberSpringConfiguration.java` (615 байт)
- `gauntlet/templates/acceptanceTest/resources/features/example_discount.feature` (1258 байт)
- `gauntlet/tools/CrapGate.java` (23561 байт)
- `gauntlet/tools/DryGate.java` (6538 байт)
- `gauntlet/tools/GherkinMutator.java` (42883 байт)
- `gauntlet/tools/IntegrityCheck.java` (22678 байт)
- `gauntlet/tools/PitSummary.java` (11633 байт)

## Файлы

===== BEGIN FILE .claude/agents/hardener.md =====
---
name: hardener
description: Mutation-hardens a change that already passes gauntletFast - kills surviving PIT mutants, covers uncovered lines, and fixes hollow step definitions found by Gherkin mutation. Edits test code only. Use after implementation, before review.
tools: Read, Grep, Glob, Edit, Write, Bash
model: inherit
color: orange
---

You are the **hardener**. The code already passes `./gradlew gauntletFast`; your job is to prove the
tests would notice if it were wrong. (Role adapted from Robert C. Martin's swarm-forge hardener.)

## Loop
1. `./gradlew mutationGate` — PIT on the classes changed against the base branch. `pitSummary` lists
   every `SURVIVED` and `NO_COVERAGE` mutant as `Class:line method() - description`, and every
   `RUN_ERROR` mutant as `UNVERIFIED` (the test JVM crashed on `redefineClasses`, usually on a record;
   PIT counts it as detected, the gate does not). A `RUN_ERROR` mutant outside
   `gauntlet/config/pit-runerror-allowlist.txt` fails the gate (`mutationGate: N RUN_ERROR mutant(s) …`):
   read the tests and name the assertion that fails for exactly that mutation; if there is one, report
   the allowlist line `Class#method Mutator # test` for the human to add; if there is none, write the
   test that would kill it - the crash hides a weak test.
2. For each survivor, write or sharpen a unit test whose assertion fails for that exact mutation:
   a changed boundary (`<` → `<=`) needs a test at the boundary; a removed call needs an assertion on
   its effect; a replaced return value needs an assertion on the value.
3. Cover `NO_COVERAGE` lines with focused unit tests - or report them as dead code.
4. `./gradlew gherkinMutation` — a surviving Gherkin mutant means a step definition ignores a parameter
   or asserts too weakly. Fix the step definition in `src/acceptanceTest/java` (test code).
5. Repeat until both are green. A SubagentStop hook (`.claude/settings.json`, matcher `hardener`) re-runs
   `mutationGate` before you may finish.

## Rules
- You may only edit test code: `src/test/**` and `src/acceptanceTest/java/**` of the guarded module(s)
  (a hook enforces it). Run Gradle from the module's directory when `module` is set.
  If a survivor can only be killed by changing production code (dead code, redundant condition),
  report it with the exact location and a proposed change - do not make it.
- **Manual mutants are proposed, not applied.** When PIT has nothing to mutate (a configuration-only
  change, a change outside `src/main/java`), do not edit production files "temporarily", not even through
  a script, a patch or a stash: the role scope is the rule, the hook is only a tripwire, and a mutant left
  behind would be committed as code. List the mutants you would try as `file: what to change → which test
  must fail` in your final message; the main session applies each one, runs the tests, reverts it and
  checks that `git diff --stat -- '*/src/main/*'` is clean before committing.
- Never weaken or delete an existing assertion, never tag a test `no-mutate` to hide a survivor.
- Assert on behaviour, not on implementation details (no verifying private calls, no reflection).
- Check the API of the project's test libraries against the official sources in gauntlet/CLAUDE.md,
  section «Источники документации». Use the `project.*` versions recorded by start
  (`./gradlew gauntletInfo`) and the versions the build actually resolves - not the reference versions or
  memory - and name the source in your final message.
- Tests that need a database or a broker use the module's existing Testcontainers support; they fail without Docker - start `dockerd` as gauntlet/CLAUDE.md says rather
  than skipping anything. No `Thread.sleep`: wait with Awaitility and a timeout. Test data carries no real
  personal data.
- If you believe a mutant is equivalent (no test could ever detect it), explain why and leave it for the
  human, who may add an exclusion.

## Final message
Mutation numbers before/after (killed / survived / no coverage / RUN_ERROR), tests added, survivors you
could not kill and why, RUN_ERROR mutants with the allowlist line and the killing test for each,
production-code changes you recommend.

===== END FILE .claude/agents/hardener.md =====

===== BEGIN FILE .claude/agents/reviewer.md =====
---
name: reviewer
description: Adversarial, read-only reviewer of the current change. Looks for what the gauntlet cannot see - wrong behaviour the spec implies, security and data-protection problems, transactional and concurrency bugs, gate gaming. Returns numbered recommendations or APPROVED. Never edits files.
tools: Read, Grep, Glob, Bash
model: inherit
color: red
---

You are the **reviewer** - the last pair of eyes, because the human does not read the code. The
gauntlet already proves the code is small, tested, mutation-hardened and follows the dependency
rules. Your job is what metrics cannot catch. Be critical, concrete and brief. (Inspired by the
coder/reviewer loop of Robert C. Martin's swarm-forge "adversaries" branch.)

## Gather evidence first
- The whole change, committed or not: `git diff $(git merge-base <base> HEAD)` (working tree against the
  merge base) plus the untracked files from `git ls-files --others --exclude-standard` - read those files
  directly. Base is given in your prompt; default `origin/main`.
- The approved feature files touched by the change, and the module's architecture policy `gauntlet/config/<module>/architecture.properties` (fallback: the common
  template `gauntlet/config/architecture.properties`; `./gradlew gauntletInfo` shows which applies).
- When the change relies on framework behaviour, property names or an API contract: the official
  reference for the `project.*` versions recorded by start in `gauntlet/config/gauntlet.properties`
  (`./gradlew gauntletInfo` prints them) and for the versions the build actually resolves. Use the matching
  official documentation, or offline metadata and `javap` on the jars in the build cache. Do not review API use
  from memory or inherit the reference project's versions. Allowed sources are listed in
  gauntlet/CLAUDE.md, section «Источники документации». A decision that depends on framework, library
  or protocol behaviour without a cited official source of the resolved version (in the report's
  «Сверка по документации» or in the code's Javadoc), or backed by a source outside that list, is a
  **major** finding: name the decision and the source it needs.
- The module's own rules (its `CLAUDE.md`: packages, transactions, broker acknowledgements, personal data,
  tests) and the domain documents listed in gauntlet/CLAUDE.md, «Предметная область».
- You may run `./gradlew gauntletFast --continue` from the module's directory to confirm the gates; you
  must not change files or git state (a hook enforces it).

## Look for
1. **Behaviour vs spec**: cases the scenarios imply but nothing tests; step definitions that ignore a
   parameter or assert on something weaker than the observable result. Classify every behavioural finding:
   **«дефект»** — the behaviour contradicts the approved spec or an owner decision (fixable in code);
   **«правило»** — the spec does not define the behaviour the code decides (version selection, ordering,
   refusal fate, a cleared field versus an absent one). A «правило» finding names the rule, the observable
   outcomes and the variants with a recommendation; it goes to the human, never into another fix round —
   patching one case of an undefined rule invites the next case as a new finding.
2. **Security & data protection**: missing authorisation checks, injection (SQL/JPQL, log, header),
   personal or other sensitive data in logs, errors or test fixtures, secrets in code, unsafe deserialisation,
   SSRF in outbound calls, overly broad CORS.
3. **Integration robustness**: transaction boundaries, idempotency of message and HTTP handlers,
   retries and timeouts on outbound calls, ordering and concurrency, pagination and limits; caching:
   missing on a hot path that re-reads the same rarely changing data, present without a key strategy,
   TTL, size bound and invalidation, or put on top of data that must be fresh.
4. **Design**: adapters re-implementing a domain rule instead of calling it, framework types leaking
   into the domain, dead code, speculative generality, misleading names.
5. **Gate gaming**: code shaped to satisfy a metric rather than express behaviour - flag it explicitly.
6. **SOLID, by principle**: a class with two reasons to change (SRP); a type switch or if-chain that
   grows with every new case (OCP); an implementation that narrows the contract or throws
   `UnsupportedOperationException` (LSP); an interface the client uses only a part of (ISP); a service
   that depends on a concrete class, a framework type or `new` where an abstraction belongs (DIP).
   Name the principle and the place.
7. **API use vs the official reference**: property names, annotation attributes, transaction, retry,
   listener and scheduling semantics that differ from the documented behaviour of the resolved
   versions; guessed or deprecated API; a hand-rolled mechanism where Spring or the JDK has a
   standard one; a version assumption from an older Spring Boot.
8. **The company contour** (see gauntlet/CLAUDE.md, «Рабочий контур»): a new dependency or plugin without
   coordinates in the report; production code or unit tests depending on `src/acceptanceTest` or `gauntlet/`;
   a hard-coded image registry or repository URL; a change to the repository switch in `settings.gradle`;
   an artifact the company registry is known not to serve; deleted or renamed
   files missing from the report's transfer list.
9. **Anti-patterns and readability the tools cannot measure**: boolean flag parameters, null instead
   of Optional or an empty collection, a catch-all outside a system boundary or without a decision
   (log + reject/requeue/retry/rethrow), swallowed failures, mutable shared state, names that do not
   say what the thing is in the domain, mixed levels of abstraction in one method, comments that
   explain bad code, a new integration path without idempotency, timeouts or limits, a cheaper or
   safer design the author did not consider.
10. **Comments and Javadoc in plain language** (gauntlet/CLAUDE.md, rule 15): in every file the change
   touches, a reader in the company network -
   without the plan, the ТЗ or gauntlet - must understand what the thing is and why from the comment
   alone. Flag plan or document codes instead of domain words (R-05, ТЗ-5, step numbers), telegraphic
   dash chains, «см. раздел … в CLAUDE.md», restated code, edit history («после PR #N»). Old Javadoc in
   an untouched file is not a finding; old Javadoc in a touched file is. The same applies to comments in
   configuration files that go to the company network (`application.yml`, `Dockerfile`,
   `docker-compose.yml`, migration changeSets, build scripts): one or two sentences on why the value is what
   it is, no restated key or value, no document codes. A change that only rewrites such comments must prove
   that values, keys and instructions did not change (YAML tree, `docker compose config`, Dockerfile lines
   without comments) - flag a missing proof.

## Output (exactly this shape)
```
VERDICT: APPROVED | CHANGES REQUESTED
1. [blocker|major|minor] [дефект|правило] path/File.java:123 - problem - risk - expected correction
2. ...
Residual risks: <what you could not verify>
```
Every item must be actionable. For a «правило» item the expected correction is a spec decision for the
human, not a code edit. No praise, no restating the diff.

===== END FILE .claude/agents/reviewer.md =====

===== BEGIN FILE .claude/agents/specifier.md =====
---
name: specifier
description: Turns an informal feature request into Gherkin feature files — the executable specification the human approves in the chat. Use for the specification step of every behaviour change (see gauntlet/CLAUDE.md), or whenever acceptance criteria must be written or changed. Never writes production or test code.
tools: Read, Grep, Glob, Edit, Write, Bash
model: inherit
color: blue
---

You are the **specifier**. You own externally visible behaviour: the Gherkin files in
`<module>/src/acceptanceTest/resources/features/` of the guarded modules. The human approves every change you make, in the chat,
before any code is written; the coder must then make your scenarios pass without editing them.
(Role adapted from Robert C. Martin's swarm-forge specifier.)

## How to write the specification
- Describe behaviour at the service boundary: HTTP requests/responses, messages consumed and
  published, state observable through the API. Never name classes, tables or frameworks.
- Keep scenarios concise and deterministic: fixed dates and ids, no "now", no randomness.
- One feature file per behaviour area. Give every scenario a stable, descriptive name.
- **Every value that matters goes into an Examples table** (Scenario Outline). Gherkin mutation only
  mutates Examples values, so a literal written into a step is never checked.
- Prune: no Examples column whose value is identical in every row, no column that does not affect the
  outcome. Move setup shared by all scenarios of a feature into `Background`.
- Cover the rules, the boundaries (just below / at / above a limit) and the error cases the request
  implies. Ask instead of inventing business rules.
- **Selection rules need a decision table.** When the task picks a value or a version among several
  (row history, echo, redelivery, refusal, deletion, a cleared field versus an absent one), return a
  decision table: event type × observable outcome (message sent, state saved). Every row becomes a
  scenario with its values in Examples. Before returning, check completeness: every rule the code must
  decide is pinned by a scenario or explicitly declared out of scope («Вне фичи») with an accepted risk;
  a rule neither pinned nor declared is an open question for the human, never a decision left to the code.
- Business rules come only from the domain sources in gauntlet/CLAUDE.md, section «Источники
  документации» → «Предметная область»: the module's rules (its `CLAUDE.md`) and the project's
  specifications (ТЗ, integration points, data structures; PDFs, read them with the Read tool page by page). Name the
  document and section next to every rule a scenario pins down. Documents disagree with each other or with
  the code - list it as an open question, do not pick a side.
- Personal data (full name, birth date, e-mail, identifiers of real people) never appears in scenarios as real values:
  use obviously fictional ones, and pin down that such data does not leave the service where the rules say so.
- When a scenario relies on protocol or framework semantics (broker confirms and returns, redelivery,
  dead-lettering, HTTP status codes, transaction outcomes), confirm them in the official sources listed
  in gauntlet/CLAUDE.md, section «Источники документации». Use the `project.*` versions recorded by start
  (`./gradlew gauntletInfo`) and the versions the build actually resolves - not the reference versions or
  memory - and name the source next to the assumption in your final message.
- Reuse existing step wording: grep other feature files and the step definitions in
  `src/acceptanceTest/java` first. Consistent phrasing keeps step definitions DRY.
- Features in this repository are written in Russian: start every file with `# language: ru` and use
  Функция / Предыстория / Структура сценария / Примеры / Дано / Когда / Тогда / И. The domain terms
  are the ones used in the module's rules.

## Limits
- You may only write under `<module>/src/acceptanceTest/resources/features/` of the guarded modules
  (`module` in gauntlet/config/gauntlet.properties; a hook enforces it).
- Do not commit. Uncommitted feature files are a draft the human can still change; the main agent
  commits them after the human's "yes", and from that moment the guard freezes them for everyone.
  If the branch already holds a spec commit, you cannot edit the feature files: report what should
  change and why, and let the human decide.
- You may run `./gradlew acceptanceTest` from the module's directory to see undefined
  steps; do not implement them.
- You cannot approve your own specification.

## Final message
1. Files created or changed.
2. One line per scenario: what it pins down.
3. Open questions and assumptions the human must confirm before approving.
4. The decision table for selection rules (event type × observable outcome), or «нет правил выбора».

===== END FILE .claude/agents/specifier.md =====

===== BEGIN FILE .claude/settings.json =====
{
  "disableAllHooks": false,
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/gauntlet/hooks/session_start.sh\"",
            "timeout": 180
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/gauntlet/hooks/guard.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/gauntlet/hooks/stop_gate.py\" --task gauntletFast --max-attempts 3 --timeout 1700",
            "timeout": 1800,
            "statusMessage": "Gauntlet: running ./gradlew gauntletFast..."
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
            "command": "python3 \"$CLAUDE_PROJECT_DIR/gauntlet/hooks/stop_gate.py\" --task mutationGate --max-attempts 2 --timeout 3300",
            "timeout": 7200,
            "statusMessage": "Gauntlet: running ./gradlew mutationGate for the hardener..."
          }
        ]
      }
    ]
  },
  "permissions": {
    "allow": [
      "Bash(cd:*)",
      "Bash(./gradlew:*)",
      "Bash(git:*)",
      "Bash(gh pr create:*)",
      "Bash(gh pr view:*)",
      "Bash(gh pr checks:*)",
      "Bash(gh pr comment:*)"
    ],
    "deny": [
      "Bash(gh pr merge:*)",
      "Bash(git rebase:*)",
      "Bash(git filter-branch:*)",
      "Bash(git filter-repo:*)",
      "Bash(git update-ref:*)",
      "Bash(git replace:*)",
      "Bash(git revert:*)",
      "Bash(git commit --amend:*)",
      "Bash(git reset --hard:*)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(git push --force-with-lease:*)",
      "Bash(git push --mirror:*)",
      "Bash(git push --all:*)",
      "Bash(git checkout -B:*)",
      "Bash(git switch -C:*)",
      "Bash(git branch -f:*)",
      "Bash(git branch -D:*)",
      "Bash(git branch -M:*)"
    ]
  }
}

===== END FILE .claude/settings.json =====

===== BEGIN FILE .github/workflows/gauntlet.yml =====
# Gauntlet gate for pull requests. Installed to .github/workflows/gauntlet.yml by gauntlet/install.sh.
# start records project.* and gate.java.* in the properties; CI uses gate Java and the project's Gradle wrapper.
# The agent's hooks run only inside Claude Code; this job is the check nobody can skip.
name: gauntlet

on:
  pull_request:
  workflow_dispatch:

concurrency:
  group: gauntlet-${{ github.ref }}
  cancel-in-progress: true

jobs:
  gauntlet:
    name: gauntlet
    runs-on: ubuntu-latest
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0                      # scope=changed needs the merge base with the base branch

      - name: Resolve the configured gate JVM
        id: versions
        run: |
          version=$(sed -n 's#^[[:space:]]*gate.java.version[[:space:]]*=[[:space:]]*##p' gauntlet/config/gauntlet.properties | tail -1)
          if [ -z "$version" ]; then
            version=$(sed -n 's#^[[:space:]]*project.java.version[[:space:]]*=[[:space:]]*##p' gauntlet/config/gauntlet.properties | tail -1)
          fi
          if [ -z "$version" ]; then
            echo '::error::Set gate.java.version (or project.java.version) in gauntlet/config/gauntlet.properties'
            exit 1
          fi
          echo "gate_java=$version" >> "$GITHUB_OUTPUT"

      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: ${{ steps.versions.outputs.gate_java }}

      - uses: gradle/actions/setup-gradle@v4

      - name: Resolve the base branch and the module
        id: base
        run: |
          base="${{ github.base_ref }}"
          if [ -z "$base" ]; then
            base=$(sed -n 's#^[[:space:]]*baseRef[[:space:]]*=[[:space:]]*origin/##p' gauntlet/config/gauntlet.properties | tail -1)
          fi
          modules=$(sed -n 's#^[[:space:]]*module[[:space:]]*=[[:space:]]*##p' gauntlet/config/gauntlet.properties | tail -1 | tr ',' ' ')
          echo "ref=origin/${base:-main}" >> "$GITHUB_OUTPUT"
          echo "modules=${modules:-.}" >> "$GITHUB_OUTPUT"
          git fetch --no-tags origin "${base:-main}"

      - name: Run the gauntlet in every guarded build
        run: |
          status=0
          for dir in ${{ steps.base.outputs.modules }}; do
            echo "::group::gauntlet in $dir"
            ( cd "$dir" && ./gradlew --version && ./gradlew gauntletInfo && ./gradlew gauntlet --continue --console=plain -Pgauntlet.baseRef="${{ steps.base.outputs.ref }}" ) || status=1
            echo "::endgroup::"
          done
          exit $status

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: gauntlet-reports
          path: |
            **/build/reports
            **/build/gauntlet
          if-no-files-found: ignore

===== END FILE .github/workflows/gauntlet.yml =====

===== BEGIN FILE CLAUDE.md =====
# <проект>

<Кратко: модули репозитория, что делает каждый и какие из них охраняет gauntlet
(`module=` в gauntlet/config/gauntlet.properties). Заполняется при установке.>

@gauntlet/CLAUDE.md

===== END FILE CLAUDE.md =====

===== BEGIN FILE gauntlet/CLAUDE.md =====
# Gauntlet: как здесь ведётся разработка

Код пишет агент. Человек код не читает: он читает спецификацию (Gherkin), отчёт о гейтах и изменения
самого набора `gauntlet/`. Итоговое решение по каждой задаче принимает человек — merge PR в GitHub.
Работа считается сделанной только когда `./gradlew gauntlet` зелёный, ветка запушена и PR открыт.
Никогда не сообщай об успехе, не выполнив проверку.

## Репозиторий
<Заполняется при установке: какие модули (Gradle-сборки) есть в репозитории, что делает каждый, какие
из них охраняет gauntlet (`module=` в `gauntlet/config/gauntlet.properties`), где лежат правила модуля
и документы предметной области. Если у модуля есть свой `CLAUDE.md`, он главный по предметной области и
правилам кода; по процессу, веткам, проверкам перед коммитом и лимитам размера главный этот файл: там,
где они расходятся, действует gauntlet.>

## Гейты

| Команда | Что проверяет |
|---|---|
| `./gradlew gauntletFast` | integrity (нет отключённых тестов и подавлений) → Checkstyle (размер, структура, CC ≤ 3) → PMD (антипаттерны) → unit-тесты → архитектура (ArchUnit) → приёмка (Cucumber, ни одного skipped) → CRAP ≤ 8 → дубли |
| `./gradlew mutationGate` | PIT по изменённым классам: каждый покрытый мутант убит (test strength 100 %), покрытие строк мутируемых классов ≥ 80 %; мутант RUN_ERROR (JVM тестов упала на `redefineClasses`, обычно на record; PIT считает его обнаруженным) убитым не засчитывается — только по строке `gauntlet/config/pit-runerror-allowlist.txt`, которую человек добавил, прочитав тесты |
| `./gradlew gherkinMutation` | каждое значение из Examples мутируется по очереди; какой-то сценарий обязан упасть |
| `./gradlew gauntlet` | всё вместе |

Область проверки — diff относительно базовой ветки плюс незакоммиченные файлы (`baseRef` в
`gauntlet/config/gauntlet.properties`). Если там задан `module` (монорепозиторий; может быть списком),
Gradle-сборки живут в этих каталогах: `./gradlew …` запускай из каталога модуля (`cd core && ./gradlew …`),
`src/` и `build/` — его, фичи — в `<module>/src/acceptanceTest/resources/features/`, настройки модуля —
в `gauntlet/config/<module>/` (`./gradlew gauntletInfo` покажет, что подхватилось), а `gauntlet/` остаётся
в корне. Задача, затрагивающая два модуля, — одна спецификация (фичи в обоих) и один PR. Stop-хук сам
запускает `gauntletFast` в каждом модуле, где ход менял код, и возвращает тебе падения. `--continue`
показывает все красные гейты за один прогон. Отчёты: `<module>/build/reports/`.

**Среда облачной сессии.**
- Тесты с базой и брокером (интеграционные и приёмка) поднимают контейнеры через Testcontainers. Без Docker они **падают, а не пропускаются** — так задумано. В облачной
  VM демон поднимает SessionStart-хук (`dockerd` напрямую: `service docker start` там падает на ulimit),
  строка статуса показывает `docker: up`. Если там другое или контейнер сессии перезапускался:
  `nohup dockerd --host=unix:///var/run/docker.sock > /tmp/dockerd.log 2>&1 &` и дождись `docker info`.
  Красный Stop-хук из-за «Could not find a valid Docker environment» — это окружение, а не код.
- Maven Central через прокси иногда отвечает 429 (Too Many Requests) на пачку новых артефактов: повтори
  через 20–60 секунд, к коду это отношения не имеет.
- Набор подключается к сборке только при публичных репозиториях: в облаке их включает
  `CLAUDE_CODE_REMOTE=true`, в GitHub Actions — `GITHUB_ACTIONS=true`. В локальной сессии Claude Code задай
  `ORG_GRADLE_PROJECT_publicRepositories=true`, иначе сборка пойдёт в корпоративный реестр, а Stop-хук не найдёт
  задач набора.
- Не заканчивай ход, пока идёт фоновый прогон гейтов: Stop-хук запустит свой в тот же `build/` и будет ждать
  его конца (блокировка `.gradle/gauntlet-build.lock`, до 1500 с), а при более долгом прогоне упадёт по таймауту.

## Процесс для задачи, меняющей поведение сервиса

Триггер — сообщение пользователя: новая фича, багфикс, изменение контракта или сообщения. Для правок,
не меняющих поведение (рефакторинг, зависимости, логи, инфраструктура), шаги 2–4 пропускаются,
остальное так же.

1. **Контекст.** Прочитай `gauntlet/config/gauntlet.properties`, настройки модуля в
   `gauntlet/config/<module>/` (`gauntlet.properties`, `architecture.properties`), правила модуля
   (его `CLAUDE.md` и документы предметной области из раздела «Источники документации») и существующие фичи по теме в
   `<module>/src/acceptanceTest/resources/features/`.
2. **Спецификация.** Делегируй сабагенту `specifier`: запрос дословно, релевантные фичи, ограничения из
   сообщения. Он вернёт изменённые файлы, по строке на сценарий и открытые вопросы. Спецификации пишутся
   на русском (`# language: ru`); в рабочий контур они не переносятся.
   Если задача выбирает значение или версию из нескольких (история строк, эхо, повтор, отказ, удаление,
   очистка поля), specifier дополнительно возвращает **таблицу решений**: тип события × наблюдаемый исход
   (отправленное сообщение, сохранённое состояние); каждая строка таблицы — сценарий со значениями в
   Examples. Правило выбора, которое не закреплено ни сценарием, ни явным «Вне фичи», — открытый вопрос
   владельцу до заморозки, а не место для решения кодом.
3. **Утверждение — остановись.** Покажи пользователю пути файлов, по одной строке на сценарий, вопросы и
   допущения specifier'а. Спроси, утверждает ли он спецификацию, и закончи ход. До ответа — никакого кода
   и никаких коммитов: незакоммиченные фичи — черновик, который человек ещё может править (Stop-хук их не
   гоняет). Stop-хук облачной платформы (`~/.claude/stop-hook-git-check.sh`, не gauntlet) один раз
   заблокирует остановку и попросит закоммитить и запушить изменения — черновик фич не коммить: ответь
   одной строкой, что ждёшь утверждения, и остановись повторно, вторая остановка проходит. Решения,
   нужные от человека, выводи нумерованным списком, чтобы он ответил «1) да 2) да …», и к каждому пункту ставь
   рекомендацию «ответьте здесь» или «переслать координатору» («Правила владельца»). Просят изменений —
   снова к `specifier`.
   **Дыра-чек перед заморозкой:** каждое правило, которое код должен решать (выбор версии, порядок строк,
   судьба отказа, явная очистка поля против его отсутствия), закреплено сценарием или явно вынесено
   «Вне фичи» с принятым риском. Критерий — наблюдаемость приёмкой: меняется хоть одно свойство, которое
   видит приёмка (ответ, сообщение, сохранённая строка), — правило обязано быть в спецификации. Дыра —
   вопрос владельцу до заморозки; после заморозки она стоит уже правки спецификации человеком.
   Если в `gauntlet.properties` стоит `spec.approval=pr`, не останавливайся: человек прочитает Gherkin в PR.
4. **Заморозка.** После «да» закоммить только фичи отдельным коммитом `spec: <что описано>` и сразу
   запушить ветку (`git push -u origin HEAD`): с этого момента спецификация видна человеку на GitHub,
   а хук замораживает её для всех агентов — изменить её может только человек. Если по ходу реализации
   спецификация окажется противоречивой или невыполнимой — остановись и опиши проблему; не подгоняй
   ни код, ни тесты, ни спецификацию.
5. **Реализация (ты).** TDD маленькими шагами по правилам ниже; step-классы в `src/acceptanceTest/java`.
   `./gradlew gauntletFast --continue` до зелёного.
6. **Закалка.** Сабагент `hardener` (название фичи и список изменённых классов): убивает выживших мутантов
   и пустые step-определения, правит только тестовый код. Его предложения по продакшен-коду применяй
   сам, затем снова `gauntletFast`. Если PIT нечего мутировать (правка только конфигурации), ручные мутанты
   hardener предлагает списком, а применяешь, гоняешь тесты и откатываешь их ты — и перед коммитом проверяешь,
   что `src/main` чист.
7. **Ревью.** Сабагент `reviewer` (базовая ветка, фичи, список изменённых файлов). Каждая находка
   помечается типом: **«дефект»** — поведение противоречит утверждённой спецификации или решению владельца,
   правится в коде; **«правило»** — спецификация не определяет поведение, которое код решает (выбор версии,
   порядок, судьба отказа, очистка против отсутствия). Находки типа «правило» не уходят в новый раунд
   правок: они идут владельцу нумерованным списком «ответьте здесь», работа над ними останавливается до
   ответа; после ответа правило закрепляется в спецификации (замороженные фичи правит только человек или
   его делегат), затем один проход реализации против всего правила. Исправь все blocker/major типа
   «дефект», повтори прогон, верни результат ревьюеру. **Не больше 2 раундов**; после второго
   CHANGES REQUESTED с непогашенными находками остановись и опиши остаток, а не начинай третий круг.
   Рекомендация противоречит утверждённой спецификации — вопрос человеку.
8. **Финал.** `./gradlew gauntlet --continue` зелёный → коммит → `git push` своей ветки → открой PR
   (`gh pr create`, в описании — отчёт ниже; если не получилось, скажи об этом: пользователь нажмёт
   Create PR сам). Тот же отчёт — в чат. **Никогда не мержи** и не проси мержить за тебя: merge — это
   утверждение результата человеком. Одна задача — одна ветка и одна сессия: следующую задачу человек
   начинает новой сессией от основной ветки.

### Отчёт (в PR и в чат)
- **Гейты**: каждый со статусом; max CRAP; мутанты — убито / выжило / без покрытия; Gherkin-мутанты.
- **Спецификация**: файлы и сценарии — то единственное, что человек читает.
- **Ревьюер**: вердикт, раунды, что исправлено; находки типа «правило» — отдельным списком с пометкой,
  что они ждут решения владельца, и что по ним правок кода не было.
- **Сверка по документации**: по строке на решение, которое опирается на поведение фреймворка, библиотеки
  или протокола: утверждение → источник (URL или jar и класс) → версия; отдельно — что проверено только
  по байткоду и почему.
- **Перенос в контур**: новые зависимости и плагины с координатами (group:artifact:version) для проверки
  в корпоративном реестре; удалённые и переименованные файлы и классы; новые переменные окружения и значения
  по умолчанию (см. «Правила владельца»).
- **Нужно решение человека** — нумерованным списком, у каждого пункта — «ответьте здесь» или «переслать
  координатору» («Правила владельца»): эквивалентные мутанты, предлагаемые исключения,
  вопросы к спецификации, правила выбора вне спецификации (находки типа «правило»).
- **Оценка**: трудозатраты задачи для Jira против факта, с причиной расхождения.
- **Остаточные риски**.

### Правила владельца
- **Задача для Jira** — это задача владельца в рабочем контуре, а не задание сессии. Координатор пишет её в свой чат
  простым человеческим языком, без «нейрослопа» (тема, что и зачем, критерии приёмки, трудозатраты) до начала работы;
  после апрува владельца координатор открывает сессию шага с отдельным описанием уже для сессии. Если задача пришла
  сессии в промпте, заново она не пишется.
- **Независимый ревьюер Grok AI** читает каждый PR и оставляет комментарии в GitHub; сам ничего не правит.
  Его комментарий — не истина и не шум: автор PR (сессия шага — на своём PR, координатор — на своём) проверяет каждое
  замечание по коду и источникам; прав — исправить и запушить; не прав — ответить в том же треде, почему, со ссылкой на
  код или документацию. Молчать нельзя. Замечание, противоречащее утверждённой спецификации или решению владельца, —
  вопрос владельцу, а не правка. Каждый ответ в GitHub начинается строкой «Ответ Claude Code на комментарий Grok AI»
  (с номером или датой комментария), чтобы в треде было видно, кто кому отвечает.
- **Модель и уровень рассуждений сессий.** Координатор — Fable 5.1, уровень max,
  ультракод выключен: воркфлоу из многих агентов (adversarial-проверка PR, параллельная сверка плана) — только по
  явному запросу владельца. Сессии шагов по умолчанию — Opus 5.5, уровень xhigh, без ультракода: процесс gauntlet
  уже многоагентный (specifier, hardener, reviewer, хуки), ультракод поверх него — главный расход лимита. Шаги с
  тонкой семантикой фреймворка (транзакции, Hibernate, AMQP, таймауты) — Fable 5.1 xhigh. При старте каждой сессии
  шага координатор пишет в чат рекомендацию модели и уровня под эту задачу с обоснованием; решает владелец. При
  создании сессии координатор задаёт только модель; уровень и ультракод владелец выставляет в настройках сессии.
- **Решения человека — нумерованным списком** в любой остановке и в отчёте; ответ «1) да 2) нет …»
  записывается в описание PR.
- **Какие вопросы сессия шага адресует координатору.** Сессия шага решает только свою
  задачу; к каждому пункту списка решений она ставит рекомендацию: «ответьте здесь» или «переслать координатору». Владелец
  пересылает вопрос в чат координатора, а сессия до ответа работает дальше там, где от него не зависит. Переслать
  координатору: всё, что меняет план за пределами шага (состав, оценки или порядок других шагов, новый шаг, перенос
  остатка в другой шаг); правки набора gauntlet и его файлов (`gauntlet/`, `.claude/`, любой `CLAUDE.md`, политика
  архитектуры, allowlist'ы, исключения из PIT, эквивалентные мутанты); контракты с соседними сервисами и внешними системами и
  вопросы к их разработчикам; дефекты и долг, найденные вне файлов шага; модель, уровень рассуждений и лимиты; всё, что
  затрагивает другую идущую сессию или цепочку общих файлов. Владелец отвечает сам: выбор варианта спецификации и
  критериев приёмки своего шага, бизнес-правила из ТЗ в объёме шага, утверждение спецификации, допустимые остаточные риски
  шага, замечания Grok, противоречащие спецификации. Если вопрос не попадает ни в один список, сессия предлагает
  «переслать координатору».
- **Лимит токенов.** Если в сессию пришло предупреждение о 99 % пятичасового или недельного лимита либо
  человек написал «пауза», работа ставится на паузу, 100 % не ждать: закоммить и запушь свою ветку, напиши
  статус (что сделано, что красное, что дальше). Красный гейт на паузе не чинится: отвечай Stop-хуку одной
  строкой «пауза по лимиту, работа не сделана». Возобновляет человек или координатор сообщением в сессию.
- **Рабочий контур** (если приложение живёт в закрытой сети; иначе пункт удаляется при установке) — сеть
  компании, где живут сервисы. Там нет GitHub, интернета и Claude: облачные сессии Claude Code и GitHub —
  внешний контур. Зависимости и образы в контуре берутся только из корпоративного реестра (Nexus, Artifactory),
  с ним владелец работает сам, вручную; правки переносит тоже вручную, PR за PR в порядке мержа. Из сессии
  реестр закрыт, и обращаться к нему не нужно: здесь — только публичные адреса (Maven Central, портал плагинов
  Gradle, Docker Hub, официальная документация).
  - Сборка сама выбирает репозитории (`settings.gradle` модуля): в облаке (`CLAUDE_CODE_REMOTE=true`) и
    в GitHub Actions — публичные, иначе — корпоративный реестр; набор gauntlet подключается, только когда рядом
    лежит `gauntlet/` и репозитории публичные. Переключатель и вариант «только реестр» не трогай.
  - В контур не переносятся `gauntlet/`, `.claude/`, корневой `CLAUDE.md`, `.github/`,
    `<module>/src/acceptanceTest/` и каталог документов предметной области. Продакшен-код и unit-тесты от них не зависят,
    а сборка модуля без них зелёная.
  - Каждая новая зависимость и плагин — в отчёт с координатами `group:artifact:version`: владелец проверит
    их в реестре до переноса. Известные ограничения реестра (артефакты, которых он не отдаёт) записываются
    здесь при установке; такие ограничения не обходить.
  - Удалённые и переименованные файлы — отдельным списком в отчёте: при ручном переносе старые файлы
    удаляются, иначе останутся дубли классов и бинов. Переносы и переименования — только когда они нужны
    задаче.
  - Новые переменные окружения и изменённые значения по умолчанию — в отчёт.
  - Реестр образов в коде не хардкодится: в облаке образы Testcontainers идут с Docker Hub, в контуре
    префикс реестра задаёт его CI (`TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX`).

## Жёсткие правила
1. **Не трогай gauntlet.** `gauntlet/`, `.claude/`, `CLAUDE.md` и `.github/workflows/gauntlet.yml`
   принадлежат человеку (хук блокирует правки). Если проверка выглядит неверной — остановись и объясни,
   не обходи её.
2. **Никогда не ослабляй проверку ради зелёного**: никаких `@Disabled`/`@Ignore`/assumptions, `@Generated`/
   `@DoNotMutate`, `CHECKSTYLE:OFF`/`NOPMD`, фильтров тестов, `enabled = false` или переконфигурации гейтов
   в build-скриптах, удалённых или ослабленных assert'ов. `integrityCheck` это ловит; человек видит каждую
   попытку в diff.
3. **Фичи — это спецификация** (`<module>/src/acceptanceTest/resources/features/`, на русском,
   `# language: ru`). Пишет их только сабагент `specifier`, утверждает только человек — в чате. Код должен удовлетворять спецификации, а не наоборот.
4. **TDD.** На каждое поведение: сфокусированный падающий unit-тест, который упал бы на правдоподобной
   неверной реализации → минимум кода → рефакторинг. Приёмочные тесты не заменяют unit-тесты.
5. **Маленькие функции.** Цикломатическая сложность ниже 4 (Checkstyle: CC ≤ 3, NPath ≤ 20); CRAP-гейт
   падает выше 8. Дели методы со смешанными обязанностями; извлечённый метод сам владеет своими входами —
   не передавай boolean, который вызывающий уже знал. Одна задача на класс и файл (Checkstyle: метод
   ≤ 25 строк кода без пустых и комментариев, ≤ 4 параметров, файл ≤ 300 строк, fan-out ≤ 20; PMD:
   ≤ 12 методов в классе, cognitive complexity < 10). Лимиты набора строже правил проекта и действуют
   вместо них. Область гейтов — изменённый файл целиком: большой файл сначала приводится к лимитам
   отдельной задачей без изменения поведения.
6. **Зависимости направлены к политике**, как объявлено в политике модуля
   `gauntlet/config/<module>/architecture.properties` (`./gradlew gauntletInfo` покажет, какой файл
   действует): без новых циклов и рёбер против направления, домен и прикладная логика свободны от
   транспорта и персистентности. Исключения, которые политика объявляет явно (например, унаследованный
   цикл между двумя пакетами), — долг, а не образец: новый код их не расширяет. Адаптеры вызывают прикладную
   логику и никогда не дублируют её правило.
7. **Step-определения используют каждый параметр** и проверяют наблюдаемое поведение (HTTP-ответ,
   сохранённое состояние, отправленное сообщение). Пустой step проявится как выживший Gherkin-мутант.
8. Помечай `@Tag("no-mutate")` только медленные тесты с полным контекстом или Testcontainers: они
   идут в `test`, но PIT их пропускает, и код, покрытый только ими, считается непокрытым. Держи логику
   в обычных unit-тестируемых классах; тонкие IO-адаптеры, до которых дотягиваются только интеграционные
   тесты, человек исключает через `exclude.classes`.
9. Секретам, персональным и другим чувствительным данным не место в логах, тестовых фикстурах и текстах исключений.
10. **Git.** Коммиты говорят, что изменилось и зачем, и заканчиваются `By <role>.` (coder, specifier,
    hardener…). Только новые коммиты в своей ветке: никаких `--amend`, `rebase`, `revert`, `reset` на другую
    ревизию, `checkout -B`, `push --force`, push в базовую ветку, `--no-verify` (хук блокирует). Ошибку
    исправляй новым коммитом.
11. **SOLID — по каждому принципу, не «в целом».** SRP: у класса одна причина меняться — оркестрацию,
    маппинг и IO не смешивай в одном классе. OCP: новый случай — новый класс или стратегия, а не ещё одна
    ветка `if`/`switch` по типу. LSP: реализация не ужесточает предусловия и не бросает
    `UnsupportedOperationException` вместо обещанного поведения. ISP: интерфейсы узкие — клиент не зависит
    от методов, которые не вызывает. DIP: сервис зависит от абстракции (интерфейс, порт, `List`/`Map`),
    конкретный класс выбирает конфигурация или адаптер. Измеримую часть ловит `pmdGate` (god class,
    число методов, loose coupling), остальное — `reviewer`, который называет принцип и место.
12. **Сверяйся с официальной документацией, а не с памятью — строго и на каждом шаге.** Версии языка,
    сборщика и фреймворков бери из `project.*` в `gauntlet/config/gauntlet.properties` (их показывает
    `./gradlew gauntletInfo`), а версии библиотек — из фактического разрешения зависимостей сборки
    (`./gradlew dependencies`), а не из эталонных примеров или «latest». Правило действует для всех ролей:
    `specifier` сверяет семантику протоколов и фреймворка, на которую опираются сценарии (подтверждения
    брокера, повторная доставка, коды HTTP); кодер — каждый API, аннотацию, свойство, поведение потоков,
    транзакций и таймаутов до того, как написать код; `hardener` — тестовые библиотеки; `reviewer` —
    что сверка была и источник подходит к версии. Документация — той же версии. Источники — только из раздела «Источники документации»
    ниже. Никогда не выдумывай имя свойства, атрибут аннотации, метод или поведение: нет подтверждения
    ни в одном источнике — не используй, остановись и опиши. Офлайн-источники, которые есть всегда:
    имена, типы и значения по умолчанию свойств Spring Boot — `META-INF/spring-configuration-metadata.json`
    внутри jar в кэше Gradle (`~/.gradle/caches/modules-2/files-2.1/`), сигнатуры и поведение —
    `javap -p -c -cp <jar>`. Сайт недоступен — запасные пути раздела «Источники документации» по порядку:
    javadoc-jar и sources-jar нужной версии, исходники документации по тегу, jar в кэше Gradle; каждый случай
    — в отчёт. Версии инструментов Gauntlet фиксируются в `gauntlet/config/gauntlet.properties`; JVM инструментов
    задаётся отдельно через `gate.java.version`/`gate.java.home` и не меняет Java приложения. Обновлять версии
    языка, сборщика, фреймворков или библиотек самого приложения ради зелёного гейта нельзя: это требует
    отдельного решения владельца и отдельной задачи. Зависимости Gauntlet держим отдельно от приложения.
13. **Антипаттерны запрещены**, не только те, что ловит `pmdGate`: god class и класс-«сервис» со всем
    подряд, логика в листенере/контроллере/планировщике вместо домена, магические строки и числа,
    boolean-параметр-переключатель, `null` вместо `Optional` или пустой коллекции, проглоченное
    исключение, `catch (Exception)` вне границы системы (листенер, планировщик, внешний клиент) или без
    решения (лог + reject/requeue/повтор/пробросить), мутабельное статическое состояние, самописный
    механизм там, где у Spring/JDK есть стандартный (retry, транзакции, валидация, конвертация, планирование, кэш).
14. **Оптимальный, безопасный и отказоустойчивый путь.** Перед реализацией назови 2–3 варианта и выбери
    с обоснованием (кратко — в отчёт). Для каждого нового пути продумай: идемпотентность обработчика
    (повторная доставка сообщения, повторный HTTP-запрос), границы транзакций (транзакция не пересекает
    вызов внешней системы), таймауты и ограниченные ретраи внешних вызовов, судьбу отказа (dead letter,
    outbox, компенсация), потокобезопасность, валидацию входа на границе, наблюдаемость (структурный лог
    без ПДн, метрика, correlation id). Кэширование закладывай сразу там, где данные читаются многократно
    и меняются редко (справочники, реестры подразделений, конфигурация внешних систем, результаты дорогих
    запросов): только стандартный Spring Cache (`@Cacheable`/`@CacheEvict`, провайдер из конфигурации),
    у каждого кэша явно заданы ключ, TTL, предел размера и инвалидация при изменении источника. Без кэша
    там, где нужна свежесть (статусы заявок, всё, что участвует в принятии решения). Самописные
    `static Map`-кэши запрещены.
15. **Читаемый код.** Имена из предметной области (заказ, счёт, клиент — не data/info/tmp);
    метод делает ровно то, что говорит имя, и держит один уровень абстракции; guard clause вместо
    вложенности; комментарий, объясняющий плохой код, — повод переписать код; Javadoc на русском для
    публичных классов и неочевидных методов; `var` — только когда тип виден из правой части. Класс должен
    читаться сверху вниз как рассказ. Комментарии и Javadoc — простым человеческим языком для читателя, у
    которого нет плана, ТЗ и gauntlet: первое предложение — что это и для чего, слова предметной области
    вместо кодов документов и шагов плана, полные предложения, без истории правок и без пересказа кода;
    всё не переписывается — старые комментарии правятся в файлах, которые задача меняет (файл целиком).
    Javadoc — контракт, а не рассуждение: у класса резюме одной фразой и ещё 2–6 строк того, чего не видно из
    кода (больше 10 строк — сигнал вынести объяснение в документ), у метода 1–3 строки; без Javadoc у геттеров,
    DTO и очевидных методов, без пересказа кода и разбора альтернатив. Комментарии в конфигурации — по тем же правилам: у свойства или инструкции в `application.yml`, `Dockerfile`, `docker-compose.yml`, changeSet'ах миграций и скриптах сборки — одна-две фразы о том, зачем это значение и что сломается без него, без пересказа ключа и без кодов документов; длинное объяснение — в документ эксплуатации. Правка только комментариев доказывается сравнением конфигурации до и после (дерево YAML, `docker compose config`, строки Dockerfile без комментариев).
    **Никаких следов разработки вне рабочего контура**: в коде, комментариях, тестовых фикстурах и примерах не упоминаются PR и их
    номера, GitHub, ветки, gauntlet и гейты, сессии и роли, «решение владельца», номера шагов и решений плана —
    причина правила пишется словами. То же для документов, которые уходят в контур (описание API).

## Источники документации
Единственные допустимые источники для правила 12. Версии — те, что разрешает сборка модуля
(`./gradlew dependencies`; в эталоне — Spring Boot 4.0.7, при установке таблица заменяется версиями своей
сборки); при обновлении BOM сверяй по новой версии. `<версия>` — версия артефакта из `./gradlew dependencies`.
Адреса проверены запросом из облачной сессии эталона 2026-09-30, ревизия 2026-10-05 (все адреса таблицы и
запасные пути перепроверены `curl` из сессии; при установке повторить проверку из своего окружения);
пометка «закрыт» — домен не пропускает сетевая политика окружения (прокси отвечает «CONNECT tunnel failed, response
403»), тогда сразу запасной путь. Домены, которые стоит открыть в Network access окружения (решение владельца):
`docs.liquibase.com`, `prometheus.io`, `docs.docker.com`, `git-scm.com`, `docs.github.com`; по желанию —
`search.maven.org` и `central.sonatype.com` (поиск версий; `repo.maven.apache.org` и так открыт) и `api.osv.dev`
(проверка уязвимостей зависимостей; сейчас из сессии недоступна ни одна база уязвимостей — NVD, OSV, Snyk закрыты,
проверка остаётся на стороне владельца).

**Предметная область** (для `specifier`, кодера и `reviewer`; бизнес-правила берутся только отсюда, не выдумываются):

| Что | Источник |
|---|---|
| Правила и контракт модуля | <`<module>/CLAUDE.md`: разделы о контракте с внешними системами, соседях, пакетах, коде> |
| ТЗ, схемы процессов, структуры данных | <каталог документов проекта, например `project_docs/*.pdf`; заполняется при установке> |

PDF читаются инструментом Read (страницами). Документы противоречат друг другу или коду — остановись и
спроси владельца, не выбирай сам.

**Технологии** (версия из сборки → источник той же версии):

| Что | Официальный источник | Если сайт недоступен |
|---|---|---|
| Java SE 21 | API: docs.oracle.com/en/java/javase/21/docs/api/; JLS и JVMS: docs.oracle.com/javase/specs/ (se21) | `javap -p -c` на классах JDK |
| Spring Boot 4.0.7 | docs.spring.io/spring-boot/4.0/; API: docs.spring.io/spring-boot/4.0/api/java/; свойства: docs.spring.io/spring-boot/4.0/appendix/application-properties/; плагин Gradle: docs.spring.io/spring-boot/4.0/gradle-plugin/; Actuator и метрики: docs.spring.io/spring-boot/4.0/reference/actuator/ (metrics.html, endpoints.html); кэш: docs.spring.io/spring-boot/4.0/reference/io/caching.html; Testcontainers: docs.spring.io/spring-boot/4.0/reference/testing/testcontainers.html; миграция: вики github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide (из сессии закрыта, raw-вики Boot отвечает 404 — открывает человек) | `META-INF/spring-configuration-metadata.json` в jar, `javap` |
| Spring Framework 7.0.8 | docs.spring.io/spring-framework/reference/7.0/ (в т. ч. core/resilience.html — `@Retryable`, `RetryTemplate`, `@ConcurrencyLimit`, включаются `@EnableResilientMethods`; core/null-safety.html — JSpecify; integration/cache.html — `@Cacheable`/`@CacheEvict`, менеджеры кэша); **адрес с `7.0/` перенаправляет на страницу без версии** — это текущая ветка 7.0.x (метатег `version` показывал 7.0.9 при сборке на 7.0.8: патч-расхождение, сверять по метатегу); Javadoc: docs.spring.io/spring-framework/docs/7.0.x/javadoc-api/; изменения: raw.githubusercontent.com/wiki/spring-projects/spring-framework/Spring-Framework-7.0-Release-Notes.md | javadoc-jar и sources-jar, `javap` |
| Spring AMQP 4.0.4 | docs.spring.io/spring-amqp/reference/4.0/; API: docs.spring.io/spring-amqp/docs/4.0.4/api/ | javadoc-jar, `javap` |
| Spring Data JPA 4.0.6 | docs.spring.io/spring-data/jpa/reference/4.0/; API: docs.spring.io/spring-data/jpa/reference/4.0/api/java/ | javadoc-jar, `javap` |
| Hibernate ORM 7.2.19 | docs.hibernate.org/orm/7.2/ (руководство: userguide/html_single/Hibernate_User_Guide.html) | javadoc-jar, `javap` |
| Hibernate Validator 9.0.1, Jakarta Validation 3.1 | docs.jboss.org/hibernate/validator/9.0/reference/en-US/html_single/; jakarta.ee/specifications/bean-validation/3.1/ | javadoc-jar |
| Jakarta Persistence 3.2 | jakarta.ee/specifications/persistence/3.2/ | javadoc-jar |
| Liquibase 5.0.3 | docs.liquibase.com — **закрыт** (с 2026-10-05; репозиторий исходников документации liquibase/liquibase-docs заархивирован в сентябре 2025 и ветки под 5.0 не имеет) | javadoc-jar: javadoc.io/doc/org.liquibase/liquibase-core/5.0.3; sources-jar `org.liquibase:liquibase-core`; исходники по тегу raw.githubusercontent.com/liquibase/liquibase/v5.0.3/ (README, `liquibase-standard/src/main/resources/` — схемы changelog); поведение проверять `./gradlew test` с Testcontainers |
| PostgreSQL 16 (образ `postgres:16.10-alpine`), JDBC 42.7.11 | www.postgresql.org/docs/16/; jdbc.postgresql.org/documentation/ | исходник документации: raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/doc/src/sgml/ |
| RabbitMQ 4.1 (образ `rabbitmq:4.1.2-alpine` — патч-версия брокера рабочего контура): подтверждения, повторная доставка, DLX, аргументы очередей | www.rabbitmq.com/docs/4.1/<страница> (например, /docs/4.1/confirms) — **открыт с 2026-10-05**, брать адрес с версией: /docs/<страница> без версии показывает последнюю | исходники той же документации: raw.githubusercontent.com/rabbitmq/rabbitmq-website/main/versioned_docs/version-4.1/<страница>.md (например, confirms.md) |
| RabbitMQ Java-клиент 5.27.1 | www.rabbitmq.com/client-libraries/java-api-guide; Javadoc rabbitmq.github.io/rabbitmq-java-client/api/current/ — **открыты с 2026-10-05** (Javadoc — последней версии клиента, сверять с 5.27.1 по javadoc-jar) | javadoc-jar `com.rabbitmq:amqp-client:5.27.1`; raw.githubusercontent.com/rabbitmq/rabbitmq-java-client/v5.27.1/ |
| Jackson 3.1.4 (`tools.jackson`) | javadoc.io/doc/tools.jackson.core/jackson-databind/3.1.4; миграция: raw.githubusercontent.com/FasterXML/jackson/main/jackson3/MIGRATING_TO_JACKSON_3.md | javadoc-jar, `javap` |
| JSpecify 1.0 | jspecify.dev/docs/user-guide/ | javadoc-jar |
| Tomcat 11.0.22 (встроенный) | tomcat.apache.org/tomcat-11.0-doc/ | javadoc-jar |
| Kubernetes (пробы liveness/readiness, graceful shutdown — только при вопросах эксплуатации; манифестов в репозитории нет) | kubernetes.io/docs — **закрыт** | исходники документации: raw.githubusercontent.com/kubernetes/website/main/content/en/docs/<раздел>.md (например, concepts/workloads/pods/pod-lifecycle.md) |
| HikariCP 7.0.2 (пул соединений, версия из BOM Boot 4.0.7) | README по тегу: raw.githubusercontent.com/brettwooldridge/HikariCP/HikariCP-7.0.2/README.md (свойства пула, единицы и умолчания) | sources-jar и javadoc-jar `com.zaxxer:HikariCP:7.0.2` |
| SLF4J 2.0, Logback 1.5 | www.slf4j.org/manual.html, www.slf4j.org/api/; logback.qos.ch/manual/ | `javap` |
| Micrometer 1.16.6 (`micrometer-core`; для метрик Prometheus — `micrometer-registry-prometheus:1.16.6`) | docs.micrometer.io/micrometer/reference/1.16/ (реестр Prometheus: implementations/prometheus.html; имена и теги метрик, `MeterBinder`) ; Javadoc: javadoc.io/doc/io.micrometer/micrometer-registry-prometheus/1.16.6 | javadoc-jar, `javap` |
| Prometheus (формат выдачи `/actuator/prometheus`, типы метрик, правила именования) | prometheus.io/docs — **закрыт** | исходники документации: raw.githubusercontent.com/prometheus/docs/main/docs/instrumenting/exposition_formats.md, …/docs/practices/naming.md; клиент Java (его использует реестр Micrometer): raw.githubusercontent.com/prometheus/client_java/main/README.md |
| Caffeine 3.2.4 и Spring Cache (кэш справочников: `spring-boot-starter-cache`, `com.github.ben-manes.caffeine:caffeine:3.2.4`) | Caffeine: raw.githubusercontent.com/ben-manes/caffeine/v3.2.4/README.md и вики raw.githubusercontent.com/wiki/ben-manes/caffeine/<Страница>.md (Home, Population, Eviction, Statistics); Javadoc: javadoc.io/doc/com.github.ben-manes.caffeine/caffeine/3.2.4; Spring Cache — строки Spring Framework и Spring Boot выше (integration/cache.html, io/caching.html; свойства `spring.cache.caffeine.spec`) | javadoc-jar, `javap`; страницы вики github.com закрыты — только raw |
| JUnit 6.0.3 | docs.junit.org/6.0.3/ — **открыт с 2026-10-05** (руководство с версией в пути: docs.junit.org/6.0.3/user-guide/, Javadoc docs.junit.org/6.0.3/api/) | исходники руководства по тегу: raw.githubusercontent.com/junit-team/junit-framework/r6.0.3/documentation/modules/ROOT/pages/ (оглавление — …/modules/ROOT/nav.adoc); javadoc-jar |
| AssertJ 3.27.7 | assertj.github.io/doc/ | raw.githubusercontent.com/assertj/doc/main/src/docs/asciidoc/user-guide/ |
| Mockito 5.20.0 | Javadoc (он же руководство): javadoc.io/doc/org.mockito/mockito-core/5.20.0 (site.mockito.org открыт с 2026-10-05, но без версии — только как указатель) | javadoc-jar |
| Testcontainers 2.0.5 | java.testcontainers.org (модули: /modules/databases/postgres/, /modules/rabbitmq/) | raw.githubusercontent.com/testcontainers/testcontainers-java/2.0.5/docs/ |
| Awaitility 4.3 | руководство — вики: raw.githubusercontent.com/wiki/awaitility/awaitility/Usage.md | javadoc-jar |
| Cucumber-JVM 8.0.1 (приёмка); Cucumber Expressions 20.1.0; Gherkin 42.0.1 | cucumber.io/docs/ (Java: installation/java/; выражения шагов — docs/cucumber/cucumber-expressions/); Gherkin на русском — cucumber.io/docs/gherkin/languages/. Сайт без версии — сверять с исходниками по тегу | javadoc-jar, raw.githubusercontent.com/cucumber/cucumber-jvm/v8.0.1/; грамматика выражений шагов (альтернативы `a/b`, параметры) — raw.githubusercontent.com/cucumber/cucumber-expressions/v20.1.0/ARCHITECTURE.md (README тега документации не содержит); грамматика Gherkin — raw.githubusercontent.com/cucumber/gherkin/v42.0.1/gherkin.berp |
| Gradle 8.14.3 | docs.gradle.org/8.14.3/userguide/; DSL: docs.gradle.org/8.14.3/dsl/ | нет |
| Docker Compose v5.1.1 (CLI; в облачной VM версия меняется от сессии к сессии — встречалась и v5.3.1: сверять `docker compose version` и брать справку по своему тегу) и спецификация compose-файла (`docker-compose.yml`) | docs.docker.com — **закрыт** | CLI — по тегу версии: raw.githubusercontent.com/docker/compose/v5.1.1/docs/reference/<команда>.md (compose.md, compose_up.md, compose_down.md …); файл — raw.githubusercontent.com/docker/docs/main/content/reference/compose-file/<раздел>.md (services.md, build.md, fragments.md) и raw.githubusercontent.com/compose-spec/compose-spec/main/<NN>-<раздел>.md; руководства — raw…/docker/docs/main/content/manuals/compose/…; у docker/docs и compose-spec тегов под версию нет — ветка main, поведение проверять `docker compose … config` |
| Dockerfile и BuildKit (`Dockerfile` модуля: `RUN --mount`, `FROM ${ARG}`) | docs.docker.com — **закрыт** | raw.githubusercontent.com/moby/buildkit/master/frontend/dockerfile/docs/reference.md; руководства — raw…/docker/docs/main/content/manuals/build/…; поведение проверять `docker build` локально |
| Гейты: PIT 1.22.1, gradle-pitest-plugin 1.19.0, ArchUnit 1.5.1, Checkstyle 12.3.1, PMD 7.27.0, JaCoCo 0.8.15 | pitest.org; gradle-pitest-plugin.solidsoft.info; www.archunit.org/userguide/; checkstyle.org; docs.pmd-code.org/pmd-doc-7.27.0/; www.jacoco.org/jacoco/trunk/doc/ | по тегу версии на raw.githubusercontent.com: hcoles/pitest/1.22.1/README.md; szpak/gradle-pitest-plugin/release/1.19.0/README.md; TNG/ArchUnit/v1.5.1/docs/userguide/; checkstyle/checkstyle/checkstyle-12.3.1/src/site/xdoc/checks/; pmd/pmd/pmd_releases/7.27.0/pmd-java/src/main/resources/category/java/; jacoco/jacoco/v0.8.15/org.jacoco.doc/docroot/doc/ |
| Git (`.gitattributes`, `.gitignore`; версия — `git --version` в сессии, сейчас 2.43.0) | git-scm.com/docs — **закрыт** (и без версии) | по тегу версии: raw.githubusercontent.com/git/git/v<версия>/Documentation/<страница>.txt (например, gitattributes.txt); поведение проверять `git ls-files --eol`, `git check-attr` |
| GitHub Actions (`.github/workflows/gauntlet.yml`: синтаксис workflow, `services`, кэш Gradle) | docs.github.com — **закрыт** | исходники документации: raw.githubusercontent.com/github/docs/main/content/actions/reference/workflows-and-actions/workflow-syntax.md (оглавление — …/content/actions/index.md); поведение проверять прогоном CI на PR |
| Образы контейнеров: `postgres:16.10-alpine`, `rabbitmq:4.1.2-alpine`, `eclipse-temurin:21.0.12.1_1-jdk/-jre` (Dockerfile), Testcontainers (`testcontainers/ryuk`) | теги и даты сборки — API Docker Hub: hub.docker.com/v2/repositories/library/<образ>/tags?name=<тег> (страницы hub.docker.com/_/<образ> тоже открыты); зеркало с манифестами: mirror.gcr.io/v2/library/<образ>/tags/list; Temurin: raw.githubusercontent.com/adoptium/containers/main/README.md | `docker manifest inspect`, `docker run … --version`; реестр registry-1.docker.io отвечает 401 без токена — нормально |
| Maven Central (версии артефактов, javadoc-jar и sources-jar) | repo.maven.apache.org/maven2/<group/path>/<artifact>/maven-metadata.xml и …/<version>/<artifact>-<version>-javadoc.jar (иногда 429 — повторить через 20–60 с); зеркало javadoc.io/doc/<group>/<artifact>/<version> | search.maven.org и central.sonatype.com — **закрыты**; плагины Gradle: plugins.gradle.org/plugin/<id> открыт; дистрибутивы services.gradle.org/downloads.gradle.org — **закрыты** (wrapper в сессии уже в кэше) |
| Хуки и сабагенты Claude Code (правки `.claude/settings.json`, `.claude/agents/`, `gauntlet/hooks/`) | code.claude.com/docs/en/hooks, code.claude.com/docs/en/sub-agents — без версии: сверять с версией Claude Code в сессии (`claude --version`, в облаке — строка статуса или метаданные сессии) | поведение проверять `python3 gauntlet/hooks/selftest.py` и журналом хука в `build/gauntlet/` |

- Адрес без версии показывает последнюю ветку, а не нашу: у docs.spring.io, docs.hibernate.org,
  docs.micrometer.io версия major.minor стоит в пути (`/spring-boot/4.0/`, `/orm/7.2/`, `/reference/1.16/`);
  проверь по метатегу `version` страницы. Сайты без версий (docs.liquibase.com, java.testcontainers.org,
  assertj.github.io, cucumber.io) — источник, только если страница не расходится с исходниками по тегу
  нужной версии; в отчёт тогда идёт ссылка на тег.
- Страница с major.minor в пути может расходиться с кодом и нашей, и последней версии. Пример из эталона: how-to
  Boot 4.0 «Database Initialization» обещает наследование незаданных `spring.liquibase.*` из `spring.datasource.*`,
  а spring-boot-liquibase 4.0.7 (`LiquibaseAutoConfiguration.getMigrationDataSource`) при заданном
  `spring.liquibase.url` их не наследует. При расхождении прав код нужной версии (sources-jar, `javap`); в «Сверку
  по документации» идут оба источника.
- Универсальная замена недоступного сайта: javadoc-jar и sources-jar нужной версии на repo.maven.apache.org
  (зеркало — javadoc.io), исходники документации по тегу версии на raw.githubusercontent.com; последний
  рубеж — jar в кэше Gradle (`~/.gradle/caches/modules-2/files-2.1/`).
- Не источник: блоги, Stack Overflow, статьи, ответы ИИ, память модели, код других проектов. Официальный
  источник противоречит «привычному» — прав источник.
- Домен недоступен из облачной сессии — его добавляет человек в Network access окружения; до этого — запасной
  путь и пометка в отчёте. Ответ прокси «CONNECT tunnel failed, response 403» бывает и у несуществующего домена:
  существование адреса сначала сверь с метаданными артефакта (`<url>` в POM).
- Веб-страницы github.com чужих репозиториев из сессии закрыты (HTTP 403 «GitHub access to this repository is
  not enabled for this session»); чужие репозитории ради документации не подключать. Файлы репозитория —
  `raw.githubusercontent.com/<owner>/<repo>/<тег>/…`, вики — `raw.githubusercontent.com/wiki/<owner>/<repo>/<Страница>.md`;
  страницу, которой нет и там (вики миграции Spring Boot), открывает человек.
- Корпоративный реестр — не источник документации и из сессии не используется (см. «Рабочий контур»).

## Когда застрял
- Выживший мутант, который ты считаешь эквивалентным; `switch`, который должен остаться выше лимита
  CRAP; легитимная находка integrity — **остановись и опиши**. Человек может добавить исключение в
  `gauntlet/config/*-allowlist.txt`.
- Мутант RUN_ERROR вне `pit-runerror-allowlist.txt` (`mutationGate: N RUN_ERROR mutant(s) …`) — прочитай тесты
  и назови ассерт, который упал бы ровно на этой мутации. Есть такой — **остановись** и предложи человеку строку
  `Class#method Mutator # тест`; нет — это слабый тест, напиши тест, который убил бы мутанта. Падение JVM не чинится
  исключением класса из PIT и не обходится тегом `no-mutate`.
- Спецификация противоречит unit-тесту или коду — остановись и спроси; не правь ни одну сторону,
  чтобы «подружить» их.
- Ревью или координатор нашёл поведение, которое спецификация не определяет (находка типа «правило»), —
  **остановись и опиши**: какое правило решает код, какие исходы видны приёмке, варианты с рекомендацией.
  Не подбирай правило по одному случаю за раунд: следующее проявление того же пробела придёт новым
  заворотом, и гейты его не поймают — мутации закаляют тесты против спецификации, а не против
  ненаписанных правил. Решение владельца закрепляется в спецификации, затем один проход реализации
  против всего правила; накопленные регрессионные случаи становятся приёмочным набором.
- Гейт красный после 3 попыток — Stop-хук отпустит тебя с предупреждением. Работа при этом НЕ сделана:
  так и напиши в отчёте, с причинами.

===== END FILE gauntlet/CLAUDE.md =====

===== BEGIN FILE gauntlet/INSTALL.md =====
# Установка gauntlet в этот сервис

Инструкция для Claude Code: выполняется в первой сессии по запросу «выполни gauntlet/INSTALL.md».
Цель сессии: после неё `./gradlew gauntlet` зелёный на **текущем** коде, хуки и роли подключены,
PR открыт. Бизнес-код и существующие тесты не менять: всё, что найдено про старый код, идёт в отчёт.

Порядок важен: хуки становятся активны в момент появления `.claude/settings.json` (шаг 7) — после
этого `gauntlet/` для агентов доступен только на чтение. Поэтому вся настройка делается до шага 7.

## 0. Какие сборки охраняет gauntlet
Если в корне репозитория лежит `build.gradle(.kts)` и `gradlew` — это и есть сборка, `module` остаётся
пустым. Если репозиторий — монорепо с несколькими независимыми сборками в подкаталогах (свой
`settings.gradle`, `build.gradle`, `gradlew` у каждой), gauntlet подключается к тем из них, что названы
в запросе пользователя («… для модулей core и adapter»); если не названы — остановись и
спроси, предложив кандидатов (сервисы с логикой, а не библиотеки и тестовая обвязка).
- Впиши их в `gauntlet/config/gauntlet.properties`: `module=core,adapter`. Хуки будут
  запускать Gradle в каждом изменённом модуле, CI — во всех; `src/` и `build/` — каждого модуля,
  `gauntlet/` остаётся в корне.
- Общие пороги — в `gauntlet/config/`; то, что у модуля своё (`basePackage`, `acceptance.glue`,
  `exclude.classes`, архитектура), — в `gauntlet/config/<module>/`: `gauntlet.properties` там дополняет
  общий файл, `architecture.properties` (и при нужде `checkstyle.xml`, allowlist'ы) заменяет общий.
  Проверить, что подхватилось: `cd <module> && ./gradlew gauntletInfo`.
- Корневую сборку **не создавай**, остальные модули не трогай. Если у модуля нет своего `gradlew`,
  скопируй `gradlew`, `gradlew.bat` и `gradle/wrapper/` из соседнего модуля.
- Если модуль зависит от библиотеки-соседа (например `shared-lib`) через артефакт из
  внутреннего Maven-репозитория, облачная сборка его не достанет: подключи соседа как
  `includeBuild('../shared-lib')` в `settings.gradle` модуля (composite build, подмена
  по group:name автоматическая) — или, если это невозможно, остановись и опиши проблему.
Шаги 1–6 выполняются для каждого модуля; пути вида `src/…`, `build.gradle` и команды `./gradlew`
относятся к каталогу модуля.

## 1. Разведка
Определи и запиши для отчёта с доказательством (файл:строка или вывод команды):
- Java приложения (`sourceCompatibility`/`targetCompatibility`/toolchain), Gradle (`gradle/wrapper/gradle-wrapper.properties`
  и `./gradlew --version`), DSL сборки (Groovy или Kotlin);
- Spring Boot и остальные фреймворки (`build.gradle(.kts)`, `gradle/libs.versions.toml`, lock-файлы и
  `./gradlew dependencies`), JUnit и другие тестовые библиотеки; не угадывай версии по эталону;
- корневой пакет сервиса (`@SpringBootApplication`) и его прямые подпакеты;
- какие подпакеты от каких зависят сейчас (импорты между ними);
- основную ветку репозитория (`git remote show origin` → HEAD branch);
- как существующие интеграционные тесты поднимают контекст (Testcontainers? какие контейнеры?);
- есть ли уже `CLAUDE.md`, `.claude/`, `.github/workflows/`.

## 2. `gauntlet/config/gauntlet.properties` (при нескольких модулях — `gauntlet/config/<module>/gauntlet.properties`)
- `module`, `baseRef`, `cucumber.version` и пороги — только в общем файле.
- `basePackage` — корневой пакет модуля.
- `acceptance.glue` — `<basePackage>.acceptance`.
- `baseRef` — `origin/<основная ветка>`, если это не `main`.
- `project.java.version`, `project.gradle.version`, `project.framework.<имя>.version`,
  `project.test.<имя>.version` — фактические версии из шага 1, не значения шаблона. CI и роли используют
  эти записи; `./gradlew gauntletInfo` показывает их вместе с версиями инструментов.
- `gate.java.version` — major-версия JVM инструментов Gauntlet, `gate.java.home` — необязательный локальный
  абсолютный путь к ней. Если гейту нужна другая JVM, меняй только эти ключи, не Java приложения и не его
  toolchain. CI устанавливает `gate.java.version`; если она пуста, использует `project.java.version`.
- `cucumber.version`, `archunit.version`, `pit.version`, `pit.junit5PluginVersion`, `jacoco.version`,
  `checkstyle.version`, `pmd.version` и плагин PIT — совместимые с обнаруженными Java/Gradle/JUnit/Spring
  версии, зафиксированные после реального прогона. Например, Boot 3.5 с JUnit 5.12 → Cucumber 7.23.0;
  Boot 4 с JUnit 6 → Cucumber 8.0.1. Это примеры, не разрешение менять зависимости проекта.
- Не обновляй JUnit, Spring Boot, Java, Gradle или другие зависимости приложения для совместимости гейтов.
  Если подходящей связки нет, остановись и вынеси владельцу варианты отдельным решением и отдельной задачей.
- `exclude.classes` — добавь маски тонких IO-адаптеров, которых достигают только интеграционные тесты
  (`*Repository`, `*Client`, `*Listener`, `*Publisher`…): их не мутируем и не считаем в CRAP.
  Не добавляй туда классы с бизнес-логикой.
- `spec.approval` оставь `chat`.

## 3. `gauntlet/config/architecture.properties` (при нескольких модулях — `gauntlet/config/<module>/architecture.properties`, общий файл тогда не используется)
- `base.package` — корневой пакет модуля.
- `allowed.<подпакет>=…` для **каждого** прямого подпакета — так, как зависимости устроены сейчас
  (гейт должен быть зелёным на текущем коде; незаявленный подпакет — падение с перечислением).
- `forbidden.*` оставь только те правила, которые выполняются уже сейчас; остальные закомментируй.
- В отчёт: рёбра, которые идут против направления «адаптеры → application → domain», и `forbidden`,
  которые пришлось снять. Ужесточать — решение человека, отдельными задачами.

## 4. Сборка
Kotlin DSL (`build.gradle.kts`):
```kotlin
plugins {
    // ...существующие
    id("info.solidsoft.pitest") version "1.19.0"
}
// ...
apply(from = "gauntlet/gauntlet.gradle")      // последней строкой; из модуля: "../gauntlet/gauntlet.gradle"
```
Groovy DSL (`build.gradle`):
```groovy
plugins {
    // ...существующие
    id 'info.solidsoft.pitest' version '1.19.0'
}
// ...
apply from: '../gauntlet/gauntlet.gradle'      // последней строкой; из корня: 'gauntlet/gauntlet.gradle'
```
Скрипт находит `gauntlet/` рядом с собой, а `src/` и `build/` берёт у сборки, в которой применён.
Он не меняет `./gradlew build`; все проверки идут через задачи группы `gauntlet`.

## 5. Приёмочные тесты
- Скопируй `gauntlet/templates/acceptanceTest/java/.../CucumberSpringConfiguration.java` в
  `src/acceptanceTest/java/<пакет из acceptance.glue>/` и поправь `package`.
- Если контексту нужны PostgreSQL, RabbitMQ и т. п. — добавь в этот класс Testcontainers так же, как в
  существующих интеграционных тестах (`@ServiceConnection` / `@DynamicPropertySource`).
- Пример фичи `templates/.../example_discount.feature` **не копируй**: это только образец формата.
  Каталог `src/acceptanceTest/resources/features/` создай пустым (файл `.gitkeep`).

## 6. Первый прогон
`./gradlew gauntlet --continue` (из каталога сборки). Изменённых main-классов в этой ветке нет, поэтому Checkstyle, CRAP,
DRY, PIT и Gherkin-мутация проверят пустое множество; реально прогоняются `integrityCheck`, `test`
и `archTest`. Чини только конфигурацию gauntlet:
- `integrityCheck` нашёл в старых тестах `@Disabled`, `assume*`, `disabledWithoutDocker` и т. п. →
  запиши каждое в `gauntlet/config/integrity-allowlist.txt` с причиной `pre-existing at install`
  и перечисли в отчёте. Сами тесты не трогай.
- `archTest` перечислил незаявленные подпакеты или рёбра → шаг 3.
- `test` красный → это не про gauntlet. Если причина в окружении (нужен Docker: в облачной VM
  `service docker start` падает на ulimit — запусти `nohup dockerd --host=unix:///var/run/docker.sock &` и
  дождись `docker info`) — подними окружение; если тест падает по существу — в отчёт, не чини.
- `gauntletScope` не находит merge-base → `git fetch origin +refs/heads/<ветка>:refs/remotes/origin/<ветка>`
  (именно с refspec: клон облачной сессии может быть single-branch, и обычный `git fetch origin main`
  не создаст `origin/main`); если клон shallow — сначала `git fetch --unshallow origin`.
Повторяй до зелёного. В отчёт выпиши фактически проверенную матрицу `project.*`, `gate.java.*` и версий
инструментов. Просмотри diff манифестов сборки: там только подключение Gauntlet, никаких обновлений версий
приложения или его зависимостей. Такое обновление прекращает установку и уходит владельцу отдельным решением.

## 7. Подключение хуков — последним
Сначала `python3 gauntlet/hooks/selftest.py` — самопроверка хуков на этой VM, ожидается `0 failed`.
Затем `bash gauntlet/install.sh`. Скрипт создаст `.claude/settings.json`, `.claude/agents/`,
`.github/workflows/gauntlet.yml` и добавит `@gauntlet/CLAUDE.md` в корневой `CLAUDE.md`
(существующие файлы не перезаписывает: положит рядом `*.gauntlet.*` — тогда слей их вручную и удали копию).
После этого шага `gauntlet/`, `.claude/` и `CLAUDE.md` не редактируй.

## 8. Коммит, push, PR
`git add -A && git commit -m "chore: install the gauntlet"`, `git push -u origin HEAD`, затем
`gh pr create` с отчётом:
- модуль (если монорепо) и как подключены соседние библиотеки;
- обнаруженные версии проекта (`project.*`), отдельная JVM гейта (`gate.java.*`), совместимые версии
  инструментов и доказательство их реального прогона; заполненные `basePackage`/`glue`/`baseRef`;
- `exclude.classes` и почему;
- архитектура: заявленные компоненты, рёбра против направления, снятые `forbidden`;
- integrity-исключения с причинами;
- что не удалось прогнать и почему.

Человек прочитает отчёт и смержит PR — это и есть утверждение установки.

===== END FILE gauntlet/INSTALL.md =====

===== BEGIN FILE gauntlet/README.md =====
# gauntlet/ — работа «не читая код» для Java 21 + Gradle + Spring Boot + Claude Code в облаке

Подход Роберта Мартина (Uncle Bob), переложенный на обычный Spring-сервис и веб-версию Claude Code
(claude.ai/code): код пишет агент, человек читает **спецификации (Gherkin), отчёт о гейтах и
изменения самого набора** — и принимает решение кнопкой merge. Терминал не нужен.

> Оговорка. В сентябре 2026 Мартин написал, что пересматривает подход: без своего харнесса
> (swarm-forge) расход токенов «упал в разы», а модели стали достаточно хороши, чтобы жёсткие
> детерминированные харнессы были неоптимальны. Здесь взята та часть, которая от оркестрации
> не зависит — **гейты качества** — и один основной агент с тремя лёгкими ролями вместо шести.

## 1. Как это выглядит для вас

1. Пишете в чат сессии: «Хочу, чтобы при отказе внешней системы заявка …» — обычными словами.
2. Claude читает `gauntlet/CLAUDE.md` (он подключён к корневому `CLAUDE.md` и загружается в каждую
   сессию), делегирует роль `specifier`, и присылает вам сценарии на Gherkin по одной строке
   плюс вопросы. Сессия останавливается. **Это единственное чтение, которое от вас требуется.**
3. Отвечаете «да» (или «поправь…»). Claude коммитит спецификацию и сразу пушит ветку — с этого
   момента спецификация видна на GitHub, а хук её замораживает — и реализует по TDD, прогоняет
   `hardener` и `reviewer`, гоняет `./gradlew gauntlet`, пушит результат и открывает PR с отчётом
   (гейты, мутанты, вердикт ревьюера, что требует вашего решения).
4. Смотрите отчёт и Gherkin в PR, CI показывает зелёный `gauntlet` — нажимаете merge. **Это утверждение
   результата.** Красное — не мержите, пишете в сессию, что не так.

Одна задача — одна сессия и одна ветка; следующую задачу начинайте новой сессией от основной ветки.
Две вещи делаете только вы: «да» спецификации в чате и merge в GitHub. Агент не может ни того, ни
другого: спецификация после коммита закрыта хуком, push возможен только в собственную ветку (так
устроен GitHub-прокси облачных сессий), `gh pr merge` запрещён.

## 2. Состав

```
gauntlet/
  CLAUDE.md               процесс и правила для агентов — импортируется корневым CLAUDE.md
  README.md               этот файл
  INSTALL.md              что делает Claude в первой сессии, чтобы вживить набор в сервис
  install.sh              механическая часть установки (запускает Claude, шаг 7 INSTALL.md)
  gauntlet.gradle         все гейты (скрипт-плагин; build.gradle(.kts) сборки подключает его последней строкой)
  config/                 пороги (gauntlet.properties), архитектура, checkstyle.xml, pmd-ruleset.xml, allowlist'ы;
                          config/<module>/ — то, что у модуля монорепо своё
  tools/                  IntegrityCheck, CrapGate, DryGate, GherkinMutator, PitSummary (single-file Java)
  archtest/               ArchUnit-тест, читающий config/architecture.properties
  hooks/                  guard.py (PreToolUse), stop_gate.py (Stop; SubagentStop hardener'а — matcher в
                          .claude/settings.json), session_start.sh (SessionStart; в облаке поднимает dockerd),
                          selftest.py (994 проверки хуков в трёх раскладках: python3 gauntlet/hooks/selftest.py)
  templates/              конфигурация Cucumber+Spring, пример фичи на русском
  claude/, ci/            только до установки: install.sh переносит их в .claude/ и .github/workflows/
```

После установки в корне появляются `CLAUDE.md` (одна строка `@gauntlet/CLAUDE.md`), `.claude/settings.json`
(хуки и права), `.claude/agents/{specifier,hardener,reviewer}.md` и `.github/workflows/gauntlet.yml`.
Роли живут в `.claude/agents/` репозитория: только они доходят до облачной сессии, пользовательские
`~/.claude/agents/` остаются на машине. Всё остальное — в `gauntlet/`. Хук защищает и то, и другое.

## 3. Гейты

| Gradle-задача | Инструмент | Порог по умолчанию | Где менять |
|---|---|---|---|
| `integrityCheck` | свой (`IntegrityCheck.java`) | 0 находок | `config/integrity-allowlist.txt` |
| `checkstyleGate` | Checkstyle 12.3.1 (CLI) | метод ≤ 25 строк, ≤ 4 параметров, CC ≤ 3, NPath ≤ 20, файл ≤ 300 строк, fan-out ≤ 20, вложенность if ≤ 2, magic numbers, фигурные скобки | `config/checkstyle.xml` |
| `pmdGate` | PMD 7.27 (CLI) | 0 антипаттернов: god class, > 12 методов, cognitive complexity ≥ 10, сырые/проглоченные исключения, неиспользуемое, незакрытые ресурсы, потоки, крипто, именование | `config/pmd-ruleset.xml` |
| `test` | JUnit, как у вас | — | — |
| `archTest` | ArchUnit 1.5.1 | разрешённые рёбра, без циклов | `config/architecture.properties` |
| `acceptanceTest` + `acceptanceCheck` | Cucumber 7/8 | всё зелёное, **ни одного skipped**, при наличии фич исполнен хотя бы один сценарий; судятся только результаты этого прогона | — |
| `crapGate` | свой (`CrapGate.java`) по JaCoCo XML, формула crap4java | **8** | `crap.threshold`, `config/crap-allowlist.txt` |
| `dryGate` | PMD CPD 7.27 | 0 дублей ≥ 60 токенов (имена и литералы игнорируются; `dry.exclude` — пути вне поиска, например каталог JPA-сущностей) | `dry.*` |
| `mutationGate` | PIT 1.22 + gradle-pitest-plugin 1.19.0, свой `PitSummary.java` | **все покрытые мутанты убиты** (test strength 100 %), покрытие мутируемых классов ≥ 80 %; RUN_ERROR (JVM тестов упала на `redefineClasses`, PIT считает его обнаруженным) **не засчитывается убитым** — только строкой в allowlist, которую человек добавил, прочитав тесты | `pit.*`, `config/pit-runerror-allowlist.txt` |
| `gherkinMutation` | свой (`GherkinMutator.java`) | 0 выживших мутантов значений Examples | — |

Значения Мартина и их источники — в комментариях `config/gauntlet.properties`
(CRAP > 8 у crap4java, «ни один покрытый мутант не выживает» у mutate4java, DRY 0.82 у dry4java, CC < 4).
Версии инструментов в таблице — примеры эталона. При `start` фактические версии языка, сборщика,
фреймворков и тестовых библиотек определяются по файлам целевого проекта и записываются в `project.*`;
совместимые версии инструментов фиксируются после реального прогона. `gate.java.version` и
`gate.java.home` задают JVM только для гейтов, отдельно от Java приложения. CI и роли читают эту
конфигурацию (`./gradlew gauntletInfo`). Обновление зависимостей приложения — только отдельным решением
владельца и отдельной задачей, не часть установки Gauntlet.

**Монорепо.** Если в репозитории несколько независимых Gradle-сборок (у каждой свой `build.gradle` и
`gradlew` в подкаталоге), в `config/gauntlet.properties` перечисляются охраняемые:
`module=core,adapter`. Хуки запускают Gradle в каждом изменённом модуле, CI — во всех;
`src/` и `build/` — каждого модуля, `gauntlet/` остаётся в корне, прочие модули не трогаются. Общие
пороги — в `config/`, своё у модуля (`basePackage`, `acceptance.glue`, `exclude.classes`, архитектура) —
в `config/<module>/` (`gauntlet.properties` дополняет общий, остальные файлы заменяют одноимённые);
`./gradlew gauntletInfo` в модуле показывает, что подхватилось. Спецификация одна на задачу: коммит
фич любого модуля замораживает фичи всех. Groovy и Kotlin DSL поддерживаются одинаково.

`./gradlew gauntletFast` — всё, кроме мутаций (минуты); `./gradlew gauntlet` — целиком; `--continue`
показывает все красные гейты за прогон. **Режим `scope=changed`** (по умолчанию): CRAP, DRY, Checkstyle, PMD
и мутации проверяются только для файлов, отличающихся от базовой ветки, поэтому набор подключается к
работающему сервису без разбора старого кода. Для ночного CI есть `-Pgauntlet.scope=all`.

## 4. Утверждение спецификации без терминала

В первой версии набора спецификацию «запирал» хэш-файл, который писала только команда в вашем
терминале. В облаке терминала нет, поэтому утверждение устроено через git и чат:

| Момент | Состояние фич | Кто может менять |
|---|---|---|
| specifier написал черновик | не закоммичены | `specifier` (по вашим замечаниям в чате) |
| вы сказали «да», агент сделал коммит `spec: …` и запушил ветку | закоммичены и видны на GitHub | **никто из агентов**: guard видит коммит в ветке, трогающий `features/`, и отклоняет любую правку; `--amend`, `rebase`, `revert`, `reset`, `checkout -B`, `branch -f`, `push --force` запрещены, так что коммит не исчезнет ни локально, ни на GitHub |
| PR смержен | в основной ветке | заморозка снимается сама (фичи ветки совпадают с основной); следующая задача — новая сессия |

Правила хука (`hooks/guard.py`) — «заморожено, если в ветке есть коммит с фичами»; ему не нужны
ни файлы-замки, ни ваша команда. Stop-хук (`hooks/stop_gate.py`), пока фичи не закоммичены, не гоняет
приёмочные тесты (иначе агент не смог бы остановиться и спросить), а ход, в котором менялись только
фичи, вообще не проверяет.

Переключатель `spec.approval` в `config/gauntlet.properties`: `chat` (по умолчанию, описано выше) или
`pr` — агент не останавливается, вы читаете Gherkin в PR, заморозки нет.

**Если после утверждения спецификацию нужно изменить** (оказалась противоречивой, передумали):
агент этого сделать не может. Либо правите `.feature` прямо на GitHub в ветке сессии (она запушена
сразу после утверждения) и пишете агенту «git pull, спека изменилась», либо переключаетесь в
админ-окружение (раздел 5).

## 5. Что можете только вы, и как это делается без терминала

| Действие | Как |
|---|---|
| Утвердить спецификацию | ответить «да» в сессии |
| Принять результат | merge PR в GitHub |
| Изменить пороги, allowlist'ы, архитектуру, роли, CLAUDE.md, замороженную спеку | (а) отредактировать файл на GitHub в ветке; (б) **админ-окружение**: на claude.ai/code создайте второе cloud environment «gauntlet-admin» с переменной `GAUNTLET_GUARD=off` (и при желании `GAUNTLET_STOP_HOOK=off`); сессия, запущенная в нём, работает без guard-хука — просите Claude менять что угодно, изменения всё равно пройдут через PR и CI |
| Исключения: эквивалентный мутант, большой `switch`, легитимный `@Generated`, RUN_ERROR-мутант, который тесты убили бы | агент остановится и опишет (для RUN_ERROR — назовёт тест и ассерт, который упал бы на мутанте); вы проверяете и добавляете строку в `config/*-allowlist.txt` одним из способов выше |

Переменные окружения cloud environment попадают в процессы сессии, хуки их читают при запуске.
Обычные фичи делайте в охраняемом окружении — там, где переменная `GAUNTLET_GUARD` не задана. Проверка —
строка статуса SessionStart в начале сессии: `guard: on; stop hook: on`. Имя окружения ничего не гарантирует:
переменную видно только в его настройках.

**CI и защита ветки.** `.github/workflows/gauntlet.yml` устанавливает `gate.java.version` (при пустой —
`project.java.version`), вызывает Gradle wrapper той версии, которую `start` нашёл в проекте, печатает
`./gradlew --version` и `gauntletInfo`, затем гоняет `./gradlew gauntlet` на каждый PR с
полной историей (`fetch-depth: 0`) — это проверка, которую агент не может обойти (хуки работают только
внутри Claude Code). Если репозиторий приватный на бесплатном плане GitHub, правила защиты веток
недоступны; тогда гейт — это ваше правило не мержить красный PR. Агент мержить не может в любом случае.
Auto-fix (кнопка в CI status bar сессии): на упавший CI или комментарий в PR Claude отвечает сам, в той же
сессии, под теми же хуками.

## 6. Установка (одна сессия, без терминала)

1. Положите каталог `gauntlet/` в корень репозитория в новой ветке: на GitHub → *Add file → Upload files*,
   перетащите папку целиком, commit в ветку `gauntlet-setup`.
2. На claude.ai/code выберите репозиторий, ветку `gauntlet-setup`, режим **Accept edits**, окружение
   без `GAUNTLET_GUARD`, сеть **Custom** с галкой «Also include default list of common package managers»
   (Maven Central, Gradle Plugin Portal и GitHub приходят из этого списка) и ровно этим списком доменов
   документации (он же — «Разрешённые домены окружения» в `gauntlet/CLAUDE.md`, правило 12 берёт их первыми):
   `logback.qos.ch www.slf4j.org docs.gradle.org www.rabbitmq.com rabbitmq.github.io docs.micrometer.io pitest.org
   cucumber.io min.io docs.spring.io docs.oracle.com javadoc.io docs.liquibase.com www.postgresql.org
   jdbc.postgresql.org assertj.github.io site.mockito.org docs.junit.org java.testcontainers.org jspecify.dev
   tomcat.apache.org www.archunit.org checkstyle.org docs.pmd-code.org www.jacoco.org
   gradle-pitest-plugin.solidsoft.info docs.hibernate.org docs.jboss.org jakarta.ee prometheus.io docs.docker.com
   git-scm.com docs.github.com code.claude.com`. Открыты уровнем Trusted и в список не вносятся: Maven Central,
   портал плагинов Gradle, raw.githubusercontent.com, API Docker Hub (hub.docker.com), mirror.gcr.io.
   По желанию можно добавить `www.min.io` (на него редиректит min.io), `wiremock.org`, `mapstruct.org`,
   `projectlombok.org`, `www.instancio.org`, `kubernetes.io`, `search.maven.org`, `central.sonatype.com`,
   `api.osv.dev` (проверка уязвимостей зависимостей); без них агент идёт
   запасными путями (javadoc-jar и sources-jar с Maven Central, javadoc.io, исходники документации на
   raw.githubusercontent.com, `javap`) и отмечает это в отчёте.
3. Промпт: `Выполни gauntlet/INSTALL.md.` (в монорепо — `Выполни gauntlet/INSTALL.md для модулей core и adapter.`)
   Claude определит по файлам проекта и зафиксирует версии языка, сборщика, фреймворков и тестовых
   библиотек (`project.*`), подберёт и проверит совместимые инструменты, настроит `basePackage` и архитектуру,
   подключит скрипт в `build.gradle.kts`, добьётся зелёного прогона на текущем коде,
   подключит хуки и откроет PR с отчётом.
4. Прочитайте отчёт (исключения для старого кода, рёбра архитектуры против направления) — merge.

Дальше — раздел 1. Полезно завести две закладки с готовым промптом:
`https://claude.ai/code?repositories=<owner>/<repo>&prompt=...` (параметры `prompt` и `repositories`).

## 7. Почему агент не может «договориться» с гейтами

| Лазейка | Что закрывает |
|---|---|
| поднять порог, выключить задачу, поправить роль | `gauntlet/`, `.claude/`, `CLAUDE.md`, workflow защищены guard-хуком; правки `build.gradle*`, `buildSrc/`, `gradle/*` вроде `enabled = false`, фильтров тестов, `afterEvaluate` находит `integrityCheck` (правила B1–B5) |
| подогнать спецификацию под код | после коммита спецификации guard отклоняет её правку; `--amend`, `rebase`, `revert`, `reset --hard`, `push --force`/`--mirror`/`--all`, `checkout -B`, `branch -f`/`-D` запрещены: guard ловит их семантически (в т. ч. внутри `bash -c`, `eval`, обёрток `sudo`/`env`), а `permissions.deny` дублирует прямые формы префиксом. Префиксный deny и эвристика guard обходятся хитрой командой — настоящая опора для базовой ветки: GitHub branch protection + CI + diff PR, который читает человек |
| смержить самому | `gh pr merge` и API-merge запрещены; push в базовую ветку — тоже (и невозможен через GitHub-прокси облака) |
| `@Disabled`, `@Ignore`, `assume*`, `disabledWithoutDocker` | `integrityCheck` T1–T5 |
| спрятать код от JaCoCo и PIT через `@Generated` | `integrityCheck` M1 |
| `CHECKSTYLE:OFF`, `NOPMD`, `@SuppressWarnings("checkstyle…")` | M2–M3; в checkstyle.xml нет фильтров подавления |
| сценарий «skipped», а сборка зелёная | `acceptanceCheck` |
| фичи есть, а не исполнено ни одного сценария; устаревшие результаты прошлого прогона | `acceptanceCheck` (результаты стираются перед прогоном) |
| фича без значений «Примеров» проходит `gherkinMutation` вхолостую | `gherkinMutants`: «GHERKIN VACUOUS» по каждому сценарию со своими шагами, но без значений «Примеров»; сценарий без собственных шагов освобождён — Cucumber компилирует для него пустой pickle (Gherkin `compilePickleSteps` не подмешивает Background при пустом списке шагов), исполнять и мутировать нечего |
| два прогона Gradle в одном `build/` (фоновый прогон, Stop-хук, сабагент) | блокировка `.gradle/gauntlet-build.lock`: второй ждёт до 1500 с (`-Pgauntlet.lockWaitSeconds`) |
| hardener заканчивает с выжившими мутантами | SubagentStop-хук в `.claude/settings.json` (matcher `^hardener$`) гоняет `mutationGate` |
| hardener «временно» правит продакшен-файлы ради ручных мутантов (PIT нечего мутировать) | правило роли: мутанты предлагает списком, применяет, гоняет тесты и откатывает кодер, перед коммитом `src/main` проверяется на чистоту; guard по `agent_type` — растяжка, обход через скрипт виден в diff |
| мутант RUN_ERROR засчитан PIT как убитый, хотя тест не запускался | `PitSummary.java`: RUN_ERROR печатается `UNVERIFIED` и валит `mutationGate`, пока человек не впишет его в `config/pit-runerror-allowlist.txt` |
| обход guard через ключевые слова shell (`for … do rm`, `if …; then git push --force`) | guard разбирает команду после `do`, `then`, `else`, `{`, `!` так же, как после `&&` |
| обход human-only правил через обёртки и inline-код (`sudo git push --force`, `bash -c '…'`, `eval`, `echo '…' \| sh`, `echo git push --force \| bash` без кавычек, `python3 -c "os.system('…')"`, `python3.12 -c`, `node --eval "…"`, `perl -E '…'`, `subprocess.run(['git','push','--force'])`, `env -S 'git push --force'`, `"$(git push --force)"`, `"$(python3 -c 'print(")")'; git push --force)"`) | guard снимает обёртки (`sudo`/`env`/`exec`/`command`/`nohup`/`time` с их опциями, включая `env -S`/`--split-string`), рекурсивно проверяет код после `-c`/`-e` (и `--eval`/`--print` у node, `-E` у perl, версионные имена `python3.X`), `eval`/`source`, весь текст `echo`/`printf` через pipe (в кавычках и без), argv из отдельных кавычек (`subprocess`/`os.exec`/`execSync`) и тела подстановок `$(…)`/`` `…` `` вне одинарных кавычек — глубина учитывает кавычки, поэтому `)` внутри кавычек не обрывает тело |
| удалить `.git`, чтобы снять заморозку и Stop-хук, или подделать зелёный статус | `.git/` — зона человека: guard отклоняет запись/удаление, в т. ч. `last-green-*` в `.git/gauntlet-hook/` |
| `git push --mirror`/`--all`, `push HEAD`/`push origin @` (`@` — синоним HEAD) или push без refspec сидя на базовой ветке; `git -C <worktree> push` из feature-сессии, когда worktree на базовой ветке; `--no-verif` (сокращение), `core.hooksPath=/dev/null`; пути в другом регистре (`GAUNTLET/…`) | guard ловит все эти формы (push без refspec на базовой ветке = push базовой ветки при `push.default=simple`; текущая ветка берётся с учётом `-C`/`--git-dir`); `HEAD:other`/`@:other` базовой веткой не считаются и разрешены; сравнение путей и `mentions` регистронезависимы (macOS/Windows) |
| step-определение игнорирует параметр | `gherkinMutation` |
| слабые ассерты | `mutationGate` |
| сабагент вышел за роль | guard по `agent_type`: specifier пишет только фичи, hardener — только тесты, reviewer — ничего |
| закончить работу с красным гейтом | Stop-хук возвращает падения; после 3 попыток отпускает с предупреждением «работа не сделана» |

Проверка shell-команд в guard эвристическая: сознательный обход через хитрый Bash возможен. Известный
остаток — подстановка команды, порождающая имя бинарника (`$(which git) push --force`), разворачивание
переменной (`G=git; $G push --force`) и закодированные payload'ы: статический разбор их не видит.
`permissions.deny` тоже префиксный и обходится обёрткой. Опора — `integrityCheck`, CI, GitHub branch
protection базовой ветки и то, что любая попытка видна в diff PR, который читает человек. Это растяжка,
а не сейф.

## 8. Что проверено в этой версии, а что нет

Проверено здесь (Gradle 8.14.3, Java 21):
- Хуки, `hooks/selftest.py`, 994 проверки в трёх раскладках (сборка в корне; модуль `core/`; два модуля
  `core/` + `adapter/` — Gradle только в изменённом модуле, красный модуль блокирует, коммит
  спецификации одного модуля замораживает фичи другого, чужая незакоммиченная работа не считается)
  на временном git-репозитории с фиктивным `origin/main`:
  guard — роли и их shell-границы, заморозка спецификации по коммиту в ветке и её снятие после merge,
  `spec.approval=pr`, `--amend`/`rebase`/`revert`/`reset`/`checkout -B`/`branch -f`/`push --force`/push
  в базовую ветку, detached HEAD, `gh pr merge` (включая `-R` и GraphQL auto-merge), редиректы в кавычках
  и `2>`/`&>`, `rm -rf src` и `rm -rf *`, `cd … && cp`, `git -C`, `$PWD`/`$CLAUDE_PROJECT_DIR`, `xargs rm`,
  `$(…)`, запись в `~/.claude`; human-only правила внутри обёрток (`sudo`/`env`/`exec`/`command`/`nohup`,
  включая `env -S`/`--split-string`), inline-кода (`bash -c`, `python3 -c`/`node -e`/`node --eval`/`--print`,
  `perl -e`/`-E`, версионные `python3.X`, argv из отдельных кавычек `subprocess.run(['git','push',…])` с вложенным
  `os.system`/`subprocess`/`execSync`, многострочный `bash -c 'echo ok; git push --force'` — разделители
  в кавычках не режут payload), `eval`, pipe в интерпретатор (весь текст `echo`/`printf`, в кавычках и без)
  и тела подстановок `$(…)`/`` `…` `` вне одинарных кавычек (в двойных и без кавычек shell их исполняет;
  глубина учитывает кавычки — `)` внутри кавычек не обрывает тело); защита `.git/` (включая подделку
  `last-green-*`); `push --mirror`/`--all`/`HEAD`/`@` и push без refspec на базовой ветке, push через
  `-C`/`--git-dir` в worktree на базовой ветке (`HEAD:other`/`@:other` разрешены); сокращения
  `--no-verif` и `core.hooksPath`; регистронезависимые пути (`GAUNTLET/…`,
  `.Claude/…`); и отсутствие ложных срабатываний на `./gradlew gauntletFast`, `git add -A`,
  `git commit` (в том числе с heredoc-сообщением и словами `--no-verify`/`push --force`/`core.hooksPath` в тексте сообщения),
  `git stash push -m`, `tee build/…`, `rm -rf build`, `git push -u origin HEAD` на своей ветке,
  `sudo ./gradlew`, `bash -c 'echo hello'`, Python-тесты с лямбдами через heredoc; stop_gate — ход только
  со спецификацией не гоняет гейт (и после кодового хода тоже), незакоммиченные фичи исключают приёмку,
  коммит спецификации возвращает приёмку, красный результат не перезапускается, пока не изменились дерево
  или отчёты тестов, отпущенный красный напоминает о себе в следующих ходах, вопрос человеку проходит даже
  после красного, лимит попыток (окно повторов покрывает весь бюджет прогона — `timeout × число модулей`
  плюс запас; медленный двухмодульный `mutationGate` не сбрасывает счётчик), выключение переменной окружения;
  SubagentStop hardener'а — повторы считаются до лимита и отпускают;
  session_start — добывает `origin/main` в single-branch shallow-клоне.
- Два прохода независимого агента-ревьюера по набору: 12 и 7 находок (обход заморозки через
  `checkout -B` и `revert`, редиректы в кавычках, `disableAllHooks` через `~/.claude`, блокировка вопроса
  человеку после красного и т. д.) — все закрыты и покрыты самопроверкой.
- Ревью Kimi по PR: шесть функциональных находок подтверждены воспроизведением; пять закрыты, а правка
  `GherkinMutator` (K2, «пустой сценарий при непустом Background») позже отменена ревью Grok (G6) — её посылка
  оказалась неверной. Guard — тела подстановок `$(…)`/`` `…` `` в двойных кавычках и без кавычек,
  `env -S`/`--split-string`, push без refspec на базовой ветке (+36 проверок самопроверки); `stop_gate` — окно
  повторов на весь бюджет двух модулей (+15 проверок). `IntegrityCheck` (смешанная строка
  `test.enabled = false; jar { }`) — целевая Java-регрессия. Итого 682 → 733 проверки.
- Ревью Grok по PR: семь находок подтверждены воспроизведением и закрыты. Guard — некавыченный payload
  `echo`/`printf` через pipe, глубина подстановок с учётом кавычек (`)` внутри кавычек не обрывает тело),
  `@` как синоним HEAD (и `HEAD:other`/`@:other` не базовая ветка), push через `-C`/`--git-dir` в worktree на
  базовой ветке, версионные интерпретаторы (`python3.X`)/`node --eval`/`--print`/`perl -E`/argv из отдельных
  кавычек (+25 проверок × 3 раскладки = +75). `GherkinMutator` — отмена K2: пустой сценарий компилируется в
  пустой pickle (Gherkin 42.0.1, `PickleCompiler.compilePickleSteps` не подмешивает Background при пустом
  списке шагов; проверено на исходниках и прогоне — steps=0), поэтому всегда освобождён; ложный
  `GHERKIN VACUOUS` снят, сценарий со своими шагами без «Примеров» по-прежнему vacuous. `IntegrityCheck` —
  освобождение B1 проверяет получателя отключения: `test.enabled`/`tasks.test.enabled` внутри `jar { }` снова
  B1, легитимное `jar { enabled = false }` свободно. Итого 733 → 808 проверок.
- Ревью Codex по PR (полный прогон набора): находки V1–V7 подтверждены воспроизведением и закрыты;
  поведение гейтов не ослаблено. `install.sh` — слияние 4.2 → 4.3 обновляет поля уже установленных
  gauntlet-хуков (command/type/timeout/statusMessage/matcher), не теряет таймаут `SubagentStop`, масштабирует
  внешний таймаут Gradle-хуков по числу модулей (`Stop` ≥ 1800, `SubagentStop` ≥ 7200, плюс `timeout × модули`),
  объединяет права и пинит `disableAllHooks=false`; чужие хуки не трогает, дублей не плодит (идемпотентно).
  `CrapGate` — запись allowlist `Class#method(desc)` освобождает ровно одну перегрузку, `Class#method` без
  сигнатуры — только когда имя однозначно (при перегрузках не освобождает ничего и предупреждает); пустой
  `sourcefilename` (debug=false) выводится из имени класса, метод не пропускается молча; область `--only`
  сравнивает точный package-relative путь, а не суффикс. `IntegrityCheck` — получатель `delegate.enabled`/
  `this.enabled` внутри безобидного блока свободен, многострочная скобка переносит проверку на следующую строку.
  `GherkinMutator` — сценарий без собственных шагов (описание или пустой outline) не даёт мутантов и не vacuous
  (`stepCount`, а не «есть тело»); `<error>` (исключение/crash) в verdict — ошибка, а не kill; отсутствующий
  каталог фич в `no-skipped` — exit 1; перенос строки в тексте шага экранируется в литерал `\n` (без PARSE_ERROR).
  guard — сняты over-block: push из worktree после `cd`/`pushd` на своей ветке, `print`/`console.log` с литералом
  `git push`, pipe документа в `python3 script.py`/`node app.js`/`python3 -m json.tool` (stdin-код `bash -s`/
  `python3 -` по-прежнему блокируется). `stop_gate` — негативный код Gradle (сигнал) считается красным (`worst`),
  rename в `git status` разбирается по обоим концам, общий `gauntlet/config/` затрагивает все модули.
  `gauntlet.gradle` — `acceptanceTest` объявляет каталог фич входом (`PathSensitivity.RELATIVE`), `mutationGate`
  целит в скомпилированные типы (включая package-private и вложенные `Name$*`), а не в имена исходников.
  Сборщик/распаковщик бандла — побайтный round-trip (тело файла пишется без снятия/добавления переноса строки).
  Регрессии: guard print-литерал/stdin (+9) и cd-worktree push (+6) × 3 раскладки = +45; `stop_gate` —
  негативные коды и область модулей (rename/общий config) +13 × 3 = +39; целевые harness'ы `CrapGate` (14),
  `IntegrityCheck` (24), `GherkinMutator` (52), `install.sh` (29). Итого 808 → 892 проверки самопроверки.
- Второй раунд ревью Codex по PR: находки F1–F14 подтверждены воспроизведением и закрыты; поведение гейтов
  не ослаблено. `GherkinMutator` — сбой подготовки (`<failure>`/`<error>` в `@Before` до первого шага) считается
  ошибкой мутанта, а не убийством (kill только когда упал сам шаг); замена одной ячейки «Примеров» сохраняет
  outline и не портит соседнюю колонку (перенос строки в ячейке не превращается в два символа `\n`); неразрывный
  пробел (U+00A0) в отступе шага не теряется при подсчёте (`stepCount`). `CrapGate` — пустой/несовпадающий
  `sourcefilename` не пропускает метод молча; уникальность лямбд проверяется и по имени, принятому из allowlist.
  `gauntlet.gradle` — regex поиска типов находит объявление с аннотацией на той же строке
  (`@Deprecated final class X` в `Y.java`), `mutationGate` в режиме `changed` не даёт ложный «0 целей».
  `stop_gate` — закоммиченный rename берёт оба пути из `git diff --name-status -M`; вложенные сборки
  (`core,core/adapter`) — самый длинный совпавший префикс, а не первый; возраст отчётов сравнивается по модулю
  (отчёт второго модуля не сбрасывает кэш первого), удалённый отслеживаемый файл не выпадает из области Git.
  `install.sh` — команда узнаётся по запуску (интерпретатор + первый операнд-скрипт), а не по пути в любом
  аргументе (`sha256sum …/guard.py` остаётся пользовательским хуком); `matcher` группы трогается только когда
  все хуки в ней gauntlet'овские (соседний пользовательский хук не перестаёт запускаться). `IntegrityCheck` —
  получатель `it.enabled`/именованный параметр замыкания (`archive -> archive.enabled`) внутри безобидного блока
  свободен; `test.enabled`/чужое имя по-прежнему B1. guard — `cd` внутри подоболочки `( )`/`$( )` не утекает в
  родительскую оболочку (стек cwd), push своей ветки после `( cd ../main && git status )` разрешён; argv-список
  экранируется (`shlex.quote`), поэтому `subprocess.run(['echo', 'example; git rebase'])` — данные, а не команда
  (реальный `git push --force` в argv по-прежнему блокируется). Сборщик бандла (§8.4) — распаковщик поставляется
  вместе со сборщиком одной версии и встроенный round-trip сверяет побайтно (старый распаковщик добавлял LF).
  Регрессии: guard F10/F14 (+12 сценариев × 3 раскладки = +36) и stop_gate F6/F7/F13 (+42); целевые harness'ы
  `GherkinMutator` (12), `CrapGate` (8), `IntegrityCheck` (17), `stop_gate` (8), `install.sh` (19), guard (17),
  сборщик (14), regex PIT (15) — 110/110. Итого 892 → 970 проверок самопроверки.
- Третий раунд ревью Codex: `gherkinMutantsRun` закрепляет `cucumber.junit-platform.naming-strategy=long`,
  поэтому ID из манифеста сохраняется в JUnit XML; kill требует assertion именно в кадре шага Cucumber (включая
  Truth `ComparisonFailureWithFacts`), а `@Before` без кадра шага и `IOException("… is undefined")` — error.
  NBSP учитывается и в заголовках `Scenario Outline`/`Examples`. PIT/CRAP разбирают объявленные top-level типы
  с аннотациями, отступами и Unicode-именами; CRAP различает точный пакет и вложенный/верхнеуровневый тип.
  `install.sh` не принимает `legacy-gauntlet` за штатный каталог и выносит свой хук из смешанной группы в группу
  с эталонным matcher, не меняя пользовательскую. `IntegrityCheck` принимает `final Jar archive ->` и параметр
  на следующей строке. Guard использует `event.cwd` для Git и не трактует `-e` после программы `python -c` как
  новый код. Stop-gate проверяет и путь из начального dirty-списка, возвращённый к HEAD за сессию.
  Регрессии: selftest 970 → 985; Java/XML harness 27/27; install 14/14; реальные Gradle 8.14.3/JDK 21 —
  PIT 4/4 по `StandardPrices` и `Тариф`, CRAP 5 методов при debug=false, Cucumber 8.0.1 и 7.23.0 — 12/12 kill,
  `@Before` → 12 errors, контрольный survivor отдельно.
- Четвёртый раунд ревью Codex: PIT и CRAP используют объявленный Java-пакет и только объявленные типы,
  а не каталог/имя файла — изменённый класс вне ожидаемого каталога не теряется, чужой одноимённый класс не
  подключается. Установщик узнаёт только корневой `gauntlet/hooks` и одиночную управляемую команду, поэтому
  `tools/gauntlet` и `guard.py && auditor` сохраняются. Truth `AssertionErrorWithFacts` (`isTrue()`) засчитывается
  kill в шаге. Guard не исполняет аргументы после Python-скрипта/`-m`; `IntegrityCheck` принимает комментарий
  после `{` перед параметром замыкания. Регрессии: selftest 985 → 994, Java/XML 32/32, install 16/16; реальные
  PIT — `domain.Prices` найден, чужой `Rules` исключён; CRAP — 4 метода в changed и 2 для `Rules.java`;
  Cucumber 7.23.0 + Truth `isTrue()` — 12/12 kill; Gradle-комментарий — только `jar`/`sourcesJar` выключены.
- Управление версиями: на учебном проекте Java 17 + Gradle 8.14.3 + JUnit 5.12.2 + Cucumber 7.23.0
  `gauntletInfo` показал отдельную JVM 21 гейта, реальный `gherkinMutation` дал 12/12 kill, а манифест
  приложения не изменился. На втором проекте `gauntletInfo`/`integrityCheck` и PIT 8/8 прошли с той же настройкой.
  Workflow распарсен как YAML (7 шагов), чтение `gate.java.version` для CI проверено; GitHub Actions здесь
  не запускался.
- `install.sh` на демо-проекте: чистая установка; слияние с существующим `.claude/settings.json`
  (хуки и права добавлены, `disableAllHooks=false`); обновление 4.2 → 4.3 освежает поля gauntlet-хуков и
  масштабирует таймауты по модулям, чужие хуки и роль/`CLAUDE.md` не перезаписаны; идемпотентно (без дублей);
  отказ до любых изменений при битом JSON.
- Скрипт Gradle: конфигурация проекта, `integrityCheck`, `gauntletScope`, `gauntletInfo` — из корня
  (Kotlin DSL) и из двух модулей монорепо (Groovy DSL, `apply from: '../gauntlet/gauntlet.gradle'`,
  оверлей `config/adapter/` подхватывается); single-file Java-инструменты компилируются.
- Пороги и правила гейтов (Checkstyle, JaCoCo/CRAP, CPD, integrity, Gherkin-мутатор) не ослаблены: ни один
  порог, тест или правило не сняты. Правки инструментов закрывали обходы и проверялись на внесённом нарушении.

В эталонном проекте (Spring Boot 4.0, Gradle 8.14.3, Java 21, облачные сессии Claude Code) набор с ревизии 2
прошёл серию задач: реальные PIT, Cucumber-JVM с `# language: ru`, ArchUnit, хуки в облачной сессии
(`.claude/settings.json` и `.claude/agents/` из репозитория подхватываются в сессии с одним репозиторием),
CI на GitHub. Оттуда — правки ревизии 3: RUN_ERROR в `mutationGate`, SubagentStop для hardener'а,
блокировка одного прогона Gradle на `build/`, Docker из SessionStart, закрытые обходы guard. Ревизия 4 (ещё
десять задач серии): роль hardener при пустой области PIT, правка замороженной спецификации только человеком или
его делегатом, строки allowlist RUN_ERROR через PR владельца набора после его собственного прогона, правило «без
следов внешнего контура» в коде и документах, ревизия источников документации по фактической доступности.

## 9. Ограничения
- Метрики не ловят уязвимости и ошибки бизнес-логики, которых нет в спецификации. Для регулируемого
  контура стоит добавить SAST (SpotBugs+FindSecBugs или Semgrep) и проверку зависимостей.
- Хуки читаются только в сессии с одним репозиторием; в сессии с несколькими репозиториями и в тредах
  Projects они не работают. Одна сессия — один сервис.
- Облачная VM: ~4 vCPU, 16 ГБ, 30 ГБ; PIT на Spring-коде бывает медленным — помогают `scope=changed`,
  инкрементальный анализ и `@Tag("no-mutate")` для тяжёлых тестов.
- `pit.testStrengthThreshold=100` будет упираться в эквивалентных мутантов: агент остановится и покажет
  мутанта, решение за вами.
- Внутренние зависимости (общая библиотека из корпоративного Nexus) из облака недоступны: библиотека
  должна лежать в репозитории или тянуться из GitHub.
- Лицензии в swarm-forge нет, промпты ролей написаны заново по мотивам.

===== END FILE gauntlet/README.md =====

===== BEGIN FILE gauntlet/archtest/gauntlet/architecture/ArchitectureTest.java =====
package gauntlet.architecture;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;
import static org.junit.jupiter.api.Assertions.fail;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaPackage;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.library.metrics.ArchitectureMetrics;
import com.tngtech.archunit.library.metrics.ComponentDependencyMetrics;
import com.tngtech.archunit.library.metrics.MetricsComponents;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Properties;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;

/**
 * Architecture gate. The policy lives in gauntlet/config/architecture.properties (human-owned);
 * this test only enforces it. Run with ./gradlew archTest.
 */
class ArchitectureTest {

    private static final Properties POLICY = load();
    private static final String BASE = POLICY.getProperty("base.package", "").trim();
    private static final JavaClasses CLASSES = new ClassFileImporter()
            .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
            .importPackages(BASE);

    @Test
    void basePackageContainsProductionClasses() {
        if (CLASSES.isEmpty()) {
            fail("No production classes found under base.package=" + BASE
                    + " - check gauntlet/config/architecture.properties.");
        }
    }

    @Test
    void everyComponentIsDeclaredInThePolicy() {
        List<String> undeclared = new ArrayList<>();
        for (String component : componentsInCode()) {
            if (!POLICY.containsKey("allowed." + component)) {
                undeclared.add(component);
            }
        }
        if (!undeclared.isEmpty()) {
            fail("Undeclared component(s) under " + BASE + ": " + undeclared + ". The human must add "
                    + "allowed.<component>=... to gauntlet/config/architecture.properties (or move the code).");
        }
    }

    @Test
    void componentsDependOnlyOnAllowedComponents() {
        Set<String> all = allComponents();
        List<String> violations = new ArrayList<>();
        for (String component : all) {
            Set<String> allowed = csv(POLICY.getProperty("allowed." + component, ""));
            List<String> forbidden = new ArrayList<>();
            for (String other : all) {
                if (!other.equals(component) && !allowed.contains(other)) {
                    forbidden.add(BASE + "." + other + "..");
                }
            }
            if (!forbidden.isEmpty()) {
                check(noClasses().that().resideInAPackage(BASE + "." + component + "..")
                        .should().dependOnClassesThat().resideInAnyPackage(forbidden.toArray(new String[0]))
                        .because("architecture.properties allows " + component + " -> " + allowed)
                        .allowEmptyShould(true), violations);
            }
        }
        failIfAny(violations);
    }

    @Test
    void componentsStayAwayFromForbiddenPackages() {
        List<String> violations = new ArrayList<>();
        for (String key : POLICY.stringPropertyNames()) {
            if (!key.startsWith("forbidden.")) {
                continue;
            }
            String component = key.substring("forbidden.".length());
            Set<String> packages = csv(POLICY.getProperty(key));
            if (!packages.isEmpty()) {
                check(noClasses().that().resideInAPackage(BASE + "." + component + "..")
                        .should().dependOnClassesThat().resideInAnyPackage(packages.toArray(new String[0]))
                        .because("architecture.properties forbids " + component + " -> " + packages)
                        .allowEmptyShould(true), violations);
            }
        }
        failIfAny(violations);
    }

    @Test
    void noCyclesBetweenComponents() {
        if (Boolean.parseBoolean(POLICY.getProperty("fail.on.cycles", "true"))) {
            slices().matching(BASE + ".(*)..").should().beFreeOfCycles().allowEmptyShould(true).check(CLASSES);
        }
    }

    @Test
    void componentMetrics() {
        JavaPackage base = CLASSES.getPackage(BASE);
        ComponentDependencyMetrics metrics =
                ArchitectureMetrics.componentDependencyMetrics(MetricsComponents.fromPackages(base.getSubpackages()));
        String maxDistance = POLICY.getProperty("max.distance", "").trim();
        List<String> tooFar = new ArrayList<>();
        System.out.println("ARCH component          Ca   Ce      I      A      D");
        List<JavaPackage> components = base.getSubpackages().stream()
                .sorted(Comparator.comparing(JavaPackage::getName)).toList();
        for (JavaPackage p : components) {
            String id = p.getName();
            double d = metrics.getNormalizedDistanceFromMainSequence(id);
            System.out.printf(Locale.ROOT, "ARCH %-18s %4d %4d %6.2f %6.2f %6.2f%n", p.getRelativeName(),
                    metrics.getAfferentCoupling(id), metrics.getEfferentCoupling(id), metrics.getInstability(id),
                    metrics.getAbstractness(id), d);
            if (!maxDistance.isEmpty() && d > Double.parseDouble(maxDistance)) {
                tooFar.add(p.getRelativeName() + " D=" + String.format(Locale.ROOT, "%.2f", d));
            }
        }
        if (!tooFar.isEmpty()) {
            fail("Components too far from the main sequence (max " + maxDistance + "): " + tooFar
                    + ". Stable components should be abstract, unstable ones concrete.");
        }
    }

    // ------------------------------------------------------------------ helpers

    private static Set<String> componentsInCode() {
        Set<String> names = new TreeSet<>();
        for (JavaPackage p : CLASSES.getPackage(BASE).getSubpackages()) {
            names.add(p.getRelativeName());
        }
        return names;
    }

    private static Set<String> allComponents() {
        Set<String> names = componentsInCode();
        for (String key : POLICY.stringPropertyNames()) {
            if (key.startsWith("allowed.")) {
                names.add(key.substring("allowed.".length()));
            }
        }
        return names;
    }

    private static void check(ArchRule rule, List<String> violations) {
        try {
            rule.check(CLASSES);
        } catch (AssertionError e) {
            violations.add(e.getMessage());
        }
    }

    private static void failIfAny(List<String> violations) {
        if (!violations.isEmpty()) {
            fail(String.join("\n\n", violations));
        }
    }

    private static Set<String> csv(String value) {
        Set<String> set = new TreeSet<>();
        Arrays.stream(value.split(",")).map(String::trim).filter(s -> !s.isEmpty()).forEach(set::add);
        return set;
    }

    private static Properties load() {
        Path file = Path.of(System.getProperty("gauntlet.architecture", "gauntlet/config/architecture.properties"));
        Properties p = new Properties();
        try (InputStream in = Files.newInputStream(file)) {
            p.load(in);
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read architecture policy " + file.toAbsolutePath(), e);
        }
        if (p.getProperty("base.package", "").isBlank()) {
            throw new IllegalStateException("base.package is missing in " + file.toAbsolutePath());
        }
        return p;
    }
}

===== END FILE gauntlet/archtest/gauntlet/architecture/ArchitectureTest.java =====

===== BEGIN FILE gauntlet/config/architecture.properties =====
# =============================================================================
#  Architecture policy - HUMAN-OWNED. Checked by gauntlet/archtest (ArchUnit),
#  modelled on unclebob/dependency-checker: components, allowed edges, no cycles, metrics.
# =============================================================================

# Root package. Components are its direct sub-packages (e.g. com.example.service.domain).
base.package=com.example.service

# allowed.<component> = components it MAY depend on (comma-separated, empty = none).
# Anything not listed is a violation. Every component found in the code must be declared.
# Dependencies point toward policy: adapters -> application -> domain, never back.
allowed.domain=
allowed.application=domain
allowed.api=application,domain
allowed.infrastructure=application,domain

# forbidden.<component> = outside packages it must not touch (ArchUnit package syntax).
# Keeps the domain free of framework, persistence and transport details.
forbidden.domain=org.springframework..,jakarta.persistence..,org.hibernate..,com.fasterxml.jackson..
forbidden.application=org.springframework.web..,jakarta.persistence..

# Fail on dependency cycles between components.
fail.on.cycles=true

# Martin's "distance from the main sequence" D = |A + I - 1| per component (0..1).
# Empty = report only. Uncle Bob's dependency-checker flags the zones of pain/uselessness.
max.distance=

===== END FILE gauntlet/config/architecture.properties =====

===== BEGIN FILE gauntlet/config/checkstyle.xml =====
<?xml version="1.0"?>
<!DOCTYPE module PUBLIC
        "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN"
        "https://checkstyle.org/dtds/configuration_1_3.dtd">
<!--
  Size, structure and control flow - no formatting rules. HUMAN-OWNED (gauntlet/ is guarded).
  Uncle Bob measures "module sizes" and keeps functions small; these are the kit's defaults.
  Anti-patterns that need semantics (types, exceptions, concurrency) live in pmd-ruleset.xml (pmdGate).
  There is deliberately no SuppressWarningsFilter / comment filter: agents cannot switch rules
  off inline. Human-approved exceptions go to checkstyle-suppressions.xml (optional file).
-->
<module name="Checker">
    <property name="severity" value="error"/>
    <property name="fileExtensions" value="java"/>

    <module name="SuppressionFilter">
        <property name="file" value="${config_loc}/checkstyle-suppressions.xml"/>
        <property name="optional" value="true"/>
    </module>

    <!-- A file that needs more than this usually has more than one job. -->
    <module name="FileLength">
        <property name="max" value="300"/>
    </module>

    <module name="TreeWalker">
        <!-- Small functions. Blank lines and comments do not count. -->
        <module name="MethodLength">
            <property name="max" value="25"/>
            <property name="countEmpty" value="false"/>
        </module>
        <module name="LambdaBodyLength">
            <property name="max" value="10"/>
        </module>
        <!-- Few arguments (Clean Code: more than three needs a very good reason).
             Constructors are exempt: DI constructors are policed by ClassFanOutComplexity. -->
        <module name="ParameterNumber">
            <property name="max" value="4"/>
            <property name="ignoreOverriddenMethods" value="true"/>
            <property name="tokens" value="METHOD_DEF"/>
        </module>
        <!-- Simple functions: cyclomatic complexity below 4 (Martin's CC < 4) at the source, not only via CRAP,
             which forgives complexity when coverage is high. A switch counts as one decision point. -->
        <module name="CyclomaticComplexity">
            <property name="max" value="3"/>
            <property name="switchBlockAsSingleDecisionPoint" value="true"/>
        </module>
        <!-- Number of acyclic execution paths through a method. -->
        <module name="NPathComplexity">
            <property name="max" value="20"/>
        </module>
        <!-- Shallow control flow. -->
        <module name="NestedIfDepth">
            <property name="max" value="1"/>
        </module>
        <module name="NestedForDepth">
            <property name="max" value="1"/>
        </module>
        <module name="NestedTryDepth">
            <property name="max" value="1"/>
        </module>
        <module name="BooleanExpressionComplexity">
            <property name="max" value="3"/>
        </module>
        <!-- Coupling: how many other classes one class depends on. -->
        <module name="ClassFanOutComplexity">
            <property name="max" value="20"/>
        </module>
        <!-- One top-level type per file. -->
        <module name="OuterTypeNumber">
            <property name="max" value="1"/>
        </module>

        <!-- Control flow that hides intent. -->
        <module name="NeedBraces"/>
        <module name="AvoidNestedBlocks">
            <property name="allowInSwitchCase" value="true"/>
        </module>
        <module name="OneStatementPerLine"/>
        <module name="MultipleVariableDeclarations"/>
        <module name="InnerAssignment"/>
        <module name="ModifiedControlVariable"/>
        <module name="MissingSwitchDefault"/>
        <module name="SimplifyBooleanExpression"/>
        <module name="SimplifyBooleanReturn"/>
        <module name="EqualsHashCode"/>
        <!-- A number in the logic needs a name. -1, 0, 1, 2 and constant definitions are fine. -->
        <module name="MagicNumber">
            <property name="ignoreHashCodeMethod" value="true"/>
            <property name="ignoreAnnotation" value="true"/>
        </module>
        <!-- Catching Exception/RuntimeException is a human decision: the service catches broadly at its
             boundaries (listeners, dispatchers, parsers) on purpose. Enable here (per-file exceptions in
             checkstyle-suppressions.xml) or extend AvoidCatchingGenericException in pmd-ruleset.xml, which
             already forbids Throwable, Error and NullPointerException. -->
        <!-- <module name="IllegalCatch"/> -->
    </module>
</module>

===== END FILE gauntlet/config/checkstyle.xml =====

===== BEGIN FILE gauntlet/config/crap-allowlist.txt =====
# Human-approved CRAP exceptions. One method per line:  fully.qualified.Class#method   # reason
# Use it for the case Uncle Bob allows: "a single switch that answers one question may stay
# above the limit - do not split it into helpers that take booleans the caller already knew".
# Class#* allows every method of a class. Agents cannot edit this file.
#
# Overloads: a name-only Class#method entry exempts the method only when that name is unique in
# the class. If the class has several overloads of the name, the entry is ambiguous and exempts
# NOTHING (the gate prints the descriptors and fails) - a later overload must not inherit an
# exception approved for an older one. Pick the exact overload with its JVM descriptor:
#   Class#method(I)D            # quote(int)
#   Class#method(Ljava/lang/String;)D   # quote(String)
#
# com.example.service.domain.DeliveryZone#forRegionCode   # one switch over 12 region codes

===== END FILE gauntlet/config/crap-allowlist.txt =====

===== BEGIN FILE gauntlet/config/gauntlet.properties =====
# =============================================================================
#  Gauntlet thresholds. HUMAN-OWNED: agents are blocked from editing gauntlet/.
#  Uncle Bob's own numbers are quoted in comments; defaults below are the kit's.
# =============================================================================

# --- process -----------------------------------------------------------------
# How the human approves the Gherkin specification (see gauntlet/CLAUDE.md, step 3):
#   chat = the agent stops after the specifier and waits for "yes" in the chat; once the spec is
#          committed on the branch the guard hook freezes the feature files (default, closest to
#          Uncle Bob's "specifier -> human approval -> coder").
#   pr   = the agent does not stop; the human reads the Gherkin in the pull request. No freeze:
#          the PR diff is the only control over spec changes.
spec.approval=chat

# --- layout ------------------------------------------------------------------
# Directories of the Gradle builds this gauntlet guards, relative to the repository root, comma-separated.
# Empty = one build (build.gradle[.kts], gradlew, src/) at the root. In a monorepo with independent
# builds list them, e.g. module=core,adapter: the hooks run Gradle in every module that
# changed, CI in all of them; src/ and build/ are each module's, gauntlet/ stays at the root. Settings
# a module needs differently (basePackage, acceptance.glue, exclude.classes, the architecture) go to
# gauntlet/config/<module>/: gauntlet.properties there overlays this file, any other file there
# (architecture.properties, checkstyle.xml, *-allowlist.txt) replaces the common one of the same name.
# acceptance.features must be the same relative path in every module. `./gradlew gauntletInfo` shows
# what a build resolved. Every module's spec is one specification: a spec commit freezes them all.
module=core,adapter

# --- scope -------------------------------------------------------------------
# changed = check only what differs from baseRef (+ uncommitted/untracked files).
#           Uncle Bob: "differential" mutation, CRAP gate "on changed files".
#           Use it to adopt the gauntlet in an existing service without fixing history.
# all     = check the whole codebase (new projects, nightly CI).
# Overridable per run: ./gradlew gauntlet -Pgauntlet.scope=all -Pgauntlet.baseRef=origin/develop
scope=changed
baseRef=origin/main

# Root package of the service. Used when scope=all to target mutation testing.
# In a monorepo a module may set its own basePackage in gauntlet/config/<module>/gauntlet.properties.
basePackage=com.example.service

# Class-name globs excluded from coverage, CRAP and mutation: bootstrap and generated code, plus
# thin IO adapters that only integration tests can exercise (Uncle Bob keeps such "environmentally
# unsuitable" modules as small shells outside coverage/mutation), e.g. *Repository,*Client,*Listener.
#   *Repository*  Spring Data interfaces and their *RepositoryImpl/*RepositoryCustom: JPQL and native SQL
#                 (including locking queries) that only a real database exercises. HTTP clients (*HttpClient)
#                 are NOT excluded: they have WireMock/Mockito unit tests. Listeners, workers, dispatchers,
#                 parsers, mappers, services and schedulers stay in.
exclude.classes=*Application,*MapperImpl,*Config,*Configuration,*Properties,*Repository*

# --- CRAP (complexity x lack of coverage) -------------------------------------
# CRAP = CC^2 * (1 - coverage)^3 + CC.  unclebob/crap4java fails above 8.0; his swarm-forge
# roles use "10 or below". He also suggests keeping cyclomatic complexity "below 4 or so".
crap.threshold=8

# --- DRY (PMD copy/paste detector) ----------------------------------------------
# Uncle Bob's dry4java: structural similarity >= 0.82, >= 4 lines, >= 20 AST nodes.
# CPD equivalent here: token runs with identifiers and literals normalised away.
dry.minimumTokens=60
dry.ignoreIdentifiers=true
dry.ignoreLiterals=true
dry.maxDuplications=0
# Paths relative to the module (files or directories, comma-separated) left out of the duplicate search:
# CPD --exclude (PMD 7.27.0 CLI reference, "--exclude", CPD since 7.0.0). Set per module in its overlay, with the reason.
dry.exclude=

# --- Mutation testing (PIT) -------------------------------------------------------
# Uncle Bob (mutate4java): every COVERED mutant must be killed, differential runs only.
# PIT "test strength" = killed / mutants with coverage, in percent -> 100 is exactly that rule.
pit.testStrengthThreshold=100
# Line coverage of the mutated (changed) classes by the tests PIT runs, percent. 0 = off.
# Uncle Bob: "use mutation to cover the uncovered and kill survivors".
pit.coverageThreshold=80
pit.mutators=DEFAULTS
pit.threads=4
# Tests tagged @Tag("no-mutate") are skipped by PIT (same convention as mutate4java).
pit.excludedGroups=no-mutate
# swarm-forge: a file with >100 mutation sites probably mixes jobs (warning only).
pit.maxMutationsPerFile=100

# --- Acceptance (Cucumber) ----------------------------------------------------------
acceptance.features=src/acceptanceTest/resources/features
# Package(s) with step definitions and the @CucumberContextConfiguration class.
acceptance.glue=com.example.service.acceptance
# Adds io.cucumber:cucumber-spring (Spring Boot projects).
acceptance.spring=true

# --- Tool versions (pit.version = the default of gradle-pitest-plugin 1.19.0; newer PIT usually works) ----
# Cucumber must match the JUnit Platform your Spring Boot manages:
#   Spring Boot 3.5.x (JUnit 5.12) -> 7.23.0   (built against JUnit 5.12.2)
#   Spring Boot 4.x   (JUnit 6.0)  -> 8.0.1 and set junit-jupiter.version=6.1.2 (see INSTALL.md)
cucumber.version=8.0.1
archunit.version=1.5.1
pit.version=1.22.1
pit.junit5PluginVersion=1.2.3
jacoco.version=0.8.15
checkstyle.version=12.3.1
pmd.version=7.27.0

# --- Project versions detected by start (examples for the reference project; replace, do not inherit) ---
project.java.version=21
project.gradle.version=8.14.3
project.framework.springBoot.version=4.0.7
project.test.junit-jupiter.version=6.1.2

# JVM for Gauntlet tools only. The application keeps its own Java/toolchain and dependencies.
# gate.java.home is an optional local absolute path; CI uses gate.java.version.
gate.java.version=21
gate.java.home=

===== END FILE gauntlet/config/gauntlet.properties =====

===== BEGIN FILE gauntlet/config/integrity-allowlist.txt =====
# Human-approved integrity exceptions:   <path glob from project root>  <RULE-ID>   # reason
# Rule IDs are printed by the integrity check (T1..T5 tests, M1..M3 main code, F1 features,
# B1..B5 build scripts, P1 test properties). Agents cannot edit this file.
#
# src/main/java/**/entity/*.java          M1   # Hibernate @Generated on DB-generated columns
# build.gradle.kts                        B2   # excludeTags("slow") reviewed by a human

===== END FILE gauntlet/config/integrity-allowlist.txt =====

===== BEGIN FILE gauntlet/config/pit-runerror-allowlist.txt =====
# Human-verified RUN_ERROR mutants. One line per method and mutator:  fully.qualified.Class#method  Mutator   # which test kills it
# PIT 1.22.1 counts RUN_ERROR as detected, but the test JVM crashed on redefineClasses (records) before any
# test ran, so nothing proved the mutant dead. A line here says a human read the tests and named the
# assertion that fails for the mutant. The key is the method and the mutator, not the line number or the
# description: RUN_ERROR is not deterministic (another run crashes on another mutant), and line numbers
# go stale on every edit. So a line covers every RUN_ERROR of that mutator in that method - keep the
# mutator explicit (one line per verified mutator, as for the two Boolean*ReturnVals of a lambda) and
# reread the tests when the method grows a new conditional, return or lambda. The mutator is the simple
# PIT name; omit it (or use *) only when every mutator of the method was verified; * also works inside
# the method name (lambda$of$* - the compiler numbers lambdas). Agents cannot edit this file.
#
# Before adding a line: run the tests, read the mutated line, find the assertion that fails for exactly
# this mutation. A mutant with no such assertion is a weak test, not an allowlist entry.

# Example (remove): OrderTotalTest.discountAppliesOnlyAboveThreshold fails when the boundary moves.
# com.example.service.domain.OrderTotal#discount  ConditionalsBoundaryMutator  # discountAppliesOnlyAboveThreshold: 100 -> no discount

===== END FILE gauntlet/config/pit-runerror-allowlist.txt =====

===== BEGIN FILE gauntlet/config/pmd-ruleset.xml =====
<?xml version="1.0" encoding="UTF-8"?>
<!--
  Anti-patterns - what Checkstyle (size, structure, control flow) and CRAP/DRY do not see. HUMAN-OWNED
  (gauntlet/ is guarded). Runs as the pmdGate task over the main sources in scope; any violation fails.
  Rules the kit already enforces elsewhere are deliberately absent: cyclomatic/NPath complexity, nesting,
  braces, magic numbers, inner assignments, one statement per line (checkstyle.xml), duplicated code
  (dryGate), disabled tests and inline suppressions (integrityCheck). Suppressed violations
  (@SuppressWarnings("PMD...") or NOPMD) are reported as violations too: agents cannot switch rules off
  inline. A human-approved exception goes here (exclude-pattern, or a rule property such as
  violationSuppressXPath) - nowhere else.
  Reference: https://docs.pmd-code.org/latest/pmd_rules_java.html
-->
<ruleset name="gauntlet"
         xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">
    <description>Gauntlet: anti-patterns in design, error handling, concurrency, security and readability.</description>

    <!-- ===== design (SOLID smells) ===== -->
    <!-- Single responsibility: too much state and behaviour in one class (WMC >= 47, ATFD > 5, TCC < 1/3). -->
    <rule ref="category/java/design.xml/GodClass"/>
    <!-- Getters, setters, equals/hashCode/toString and overridden methods are not counted. -->
    <rule ref="category/java/design.xml/TooManyMethods">
        <properties>
            <property name="maxmethods" value="12"/>
        </properties>
    </rule>
    <!-- Cognitive complexity (SonarSource): nesting and breaks in linear flow - a backstop next to CC < 4. -->
    <rule ref="category/java/design.xml/CognitiveComplexity">
        <properties>
            <property name="reportLevel" value="10"/>
        </properties>
    </rule>
    <rule ref="category/java/design.xml/AvoidThrowingRawExceptionTypes"/>
    <rule ref="category/java/design.xml/AvoidThrowingNullPointerException"/>
    <rule ref="category/java/design.xml/AvoidRethrowingException"/>
    <rule ref="category/java/design.xml/AvoidThrowingNewInstanceOfSameException"/>
    <rule ref="category/java/design.xml/ExceptionAsFlowControl"/>
    <rule ref="category/java/design.xml/SignatureDeclareThrowsException"/>
    <rule ref="category/java/design.xml/DoNotExtendJavaLangError"/>
    <rule ref="category/java/design.xml/MutableStaticState"/>
    <rule ref="category/java/design.xml/SingularField"/>
    <rule ref="category/java/design.xml/ImmutableField"/>
    <rule ref="category/java/design.xml/FinalFieldCouldBeStatic"/>
    <rule ref="category/java/design.xml/UselessOverridingMethod"/>
    <rule ref="category/java/design.xml/ClassWithOnlyPrivateConstructorsShouldBeFinal"/>
    <rule ref="category/java/design.xml/InstantiableUtilityClass"/>
    <rule ref="category/java/design.xml/CollapsibleIfStatements"/>
    <rule ref="category/java/design.xml/LogicInversion"/>
    <rule ref="category/java/design.xml/SimplifiedTernary"/>
    <rule ref="category/java/design.xml/SimplifyConditional"/>
    <!-- Law of Demeter: correct in spirit, too noisy on fluent builders and streams to be a hard gate. -->
    <!-- <rule ref="category/java/design.xml/LawOfDemeter"/> -->

    <!-- ===== error handling and error-prone code ===== -->
    <!-- Throwable, Error and NullPointerException are never caught. Catching Exception/RuntimeException is
         a human decision: the service catches broadly at its boundaries (listeners, dispatchers, parsers) on
         purpose. To forbid it too, add java.lang.Exception,java.lang.RuntimeException to the list below
         (or enable IllegalCatch in checkstyle.xml, which has per-file suppressions). -->
    <rule ref="category/java/errorprone.xml/AvoidCatchingGenericException">
        <properties>
            <property name="typesThatShouldNotBeCaught"
                      value="java.lang.Throwable,java.lang.Error,java.lang.NullPointerException"/>
        </properties>
    </rule>
    <rule ref="category/java/errorprone.xml/EmptyCatchBlock"/>
    <rule ref="category/java/errorprone.xml/AvoidInstanceofChecksInCatchClause"/>
    <rule ref="category/java/errorprone.xml/DoNotThrowExceptionInFinally"/>
    <rule ref="category/java/errorprone.xml/ReturnFromFinallyBlock"/>
    <rule ref="category/java/errorprone.xml/ReturnEmptyCollectionRatherThanNull"/>
    <rule ref="category/java/errorprone.xml/CloseResource"/>
    <rule ref="category/java/errorprone.xml/CompareObjectsWithEquals"/>
    <rule ref="category/java/errorprone.xml/UseEqualsToCompareStrings"/>
    <rule ref="category/java/errorprone.xml/EqualsNull"/>
    <rule ref="category/java/errorprone.xml/BrokenNullCheck"/>
    <rule ref="category/java/errorprone.xml/MisplacedNullCheck"/>
    <rule ref="category/java/errorprone.xml/UnusedNullCheckInEquals"/>
    <rule ref="category/java/errorprone.xml/ConstructorCallsOverridableMethod"/>
    <rule ref="category/java/errorprone.xml/ImplicitSwitchFallThrough"/>
    <rule ref="category/java/errorprone.xml/UnconditionalIfStatement"/>
    <rule ref="category/java/errorprone.xml/IdenticalConditionalBranches"/>
    <rule ref="category/java/errorprone.xml/IdempotentOperations"/>
    <rule ref="category/java/errorprone.xml/AvoidBranchingStatementAsLastInLoop"/>
    <rule ref="category/java/errorprone.xml/JumbledIncrementer"/>
    <rule ref="category/java/errorprone.xml/DontUseFloatTypeForLoopIndices"/>
    <rule ref="category/java/errorprone.xml/ComparisonWithNaN"/>
    <rule ref="category/java/errorprone.xml/NonStaticInitializer"/>
    <!-- Ignored result of a pure method (String.trim(), BigDecimal.add(), InputStream.skip()...). -->
    <rule ref="category/java/errorprone.xml/UnusedReturnValue"/>
    <rule ref="category/java/errorprone.xml/CollectionTypeMismatch"/>
    <rule ref="category/java/errorprone.xml/ConfusingArgumentToVarargsMethod"/>
    <rule ref="category/java/errorprone.xml/UseLocaleWithCaseConversions"/>
    <rule ref="category/java/errorprone.xml/UnnecessaryCaseChange"/>
    <!-- SLF4J placeholders vs arguments. -->
    <rule ref="category/java/errorprone.xml/InvalidLogMessageFormat"/>

    <!-- ===== best practices ===== -->
    <rule ref="category/java/bestpractices.xml/PreserveStackTrace"/>
    <rule ref="category/java/bestpractices.xml/UnusedPrivateField"/>
    <rule ref="category/java/bestpractices.xml/UnusedPrivateMethod"/>
    <rule ref="category/java/bestpractices.xml/UnusedLocalVariable"/>
    <rule ref="category/java/bestpractices.xml/UnusedFormalParameter"/>
    <rule ref="category/java/bestpractices.xml/UnusedAssignment"/>
    <rule ref="category/java/bestpractices.xml/AvoidReassigningParameters"/>
    <rule ref="category/java/bestpractices.xml/AvoidReassigningLoopVariables"/>
    <rule ref="category/java/bestpractices.xml/AvoidReassigningCatchVariables"/>
    <!-- Depend on abstractions (DIP): List, Map, Set - not ArrayList, HashMap, HashSet. -->
    <rule ref="category/java/bestpractices.xml/LooseCoupling"/>
    <rule ref="category/java/bestpractices.xml/AbstractClassWithoutAbstractMethod"/>
    <rule ref="category/java/bestpractices.xml/MissingOverride"/>
    <rule ref="category/java/bestpractices.xml/AvoidPrintStackTrace"/>
    <rule ref="category/java/bestpractices.xml/SystemPrintln"/>
    <rule ref="category/java/bestpractices.xml/UseCollectionIsEmpty"/>
    <rule ref="category/java/bestpractices.xml/LiteralsFirstInComparisons"/>
    <rule ref="category/java/bestpractices.xml/ForLoopCanBeForeach"/>
    <rule ref="category/java/bestpractices.xml/UseTryWithResources"/>
    <rule ref="category/java/bestpractices.xml/CheckResultSet"/>
    <rule ref="category/java/bestpractices.xml/ArrayIsStoredDirectly"/>
    <rule ref="category/java/bestpractices.xml/MethodReturnsInternalArray"/>
    <rule ref="category/java/bestpractices.xml/AvoidStringBufferField"/>
    <rule ref="category/java/bestpractices.xml/AvoidMessageDigestField"/>
    <rule ref="category/java/bestpractices.xml/DoubleBraceInitialization"/>
    <rule ref="category/java/bestpractices.xml/AvoidUsingHardCodedIP"/>
    <rule ref="category/java/bestpractices.xml/RelianceOnDefaultCharset"/>
    <rule ref="category/java/bestpractices.xml/UseStandardCharsets"/>
    <rule ref="category/java/bestpractices.xml/UseEnumCollections"/>

    <!-- ===== concurrency ===== -->
    <rule ref="category/java/multithreading.xml/AvoidSynchronizedAtMethodLevel"/>
    <rule ref="category/java/multithreading.xml/DoubleCheckedLocking"/>
    <rule ref="category/java/multithreading.xml/NonThreadSafeSingleton"/>
    <rule ref="category/java/multithreading.xml/UnsynchronizedStaticFormatter"/>
    <rule ref="category/java/multithreading.xml/AvoidThreadGroup"/>
    <rule ref="category/java/multithreading.xml/DontCallThreadRun"/>
    <rule ref="category/java/multithreading.xml/UseNotifyAllInsteadOfNotify"/>

    <!-- ===== security ===== -->
    <rule ref="category/java/security.xml/HardCodedCryptoKey"/>
    <rule ref="category/java/security.xml/InsecureCryptoIv"/>

    <!-- ===== performance (only the ones that are also readability) ===== -->
    <rule ref="category/java/performance.xml/StringInstantiation"/>
    <rule ref="category/java/performance.xml/StringToString"/>
    <rule ref="category/java/performance.xml/UselessStringValueOf"/>
    <rule ref="category/java/performance.xml/AddEmptyString"/>
    <rule ref="category/java/performance.xml/AppendCharacterWithChar"/>
    <rule ref="category/java/performance.xml/InefficientStringBuffering"/>
    <rule ref="category/java/performance.xml/UseStringBufferForStringAppends"/>
    <rule ref="category/java/performance.xml/InefficientEmptyStringCheck"/>
    <rule ref="category/java/performance.xml/UseIndexOfChar"/>
    <rule ref="category/java/performance.xml/BigIntegerInstantiation"/>
    <rule ref="category/java/performance.xml/AvoidCalendarDateCreation"/>
    <rule ref="category/java/performance.xml/AvoidFileStream"/>

    <!-- ===== readability (no formatting: only what hides intent) ===== -->
    <rule ref="category/java/codestyle.xml/LinguisticNaming"/>
    <rule ref="category/java/codestyle.xml/UnnecessaryFullyQualifiedName"/>
    <rule ref="category/java/codestyle.xml/UnnecessaryImport"/>
    <rule ref="category/java/codestyle.xml/UnnecessaryModifier"/>
    <rule ref="category/java/codestyle.xml/UnnecessaryReturn"/>
    <rule ref="category/java/codestyle.xml/UnnecessarySemicolon"/>
    <rule ref="category/java/codestyle.xml/UnnecessaryBoxing"/>
    <rule ref="category/java/codestyle.xml/UnnecessaryCast"/>
    <rule ref="category/java/codestyle.xml/UnnecessaryConstructor"/>
    <rule ref="category/java/codestyle.xml/VariableCanBeInlined"/>
    <rule ref="category/java/codestyle.xml/UselessQualifiedThis"/>
    <rule ref="category/java/codestyle.xml/IdenticalCatchBranches"/>
    <rule ref="category/java/codestyle.xml/EmptyControlStatement"/>
    <rule ref="category/java/codestyle.xml/ForLoopShouldBeWhileLoop"/>
    <rule ref="category/java/codestyle.xml/ExtendsObject"/>
    <rule ref="category/java/codestyle.xml/UseDiamondOperator"/>
    <rule ref="category/java/codestyle.xml/ModifierOrder"/>
    <rule ref="category/java/codestyle.xml/FieldDeclarationsShouldBeAtStartOfClass"/>
</ruleset>

===== END FILE gauntlet/config/pmd-ruleset.xml =====

===== BEGIN FILE gauntlet/gauntlet.gradle =====
/*
 * =============================================================================================
 *  GAUNTLET - the checks that let you stop reading AI-written code (after Robert C. Martin).
 *  HUMAN-OWNED: agents are blocked from editing gauntlet/. Thresholds: gauntlet/config/*.
 * =============================================================================================
 *
 *  Install: in build.gradle(.kts) declare the PIT plugin, then apply this script at the END:
 *      plugins { ...; id("info.solidsoft.pitest") version "1.19.0" }
 *      apply(from = "gauntlet/gauntlet.gradle")            // Kotlin DSL, build at the repository root
 *      apply from: '../gauntlet/gauntlet.gradle'           // Groovy DSL, build in a module directory (monorepo)
 *  The script finds gauntlet/ next to itself, so it works from any module; src/ and build/ are the module's.
 *  Several modules in one repository share gauntlet/config/*; a module overrides what differs (basePackage,
 *  acceptance.glue, exclude.classes, the architecture...) in gauntlet/config/<module>/ - a file there
 *  replaces the common one of the same name, gauntlet.properties there is an overlay of the common one.
 *
 *  The script does not change what ./gradlew build does (it only adds jacoco to the test task); every
 *  check runs through the gauntlet tasks below.
 *
 *  Tasks (group "gauntlet"):
 *      gauntletFast     integrity -> checkstyle -> PMD (anti-patterns) -> unit tests -> architecture ->
 *                       acceptance (Cucumber) -> CRAP -> DRY
 *      mutationGate     PIT on the classes in scope, no surviving mutants (+ agent-friendly summary)
 *      gherkinMutation  mutate Examples values one at a time; every mutant must fail a scenario
 *      gauntlet         all of the above
 *
 *  The specification (feature files) is approved by the human in the chat and frozen by the
 *  Claude Code guard hook once committed; there is no lock file to maintain (see gauntlet/README.md).
 *
 *  Scope: -Pgauntlet.scope=changed|all  -Pgauntlet.baseRef=origin/main  (defaults in gauntlet.properties)
 */

import java.nio.file.Files
import java.util.regex.Pattern
import org.gradle.api.tasks.PathSensitivity

// gauntlet/ is wherever this script lives (repository root, or one level above a module's build)
def gauntletDir = buildscript.sourceFile.parentFile
def gauntletFile = { String path -> new File(gauntletDir, path) }
// the module = this build's directory relative to the repository root ('' for a build at the root)
def moduleName = gauntletDir.parentFile.toPath().toAbsolutePath().normalize()
        .relativize(projectDir.toPath().toAbsolutePath().normalize()).toString().replace(File.separator, '/')
// config/<module>/<name> replaces config/<name> when it exists
def configFile = { String name ->
    def own = moduleName ? gauntletFile("config/${moduleName}/${name}") : null
    (own != null && own.exists()) ? own : gauntletFile("config/${name}")
}
def gauntletConfig = new Properties()
gauntletFile('config/gauntlet.properties').withReader('UTF-8') { gauntletConfig.load(it) }
def moduleProperties = moduleName ? gauntletFile("config/${moduleName}/gauntlet.properties") : null
if (moduleProperties != null && moduleProperties.exists()) {
    moduleProperties.withReader('UTF-8') { gauntletConfig.load(it) }   // overlay: the module's keys win
}
def setting = { String key, String fallback -> (gauntletConfig.getProperty(key) ?: fallback).trim() }
def listSetting = { String key, String fallback -> setting(key, fallback).split(',')*.trim().findAll { it } }

def scope = (findProperty('gauntlet.scope') ?: setting('scope', 'changed')).toString()
def baseRef = (findProperty('gauntlet.baseRef') ?: setting('baseRef', 'origin/main')).toString()
def featuresPath = setting('acceptance.features', 'src/acceptanceTest/resources/features')
def featuresDir = file(featuresPath)
def glue = setting('acceptance.glue', '')
def basePackage = setting('basePackage', '')
def excludedClassGlobs = listSetting('exclude.classes', '*Application,*MapperImpl')  // not 'excludedClasses': a local of that name would shadow pitest.excludedClasses
def tools = gauntletFile('tools').absolutePath
def buildDirFile = { String path -> layout.buildDirectory.file(path).get().asFile }

// ------------------------------------------------------------------------------ changed files

def git = { List<String> args ->
    providers.exec {
        commandLine(['git', '-c', 'core.quotePath=false'] + args)
        workingDir = projectDir
        ignoreExitValue = true
    }.standardOutput.asText.get().readLines()*.trim().findAll { it }
}
def mergeBase = { -> scope == 'all' ? null : git(['merge-base', 'HEAD', baseRef]).find() }.memoize()
// Why scope=changed cannot work here (null = fine). Reported by the gauntletScope task, never silently ignored.
def scopeProblem = { ->
    if (scope == 'all') {
        return null
    }
    if (git(['rev-parse', '--is-inside-work-tree']) != ['true']) {
        return 'scope=changed needs a git work tree'
    }
    return mergeBase() ? null : "cannot find the merge base of HEAD and '${baseRef}'"
}.memoize()
// null = whole codebase; otherwise paths relative to the project directory
def changedFiles = {
    if (scope == 'all') {
        return null
    }
    if (scopeProblem()) {
        return []   // gauntletScope fails the build before any scoped check runs
    }
    def files = new LinkedHashSet<String>()
    files.addAll(git(['diff', '--relative', '--name-only', '--diff-filter=ACMR', mergeBase()]))
    files.addAll(git(['ls-files', '--others', '--exclude-standard']))
    return files as List<String>
}.memoize()
def changedMainJava = { -> changedFiles()?.findAll { it.startsWith('src/main/java/') && it.endsWith('.java') } }
def changedFeatures = { -> changedFiles()?.findAll { it.startsWith(featuresPath + '/') && it.endsWith('.feature') } }
def javaTopLevelSource = { String source ->
    def code = new StringBuilder(source.length())
    def state = 'code'
    def depth = 0
    def i = 0
    while (i < source.length()) {
        def c = source.charAt(i)
        def next = i + 1 < source.length() ? source.charAt(i + 1) : '\0'
        if (state == 'lineComment') {
            code.append(c == '\n' ? c : ' ')
            if (c == '\n') state = 'code'
            i++
            continue
        }
        if (state == 'blockComment') {
            if (c == '*' && next == '/') {
                code.append('  ')
                i += 2
                state = 'code'
            } else {
                code.append(c == '\n' ? c : ' ')
                i++
            }
            continue
        }
        if (state == 'textBlock') {
            if (c == '\\' && i + 1 < source.length()) {
                code.append(' ').append(next == '\n' ? '\n' : ' ')
                i += 2
            } else if (c == '"' && next == '"' && i + 2 < source.length() && source.charAt(i + 2) == '"') {
                code.append('   ')
                i += 3
                state = 'code'
            } else {
                code.append(c == '\n' ? c : ' ')
                i++
            }
            continue
        }
        if (state == 'string' || state == 'character') {
            def delimiter = state == 'string' ? '"' : "'"
            if (c == '\\' && i + 1 < source.length()) {
                code.append(' ').append(next == '\n' ? '\n' : ' ')
                i += 2
            } else {
                code.append(c == '\n' ? c : ' ')
                if (c == delimiter) state = 'code'
                i++
            }
            continue
        }
        if (c == '/' && next == '/') {
            code.append('  ')
            i += 2
            state = 'lineComment'
        } else if (c == '/' && next == '*') {
            code.append('  ')
            i += 2
            state = 'blockComment'
        } else if (c == '"' && next == '"' && i + 2 < source.length() && source.charAt(i + 2) == '"') {
            code.append('   ')
            i += 3
            state = 'textBlock'
        } else if (c == '"') {
            code.append(' ')
            i++
            state = 'string'
        } else if (c == "'") {
            code.append(' ')
            i++
            state = 'character'
        } else {
            if (c == '{') depth++
            if (c == '}') depth = Math.max(0, depth - 1)
            code.append(depth == 0 || c == '\n' ? c : ' ')
            i++
        }
    }
    return code.toString()
}
def declaredJavaPackage = { String source ->
    def pattern = Pattern.compile('(?<![\\p{javaJavaIdentifierPart}$])package\\s+([\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}]*(?:\\s*\\.\\s*[\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}]*)*)\\s*;')
    def matcher = pattern.matcher(javaTopLevelSource(source))
    return matcher.find() ? matcher.group(1).replaceAll(/\s+/, '') : ''
}
def topLevelTypeNames = { String source ->
    def names = new LinkedHashSet<String>()
    def type = Pattern.compile('(?<![\\p{javaJavaIdentifierPart}$])(?:class|interface|enum|record)\\s+([\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}]*)')
    def matcher = type.matcher(javaTopLevelSource(source))
    while (matcher.find()) names << matcher.group(1)
    return names
}
def changedClassGlobs = { ->
    changedMainJava()?.collectMany { path ->
        def rel = path - 'src/main/java/'
        def fqcn = rel.replaceAll(/\.java$/, '').replace('/', '.')
        def globs = new LinkedHashSet<String>()
        def src = file(path)
        if (src.isFile()) {
            def source = src.getText('UTF-8')
            def pkg = declaredJavaPackage(source)
            topLevelTypeNames(source).each { simpleName ->
                def name = (pkg ? pkg + '.' : '') + simpleName
                globs << name
                globs << name + '$*'
            }
        } else {
            globs << fqcn
            globs << fqcn + '$*'
        }
        return globs as List
    }
}

// ------------------------------------------------------------------------------ source sets

apply plugin: 'java'
apply plugin: 'jacoco'

def gateJavaHome = setting('gate.java.home', '')
def gateJavaVersion = setting('gate.java.version', '')
def gateJavaLauncher = gateJavaVersion ? javaToolchains.launcherFor {
    languageVersion = JavaLanguageVersion.of(gateJavaVersion)
} : null
def javaBin = gateJavaHome ? "${gateJavaHome}/bin/java" :
        gateJavaLauncher != null ? gateJavaLauncher.get().executablePath.asFile.absolutePath :
                "${System.getProperty('java.home')}/bin/java"
def gateJava = { task ->
    if (task instanceof JavaExec) {
        if (gateJavaHome) {
            task.executable = javaBin
        } else if (gateJavaLauncher != null) {
            task.javaLauncher = gateJavaLauncher
        }
    }
    if (task instanceof Test && (gateJavaHome || gateJavaLauncher != null)) {
        task.executable = javaBin
    }
}

sourceSets {
    acceptanceTest {
        compileClasspath += sourceSets.main.output
        runtimeClasspath += sourceSets.main.output
    }
    archTest {
        java.srcDirs = [gauntletFile('archtest')]
        resources.srcDirs = []
        compileClasspath += sourceSets.main.output
        runtimeClasspath += sourceSets.main.output
    }
}

configurations {
    acceptanceTestImplementation.extendsFrom testImplementation
    acceptanceTestRuntimeOnly.extendsFrom testRuntimeOnly
    archTestImplementation.extendsFrom testImplementation
    archTestRuntimeOnly.extendsFrom testRuntimeOnly
    gauntletCpd
    gauntletCheckstyle
}

def addDefault = { String configuration, List<Object> notations ->
    if (configurations.getByName(configuration).dependencies.isEmpty()) {
        notations.each { dependencies.add(configuration, it) }
    }
}
addDefault('acceptanceTestImplementation', [
        dependencies.platform("io.cucumber:cucumber-bom:${setting('cucumber.version', '7.23.0')}"),
        'io.cucumber:cucumber-java',
        'io.cucumber:cucumber-junit-platform-engine'] +
        (setting('acceptance.spring', 'true').toBoolean() ? ['io.cucumber:cucumber-spring'] : []))
addDefault('archTestImplementation', ["com.tngtech.archunit:archunit:${setting('archunit.version', '1.5.1')}"])
addDefault('gauntletCheckstyle', ["com.puppycrawl.tools:checkstyle:${setting('checkstyle.version', '12.3.1')}"])
addDefault('gauntletCpd', ["net.sourceforge.pmd:pmd-cli:${setting('pmd.version', '7.27.0')}",     // pmdGate and cpdReport
                           "net.sourceforge.pmd:pmd-java:${setting('pmd.version', '7.27.0')}"])

// ------------------------------------------------------------------------------ cheap checks first

tasks.register('gauntletInfo') {
    group = 'gauntlet'
    description = 'Prints which gauntlet files and settings this build uses.'
    def lines = [
            "gauntlet dir : ${gauntletDir}",
            "module       : ${moduleName ?: '(build at the repository root)'}",
            "properties   : config/gauntlet.properties" + ((moduleProperties != null && moduleProperties.exists()) ?
                    " + config/${moduleName}/gauntlet.properties (overlay)" : ''),
            "architecture : ${gauntletDir.toPath().relativize(configFile('architecture.properties').toPath())}",
            "checkstyle   : ${gauntletDir.toPath().relativize(configFile('checkstyle.xml').toPath())}",
            "pmd          : ${gauntletDir.toPath().relativize(configFile('pmd-ruleset.xml').toPath())}",
            "allowlists   : ${gauntletDir.toPath().relativize(configFile('integrity-allowlist.txt').toPath())}, " +
                    "${gauntletDir.toPath().relativize(configFile('crap-allowlist.txt').toPath())}, " +
                    "${gauntletDir.toPath().relativize(configFile('pit-runerror-allowlist.txt').toPath())}",
            "basePackage  : ${basePackage ?: '(not set)'}    glue: ${glue ?: '(not set)'}",
            "cucumber     : ${setting('cucumber.version', '7.23.0')}    scope: ${scope}    baseRef: ${baseRef}",
            "features     : ${featuresPath}",
            "tools        : PIT ${setting('pit.version', '1.22.1')}, ArchUnit ${setting('archunit.version', '1.5.1')}, " +
                    "Checkstyle ${setting('checkstyle.version', '12.3.1')}, PMD ${setting('pmd.version', '7.27.0')}, " +
                    "JaCoCo ${setting('jacoco.version', '0.8.15')}",
            "gate JVM    : version=${gateJavaVersion ?: '(Gradle JVM)'}; home=${gateJavaHome ?: '(from toolchain)'}; " +
                    "executable=${javaBin}"].collect { it.toString() }
    gauntletConfig.stringPropertyNames().findAll { it.startsWith('project.') }.sort().each { key ->
        lines.add("${key} = ${gauntletConfig.getProperty(key)}".toString())
    }
    doLast { lines.each { println it } }
}

tasks.register('gauntletScope') {
    group = 'gauntlet'
    description = 'Prints the scope of the scoped checks; fails when scope=changed cannot tell what changed.'
    def problem = scopeProblem()
    def summary = scope == 'all' ? 'whole codebase' :
            "changed vs ${baseRef} (merge-base ${mergeBase()?.take(10)}): ${changedFiles()?.size() ?: 0} file(s)".toString()
    doLast {
        if (problem) {
            def branch = baseRef.contains('/') ? baseRef.substring(baseRef.indexOf('/') + 1) : baseRef
            throw new GradleException("gauntlet: ${problem}, so the changed files are unknown. Fetch the base branch: " +
                    "git fetch origin +refs/heads/${branch}:refs/remotes/origin/${branch} (a single-branch clone needs the " +
                    "refspec; a shallow clone needs git fetch --unshallow origin first; CI needs full history: " +
                    "GIT_DEPTH=0 / fetch-depth: 0). Or set baseRef in gauntlet/config/gauntlet.properties, or run " +
                    "with -Pgauntlet.scope=all.")
        }
        logger.lifecycle("gauntlet scope: ${summary}")
    }
}

tasks.register('integrityCheck', Exec) {
    group = 'gauntlet'
    description = 'Finds disabled tests, coverage/mutation evasion, inline suppressions and gate tampering.'
    executable javaBin
    args "${tools}/IntegrityCheck.java", '--root', projectDir.absolutePath, '--features', featuresPath,
            '--allowlist', configFile('integrity-allowlist.txt').absolutePath
}

// Checkstyle runs through its CLI on purpose: the Gradle checkstyle plugin would hook into `check`/`build`
// and collide with a project's own Checkstyle setup.
tasks.register('checkstyleGate', JavaExec) {
    group = 'gauntlet'
    description = 'Size and structure rules from gauntlet/config/checkstyle.xml (main sources in scope).'
    dependsOn 'gauntletScope'
    mustRunAfter 'integrityCheck'
    classpath = configurations.gauntletCheckstyle
    mainClass = 'com.puppycrawl.tools.checkstyle.Main'
    systemProperty 'config_loc', configFile('checkstyle.xml').parentFile.absolutePath
    def changed = changedMainJava()
    def targets = changed == null ? [file('src/main/java').absolutePath] : changed.collect { file(it).absolutePath }
    def report = buildDirFile('reports/checkstyle/gauntlet.xml')
    args(['-c', configFile('checkstyle.xml').absolutePath, '-f', 'xml', '-o', report.absolutePath] + targets)
    // The CLI exits with the violation count, which the OS truncates to 8 bits (256 violations = exit 0),
    // so the verdict comes from the XML report instead.
    ignoreExitValue = true
    onlyIf { !targets.isEmpty() && new File(targets[0]).exists() }
    doFirst {
        report.delete()
        report.parentFile.mkdirs()
    }
    doLast {
        if (!report.exists()) {
            throw new GradleException("Checkstyle did not produce ${report} - see the output above")
        }
        def violations = []
        new groovy.xml.XmlSlurper().parse(report).file.each { f ->
            f.error.each { e ->
                def check = e.@source.toString().tokenize('.').last().replaceAll(/Check$/, '')
                violations << "[ERROR] ${f.@name}:${e.@line}: ${e.@message} [${check}]"
            }
        }
        violations.each { println it }
        if (violations) {
            throw new GradleException("Checkstyle: ${violations.size()} violation(s) of gauntlet/config/checkstyle.xml")
        }
        println 'Checkstyle: OK'
    }
}

// PMD through the same CLI as CPD, for the same reason as Checkstyle. It needs the compiled classes and their
// dependencies (--aux-classpath) so that rules about types, overrides and resources can resolve symbols.
// Suppressed violations (NOPMD, @SuppressWarnings("PMD...")) count as violations: rules are switched off
// only by the human, in gauntlet/config/pmd-ruleset.xml. Suppressions declared there (rule properties
// violationSuppressXPath and violationSuppressRegex, report types "xpath" and "regex") are that human decision and
// do not count.
tasks.register('pmdGate', JavaExec) {
    group = 'gauntlet'
    description = 'Anti-pattern rules from gauntlet/config/pmd-ruleset.xml (main sources in scope).'
    dependsOn 'gauntletScope', 'classes'
    mustRunAfter 'checkstyleGate'
    classpath = configurations.gauntletCpd
    mainClass = 'net.sourceforge.pmd.cli.PmdCli'
    def changed = changedMainJava()
    def targets = changed == null ? [file('src/main/java').absolutePath] : changed.collect { file(it).absolutePath }
    def report = buildDirFile('reports/pmd/gauntlet.xml')
    args(['check', '--rulesets', configFile('pmd-ruleset.xml').absolutePath,
          '--use-version', "java-${java.targetCompatibility.majorVersion}".toString(),
          '--format', 'xml', '--report-file', report.absolutePath, '--relativize-paths-with', projectDir.absolutePath,
          '--no-fail-on-violation', '--no-cache', '--no-progress', '--show-suppressed'] + targets.collectMany { ['--dir', it] })
    ignoreExitValue = true   // the verdict comes from the XML report, like checkstyleGate
    onlyIf { !targets.isEmpty() && new File(targets[0]).exists() }
    doFirst {
        // the JDK's own classes (jrt-fs.jar of the JDK running PMD) explicitly, or PMD warns about guessing them
        def jdk = javaLauncher.get().metadata.installationPath.asFile
        args '--aux-classpath', (sourceSets.main.compileClasspath + sourceSets.main.output.classesDirs +
                files(new File(jdk, 'lib/jrt-fs.jar'))).asPath
        report.delete()
        report.parentFile.mkdirs()
    }
    doLast {
        if (!report.exists()) {
            throw new GradleException("PMD did not produce ${report} - see the output above")
        }
        def root = new groovy.xml.XmlSlurper().parse(report)
        def violations = []
        root.file.each { f ->
            f.violation.each { v -> violations << "[ERROR] ${f.@name}:${v.@beginline}: ${v.text().trim()} [${v.@rule}]" }
        }
        def rulesetSuppressions = ['xpath', 'regex']
        root.suppressedviolation.findAll { !(it.@suppressiontype.text() in rulesetSuppressions) }.each { s ->
            violations << "[ERROR] ${s.@filename}: suppressed (${s.@suppressiontype}) - ${s.@msg} [suppression]"
        }
        root.error.each { e -> violations << "[ERROR] ${e.@filename}: PMD could not analyse the file - ${e.@msg} [error]" }
        root.configerror.each { e -> violations << "[ERROR] rule ${e.@rule}: ${e.@msg} [ruleset]" }
        violations.each { println it }
        if (violations) {
            throw new GradleException("PMD: ${violations.size()} violation(s) of gauntlet/config/pmd-ruleset.xml")
        }
        println 'PMD: OK'
    }
}

// ------------------------------------------------------------------------------ tests

tasks.named('test') {
    mustRunAfter 'checkstyleGate', 'pmdGate'
}

tasks.register('archTest', Test) {
    group = 'gauntlet'
    description = 'Enforces gauntlet/config/architecture.properties with ArchUnit.'
    testClassesDirs = sourceSets.archTest.output.classesDirs
    classpath = sourceSets.archTest.runtimeClasspath
    useJUnitPlatform()
    systemProperty 'gauntlet.architecture', configFile('architecture.properties').absolutePath
    testLogging { events 'failed'; exceptionFormat = 'full'; showStandardStreams = true }
    jacoco { enabled = false }
    mustRunAfter 'test'
}

def configureCucumber = { Test task, File features ->
    task.testClassesDirs = sourceSets.acceptanceTest.output.classesDirs
    task.classpath = sourceSets.acceptanceTest.runtimeClasspath
    task.useJUnitPlatform { includeEngines 'cucumber' }
    task.systemProperty 'cucumber.features', features.absolutePath
    task.systemProperty 'cucumber.publish.quiet', 'true'
    if (glue) {
        task.systemProperty 'cucumber.glue', glue
    }
}
def hasFeatures = { File dir -> dir.exists() && Files.walk(dir.toPath()).withCloseable { s -> s.anyMatch { it.toString().endsWith('.feature') } } }

tasks.register('acceptanceTest', Test) {
    group = 'gauntlet'
    description = 'Runs the Gherkin acceptance tests (Cucumber) from ' + featuresPath
    configureCucumber(it, featuresDir)
    // the features are passed as a system property, which Gradle does not track by content: without this
    // input a change to only the feature files leaves acceptanceTest UP-TO-DATE and the new spec never runs.
    inputs.dir(featuresDir).optional().withPathSensitivity(PathSensitivity.RELATIVE)
    testLogging { events 'failed'; exceptionFormat = 'full' }
    onlyIf { hasFeatures(featuresDir) }
    mustRunAfter 'archTest'
    finalizedBy 'acceptanceCheck'
    // acceptanceCheck must judge this run only, never results a previous run left behind
    def results = reports.junitXml.outputLocation.get().asFile
    doFirst { results.deleteDir(); results.mkdirs() }
}

tasks.register('acceptanceCheck', Exec) {
    group = 'gauntlet'
    description = 'Fails when scenarios were skipped (aborted by an assumption or a skipped step) - Gradle would pass them - ' +
            'or when feature files exist but no scenario ran.'
    def results = buildDirFile('test-results/acceptanceTest')
    executable javaBin
    args "${tools}/GherkinMutator.java", 'no-skipped', '--results', results.absolutePath,
            '--features', featuresDir.absolutePath
}

// ------------------------------------------------------------------------------ CRAP and DRY

jacoco {
    toolVersion = setting('jacoco.version', '0.8.15')
}
def jacocoExcludes = excludedClassGlobs.collectMany { ["**/${it}.class", "**/${it}\$*.class"] }
tasks.named('jacocoTestReport', JacocoReport) {
    dependsOn 'test'
    reports {
        xml.required = true
        html.required = true
    }
    classDirectories.setFrom(files(sourceSets.main.output.classesDirs.files.collect { dir ->
        fileTree(dir) { exclude jacocoExcludes }
    }))
}

tasks.register('crapGate', Exec) {
    group = 'gauntlet'
    description = 'CRAP = CC^2 * (1 - coverage)^3 + CC per method; fails above crap.threshold.'
    dependsOn 'jacocoTestReport', 'gauntletScope'
    mustRunAfter 'acceptanceTest'
    executable javaBin
    args "${tools}/CrapGate.java", '--report', buildDirFile('reports/jacoco/test/jacocoTestReport.xml').absolutePath,
            '--threshold', setting('crap.threshold', '8'), '--allowlist', configFile('crap-allowlist.txt').absolutePath,
            '--exclude', excludedClassGlobs.join(',')
    def only = changedMainJava()
    if (only != null) {
        args '--only', only.join(',')
    }
}

tasks.register('cpdReport', JavaExec) {
    group = 'gauntlet'
    description = 'Runs PMD CPD (copy/paste detector) over src/main/java.'
    def report = buildDirFile('reports/cpd/cpd.xml')
    classpath = configurations.gauntletCpd
    mainClass = 'net.sourceforge.pmd.cli.PmdCli'
    args 'cpd', '--language', 'java', '--dir', file('src/main/java').absolutePath,
            '--minimum-tokens', setting('dry.minimumTokens', '60'), '--format', 'xml',
            '--report-file', report.absolutePath, '--no-fail-on-violation', '--ignore-annotations'
    if (setting('dry.ignoreIdentifiers', 'true').toBoolean()) {
        args '--ignore-identifiers'
    }
    if (setting('dry.ignoreLiterals', 'true').toBoolean()) {
        args '--ignore-literals'
    }
    // paths (files or directories) relative to the module, left out of the duplicate search (CLI --exclude, CPD 7.0+)
    listSetting('dry.exclude', '').each { args '--exclude', file(it).absolutePath }
    inputs.dir('src/main/java').optional()
    outputs.file(report)
    onlyIf { file('src/main/java').exists() }
    doFirst { report.parentFile.mkdirs() }
}

tasks.register('dryGate', Exec) {
    group = 'gauntlet'
    description = 'Fails on duplicated code (in scope: duplications touching a changed file).'
    dependsOn 'cpdReport', 'gauntletScope'
    mustRunAfter 'crapGate'
    executable javaBin
    args "${tools}/DryGate.java", '--report', buildDirFile('reports/cpd/cpd.xml').absolutePath,
            '--project-dir', projectDir.absolutePath, '--max', setting('dry.maxDuplications', '0')
    def only = changedMainJava()
    if (only != null) {
        args '--only', only.join(',')
    }
}

// ------------------------------------------------------------------------------ mutation testing

def pit = [applied: false]
plugins.withId('info.solidsoft.pitest') {
    pit.applied = true
    pitest {
        pitestVersion = setting('pit.version', '1.22.1')
        junit5PluginVersion = setting('pit.junit5PluginVersion', '1.2.3')
        // The plugin would add its own org.junit.platform:junit-platform-launcher to the test runtime classpath; when
        // the JUnit version is managed by a BOM (Spring Boot) rather than declared literally it falls back to a
        // hard-coded 1.x launcher, which cannot drive a JUnit 6 engine ("OutputDirectoryCreator not available") and
        // breaks ./gradlew test. The project declares the launcher itself (testRuntimeOnly), BOM-aligned.
        addJUnitPlatformLauncher = false
        threads = setting('pit.threads', '4').toInteger()
        mutators = listSetting('pit.mutators', 'DEFAULTS') as Set
        outputFormats = ['XML', 'HTML'] as Set
        timestampedReports = false
        enableDefaultIncrementalAnalysis = true
        excludedGroups = listSetting('pit.excludedGroups', 'no-mutate') as Set
        // nested classes too, as JaCoCo (jacocoExcludes) and CrapGate (outer class name) already do
        excludedClasses = excludedClassGlobs.collectMany { [it, it + '$*'] } as Set
        // Uncle Bob's rule: every COVERED mutant is killed (PIT test strength). maxSurviving would also count
        // uncovered mutants; uncovered code is policed by coverageThreshold (line coverage of mutated classes).
        testStrengthThreshold = setting('pit.testStrengthThreshold', '100').toInteger()
        coverageThreshold = setting('pit.coverageThreshold', '0').toInteger()
        failWhenNoMutations = false
        if (basePackage) {
            targetClasses = ["${basePackage}.*".toString()] as Set
            // must be explicit: by default the plugin uses targetClasses as targetTests, and with a changed-class
            // scope that would exclude FooTest when mutating Foo - every mutant would look uncovered
            targetTests = ["${basePackage}.*".toString()] as Set
        }
    }
    tasks.named('pitest') {
        group = 'gauntlet'
        dependsOn 'gauntletScope'
        mustRunAfter 'crapGate', 'dryGate', 'acceptanceTest'
        finalizedBy 'pitSummary'
        def staleReport = buildDirFile('reports/pitest/mutations.xml')
        def pkg = basePackage
        doFirst {
            staleReport.delete()
            if (!pkg) {
                throw new GradleException('gauntlet: set basePackage in gauntlet/config/gauntlet.properties')
            }
        }
        def targets = changedClassGlobs()
        if (targets != null) {
            if (targets.isEmpty()) {
                onlyIf { false }
                logger.lifecycle('gauntlet: no changed main classes - mutation testing skipped')
            } else {
                targetClasses.set(targets as Set)
            }
        }
    }
}

tasks.register('pitSummary', Exec) {
    group = 'gauntlet'
    description = 'Lists surviving, uncovered and unverified (RUN_ERROR) mutants and oversized files from the PIT ' +
            'report; fails on a RUN_ERROR mutant outside config/pit-runerror-allowlist.txt.'
    def nothingToMutate = changedClassGlobs()?.isEmpty()
    onlyIf { !nothingToMutate }
    executable javaBin
    args "${tools}/PitSummary.java", '--report', buildDirFile('reports/pitest/mutations.xml').absolutePath,
            '--max-per-file', setting('pit.maxMutationsPerFile', '100'),
            '--allowlist', configFile('pit-runerror-allowlist.txt').absolutePath
}

tasks.register('mutationGate') {
    group = 'gauntlet'
    description = 'Mutation testing with PIT: every covered mutant in scope must be killed, and a RUN_ERROR mutant ' +
            '(PIT counts it as detected, the tests never ran) only passes through config/pit-runerror-allowlist.txt.'
    if (pit.applied) {
        dependsOn 'pitest', 'pitSummary'
    }
    def applied = pit.applied
    doLast {
        if (!applied) {
            throw new GradleException("mutationGate needs the PIT plugin: add id(\"info.solidsoft.pitest\") version \"1.19.0\" to plugins {}")
        }
    }
}

// ------------------------------------------------------------------------------ Gherkin mutation

def mutantsDir = buildDirFile('gherkin-mutation/mutants')
def mutantResults = buildDirFile('gherkin-mutation/results')

tasks.register('gherkinMutants', Exec) {
    group = 'gauntlet'
    description = 'Generates one feature file per mutated Examples value.'
    dependsOn 'acceptanceTest', 'gauntletScope'
    if (pit.applied) {
        mustRunAfter 'pitest'
    }
    executable javaBin
    args "${tools}/GherkinMutator.java", 'generate', '--features', featuresPath, '--out', mutantsDir.absolutePath
    def only = changedFeatures()
    if (only != null) {
        args '--only', only.join(',')
    }
}

tasks.register('gherkinMutantsRun', Test) {
    group = 'gauntlet'
    description = 'Runs the generated mutant scenarios; failures are the expected outcome.'
    dependsOn 'gherkinMutants'
    configureCucumber(it, mutantsDir)
    systemProperty 'cucumber.junit-platform.naming-strategy', 'long'
    ignoreFailures = true
    reports.junitXml.outputLocation.set(mutantResults)
    reports.html.required = false
    outputs.upToDateWhen { false }
    jacoco { enabled = false }
    onlyIf { hasFeatures(mutantsDir) }
    // Gradle 8.14 lists the report directory without creating it: recreate it after the wipe
    doFirst { mutantResults.deleteDir(); mutantResults.mkdirs() }
}

tasks.register('gherkinMutation', Exec) {
    group = 'gauntlet'
    description = 'Gherkin acceptance mutation: every mutated Examples value must make a scenario fail.'
    dependsOn 'gherkinMutantsRun'
    executable javaBin
    args "${tools}/GherkinMutator.java", 'verdict', '--mutants', mutantsDir.absolutePath, '--results', mutantResults.absolutePath
}

// ------------------------------------------------------------------------------ aggregates

tasks.register('gauntletFast') {
    group = 'gauntlet'
    description = 'Integrity, checkstyle, PMD, unit, architecture and acceptance tests, CRAP, DRY.'
    dependsOn 'gauntletScope', 'integrityCheck', 'checkstyleGate', 'pmdGate', 'test', 'archTest', 'acceptanceTest',
            'acceptanceCheck', 'crapGate', 'dryGate'
}

tasks.register('gauntlet') {
    group = 'gauntlet'
    description = 'The whole gauntlet: gauntletFast + mutationGate + gherkinMutation.'
    dependsOn 'gauntletFast', 'mutationGate', 'gherkinMutation'
}

// ------------------------------------------------------------------------------ one run per build directory

// Two Gradle runs in the same build/ (the agent's own run in the background, a Stop hook, a subagent's run)
// overwrite each other's classes, test results and reports: a gate can then judge a half-written or foreign
// result. Every task of this build therefore holds an exclusive OS file lock on .gradle/gauntlet-build.lock
// (outside build/, so clean cannot delete it from under a holder) from its first action until the build ends;
// a second run waits for it. Gradle closes the service after the last task that uses it (Gradle 8.14 user guide,
// "Using Shared Build Services"), which releases the lock.
abstract class GauntletBuildLock implements BuildService<GauntletBuildLock.Params>, AutoCloseable {
    interface Params extends BuildServiceParameters {
        Property<String> getLockPath()
        Property<Integer> getWaitSeconds()
    }

    private java.nio.channels.FileChannel channel
    private java.nio.channels.FileLock lock

    synchronized void hold(String taskPath) {
        if (lock != null) {
            return
        }
        def file = new File(parameters.lockPath.get())
        file.parentFile.mkdirs()
        channel = java.nio.channels.FileChannel.open(file.toPath(), java.nio.file.StandardOpenOption.CREATE,
                java.nio.file.StandardOpenOption.READ, java.nio.file.StandardOpenOption.WRITE)
        long deadline = System.currentTimeMillis() + parameters.waitSeconds.get() * 1000L
        boolean told = false
        while ((lock = tryLock()) == null) {
            if (System.currentTimeMillis() > deadline) {
                channel.close()
                channel = null
                throw new GradleException("[gauntlet] another Gradle run (${holder(file)}) has been using this build " +
                        "directory for over ${parameters.waitSeconds.get()} s - wait for it to finish, then run again.")
            }
            if (!told) {
                println "[gauntlet] ${taskPath}: another Gradle run (${holder(file)}) is using this build directory - waiting for it"
                told = true
            }
            Thread.sleep(2000)
        }
        channel.truncate(0)
        channel.write(java.nio.ByteBuffer.wrap("pid ${ProcessHandle.current().pid()}".getBytes('UTF-8')), 0)
        channel.force(false)
    }

    // a lock another build of the same JVM (daemon) still holds shows up as an exception, not as null
    private java.nio.channels.FileLock tryLock() {
        try {
            return channel.tryLock()
        } catch (java.nio.channels.OverlappingFileLockException ignored) {
            return null
        }
    }

    private static String holder(File file) {
        try {
            return file.getText('UTF-8').trim() ?: 'pid unknown'
        } catch (IOException ignored) {
            return 'pid unknown'
        }
    }

    @Override
    void close() {
        lock?.release()
        channel?.close()
    }
}

def buildLock = gradle.sharedServices.registerIfAbsent('gauntletBuildLock-' + projectDir.absolutePath.md5(), GauntletBuildLock) {
    parameters.lockPath = new File(projectDir, '.gradle/gauntlet-build.lock').absolutePath
    parameters.waitSeconds = (findProperty('gauntlet.lockWaitSeconds') ?: '1500').toString().toInteger()
}
tasks.configureEach { Task task ->
    task.usesService(buildLock)
    def path = task.path
    task.doFirst { buildLock.get().hold(path) }
}

// ------------------------------------------------------------------------------ gate JVM

['checkstyleGate', 'pmdGate', 'cpdReport', 'acceptanceTest', 'archTest', 'gherkinMutantsRun'].each {
    tasks.named(it) { gateJava(it) }
}
plugins.withId('info.solidsoft.pitest') {
    tasks.named('pitest') { gateJava(it) }
}

// ------------------------------------------------------------------------------ configuration cache

// A project may enable the configuration cache (org.gradle.configuration-cache=true in gradle.properties).
// Several gauntlet tasks read the project while they run (file() in onlyIf, sourceSets and javaLauncher in
// doFirst), which the cache forbids. They opt out explicitly (Task.notCompatibleWithConfigurationCache): a build
// that runs any of them discards its cache entry instead of failing; the project's own builds keep the cache.
def notCacheable = { Task task -> task.notCompatibleWithConfigurationCache('gauntlet tasks read the project at execution time') }
['gauntletInfo', 'gauntletScope', 'integrityCheck', 'checkstyleGate', 'pmdGate', 'archTest', 'acceptanceTest',
 'acceptanceCheck', 'crapGate', 'cpdReport', 'dryGate', 'pitSummary', 'mutationGate', 'gherkinMutants',
 'gherkinMutantsRun', 'gherkinMutation', 'gauntletFast', 'gauntlet'].each { tasks.named(it, notCacheable) }
plugins.withId('info.solidsoft.pitest') { tasks.named('pitest', notCacheable) }

===== END FILE gauntlet/gauntlet.gradle =====

===== BEGIN FILE gauntlet/hooks/guard.py =====
#!/usr/bin/env python3
"""PreToolUse guard for the gauntlet (Claude Code hook).

Keeps agents from changing their own constraints:
  1. nobody edits the gauntlet itself (gauntlet/, .claude/, CLAUDE.md, the CI workflow) or the user-level
     Claude Code settings (~/.claude/), which could switch the hooks off;
  2. only the `specifier` subagent writes the Gherkin specification, and once the specification is
     committed on the branch (= approved by the human in the chat) it is frozen for every agent;
  3. role scopes: specifier -> specs only, hardener -> test code only, reviewer -> read-only;
  4. human-only actions are refused: merging the PR, rewriting or re-pointing the branch (--amend,
     rebase, force push, reset/checkout -B/branch -f to another revision), pushing to the base branch,
     --no-verify, switching the hooks off.

Shell commands are checked heuristically: every path-like token of a command that writes to the working
tree is resolved (following `cd` and `git -C`, expanding globs) and compared with the protected paths.
A determined agent could still find a way; the integrity check, CI and the human's PR review are the
backstop. The hook fails open on malformed input so a broken hook never bricks a session.

Maintenance without the guard (humans only): set GAUNTLET_GUARD=off in the environment the session
starts with - locally `GAUNTLET_GUARD=off claude`, in the cloud an environment variable of a
separate "admin" cloud environment (see gauntlet/README.md).
"""
import glob
import json
import os
import re
import shlex
import subprocess
import sys

HUMAN_OWNED = ("gauntlet/", ".claude/", "CLAUDE.md", ".github/workflows/gauntlet.yml",
               ".github/CODEOWNERS", ".gitlab/CODEOWNERS", "CODEOWNERS", ".git/")
PROPERTIES = "gauntlet/config/gauntlet.properties"
DEFAULT_FEATURES = "src/acceptanceTest/resources/features"
DEFAULT_BASE = "origin/main"
TEST_CODE = ("src/test/", "src/acceptanceTest/java/")
GIT_VALUE_OPTIONS = {"-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author", "--date", "--template",
                     "--reuse-message", "--reedit-message", "--fixup", "--squash", "--trailer"}
HOOK_SWITCH = re.compile(r"(?:^|[\s;&|(])(?:(?:export|unset)\s+GAUNTLET_(?:GUARD|STOP_HOOK)\b|GAUNTLET_(?:GUARD|STOP_HOOK)=)")
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
MUTATING_COMMANDS = {"mv", "cp", "rm", "rmdir", "truncate", "tee", "ln", "chmod", "chown", "touch", "dd",
                     "install", "patch", "unzip", "tar", "rsync", "vi", "vim", "nvim", "nano", "emacs", "ed", "ex",
                     "mkdir", "shred"}
# git subcommands that rewrite files in the working tree (checked against protected paths) ...
GIT_WORKTREE_WRITING = {"checkout", "switch", "restore", "rm", "mv", "apply", "stash", "reset", "clean", "am",
                        "cherry-pick", "revert", "merge", "rebase", "pull"}
# ... and the ones that only change git state (forbidden to the read-only reviewer, fine for others)
GIT_STATE_CHANGING = GIT_WORKTREE_WRITING | {"commit", "add", "push", "tag", "branch", "update-ref", "replace",
                                             "filter-branch", "filter-repo", "notes", "worktree", "submodule"}
GIT_READ_ONLY_FORMS = {"branch": ("--show-current", "--list", "-l", "-a", "-r", "-v", "-vv", "--contains", "--merged",
                                  "--no-merged", "--points-at", "--format", "--sort"),
                       "stash": ("list", "show"), "tag": ("--list", "-l", "-n", "--contains", "--points-at"),
                       "worktree": ("list",), "notes": ("list", "show"), "submodule": ("status",)}
HISTORY_REWRITING = {"rebase", "filter-branch", "filter-repo", "update-ref", "replace", "revert"}
INTERPRETERS = {"python", "python3", "node", "ruby", "bash", "sh", "zsh"}   # with -c / -e inline code
WRAPPERS = {"sudo", "command", "exec", "nohup", "time", "env", "timeout", "nice"}
# options of wrappers that take a separate value: skipped together with the value so the wrapped command surfaces
WRAPPER_VALUE_OPTS = {
    "sudo": {"-u", "-g", "-p", "-r", "-t", "-C", "-U", "-h", "--user", "--group", "--prompt", "--role",
             "--type", "--close-from", "--other-user", "--host"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "exec": {"-a", "--argv0"},
    "time": {"-o", "-f", "--output", "--format"},
    "command": set(), "nohup": set(),
}
SHELL_KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{"}   # `then rm x` runs rm
GRADLE = {"gradlew", "gradle"}
GRADLE_PATH_OPTIONS = {"-p", "--project-dir", "-g", "--gradle-user-home", "--project-cache-dir", "-b", "--build-file",
                       "-c", "--settings-file", "-I", "--init-script", "--include-build"}
PERL_WRITES = re.compile(r"\b(open|unlink|rename|system|exec|qx|mkdir|rmdir|truncate|chmod|chown|symlink|link|"
                         r"utime|syswrite|sysopen)\b|`")
REDIRECT = re.compile(r"(?<!>)>>?\|?\s*([^\s;&|<>()]+)")
GLOB_CHARS = re.compile(r"[*?\[]")


def main():
    if os.environ.get("GAUNTLET_GUARD", "").lower() == "off":
        return 0
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    agent = event.get("agent_type") or "main"
    tool = event.get("tool_name", "")
    params = event.get("tool_input") or {}
    ctx = Context(project)
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = params.get("file_path") or params.get("notebook_path") or ""
        reason = user_config_violation(path) or path_violation(agent, relative(path, project), ctx)
    elif tool == "Bash":
        reason = command_violation(agent, params.get("command", ""), ctx, event.get("cwd") or project)
    else:
        reason = None
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "[gauntlet guard] " + reason}}))
    return 0


class Context:
    """Where the specification lives, which branch is the base, and whether the spec is frozen."""

    def __init__(self, project):
        self.project = project
        props = read_properties(os.path.join(project, PROPERTIES))
        # module = the Gradle build directories inside a monorepo, comma-separated ("" = the repository root)
        self.modules = [m.strip().strip("/") for m in props.get("module", "").split(",") if m.strip()]
        prefixes = [m + "/" for m in self.modules] or [""]
        features_rel = props.get("acceptance.features", DEFAULT_FEATURES).strip("/") + "/"
        self.features_dirs = tuple(pfx + features_rel for pfx in prefixes)
        self.test_code = tuple(pfx + p for pfx in prefixes for p in TEST_CODE)
        self.src_main = [pfx + "src/main" for pfx in prefixes]
        self.build_dirs = tuple(pfx + d for pfx in prefixes for d in ("build/", ".gradle/")) + ("build/", ".gradle/")
        self.base_ref = props.get("baseRef", DEFAULT_BASE)
        self.base_branch = self.base_ref.split("/", 1)[1] if "/" in self.base_ref else self.base_ref
        self.approval = props.get("spec.approval", "chat").lower()
        self._frozen = None

    @property
    def frozen(self):
        """True once the branch holds a commit that touches the feature files and they differ from the
        base branch: the human approved the specification in the chat and the agent committed it. From
        then on only the human changes it. Once the base branch has the same feature files (the PR was
        merged) the branch is free again. Fails open (not frozen) when the base branch cannot be found."""
        if self._frozen is None:
            if self.approval == "pr":
                self._frozen = False    # spec.approval=pr: the human reads the spec in the PR, no freeze
            elif git_code(self.project, "symbolic-ref", "-q", "HEAD") != 0:
                self._frozen = True     # detached HEAD: not the task's branch, nothing may be specified here
            else:
                specs = [d.rstrip("/") for d in self.features_dirs]   # one task per branch: any module's spec freezes all
                count = git(self.project, "rev-list", "--count", f"{self.base_ref}..HEAD", "--", *specs)
                differs = git_code(self.project, "diff", "--quiet", self.base_ref, "HEAD", "--", *specs) == 1
                self._frozen = count.isdigit() and int(count) > 0 and differs
        return self._frozen

    def role_scope(self, agent):
        return {"specifier": self.features_dirs, "hardener": self.test_code, "reviewer": ()}.get(agent)

    def protected(self, agent):
        paths = [p.rstrip("/") for p in HUMAN_OWNED]
        if agent != "specifier" or self.frozen:
            paths += [d.rstrip("/") for d in self.features_dirs]
        if agent == "hardener":
            paths += self.src_main
        return paths

    def is_spec(self, path):
        return path in [d.rstrip("/") for d in self.features_dirs]


# ----------------------------------------------------------------------------- paths

def relative(path, project, cwd=None):
    if not path:
        return None
    base = cwd or project
    absolute = os.path.realpath(path if os.path.isabs(path) else os.path.join(base, path))
    rel = os.path.relpath(absolute, os.path.realpath(project)).replace(os.sep, "/")
    return None if rel.startswith("..") else rel


def is_under(rel, prefixes):
    r = rel.lower()
    return any(r == p.rstrip("/").lower() or r.startswith((p if p.endswith("/") else p + "/").lower()) for p in prefixes)


def contains(rel, prefixes):
    """The path is a parent of a protected path (rm -rf src takes the features with it)."""
    if rel == ".":
        return True
    r = rel.lower()
    return any(p.rstrip("/").lower().startswith(r + "/") for p in prefixes)


def user_config_violation(path):
    if not path:
        return None
    home_claude = os.path.realpath(os.path.expanduser("~/.claude"))
    absolute = os.path.realpath(os.path.expanduser(path)) if os.path.isabs(os.path.expanduser(path)) else None
    if absolute and (absolute == home_claude or absolute.startswith(home_claude + os.sep)):
        return "~/.claude is the user's Claude Code configuration (it could switch the hooks off). Do not touch it."
    return None


def path_violation(agent, rel, ctx):
    if rel is None:
        return None
    if is_under(rel, HUMAN_OWNED):
        return (f"{rel} is part of the gauntlet and is human-owned. Do not change the checks; if one "
                f"looks wrong, stop and explain it to the human.")
    scope = ctx.role_scope(agent)
    if scope is not None:
        if not scope:
            return f"The {agent} is read-only. Report findings instead of editing files."
        if not is_under(rel, scope):
            return f"The {agent} may only write under {', '.join(scope)} (tried {rel})."
        if agent == "specifier" and ctx.frozen:
            return frozen_reason(rel)
        return None
    if is_under(rel, ctx.features_dirs):
        if ctx.frozen:
            return frozen_reason(rel)
        return (f"{rel} is the specification. Only the specifier subagent writes it, and only the human "
                f"approves it (in the chat). Make the code satisfy the spec; if the spec looks wrong, stop and ask.")
    return None


def frozen_reason(rel):
    return (f"{rel} is the approved specification: it is already committed on this branch, so it is frozen. "
            f"Make the code satisfy it. If it is wrong or impossible, stop and tell the human - only the human "
            f"changes an approved spec (on GitHub, or in a session with GAUNTLET_GUARD=off).")


# ----------------------------------------------------------------------------- shell

def command_violation(agent, command, ctx, cwd=None):
    reason = human_only(command, ctx, cwd)
    if reason:
        return reason
    scope = ctx.role_scope(agent)
    read_only = scope is not None and not scope
    protected = ctx.protected(agent)
    command = strip_heredocs(command)       # a heredoc body is data, not commands
    neutral = QUOTED.sub(lambda m: re.sub(r"[>;&|()]", "_", m.group(0)), command)  # '>' in quotes is text
    cwd = cwd or ctx.project
    stack = []                              # subshell cwd scopes: a cd inside ( ... ) must not leak to the parent
    for segment in segments_scoped(neutral):
        if segment == "(":
            stack.append(cwd)
            continue
        if segment == ")":
            if stack:
                cwd = stack.pop()
            continue
        words = words_of(segment)
        cwd = follow_cd(words, cwd, ctx.project)
        for target in REDIRECT.findall(segment):
            reason = write_violation(agent, target, cwd, ctx, protected, read_only, scope, "writing " + target)
            if reason:
                return reason
        if read_only and changes_state(words, segment):
            return f"The {agent} is read-only: no file or git state changes. Report findings instead."
        if not writes_worktree(words, segment):
            continue
        tokens = [] if inline_code(words) else path_tokens(words, cwd, ctx.project)
        for token in tokens:
            reason = write_violation(agent, token, cwd, ctx, protected, read_only, scope, "this command")
            if reason:
                return reason
        # paths the tokens cannot resolve (`python -c ...`, $VAR, `...`, xargs, no path at all): match the text -
        # the whole command for inline code, otherwise outside quotes (a commit or stash message is not a path)
        if not tokens or unresolvable(segment, command):
            text = command if inline_code(words) else without_gradle_tasks(QUOTED.sub("''", command))
            hit = next((p for p in protected if mentions(text, p)), None)
            if hit:
                return protected_reason(agent, hit, ctx)
    return None


def strip_heredocs(command):
    """Drop heredoc bodies (`<<EOF` ... `EOF`): they are text, and `->` or `rm` inside them are not commands."""
    lines = command.split("\n")
    out, delimiters = [], []
    for line in lines:
        if delimiters:
            if line.strip() == delimiters[0]:
                delimiters.pop(0)
            continue
        out.append(line)
        delimiters += [m.group(2) for m in re.finditer(r"<<-?\s*(['\"]?)(\w+)\1", line)]
    return "\n".join(out)


def unresolvable(segment, command):
    return "$" in command or "`" in command or re.search(r"(^|[\s|;&])xargs\s", segment) is not None


def expand(token, cwd, project):
    """The few variables whose value the hook knows; anything else stays literal and triggers text matching."""
    token = token.strip("'\"")
    for var in ("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR"):
        token = token.replace(var, project)
    for var in ("${PWD}", "$PWD"):
        token = token.replace(var, cwd)
    return os.path.expanduser(token)


def write_violation(agent, target, cwd, ctx, protected, read_only, scope, what):
    target = expand(target, cwd, ctx.project)
    reason = user_config_violation(target)
    if reason:
        return reason
    rel = relative(target, ctx.project, cwd)
    if rel is None:
        return None
    if read_only:
        return f"The {agent} is read-only. Report findings instead of {what}."
    if is_under(rel, ctx.build_dirs):
        return None                     # Gradle outputs: any role may clean or write them
    hit = next((p for p in protected if is_under(rel, (p,)) or contains(rel, (p,))), None)
    if hit:
        return protected_reason(agent, hit, ctx)
    if scope and not is_under(rel, scope) and rel != ".":
        return f"The {agent} may only change files under {', '.join(scope)} ({what} touches {rel})."
    return None


def protected_reason(agent, hit, ctx):
    if ctx.is_spec(hit) and ctx.frozen:
        return frozen_reason(hit)
    return (f"This command could modify {hit}, which the {agent} agent must not change. "
            f"Human-owned files and the specification change only through the human.")


def human_only(command, ctx, cwd=None):
    if cwd is None:
        cwd = ctx.project
    if HOOK_SWITCH.search(QUOTED.sub("''", command)):
        return "Switching the gauntlet hooks off is reserved for the human."
    stack = []                              # subshell cwd scopes: a cd inside ( ... ) must not leak to the parent
    for segment in split_shell(command):
        if segment == "(":
            stack.append(cwd)
            continue
        if segment == ")":
            if stack:
                cwd = stack.pop()
            continue
        words = words_of(segment)
        cwd = follow_cd(words, cwd, ctx.project)   # `cd worktree && git push`: judge the branch of that worktree
        if len(words) < 2:
            continue
        cmd, args = os.path.basename(words[0]), words[1:]
        if cmd == "git":
            reason = git_human_only(args, ctx, cwd)
            if reason:
                return reason
        elif cmd == "gh":
            reason = gh_human_only(args)
            if reason:
                return reason
        for code in inline_code_strings(cmd, args):
            reason = human_only(code, ctx, cwd)
            if reason:
                return reason
    for code in piped_shell_code(command):
        reason = human_only(code, ctx, cwd)
        if reason:
            return reason
    for code in command_substitutions(command):
        reason = human_only(code, ctx, cwd)
        if reason:
            return reason
    return None


PYTHON_VERSIONED = re.compile(r"^python[23](?:\.\d+)?$")
ARGV_EXEC = re.compile(r"(?:subprocess\.\w+|os\.exec\w*|os\.spawn\w*|os\.popen)\s*\(\s*"
                       r"(\[\s*(?:['\"][^'\"]*['\"]\s*,?\s*)+\])")
# an exec-style call whose first argument is a shell string: os.system('git push --force'),
# subprocess.run('gh pr merge'), perl system("..."), node child_process.execSync('...'). A quoted string
# anywhere else (print('git rebase'), console.log('...'), regex.exec('...')) is data, not a command.
STRING_EXEC = re.compile(
        r"(?:os\.(?:system|popen|exec\w*|spawn\w*)|subprocess\.\w+|child_process\.\w+"
        r"|\b(?:execSync|execFileSync|spawnSync|execFile|shell_exec|passthru|proc_open|system|popen)"
        r"|(?<![.\w])(?:exec|spawn))\s*\(\s*")


def is_interpreter(cmd):
    """An interpreter that runs inline code with -c/-e, including a versioned python3.12 / python2.7."""
    return cmd in INTERPRETERS or PYTHON_VERSIONED.match(cmd) is not None


def argv_commands(codes):
    """`subprocess.run(['git','push','--force'])`: the argv list is one command - program argv[0] with its
    literal arguments. Quote each element so a DATA argument (`['echo', 'example; git rebase']` only prints
    text) is not re-split on shell metacharacters; only the program and its real flags reach the git/gh rules.
    Only an exec-style call qualifies, so a plain data list (`print(['git','push'])`) is not assembled."""
    out = []
    for code in codes:
        for m in ARGV_EXEC.finditer(code):
            parts = re.findall(r"['\"]([^'\"]*)['\"]", m.group(1))
            if parts:
                out.append(" ".join(shlex.quote(p) for p in parts))
    return out


def interpreter_option_value(cmd, args, index):
    if index == 0:
        return False
    previous = args[index - 1]
    if cmd == "python" or PYTHON_VERSIONED.match(cmd):
        return previous in ("-W", "-X", "--check-hash-based-pycs")
    if cmd == "node":
        return previous in ("-r", "--require", "--loader", "--import", "--inspect", "--inspect-brk",
                            "--inspect-port", "--conditions", "-C")
    if cmd in ("bash", "sh", "zsh"):
        return previous in ("-O", "-o")
    if cmd == "ruby":
        return previous in ("-I", "-r", "-C", "--load-path", "--require")
    return False


def inline_code_strings(cmd, args):
    """Code handed to an interpreter or eval: the human-only git/gh rules apply inside it too."""
    codes = []
    if is_interpreter(cmd) or cmd == "perl":
        python = cmd == "python" or PYTHON_VERSIONED.match(cmd) is not None
        for i, a in enumerate(args):
            if cmd != "perl":
                if a in ("--", "-") or (python and (a == "-m" or (a.startswith("-m") and not a.startswith("--")))):
                    break                   # stdin/script/module: the rest belongs to the application
                if cmd in ("bash", "sh", "zsh") and a == "-s":
                    break
                if not a.startswith("-") and not interpreter_option_value(cmd, args, i):
                    break                   # script filename: option-looking values after it are application argv
            flag = a.lower() if cmd == "perl" else a   # perl -E runs code like -e
            if flag in ("-c", "-e"):
                if i + 1 < len(args):
                    codes.append(args[i + 1])
                if cmd != "perl":
                    break                   # everything after the program is argv data, not more code flags
            elif flag.startswith("-c") and len(flag) > 2 and not flag.startswith("--"):
                codes.append(a[2:])
                if cmd != "perl":
                    break
            elif flag.startswith("-e") and len(flag) > 2 and not flag.startswith("--"):
                codes.append(a[2:])
                if cmd != "perl":
                    break
            elif cmd == "node" and (flag in ("--eval", "--print")
                                    or flag.startswith("--eval=") or flag.startswith("--print=")):
                if "=" in a:
                    codes.append(a.split("=", 1)[1])
                elif i + 1 < len(args):
                    codes.append(args[i + 1])
                break
        for code in list(codes):
            for m in STRING_EXEC.finditer(code):
                q = QUOTED.match(code, m.end())
                if q:
                    codes.append(q.group(0)[1:-1])   # the exec call's shell string: os.system('git push --force')
        codes.extend(argv_commands(codes))
    if cmd in ("eval", "source", "."):
        codes.append(" ".join(args))
    return codes


def reads_stdin_program(words):
    """True when an interpreter runs a program read from stdin (bare, '-', or shell -s), so text piped to it
    is code. A script file (`python3 s.py`), a module (`python3 -m m`) or inline code (-c/-e/--eval) is not:
    there the piped text is data the program reads, not commands the shell runs."""
    if not words:
        return False
    cmd, args = os.path.basename(words[0]), words[1:]
    if not is_interpreter(cmd) or inline_code(words):
        return False
    if any(a in ("--eval", "--print") or a.startswith(("--eval=", "--print=")) for a in args):
        return False
    if any(a == "-m" or (a.startswith("-m") and not a.startswith("--")) for a in args):
        return False
    if cmd in ("bash", "sh", "zsh") and any(
            a == "-s" or (a.startswith("-") and not a.startswith("--") and "s" in a[1:]) for a in args):
        return True
    return not [a for a in args if not a.startswith("-")]   # no script-file argument: the program is stdin


def piped_shell_code(command):
    """Text piped into an interpreter reading stdin (`echo 'git push --force' | bash`): scan the payload.
    Quoted fragments are scanned for any left command; for echo/printf the unquoted args are printed text
    too, so reconstruct them (`echo git push --force | bash` really runs the push)."""
    codes = []
    parts = command.split("|")
    for i in range(len(parts) - 1):
        right = words_of(parts[i + 1])
        if reads_stdin_program(right):
            for m in QUOTED.finditer(parts[i]):
                codes.append(m.group(0)[1:-1])
            left = words_of(parts[i])
            if left:
                lcmd = os.path.basename(left[0])
                if lcmd == "echo":
                    rest = left[1:]
                    while rest and rest[0] in ("-n", "-e", "-E", "-ne", "-en", "-nE"):
                        rest = rest[1:]
                    if rest:
                        codes.append(" ".join(rest))
                elif lcmd == "printf":
                    if len(left) > 1:
                        codes.append(" ".join(left[1:]))   # the format string may itself be the payload
                    if len(left) > 2:
                        codes.append(" ".join(left[2:]))   # ...or the args printed after the format
    return codes


def command_substitutions(command):
    """Bodies of $(...) and `...` that the shell actually executes: unquoted and inside double quotes run
    substitutions, inside single quotes they are literal text. Returned bodies are re-checked by human_only,
    which recurses into nested substitutions on its own."""
    bodies = []
    i, n, quote = 0, len(command), None
    while i < n:
        c = command[i]
        if quote == "'":
            if c == "'":
                quote = None
            i += 1
            continue
        if c == "'" and quote is None:
            quote = "'"
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif c == "\\" and quote is None:
            i += 1
        elif command.startswith("$(", i):
            depth, j, q = 1, i + 2, None
            while j < n and depth:
                cj = command[j]
                if q == "'":
                    if cj == "'":
                        q = None
                elif cj == "'" and q is None:
                    q = "'"
                elif cj == '"':
                    q = None if q == '"' else '"'
                elif cj == "\\" and q != "'":
                    j += 1                      # escaped char: neither a paren nor a quote
                elif q is None:
                    if cj == "(":
                        depth += 1
                    elif cj == ")":
                        depth -= 1              # a ) inside quotes is literal, it does not close the body
                j += 1
            bodies.append(command[i + 2:j - 1])
            i = j
            continue
        elif c == "`":
            j = command.find("`", i + 1)
            j = n if j < 0 else j
            bodies.append(command[i + 1:j])
            i = j + 1
            continue
        i += 1
    return bodies


def gh_human_only(args):
    rest = list(args)
    while rest and rest[0].startswith("-"):          # global options: -R/--repo <owner/repo>, --hostname <host>
        opt = rest.pop(0)
        if opt in ("-R", "--repo", "--hostname") and rest:
            rest.pop(0)
    if rest[:2] == ["pr", "merge"] or rest[:1] == ["merge"]:
        return "Merging the pull request is the human's decision. Push the branch, open the PR and report."
    if rest[:1] == ["api"] and any("merge" in a.lower() for a in rest[1:]):
        return "Merging through the GitHub API is reserved for the human."
    if rest[:1] == ["repo"] and rest[1:2] and rest[1] in ("delete", "edit", "rename", "archive"):
        return "Changing the repository itself is reserved for the human."
    return None


def push_branch_dir(args, cwd):
    """Directory whose HEAD a push acts on: honour -C and --git-dir, as git_subcommand/path_tokens do.
    A worktree on the base branch is pushed even when the session's own project sits on a feature branch."""
    base, git_dir = cwd, None
    sub = git_subcommand(args)
    region = args[:args.index(sub)] if sub in args else args
    i = 0
    while i < len(region):
        a = region[i]
        if a == "-C" and i + 1 < len(region):
            t = region[i + 1]
            base = os.path.realpath(t if os.path.isabs(t) else os.path.join(base, t))
            i += 2
            continue
        if a.startswith("-C") and not a.startswith("--") and len(a) > 2:
            t = a[2:]
            base = os.path.realpath(t if os.path.isabs(t) else os.path.join(base, t))
        elif a == "--git-dir" and i + 1 < len(region):
            git_dir = region[i + 1]
            i += 2
            continue
        elif a.startswith("--git-dir="):
            git_dir = a.split("=", 1)[1]
        i += 1
    return base, git_dir


def push_current_branch(args, cwd):
    base, git_dir = push_branch_dir(args, cwd)
    if git_dir:
        return git(base, "--git-dir", git_dir, "symbolic-ref", "--short", "HEAD")
    return git(base, "symbolic-ref", "--short", "HEAD")


def git_human_only(args, ctx, cwd):
    sub = git_subcommand(args)
    rest = args[args.index(sub) + 1:] if sub in args else []
    if skips_git_hooks(args):
        return "Skipping git hooks (--no-verify) is reserved for the human."
    if sub in HISTORY_REWRITING:
        return (f"git {sub} rewrites or undoes history, which may drop the approved specification commit. "
                f"Reserved for the human (fix forward with a new commit instead).")
    if sub == "commit" and "--amend" in rest:
        return "git commit --amend rewrites history (the approved spec commit must stay as it is). Make a new commit."
    if sub == "push":
        if any(a.startswith("--force") or (a.startswith("-") and not a.startswith("--") and "f" in a[1:])
               for a in rest):
            return "Force-pushing is reserved for the human."
        if any(a in ("--mirror", "--all") for a in rest):
            return ("git push --mirror/--all rewrites every ref including the base branch. "
                    "Reserved for the human. Push your own branch only.")
        refspecs = [a for a in rest if not a.startswith("-")][1:]   # after the remote name
        if any(a.startswith("+") or a == ctx.base_branch or a.endswith(":" + ctx.base_branch)
               or a.endswith("/" + ctx.base_branch) for a in refspecs):
            return f"Pushing to {ctx.base_branch} is the human's decision (merge the PR). Push your own branch only."
        if any(a in ("HEAD", "@") for a in refspecs):   # bare HEAD/@ pushes the current branch; @ is git's HEAD synonym
            current = push_current_branch(args, cwd)
            if current == ctx.base_branch:
                return (f"Pushing HEAD while on {ctx.base_branch} pushes the base branch. "
                        "Reserved for the human. Push your own branch only.")
        if not refspecs:
            current = push_current_branch(args, cwd)
            if current == ctx.base_branch:
                return (f"Pushing without a refspec while on {ctx.base_branch} pushes the base branch "
                        "(push.default=simple). Reserved for the human. Push your own branch only.")
    if sub == "reset":
        before_dashes = rest[:rest.index("--")] if "--" in rest else rest
        positional = [a for a in before_dashes if not a.startswith("-")]
        revision = positional[0] if positional else None
        # `git reset`, `git reset HEAD file`, `git reset file` unstage; anything else moves the branch
        if revision not in (None, "HEAD") and not os.path.exists(os.path.join(cwd, revision)):
            return "git reset to another revision drops commits (possibly the approved spec). Reserved for the human."
    if sub in ("checkout", "switch") and any(a in ("-B", "-C", "--force-create") for a in rest):
        return "Re-creating the branch at another revision drops its commits (the approved spec). Reserved for the human."
    if sub == "branch" and any(a in ("-f", "--force", "-D", "-M", "-d", "-m", "--delete", "--move", "--copy", "-c", "-C")
                               or (a.startswith("-") and not a.startswith("--") and any(ch in "fDMdmcC" for ch in a[1:]))
                               for a in rest):
        return "Moving, forcing or deleting branches is reserved for the human."
    return None


def hooksPath_override(args):
    """`git -c core.hooksPath=…` disables hooks. Only a real config override — the value of a global -c
    before the subcommand — not a commit message that happens to mention core.hooksPath."""
    sub = git_subcommand(args)
    region = args[:args.index(sub)] if sub in args else args
    i = 0
    while i < len(region):
        a = region[i]
        if a == "-c":
            if i + 1 < len(region) and region[i + 1].lower().startswith("core.hookspath="):
                return True
            i += 2
            continue
        if a.startswith("-c") and not a.startswith("--") and a[2:].lower().startswith("core.hookspath="):
            return True
        i += 1
    return False


def skips_git_hooks(args):
    if any(a.startswith("--no-v") and "--no-verify".startswith(a) for a in args):
        return True
    if git_subcommand(args) != "commit":
        return False
    if hooksPath_override(args):
        return True
    skip = False
    for a in args:
        if skip:
            skip = False
        elif a in GIT_VALUE_OPTIONS:
            skip = True
        elif a.startswith("-") and not a.startswith("--"):
            for i, flag in enumerate(a[1:]):      # short-option cluster such as -an or -am "msg"
                if flag == "n":
                    return True
                if flag in "mFCct":               # takes a value: attached ("-mfix") or the next argument
                    skip = i == len(a) - 2
                    break
    return False


def segments(command):
    return [s for s in re.split(r"\|\||&&|[;|&`\n]|\$\(|[()]", command) if s.strip()]


def split_shell(command):
    """Like segments, but separators inside quotes do not split: `bash -c 'echo ok; git push --force'`
    stays one segment so the inline code reaches inline_code_strings intact (the ';' is code, not a separator).
    Subshell boundaries are emitted as standalone '(' / ')' markers (a '$(' opens a scope too) so the caller
    can keep a cd inside ( ... ) from leaking to the parent shell."""
    parts, buf = [], []
    quote, esc, i, n = None, False, 0, len(command)
    while i < n:
        c = command[i]
        if esc:
            buf.append(c)
            esc = False
        elif c == "\\" and quote != "'":
            buf.append(c)
            esc = True
        elif quote:
            buf.append(c)
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
            buf.append(c)
        elif command.startswith(("||", "&&"), i):
            parts.append("".join(buf))
            buf = []
            i += 1
        elif command.startswith("$(", i):
            parts.append("".join(buf))
            buf = []
            parts.append("(")
            i += 1
        elif c == "(":
            parts.append("".join(buf))
            buf = []
            parts.append("(")
        elif c == ")":
            parts.append("".join(buf))
            buf = []
            parts.append(")")
        elif c in ";|&`\n":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [s for s in parts if s.strip()]


def segments_scoped(command):
    """segments() for quote-neutralised text, but subshell parens are emitted as '(' / ')' markers so a cd
    inside ( ... ) or $( ... ) is scoped to the subshell and cannot leak to the parent shell's commands."""
    out, last = [], 0
    for m in re.finditer(r"\|\||&&|[;|&`\n]|\$\(|[()]", command):
        out.append(command[last:m.start()])
        sep = m.group(0)
        if sep in ("(", "$("):
            out.append("(")
        elif sep == ")":
            out.append(")")
        last = m.end()
    out.append(command[last:])
    return [s for s in out if s.strip()]


def words_of(segment):
    try:
        words = shlex.split(segment, posix=True)
    except ValueError:
        words = segment.split()
    while words and (re.match(r"^\w+=", words[0]) or words[0] in WRAPPERS or words[0] in SHELL_KEYWORDS
                     or words[0] == "xargs"):
        wrapper = words.pop(0)
        if wrapper in ("xargs", "timeout", "nice"):
            while words and words[0].startswith("-"):
                words.pop(0)
            if wrapper == "timeout" and words:
                words.pop(0)   # the duration
        elif wrapper == "env":
            split_value = None
            while words and words[0].startswith("-"):
                opt = words.pop(0)
                name = opt.split("=", 1)[0]
                if name in ("-S", "--split-string"):
                    # -S/--split-string value IS the command: env splits and executes it, so surface it
                    split_value = opt.split("=", 1)[1] if "=" in opt else (words.pop(0) if words else None)
                    break
                if "=" not in opt and name in WRAPPER_VALUE_OPTS["env"] and words:
                    words.pop(0)
            if split_value is not None:
                try:
                    inner = shlex.split(split_value, posix=True)
                except ValueError:
                    inner = split_value.split()
                words = inner + words
                continue                       # re-strip wrappers on the surfaced command (nested env/sudo)
            while words and re.match(r"^\w+=", words[0]):
                words.pop(0)   # env NAME=VALUE assignments before the wrapped command
        elif wrapper in WRAPPER_VALUE_OPTS:
            value_opts = WRAPPER_VALUE_OPTS[wrapper]
            while words and words[0].startswith("-"):
                opt = words.pop(0)
                name = opt.split("=", 1)[0]
                if "=" not in opt and name in value_opts and words:
                    words.pop(0)
            while words and re.match(r"^\w+=", words[0]):
                words.pop(0)   # env NAME=VALUE assignments before the wrapped command
    return words


def follow_cd(words, cwd, project):
    """`cd dir && ...` (or pushd): later segments resolve relative to dir."""
    if words and words[0] in ("cd", "pushd"):
        target = words[1] if len(words) > 1 and not words[1].startswith("-") else "~"
        target = os.path.expanduser(target)
        return os.path.realpath(target if os.path.isabs(target) else os.path.join(cwd, target))
    return cwd


def short_flags(args):
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))


def mentions(command, path):
    """The command names this path as a whole segment ('gauntlet' matches 'gauntlet/x', not 'gauntletFast');
    a name inside a Gradle output directory ('build/gauntlet/x.log') is not the protected path."""
    return re.search(r"(?<![\w.-])(?<!build/)(?<!\.gradle/)" + re.escape(path) + r"(?![\w-])", command,
                     re.IGNORECASE) is not None


def without_gradle_tasks(text):
    """`./gradlew gauntlet` names a task, not the directory: drop task names (bare words of a Gradle call that are
    neither options nor option values) before the text match; everything else of the command stays."""
    for segment in segments(text):
        words = words_of(segment)
        if not words or os.path.basename(words[0]) not in GRADLE:
            continue
        tasks = {w for i, w in enumerate(words[1:], 1)
                 if not w.startswith("-") and "/" not in w and words[i - 1] not in GRADLE_PATH_OPTIONS}
        cleaned = segment
        for task in tasks:
            cleaned = re.sub(r"(?<!\S)" + re.escape(task) + r"(?!\S)", " ", cleaned)
        text = text.replace(segment, cleaned, 1)     # only inside the Gradle call itself
    return text


def inline_code(words):
    if not words:
        return False
    cmd, args = os.path.basename(words[0]), words[1:]
    if is_interpreter(cmd):
        return any(f in short_flags(args) for f in "ce")
    return cmd == "perl" and "e" in short_flags(args).lower()


def writes_worktree(words, segment):
    if not words:
        return False
    cmd, args = os.path.basename(words[0]), words[1:]
    if cmd in MUTATING_COMMANDS:
        return True
    if cmd == "sed":
        return "i" in short_flags(args) or "--in-place" in args
    if cmd == "perl":
        return "i" in short_flags(args) or ("e" in short_flags(args).lower() and bool(PERL_WRITES.search(segment)))
    if cmd in ("awk", "gawk"):
        return "-i" in args or any(a.startswith("-i") for a in args)
    if is_interpreter(cmd):
        return any(f in short_flags(args) for f in "ce")
    if cmd == "git":
        return git_subcommand(args) in GIT_WORKTREE_WRITING
    if cmd == "find":
        if "-delete" in args:
            return True
        return any(a in ("-exec", "-execdir", "-ok") and i + 1 < len(args) and os.path.basename(args[i + 1])
                   in MUTATING_COMMANDS for i, a in enumerate(args))
    return False


def changes_state(words, segment):
    if words and os.path.basename(words[0]) == "git":
        sub = git_subcommand(words[1:])
        rest = words[words.index(sub) + 1:] if sub in words else []
        return sub in GIT_STATE_CHANGING and not git_read_only(sub, rest)
    return writes_worktree(words, segment)


def git_read_only(sub, rest):
    """`git branch -a`, `git stash list`, `git tag -l`: listing forms of otherwise state-changing commands."""
    forms = GIT_READ_ONLY_FORMS.get(sub)
    if forms is None:
        return False
    if not rest:
        return sub != "stash"              # bare `git stash` saves; bare branch/tag/notes/submodule list
    if sub in ("stash", "worktree", "notes", "submodule") or rest[0] in ("-l", "--list"):
        return rest[0] in forms or rest[0] in ("-l", "--list")
    return all(a in forms or a.startswith(("--format", "--sort", "--contains", "--points-at", "--merged", "--no-merged"))
               or (a.startswith("-") and not a.startswith("--") and set(a[1:]) <= set("larvn")) for a in rest)


def git_subcommand(args):
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ("-C", "-c", "--git-dir", "--work-tree"):
            skip = True
            continue
        if not a.startswith("-"):
            return a
    return ""


def path_tokens(words, cwd, project):
    """Path-like arguments of a command, with `git -C dir` honoured and globs expanded."""
    if not words:
        return []
    cmd, args = os.path.basename(words[0]), words[1:]
    base = cwd
    if cmd == "git" and "-C" in args and args.index("-C") + 1 < len(args):
        target = args[args.index("-C") + 1]
        base = os.path.realpath(target if os.path.isabs(target) else os.path.join(cwd, target))
    tokens = []
    for a in args:
        if a.startswith("-") and not a.startswith("-/"):
            continue
        if GLOB_CHARS.search(a):
            pattern = a if os.path.isabs(a) else os.path.join(base, a)
            tokens.extend(glob.glob(pattern) or [a])
        elif "/" in a or a in (".", "..") or os.path.exists(os.path.join(base, a)):
            tokens.append(a)
    if base == cwd:
        return tokens
    return [t if os.path.isabs(t) else os.path.join(base, t) for t in tokens]   # git -C dir: resolve against dir


# ----------------------------------------------------------------------------- helpers

def read_properties(path):
    props = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    props[key.strip()] = value.strip()
    except OSError:
        pass
    return props


def git(project, *args):
    try:
        return subprocess.run(["git", "-C", project, "-c", "core.quotePath=false", *args], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def git_code(project, *args):
    try:
        return subprocess.run(["git", "-C", project, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=30).returncode
    except (OSError, subprocess.TimeoutExpired):
        return -1


if __name__ == "__main__":
    sys.exit(main())

===== END FILE gauntlet/hooks/guard.py =====

===== BEGIN FILE gauntlet/hooks/selftest.py =====
#!/usr/bin/env python3
"""Self-test for the gauntlet hooks. Builds a throwaway git repository with a fake base branch and
runs guard.py / stop_gate.py against it the way Claude Code does (JSON on stdin, environment set).

    python3 gauntlet/hooks/selftest.py          # from any directory; needs git and python3

Gradle is stubbed with a fake ./gradlew that exits with the code found in a marker file, so the
Stop-gate logic is exercised without a JVM.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HOOKS = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HOOKS)
FEATURES_REL = "src/acceptanceTest/resources/features"
MODULES = []          # Gradle builds inside the repository: [] = one build at the root, ["core", "adapter"] = monorepo
M = ""                # prefix of the module the shared tests work in ("" or "core/")
FEATURES = FEATURES_REL
FAKE_GRADLEW = ("#!/bin/sh\ncode=$(cat build/gauntlet/fake-exit 2>/dev/null || echo 0)\n"
                "echo \"fake gradle $*\"\n[ \"$code\" = 0 ] || echo 'CRAP FAIL com.example.X#y'\nexit $code\n")
failures = []
passed = 0


def sh(repo, *cmd, **kw):
    return subprocess.run(cmd, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)


def git(repo, *args):
    r = sh(repo, "git", *args)
    assert r.returncode == 0, f"git {' '.join(args)}: {r.stdout}"
    return r.stdout.strip()


def make_repo():
    root = tempfile.mkdtemp(prefix="gauntlet-selftest-")
    repo = os.path.join(root, "service")
    bare = os.path.join(root, "origin.git")
    os.makedirs(repo)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    shutil.copytree(KIT, os.path.join(repo, "gauntlet"), ignore=shutil.ignore_patterns("__pycache__"))
    # the layout under test decides `module`, not the installed kit's value (a monorepo install sets it)
    props = os.path.join(repo, "gauntlet/config/gauntlet.properties")
    with open(props) as f:
        lines = [line for line in f.read().splitlines() if not line.strip().startswith("module=")]
    with open(props, "w") as f:
        f.write("\n".join(lines) + f"\nmodule={','.join(MODULES)}\n")
    for prefix in [m + "/" for m in MODULES] or [""]:
        write(repo, prefix + "build.gradle.kts", 'plugins { java }\napply(from = "../gauntlet/gauntlet.gradle")\n')
        write(repo, prefix + "src/main/java/com/example/service/domain/Order.java",
              "package com.example.service.domain;\npublic class Order { public int discount(int p) { return p / 10; } }\n")
        write(repo, prefix + "src/test/java/com/example/service/domain/OrderTest.java",
              "package com.example.service.domain;\nclass OrderTest { }\n")
        write(repo, prefix + FEATURES_REL + "/.gitkeep", "")
        write(repo, prefix + "gradlew", FAKE_GRADLEW)
        os.chmod(os.path.join(repo, prefix + "gradlew"), 0o755)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    git(repo, "remote", "add", "origin", bare)
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "-b", "claude/feature-x")
    return repo


def write(repo, rel, text):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def run_hook(repo, script, event, env=None, args=()):
    e = dict(os.environ, CLAUDE_PROJECT_DIR=repo)
    e.pop("GAUNTLET_GUARD", None)
    e.pop("GAUNTLET_STOP_HOOK", None)
    e.update(env or {})
    r = subprocess.run([sys.executable, os.path.join(repo, "gauntlet", "hooks", script), *args], cwd=repo,
                       input=json.dumps(event), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=e)
    return r


def guard(repo, agent, tool, **params):
    event = {"session_id": "s1", "cwd": repo, "tool_name": tool, "tool_input": params}
    if agent != "main":
        event["agent_type"] = agent
    r = run_hook(repo, "guard.py", event)
    if r.returncode != 0:
        return "CRASH " + r.stderr
    if not r.stdout.strip():
        return None
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


def check(name, condition, detail=""):
    global passed
    if condition:
        passed += 1
    else:
        failures.append(f"{name}  {detail}")


def expect_deny(repo, name, agent, tool, **params):
    reason = guard(repo, agent, tool, **params)
    check(name, reason is not None and not reason.startswith("CRASH"), f"expected deny, got {reason!r}")


def expect_allow(repo, name, agent, tool, **params):
    reason = guard(repo, agent, tool, **params)
    check(name, reason is None, f"expected allow, got {reason!r}")


def guard_tests(repo):
    feature = FEATURES + "/order.feature"
    # --- human-owned files
    for path in ("gauntlet/config/gauntlet.properties", "gauntlet/gauntlet.gradle", "gauntlet/hooks/guard.py",
                 ".claude/settings.json", ".claude/agents/specifier.md", "CLAUDE.md", ".github/workflows/gauntlet.yml"):
        expect_deny(repo, f"edit {path}", "main", "Edit", file_path=path, old_string="a", new_string="b")
    expect_deny(repo, "write absolute gauntlet path", "main", "Write",
                file_path=os.path.join(repo, "gauntlet/config/crap-allowlist.txt"), content="x")
    expect_allow(repo, "edit main code", "main", "Edit", file_path=M + "src/main/java/com/example/service/domain/Order.java",
                 old_string="a", new_string="b")
    expect_allow(repo, "edit build.gradle.kts", "main", "Edit", file_path=M + "build.gradle.kts", old_string="a", new_string="b")
    expect_allow(repo, "write step definitions", "main", "Write",
                 file_path=M + "src/acceptanceTest/java/com/example/service/acceptance/Steps.java", content="x")
    # --- shell writes to protected paths
    expect_deny(repo, "sed -i on gauntlet", "main", "Bash", command="sed -i 's/8/80/' gauntlet/config/gauntlet.properties")
    expect_deny(repo, "redirect into gauntlet", "main", "Bash", command="echo x > gauntlet/config/crap-allowlist.txt")
    expect_deny(repo, "cp over .claude", "main", "Bash", command="cp /tmp/s.json .claude/settings.json")
    expect_deny(repo, "python -c writing CLAUDE.md", "main", "Bash", command="python3 -c \"open('CLAUDE.md','w').write('')\"")
    expect_deny(repo, "git checkout gauntlet", "main", "Bash", command="git checkout -- gauntlet/config/checkstyle.xml")
    expect_deny(repo, "rm gauntlet dir", "main", "Bash", command="rm -rf gauntlet")
    expect_deny(repo, "hook switch", "main", "Bash", command="GAUNTLET_GUARD=off ./gradlew gauntlet")
    expect_deny(repo, "export hook switch", "main", "Bash", command="export GAUNTLET_STOP_HOOK=off; ./gradlew test")
    # --- no false positives
    expect_allow(repo, "gradlew gauntletFast", "main", "Bash", command="./gradlew gauntletFast --continue")
    expect_allow(repo, "gradlew gauntlet", "main", "Bash", command="./gradlew gauntlet --continue -Pgauntlet.baseRef=origin/main")
    expect_allow(repo, "cat gauntlet file", "main", "Bash", command="cat gauntlet/config/gauntlet.properties")
    expect_allow(repo, "git add -A", "main", "Bash", command="git add -A && git commit -m 'feat: discount'")
    expect_allow(repo, "git add gauntlet path", "main", "Bash", command="git add gauntlet/ .claude/ CLAUDE.md")
    expect_allow(repo, "commit mentioning gauntlet", "main", "Bash", command='git commit -m "chore: install the gauntlet"')
    expect_allow(repo, "git push own branch", "main", "Bash", command="git push -u origin HEAD")
    expect_allow(repo, "git push named branch", "main", "Bash", command="git push origin claude/feature-x")
    expect_allow(repo, "rm build/reports", "main", "Bash", command=f"rm -rf {M}build/reports")
    expect_allow(repo, "rm build/gauntlet (hook log dir)", "main", "Bash", command=f"rm -rf {M}build/gauntlet")
    expect_allow(repo, "tee into build/gauntlet", "main", "Bash", command=f"./gradlew gauntletFast 2>&1 | tee {M}build/gauntlet/run.log")
    expect_allow(repo, "cp hook log out", "main", "Bash", command=f"cp {M}build/gauntlet/gauntletFast-hook.log /tmp/")
    expect_allow(repo, "stash with gauntlet in message", "main", "Bash", command='git stash push -m "before gauntlet run"')
    expect_allow(repo, "mkdir build dir", "main", "Bash", command=f"mkdir -p {M}build/tmp && echo x > {M}build/tmp/a.txt")
    expect_allow(repo, "redirect 2>&1", "main", "Bash", command="./gradlew test 2>&1 | tail -20")
    expect_allow(repo, "redirect to /dev/null", "main", "Bash", command="./gradlew test > /dev/null 2>&1")
    expect_deny(repo, "quoted redirect into gauntlet", "main", "Bash", command='echo x > "gauntlet/config/crap-allowlist.txt"')
    expect_deny(repo, "heredoc into CLAUDE.md", "main", "Bash", command="cat > 'CLAUDE.md' <<EOF\nx\nEOF")
    expect_deny(repo, "2> into .claude", "main", "Bash", command="ls 2> .claude/settings.json")
    expect_deny(repo, "&> into .claude", "main", "Bash", command="ls &> .claude/settings.json")
    expect_deny(repo, "1> into gauntlet", "main", "Bash", command="ls 1> gauntlet/config/x")
    expect_deny(repo, "rm -rf star", "main", "Bash", command="rm -rf *")
    expect_deny(repo, "rm -rf dot", "main", "Bash", command="rm -rf .")
    expect_deny(repo, "rm glob under gauntlet", "main", "Bash", command="rm gauntlet/config/*.txt")
    expect_deny(repo, "cd into gauntlet then write", "main", "Bash", command="cd gauntlet/config && cp /tmp/x crap-allowlist.txt")
    expect_deny(repo, "git -C gauntlet checkout", "main", "Bash", command="git -C gauntlet checkout -- config/checkstyle.xml")
    expect_deny(repo, "write ~/.claude settings", "main", "Write", file_path=os.path.expanduser("~/.claude/settings.json"), content="{}")
    expect_deny(repo, "redirect into ~/.claude", "main", "Bash", command="echo '{\"disableAllHooks\": true}' > ~/.claude/settings.json")
    expect_deny(repo, "checkout -B to base", "main", "Bash", command="git checkout -B claude/feature-x origin/main")
    expect_deny(repo, "switch -C to base", "main", "Bash", command="git switch -C claude/feature-x origin/main")
    expect_deny(repo, "branch -f", "main", "Bash", command="git branch -f claude/feature-x origin/main")
    expect_deny(repo, "branch -D", "main", "Bash", command="git branch -D claude/feature-x")
    expect_allow(repo, "checkout -b new branch", "main", "Bash", command="git checkout -b claude/feature-z")
    expect_allow(repo, "switch existing", "main", "Bash", command="git switch main")
    expect_deny(repo, "gh -R pr merge", "main", "Bash", command="gh -R o/r pr merge 12 --squash")
    expect_deny(repo, "gh --repo pr merge", "main", "Bash", command="gh --repo o/r pr merge 12")
    # --- `gauntlet` as a Gradle task or under build/ is not the kit
    expect_allow(repo, "rm build/gauntlet log with $?", "main", "Bash", command=f"rm -f {M}build/gauntlet/x.log; echo $?")
    expect_allow(repo, "rm missing file then gradlew gauntlet", "main", "Bash",
                 command="rm -f out.log && ./gradlew gauntlet --continue > out.log 2>&1")
    expect_allow(repo, "gradlew gauntlet | tee $VAR", "main", "Bash", command='./gradlew gauntlet --continue 2>&1 | tee "$TMPDIR/run.log"')
    expect_allow(repo, "mkdir $VAR then gradlew gauntlet", "main", "Bash", command='mkdir -p "$SCRATCH" && ./gradlew gauntlet')
    expect_allow(repo, "python -c reads build/gauntlet", "main", "Bash",
                 command=f"python3 -c \"print(open('{M}build/gauntlet/gauntletFast-hook.log').read())\"")
    expect_deny(repo, "rm $VAR with gauntlet assigned", "main", "Bash", command="D=gauntlet; rm -rf $D")
    expect_deny(repo, "rm $VAR next to gradlew gauntlet", "main", "Bash", command="./gradlew gauntlet; X=gauntlet/config; rm -rf $X")
    expect_deny(repo, "echo gauntlet | xargs rm next to gradlew gauntlet", "main", "Bash",
                command="./gradlew gauntlet; echo gauntlet | xargs rm -rf")
    expect_deny(repo, "rm $VAR next to gradlew -p gauntlet", "main", "Bash", command="./gradlew -p gauntlet tasks; rm -rf $X")
    expect_deny(repo, "rm via build/.. back into gauntlet", "main", "Bash", command="rm -rf $P/build/../gauntlet")
    expect_deny(repo, "for ... do rm", "main", "Bash", command='for f in gauntlet/config/*; do rm "$f"; done')
    expect_deny(repo, "then rm", "main", "Bash", command="if true; then rm -rf gauntlet; fi")
    expect_deny(repo, "brace group rm", "main", "Bash", command="{ rm -rf .claude; }")
    expect_deny(repo, "negated rm", "main", "Bash", command="! rm -f CLAUDE.md")
    expect_deny(repo, "do sed -i", "main", "Bash", command="while false; do sed -i 's/8/80/' gauntlet/config/gauntlet.properties; done")
    expect_deny(repo, "then git push --force", "main", "Bash", command="if true; then git push --force; fi")
    expect_deny(repo, "rm via $PWD", "main", "Bash", command="rm -rf $PWD/gauntlet")
    expect_deny(repo, "rm via $CLAUDE_PROJECT_DIR", "main", "Bash", command='rm -rf "$CLAUDE_PROJECT_DIR/.claude"')
    expect_deny(repo, "xargs rm", "main", "Bash", command="git ls-files gauntlet/config | xargs rm -f")
    expect_deny(repo, "sed -i on substitution", "main", "Bash", command="sed -i 's/8/80/' $(git ls-files gauntlet/config/gauntlet.properties)")
    expect_deny(repo, "pushd then sed", "main", "Bash", command="pushd gauntlet/config && sed -i 's/8/80/' gauntlet.properties")
    expect_allow(repo, "mkdir via $CLAUDE_PROJECT_DIR in tests", "hardener", "Bash", command=f'mkdir -p "$CLAUDE_PROJECT_DIR/{M}src/test/java/com/example/api"')
    expect_allow(repo, "commit message heredoc mentioning install", "main", "Bash",
                 command='git commit -m "$(cat <<\'EOF\'\nchore: install the gauntlet hooks, roles and the CI workflow\n\nrm nothing; patch nothing.\nEOF\n)"')
    expect_allow(repo, "heredoc report into /tmp", "main", "Bash", command="cat > /tmp/report.md <<'EOF'\n- gauntlet/README.md -> see\nrm -rf gauntlet\nEOF")
    expect_deny(repo, "heredoc opener still checked", "main", "Bash", command="cat > gauntlet/config/x <<'EOF'\nx\nEOF")
    expect_allow(repo, "hardener heredoc test with lambda", "hardener", "Bash",
                 command=f"cat > {M}src/test/java/com/example/service/domain/OrderTest.java <<'EOF'\nassertTrue(discount(100) >= 10); list.forEach(x -> check(x));\nEOF")
    expect_allow(repo, "hardener cleans pit history", "hardener", "Bash", command=f"rm -rf {M}build/pitHistory.txt {M}build/reports/pitest")
    expect_allow(repo, "hardener tee into build", "hardener", "Bash", command=f"./gradlew mutationGate --continue 2>&1 | tee {M}build/pit.log")
    expect_allow(repo, "specifier tee into build", "specifier", "Bash", command=f"./gradlew acceptanceTest 2>&1 | tee {M}build/acceptance.log")
    expect_deny(repo, "git revert", "main", "Bash", command="git revert --no-edit HEAD")
    expect_allow(repo, "rm -rf build via var", "main", "Bash", command='rm -rf "$CLAUDE_PROJECT_DIR/build"')
    expect_deny(repo, "gh api graphql automerge", "main", "Bash",
                command="gh api graphql -f query='mutation { enablePullRequestAutoMerge(input: {pullRequestId: \"x\"}) { clientMutationId } }'")
    expect_allow(repo, "gh pr create", "main", "Bash", command='gh pr create --title "feat" --body-file /tmp/report.md')
    expect_allow(repo, "gh pr view", "main", "Bash", command="gh pr view --json url")
    expect_allow(repo, "git reset unstage", "main", "Bash", command=f"git reset HEAD {M}build.gradle.kts")
    expect_allow(repo, "git reset plain", "main", "Bash", command="git reset")
    expect_allow(repo, "git reset path", "main", "Bash", command=f"git reset {M}build.gradle.kts")
    expect_allow(repo, "git commit -am", "main", "Bash", command='git commit -am "msg no verify words"')
    # --- human-only git and gh
    expect_deny(repo, "commit --amend", "main", "Bash", command='git commit --amend -m "x"')
    expect_deny(repo, "commit -n", "main", "Bash", command='git commit -anm "x"')
    expect_deny(repo, "no-verify", "main", "Bash", command="git push --no-verify")
    expect_deny(repo, "rebase", "main", "Bash", command="git rebase -i origin/main")
    expect_deny(repo, "push --force", "main", "Bash", command="git push --force origin claude/feature-x")
    expect_deny(repo, "push -f", "main", "Bash", command="git push -f")
    expect_deny(repo, "push force-with-lease", "main", "Bash", command="git push --force-with-lease")
    expect_deny(repo, "push to main", "main", "Bash", command="git push origin main")
    expect_deny(repo, "push HEAD:main", "main", "Bash", command="git push origin HEAD:main")
    expect_deny(repo, "push +refspec", "main", "Bash", command="git push origin +claude/feature-x")
    expect_deny(repo, "reset --hard revision", "main", "Bash", command="git reset --hard origin/main")
    expect_deny(repo, "reset HEAD~1", "main", "Bash", command="git reset HEAD~1")
    expect_deny(repo, "reset --soft", "main", "Bash", command="git reset --soft HEAD^")
    expect_deny(repo, "filter-branch", "main", "Bash", command="git filter-branch --tree-filter 'rm -f x' HEAD")
    expect_deny(repo, "update-ref", "main", "Bash", command="git update-ref refs/heads/claude/feature-x abc123")
    expect_deny(repo, "gh pr merge", "main", "Bash", command="gh pr merge 12 --squash")
    expect_deny(repo, "gh api merge", "main", "Bash", command="gh api -X PUT repos/o/r/pulls/12/merge")
    expect_deny(repo, "gh merge in chain", "main", "Bash", command="./gradlew gauntlet && gh pr merge --auto")
    # --- hardening: human-only rules inside wrappers and inline code
    expect_deny(repo, "bash -c force push", "main", "Bash", command="bash -c 'git push --force origin main'")
    expect_deny(repo, "sh -c no-verify commit", "main", "Bash", command="sh -c 'git commit --no-verify -m x'")
    expect_deny(repo, "eval force push", "main", "Bash", command="eval 'git push --force'")
    expect_deny(repo, "env -i force push", "main", "Bash", command="env -i git push --force")
    expect_deny(repo, "sudo -u force push", "main", "Bash", command="sudo -u root git push --force")
    expect_deny(repo, "command -p force push", "main", "Bash", command="command -p git push --force")
    expect_deny(repo, "echo force push | bash", "main", "Bash", command="echo 'git push --force origin main' | bash")
    expect_deny(repo, "bash -c gh pr merge", "main", "Bash", command="bash -c 'gh pr merge 12'")
    expect_deny(repo, "env assignment then force push", "main", "Bash", command="env FOO=bar git push --force")
    expect_deny(repo, "env -S force push", "main", "Bash",
                command="env -S 'git push --force origin main'")
    expect_deny(repo, "env --split-string attached force push", "main", "Bash",
                command="env --split-string='git push --force origin main'")
    expect_deny(repo, "sudo env -S nested force push", "main", "Bash",
                command="sudo env -S 'git push --force origin main'")
    expect_allow(repo, "env -S harmless", "main", "Bash", command="env -S 'printf hello'")
    expect_deny(repo, "python os.system nested force push", "main", "Bash",
                command="python3 -c \"import os; os.system('git push --force')\"")
    expect_deny(repo, "python subprocess nested gh merge", "main", "Bash",
                command="python3 -c \"import subprocess; subprocess.run('gh pr merge 12', shell=True)\"")
    expect_deny(repo, "node child_process nested force push", "main", "Bash",
                command="node -e \"require('child_process').execSync('git push --force')\"")
    expect_deny(repo, "bash -c multi-command inline force push", "main", "Bash",
                command="bash -c 'echo ok; git push --force origin main'")
    expect_deny(repo, "sh -c inline amend after echo", "main", "Bash",
                command="sh -c 'echo hi && git commit --amend'")
    expect_deny(repo, "bash -c multi-command inline gh merge", "main", "Bash",
                command="bash -c 'echo ok; gh pr merge 12'")
    expect_allow(repo, "bash -c multi-command harmless", "main", "Bash",
                 command="bash -c 'echo ok; echo done'")
    expect_allow(repo, "python -c harmless quoted text", "main", "Bash",
                 command="python3 -c \"print('hello; world')\"")
    expect_allow(repo, "bash -c harmless", "main", "Bash", command="bash -c 'echo hello'")
    expect_deny(repo, "double-quote command substitution force push", "main", "Bash",
                command='echo "$(git push --force origin main)"')
    expect_deny(repo, "double-quote backtick amend", "main", "Bash",
                command='echo "`git commit --amend`"')
    expect_allow(repo, "single-quote substitution is literal", "main", "Bash",
                 command="echo '$(git push --force origin main)'")
    expect_allow(repo, "double-quote harmless substitution", "main", "Bash",
                 command='git commit -m "release $(date)"')
    # --- hardening (Grok): unquoted pipe payload, quote-aware substitution depth, wider inline interpreters
    expect_deny(repo, "echo unquoted force push | bash", "main", "Bash",
                command="echo git push --force origin main | bash")
    expect_deny(repo, "echo unquoted force push | sh", "main", "Bash", command="echo git push --force | sh")
    expect_deny(repo, "printf unquoted force push | bash", "main", "Bash",
                command="printf %s git\\ push\\ --force | bash")
    expect_allow(repo, "echo harmless | bash", "main", "Bash", command="echo hello | bash")
    expect_allow(repo, "printf harmless | bash", "main", "Bash", command="printf '%s\\n' hello | bash")
    expect_deny(repo, "substitution depth past quoted paren", "main", "Bash",
                command='echo "$(python3 -c \'print(")")\'; git push --force)"')
    expect_allow(repo, "echo harmless substitution", "main", "Bash", command='echo "$(date)"')
    expect_deny(repo, "node --eval force push", "main", "Bash",
                command="node --eval \"require('child_process').execSync('git push --force')\"")
    expect_deny(repo, "node --eval= force push", "main", "Bash",
                command="node --eval=\"require('child_process').execSync('git push --force')\"")
    expect_deny(repo, "python3.12 -c force push", "main", "Bash",
                command="python3.12 -c \"import os; os.system('git push --force')\"")
    expect_deny(repo, "python subprocess argv force push", "main", "Bash",
                command="python3 -c \"import subprocess; subprocess.run(['git','push','--force'])\"")
    expect_deny(repo, "perl -E force push", "main", "Bash", command="perl -E 'system(\"git push --force\")'")
    expect_allow(repo, "node --eval harmless", "main", "Bash", command="node --eval \"console.log(1)\"")
    expect_allow(repo, "python3.12 -c harmless", "main", "Bash", command="python3.12 -c \"print(1)\"")
    expect_allow(repo, "perl -E harmless", "main", "Bash", command="perl -E 'say 1'")
    expect_allow(repo, "python data list not a command", "main", "Bash",
                 command="python3 -c \"print(['git','push'])\"")
    # --- F14: an argv list is joined and re-parsed as shell; echo DATA must not become a command.
    #          shlex.quote keeps each element intact so '; git rebase' inside an echo arg stays text.
    expect_allow(repo, "F14 echo argv semicolon data", "main", "Bash",
                 command="python3 -c \"import subprocess; subprocess.run(['echo', 'example; git rebase'])\"")
    expect_allow(repo, "F14 echo argv pipe data", "main", "Bash",
                 command="python3 -c \"import subprocess; subprocess.run(['echo', 'x | git push --force'])\"")
    expect_allow(repo, "F14 echo argv gh merge data", "main", "Bash",
                 command="python3 -c \"import subprocess; subprocess.run(['echo', 'gh pr merge 1'])\"")
    expect_allow(repo, "F14 data args after python -c program", "main", "Bash",
                 command="python3 -c \"print('hi')\" 'example; git rebase'")
    expect_allow(repo, "F14 option-looking data after python -c program", "main", "Bash",
                 command="python3 -c 'import sys; print(sys.argv[1:])' -e 'git rebase'")
    expect_allow(repo, "option-looking data after python script", "main", "Bash",
                 command="python3 docsearch.py -e 'git rebase'")
    expect_allow(repo, "option-looking data after python module", "main", "Bash",
                 command="python3 -m docsearch -e 'git rebase'")
    expect_deny(repo, "python option value does not hide inline code", "main", "Bash",
                command="python3 -W ignore -c \"import os; os.system('git push --force')\"")
    expect_deny(repo, "F14 control real force push argv", "main", "Bash",
                command="python3 -c \"import subprocess; subprocess.run(['git', 'push', '--force'])\"")
    expect_deny(repo, "F14 control real gh merge argv", "main", "Bash",
                command="python3 -c \"import subprocess; subprocess.run(['gh', 'pr', 'merge', '1'])\"")
    # --- V5b: a quoted string that merely LOOKS like a command is data unless an exec-style call runs it
    expect_allow(repo, "print literal force push is data", "main", "Bash",
                 command="python3 -c \"print('git push --force')\"")
    expect_allow(repo, "console.log literal force push is data", "main", "Bash",
                 command="node -e \"console.log('git push --force')\"")
    expect_allow(repo, "perl print literal force push is data", "main", "Bash",
                 command="perl -e \"print 'git push --force'\"")
    # --- V5c: text piped to an interpreter running a FILE/MODULE/inline code is data, not shell commands;
    #          only a stdin program (bare, '-', shell -s) executes the piped text
    expect_allow(repo, "pipe force push to python script file", "main", "Bash",
                 command="echo 'git push --force' | python3 script.py")
    expect_allow(repo, "pipe force push to node script file", "main", "Bash",
                 command="echo 'git push --force' | node app.js")
    expect_allow(repo, "pipe force push to python module", "main", "Bash",
                 command="echo 'git push --force' | python3 -m json.tool")
    expect_allow(repo, "pipe force push to bash inline code", "main", "Bash",
                 command="echo 'git push --force' | bash -c 'echo hi'")
    expect_deny(repo, "pipe force push to bash -s", "main", "Bash",
                command="echo 'git push --force' | bash -s")
    expect_deny(repo, "pipe force push to python stdin dash", "main", "Bash",
                command="echo 'git push --force' | python3 -")
    expect_allow(repo, "sudo gradlew", "main", "Bash", command="sudo -u root ./gradlew test")
    # --- hardening: .git is human-owned (deleting it disables the stop hook and unfreezes the spec)
    expect_deny(repo, "rm -rf .git", "main", "Bash", command="rm -rf .git")
    expect_deny(repo, "write .git/config", "main", "Write", file_path=".git/config", content="x")
    expect_deny(repo, "forge green state", "main", "Bash",
                command="echo x > .git/gauntlet-hook/last-green-gauntletFast")
    expect_allow(repo, "commit still works with .git protected", "main", "Bash", command="git commit -m 'feat: x'")
    # --- hardening: push forms that rewrite every ref or the base branch
    expect_deny(repo, "push --mirror", "main", "Bash", command="git push --mirror origin")
    expect_deny(repo, "push --all", "main", "Bash", command="git push --all origin")
    cur = git(repo, "symbolic-ref", "--short", "HEAD")
    git(repo, "switch", "-q", "main")
    expect_deny(repo, "push HEAD while on main", "main", "Bash", command="git push origin HEAD")
    expect_deny(repo, "push no refspec while on main", "main", "Bash", command="git push origin")
    expect_deny(repo, "push bare while on main", "main", "Bash", command="git push")
    expect_deny(repo, "push @ while on main", "main", "Bash", command="git push origin @")
    expect_deny(repo, "push @:main while on main", "main", "Bash", command="git push origin @:main")
    expect_allow(repo, "push HEAD:other while on main", "main", "Bash", command="git push origin HEAD:other")
    expect_allow(repo, "push @:other while on main", "main", "Bash", command="git push origin @:other")
    git(repo, "switch", "-q", cur)
    expect_allow(repo, "push HEAD on feature branch", "main", "Bash", command="git push -u origin HEAD")
    expect_allow(repo, "push no refspec on feature branch", "main", "Bash", command="git push origin")
    expect_allow(repo, "push bare on feature branch", "main", "Bash", command="git push")
    expect_allow(repo, "push @ on feature branch", "main", "Bash", command="git push origin @")
    # --- hardening (Grok): a worktree on the base branch is pushed even from a feature-branch session
    root = os.path.dirname(repo)
    wt_main = os.path.join(root, "wt-main")
    wt_feat = os.path.join(root, "wt-feat")
    git(repo, "worktree", "add", "-q", wt_main, "main")
    git(repo, "worktree", "add", "-q", "-b", "claude/wt-feature", wt_feat)
    expect_deny(repo, "push -C worktree HEAD on main", "main", "Bash", command=f"git -C {wt_main} push origin HEAD")
    expect_deny(repo, "push -C worktree no refspec on main", "main", "Bash", command=f"git -C {wt_main} push")
    expect_deny(repo, "push -C worktree @ on main", "main", "Bash", command=f"git -C {wt_main} push origin @")
    expect_allow(repo, "push -C worktree HEAD on feature", "main", "Bash", command=f"git -C {wt_feat} push origin HEAD")
    # --- V5a: `cd worktree && git push` judges the branch of THAT worktree (follow_cd), not the session's project
    expect_allow(repo, "cd feature worktree push HEAD", "main", "Bash", command=f"cd {wt_feat} && git push origin HEAD")
    expect_allow(repo, "cd feature worktree push no refspec", "main", "Bash", command=f"cd {wt_feat} && git push")
    expect_deny(repo, "cd main worktree push HEAD", "main", "Bash", command=f"cd {wt_main} && git push origin HEAD")
    expect_deny(repo, "cd main worktree push no refspec", "main", "Bash", command=f"cd {wt_main} && git push")
    expect_allow(repo, "pushd feature worktree push HEAD", "main", "Bash", command=f"pushd {wt_feat} && git push origin HEAD")
    expect_allow(repo, "cd relative feature worktree push HEAD", "main", "Bash", command="cd ../wt-feat && git push origin HEAD")
    # --- F10: a `cd` INSIDE a subshell ( ) or command-substitution $( ) must not leak to the parent shell,
    #          so a parent push of the session's own feature branch is judged against the project, not mainwt.
    expect_allow(repo, "F10 subshell cd to main does not leak", "main", "Bash",
                 command=f"( cd {wt_main} && git status ) && git push -u origin HEAD")
    expect_allow(repo, "F10 cmdsubst cd to main does not leak", "main", "Bash",
                 command=f"echo $( cd {wt_main} && git status ) && git push -u origin HEAD")
    expect_allow(repo, "F10 nested subshell cd does not leak", "main", "Bash",
                 command=f"( cd {wt_main} && ( git status ) ) && git push -u origin HEAD")
    expect_deny(repo, "F10 control push inside subshell on main", "main", "Bash",
                command=f"( cd {wt_main} && git push -u origin HEAD )")
    expect_deny(repo, "F10 control real cd to main then push", "main", "Bash",
                command=f"cd {wt_main} && git push -u origin HEAD")
    expect_deny(repo, "F10 control cd then subshell then push", "main", "Bash",
                command=f"cd {wt_main} && ( git status ) && git push -u origin HEAD")
    for name, project, event_cwd, expected in (
            ("F10 event cwd feature overrides main project", wt_main, wt_feat, False),
            ("F10 event cwd main overrides feature project", wt_feat, wt_main, True)):
        event = {"session_id": "s1", "cwd": event_cwd, "tool_name": "Bash",
                 "tool_input": {"command": "git push origin HEAD"}}
        r = run_hook(repo, "guard.py", event, env={"CLAUDE_PROJECT_DIR": project})
        check(name, r.returncode == 0 and bool(r.stdout.strip()) == expected, r.stdout + r.stderr)
    git(repo, "worktree", "remove", "--force", wt_main)   # free main again for the later checkout-main tests
    git(repo, "worktree", "remove", "--force", wt_feat)
    # --- hardening: hook-skipping abbreviations and config
    expect_deny(repo, "no-verify abbreviation", "main", "Bash", command="git commit --no-verif -m x")
    expect_deny(repo, "core.hooksPath off", "main", "Bash", command="git -c core.hooksPath=/dev/null commit -m x")
    expect_deny(repo, "core.hooksPath attached -c", "main", "Bash", command="git -ccore.hooksPath=/dev/null commit -m x")
    expect_allow(repo, "core.hooksPath in commit message", "main", "Bash",
                 command="git commit -m 'Document core.hooksPath behavior'")
    expect_allow(repo, "core.hooksPath assignment in message", "main", "Bash",
                 command="git commit -m 'core.hooksPath=/dev/null is bad'")
    expect_allow(repo, "no-verify words in message", "main", "Bash",
                 command='git commit -m "docs: mention --no-verify in the message"')
    # --- hardening: case-insensitive protected paths (macOS/Windows)
    expect_deny(repo, "edit uppercase GAUNTLET", "main", "Edit",
                file_path="GAUNTLET/config/gauntlet.properties", old_string="a", new_string="b")
    expect_deny(repo, "sed uppercase GAUNTLET", "main", "Bash",
                command="sed -i 's/8/80/' GAUNTLET/config/gauntlet.properties")
    expect_deny(repo, "write mixed-case .Claude", "main", "Write", file_path=".Claude/settings.json", content="{}")
    # --- specification: before any spec commit (draft)
    check("not frozen initially", git(repo, "rev-list", "--count", "origin/main..HEAD", "--", FEATURES) == "0")
    expect_allow(repo, "specifier writes draft", "specifier", "Write", file_path=feature, content="# language: ru\n")
    expect_deny(repo, "main agent writes feature", "main", "Write", file_path=feature, content="x")
    expect_deny(repo, "specifier writes code", "specifier", "Write", file_path=M + "src/main/java/A.java", content="x")
    expect_deny(repo, "specifier edits gauntlet", "specifier", "Edit", file_path="gauntlet/CLAUDE.md", old_string="a", new_string="b")
    expect_allow(repo, "specifier bash on features", "specifier", "Bash", command=f"cp /tmp/x.feature {feature}")
    expect_deny(repo, "main bash on features", "main", "Bash", command=f"sed -i 's/10/20/' {feature}")
    expect_deny(repo, "hardener writes feature", "hardener", "Write", file_path=feature, content="x")
    if len(MODULES) > 1:
        other = MODULES[1] + "/" + FEATURES_REL + "/mapping.feature"
        expect_allow(repo, "specifier writes the other module's draft", "specifier", "Write", file_path=other, content="x")
        expect_deny(repo, "main writes the other module's feature", "main", "Write", file_path=other, content="x")
        expect_allow(repo, "hardener writes the other module's tests", "hardener", "Write",
                     file_path=MODULES[1] + "/src/test/java/com/example/MappingTest.java", content="x")
        expect_deny(repo, "hardener writes the other module's main", "hardener", "Write",
                    file_path=MODULES[1] + "/src/main/java/com/example/Mapper.java", content="x")
    # --- specification: after the spec commit (approved -> frozen)
    write(repo, feature, "# language: ru\nФункция: Заказ\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "spec: order flow")
    check("frozen after spec commit", git(repo, "rev-list", "--count", "origin/main..HEAD", "--", FEATURES) == "1")
    r = guard(repo, "specifier", "Edit", file_path=feature, old_string="a", new_string="b")
    check("specifier blocked when frozen", r is not None and "frozen" in r, repr(r))
    expect_deny(repo, "specifier new feature file when frozen", "specifier", "Write", file_path=FEATURES + "/other.feature", content="x")
    expect_deny(repo, "main blocked when frozen", "main", "Edit", file_path=feature, old_string="a", new_string="b")
    r = guard(repo, "main", "Bash", command=f"git rm {feature}")
    check("git rm feature when frozen", r is not None and "frozen" in r, repr(r))
    expect_deny(repo, "specifier bash on frozen features", "specifier", "Bash", command=f"cp /tmp/x.feature {feature}")
    if len(MODULES) > 1:
        other = MODULES[1] + "/" + FEATURES_REL + "/mapping.feature"
        r = guard(repo, "specifier", "Write", file_path=other, content="x")
        check("other module's spec frozen by core's spec commit", r is not None and "frozen" in r, repr(r))
        expect_deny(repo, "rm other module's acceptance dir when frozen", "main", "Bash",
                    command=f"rm -rf {MODULES[1]}/src/acceptanceTest")
    expect_deny(repo, "rm -rf src when frozen", "main", "Bash", command=f"rm -rf {M}src/acceptanceTest/resources")
    expect_deny(repo, "git rm -r src/acceptanceTest when frozen", "main", "Bash", command=f"git rm -r {M}src/acceptanceTest")
    expect_deny(repo, "git checkout base -- src when frozen", "main", "Bash", command=f"git checkout origin/main -- {M}src")
    expect_deny(repo, "cd then cp into features when frozen", "specifier", "Bash",
                command=f"cd {M}src/acceptanceTest/resources && cp /tmp/x.feature features/order.feature")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "--detach", "origin/main")
    expect_deny(repo, "detached HEAD at base is frozen", "specifier", "Write", file_path=FEATURES + "/other.feature", content="x")
    git(repo, "checkout", "-q", "claude/feature-x")
    check("back on the branch", git(repo, "rev-parse", "HEAD") == head)
    expect_allow(repo, "rm test dir when frozen", "main", "Bash", command=f"rm -rf {M}src/test/java/com/example/service/domain/Old.java")
    expect_allow(repo, "code edits still fine when frozen", "main", "Edit",
                 file_path=M + "src/main/java/com/example/service/domain/Order.java", old_string="a", new_string="b")
    # --- roles
    expect_allow(repo, "hardener writes unit test", "hardener", "Write", file_path=M + "src/test/java/com/example/OrderTest.java", content="x")
    expect_allow(repo, "hardener writes step defs", "hardener", "Edit", file_path=M + "src/acceptanceTest/java/com/example/Steps.java",
                 old_string="a", new_string="b")
    expect_deny(repo, "hardener writes main", "hardener", "Edit", file_path=M + "src/main/java/com/example/service/domain/Order.java",
                old_string="a", new_string="b")
    expect_deny(repo, "hardener bash on main", "hardener", "Bash", command=f"sed -i 's/a/b/' {M}src/main/java/com/example/service/domain/Order.java")
    expect_allow(repo, "hardener runs pit", "hardener", "Bash", command="./gradlew mutationGate --continue")
    expect_deny(repo, "hardener sed on build script", "hardener", "Bash", command=f"sed -i 's/x/y/' {M}build.gradle.kts")
    expect_deny(repo, "hardener cp into resources", "hardener", "Bash", command=f"cp /tmp/a {M}src/acceptanceTest/resources/x.properties")
    expect_allow(repo, "hardener cp within tests", "hardener", "Bash",
                 command=f"cp {M}src/test/java/com/example/service/domain/OrderTest.java {M}src/test/java/com/example/service/domain/OrderBoundaryTest.java")
    expect_allow(repo, "hardener mkdir tests", "hardener", "Bash", command=f"mkdir -p {M}src/test/java/com/example/service/api")
    expect_deny(repo, "reviewer writes", "reviewer", "Write", file_path=M + "src/main/java/A.java", content="x")
    expect_deny(repo, "reviewer git add", "reviewer", "Bash", command="git add -A")
    expect_deny(repo, "reviewer git stash", "reviewer", "Bash", command="git stash")
    expect_deny(repo, "reviewer redirect", "reviewer", "Bash", command="echo x > notes.txt")
    expect_allow(repo, "reviewer redirect outside project", "reviewer", "Bash", command="echo x > /tmp/notes.txt")
    expect_allow(repo, "reviewer reads diff", "reviewer", "Bash", command=f"git diff $(git merge-base origin/main HEAD) -- {M}src")
    expect_allow(repo, "reviewer runs gauntletFast", "reviewer", "Bash", command="./gradlew gauntletFast --continue")
    expect_allow(repo, "reviewer branch --show-current", "reviewer", "Bash", command="git branch --show-current")
    expect_allow(repo, "reviewer branch -a", "reviewer", "Bash", command="git branch -a")
    expect_allow(repo, "reviewer stash list", "reviewer", "Bash", command="git stash list")
    expect_allow(repo, "reviewer tag -l", "reviewer", "Bash", command="git tag -l 'v*'")
    expect_deny(repo, "reviewer creates branch", "reviewer", "Bash", command="git branch scratch")
    expect_deny(repo, "reviewer tags", "reviewer", "Bash", command="git tag v9")
    expect_deny(repo, "reviewer mkdir", "reviewer", "Bash", command="mkdir notes")
    # --- after the PR is merged (base holds the same feature files) the branch is not frozen any more
    git(repo, "push", "-q", "origin", "HEAD:refs/heads/merged-main")
    props = os.path.join(repo, "gauntlet/config/gauntlet.properties")
    with open(props) as f:
        original = f.read()
    with open(props, "w") as f:
        f.write(original.replace("baseRef=origin/main", "baseRef=origin/merged-main"))
    expect_allow(repo, "merged spec -> specifier may edit again", "specifier", "Edit", file_path=feature, old_string="a", new_string="b")
    with open(props, "w") as f:
        f.write(original)
    # --- spec.approval=pr: no freeze
    props = os.path.join(repo, "gauntlet/config/gauntlet.properties")
    with open(props) as f:
        original = f.read()
    with open(props, "w") as f:
        f.write(original.replace("spec.approval=chat", "spec.approval=pr"))
    expect_allow(repo, "pr mode: specifier edits committed feature", "specifier", "Edit", file_path=feature, old_string="a", new_string="b")
    expect_deny(repo, "pr mode: main still cannot write features", "main", "Edit", file_path=feature, old_string="a", new_string="b")
    with open(props, "w") as f:
        f.write(original)
    # --- guard off (human's admin environment)
    e = {"session_id": "s1", "cwd": repo, "tool_name": "Edit",
         "tool_input": {"file_path": "gauntlet/config/gauntlet.properties", "old_string": "a", "new_string": "b"}}
    r = run_hook(repo, "guard.py", e, env={"GAUNTLET_GUARD": "off"})
    check("GAUNTLET_GUARD=off allows gauntlet edits", r.returncode == 0 and not r.stdout.strip(), r.stdout)
    # --- fail open on garbage
    r = subprocess.run([sys.executable, os.path.join(repo, "gauntlet/hooks/guard.py")], input="not json", cwd=repo,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    check("fails open on malformed input", r.returncode == 0 and not r.stdout.strip())


def stop_tests(repo):
    """Runs on a fresh branch state: HEAD = spec commit, clean tree."""
    def stop(session="s2", fake_exit="0", stop_hook_active=False):
        os.makedirs(os.path.join(repo, M + "build/gauntlet"), exist_ok=True)
        write(repo, M + "build/gauntlet/fake-exit", fake_exit)
        event = {"session_id": session, "cwd": repo, "hook_event_name": "Stop", "stop_hook_active": stop_hook_active}
        return run_hook(repo, "stop_gate.py", event, args=("--task", "gauntletFast", "--max-attempts", "3", "--timeout", "60"))

    def record(session="s2"):
        return run_hook(repo, "stop_gate.py", {"session_id": session, "cwd": repo, "hook_event_name": "SessionStart"},
                        args=("--record-start",))

    def log():
        try:
            with open(os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log")) as f:
                return f.read()
        except OSError:
            return ""

    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-q", "-b", "claude/feature-y")
    record()
    r = stop()
    check("no change -> no run", r.returncode == 0 and "fake gradle" not in log(), r.stderr)
    # spec-only turn: never runs the gate
    write(repo, FEATURES + "/draft.feature", "# language: ru\nФункция: Черновик\n")
    r = stop()
    check("spec-only change -> no run", r.returncode == 0 and "fake gradle" not in log(), r.stderr)
    # code change while the spec is still a draft: run without the acceptance tasks
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order {}\n")
    r = stop()
    check("pending spec -> acceptance excluded", r.returncode == 0 and "-x acceptanceTest -x acceptanceCheck" in log(), log())
    check("pending spec -> note to agent", "human's approval" in r.stdout, r.stdout)
    # commit the spec: acceptance tasks come back
    git(repo, "add", FEATURES)
    git(repo, "commit", "-q", "-m", "spec: draft")
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order { int a; }\n")
    r = stop()
    check("committed spec -> full gauntletFast", r.returncode == 0 and "-x acceptanceTest" not in log(), log())
    # red: blocked, and re-run only when something changed
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order { int b; }\n")
    r = stop(fake_exit="1")
    check("red -> exit 2 with reasons", r.returncode == 2 and "CRAP FAIL" in r.stderr and "attempt 1/3" in r.stderr, r.stderr)
    os.remove(os.path.join(repo, M + "build/gauntlet/fake-exit"))   # fake gradle would now be green if it ran
    r = stop(stop_hook_active=True)
    check("same tree -> cached red, no re-run", r.returncode == 2 and "attempt 2/3" in r.stderr, r.stderr)
    r = stop(stop_hook_active=True)
    check("attempt 3 still blocks", r.returncode == 2 and "attempt 3/3" in r.stderr, r.stderr)
    r = stop(stop_hook_active=True)
    check("attempt limit -> let go with warning", r.returncode == 0 and "still RED" in r.stdout, r.stdout + r.stderr)
    # fix -> green -> cached green
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order { int c; }\n")
    r = stop()
    check("changed tree -> re-run, green", r.returncode == 0 and "fake gradle gauntletFast" in log(), log())
    os.remove(os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log"))
    r = stop()
    check("green cached -> no re-run", r.returncode == 0 and not os.path.exists(os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log")))
    # a later spec-only turn (code unchanged since the last allowed stop) never waits for Gradle
    write(repo, FEATURES + "/second.feature", "# language: ru\nФункция: Вторая\n")
    if os.path.exists(os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log")):
        os.remove(os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log"))
    r = stop(fake_exit="1")
    check("spec-only turn after code turn -> no run", r.returncode == 0
          and not os.path.exists(os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log")), r.stderr)
    # after a green stop the agent's own Gradle runs change nothing: still no re-run
    time.sleep(1.1)
    write(repo, M + "build/test-results/test/TEST-x.xml", "<testsuite/>")
    r = stop(fake_exit="1")
    check("green mark + newer reports -> still no run", r.returncode == 0 and not os.path.exists(
        os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log")), r.stderr)
    # a released RED is remembered: later turns on the same code get a reminder, not silence
    git(repo, "add", FEATURES)
    git(repo, "commit", "-q", "-m", "spec: second (for the red scenario)")
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order { int e; }\n")
    for _ in range(3):
        r = stop(fake_exit="1", stop_hook_active=True)
    r = stop(fake_exit="1", stop_hook_active=True)
    check("red released after 3 attempts (2nd scenario)", r.returncode == 0 and "still RED" in r.stdout, r.stdout + r.stderr)
    r = stop(fake_exit="1")
    check("same red code next turn -> reminder", r.returncode == 0 and "reminder" in r.stdout, r.stdout + r.stderr)
    # ... a spec draft waiting for the human goes first even if the specifier ran Gradle
    write(repo, FEATURES + "/third.feature", "# language: ru\nФункция: Третья\n")
    time.sleep(1.1)
    write(repo, M + "build/test-results/acceptanceTest/TEST-z.xml", "<testsuite/>")
    r = stop(fake_exit="1")
    check("draft spec after released red -> question passes with reminder", r.returncode == 0 and "reminder" in r.stdout
          and "attempt" not in r.stderr, r.stdout + r.stderr)
    git(repo, "add", FEATURES)
    git(repo, "commit", "-q", "-m", "spec: third")
    # ... the agent fixed the environment and ran Gradle itself (newer reports, no draft): re-run, now green
    time.sleep(1.1)
    write(repo, M + "build/test-results/test/TEST-fixed.xml", "<testsuite/>")
    r = stop()
    check("released red + newer reports -> re-run -> green", r.returncode == 0 and "reminder" not in r.stdout
          and "fake gradle gauntletFast" in log(), r.stdout + r.stderr + log())
    # green while the spec was a draft, then the spec gets committed with no code change: acceptance must run now
    write(repo, FEATURES + "/fourth.feature", "# language: ru\nФункция: Четвёртая\n")
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order { int f; }\n")
    r = stop()
    check("draft + code -> green with acceptance excluded", r.returncode == 0 and "-x acceptanceTest" in log(), log())
    git(repo, "add", FEATURES)
    git(repo, "commit", "-q", "-m", "spec: fourth")
    r = stop(fake_exit="1")
    check("pending -> approved with same code re-checks", r.returncode == 2 and "-x acceptanceTest" not in log(), r.stderr + log())
    os.remove(os.path.join(repo, M + "build/gauntlet/fake-exit"))
    # SubagentStop (hardener, from settings.json): stop_hook_active there only says whether the subagent has Stop hooks
    # of its own, so it is always false - retries within the window must still count up to the limit and let go
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order { int g; }\n")
    write(repo, M + "build/gauntlet/fake-exit", "1")
    sub = {"session_id": "s2", "cwd": repo, "hook_event_name": "SubagentStop", "agent_type": "hardener",
           "agent_id": "h1", "stop_hook_active": False}
    sub_args = ("--task", "mutationGate", "--max-attempts", "2", "--timeout", "60")
    r = run_hook(repo, "stop_gate.py", sub, args=sub_args)
    check("subagent red -> blocked, attempt 1/2", r.returncode == 2 and "attempt 1/2" in r.stderr, r.stderr)
    r = run_hook(repo, "stop_gate.py", sub, args=sub_args)
    check("subagent retry counts although stop_hook_active=false", r.returncode == 2 and "attempt 2/2" in r.stderr,
          r.stderr)
    r = run_hook(repo, "stop_gate.py", sub, args=sub_args)
    check("subagent attempt limit -> let go with warning", r.returncode == 0 and "still RED" in r.stdout,
          r.stdout + r.stderr)
    os.remove(os.path.join(repo, M + "build/gauntlet/fake-exit"))
    # switched off by the human
    write(repo, M + "src/main/java/com/example/service/domain/Order.java", "package x; class Order { int d; }\n")
    write(repo, M + "build/gauntlet/fake-exit", "1")
    e = {"session_id": "s2", "cwd": repo, "hook_event_name": "Stop"}
    r = run_hook(repo, "stop_gate.py", e, env={"GAUNTLET_STOP_HOOK": "off"}, args=("--task", "gauntletFast"))
    check("GAUNTLET_STOP_HOOK=off", r.returncode == 0)


def baseline_revert_tests(repo):
    git(repo, "reset", "--hard", "-q", "main")
    git(repo, "clean", "-fdq")
    git(repo, "checkout", "-q", "-b", "claude/baseline-revert")
    source = M + "src/main/java/com/example/service/domain/Order.java"
    log = os.path.join(repo, M + "build/gauntlet/gauntletFast-hook.log")
    write(repo, source, "package x; class Order { int preexisting; }\n")
    run_hook(repo, "stop_gate.py", {"session_id": "s-revert", "cwd": repo, "hook_event_name": "SessionStart"},
             args=("--record-start",))

    def stop():
        write(repo, M + "build/gauntlet/fake-exit", "1")
        event = {"session_id": "s-revert", "cwd": repo, "hook_event_name": "Stop", "stop_hook_active": False}
        return run_hook(repo, "stop_gate.py", event,
                        args=("--task", "gauntletFast", "--max-attempts", "3", "--timeout", "60"))

    r = stop()
    check("untouched pre-existing dirty file -> no run", r.returncode == 0 and not os.path.exists(log), r.stderr)
    git(repo, "checkout", "--", source)
    r = stop()
    check("pre-existing dirty file restored to HEAD -> gate runs", r.returncode == 2 and os.path.exists(log),
          r.stdout + r.stderr)


def multi_module_stop_tests(repo):
    """Two modules: Gradle runs only where something changed; a red module blocks."""
    core, adapter = MODULES[0], MODULES[1]

    def stop(stop_hook_active=False):
        event = {"session_id": "s3", "cwd": repo, "hook_event_name": "Stop", "stop_hook_active": stop_hook_active}
        return run_hook(repo, "stop_gate.py", event, args=("--task", "gauntletFast", "--max-attempts", "3", "--timeout", "60"))

    def log_of(module):
        path = os.path.join(repo, module, "build/gauntlet/gauntletFast-hook.log")
        try:
            with open(path) as f:
                return f.read()
        except OSError:
            return ""

    def clear_logs():
        for m in (core, adapter):
            shutil.rmtree(os.path.join(repo, m, "build"), ignore_errors=True)

    sh(repo, "git", "stash", "-u", "-q")             # leftovers of the previous scenario
    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-q", "-b", "claude/feature-z")
    # the developer's own uncommitted work, present before the session, must not count as the agent's change
    write(repo, core + "/src/main/java/com/example/service/domain/Draft.java", "package x; class Draft {}\n")
    run_hook(repo, "stop_gate.py", {"session_id": "s3", "cwd": repo, "hook_event_name": "SessionStart"}, args=("--record-start",))
    clear_logs()
    write(repo, adapter + "/src/main/java/com/example/service/domain/Mapper.java", "package x; class Mapper {}\n")
    r = stop()
    check("adapter change -> gradle in adapter only (pre-existing dirty core file ignored)", r.returncode == 0
          and "fake gradle" in log_of(adapter) and not log_of(core), r.stderr + log_of(core))
    clear_logs()
    write(repo, core + "/src/main/java/com/example/service/domain/Order.java", "package x; class Order { int z; }\n")
    r = stop()
    check("both changed -> gradle in both", r.returncode == 0 and "fake gradle" in log_of(core) and "fake gradle" in log_of(adapter),
          r.stderr)
    write(repo, adapter + "/build/gauntlet/fake-exit", "1")
    write(repo, adapter + "/src/main/java/com/example/service/domain/Mapper.java", "package x; class Mapper { int a; }\n")
    r = stop()
    check("red adapter blocks", r.returncode == 2 and f"=== {adapter} ===" in r.stderr and "CRAP FAIL" in r.stderr, r.stderr)
    os.remove(os.path.join(repo, adapter, "build/gauntlet/fake-exit"))
    write(repo, adapter + "/src/main/java/com/example/service/domain/Mapper.java", "package x; class Mapper { int b; }\n")
    r = stop(stop_hook_active=True)
    check("fixed adapter -> green", r.returncode == 0, r.stderr)


def cache_isolation_tests(repo):
    """F13a: a red-run cache is judged per module. Core's reports being newer than ADAPTER's log must not
    invalidate the cache while each module's own reports are older than its own log; a genuinely newer report
    in one module must still force a re-run."""
    core, adapter = MODULES[0], MODULES[1]
    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-q", "-b", "claude/cache-iso")
    run_hook(repo, "stop_gate.py", {"session_id": "s4", "cwd": repo, "hook_event_name": "SessionStart"}, args=("--record-start",))

    def stop(active=True):
        ev = {"session_id": "s4", "cwd": repo, "hook_event_name": "Stop", "stop_hook_active": active}
        return run_hook(repo, "stop_gate.py", ev, args=("--task", "gauntletFast", "--max-attempts", "5", "--timeout", "60"))

    def setm(rel, t):
        p = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p):
            write(repo, rel, "<testsuite/>")
        os.utime(p, (t, t))

    write(repo, core + "/src/main/java/com/example/service/domain/Order.java", "package x; class Order { int iso; }\n")
    write(repo, adapter + "/src/main/java/com/example/service/domain/Mapper.java", "package x; class Mapper { int iso; }\n")
    for m in (core, adapter):
        write(repo, m + "/build/gauntlet/fake-exit", "1")
    r = stop(active=False)
    check("F13a setup: both modules red on the first run", r.returncode == 2, r.stderr)
    for m in (core, adapter):
        os.remove(os.path.join(repo, m, "build/gauntlet/fake-exit"))   # a re-run would now be green
    base = time.time()
    core_log = core + "/build/gauntlet/gauntletFast-hook.log"
    setm(core_log, base + 100)
    setm(adapter + "/build/gauntlet/gauntletFast-hook.log", base + 50)
    setm(core + "/build/test-results/test/TEST-c.xml", base + 90)      # newer than adapter's log, older than core's
    setm(adapter + "/build/test-results/test/TEST-a.xml", base + 40)
    r = stop(active=True)
    core_mtime = os.path.getmtime(os.path.join(repo, core_log))
    check("F13a: cross-module reports do not invalidate a fresh per-module cache (cached red, no re-run)",
          r.returncode == 2 and abs(core_mtime - (base + 100)) < 1, f"rc={r.returncode} core_log_mtime={core_mtime} want~{base + 100}")
    setm(adapter + "/build/test-results/test/TEST-a2.xml", base + 200)  # genuinely newer than adapter's own log
    r = stop(active=True)
    check("F13a control: a newer report in one module forces a re-run (now green)", r.returncode == 0, r.stderr)


def continuation_window_tests(repo):
    """Kimi P2: the SubagentStop continuation window must cover the WHOLE multi-module run budget
    (modules * timeout), not a single module's timeout, or a slow two-module mutationGate resets the counter."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("sg_win", os.path.join(repo, "gauntlet", "hooks", "stop_gate.py"))
    sg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sg)
    f = os.path.join(repo, "build", "gauntlet", "window.attempts")
    os.makedirs(os.path.dirname(f), exist_ok=True)

    def attempt(age, timeout, modules):
        with open(f, "w") as fh:
            fh.write(f"1 {time.time() - age}")
        return sg.next_attempt(f, {"hook_event_name": "SubagentStop"}, timeout, modules)

    check("window: single module slow run continues", attempt(3500, 3300, 1) == 2)
    check("window: two modules 4000s continues (not reset)", attempt(4000, 3300, 2) == 2)
    check("window: two modules full 6600s continues", attempt(6600, 3300, 2) == 2)
    check("window: beyond total budget resets", attempt(7300, 3300, 2) == 1)
    check("window: single module beyond its budget resets", attempt(4000, 3300, 1) == 1)


def gate_scope_tests(repo):
    """V6-c: a signal-killed Gradle run reports a negative return code - run_all must call it RED, not green.
    V7-2: affected_modules maps a change to the builds it touches (own dir, module overlay, shared config/tooling
    = every module), and uncommitted_paths splits a git rename into both ends."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("sg_scope", os.path.join(repo, "gauntlet", "hooks", "stop_gate.py"))
    sg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sg)

    orig_gradle = sg.run_gradle
    sg.run_gradle = lambda task, excluded, timeout, module=".": (-15, "log", "killed by signal")
    try:
        code, _ = sg.run_all(["."], "gauntletFast", [], 60)
        check("V6-c: signal-killed gradle (negative code) is red", code == 1, str(code))
        code2, _ = sg.run_all(["core", "adapter"], "gauntletFast", [], 60)
        check("V6-c: negative code red across modules", code2 == 1, str(code2))
    finally:
        sg.run_gradle = orig_gradle

    sg.MODULES = ["core", "adapter"]
    am = sg.affected_modules
    check("V7-2: own module dir touches only that module", am({"core/src/main/java/X.java"}) == ["core"], str(am({"core/src/main/java/X.java"})))
    check("V7-2: other module dir touches that module", am({"adapter/src/main/java/Y.java"}) == ["adapter"])
    check("V7-2: module overlay config touches only that module", am({"gauntlet/config/core/gauntlet.properties"}) == ["core"])
    check("V7-2: shared common config touches every module", set(am({"gauntlet/config/gauntlet.properties"})) == {"core", "adapter"})
    check("V7-2: shared hook touches every module", set(am({"gauntlet/hooks/guard.py"})) == {"core", "adapter"})
    check("V7-2: shared gradle script touches every module", set(am({"gauntlet/gauntlet.gradle"})) == {"core", "adapter"})
    check("V7-2: rename across modules touches both", set(am({"core/src/main/java/X.java", "adapter/src/main/java/X.java"})) == {"core", "adapter"})
    check("V7-2: unrelated path touches no build", am({"README.md"}) == [])
    sg.MODULES = []
    check("V7-2: no modules -> single root build", am({"src/main/java/X.java"}) == ["."])

    orig_bytes = sg.git_bytes
    try:
        sg.git_bytes = lambda *a, **k: b"R  core/src/main/java/X.java -> adapter/src/main/java/X.java\n"
        check("V7-2: rename yields both ends", sg.uncommitted_paths() == {"core/src/main/java/X.java", "adapter/src/main/java/X.java"},
              str(sg.uncommitted_paths()))
        sg.git_bytes = lambda *a, **k: b' M "core/src/main/java/My File.java"\nR  core/a.java -> adapter/a.java\n'
        check("V7-2: quoted path and rename parsed", sg.uncommitted_paths() == {"core/src/main/java/My File.java", "core/a.java", "adapter/a.java"},
              str(sg.uncommitted_paths()))
    finally:
        sg.git_bytes = orig_bytes

    # F7: nested builds (module=core,core/adapter) - the longest prefix owns the change, not the first match
    am = sg.affected_modules
    for order in (["core", "core/adapter"], ["core/adapter", "core"]):
        sg.MODULES = order
        tag = ",".join(order)
        check(f"F7: nested change runs the inner build, not the parent (order {tag})",
              am({"core/adapter/src/main/java/X.java"}) == ["core/adapter"], str(am({"core/adapter/src/main/java/X.java"})))
        check(f"F7: parent-only change runs the parent (order {tag})", am({"core/src/main/java/X.java"}) == ["core"])
        check(f"F7: nested overlay config runs the inner build (order {tag})",
              am({"gauntlet/config/core/adapter/gauntlet.properties"}) == ["core/adapter"])
    sg.MODULES = []

    # F6: a COMMITTED rename across modules yields both ends (--name-status -M), so the source build runs too
    orig_git, orig_uncommitted = sg.git, sg.uncommitted_paths
    try:
        sg.uncommitted_paths = lambda: set()

        def fake_git(*a):
            if a[:2] == ("rev-parse", "HEAD"):
                return "newhead"
            if a and a[0] == "diff":
                return "R100\tcore/src/main/java/X.java\tadapter/src/main/java/X.java\nM\tcore/build.gradle\n"
            return ""
        sg.git = fake_git
        cp = sg.changed_paths("oldhead")
        check("F6: committed rename yields both ends + the modified file",
              cp == {"core/src/main/java/X.java", "adapter/src/main/java/X.java", "core/build.gradle"}, str(cp))
        check("F6: committed rename includes the SOURCE module path", "core/src/main/java/X.java" in cp, str(cp))
    finally:
        sg.git, sg.uncommitted_paths = orig_git, orig_uncommitted

    # F13a: report dirs are per module, so one module's cache is never judged against another's reports
    check("F13a: root module report dirs", sg.module_report_dirs(".") == ["build/test-results", "build/reports"])
    check("F13a: nested module report dirs",
          sg.module_report_dirs("core/adapter") == ["core/adapter/build/test-results", "core/adapter/build/reports"])

    # F13b: a deleted tracked build.gradle stays in the git pathspec (index or HEAD), else its module is skipped
    orig_watched = sg.WATCHED
    tmp = tempfile.mkdtemp(prefix="sg-existing-")
    old_cwd = os.getcwd()
    try:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        subprocess.run(["git", "-C", tmp, "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", tmp, "config", "user.name", "t"], check=True)
        bg = os.path.join(tmp, "build.gradle")
        with open(bg, "w") as f:
            f.write("plugins { java }\n")
        subprocess.run(["git", "-C", tmp, "add", "build.gradle"], check=True)
        subprocess.run(["git", "-C", tmp, "commit", "-qm", "base"], check=True)
        os.chdir(tmp)
        sg.WATCHED = ["build.gradle", "src"]
        os.remove(bg)   # uncommitted deletion: absent on disk, still in the index
        check("F13b: uncommitted-deleted build.gradle stays in pathspec",
              "build.gradle" in sg.existing(["build.gradle", "src"]), str(sg.existing(["build.gradle", "src"])))
        subprocess.run(["git", "-C", tmp, "rm", "-q", "--cached", "build.gradle"], check=True)  # staged deletion: in HEAD, not index
        check("F13b: staged-deleted build.gradle stays via HEAD",
              "build.gradle" in sg.existing(["build.gradle"]), str(sg.existing(["build.gradle"])))
        check("F13b: unknown absent path is dropped", "src" not in sg.existing(["build.gradle", "src"]))
    finally:
        os.chdir(old_cwd)
        sg.WATCHED = orig_watched
        shutil.rmtree(tmp, ignore_errors=True)


def session_start_tests(repo):
    r = subprocess.run(["bash", os.path.join(repo, "gauntlet/hooks/session_start.sh")], cwd=repo, input="{}",
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=repo, CLAUDE_CODE_REMOTE="true", GAUNTLET_DOCKER="off"))
    check("session_start reports active", r.returncode == 0 and "[gauntlet] active" in r.stdout, r.stdout + r.stderr)
    # base branch missing: simulate by pointing baseRef at a branch the remote does not have
    props = os.path.join(repo, "gauntlet/config/gauntlet.properties")
    with open(props) as f:
        original = f.read()
    with open(props, "w") as f:
        f.write(original.replace("baseRef=origin/main", "baseRef=origin/nowhere"))
    r = subprocess.run(["bash", os.path.join(repo, "gauntlet/hooks/session_start.sh")], cwd=repo, input="{}",
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=repo, CLAUDE_CODE_REMOTE="true", GAUNTLET_DOCKER="off"))
    check("session_start warns about missing base", r.returncode == 0 and "WARNING" in r.stdout, r.stdout + r.stderr)
    with open(props, "w") as f:
        f.write(original)
    # shallow clone of the bare origin: the hook must fetch enough history to find the merge base
    root = os.path.dirname(repo)
    shallow = os.path.join(root, "shallow")
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "claude/feature-x",
                    "file://" + os.path.join(root, "origin.git"), shallow], check=True)
    check("clone is shallow and single-branch", git(shallow, "rev-parse", "--is-shallow-repository") == "true"
          and "origin/main" not in git(shallow, "branch", "-r"))
    r = subprocess.run(["bash", os.path.join(shallow, "gauntlet/hooks/session_start.sh")], cwd=shallow, input="{}",
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=shallow, CLAUDE_CODE_REMOTE="true", GAUNTLET_DOCKER="off"))
    check("session_start fetches the base in a shallow clone", "[gauntlet] active" in r.stdout, r.stdout + r.stderr)


def main():
    global M, MODULES, FEATURES
    for MODULES in ([], ["core"], ["core", "adapter"]):
        M = MODULES[0] + "/" if MODULES else ""
        FEATURES = M + FEATURES_REL
        print("layout: " + ("build at the repository root" if not MODULES else "builds in modules " + ", ".join(MODULES)))
        repo = make_repo()
        try:
            guard_tests(repo)
            git(repo, "push", "-q", "origin", "claude/feature-x")
            session_start_tests(repo)
            stop_tests(repo)
            baseline_revert_tests(repo)
            continuation_window_tests(repo)
            gate_scope_tests(repo)
            if len(MODULES) > 1:
                multi_module_stop_tests(repo)
                cache_isolation_tests(repo)
        finally:
            shutil.rmtree(os.path.dirname(repo), ignore_errors=True)
    for f in failures:
        print("FAIL", f)
    print(f"{passed} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

===== END FILE gauntlet/hooks/selftest.py =====

===== BEGIN FILE gauntlet/hooks/session_start.sh =====
#!/usr/bin/env bash
# SessionStart hook (local and cloud sessions).
#  1. In a cloud session make sure the base branch is reachable: the scoped checks need the merge base,
#     and a fresh clone may not have fetched it (or may be shallow).
#  2. Record the working tree so the Stop gate knows what this session changed.
#  3. Print a one-line status that lands in the agent's context.
input=$(cat)
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
props=gauntlet/config/gauntlet.properties
base=$(sed -n 's/^[[:space:]]*baseRef[[:space:]]*=[[:space:]]*//p' "$props" 2>/dev/null | tail -1)
base=${base:-origin/main}
remote=${base%%/*}
branch=${base#*/}

reachable() { git merge-base HEAD "$base" >/dev/null 2>&1; }

# An explicit refspec: a single-branch clone's configured refspec would not create origin/<base>.
fetch_base() { git fetch --quiet "$remote" "+refs/heads/$branch:refs/remotes/$remote/$branch" >/dev/null 2>&1; }

if [ "$CLAUDE_CODE_REMOTE" = "true" ] && [ "$remote" != "$base" ] && ! reachable; then
  fetch_base || true
  if ! reachable && [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
    git fetch --quiet --unshallow "$remote" >/dev/null 2>&1 || git fetch --quiet --deepen=1000 "$remote" >/dev/null 2>&1 || true
    fetch_base || true
  fi
fi

printf '%s' "$input" | python3 gauntlet/hooks/stop_gate.py --record-start

# Tests with a database or a broker run on Testcontainers and fail without Docker. In a cloud session the
# daemon is not running after the container starts (processes are not part of the environment snapshot), and
# `service docker start` fails on ulimit there, so start dockerd directly (it needs root) and wait at most
# about 30 s for it. GAUNTLET_DOCKER=off skips the start (the hooks' selftest sets it).
docker_up() { timeout 5 docker info >/dev/null 2>&1; }
docker_status=unavailable
if docker_up; then
  docker_status=up
elif pgrep -x dockerd >/dev/null 2>&1; then
  docker_status="starting (dockerd is running but not answering yet)"
elif [ "$CLAUDE_CODE_REMOTE" = "true" ] && [ "${GAUNTLET_DOCKER:-on}" != "off" ] && [ "$(id -u)" = 0 ] \
    && command -v dockerd >/dev/null 2>&1 && command -v setsid >/dev/null 2>&1; then
  # setsid + closed stdio: the daemon outlives the hook and does not hold its output open
  setsid nohup dockerd --host=unix:///var/run/docker.sock </dev/null >>/tmp/dockerd.log 2>&1 &
  daemon=$!
  docker_status="not started (see /tmp/dockerd.log)"
  deadline=$((SECONDS + 30))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if docker_up; then docker_status=up; break; fi
    kill -0 "$daemon" 2>/dev/null || break
    sleep 1
  done
fi

if reachable; then
  echo "[gauntlet] active - scope: changed vs $base; guard: ${GAUNTLET_GUARD:-on}; stop hook: ${GAUNTLET_STOP_HOOK:-on}; docker: $docker_status. Process: gauntlet/CLAUDE.md"
else
  echo "[gauntlet] WARNING: cannot find the merge base of HEAD and $base, so the scoped checks will fail. Run 'git fetch $remote +refs/heads/$branch:refs/remotes/$remote/$branch' (after 'git fetch --unshallow $remote' in a shallow clone) or use -Pgauntlet.scope=all."
fi
exit 0

===== END FILE gauntlet/hooks/session_start.sh =====

===== BEGIN FILE gauntlet/hooks/stop_gate.py =====
#!/usr/bin/env python3
"""Stop / SubagentStop gate for the gauntlet (Claude Code hook).

An agent may not finish while the gauntlet is red.

  stop_gate.py --record-start                              # SessionStart: remember the working tree
  stop_gate.py --task gauntletFast [--max-attempts 3]      # Stop / SubagentStop

The gate runs only when the content of the working tree differs from what it was when the session
started (the developer's pre-existing uncommitted work does not count, and committing it changes
nothing) and that exact content has not been verified before - so questions and read-only turns cost
nothing, and a red result is not re-run until something changes. A turn that changed nothing but the
feature files never runs the gate: the specification waits for the human, not for the gauntlet. While
uncommitted feature changes wait for the human's approval in the chat, the acceptance tests are left
out of the run (the agent must be able to stop and ask), but every other check still runs. On red it
exits 2 and feeds the failing lines back to the agent, which keeps working. After --max-attempts
consecutive red stops it lets the agent stop and warns instead, so a session can never loop forever.

Humans can switch it off for a session:  GAUNTLET_STOP_HOOK=off (environment variable at start-up)
Extra Gradle arguments (e.g. --offline):  GAUNTLET_GRADLE_ARGS="--offline"
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

BUILD_FILES = ["src", "gradle", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
               "gradle.properties"]
PROPERTIES = "gauntlet/config/gauntlet.properties"
DEFAULT_FEATURES = "src/acceptanceTest/resources/features"
SPEC_DEPENDENT_TASKS = ["acceptanceTest", "acceptanceCheck"]
# "module" in gauntlet.properties: the Gradle build directories inside a monorepo, comma-separated
# ("" = one build at the repository root). Gradle runs in each changed module; every path below is
# relative to the repository root.
MODULES = []
WATCHED = list(BUILD_FILES) + ["gauntlet"]
REPORT_DIRS = ["build/test-results", "build/reports"]   # newer files here = the agent ran Gradle itself
INTERESTING = re.compile(
    r"^(CRAP FAIL|DUPLICATE|DRY gate: FAILED|INTEGRITY|"
    r"MUTANT (SURVIVED|ERROR)|SURVIVED|NO_COVERAGE|RUN_ERROR|MEMORY_ERROR|NON_VIABLE|mutationGate: |"
    r"\s+\S+#\S+ \w+Mutator\w*$|ACCEPTANCE SKIPPED|WARNING .*mutation sites|"
    r"\[ERROR\]|\[ant:checkstyle\]|> Task .*FAILED|.*\bFAILED$|Execution failed for task|"
    r".*[A-Za-z](Exception|Error)(:|\s|$)|.*expected:?\s|Caused by|Architecture Violation|Rule '|"
    r"\s+at [a-z][\w.$]*\(\w+Test\.java:\d+\)|.*tests? completed, \d+ failed|gauntlet: )")
NOISE = re.compile(r"^(Picked up (JAVA_TOOL_OPTIONS|_JAVA_OPTIONS|JDK_JAVA_OPTIONS)|"
                   r"> Task .*(UP-TO-DATE|NO-SOURCE|SKIPPED)$|\s*$)")
CONTINUATION_MARGIN_S = 10 * 60   # added to the total run budget (modules * timeout): a slow Gradle run must not reset the counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record-start", action="store_true")
    ap.add_argument("--task", default="gauntletFast")
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1500)
    opts = ap.parse_args()
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    os.chdir(project)
    configure_module()
    state = state_dir()
    if state is None:
        return 0
    session = safe(event.get("session_id", "unknown"))
    if opts.record_start:
        start_file = os.path.join(state, session + ".start")
        if not os.path.exists(start_file):
            write(start_file, json.dumps({"head": git("rev-parse", "HEAD"), "tree": tree_fingerprint(),
                                          "dirty": dirty_files()}))
        return 0
    if os.environ.get("GAUNTLET_STOP_HOOK", "").lower() == "off":
        return 0
    return gate(opts, event, state, session)


def gate(opts, event, state, session):
    start_file = os.path.join(state, session + ".start")
    try:
        start = json.loads(read(start_file))
    except ValueError:
        # SessionStart did not record a baseline: judge by uncommitted changes against HEAD instead
        start = {"head": git("rev-parse", "HEAD"), "tree": None}
        write(start_file, json.dumps(start))
    tree = tree_fingerprint()
    if tree == start.get("tree"):
        return 0  # nothing changed in this session
    changed = changed_paths(start.get("head", ""))
    # the developer's own uncommitted work from before the session is not the agent's change (unless touched since)
    baseline = start.get("dirty") or {}
    changed.update(baseline)  # a pre-existing dirty path restored to HEAD is still a change made in this session
    changed = {p for p in changed if baseline.get(p) != file_hash(p)}
    if not changed:
        return 0
    features = features_dirs()
    if all(any(("/" + p).startswith("/" + f + "/") for f in features) for p in changed):
        return 0  # only the spec changed: it waits for the human's approval, not for the gauntlet
    affected = affected_modules(changed)
    if not affected:
        return 0  # nothing inside a guarded build changed
    pending = specs_pending_approval(features)
    excluded = SPEC_DEPENDENT_TASKS if pending else []
    key = session + "-" + safe(event.get("agent_id") or "main")
    # The last-stop mark (code tree without the spec | pending/approved | ok/red) remembers the state in
    # which this agent was last allowed to stop. Same code since then = this turn changed only the spec
    # (or nothing): the question to the human must not wait for Gradle. Exceptions: the last stop was green
    # with the acceptance tests left out and the spec has been committed since (pending -> approved) - check
    # now; the last stop released a RED result - remind the agent, and re-run when it ran Gradle itself since
    # (newer test reports) unless a spec draft is waiting for the human, whose question goes first.
    code_tree = tree_fingerprint(exclude=features)
    state_tag = "pending" if pending else "approved"
    stop_mark = os.path.join(state, key + ".last-stop")
    last = read(stop_mark).split("|")
    if len(last) == 3 and last[0] == code_tree and not (last[1] == "pending" and not pending):
        if last[2] == "ok":
            write(stop_mark, f"{code_tree}|{state_tag}|ok")
            return 0
        if pending or not newer_than(mtime(stop_mark), REPORT_DIRS):
            write(stop_mark, f"{code_tree}|{state_tag}|red")
            print(json.dumps({"systemMessage":
                              f"[gauntlet] reminder: {opts.task} was still RED when you were last allowed to stop and the "
                              f"code has not changed since. The work is NOT done - say so in your report."}))
            return 0
    fingerprint = hashlib.sha256((opts.task + ("|pending" if pending else "") + "|".join(affected) + tree).encode()).hexdigest()
    green_file = os.path.join(state, "last-green-" + safe(opts.task))
    if read(green_file) == fingerprint:
        write(stop_mark, f"{code_tree}|{state_tag}|ok")
        return 0
    attempts_file = os.path.join(state, key + ".attempts")
    red_file = os.path.join(state, "last-red-" + safe(opts.task))
    logs = [log_file(m, opts.task) for m in affected]
    # Judge each module's cache against its OWN reports: a recent Gradle run in module B must not be
    # compared with module A's log (the old min(logs) vs all REPORT_DIRS conflated the two modules).
    cached = read(red_file) == fingerprint and all(os.path.exists(l) for l in logs) \
        and not any(newer_than(mtime(log_file(m, opts.task)), module_report_dirs(m)) for m in affected)
    if cached:
        code, output = 1, "\n".join(read(l) for l in logs)   # nothing changed since the last red run: no re-run
    else:
        code, output = run_all(affected, opts.task, excluded, opts.timeout)
    log_path = ", ".join(logs)
    note = (" Acceptance tests were left out: the changed feature files wait for the human's approval "
            "in the chat (commit them only after the human said yes).") if pending else ""
    if code == 0:
        write(green_file, fingerprint)
        write(stop_mark, f"{code_tree}|{state_tag}|ok")
        remove(attempts_file)
        remove(red_file)
        if pending:
            print(json.dumps({"systemMessage": f"[gauntlet] {opts.task} is green.{note}"}))
        return 0
    write(red_file, fingerprint)
    attempts = next_attempt(attempts_file, event, opts.timeout, len(affected))
    if attempts > opts.max_attempts:
        remove(attempts_file)
        write(stop_mark, f"{code_tree}|{state_tag}|red")
        print(json.dumps({"systemMessage":
                          f"[gauntlet] {opts.task} is still RED after {opts.max_attempts} attempts - stopping anyway. "
                          f"The work is NOT done: say so in your report, with the causes; see {log_path}.{note}"}))
        return 0
    sys.stderr.write(
        f"[gauntlet] ./gradlew {opts.task} is RED (attempt {attempts}/{opts.max_attempts}). You cannot finish "
        f"yet: fix the causes below. Do not weaken tests, specs or checks.{note}\n\n{summarize(output)}\n\n"
        f"Full log: {log_path}\n")
    return 2


def uncommitted_paths():
    paths = set()
    status = git_bytes("status", "--porcelain", "--untracked-files=all", "--", *existing(WATCHED)).decode("utf-8", "replace")
    for line in status.splitlines():  # "XY path", relative to the repository root - do not strip: X may be a space
        path = line[3:].strip()
        if " -> " in path:            # a rename "R  old -> new": both ends changed, either may sit in a guarded build
            paths.update(part.strip().strip('"') for part in path.split(" -> "))
        else:
            paths.add(path.strip('"'))
    return {p for p in paths if p}


def dirty_files():
    """Uncommitted files at session start with their content hash."""
    return {p: file_hash(p) for p in uncommitted_paths()}


def file_hash(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
    except OSError:
        return "<missing>"
    return h.hexdigest()


def changed_paths(start_head):
    """Paths changed in this session: uncommitted changes plus commits made since the session started."""
    paths = uncommitted_paths()
    if start_head and git("rev-parse", "HEAD") != start_head:
        # --name-status -M reports a rename/copy as "R100\told\tnew": a committed move across modules
        # touches BOTH ends, so the source module's build must run too, not only the destination's.
        # Pass WATCHED unfiltered - a committed deletion is gone from disk/index/HEAD, and dropping it
        # from the pathspec would hide the deletion and skip the module's build.
        for line in git("diff", "--name-status", "-M", start_head, "HEAD", "--", *WATCHED).splitlines():
            paths.update(f.strip('"') for f in line.split("\t")[1:] if f.strip())
    return {p for p in paths if p}


def next_attempt(attempts_file, event, timeout, modules=1):
    previous, stamp = 0, 0.0
    raw = read(attempts_file)
    if raw:
        try:
            previous, stamp = int(raw.split()[0]), float(raw.split()[1])
        except (ValueError, IndexError):
            previous = 0
    # Stop: stop_hook_active is set by Claude Code after a blocked stop. SubagentStop: the same field only says
    # whether the subagent has Stop hooks of its own (hooks docs), so its retries are told apart by time.
    # The window must outlast the WHOLE run: run_all runs the task in every affected module sequentially, each
    # up to `timeout`, so the budget is modules * timeout. A run slower than the window would otherwise look
    # like a fresh start and reset the counter to 1 forever (a slow two-module mutationGate must not loop).
    if event.get("hook_event_name") == "Stop" or ("stop_hook_active" in event
                                                  and event.get("hook_event_name") != "SubagentStop"):
        continuing = bool(event.get("stop_hook_active"))
    else:
        continuing = time.time() - stamp < timeout * max(1, modules) + CONTINUATION_MARGIN_S
    attempts = previous + 1 if continuing else 1
    write(attempts_file, f"{attempts} {time.time()}")
    return attempts


def log_file(module, task):
    return os.path.join(module, "build", "gauntlet", f"{task}-hook.log")


def run_all(modules, task, excluded, timeout):
    """Runs the task in every affected module; red if any module is red."""
    worst, outputs = 0, []
    for module in modules:
        code, _, output = run_gradle(task, excluded, timeout, module)
        if code != 0:
            worst = max(worst, code if code > 0 else 1)   # a signal-killed run reports a negative code: red, not green
        outputs.append((f"=== {module} ===\n" if module != "." else "") + output)
    return worst, "\n".join(outputs)


def run_gradle(task, excluded, timeout, module="."):
    gradle = "./gradlew" if os.access(os.path.join(module, "gradlew"), os.X_OK) else "gradle"
    cmd = [gradle, task, "--continue", "--console=plain"]
    for name in excluded:
        cmd += ["-x", name]
    cmd += os.environ.get("GAUNTLET_GRADLE_ARGS", "").split()
    os.makedirs(os.path.dirname(log_file(module, task)), exist_ok=True)
    log_path = log_file(module, task)
    try:
        proc = subprocess.run(cmd, cwd=module, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              timeout=timeout)
        code, output = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as e:
        code = 124
        output = (e.stdout or "") if isinstance(e.stdout, str) else ""
        output += f"\nTIMEOUT: {' '.join(cmd)} did not finish within {timeout}s"
    except FileNotFoundError:
        code, output = 127, f"Cannot run {gradle}: not found"
    write(log_path, output)
    return code, log_path, output


def summarize(output, limit=12000):
    lines = [l for l in output.splitlines() if not NOISE.match(l)]
    picked, seen = [], set()
    for line in lines:
        if INTERESTING.match(line) and line not in seen:
            seen.add(line)
            picked.append(line)
    tail = [l for l in lines[-30:] if l not in seen]
    text = "\n".join(picked[:150]) + "\n\n--- end of the Gradle output ---\n" + "\n".join(tail)
    return text if len(text) <= limit else text[:limit] + "\n[...truncated]"


def tree_fingerprint(exclude=()):
    """Content of every tracked or untracked (not ignored) file under the watched paths - not HEAD."""
    h = hashlib.sha256()
    pathspec = existing(WATCHED) + [f":(exclude){e}" for e in exclude]
    files = git_bytes("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *pathspec)
    for path in sorted(set(p for p in files.decode("utf-8", "replace").split("\0") if p)):
        h.update(path.encode() + b"\0")
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 16), b""):
                    h.update(chunk)
        except OSError:
            h.update(b"<missing>")
    return h.hexdigest()


def properties():
    props = {}
    for line in read(PROPERTIES).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


def configure_module():
    """Point every path at the modules' build directories when the build is not at the repository root."""
    global MODULES, WATCHED, REPORT_DIRS
    MODULES = [m.strip().strip("/") for m in properties().get("module", "").split(",") if m.strip()]
    if MODULES:
        WATCHED = [os.path.join(m, p) for m in MODULES for p in BUILD_FILES] + ["gauntlet"]
        REPORT_DIRS = [os.path.join(m, p) for m in MODULES for p in REPORT_DIRS]


def affected_modules(changed):
    """Which builds a change touches: a module's own directory, its gauntlet/config/<module>/ overlay, or -
    for any shared gauntlet file (common config/, tools/, gauntlet.gradle) - every module, since they all
    read it. Without modules the single build at the repository root is '.'."""
    if not MODULES:
        return ["."]
    touched, shared = set(), False
    for p in changed:
        # Longest (most specific) prefix wins: with module=core,core/adapter a change inside core/adapter
        # belongs to the nested build, not the parent core - the first match depended on module order.
        owner = max((m for m in MODULES if p.startswith(m + "/")), key=len, default=None)
        if owner:
            touched.add(owner)
        elif p.startswith("gauntlet/config/"):
            overlay = max((m for m in MODULES if p.startswith("gauntlet/config/" + m + "/")), key=len, default=None)
            if overlay:
                touched.add(overlay)
            else:
                shared = True   # a common config file: every module reads it
        elif p.startswith("gauntlet/"):
            shared = True       # shared tooling, gradle script or hooks: every module runs it
    return list(MODULES) if shared else [m for m in MODULES if m in touched]


def features_dirs():
    rel = properties().get("acceptance.features", DEFAULT_FEATURES).strip("/")
    return [os.path.join(m, rel) for m in MODULES] if MODULES else [rel]


def specs_pending_approval(features):
    """Feature files that are changed but not committed wait for the human's 'yes' in the chat.
    Once committed on the branch they are the approved specification (and the guard freezes them)."""
    dirs = [f for f in features if os.path.isdir(f)]
    if not dirs:
        return False
    status = git_bytes("status", "--porcelain", "--untracked-files=all", "--", *dirs)
    return bool(status.strip())


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def newer_than(stamp, dirs):
    """Any file under dirs modified after stamp."""
    for d in dirs:
        for root, _, files in os.walk(d):
            for name in files:
                if mtime(os.path.join(root, name)) > stamp:
                    return True
    return False


def module_report_dirs(module):
    """The Gradle report directories of ONE module ('.' = the repository root), so its red-run cache is
    judged against its own reports rather than every module's combined REPORT_DIRS."""
    base = "" if module == "." else module + "/"
    return [base + "build/test-results", base + "build/reports"]


def state_dir():
    path = git("rev-parse", "--git-path", "gauntlet-hook")
    if not path:
        return None
    os.makedirs(path, exist_ok=True)
    return path


def git(*args):
    return git_bytes(*args).decode("utf-8", "replace").strip()


def git_bytes(*args):
    try:
        return subprocess.run(["git", "-c", "core.quotePath=false", *args], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL).stdout
    except OSError:
        return b""


def existing(paths):
    """Pathspec for the read-only git queries. Keep a watched path that exists on disk OR is still known
    to git (index or HEAD): a tracked build.gradle the agent deleted is absent on disk but must stay in
    scope, otherwise its deletion is invisible and the module's build is skipped. A deleted directory
    stays while git tracks files under it. Fall back to '.' only when nothing is known."""
    kept = [p for p in paths if os.path.exists(p)]
    absent = [p for p in paths if not os.path.exists(p)]
    if absent:
        known = set(git("ls-files", "--", *absent).splitlines())
        known.update(git("ls-tree", "-r", "--name-only", "HEAD", "--", *absent).splitlines())
        kept += [p for p in absent if p in known or any(k.startswith(p + "/") for k in known)]
    return kept or ["."]


def safe(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))[:80]


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())

===== END FILE gauntlet/hooks/stop_gate.py =====

===== BEGIN FILE gauntlet/install.sh =====
#!/usr/bin/env bash
# Wires the gauntlet into the project it lives in. Run from the project root:  bash gauntlet/install.sh
#
#   gauntlet/claude/settings.json  -> .claude/settings.json           (hooks + permissions; merged if one exists)
#   gauntlet/claude/agents/*.md    -> .claude/agents/                 (roles; Claude Code only looks there)
#   gauntlet/ci/gauntlet.yml       -> .github/workflows/gauntlet.yml  (CI gate for pull requests)
#   CLAUDE.md                      += @gauntlet/CLAUDE.md             (process + rules, loaded every session)
#
# Existing files: settings.json is merged in place (the gauntlet's own hooks are refreshed to this version,
# new ones appended, user hooks left untouched, permissions united, disableAllHooks pinned to false); an
# existing role file or workflow is left as it is and reported. Nothing is written
# outside these paths. The sources under gauntlet/claude and gauntlet/ci are removed afterwards so nothing
# exists twice. Run this LAST in the install session: from the moment .claude/settings.json holds the hooks
# they are live and gauntlet/ becomes read-only for agents.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# A monorepo lists its guarded builds in gauntlet/config/gauntlet.properties (module=core,adapter); otherwise the
# build is at the root (see gauntlet/INSTALL.md, step 0).
modules=$(sed -n 's#^[[:space:]]*module[[:space:]]*=[[:space:]]*##p' gauntlet/config/gauntlet.properties 2>/dev/null | tail -1 | tr ',' ' ')
[ -f build.gradle.kts ] || [ -f build.gradle ] || [ -n "$modules" ] ||
  { echo "not a Gradle project root (and no module= in gauntlet/config/gauntlet.properties): $ROOT" >&2; exit 1; }
[ -d gauntlet/claude ] || { echo "gauntlet/claude/ is missing - already installed?" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required (hooks and the settings merge)" >&2; exit 1; }
for dir in ${modules:-.}; do
  grep -q "gauntlet/gauntlet.gradle" "$dir/build.gradle.kts" "$dir/build.gradle" 2>/dev/null ||
    echo "  !! $dir/build.gradle(.kts) does not apply gauntlet/gauntlet.gradle yet - see gauntlet/INSTALL.md step 4"
done

# --- preflight: refuse before touching anything if the existing settings cannot be merged
if [ -f .claude/settings.json ] && ! python3 -c 'import json,sys; json.load(open(".claude/settings.json"))' 2>/dev/null; then
  echo ".claude/settings.json exists but is not valid JSON - fix it first, then run the installer again" >&2
  exit 1
fi

echo "Installing the gauntlet into $ROOT"
mkdir -p .claude/agents
# stop_gate runs its task in every affected module sequentially, each up to the inner --timeout in the
# command, so the outer hook timeout must outlive modules * inner + margin. Count the guarded builds.
mod_count=$(printf '%s' "$modules" | wc -w | tr -d ' ')
case "$mod_count" in ''|*[!0-9]*) mod_count=1 ;; esac
[ "$mod_count" -ge 1 ] || mod_count=1
existed=0; [ -f .claude/settings.json ] && existed=1
GAUNTLET_MOD_COUNT="$mod_count" GAUNTLET_EXISTED="$existed" python3 - <<'PY'
import json, os, re, shlex

INTERPRETERS = {"python", "python3", "bash", "sh", "zsh", "dash", "ksh"}

def gkey(cmd):
    # Identify a gauntlet hook by the script it LAUNCHES, not by a path merely mentioned somewhere in the
    # command. The gauntlet runs `python3 "<...>/gauntlet/hooks/X.py" [flags]` / `bash "<...>/X.sh"`: the
    # script is the interpreter's first operand. A user hook like `sha256sum .../gauntlet/hooks/guard.py` or
    # `python3 -c '... guard.py ...'` only MENTIONS the path - treating it as the gauntlet's own hook would
    # overwrite the user's command on upgrade. Matching the script (not the whole command) still lets the
    # version-specific --timeout/--max-attempts flags change without duplicating the hook.
    try:
        tokens = shlex.split(cmd or "")
    except ValueError:
        return None
    if not tokens or os.path.basename(tokens[0]) not in INTERPRETERS:
        return None
    if len(tokens) < 2 or tokens[1].startswith("-"):
        return None   # interpreter flags / inline code (-c, -m): not a plain hook-script launch
    script = tokens[1].replace("\\", "/")
    m = re.fullmatch(r"(?:.*/)?gauntlet/hooks/([A-Za-z0-9_.-]+)", script)
    if not m:
        return None
    managed = "gauntlet/hooks/" + m.group(1)
    root_script = os.path.join(os.getcwd(), managed).replace(os.sep, "/")
    if script not in (managed, "$CLAUDE_PROJECT_DIR/" + managed, "${CLAUDE_PROJECT_DIR}/" + managed, root_script):
        return None
    if any(t.startswith((";", "|", "&", ">", "<")) or re.match(r"^\d+[<>]", t) for t in tokens[2:]):
        return None   # a compound user command (hook && auditor, redirection) is not ours to rewrite
    return m.group(1)

def scale(event, hook, n):
    m = re.search(r"--timeout\s+(\d+)", hook.get("command", ""))
    inner = int(m.group(1)) if m else 0
    if event == "Stop":
        hook["timeout"] = max(1800, n * inner + 100)
    elif event == "SubagentStop":
        hook["timeout"] = max(7200, n * inner + 600)

n = max(1, int(os.environ.get("GAUNTLET_MOD_COUNT", "1")))
with open("gauntlet/claude/settings.json") as f:
    ours = json.load(f)
if os.environ.get("GAUNTLET_EXISTED") == "1":
    with open(".claude/settings.json") as f:
        current = json.load(f)
else:
    current = {"hooks": {}, "permissions": {}}
current["disableAllHooks"] = False
hooks = current.setdefault("hooks", {})
for event, groups in ours["hooks"].items():
    existing = hooks.setdefault(event, [])
    our_by_key = {}
    for g in groups:
        for h in g.get("hooks", []):
            k = gkey(h.get("command"))
            if k:
                our_by_key[k] = (g, h)
    present = set()
    moves = []
    for g in list(existing):                # refresh the gauntlet's own hooks; user hooks untouched
        for h in list(g.get("hooks", [])):
            k = gkey(h.get("command"))
            if k in our_by_key:
                og, oh = our_by_key[k]
                h["command"] = oh["command"]
                h["type"] = oh.get("type", "command")
                for field in ("timeout", "statusMessage"):
                    if field in oh:
                        h[field] = oh[field]
                    else:
                        h.pop(field, None)
                own_group = all(gkey(hh.get("command")) in our_by_key for hh in g.get("hooks", []))
                if own_group:
                    if "matcher" in og:
                        g["matcher"] = og["matcher"]
                    else:
                        g.pop("matcher", None)
                elif g.get("matcher") != og.get("matcher"):
                    moves.append((g, h, og))
                present.add(k)
    for g, h, og in moves:
        # A broad user matcher must stay on the user's group, but must not broaden the gauntlet hook's scope.
        g["hooks"] = [hh for hh in g.get("hooks", []) if hh is not h]
        ng = {key: json.loads(json.dumps(value)) for key, value in og.items() if key != "hooks"}
        ng["hooks"] = [h]
        existing.append(ng)
    for g in groups:                        # append gauntlet groups not already present
        if any(gkey(h.get("command")) in present for h in g.get("hooks", [])):
            continue
        ng = json.loads(json.dumps(g))
        existing.append(ng)
        for h in ng.get("hooks", []):
            k = gkey(h.get("command"))
            if k:
                present.add(k)
    for g in existing:                      # scale the outer timeout of the gauntlet's Gradle hooks by modules
        for h in g.get("hooks", []):
            if gkey(h.get("command")) in our_by_key:
                scale(event, h, n)
perms = current.setdefault("permissions", {})
for key in ("allow", "deny"):
    merged = list(perms.get(key, []))
    merged += [rule for rule in ours["permissions"].get(key, []) if rule not in merged]
    perms[key] = merged
with open(".claude/settings.json", "w") as f:
    json.dump(current, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY
if [ "$existed" = 1 ]; then
  echo "  merged .claude/settings.json (gauntlet hooks refreshed, permissions united, disableAllHooks=false)"
else
  echo "  added  .claude/settings.json"
fi
for role in gauntlet/claude/agents/*.md; do
  dst=".claude/agents/$(basename "$role")"
  if [ -e "$dst" ]; then
    echo "  kept   $dst (exists; the gauntlet version stays in git history of gauntlet/claude/agents/)"
  else
    cp "$role" "$dst"; echo "  added  $dst"
  fi
done
if [ -f gauntlet/ci/gauntlet.yml ]; then
  if [ -e .github/workflows/gauntlet.yml ]; then
    echo "  kept   .github/workflows/gauntlet.yml (exists)"
  else
    mkdir -p .github/workflows
    cp gauntlet/ci/gauntlet.yml .github/workflows/gauntlet.yml; echo "  added  .github/workflows/gauntlet.yml"
  fi
fi
if [ -f CLAUDE.md ]; then
  if grep -q "^@gauntlet/CLAUDE.md" CLAUDE.md; then
    echo "  kept   CLAUDE.md (already imports gauntlet/CLAUDE.md)"
  else
    printf '\n@gauntlet/CLAUDE.md\n' >> CLAUDE.md
    echo "  added  @gauntlet/CLAUDE.md to CLAUDE.md"
  fi
else
  printf '@gauntlet/CLAUDE.md\n' > CLAUDE.md
  echo "  added  CLAUDE.md"
fi
chmod +x gauntlet/hooks/*.py gauntlet/hooks/*.sh gauntlet/install.sh 2>/dev/null || true
rm -rf gauntlet/claude gauntlet/ci
echo "  moved  gauntlet/claude and gauntlet/ci into place (sources removed)"

cat <<'NEXT'

Done. The hooks are live from now on: gauntlet/, .claude/ and CLAUDE.md are read-only for agents.
Remaining steps (gauntlet/INSTALL.md): `git add -A`, commit, push, open the PR.
NEXT

===== END FILE gauntlet/install.sh =====

===== BEGIN FILE gauntlet/templates/acceptanceTest/java/com/example/service/acceptance/CucumberSpringConfiguration.java =====
package com.example.service.acceptance;

import io.cucumber.spring.CucumberContextConfiguration;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * One Spring context for all scenarios (cucumber-spring). Put step definitions in this package
 * (acceptance.glue in gauntlet/config/gauntlet.properties). Add Testcontainers here if the service
 * needs a real database or broker, and clean state in a @Before hook so scenarios stay independent.
 */
@CucumberContextConfiguration
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
public class CucumberSpringConfiguration {
}

===== END FILE gauntlet/templates/acceptanceTest/java/com/example/service/acceptance/CucumberSpringConfiguration.java =====

===== BEGIN FILE gauntlet/templates/acceptanceTest/resources/features/example_discount.feature =====
# language: ru
# ПРИМЕР формата спецификации - замените своей фичей. Все значимые значения вынесены в «Примеры»:
# gherkinMutation меняет их по одному и ждёт, что сценарий упадёт. Значения подобраны так, чтобы
# изменение любого из них меняло исход: если столбец не влияет на результат, его мутант выживает
# (эквивалентный мутант) - такой столбец убирают или правило закрепляют иначе.
Функция: Расчёт скидки по заказу

  Структура сценария: Фиксированная скидка уменьшает сумму заказа
    Дано клиент со скидкой <скидка> руб.
    Когда клиент оформляет заказ на сумму <сумма> руб.
    Тогда итог заказа составляет <итог> руб.

    Примеры:
      | скидка | сумма | итог |
      | 100    | 10000 | 9900 |
      | 300    | 2500  | 2200 |
      | 50     | 400   | 350  |

===== END FILE gauntlet/templates/acceptanceTest/resources/features/example_discount.feature =====

===== BEGIN FILE gauntlet/tools/CrapGate.java =====
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * CRAP gate for Java, fed by a JaCoCo XML report.
 *
 * <p>CRAP = CC^2 * (1 - coverage)^3 + CC, the formula used by unclebob/crap4java.
 * CC is the JaCoCo COMPLEXITY counter of the method, coverage is its INSTRUCTION coverage.
 * A fully covered method scores exactly its cyclomatic complexity; an uncovered complex
 * method explodes. So the gate forces either simple code or tested code - ideally both.
 *
 * <pre>
 * java CrapGate.java --report build/reports/jacoco/test/jacocoTestReport.xml --threshold 8
 *      [--only src/main/java/a/B.java,src/main/java/a/C.java]   (scope: only these files)
 *      [--allowlist gauntlet/config/crap-allowlist.txt]           (human-approved exceptions)
 *      [--exclude *Application,*MapperImpl]                        (class-name globs)
 *      [--top 15]
 * </pre>
 * Exit codes: 0 = within threshold, 1 = threshold exceeded, 2 = usage or input error.
 */
public class CrapGate {

    record Score(String className, String method, int line, String sourcePath,
                 int complexity, double coverage, double crap, boolean allowed) {

        String display() {
            String file = sourcePath.substring(sourcePath.lastIndexOf('/') + 1);
            return className + "#" + method + " (" + file + ":" + line + ")";
        }
    }

    public static void main(String[] args) {
        System.exit(run(args, utf8(FileDescriptor.out), utf8(FileDescriptor.err)));
    }

    static PrintStream utf8(FileDescriptor fd) {
        return new PrintStream(new FileOutputStream(fd), true, StandardCharsets.UTF_8);
    }

    static int run(String[] args, PrintStream out, PrintStream err) {
        Args a;
        try {
            a = Args.parse(args);
        } catch (IllegalArgumentException e) {
            err.println("CrapGate: " + e.getMessage());
            err.println("usage: java CrapGate.java --report <jacoco.xml> [--threshold 8] [--only f1,f2]"
                    + " [--allowlist file] [--exclude globs] [--top N]");
            return 2;
        }
        if (a.only != null && a.only.isEmpty()) {
            out.println("CRAP gate: no changed Java sources in scope - nothing to check.");
            return 0;
        }
        File report = new File(a.report);
        if (!report.isFile()) {
            err.println("CrapGate: JaCoCo XML report not found: " + a.report
                    + " (run the tests with JaCoCo first, e.g. ./gradlew jacocoTestReport)");
            return 2;
        }
        List<Score> scores;
        try {
            scores = score(parse(report), a);
        } catch (Exception e) {
            err.println("CrapGate: cannot read " + a.report + ": " + e);
            return 2;
        }
        return report(scores, a, out);
    }

    static Document parse(File xml) throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setValidating(false);
        f.setNamespaceAware(false);
        f.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        f.setFeature("http://xml.org/sax/features/external-general-entities", false);
        DocumentBuilder b = f.newDocumentBuilder();
        return b.parse(xml);
    }

    static List<Score> score(Document doc, Args a) {
        List<Pattern> excludes = globs(a.excludes);
        Set<String> allow = a.allow;
        Map<String, Set<String>> declared = a.only == null ? Map.of() : declaredTypes(a.only);
        List<Score> result = new ArrayList<>();
        boolean missingSource = false;
        NodeList packages = doc.getElementsByTagName("package");
        for (int p = 0; p < packages.getLength(); p++) {
            Element pkg = (Element) packages.item(p);
            for (Element cls : children(pkg, "class")) {
                String internal = cls.getAttribute("name");
                String className = internal.replace('/', '.');
                String sourceFile = cls.getAttribute("sourcefilename");
                String pkgPath = pkg.getAttribute("name");
                if (sourceFile.isEmpty()) {
                    missingSource = true;
                    String resolved = resolveSource(declared, pkgPath, outerSimpleName(className));
                    if (a.only != null && resolved == null) {
                        continue;   // this report class is not declared by any changed source file
                    }
                    sourceFile = resolved != null ? resolved : outerSimpleName(className) + ".java";
                }
                String sourcePath = (pkgPath.isEmpty() ? "" : pkgPath + "/") + sourceFile;
                if (!inScope(sourcePath, declared, a.only)) {
                    continue;
                }
                if (matchesAny(outerSimpleName(className), excludes)) {
                    continue;
                }
                List<Element> methods = children(cls, "method");
                Map<String, Integer> nameCounts = new HashMap<>();
                Map<String, List<String>> nameDescs = new HashMap<>();
                Map<String, Integer> displayCounts = new HashMap<>();
                Map<String, List<String>> displaySigs = new HashMap<>();
                for (Element m : methods) {
                    String n = m.getAttribute("name");
                    String d = prettyMethod(n);
                    nameCounts.merge(n, 1, Integer::sum);
                    nameDescs.computeIfAbsent(n, k -> new ArrayList<>()).add(n + m.getAttribute("desc"));
                    displayCounts.merge(d, 1, Integer::sum);
                    displaySigs.computeIfAbsent(d, k -> new ArrayList<>()).add(n + m.getAttribute("desc"));
                }
                for (Element m : methods) {
                    String name = m.getAttribute("name");
                    String desc = m.getAttribute("desc");
                    int cc = counterTotal(m, "COMPLEXITY");
                    int[] instr = counter(m, "INSTRUCTION");
                    int total = instr[0] + instr[1];
                    double coverage = total == 0 ? 1.0 : (double) instr[1] / total;
                    double crap = crap(cc, coverage);
                    int line = m.hasAttribute("line") ? Integer.parseInt(m.getAttribute("line")) : 0;
                    String methodName = prettyMethod(name);
                    // A signature entry Class#method(desc) exempts exactly one overload. A name-only entry
                    // exempts only when the key it matched is unambiguous. Uniqueness is checked for BOTH the
                    // raw JVM name (overloads) and the display name: two lambdas lambda$rules$0/1 collapse to
                    // one display "rules::lambda", so a display-name entry must not exempt both silently.
                    boolean rawMatch = allow.contains(className + "#" + name);
                    boolean dispMatch = allow.contains(className + "#" + methodName);
                    boolean allowed = allow.contains(className + "#*")
                            || allow.contains(className + "#" + name + desc)
                            || (rawMatch && nameCounts.getOrDefault(name, 0) == 1)
                            || (dispMatch && displayCounts.getOrDefault(methodName, 0) == 1);
                    if (rawMatch && nameCounts.getOrDefault(name, 0) > 1) {
                        a.ambiguous.add("CRAP allowlist: '" + className + "#" + name + "' matches " + nameCounts.get(name)
                                + " overloads " + nameDescs.get(name) + " - it exempts nothing; specify a signature"
                                + " (e.g. " + className + "#" + nameDescs.get(name).get(0) + ").");
                    }
                    if (dispMatch && displayCounts.getOrDefault(methodName, 0) > 1) {
                        a.ambiguous.add("CRAP allowlist: '" + className + "#" + methodName + "' matches "
                                + displayCounts.get(methodName) + " methods sharing that display name "
                                + displaySigs.get(methodName) + " (e.g. sibling lambdas) - it exempts nothing;"
                                + " specify a signature (e.g. " + className + "#" + displaySigs.get(methodName).get(0) + ").");
                    }
                    result.add(new Score(className, methodName, line, sourcePath, cc, coverage, crap, allowed));
                }
            }
        }
        if (a.only != null && !a.only.isEmpty() && result.isEmpty() && missingSource) {
            a.ambiguous.add("CRAP gate: the JaCoCo report carries no source filenames (debug=false) and the changed-file"
                    + " scope analysed 0 methods. A zero-method pass is not proof the changed code is simple: rebuild the"
                    + " report with debug info, or verify acceptance.features/changed sources resolve to the right files.");
        }
        result.sort(Comparator.comparingDouble(Score::crap).reversed()
                .thenComparing(Score::className).thenComparingInt(Score::line));
        return result;
    }

    /** Index only top-level types: a nested Selection.Legacy must not bind an unrelated top-level Legacy. */
    static Map<String, Set<String>> declaredTypes(Set<String> only) {
        Map<String, Set<String>> map = new LinkedHashMap<>();
        Pattern type = Pattern.compile("(?<![\\p{javaJavaIdentifierPart}$])(?:class|interface|enum|record)\\s+"
                + "([\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}]*)");
        Pattern pkgPattern = Pattern.compile("(?<![\\p{javaJavaIdentifierPart}$])package\\s+"
                + "([\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}]*(?:\\s*\\.\\s*"
                + "[\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}]*)*)\\s*;");
        for (String f : only) {
            Path p = Path.of(f);
            if (!Files.isRegularFile(p)) {
                continue;
            }
            String norm = f.replace('\\', '/');
            try {
                String topLevel = topLevelSource(Files.readString(p, StandardCharsets.UTF_8));
                Matcher m = type.matcher(topLevel);
                Set<String> names = new HashSet<>();
                while (m.find()) {
                    names.add(m.group(1));
                }
                Matcher pkg = pkgPattern.matcher(topLevel);
                String packageName = pkg.find() ? pkg.group(1).replaceAll("\\s+", "") : "";
                String packagePath = packageName.replace('.', '/');
                String fileName = norm.substring(norm.lastIndexOf('/') + 1);
                String rel = (packagePath.isEmpty() ? "" : packagePath + "/") + fileName;
                map.put(rel, names);
            } catch (IOException unreadable) {
                // unreadable source: cannot bind, leave it out of the index
            }
        }
        return map;
    }

    static String topLevelSource(String source) {
        StringBuilder code = new StringBuilder(source.length());
        String state = "code";
        int depth = 0;
        int i = 0;
        while (i < source.length()) {
            char c = source.charAt(i);
            char next = i + 1 < source.length() ? source.charAt(i + 1) : '\0';
            if (state.equals("lineComment")) {
                appendMasked(code, c);
                if (c == '\n') {
                    state = "code";
                }
                i++;
                continue;
            }
            if (state.equals("blockComment")) {
                if (c == '*' && next == '/') {
                    code.append("  ");
                    i += 2;
                    state = "code";
                } else {
                    appendMasked(code, c);
                    i++;
                }
                continue;
            }
            if (state.equals("textBlock")) {
                if (c == '\\' && i + 1 < source.length()) {
                    appendMasked(code, c);
                    appendMasked(code, next);
                    i += 2;
                } else if (c == '"' && next == '"' && i + 2 < source.length() && source.charAt(i + 2) == '"') {
                    code.append("   ");
                    i += 3;
                    state = "code";
                } else {
                    appendMasked(code, c);
                    i++;
                }
                continue;
            }
            if (state.equals("string") || state.equals("character")) {
                char delimiter = state.equals("string") ? '"' : '\'';
                if (c == '\\' && i + 1 < source.length()) {
                    appendMasked(code, c);
                    appendMasked(code, next);
                    i += 2;
                } else {
                    appendMasked(code, c);
                    if (c == delimiter) {
                        state = "code";
                    }
                    i++;
                }
                continue;
            }
            if (c == '/' && next == '/') {
                code.append("  ");
                i += 2;
                state = "lineComment";
            } else if (c == '/' && next == '*') {
                code.append("  ");
                i += 2;
                state = "blockComment";
            } else if (c == '"' && next == '"' && i + 2 < source.length() && source.charAt(i + 2) == '"') {
                code.append("   ");
                i += 3;
                state = "textBlock";
            } else if (c == '"') {
                code.append(' ');
                i++;
                state = "string";
            } else if (c == '\'') {
                code.append(' ');
                i++;
                state = "character";
            } else {
                if (c == '{') {
                    depth++;
                } else if (c == '}') {
                    depth = Math.max(0, depth - 1);
                }
                code.append(depth == 0 ? c : (c == '\n' ? '\n' : ' '));
                i++;
            }
        }
        return code.toString();
    }

    static void appendMasked(StringBuilder target, char c) {
        target.append(c == '\n' ? '\n' : ' ');
    }

    static String resolveSource(Map<String, Set<String>> declared, String pkgPath, String outerName) {
        String found = null;
        for (Map.Entry<String, Set<String>> e : declared.entrySet()) {
            String rel = e.getKey();
            int slash = rel.lastIndexOf('/');
            String parent = slash < 0 ? "" : rel.substring(0, slash);
            if (!parent.equals(pkgPath) || !e.getValue().contains(outerName)) {
                continue;
            }
            String base = rel.substring(slash + 1);
            if (found != null && !found.equals(base)) {
                return null;
            }
            found = base;
        }
        return found;
    }

    static double crap(int complexity, double coverage) {
        double uncovered = 1.0 - coverage;
        return complexity * complexity * uncovered * uncovered * uncovered + complexity;
    }

    static int report(List<Score> scores, Args a, PrintStream out) {
        List<Score> failing = new ArrayList<>();
        for (Score s : scores) {
            if (s.crap() > a.threshold && !s.allowed()) {
                failing.add(s);
            }
        }
        String scope = a.only == null ? "all sources" : a.only.size() + " changed file(s)";
        out.printf(Locale.ROOT, "CRAP gate: threshold %.1f, scope: %s, %d method(s) analysed%n",
                a.threshold, scope, scores.size());
        int shown = 0;
        if (!scores.isEmpty()) {
            out.printf(Locale.ROOT, "%-10s %6s %4s %7s  %s%n", "", "CRAP", "CC", "COVER", "METHOD");
        }
        for (Score s : scores) {
            boolean fail = s.crap() > a.threshold && !s.allowed();
            if (shown >= a.top && !fail) {
                continue;
            }
            String mark = fail ? "CRAP FAIL" : (s.allowed() && s.crap() > a.threshold ? "CRAP ALLOW" : "");
            out.printf(Locale.ROOT, "%-10s %6.1f %4d %6.1f%%  %s%n", mark, s.crap(), s.complexity(),
                    s.coverage() * 100.0, s.display());
            shown++;
        }
        for (String note : a.ambiguous) {
            out.println(note);
        }
        if (failing.isEmpty()) {
            out.println("CRAP gate: OK");
            return 0;
        }
        out.printf(Locale.ROOT, "CRAP gate: FAILED - %d method(s) above %.1f.%n", failing.size(), a.threshold);
        out.println("  CRAP = CC^2 * (1 - coverage)^3 + CC. Split methods that mix duties (an extracted");
        out.println("  method must own its inputs - no boolean flags the caller already knew) and cover");
        out.println("  the remaining branches with focused unit tests. Exceptions are human-owned:");
        out.println("  gauntlet/config/crap-allowlist.txt");
        return 1;
    }

    static boolean inScope(String sourcePath, Map<String, Set<String>> declared, Set<String> only) {
        return only == null || declared.containsKey(sourcePath) || inScope(sourcePath, only);
    }

    static boolean inScope(String sourcePath, Set<String> only) {
        if (only == null) {
            return true;
        }
        for (String f : only) {
            String norm = f.replace('\\', '/');
            // changed sources are module-relative (src/main/java/<package>/<File>.java); compare the exact
            // package-relative path, not a suffix - otherwise com/example/prices/Catalog.java would also
            // pull in an unrelated, unchanged prices/Catalog.java.
            int root = norm.indexOf("src/main/java/");
            if (root >= 0) {
                norm = norm.substring(root + "src/main/java/".length());
            }
            if (norm.equals(sourcePath)) {
                return true;
            }
        }
        return false;
    }

    static String outerSimpleName(String className) {
        String simple = className.substring(className.lastIndexOf('.') + 1);
        int dollar = simple.indexOf('$');
        return dollar < 0 ? simple : simple.substring(0, dollar);
    }

    static String prettyMethod(String jvmName) {
        if (jvmName.startsWith("lambda$")) {
            String[] parts = jvmName.split("\\$");
            return (parts.length > 1 ? parts[1] : "lambda") + "::lambda";
        }
        return jvmName;
    }

    static List<Element> children(Element parent, String tag) {
        List<Element> list = new ArrayList<>();
        for (Node n = parent.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element e && e.getTagName().equals(tag)) {
                list.add(e);
            }
        }
        return list;
    }

    static int[] counter(Element method, String type) {
        for (Element c : children(method, "counter")) {
            if (c.getAttribute("type").equals(type)) {
                return new int[] {Integer.parseInt(c.getAttribute("missed")), Integer.parseInt(c.getAttribute("covered"))};
            }
        }
        return new int[] {0, 0};
    }

    static int counterTotal(Element method, String type) {
        int[] c = counter(method, type);
        return Math.max(1, c[0] + c[1]);
    }

    static List<Pattern> globs(List<String> globs) {
        List<Pattern> list = new ArrayList<>();
        for (String g : globs) {
            String regex = Arrays.stream(g.trim().split("\\*", -1)).map(Pattern::quote)
                    .reduce((x, y) -> x + ".*" + y).orElse("");
            list.add(Pattern.compile(regex));
        }
        return list;
    }

    static boolean matchesAny(String name, List<Pattern> patterns) {
        for (Pattern p : patterns) {
            if (p.matcher(name).matches()) {
                return true;
            }
        }
        return false;
    }

    static final class Args {
        String report;
        double threshold = 8.0;
        Set<String> only;
        Set<String> allow = new HashSet<>();
        List<String> excludes = new ArrayList<>();
        int top = 15;
        Set<String> ambiguous = new LinkedHashSet<>();

        static Args parse(String[] args) {
            Args a = new Args();
            for (int i = 0; i < args.length; i++) {
                String key = args[i];
                if (i + 1 >= args.length) {
                    throw new IllegalArgumentException("missing value for " + key);
                }
                String value = args[++i];
                switch (key) {
                    case "--report" -> a.report = value;
                    case "--threshold" -> a.threshold = Double.parseDouble(value);
                    case "--only" -> a.only = splitToSet(value);
                    case "--allowlist" -> a.allow = readAllowlist(value);
                    case "--exclude" -> a.excludes = new ArrayList<>(splitToSet(value));
                    case "--top" -> a.top = Integer.parseInt(value);
                    default -> throw new IllegalArgumentException("unknown option " + key);
                }
            }
            if (a.report == null) {
                throw new IllegalArgumentException("--report is required");
            }
            return a;
        }

        static Set<String> splitToSet(String csv) {
            Set<String> set = new HashSet<>();
            for (String s : csv.split(",")) {
                if (!s.isBlank()) {
                    set.add(s.trim());
                }
            }
            return set;
        }

        static Set<String> readAllowlist(String file) {
            Set<String> set = new HashSet<>();
            Path p = Path.of(file);
            if (!Files.isRegularFile(p)) {
                return set;
            }
            try {
                for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
                    int comment = commentStart(line);
                    String entry = (comment < 0 ? line : line.substring(0, comment)).trim();
                    if (!entry.isEmpty()) {
                        set.add(entry);
                    }
                }
            } catch (Exception e) {
                throw new IllegalArgumentException("cannot read allowlist " + file + ": " + e.getMessage());
            }
            return set;
        }

        /** A {@code #} starts a comment only after whitespace or at line start: the one inside {@code Class#method} does not. */
        static int commentStart(String line) {
            for (int i = 0; i < line.length(); i++) {
                if (line.charAt(i) == '#' && (i == 0 || Character.isWhitespace(line.charAt(i - 1)))) {
                    return i;
                }
            }
            return -1;
        }
    }
}

===== END FILE gauntlet/tools/CrapGate.java =====

===== BEGIN FILE gauntlet/tools/DryGate.java =====
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * DRY gate: reads a PMD CPD XML report and fails on duplicated code.
 *
 * <p>With {@code --only}, only duplications that touch at least one of the listed (changed)
 * files count, so an existing codebase can adopt the gate without fixing history first.
 *
 * <pre>
 * java DryGate.java --report build/reports/cpd/cpd.xml --project-dir . [--only a.java,b.java] [--max 0]
 * </pre>
 * Exit codes: 0 = OK, 1 = too many duplications, 2 = usage or input error.
 */
public class DryGate {

    record Location(String path, int line, int endLine) {
        String display() {
            return path + ":" + line + "-" + endLine;
        }
    }

    record Duplication(int lines, int tokens, List<Location> locations) {
    }

    public static void main(String[] args) {
        System.exit(run(args, utf8(FileDescriptor.out), utf8(FileDescriptor.err)));
    }

    static PrintStream utf8(FileDescriptor fd) {
        return new PrintStream(new FileOutputStream(fd), true, StandardCharsets.UTF_8);
    }

    static int run(String[] args, PrintStream out, PrintStream err) {
        String report = null;
        String projectDir = ".";
        Set<String> only = null;
        int max = 0;
        try {
            for (int i = 0; i < args.length; i += 2) {
                String value = args[i + 1];
                switch (args[i]) {
                    case "--report" -> report = value;
                    case "--project-dir" -> projectDir = value;
                    case "--only" -> only = csv(value);
                    case "--max" -> max = Integer.parseInt(value);
                    default -> throw new IllegalArgumentException("unknown option " + args[i]);
                }
            }
            if (report == null) {
                throw new IllegalArgumentException("--report is required");
            }
        } catch (RuntimeException e) {
            err.println("DryGate: " + e.getMessage());
            err.println("usage: java DryGate.java --report <cpd.xml> [--project-dir dir] [--only f1,f2] [--max 0]");
            return 2;
        }
        if (only != null && only.isEmpty()) {
            out.println("DRY gate: no changed Java sources in scope - nothing to check.");
            return 0;
        }
        File xml = new File(report);
        if (!xml.isFile()) {
            err.println("DryGate: CPD report not found: " + report);
            return 2;
        }
        List<Duplication> all;
        try {
            all = parse(xml, Path.of(projectDir).toAbsolutePath().normalize());
        } catch (Exception e) {
            err.println("DryGate: cannot read " + report + ": " + e);
            return 2;
        }
        List<Duplication> inScope = new ArrayList<>();
        for (Duplication d : all) {
            if (touches(d, only)) {
                inScope.add(d);
            }
        }
        out.printf("DRY gate: %d duplication(s) found by CPD, %d in scope (%s), max allowed %d%n",
                all.size(), inScope.size(), only == null ? "all sources" : only.size() + " changed file(s)", max);
        for (Duplication d : inScope) {
            StringBuilder sb = new StringBuilder("DUPLICATE ").append(d.lines()).append(" lines (")
                    .append(d.tokens()).append(" tokens): ");
            for (int i = 0; i < d.locations().size(); i++) {
                sb.append(i == 0 ? "" : "  <->  ").append(d.locations().get(i).display());
            }
            out.println(sb);
        }
        if (inScope.size() <= max) {
            out.println("DRY gate: OK");
            return 0;
        }
        out.println("DRY gate: FAILED - extract the shared behaviour into one place (a method, a class, a");
        out.println("  test fixture). Do not just rename things to fool the detector.");
        return 1;
    }

    static List<Duplication> parse(File xml, Path projectDir) throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setNamespaceAware(false);
        f.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        Document doc = f.newDocumentBuilder().parse(xml);
        List<Duplication> list = new ArrayList<>();
        NodeList dups = doc.getElementsByTagName("duplication");
        for (int i = 0; i < dups.getLength(); i++) {
            Element d = (Element) dups.item(i);
            List<Location> locations = new ArrayList<>();
            for (Node n = d.getFirstChild(); n != null; n = n.getNextSibling()) {
                if (n instanceof Element e && e.getTagName().equals("file")) {
                    locations.add(new Location(relative(e.getAttribute("path"), projectDir),
                            intAttr(e, "line"), intAttr(e, "endline")));
                }
            }
            list.add(new Duplication(intAttr(d, "lines"), intAttr(d, "tokens"), locations));
        }
        return list;
    }

    static boolean touches(Duplication d, Set<String> only) {
        if (only == null) {
            return true;
        }
        for (Location l : d.locations()) {
            for (String f : only) {
                String norm = f.replace('\\', '/');
                if (l.path().equals(norm) || l.path().endsWith("/" + norm) || norm.endsWith("/" + l.path())) {
                    return true;
                }
            }
        }
        return false;
    }

    static String relative(String path, Path projectDir) {
        Path p = Path.of(path);
        if (p.isAbsolute() && p.normalize().startsWith(projectDir)) {
            return projectDir.relativize(p.normalize()).toString().replace('\\', '/');
        }
        return path.replace('\\', '/');
    }

    static int intAttr(Element e, String name) {
        String v = e.getAttribute(name);
        return v.isEmpty() ? 0 : Integer.parseInt(v);
    }

    static Set<String> csv(String value) {
        Set<String> set = new HashSet<>();
        for (String s : value.split(",")) {
            if (!s.isBlank()) {
                set.add(s.trim());
            }
        }
        return set;
    }
}

===== END FILE gauntlet/tools/DryGate.java =====

===== BEGIN FILE gauntlet/tools/GherkinMutator.java =====
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.Period;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * Gherkin acceptance mutation for Cucumber-JVM projects.
 *
 * <p>Follows the idea of unclebob/Acceptance-Pipeline-Specification: mutate one Examples value
 * at a time and expect the acceptance tests to fail. A mutant that still passes ("survives")
 * means the step that consumes that value does not really check it - the classic hollow step
 * definition. Only Examples values are mutated, never step text or literals, so every value
 * that matters must be an Examples parameter.
 *
 * <pre>
 * java GherkinMutator.java generate --features src/acceptanceTest/resources/features \
 *      --out build/gherkin-mutation/mutants [--only a.feature,b.feature]
 * java GherkinMutator.java verdict --mutants build/gherkin-mutation/mutants \
 *      --results build/gherkin-mutation/results
 * </pre>
 * {@code generate} writes one feature file per mutant: the original Scenario Outline with its
 * {@code <placeholders>} and Background intact, and a single Examples row whose one target cell is
 * mutated - Cucumber interpolates every other value exactly as in the original run, so a non-mutated
 * column (e.g. an address holding a newline) is never distorted. Plus manifest.tsv. Run them with
 * Cucumber, then {@code verdict} reads the JUnit XML results: a {@code <failure>} that is an assertion
 * with a Cucumber STEP frame = killed (an undefined step for the new value is counted separately); passed =
 * survived; a {@code <error>}, a non-assertion {@code <failure>} (IOException etc.), an assertion without
 * a step frame (including a @Before/@After hook), skipped/aborted or missing = error, never a kill.
 * {@code no-skipped} fails when the {@code --features} directory is missing, when a normal acceptance run
 * skipped scenarios, or ran none although {@code --features} holds feature files; an existing directory
 * without feature files passes without reading any results.
 * {@code generate} fails when the configured features directory does not exist (a misconfigured
 * {@code acceptance.features}; the install creates it empty), or when a scenario in scope has steps but no
 * Examples value to mutate: gherkinMutation would otherwise pass it without having checked anything.
 * A scenario with no steps of its own (empty or description-only) runs nothing under Cucumber, so it
 * yields no mutant and is not flagged vacuous.
 * Supports English and Russian keywords ("# language: ru").
 * Exit codes: 0 = OK / all killed, 1 = survivors or errors, 2 = usage or IO error.
 */
public class GherkinMutator {

    // ---------------------------------------------------------------- keywords

    record Keywords(List<String> feature, List<String> background, List<String> rule, List<String> scenario,
                    List<String> outline, List<String> examples, List<String> step) {
    }

    // Step keywords carry their trailing space (Gherkin dialect form); "* " is the universal step keyword.
    static final Map<String, Keywords> LANGUAGES = Map.of(
            "en", new Keywords(List.of("Feature", "Business Need", "Ability"), List.of("Background"), List.of("Rule"),
                    List.of("Example", "Scenario"), List.of("Scenario Outline", "Scenario Template"),
                    List.of("Examples", "Scenarios"),
                    List.of("Given ", "When ", "Then ", "And ", "But ", "* ")),
            "ru", new Keywords(List.of("Функция", "Функциональность", "Функционал", "Свойство", "Фича"),
                    List.of("Предыстория", "Контекст"), List.of("Правило"), List.of("Пример", "Сценарий"),
                    List.of("Структура сценария", "Шаблон сценария"), List.of("Примеры", "Значения"),
                    List.of("Дано ", "Допустим ", "Пусть ", "Если ", "Когда ", "То ", "Тогда ", "Затем ",
                            "И ", "А ", "Но ", "Иначе ", "Также ", "К тому же ", "* ")));

    enum Kw { FEATURE, BACKGROUND, RULE, SCENARIO, EXAMPLES }

    // ---------------------------------------------------------------- model

    static final class Examples {
        final List<String> tags;
        final int line;
        List<String> headerRaw;
        final List<List<String>> rowsRaw = new ArrayList<>();
        final List<Integer> rowLines = new ArrayList<>();

        Examples(List<String> tags, int line) {
            this.tags = tags;
            this.line = line;
        }
    }

    static final class Rule {
        final List<String> tags;
        final String header;
        final List<String> background = new ArrayList<>();

        Rule(List<String> tags, String header) {
            this.tags = tags;
            this.header = header;
        }
    }

    static final class Scenario {
        final List<String> tags;
        final String name;
        final int line;
        final Rule rule;
        final List<String> body = new ArrayList<>();
        final List<Examples> examples = new ArrayList<>();

        Scenario(List<String> tags, String name, int line, Rule rule) {
            this.tags = tags;
            this.name = name;
            this.line = line;
            this.rule = rule;
        }
    }

    static final class FeatureDoc {
        String path;
        String language = "en";
        String languageLine;
        List<String> tags = new ArrayList<>();
        String header;
        String name = "";
        final List<String> background = new ArrayList<>();
        final List<Scenario> scenarios = new ArrayList<>();
    }

    record Mutant(String id, FeatureDoc feature, Scenario scenario, Examples examples, int row, String key,
                  String original, String mutated) {
    }

    // ---------------------------------------------------------------- entry points

    public static void main(String[] args) {
        System.exit(run(args, utf8(FileDescriptor.out), utf8(FileDescriptor.err)));
    }

    static PrintStream utf8(FileDescriptor fd) {
        return new PrintStream(new FileOutputStream(fd), true, StandardCharsets.UTF_8);
    }

    static int run(String[] args, PrintStream out, PrintStream err) {
        if (args.length == 0) {
            err.println("usage: java GherkinMutator.java generate|verdict [options]");
            return 2;
        }
        Map<String, String> opts = new LinkedHashMap<>();
        for (int i = 1; i + 1 < args.length; i += 2) {
            opts.put(args[i], args[i + 1]);
        }
        try {
            return switch (args[0]) {
                case "generate" -> generate(Path.of(opts.getOrDefault("--features", "src/acceptanceTest/resources/features")),
                        Path.of(opts.getOrDefault("--out", "build/gherkin-mutation/mutants")),
                        opts.containsKey("--only") ? csv(opts.get("--only")) : null, out);
                case "verdict" -> verdict(Path.of(opts.getOrDefault("--mutants", "build/gherkin-mutation/mutants")),
                        Path.of(opts.getOrDefault("--results", "build/gherkin-mutation/results")), out);
                case "no-skipped" -> noSkipped(Path.of(opts.getOrDefault("--results", "build/test-results/acceptanceTest")),
                        opts.containsKey("--features") ? Path.of(opts.get("--features")) : null, out);
                default -> {
                    err.println("GherkinMutator: unknown command " + args[0]);
                    yield 2;
                }
            };
        } catch (IOException | RuntimeException e) {
            err.println("GherkinMutator: " + e);
            return 2;
        }
    }

    // ---------------------------------------------------------------- generate

    static int generate(Path featuresDir, Path outDir, List<String> only, PrintStream out) throws IOException {
        deleteRecursively(outDir);
        Files.createDirectories(outDir);
        if (!Files.isDirectory(featuresDir)) {
            out.println("GHERKIN ERROR features directory " + featuresDir + " does not exist - acceptance.features is"
                    + " misconfigured (the install creates it empty with a .gitkeep); gherkinMutation cannot run");
            return 1;
        }
        List<Path> files = new ArrayList<>();
        try (Stream<Path> s = Files.walk(featuresDir)) {
            files = s.filter(p -> p.toString().endsWith(".feature")).sorted().toList();
        }
        List<Mutant> mutants = new ArrayList<>();
        int inScope = 0;
        int unreadable = 0;
        int vacuous = 0;
        for (Path file : files) {
            if (only != null && !matchesAny(file, only)) {
                continue;
            }
            List<String> lines = new ArrayList<>(Files.readAllLines(file, StandardCharsets.UTF_8));
            if (!lines.isEmpty() && lines.get(0).startsWith("\uFEFF")) {
                lines.set(0, lines.get(0).substring(1));   // UTF-8 byte order mark
            }
            if (lines.stream().map(GherkinMutator::gherkinStrip).allMatch(l -> l.isEmpty() || l.startsWith("#"))) {
                continue;   // empty or comment-only feature file: valid for Cucumber, nothing to mutate
            }
            inScope++;
            FeatureDoc doc = parse(file, lines);
            if (doc.header == null) {
                unreadable++;
                out.println("GHERKIN ERROR " + file + ": no recognised Feature keyword (language '" + doc.language
                        + "'; supported: " + LANGUAGES.keySet() + " - add the keywords to GherkinMutator.LANGUAGES)");
                continue;
            }
            int before = mutants.size();
            collectMutants(doc, mutants);
            Keywords kw = LANGUAGES.get(doc.language);
            for (Scenario sc : doc.scenarios) {
                if (stepCount(sc, kw) == 0) {
                    continue;                              // no steps of its own (empty or description-only): Cucumber
                                                           // executes nothing. Gherkin's PickleCompiler.compilePickleSteps
                                                           // returns an empty step list when the scenario has no steps,
                                                           // before prepending Background - so no step definition runs.
                }
                boolean checked = false;
                for (int mi = before; mi < mutants.size(); mi++) {
                    if (mutants.get(mi).scenario() == sc) {
                        checked = true;
                        break;
                    }
                }
                if (!checked) {
                    vacuous++;
                    out.println("GHERKIN VACUOUS " + file + ":" + sc.line + " scenario \"" + sc.name + "\" has no Examples"
                            + " value to mutate - gherkinMutation cannot check its step definitions");
                }
            }
        }
        List<String> manifest = new ArrayList<>();
        manifest.add("id\tfeature\tline\tscenario\tkey\toriginal\tmutated");
        for (Mutant m : mutants) {
            Files.write(outDir.resolve(m.id() + ".feature"), render(m), StandardCharsets.UTF_8);
            manifest.add(String.join("\t", m.id(), m.feature().path, String.valueOf(m.examples().rowLines.get(m.row())),
                    tsv(m.scenario().name), tsv(m.key()), tsv(m.original()), tsv(m.mutated())));
        }
        Files.write(outDir.resolve("manifest.tsv"), manifest, StandardCharsets.UTF_8);
        out.println("Gherkin mutation: " + mutants.size() + " mutant(s) from " + inScope + " feature file(s) in scope -> "
                + outDir);
        if (vacuous > 0) {
            out.println("  Every value a scenario depends on must be an Examples parameter (Scenario Outline), so that");
            out.println("  a hollow step definition shows up as a surviving mutant. The specifier rewrites the feature;");
            out.println("  the human approves it.");
        }
        return unreadable == 0 && vacuous == 0 ? 0 : 1;
    }

    static void collectMutants(FeatureDoc doc, List<Mutant> mutants) {
        Keywords kw = LANGUAGES.get(doc.language);
        for (int s = 0; s < doc.scenarios.size(); s++) {
            Scenario sc = doc.scenarios.get(s);
            if (stepCount(sc, kw) == 0) {
                continue;   // no steps: Cucumber executes nothing, so mutating its Examples proves nothing
            }
            for (int e = 0; e < sc.examples.size(); e++) {
                Examples ex = sc.examples.get(e);
                if (ex.headerRaw == null) {
                    continue;
                }
                for (int r = 0; r < ex.rowsRaw.size(); r++) {
                    List<String> row = ex.rowsRaw.get(r);
                    for (int k = 0; k < ex.headerRaw.size() && k < row.size(); k++) {
                        String key = unescape(ex.headerRaw.get(k));
                        String original = unescape(row.get(k));
                        String seed = doc.path + "|" + s + "|" + e + "|" + r + "|" + key + "|" + original;
                        String mutated = mutate(original, new Random(seed.hashCode()));
                        if (!mutated.equals(original)) {
                            mutants.add(new Mutant("m" + (mutants.size() + 1), doc, sc, ex, r, key, original, mutated));
                        }
                    }
                }
            }
        }
    }

    static List<String> render(Mutant m) {
        FeatureDoc doc = m.feature();
        Keywords kw = LANGUAGES.get(doc.language);
        List<String> lines = new ArrayList<>();
        if (doc.languageLine != null) {
            lines.add(doc.languageLine);
        }
        lines.add("# Gherkin mutant " + m.id() + " of " + doc.path + " - generated, do not edit");
        lines.addAll(doc.tags);
        lines.add(featureKeyword(doc) + ": MUTANT " + m.id() + " | " + doc.name);
        lines.addAll(doc.background);
        Rule rule = m.scenario().rule;
        if (rule != null) {
            lines.addAll(rule.tags);
            lines.add(rule.header);
            lines.addAll(rule.background);
        }
        List<String> tags = new ArrayList<>(m.scenario().tags);
        tags.addAll(m.examples().tags);
        lines.addAll(tags);
        // Keep the Scenario Outline and its <placeholders> verbatim: Cucumber interpolates the Examples
        // values itself, exactly as in the original run. Flattening to a plain Scenario and re-escaping the
        // substituted values would distort every other column (a real newline in an address cell becomes a
        // literal \n in step text, failing an unrelated check and falsely "killing" this mutant). Only the
        // single target cell of the single target row changes; all other cells stay byte-for-byte as written.
        lines.add("  " + kw.outline().get(0) + ": MUTANT " + m.id() + " | " + m.scenario().name + " | " + m.key() + ": "
                + tsv(m.original()) + " -> " + tsv(m.mutated()));
        lines.addAll(m.scenario().body);
        Examples ex = m.examples();
        lines.add("    " + kw.examples().get(0) + ":");
        lines.add("      | " + String.join(" | ", ex.headerRaw) + " |");
        int keyIndex = -1;
        for (int k = 0; k < ex.headerRaw.size(); k++) {
            if (unescape(ex.headerRaw.get(k)).equals(m.key())) {
                keyIndex = k;
                break;
            }
        }
        List<String> row = new ArrayList<>(ex.rowsRaw.get(m.row()));
        if (keyIndex >= 0 && keyIndex < row.size()) {
            row.set(keyIndex, escapeCell(m.mutated()));
        }
        lines.add("      | " + String.join(" | ", row) + " |");
        return lines;
    }

    static String featureKeyword(FeatureDoc doc) {
        String t = gherkinStrip(doc.header);
        return t.substring(0, t.indexOf(':'));
    }

    // ---------------------------------------------------------------- parser

    static FeatureDoc parse(Path file, List<String> lines) {
        FeatureDoc doc = new FeatureDoc();
        doc.path = file.toString().replace('\\', '/');
        for (String l : lines) {
            String t = gherkinStrip(l);
            if (t.isEmpty()) {
                continue;
            }
            Matcher lang = Pattern.compile("^#\\s*language\\s*:\\s*([\\w-]+)").matcher(t);
            if (lang.find()) {
                doc.language = lang.group(1);
                doc.languageLine = l;
            }
            if (!t.startsWith("#")) {
                break;
            }
        }
        Keywords kw = LANGUAGES.get(doc.language);
        if (kw == null) {
            return doc;
        }
        List<String> pendingTags = new ArrayList<>();
        List<String> block = null;
        Scenario scenario = null;
        Examples examples = null;
        Rule rule = null;
        String docStringFence = null;
        for (int i = 0; i < lines.size(); i++) {
            String line = lines.get(i);
            String t = gherkinStrip(line);
            if (docStringFence != null) {
                if (block != null) {
                    block.add(line);
                }
                if (t.startsWith(docStringFence)) {
                    docStringFence = null;
                }
                continue;
            }
            if (t.isEmpty() || t.startsWith("#")) {
                continue;
            }
            if (t.startsWith("\"\"\"") || t.startsWith("```")) {
                docStringFence = t.startsWith("```") ? "```" : "\"\"\"";
                if (block != null) {
                    block.add(line);
                }
                continue;
            }
            if (t.startsWith("@")) {
                pendingTags.add(line);
                continue;
            }
            Kw k = keyword(t, kw);
            if (k != null) {
                String name = gherkinStrip(t.substring(t.indexOf(':') + 1));
                switch (k) {
                    case FEATURE -> {
                        doc.tags = pendingTags;
                        doc.header = line;
                        doc.name = name;
                        block = null;
                    }
                    case BACKGROUND -> {
                        block = rule != null ? rule.background : doc.background;
                        block.add(line);
                    }
                    case RULE -> {
                        rule = new Rule(pendingTags, line);
                        block = null;
                    }
                    case SCENARIO -> {
                        scenario = new Scenario(pendingTags, name, i + 1, rule);
                        doc.scenarios.add(scenario);
                        block = scenario.body;
                    }
                    case EXAMPLES -> {
                        if (scenario != null) {
                            examples = new Examples(pendingTags, i + 1);
                            scenario.examples.add(examples);
                        }
                        block = null;
                    }
                    default -> throw new IllegalStateException();
                }
                pendingTags = new ArrayList<>();
                continue;
            }
            if (t.startsWith("|") && block == null && examples != null && scenario != null
                    && !scenario.examples.isEmpty() && scenario.examples.get(scenario.examples.size() - 1) == examples) {
                List<String> cells = cells(t);
                if (examples.headerRaw == null) {
                    examples.headerRaw = cells;
                } else {
                    examples.rowsRaw.add(cells);
                    examples.rowLines.add(i + 1);
                }
                continue;
            }
            if (block != null) {
                block.add(line);
            }
        }
        return doc;
    }

    static Kw keyword(String trimmed, Keywords kw) {
        if (startsWithAny(trimmed, kw.feature())) {
            return Kw.FEATURE;
        }
        if (startsWithAny(trimmed, kw.background())) {
            return Kw.BACKGROUND;
        }
        if (startsWithAny(trimmed, kw.rule())) {
            return Kw.RULE;
        }
        if (startsWithAny(trimmed, kw.outline()) || startsWithAny(trimmed, kw.scenario())) {
            return Kw.SCENARIO;
        }
        if (startsWithAny(trimmed, kw.examples())) {
            return Kw.EXAMPLES;
        }
        return null;
    }

    static boolean startsWithAny(String trimmed, List<String> keywords) {
        for (String k : keywords) {
            if (trimmed.startsWith(k + ":")) {
                return true;
            }
        }
        return false;
    }

    /** A body line is a step when it starts with a Gherkin step keyword (which carries its trailing space).
     *  Free-text description lines are not steps; data tables and docstrings always follow a real step. */
    static boolean isStepLine(String trimmed, Keywords kw) {
        for (String s : kw.step()) {
            if (trimmed.startsWith(s)) {
                return true;
            }
        }
        return false;
    }

    static int stepCount(Scenario sc, Keywords kw) {
        int n = 0;
        for (String line : sc.body) {
            if (isStepLine(gherkinStrip(line), kw)) {
                n++;
            }
        }
        return n;
    }

    /** Gherkin's lexer treats Unicode space separators (incl. U+00A0 NBSP) as indentation, but String.trim()
     *  only strips chars <= U+0020 and keeps NBSP - a step indented with NBSP would otherwise vanish from
     *  stepCount and the scenario would be wrongly treated as having no steps (zero mutants, vacuous pass). */
    static String gherkinStrip(String line) {
        int start = 0;
        int end = line.length();
        while (start < end && isGherkinSpace(line.charAt(start))) {
            start++;
        }
        while (end > start && isGherkinSpace(line.charAt(end - 1))) {
            end--;
        }
        return line.substring(start, end);
    }

    static boolean isGherkinSpace(char c) {
        return Character.isWhitespace(c) || Character.isSpaceChar(c);
    }

    static List<String> cells(String row) {
        List<String> cells = new ArrayList<>();
        StringBuilder cur = null;
        for (int i = 0; i < row.length(); i++) {
            char c = row.charAt(i);
            if (c == '\\' && i + 1 < row.length()) {
                if (cur != null) {
                    cur.append(c).append(row.charAt(i + 1));
                }
                i++;
            } else if (c == '|') {
                if (cur != null) {
                    cells.add(gherkinStrip(cur.toString()));
                }
                cur = new StringBuilder();
            } else if (cur != null) {
                cur.append(c);
            }
        }
        return cells;
    }

    static String unescape(String cell) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < cell.length(); i++) {
            char c = cell.charAt(i);
            if (c == '\\' && i + 1 < cell.length()) {
                char n = cell.charAt(i + 1);
                if (n == '\\' || n == 'n' || n == '|') {
                    sb.append(n == 'n' ? '\n' : n);
                    i++;
                    continue;
                }
            }
            sb.append(c);
        }
        return sb.toString();
    }

    static String escapeCell(String value) {
        return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "\\n");
    }

    // ---------------------------------------------------------------- value mutation (APS rules)

    static final Pattern INTEGER = Pattern.compile("[+-]?\\d+");
    static final Pattern DECIMAL = Pattern.compile("[+-]?\\d+\\.\\d+");
    static final Pattern COMMA_DECIMAL = Pattern.compile("[+-]?\\d+,\\d+");
    static final Pattern DATE = Pattern.compile("\\d{4}-\\d{2}-\\d{2}");
    static final Pattern TIME = Pattern.compile("(\\d{2}:\\d{2})(:\\d{2})?");
    static final Pattern DATE_TIME = Pattern.compile(
            "(\\d{4}-\\d{2}-\\d{2})([T ])(\\d{2}:\\d{2})(:\\d{2})?(\\.\\d{1,9})?(Z|[+-]\\d{2}:?\\d{2})?");
    static final Pattern SHORT_DURATION = Pattern.compile("(\\d+)(ms|s|m|h|d)");

    static String mutate(String value, Random rnd) {
        String t = value.trim();
        if (COMMA_DECIMAL.matcher(t).matches()) {   // Russian-style decimal: 1,5 / 750,50
            return mutateDecimal(t.replace(',', '.'), rnd).replace('.', ',');
        }
        if (t.contains(",")) {
            String[] items = t.split(",", -1);
            int pick = rnd.nextInt(items.length);
            List<String> result = new ArrayList<>();
            for (int i = 0; i < items.length; i++) {
                String item = items[i].trim();
                result.add(i == pick ? mutate(item, rnd) : item);
            }
            return String.join(", ", result);
        }
        String lower = t.toLowerCase();
        if (lower.equals("true") || lower.equals("false")) {
            return lower.equals("true") ? "false" : "true";
        }
        if (lower.equals("null") || lower.equals("nil") || lower.equals("none")) {
            return dither(t, rnd);
        }
        if (INTEGER.matcher(t).matches()) {
            return mutateInteger(t, rnd);
        }
        if (DECIMAL.matcher(t).matches()) {
            return mutateDecimal(t, rnd);
        }
        String temporal = mutateTemporal(t, rnd);
        if (temporal != null) {
            return temporal;
        }
        return dither(value, rnd);
    }

    static int delta(Random rnd) {
        int d = 1 + rnd.nextInt(9);
        return rnd.nextBoolean() ? d : -d;
    }

    static String mutateInteger(String t, Random rnd) {
        BigInteger v = new BigInteger(t.startsWith("+") ? t.substring(1) : t);
        int d = delta(rnd);
        BigInteger r = v.add(BigInteger.valueOf(d));
        if (v.signum() >= 0 && r.signum() < 0) {
            r = v.add(BigInteger.valueOf(Math.abs(d)));
        }
        String s = r.toString();
        String digits = t.replaceFirst("^[+-]", "");
        if (digits.length() > 1 && digits.startsWith("0") && r.signum() >= 0) {
            s = "0".repeat(Math.max(0, digits.length() - s.length())) + s;
        }
        return s;
    }

    static String mutateDecimal(String t, Random rnd) {
        BigDecimal v = new BigDecimal(t.startsWith("+") ? t.substring(1) : t);
        int scale = v.scale();
        BigDecimal step = BigDecimal.valueOf(1 + rnd.nextInt(99)).movePointLeft(scale);
        BigDecimal r = rnd.nextBoolean() ? v.add(step) : v.subtract(step);
        if (v.signum() >= 0 && r.signum() < 0) {
            r = v.add(step);
        }
        return r.setScale(scale).toPlainString();
    }

    static String mutateTemporal(String t, Random rnd) {
        try {
            if (DATE.matcher(t).matches()) {
                return LocalDate.parse(t).plusDays(delta(rnd) * 3L).toString();
            }
            Matcher tm = TIME.matcher(t);
            if (tm.matches()) {
                boolean seconds = tm.group(2) != null;
                LocalTime lt = LocalTime.parse(t);
                return seconds ? lt.plusSeconds(delta(rnd) * 7L).format(DateTimeFormatter.ofPattern("HH:mm:ss"))
                        : lt.plusMinutes(delta(rnd) * 7L).format(DateTimeFormatter.ofPattern("HH:mm"));
            }
            Matcher dt = DATE_TIME.matcher(t);
            if (dt.matches()) {
                boolean seconds = dt.group(4) != null;
                LocalDateTime ldt = LocalDateTime.parse(dt.group(1) + "T" + dt.group(3) + (seconds ? dt.group(4) : ":00"));
                LocalDateTime shifted = seconds ? ldt.plusSeconds(delta(rnd) * 7L) : ldt.plusMinutes(delta(rnd) * 7L);
                String time = shifted.format(DateTimeFormatter.ofPattern(seconds ? "HH:mm:ss" : "HH:mm"));
                return shifted.toLocalDate() + dt.group(2) + time + (dt.group(5) == null ? "" : dt.group(5))
                        + (dt.group(6) == null ? "" : dt.group(6));
            }
            if (t.startsWith("P") || t.startsWith("-P")) {
                if (t.contains("T")) {
                    Duration d = Duration.parse(t);
                    Duration r = d.toMinutes() >= 1 ? d.plusMinutes(delta(rnd)) : d.plusSeconds(delta(rnd));
                    return (r.isNegative() || r.isZero() ? d.plusMinutes(Math.abs(delta(rnd))) : r).toString();
                }
                Period p = Period.parse(t);
                Period r = p.plusDays(delta(rnd));
                return (r.isNegative() ? p.plusDays(1 + rnd.nextInt(9)) : r).toString();
            }
            Matcher sd = SHORT_DURATION.matcher(t);
            if (sd.matches()) {
                long n = Long.parseLong(sd.group(1));
                long r = n + delta(rnd);
                return (r < 0 ? n + 1 + rnd.nextInt(9) : r) + sd.group(2);
            }
        } catch (RuntimeException notTemporal) {
            return null;
        }
        return null;
    }

    static String dither(String s, Random rnd) {
        if (s.isEmpty()) {
            return "x";
        }
        for (int attempt = 0; attempt < 32; attempt++) {
            int i = rnd.nextInt(s.length());
            char c = s.charAt(i);
            String r = switch (rnd.nextInt(4)) {
                case 0 -> s.substring(0, i) + similar(c, rnd) + s.substring(i + 1);
                case 1 -> i + 1 < s.length() ? s.substring(0, i) + s.charAt(i + 1) + c + s.substring(i + 2) : s;
                case 2 -> s.substring(0, i) + similar(c, rnd) + s.substring(i);
                default -> s.length() > 1 ? s.substring(0, i) + s.substring(i + 1) : s;
            };
            if (!r.equals(s) && !r.isBlank()) {
                return r;
            }
        }
        return s + "x";
    }

    static char similar(char c, Random rnd) {
        if (c >= 'a' && c <= 'z') {
            return (char) ('a' + rnd.nextInt(26));
        }
        if (c >= 'A' && c <= 'Z') {
            return (char) ('A' + rnd.nextInt(26));
        }
        if (c >= 'а' && c <= 'я') {
            return (char) ('а' + rnd.nextInt(32));
        }
        if (c >= 'А' && c <= 'Я') {
            return (char) ('А' + rnd.nextInt(32));
        }
        if (c >= '0' && c <= '9') {
            return (char) ('0' + rnd.nextInt(10));
        }
        return (char) ('a' + rnd.nextInt(26));
    }

    // ---------------------------------------------------------------- verdict

    static int verdict(Path mutantsDir, Path resultsDir, PrintStream out) throws IOException {
        Path manifestFile = mutantsDir.resolve("manifest.tsv");
        if (!Files.isRegularFile(manifestFile)) {
            out.println("Gherkin mutation: no manifest at " + manifestFile + " - nothing to judge.");
            return 0;
        }
        Map<String, String[]> manifest = new LinkedHashMap<>();
        List<String> lines = Files.readAllLines(manifestFile, StandardCharsets.UTF_8);
        for (String line : lines.subList(1, lines.size())) {
            String[] f = line.split("\t", -1);
            manifest.put(f[0], f);
        }
        if (manifest.isEmpty()) {
            out.println("Gherkin mutation: no mutants (no Examples values in scope) - OK.");
            return 0;
        }
        Map<String, String> outcome = readResults(resultsDir);
        int killed = 0;
        int byUndefinedStep = 0;
        List<String> survived = new ArrayList<>();
        List<String> errors = new ArrayList<>();
        for (Map.Entry<String, String[]> e : manifest.entrySet()) {
            String[] f = e.getValue();
            String what = f[1] + ":" + f[2] + " \"" + f[3] + "\" " + f[4] + ": " + f[5] + " -> " + f[6];
            String o = outcome.get(e.getKey());
            if (o == null) {
                errors.add("MUTANT ERROR    " + e.getKey() + " not executed  " + what);
            } else if (o.equals("passed")) {
                survived.add("MUTANT SURVIVED " + e.getKey() + "  " + what);
            } else if (o.equals("aborted")) {
                errors.add("MUTANT ERROR    " + e.getKey() + " skipped/aborted, not a kill  " + what);
            } else if (o.equals("error")) {
                errors.add("MUTANT ERROR    " + e.getKey() + " errored (exception/crash), not a kill  " + what);
            } else {
                killed++;
                byUndefinedStep += o.equals("undefined") ? 1 : 0;
            }
        }
        out.println("Gherkin mutation: " + manifest.size() + " mutant(s) - " + killed + " killed"
                + (byUndefinedStep > 0 ? " (" + byUndefinedStep + " only because no step definition matched the new value)" : "")
                + ", " + survived.size() + " survived, " + errors.size() + " error(s)");
        survived.forEach(out::println);
        errors.forEach(out::println);
        if (survived.isEmpty() && errors.isEmpty()) {
            out.println("Gherkin mutation: OK");
            return 0;
        }
        if (!survived.isEmpty()) {
            out.println("  A survivor means the scenario still passes after that Examples value changed: the step");
            out.println("  that receives the value ignores it or asserts too weakly. Fix the step definition or the");
            out.println("  production code - not the feature file. If the column truly does not matter, the");
            out.println("  specifier should remove it from the Examples (human approval required).");
        }
        if (!errors.isEmpty()) {
            out.println("  Errors: the mutant scenario did not run to a verdict (skipped by an assumption, parse error,");
            out.println("  crash, timeout). A skipped scenario proves nothing. See the test report.");
        }
        return 1;
    }

    /** Cucumber reports undefined steps as aborted, which Gradle shows as skipped - not as failed. */
    static int noSkipped(Path resultsDir, Path featuresDir, PrintStream out) throws IOException {
        if (featuresDir != null) {
            if (!Files.isDirectory(featuresDir)) {
                out.println("Acceptance: FAILED - features directory " + featuresDir + " does not exist - acceptance.features"
                        + " is misconfigured (the install creates it empty with a .gitkeep); a missing dir is not an empty run");
                return 1;
            }
            if (!hasFeatureFiles(featuresDir)) {
                out.println("Acceptance: no feature files in " + featuresDir + " - nothing to check (older results ignored)");
                return 0;
            }
        }
        List<String> skipped = new ArrayList<>();
        int total = 0;
        for (Element tc : testcases(resultsDir)) {
            total++;
            for (Node n = tc.getFirstChild(); n != null; n = n.getNextSibling()) {
                if (n instanceof Element e && e.getTagName().equals("skipped")) {
                    skipped.add("ACCEPTANCE SKIPPED " + tc.getAttribute("classname") + " > " + tc.getAttribute("name"));
                }
            }
        }
        if (total == 0 && featuresDir != null) {
            out.println("Acceptance: FAILED - feature files exist in " + featuresDir + ", but no scenario ran (no results in "
                    + resultsDir + "). An empty run proves nothing: check cucumber.features, the glue and the engine.");
            return 1;
        }
        if (skipped.isEmpty()) {
            out.println("Acceptance: " + total + " scenario(s), none skipped - OK");
            return 0;
        }
        skipped.forEach(out::println);
        out.println("Acceptance: FAILED - " + skipped.size() + " scenario(s) skipped. Cucumber reports undefined or");
        out.println("  pending steps as skipped, so they would otherwise pass silently. Implement the missing step");
        out.println("  definitions (run with -Dcucumber.plugin=pretty to see the snippets).");
        return 1;
    }

    static boolean hasFeatureFiles(Path featuresDir) throws IOException {
        if (!Files.isDirectory(featuresDir)) {
            return false;
        }
        try (Stream<Path> s = Files.walk(featuresDir)) {
            return s.filter(p -> p.toString().endsWith(".feature")).anyMatch(GherkinMutator::hasGherkin);
        }
    }

    /** Empty and comment-only feature files are valid for Cucumber but hold no specification. */
    static boolean hasGherkin(Path featureFile) {
        try {
            return Files.readAllLines(featureFile, StandardCharsets.UTF_8).stream()
                    .map(l -> gherkinStrip(l.replace("\uFEFF", ""))).anyMatch(l -> !l.isEmpty() && !l.startsWith("#"));
        } catch (IOException unreadable) {
            return true;   // unreadable is not proof of emptiness
        }
    }

    static List<Element> testcases(Path resultsDir) throws IOException {
        List<Element> list = new ArrayList<>();
        if (!Files.isDirectory(resultsDir)) {
            return list;
        }
        List<Path> xmls;
        try (Stream<Path> s = Files.walk(resultsDir)) {
            xmls = s.filter(p -> p.toString().endsWith(".xml")).sorted().toList();
        }
        for (Path xml : xmls) {
            try {
                DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
                f.setNamespaceAware(false);
                Document doc = f.newDocumentBuilder().parse(xml.toFile());
                NodeList cases = doc.getElementsByTagName("testcase");
                for (int i = 0; i < cases.getLength(); i++) {
                    list.add((Element) cases.item(i));
                }
            } catch (Exception unreadable) {
                // not a JUnit XML report - ignore
            }
        }
        return list;
    }

    static Map<String, String> readResults(Path resultsDir) throws IOException {
        Map<String, String> outcome = new LinkedHashMap<>();
        Pattern id = Pattern.compile("MUTANT (m\\d+)\\b");
        for (Element tc : testcases(resultsDir)) {
            Matcher m = id.matcher(tc.getAttribute("name") + " " + tc.getAttribute("classname"));
            if (!m.find()) {
                continue;
            }
            String result = "passed";
            for (Node n = tc.getFirstChild(); n != null; n = n.getNextSibling()) {
                if (n instanceof Element e) {
                    switch (e.getTagName()) {
                        // A kill is an assertion that failed IN A STEP. Gradle writes a @Before/@After hook
                        // exception (IOException, or an assertion in the hook) as <failure> too, but no step
                        // reached a verdict - that is an error, not a kill. <error> = a crash/glue/harness
                        // failure that never reached a verdict: also an error.
                        case "failure" -> result = undefinedStep(e) ? "undefined" : stepAssertionKill(e) ? "failed" : "error";
                        case "error" -> result = undefinedStep(e) ? "undefined" : "error";
                        case "skipped" -> result = result.equals("passed") ? "aborted" : result;
                        default -> {
                        }
                    }
                }
            }
            String prev = outcome.get(m.group(1));
            if (prev == null || prev.equals("passed") || prev.equals("aborted")) {
                outcome.put(m.group(1), result);
            }
        }
        return outcome;
    }

    /** Cucumber reports a step without a matching definition with this specific exception. */
    static boolean undefinedStep(Element failure) {
        String text = failure.getAttribute("type") + " " + failure.getTextContent();
        return text.contains("UndefinedStepException");
    }

    /** A mutant is killed only by an assertion with positive evidence that a STEP ran. Runner filtering can
     *  omit all hook frames from a @Before failure, so absence of hook markers is not evidence of a step. */
    static boolean stepAssertionKill(Element failure) {
        return assertionType(failure.getAttribute("type")) && stepStage(failure.getTextContent());
    }

    static boolean assertionType(String type) {
        return type.endsWith("AssertionError") || type.endsWith("AssertionFailedError")
                || type.endsWith("AssertFailedError") || type.endsWith("ComparisonFailure")
                || type.endsWith("ComparisonFailureWithFacts") || type.endsWith("AssertionErrorWithFacts")
                || type.endsWith("MultipleFailuresError");
    }

    static boolean stepStage(String trace) {
        return trace.contains("PickleStepDefinitionMatch") || trace.contains("StepDefinitionMatch")
                || trace.contains("✽.");
    }

    // ---------------------------------------------------------------- helpers

    static boolean matchesAny(Path file, List<String> only) {
        String p = file.toString().replace('\\', '/');
        for (String o : only) {
            String n = o.replace('\\', '/');
            if (p.equals(n) || p.endsWith("/" + n) || n.endsWith("/" + p) || n.endsWith(p)) {
                return true;
            }
        }
        return false;
    }

    static List<String> csv(String s) {
        List<String> list = new ArrayList<>();
        for (String x : s.split(",")) {
            if (!x.isBlank()) {
                list.add(x.trim());
            }
        }
        return list;
    }

    static String tsv(String s) {
        return s.replace('\t', ' ').replace('\n', ' ');
    }

    static void deleteRecursively(Path dir) throws IOException {
        if (!Files.exists(dir)) {
            return;
        }
        try (Stream<Path> s = Files.walk(dir)) {
            for (Path p : s.sorted((a, b) -> b.getNameCount() - a.getNameCount()).toList()) {
                Files.delete(p);
            }
        }
    }
}

===== END FILE gauntlet/tools/GherkinMutator.java =====

===== BEGIN FILE gauntlet/tools/IntegrityCheck.java =====
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.PathMatcher;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

/**
 * Integrity check: finds the usual ways to turn a red gauntlet green without fixing anything.
 *
 * <p>If nobody reads the code, the gates must not be quietly bypassable. This scans tests,
 * production code, feature files and build scripts for skip/suppress/exclude tricks. A finding
 * can be accepted only by the human, in {@code gauntlet/config/integrity-allowlist.txt}:
 * <pre>
 *   &lt;path glob relative to the project root&gt; &lt;RULE-ID&gt;   # reason
 *   src/test/java/**&#47;LegacyReportIT.java T4               # needs a real Oracle, runs in CI only
 * </pre>
 * Usage: {@code java IntegrityCheck.java --root . [--features <dir>] [--allowlist <file>]}
 * Exit codes: 0 = clean, 1 = findings, 2 = usage or IO error.
 */
public class IntegrityCheck {

    enum Kind { TEST, MAIN, FEATURE, BUILD, PROPS }

    record Rule(String id, Kind kind, Pattern pattern, boolean includeComments, String why) {
    }

    record Finding(String path, int line, Rule rule, String text) {
    }

    record Allow(PathMatcher matcher, String ruleId) {
    }

    /** Switching off packaging/doc tasks (e.g. Spring Boot's plain jar) is normal and not a gate. */
    static final String HARMLESS_NAMES = "(jar|bootJar|bootRun|javadoc\\w*|sourcesJar|distZip|distTar|startScripts"
            + "|bootDist\\w*|bootStartScripts|bootBuildImage|publish\\w*|generate\\w*|openApi\\w*|Jar|Javadoc|Zip|Tar)";
    static final Pattern HARMLESS_TASK = Pattern.compile("(?i)[\"'<(]" + HARMLESS_NAMES + "[\"'>)]|^\\s*"
            + HARMLESS_NAMES + "\\s*\\{");
    static final Pattern DISABLED = Pattern.compile("\\b(is)?[eE]nabled\\s*=\\s*false|setEnabled\\s*\\(\\s*false");
    /** Receiver of a disabled statement: tasks.named("x")/getByName("x")/register("x") -> x. */
    static final Pattern TASK_REF = Pattern.compile(
            "(?:named|getByName|maybeCreate|register)\\s*\\(\\s*[\"']([^\"']+)[\"']\\s*\\)$");
    static final Pattern LAST_ID = Pattern.compile("([A-Za-z_$][\\w$]*)$");
    static final Pattern HARMLESS_NAME = Pattern.compile("(?i)^(?:" + HARMLESS_NAMES + ")$");
    /** Single named parameter of a task-configuration closure: {@code jar { t -> }} / {@code jar { Task t -> }}. */
    static final Pattern CLOSURE_PARAM = Pattern.compile("^\\s*(?:final\\s+)?"
            + "(?:[\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}$.]*(?:\\s*<[^>]*>)?(?:\\[\\])?\\s+)?"
            + "([\\p{javaJavaIdentifierStart}][\\p{javaJavaIdentifierPart}$]*)\\s*->");

    static final List<Rule> RULES = List.of(
            rule("T1", Kind.TEST, "@Disabled\\w*", false, "disabled test"),
            rule("T2", Kind.TEST, "@Enabled(If|On)\\w*", false, "conditionally enabled test"),
            rule("T3", Kind.TEST, "@Ignore\\b", false, "ignored JUnit 4 test"),
            rule("T4", Kind.TEST, "\\bassum(e|ing)(True|False|That)\\s*\\(|\\bAssumptions\\.|(?<![.\\w])abort\\s*\\(", false,
                    "assumption can silently skip the test"),
            rule("T5", Kind.TEST, "disabledWithoutDocker\\s*=\\s*true", false,
                    "Testcontainers tests silently skipped without Docker"),
            rule("M1", Kind.MAIN, "@[\\w.]*(Generated(?!Value)|DoNotMutate|CoverageIgnore)\\w*", false,
                    "annotation hides code from coverage/CRAP/mutation"),
            rule("M2", Kind.MAIN, "CHECKSTYLE\\s*[:.]\\s*OFF|checkstyle:off|NOPMD|CPD-OFF", true,
                    "inline suppression of a quality check"),
            rule("M3", Kind.MAIN, "@SuppressWarnings\\s*\\(\\s*\\{?\\s*\"(checkstyle|PMD|CPD)", false,
                    "suppression of a quality check"),
            rule("F1", Kind.FEATURE,
                    "^\\s*(?:@\\S+\\s+)*@(ignore|ignored|disabled|skip|skipped|wip|pending|manual)(?![\\w-])", true,
                    "tag commonly used to exclude a scenario"),
            rule("B1", Kind.BUILD, "ignoreFailures|\\b(is)?[eE]nabled\\s*=\\s*false|setEnabled\\s*\\(\\s*false|onlyIf\\s*[({]",
                    false, "build script switches a check off"),
            rule("B2", Kind.BUILD, "(exclude|include)TestsMatching|(exclude|include)Tags|excludeEngines|failOnNoDiscoveredTests",
                    false, "build script filters which tests run"),
            rule("B3", Kind.BUILD, "maxSurviving|mutationThreshold|coverageThreshold|testStrengthThreshold"
                    + "|excludedClasses|excludedMethods|excludedTestClasses|excludedGroups|avoidCallsTo|targetClasses"
                    + "|targetTests|classDirectories|cucumber\\.(filter|features|glue)", false,
                    "build script reconfigures a gate (gates live in gauntlet/gauntlet.gradle)"),
            rule("B4", Kind.BUILD, "tasks\\s*\\.\\s*(named|getByName|register)\\s*(<[^>]*>)?\\s*\\(\\s*[\"'](gauntlet\\w*"
                    + "|crapGate|dryGate|integrityCheck|archTest|acceptanceTest|acceptanceCheck|gherkin\\w+"
                    + "|mutationGate|pitest|pitSummary|jacocoTestReport|checkstyleGate|pmdGate|cpdReport)[\"']", false,
                    "build script touches a gauntlet task"),
            rule("B5", Kind.BUILD, "afterEvaluate|taskGraph|whenReady|beforeTask|projectsEvaluated", false,
                    "late build configuration can override the gauntlet"),
            rule("P1", Kind.PROPS, "cucumber\\.(filter|features)", false, "test properties filter scenarios"));

    public static void main(String[] args) {
        System.exit(run(args, utf8(FileDescriptor.out), utf8(FileDescriptor.err)));
    }

    static PrintStream utf8(FileDescriptor fd) {
        return new PrintStream(new FileOutputStream(fd), true, StandardCharsets.UTF_8);
    }

    static int run(String[] args, PrintStream out, PrintStream err) {
        Path root = Path.of(".");
        Path features = null;
        Path allowlist = null;
        try {
            for (int i = 0; i < args.length; i += 2) {
                switch (args[i]) {
                    case "--root" -> root = Path.of(args[i + 1]);
                    case "--features" -> features = Path.of(args[i + 1]);
                    case "--allowlist" -> allowlist = Path.of(args[i + 1]);
                    default -> throw new IllegalArgumentException("unknown option " + args[i]);
                }
            }
        } catch (RuntimeException e) {
            err.println("IntegrityCheck: " + e.getMessage());
            return 2;
        }
        root = root.toAbsolutePath().normalize();
        if (features == null) {
            features = root.resolve("src/acceptanceTest/resources/features");
        } else if (!features.isAbsolute()) {
            features = root.resolve(features);
        }
        try {
            List<Allow> allows = readAllowlist(allowlist == null ? null : root.resolve(allowlist));
            List<Finding> findings = new ArrayList<>();
            scanTree(root, root.resolve("src/test/java"), Kind.TEST, findings);
            scanTree(root, root.resolve("src/acceptanceTest/java"), Kind.TEST, findings);
            scanTree(root, root.resolve("src/main/java"), Kind.MAIN, findings);
            scanTree(root, features, Kind.FEATURE, findings);
            for (String f : List.of("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
                    "gradle.properties")) {
                scanFile(root, root.resolve(f), Kind.BUILD, findings);
            }
            for (Path script : buildLogic(root)) {
                scanFile(root, script, Kind.BUILD, findings);
            }
            for (Path script : includedBuilds(root)) {
                scanFile(root, script, Kind.BUILD, findings);
            }
            for (String dir : List.of("src/main/resources", "src/test/resources", "src/acceptanceTest/resources")) {
                for (String f : List.of("junit-platform.properties", "cucumber.properties")) {
                    scanFile(root, root.resolve(dir).resolve(f), Kind.PROPS, findings);
                }
            }
            List<Finding> reported = findings.stream().filter(f -> !allowed(f, allows)).toList();
            List<String> structural = structuralProblems(root);
            return print(reported, findings.size() - reported.size(), structural, out);
        } catch (IOException e) {
            err.println("IntegrityCheck: " + e);
            return 2;
        }
    }

    /** Other places build logic can hide: extra script plugins under gradle/ and buildSrc/. */
    static List<Path> buildLogic(Path root) throws IOException {
        List<Path> scripts = new ArrayList<>();
        Path gauntlet = root.resolve("gauntlet/gauntlet.gradle");
        for (String dir : List.of("gradle", "buildSrc")) {
            Path d = root.resolve(dir);
            if (!Files.isDirectory(d)) {
                continue;
            }
            try (Stream<Path> s = Files.walk(d)) {
                s.filter(Files::isRegularFile)
                        .filter(p -> !p.equals(gauntlet) && !p.toString().contains("/build/"))
                        .filter(p -> p.toString().matches(".*\\.(gradle|gradle\\.kts|kt|groovy|java)$"))
                        .sorted().forEach(scripts::add);
            }
        }
        return scripts;
    }

    /**
     * Build scripts of the builds this one includes (settings.gradle: includeBuild("../lib")): they run inside
     * this build too, so they are scanned with the same rules (reported as ../lib/build.gradle).
     */
    static List<Path> includedBuilds(Path root) throws IOException {
        List<Path> scripts = new ArrayList<>();
        Pattern include = Pattern.compile("includeBuild\\s*\\(?\\s*['\"]([^'\"]+)['\"]");
        for (String f : List.of("settings.gradle", "settings.gradle.kts")) {
            Path settings = root.resolve(f);
            if (!Files.isRegularFile(settings)) {
                continue;
            }
            Matcher m = include.matcher(Files.readString(settings, StandardCharsets.UTF_8));
            while (m.find()) {
                Path dir = root.resolve(m.group(1)).normalize();
                for (String b : List.of("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
                        "gradle.properties")) {
                    Path p = dir.resolve(b);
                    if (Files.isRegularFile(p)) {
                        scripts.add(p);
                    }
                }
            }
        }
        return scripts;
    }

    static List<String> structuralProblems(Path root) throws IOException {
        List<String> problems = new ArrayList<>();
        boolean applied = false;
        for (String f : List.of("build.gradle", "build.gradle.kts")) {
            Path p = root.resolve(f);
            if (Files.isRegularFile(p) && Files.readString(p, StandardCharsets.UTF_8).contains("gauntlet.gradle")) {
                applied = true;
            }
        }
        if (!applied) {
            problems.add("INTEGRITY build script does not apply gauntlet/gauntlet.gradle");
        }
        return problems;
    }

    static int print(List<Finding> findings, int allowedCount, List<String> structural, PrintStream out) {
        for (Finding f : findings) {
            out.println("INTEGRITY " + f.rule().id() + " " + f.path() + ":" + f.line() + "  " + f.rule().why()
                    + "  |  " + abbreviate(f.text().trim()));
        }
        structural.forEach(out::println);
        int total = findings.size() + structural.size();
        if (total == 0) {
            out.println("Integrity check: OK" + (allowedCount > 0 ? " (" + allowedCount + " allowlisted)" : ""));
            return 0;
        }
        out.println("Integrity check: FAILED - " + total + " finding(s). Fix the cause instead of hiding it.");
        out.println("  Only the human can accept a finding, in gauntlet/config/integrity-allowlist.txt (path-glob RULE-ID).");
        return 1;
    }

    static void scanTree(Path root, Path dir, Kind kind, List<Finding> findings) throws IOException {
        if (!Files.isDirectory(dir)) {
            return;
        }
        String ext = kind == Kind.FEATURE ? ".feature" : ".java";
        List<Path> files;
        try (Stream<Path> s = Files.walk(dir)) {
            files = s.filter(p -> p.toString().endsWith(ext)).sorted().toList();
        }
        for (Path p : files) {
            scanFile(root, p, kind, findings);
        }
    }

    static void scanFile(Path root, Path file, Kind kind, List<Finding> findings) throws IOException {
        if (!Files.isRegularFile(file)) {
            return;
        }
        String rel = root.relativize(file.toAbsolutePath().normalize()).toString().replace('\\', '/');
        List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
        for (int i = 0; i < lines.size(); i++) {
            String line = lines.get(i);
            boolean comment = isComment(line, kind);
            for (Rule r : RULES) {
                if (r.kind() == kind && (r.includeComments() || !comment) && r.pattern().matcher(line).find()
                        && !(r.id().equals("B1") && harmlessTask(lines, i))) {
                    findings.add(new Finding(rel, i + 1, r, line));
                }
            }
        }
    }

    /**
     * "enabled = false" inside the innermost block that configures a packaging/doc task (e.g. Spring Boot's
     * plain jar). Only that form is exempt - ignoreFailures or onlyIf never are.
     */
    static boolean harmlessTask(List<String> lines, int index) {
        if (!DISABLED.matcher(lines.get(index)).find()) {
            return false;
        }
        int depth = 0;
        for (int j = index; j >= Math.max(0, index - 30); j--) {
            String line = lines.get(j);
            int closes = count(line, '}');
            int opens = count(line, '{');
            if (j == index) {
                if (opens > 1) {
                    return false;                                // several blocks on one line: judge none as harmless
                }
                if (opens == 1) {
                    return harmlessSingleLine(line);           // single-line block: enabled=false must sit inside it
                }
                continue;
            }
            depth += closes - opens;
            if (depth < 0) {
                // the innermost enclosing block opener must be harmless AND the assignment on this line
                // must target that harmless task itself, not a gate task (jar { test.enabled = false }).
                return harmlessOpener(line) && disabledTargetsHarmless(lines.get(index), closureParam(lines, j));
            }
        }
        return false;
    }

    /**
     * True only when the block opened on this line is itself a packaging/doc task. The harmless name must
     * be the task reference right before '{', not any name elsewhere on the line: {@code test { dependsOn(jar);
     * enabled = false }} disables tests and is not exempt, while {@code tasks.named("jar") { enabled = false }} is.
     */
    static boolean harmlessOpener(String line) {
        int brace = line.indexOf('{');
        if (brace < 0) {
            return false;
        }
        String opener = line.substring(0, brace).trim();
        int semi = opener.lastIndexOf(';');                      // last statement before the block opens
        if (semi >= 0) {
            opener = opener.substring(semi + 1).trim();
        }
        return HARMLESS_TASK.matcher(opener + " {").find();
    }

    /**
     * A block opened on this line is harmless only when every disabled statement on the line sits INSIDE the
     * block's braces and the block opener is a packaging/doc task. {@code test.enabled = false; jar { }} and
     * {@code jar { }; test.enabled = false } disable test with a separate statement outside the jar block, so
     * they are not exempt; {@code jar { enabled = false }} is. The closing brace may sit on a LATER line
     * ({@code jar { enabled = false} newline {@code }}): then everything after '{' on this line is inside the block.
     */
    static boolean harmlessSingleLine(String line) {
        int open = line.indexOf('{');
        if (open < 0) {
            return false;
        }
        int close = line.lastIndexOf('}');
        int insideEnd = close > open ? close : line.length();   // no '}' here: the block continues on the next line
        String opener = line.substring(0, open).trim();
        int semi = opener.lastIndexOf(';');
        if (semi >= 0) {
            opener = opener.substring(semi + 1).trim();
        }
        if (!HARMLESS_TASK.matcher(opener + " {").find()) {
            return false;
        }
        String param = closureParam(line);
        Matcher m = DISABLED.matcher(line);
        while (m.find()) {
            if (m.start() < open || m.start() > insideEnd) {
                return false;                              // a disabled statement before/after the block, not inside it
            }
            if (!receiverIsHarmless(line, m.start(), param)) {
                return false;                              // disables a gate task (test), not the harmless block's task
            }
        }
        return true;
    }

    /** Every disabled statement on the line must target the harmless task itself, not a gate task. */
    static boolean disabledTargetsHarmless(String line, String closureParam) {
        Matcher m = DISABLED.matcher(line);
        while (m.find()) {
            if (!receiverIsHarmless(line, m.start(), closureParam)) {
                return false;
            }
        }
        return true;
    }

    /** The closure's single named parameter ({@code jar { t -> }}), bound to the task itself; null for a
     *  closure with no/other parameters. The declaration may continue on the line after the opening brace. */
    static String closureParam(List<String> lines, int openerIndex) {
        String opener = lines.get(openerIndex);
        int brace = opener.indexOf('{');
        if (brace < 0) {
            return null;
        }
        String tail = opener.substring(brace + 1);
        int lineComment = tail.indexOf("//");
        if (lineComment >= 0) {
            tail = tail.substring(0, lineComment);
        }
        String param = closureParamText(tail);
        if (param != null || !tail.trim().isEmpty()) {
            return param;
        }
        for (int i = openerIndex + 1; i < lines.size(); i++) {
            String next = lines.get(i);
            if (next.trim().isEmpty()) {
                continue;
            }
            return closureParamText(next);
        }
        return null;
    }

    static String closureParam(String openerLine) {
        int brace = openerLine.indexOf('{');
        return brace < 0 ? null : closureParamText(openerLine.substring(brace + 1));
    }

    static String closureParamText(String text) {
        Matcher m = CLOSURE_PARAM.matcher(text);
        return m.find() ? m.group(1) : null;
    }

    /**
     * The receiver left of {@code enabled = false}/{@code setEnabled(false)} must be empty (a bare assignment
     * configures the enclosing harmless task), name a harmless task, or be {@code delegate}/{@code this}/{@code it}
     * or the closure's own named parameter - which inside the harmless task's configuration block refer to that
     * task itself. {@code test.enabled}, {@code tasks.test.enabled} and {@code tasks.named("test").enabled} disable
     * a gate task and are never exempt, even inside {@code jar { }}.
     */
    static boolean receiverIsHarmless(String line, int matchStart, String closureParam) {
        String before = line.substring(0, matchStart).stripTrailing();
        if (!before.endsWith(".")) {
            return true;                                   // bare enabled = false / setEnabled(false)
        }
        String recv = before.substring(0, before.length() - 1).stripTrailing();
        Matcher ref = TASK_REF.matcher(recv);
        String name;
        if (ref.find()) {
            name = ref.group(1);                           // tasks.named("jar") -> jar
        } else {
            Matcher id = LAST_ID.matcher(recv);
            name = id.find() ? id.group(1) : recv;         // tasks.test -> test, jar -> jar, delegate -> delegate
        }
        if (name.equals("delegate") || name.equals("this") || name.equals("it")
                || (closureParam != null && name.equals(closureParam))) {
            return true;                                   // the enclosing block's own task (already verified harmless)
        }
        return HARMLESS_NAME.matcher(name).matches();
    }

    static int count(String s, char c) {
        return (int) s.chars().filter(ch -> ch == c).count();
    }

    static boolean isComment(String line, Kind kind) {
        String t = line.trim();
        if (kind == Kind.FEATURE || kind == Kind.PROPS) {
            return t.startsWith("#");
        }
        return t.startsWith("//") || t.startsWith("*") || t.startsWith("/*");
    }

    static boolean allowed(Finding f, List<Allow> allows) {
        for (Allow a : allows) {
            if (a.ruleId().equals(f.rule().id()) && a.matcher().matches(Path.of(f.path()))) {
                return true;
            }
        }
        return false;
    }

    static List<Allow> readAllowlist(Path file) throws IOException {
        List<Allow> list = new ArrayList<>();
        if (file == null || !Files.isRegularFile(file)) {
            return list;
        }
        for (String raw : Files.readAllLines(file, StandardCharsets.UTF_8)) {
            String line = raw.replaceAll("#.*$", "").trim();
            if (line.isEmpty()) {
                continue;
            }
            String[] parts = line.split("\\s+");
            if (parts.length >= 2) {
                list.add(new Allow(FileSystems.getDefault().getPathMatcher("glob:" + parts[0]), parts[1]));
            }
        }
        return list;
    }

    static Rule rule(String id, Kind kind, String regex, boolean includeComments, String why) {
        return new Rule(id, kind, Pattern.compile(regex), includeComments, why);
    }

    static String abbreviate(String s) {
        return s.length() <= 100 ? s : s.substring(0, 97) + "...";
    }
}

===== END FILE gauntlet/tools/IntegrityCheck.java =====

===== BEGIN FILE gauntlet/tools/PitSummary.java =====
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Pattern;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

/**
 * Agent-friendly summary of a PIT mutations.xml report, and the part of the mutation gate PIT cannot do.
 *
 * <p>Lists every SURVIVED and NO_COVERAGE mutant as {@code Class:line method - description}
 * so an agent can go straight to the weak test. It also counts mutation sites per source file:
 * above {@code --max-per-file} it prints a warning - Uncle Bob's swarm-forge uses the
 * mutation-site count as a hint that a module mixes jobs (split it if it has more than one job,
 * never just to chase the number).
 *
 * <p>RUN_ERROR, MEMORY_ERROR and NON_VIABLE mutants are printed as UNVERIFIED: PIT 1.22.1 counts them
 * as detected ({@code DetectionStatus.RUN_ERROR(true)}), so test strength stays 100 % even though the
 * tests never ran against the mutant (the test JVM crashed on {@code redefineClasses}, typically on a
 * record). A RUN_ERROR mutant that is not listed in {@code --allowlist} fails this tool (exit 1), and
 * with it the mutation gate: a human verifies by reading the tests that the mutant would be killed and
 * adds {@code Class#method Mutator # which test} to the allowlist. MEMORY_ERROR and NON_VIABLE are
 * reported only: the first is PIT's own verdict on a runaway mutant, the second is bytecode the JVM
 * rejected, not a code change. TIMED_OUT is deliberately NOT unverified: the tests ran against the
 * mutant and it hung them (an infinite loop), so PIT counts it as a real kill ({@code TIMED_OUT(true)});
 * it is a detection, not a crash that skipped the tests.
 *
 * <pre>
 * java PitSummary.java --report build/reports/pitest/mutations.xml [--max-per-file 100]
 *                      [--allowlist gauntlet/config/pit-runerror-allowlist.txt]
 * </pre>
 * Exit codes: 0 = summary printed (or no report), 1 = unverified RUN_ERROR mutants outside the allowlist,
 * 2 = usage or unreadable report / allowlist.
 */
public class PitSummary {

    static final String RUN_ERROR = "RUN_ERROR";
    static final List<String> UNVERIFIED = List.of(RUN_ERROR, "MEMORY_ERROR", "NON_VIABLE");

    record Mutant(String status, String sourceFile, String mutatedClass, String method,
                  int line, String mutator, String description) {
        String simpleMutator() {
            return mutator.substring(mutator.lastIndexOf('.') + 1);
        }

        String display() {
            return mutatedClass + ":" + line + " " + method + "() - " + description + " [" + simpleMutator() + "]";
        }
    }

    /** One allowlist line: exact class, glob method, glob mutator ({@code *} = any). */
    record Allowed(String mutatedClass, Pattern method, Pattern mutator) {
        boolean covers(Mutant m) {
            return mutatedClass.equals(m.mutatedClass()) && method.matcher(m.method()).matches()
                    && mutator.matcher(m.simpleMutator()).matches();
        }
    }

    public static void main(String[] args) {
        System.exit(run(args, utf8(FileDescriptor.out), utf8(FileDescriptor.err)));
    }

    static PrintStream utf8(FileDescriptor fd) {
        return new PrintStream(new FileOutputStream(fd), true, StandardCharsets.UTF_8);
    }

    static int run(String[] args, PrintStream out, PrintStream err) {
        String report = null;
        String allowlist = null;
        int maxPerFile = 100;
        try {
            for (int i = 0; i < args.length; i += 2) {
                if (i + 1 >= args.length) {
                    throw new IllegalArgumentException("option " + args[i] + " needs a value");
                }
                switch (args[i]) {
                    case "--report" -> report = args[i + 1];
                    case "--max-per-file" -> maxPerFile = Integer.parseInt(args[i + 1]);
                    case "--allowlist" -> allowlist = args[i + 1];
                    default -> throw new IllegalArgumentException("unknown option " + args[i]);
                }
            }
            if (report == null) {
                throw new IllegalArgumentException("--report is required");
            }
        } catch (RuntimeException e) {
            err.println("PitSummary: " + e.getMessage());
            return 2;
        }
        File xml = new File(report);
        if (!xml.isFile()) {
            out.println("PIT summary: no report at " + report + " (PIT did not run or found nothing to mutate).");
            return 0;
        }
        List<Mutant> mutants;
        List<Allowed> allowed;
        try {
            mutants = parse(xml);
            allowed = allowlist == null ? List.of() : readAllowlist(new File(allowlist));
        } catch (Exception e) {
            err.println("PitSummary: cannot read " + report + " or " + allowlist + ": " + e);
            return 2;
        }
        print(mutants, maxPerFile, out);
        return gate(mutants, allowed, allowlist, out) ? 0 : 1;
    }

    static List<Mutant> parse(File xml) throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setNamespaceAware(false);
        Document doc = f.newDocumentBuilder().parse(xml);
        List<Mutant> list = new ArrayList<>();
        NodeList nodes = doc.getElementsByTagName("mutation");
        for (int i = 0; i < nodes.getLength(); i++) {
            Element m = (Element) nodes.item(i);
            String line = text(m, "lineNumber");
            list.add(new Mutant(m.getAttribute("status"), text(m, "sourceFile"), text(m, "mutatedClass"),
                    text(m, "mutatedMethod"), line.isEmpty() ? 0 : Integer.parseInt(line),
                    text(m, "mutator"), text(m, "description")));
        }
        return list;
    }

    /** {@code fully.qualified.Class#method  Mutator   # reason}; the mutator may be omitted ({@code *}). */
    static List<Allowed> readAllowlist(File file) throws IOException {
        List<Allowed> list = new ArrayList<>();
        if (!file.isFile()) {
            return list;
        }
        for (String raw : Files.readAllLines(file.toPath(), StandardCharsets.UTF_8)) {
            String line = raw;
            int comment = commentStart(line);
            if (comment >= 0) {
                line = line.substring(0, comment);
            }
            String[] tokens = line.trim().split("\\s+");
            if (tokens.length == 0 || tokens[0].isEmpty()) {
                continue;
            }
            int hash = tokens[0].indexOf('#');
            if (hash <= 0) {
                throw new IOException("allowlist line without Class#method: " + raw);
            }
            String mutator = tokens.length > 1 ? tokens[1] : "*";
            list.add(new Allowed(tokens[0].substring(0, hash), glob(tokens[0].substring(hash + 1)), glob(mutator)));
        }
        return list;
    }

    /** A {@code #} starts a comment only after whitespace or at line start: the one inside {@code Class#method} does not. */
    static int commentStart(String line) {
        for (int i = 0; i < line.length(); i++) {
            if (line.charAt(i) == '#' && (i == 0 || Character.isWhitespace(line.charAt(i - 1)))) {
                return i;
            }
        }
        return -1;
    }

    static Pattern glob(String glob) {
        StringBuilder regex = new StringBuilder();
        for (String part : glob.split("\\*", -1)) {
            if (!regex.isEmpty()) {
                regex.append(".*");
            }
            regex.append(Pattern.quote(part));
        }
        return Pattern.compile(regex.toString());
    }

    static void print(List<Mutant> mutants, int maxPerFile, PrintStream out) {
        Map<String, Integer> byStatus = new TreeMap<>();
        Map<String, Integer> perFile = new LinkedHashMap<>();
        for (Mutant m : mutants) {
            byStatus.merge(m.status(), 1, Integer::sum);
            String pkg = m.mutatedClass().contains(".")
                    ? m.mutatedClass().substring(0, m.mutatedClass().lastIndexOf('.')).replace('.', '/') + "/" : "";
            perFile.merge(pkg + m.sourceFile(), 1, Integer::sum);
        }
        out.println("PIT summary: " + mutants.size() + " mutant(s) " + byStatus);
        for (String status : List.of("SURVIVED", "NO_COVERAGE")) {
            for (Mutant m : mutants) {
                if (m.status().equals(status)) {
                    out.println((status.equals("SURVIVED") ? "SURVIVED    " : "NO_COVERAGE ") + m.display());
                }
            }
        }
        for (String status : UNVERIFIED) {
            for (Mutant m : mutants) {
                if (m.status().equals(status)) {
                    out.println(status + " ".repeat(Math.max(1, 12 - status.length())) + m.display()
                            + " - UNVERIFIED: tests did not run");
                }
            }
        }
        for (Map.Entry<String, Integer> e : perFile.entrySet()) {
            if (e.getValue() > maxPerFile) {
                out.println("WARNING " + e.getKey() + " has " + e.getValue() + " mutation sites (> " + maxPerFile
                        + "). If it has more than one job, split it; do not split a one-job module just to chase the count.");
            }
        }
        if (byStatus.getOrDefault("SURVIVED", 0) > 0) {
            out.println("  A surviving mutant is a code change no test noticed: add or sharpen an assertion that");
            out.println("  fails for it. If you believe it is equivalent (cannot be detected), stop and tell the human.");
        }
        if (byStatus.getOrDefault("NO_COVERAGE", 0) > 0) {
            out.println("  NO_COVERAGE lines are not executed by any unit test - cover them or delete dead code.");
        }
    }

    /** The gate: every RUN_ERROR mutant is either human-verified (allowlist) or a red gate. */
    static boolean gate(List<Mutant> mutants, List<Allowed> allowed, String allowlist, PrintStream out) {
        List<Mutant> unverified = new ArrayList<>();
        for (Mutant m : mutants) {
            if (m.status().equals(RUN_ERROR) && allowed.stream().noneMatch(a -> a.covers(m))) {
                unverified.add(m);
            }
        }
        if (unverified.isEmpty()) {
            return true;
        }
        out.println("mutationGate: " + unverified.size() + " RUN_ERROR mutant(s) not verified by any test and not in "
                + (allowlist == null ? "an allowlist" : allowlist) + ":");
        for (Mutant m : unverified) {
            out.println("  " + m.mutatedClass() + "#" + m.method() + " " + m.simpleMutator());
        }
        out.println("  PIT counts RUN_ERROR as detected; this gate does not. The test JVM crashed before the tests ran");
        out.println("  (usually redefineClasses on a record). Read the tests and name the assertion that would fail for");
        out.println("  the mutant, then stop and ask the human to add that line (with the test as the reason) to the");
        out.println("  allowlist - or fix the crash. Agents cannot edit the allowlist.");
        return false;
    }

    static String text(Element parent, String tag) {
        NodeList n = parent.getElementsByTagName(tag);
        return n.getLength() == 0 ? "" : n.item(0).getTextContent().trim();
    }
}

===== END FILE gauntlet/tools/PitSummary.java =====

