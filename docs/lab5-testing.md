# Лабораторная работа № 5. Тестирование: сценарии, сквозной сценарий и спецификации unit-тестов

Проект: «Система мониторинга и управления распределённой телеметрической сетью».
Команда и зоны ответственности — [README §1](../README.md). Требования — [User stories и MVP](<User stories и MVP.md>)
(истории `US-xx`, критерии приёмки `AC-xx`), модули — [Описание архитектуры](<Описание архитектуры.md>).
Интеграционные сценарии стенда и формат их описания — [TESTING.md](TESTING.md), запуск — [CI.md](CI.md).

Документ написан постфактум: тесты уже реализованы и зелёные, поэтому каждая спецификация ниже указывает на
реальную проверку (имя теста в обратных кавычках) и сопоставлена с критерием приёмки.

## 1. Объём тестирования

Покрывается ядро MVP: приём и передача телеметрии, правила доступа и актуальности, формат кадра LMash v1.

| Модуль (лаб. № 3) | Каталог | Истории / критерии | Где живут тесты | Запуск |
|---|---|---|---|---|
| Протокол LMash v1 | `protocol/`, кодек `emulator/lmash_v1.py` | US-05, US-10; AC-04.1, AC-06.1 | `emulator/tests/test_lmash_v1_spec.py` | `make test` |
| Эмулятор периферии и CLI сценариев | `emulator/` | US-05, US-25; AC-11.1 | `emulator/tests/test_cli_validation_spec.py`, `test_cli.py` | `make test` |
| Edge-сервис (кадры UART/CAN → MQTT) | `rpi-app/` | US-05, US-09, US-13; AC-04.1, AC-06.2, AC-08.4 | `rpi-app/tests/test_*_edge.cpp` | `make test` (ctest) |
| Стенд и CI (раннер сценариев, guard) | `ci/`, `tests/e2e/` | US-23, US-25; AC-09, AC-11 | `ci/test_*_spec.py` | `make test`, `make e2e` |
| Android-приложение (домен, протокол, безопасность) | `mobile_app/` | US-03, US-06, US-07, US-08, US-12, US-13; AC-02, AC-04, AC-05, AC-08 | `mobile_app/app/src/test/java/…` | JUnit 4 (см. §6) |

Не покрывается этой работой: UI-фрагменты, MapLibre, Room DAO и `KeyStoreManager` (нужен Android),
ручная приёмка (AC-12), сборка образа Yocto (AC-10).

Размер набора (всё зелёное на момент коммита):

| Набор | Новых случаев | Класс проверки |
|---|---|---|
| edge, C++ (ctest `lmash_edge`, `telemetry_edge`, `broker_config_edge`, `mqtt_edge`) | 84 | unit |
| эмулятор, Python | 175 | unit |
| ci, Python | 184 | unit + проверка файлов сценариев |
| Android, JUnit 4 | 216 (всего 267 с прежними) | unit |
| интеграционные сценарии `tests/e2e` | 2 (E2E-01, E2E-02) | e2e |

## 2. Тестовые сценарии

Формат «Дано – Когда – Тогда». Классы случаев подобраны по эквивалентности и границам: порог актуальности
позиции 30 с проверяется значениями 30 и 31 с, длина кадра — 53, 54 и 55 байт.

| ID | История / критерий | Класс | Дано | Когда | Тогда | Автоматизация |
|---|---|---|---|---|---|---|
| TS-01 | US-07, AC-04.4 | успешный | Валидная позиция участника, возраст 30 с | оценивается статус позиции | статус `CURRENT` | `PositionStatusEvaluatorTest.ageExactly30SecondsIsCurrent` |
| TS-02 | US-07, AC-04.4 | граничный | Та же позиция, новых пакетов нет, возраст 31 с | оценивается статус позиции | статус `STALE`; один и тот же пакет сменил статус `CURRENT → STALE` без прихода новых данных | `ageExactly31SecondsIsStale`, `sameFixBecomesStaleWithoutNewPackets` |
| TS-03 | US-07, AC-04.5 | отрицательный | Пакет с координатами 0°, 0° и качеством «хорошее» | оценивается статус позиции | статус `UNKNOWN`, маркер в точке 0°, 0° не рисуется | `zeroZeroWithGoodQualityIsUnknown` |
| TS-04 | US-03, AC-02.1 | отрицательный | Иерархия из пяти уровней, у батальона есть потомки | батальон переносят под своего потомка (в том числе глубокого) | перенос отклонён (`IllegalArgumentException`, «AC-02.1»), дерево и сохранённые строки не изменились | `UnitHierarchyManagerTest.moveToDeepDescendantIsRejectedAndTreeIsUnchanged`, `rejectedMoveDoesNotTouchDao` |
| TS-05 | US-25, AC-11 | отрицательный | Edge подключён к брокеру с TLS и ACL; подписчик встал на `<root>/#` | по UART подан кадр с `version = 2`, затем валидный | edge пишет `unsupported LMash version 2`, до брокера дошёл только валидный кадр, лишнего нет | `tests/e2e/E2E-02-bad-version.json` (`make e2e`) |
| TS-06 | US-10, AC-06 | граничный | Кадр размером 53, 54 и 55 байт | стенд считает ожидаемое для брокера | доходит только кадр в 54 байта | `ci/test_stand_spec.py` `ExpectedLines.test_frame_length_53/54/55…` |
| TS-07 | US-05, AC-04.1 | успешный | Вектор `protocol/vectors/telemetry-v1.json` | кадр кодируется эмулятором и разбирается приложением | байты равны `wireHex`, все 17 полей совпадают | `test_vectors_encode_byte_for_byte`, `LMashPayloadTest.telemetryVectorDecodesToDocumentedFields` |

## 3. Сквозной сценарий (E2E)

**E2E-01. Телеметрия бойца доходит от датчика до оператора (US-05 → US-06 → US-07, AC-04, AC-11.2).**

Автоматизация: `tests/e2e/E2E-01-telemetry.json`, `make e2e` (host), `EDGE=qemu` (образ Yocto),
`stand.yml` (с Android-эмулятором и реальным приложением), `make demo` — то же в интерактивном виде.

1. Исходно: поднят брокер MQTT с TLS и ACL, подписчик пользователь `app` стоит на `mesh-a/7F10/21A0/#`;
   edge запущен и напечатал `edge: reading frames from` (раньше кадр может потеряться — см. TESTING.md).
2. Эмулятор по UART подаёт кадр LMash v1 из `emulator/mocks/telemetry-v1.json`
   (userId 1001, sequence 471). *(Эмулятор → Протокол)*
3. Edge принимает 54 байта, проверяет версию и тип, формирует топик
   `mesh-a/7F10/21A0/telemetry/to/<dst>/from/<src>` и публикует на брокер. *(Edge → Брокер)*
4. Подписчик получает ровно 54 байта, равных `wireHex`, по топику схемы §9 архитектуры.
5. Приложение на Android-эмуляторе подписано на тот же корень, разбирает пакет и пишет
   `Телеметрия сохранена от бойца [1001], seq=471`. *(Брокер → Приложение)*
6. **Итог:** оператор получил показатели бойца, дошедшие от периферии без потерь и искажений; невалидный кадр
   (E2E-02) этот путь не проходит. Раннер пишет `build/stand/junit.xml`, провал или таймаут — код выхода 1.

Задействованные модули: Эмулятор периферии, Протокол LMash v1, Edge-сервис, брокер MQTT (стенд), Android-приложение.

## 4. Спецификации unit-тестов

Полный реестр случаев — в самих тестах: имена методов и docstring (в `ci/*_spec.py` у каждого теста есть
идентификатор `UT-CI-nn` и строка «вход | ожидание | класс»). Ниже — спецификации по основным модулям: правила и логика,
которые проверять важнее всего. Классы случаев: у — успешный, о — отрицательный, г — граничный.

### 4.1. Edge-сервис (`rpi-app`)

| № | Модуль / функция | Вход | Ожидаемый выход | Класс |
|---|---|---|---|---|
| UT-01 | `lmash_topic` / `valid_telemetry_minimal_frame` | кадр 54 байта, version 1, type 0, остальное 0, root `r` | `true`; топик `r/telemetry/to/0000000000000000/from/0000000000000000` | у |
| UT-02 | `lmash_topic` / `length_53_rejected` | валидный кадр, размер 53 | `false`; ошибка `frame is 53 bytes, expected 54`; выходной топик не изменён | г |
| UT-03 | `lmash_topic` / `length_55_rejected` | буфер 55 байт | `false`; `frame is 55 bytes, expected 54` | г |
| UT-04 | `lmash_topic` / `every_version_except_one_rejected` | version 0..255 | принимается только 1, остальные 255 значений отклонены | г |
| UT-05 | `lmash_topic` / `message_type_only_zero_and_one_accepted` | messageType 0..255 | принимаются 0 и 1, ошибка `unknown messageType N` для остальных | г |
| UT-06 | `lmash_topic` / `id_max_u64_formats_sixteen_f` | dest = serial = 2^64−1 | `…/to/FFFFFFFFFFFFFFFF/from/FFFFFFFFFFFFFFFF` | г |
| UT-07 | `lmash_topic` / `vector_telemetry_topic` | `protocol/vectors/telemetry-v1.json` | топик строится по полям вектора, `payloadSize == 54` | у |
| UT-08 | `parse_broker_config` / `port_zero_rejected`, `port_65536_rejected` | `port=0`, `port=65536` | `false`; `line N: port: expected 1-65535, got '…'` | г |
| UT-09 | `parse_broker_config` / `required_each_field_missing` | нет host, нет cafile, нет topic_root (по очереди) | `host is required`, `cafile is required`, `topic_root is required` | о |
| UT-10 | `parse_broker_config` / `port_default_when_absent` | ключа `port` нет | `true`, порт 8883 | у |
| UT-11 | `to_telemetry_line` / `standard_max_id_full_payload` | id 0x7FF, standard, 8 байт 0xFF | `7FF FFFFFFFFFFFFFFFF` | г |
| UT-12 | `Mqtt::publish` / `publish_before_open_fails` | клиент не открыт | `false`; `MQTT client is not open` | о |

### 4.2. Протокол и эмулятор (`emulator`)

| № | Модуль / функция | Вход | Ожидаемый выход | Класс |
|---|---|---|---|---|
| UT-13 | `lmash_v1.encode` / `test_vectors_encode_byte_for_byte` | поля каждого файла из `protocol/vectors/` | `encode(fields).hex() == wireHex` | у |
| UT-14 | `lmash_v1.encode` / `test_below_min_and_above_max_rejected_per_field` | каждое поле на min−1 и max+1 | `ProtocolError: <поле>: outside N-bit range` | г |
| UT-15 | `lmash_v1.encode` / `test_version_other_than_1_rejected` | version 0, 2, 255, 256, −1 | `ProtocolError: version: expected 1` | о |
| UT-16 | `lmash_v1.encode` / `test_command_rejects_nonzero_telemetry_bytes` | COMMAND с ненулевым полем телеметрии | `ProtocolError: <поле>: COMMAND telemetry bytes must be zero` | о |
| UT-17 | `lmash_v1.encode` / `test_little_endian_byte_order` | sequence = 0x01020304 | байты 5..8 = `04 03 02 01` | у |
| UT-18 | `cli.validate` / `test_unknown_top_level_key` | сценарий с лишним ключом `extra` | `CliError: scenario: unknown fields: extra` | о |
| UT-19 | `cli.validate` / `test_data_length_boundary` | `can.send` с 0, 8, 9 байтами данных | 0 и 8 принимаются; 9 — `at most 8 bytes` | г |
| UT-20 | `cli.validate` / `test_standard_id_boundary` | CAN id 0x7FF и 0x800 без `extended` | 0x7FF принят; 0x800 — `standard CAN ID exceeds 0x7ff` | г |
| UT-21 | `cli.validate` / `test_requires_process` | `stdout.expect` без `process` | `CliError: stdout.expect requires process` | о |
| UT-22 | `cli.main validate` / `test_validate_ok` | корректный файл сценария | код 0, `valid scenario` | у |

### 4.3. Стенд и CI (`ci`)

| № | Модуль / функция | Вход | Ожидаемый выход | Класс |
|---|---|---|---|---|
| UT-23 | `stand.expected_lines` / `test_frame_length_54_is_expected` | кадр 54 байта, version 1, type 0 | одна ожидаемая строка «топик payload-hex» | г |
| UT-24 | `stand.expected_lines` / `test_version_2_is_not_expected` | кадр 54 байта, version 2 (как в E2E-02) | пустой список: до брокера не должен дойти | г |
| UT-25 | `stand.expected_lines` / `test_order_of_frames_is_preserved` | три валидных кадра подряд | строки в том же порядке, не отсортированы | у |
| UT-26 | `stand.check_delivery` / `test_nothing_arrived_is_failure` | ожидается 1 строка, принято 0 | сообщение `broker saw different messages` (отказ, не пропуск) | о |
| UT-27 | `stand.check_delivery` / `test_single_byte_difference_fails` | payload отличается одним байтом | сообщение о расхождении | г |
| UT-28 | `stand.write_junit` / `test_failure_count` | три результата, два с проблемой | `tests="3" failures="2"`, два элемента `failure` | у |
| UT-29 | `stand.main` / `test_one_failure_exit_1` | один сценарий падает | код выхода 1, `FAIL <имя>` на stdout | о |
| UT-30 | `guard.check_file_length` / `test_600_lines_pass`, `test_601_lines_fail` | файл `.cpp` в 600 и 601 строку | 600 проходит; 601 — `601 lines (limit 600) -- split it` | г |
| UT-31 | `tests/e2e` / `test_first_event_waits_for_reading_frames` | `events[0]` каждого сценария | `stdout.expect` с текстом `edge: reading frames from…` | у |

### 4.4. Android-приложение (`mobile_app`)

| № | Класс / метод | Вход | Ожидаемый выход | Класс |
|---|---|---|---|---|
| UT-32 | `PositionStatusEvaluator` / `ageExactly30SecondsIsCurrent` | валидная позиция, возраст 30 с | `CURRENT` | г |
| UT-33 | `PositionStatusEvaluator` / `ageExactly31SecondsIsStale` | возраст 31 с | `STALE` | г |
| UT-34 | `PositionStatusEvaluator` / `zeroQualityIsUnknownEvenWhenFresh` | качество 0, возраст 0 | `UNKNOWN` | о |
| UT-35 | `PositionStatusEvaluator` / `ageCalculationClampsFutureTimestampToZero` | метка 1500, «сейчас» 1000 | возраст 0 | г |
| UT-36 | `UnitHierarchyManager` / `moveToDirectChildIsRejected` | перенести узел под его дочерний | `IllegalArgumentException`, дерево не изменилось | о |
| UT-37 | `UnitHierarchyManager` / `moveUnknownNodeReturnsFalse` | перенос узла id 999 | `false` | о |
| UT-38 | `UnitHierarchyManager` / `telemetryTopicForSquadSubscribesToWholeSubtree` | отделение / батальон, сети mesh-a и mesh-b | `mesh-a/BN1/CO2/PL3/SQ1/#`; `mesh-b/BN1/#` | у |
| UT-39 | `UnitHierarchyManager` / `ordinarySoldiersCannotCommandPeers` | пары рядовых бойцов | `isSubordinate` = `false` во всех | о |
| UT-40 | `UnitHierarchyManager` / `persistedHierarchyIsRestoredOnNextStart` | добавить боец 1004, новый менеджер на том же DAO | боец 1004 на месте (AC-03.4) | у |
| UT-41 | `LMashPayload` / `telemetryVectorEncodesToExactWireBytes` | поля `telemetry-v1.json` | `toBytes` равен `wireHex` | у |
| UT-42 | `LMashPayload` / `shortArrayOf53BytesIsRejected`, `exactly54ZeroBytesParse` | 53 байта; 54 нулевых байта | `IllegalArgumentException`; разбор успешен | г |
| UT-43 | `LMashPayload` / `allOnesBytesParseAsUnsignedFields` | 54 × `0xFF` | беззнаковые поля максимальны, знаковые = −1 | г |
| UT-44 | `MqttTopicBuilder` / `hexIdOfNegativeLongIsUnsignedRepresentation` | −1; `Long.MIN_VALUE` | `FFFFFFFFFFFFFFFF`; `8000000000000000` | г |
| UT-45 | `MqttTopicBuilder` / `nullHierarchyPathIsRejected` | путь `null` | `NullPointerException` | о |
| UT-46 | `SquadAlertManager` / `alertIsNewAgainAfterRecovery` | critical → OK → critical | третье событие `isNewAlert = true` | у |
| UT-47 | `TacticalCommand` / `returnCommandMatchesProtocolVectorWireBytes` | RETURN с параметрами `command-return-v1.json` | байты равны `wireHex` вектора | у |
| UT-48 | `CryptoException` / `errorCodesCoverAcceptanceCriteriaSet` | значения `CryptoErrorCode` | ровно `UNKNOWN_KEY`, `DECRYPTION_FAILED`, `AUTHENTICATION_FAILED`, `UNSUPPORTED_CRYPTO` (AC-08.2) | у |
| UT-49 | `TacticalNavigationCalculator` / `distanceAcrossAntimeridianIsShort` | (0; 179,5) → (0; −179,5) | 111195 ± 5 м | г |

## 5. Что найдено при написании тестов

Тесты фиксируют фактическое поведение или спецификацию; расхождения кода и документации в код не вносились,
перечислены для команды. Ничего из этого тесты не закрепляют как «правильное» там, где оно противоречит
спецификации.

| № | Где | Что | Чем важно |
|---|---|---|---|
| F-1 | `mobile_app` `LMashPayload.fromBytes` | не проверяет `version` и принимает массив длиннее 54 байт; 64-битные id читаются знаковыми | спецификация требует отклонять неизвестную версию и неверную длину |
| F-2 | `mobile_app` `UnitHierarchyManager.moveNode` | пути потомков перенесённого узла не пересчитываются | противоречит AC-02.1 (пересчёт topics при перемещении) |
| F-3 | `mobile_app` `isSubordinate` | `isSubordinate(x, x)` истинно даже для отсутствующего пользователя; права «командира» зашиты по id 1001 и по слову в имени | слабая проверка полномочий (AC-02.2) |
| F-4 | `mobile_app` `PositionStatusEvaluator` | метка из далёкого будущего даёт `CURRENT` | AC: пакет с недопустимой меткой не становится актуальным |
| F-5 | `rpi-app` `Mqtt::publish` | всегда QoS 1; спецификация: QoS 0 для TELEMETRY | без брокера не проверить, в unit-тестах не отражено |
| F-6 | `ci/stand.py` `write_junit` | управляющие символы в логе (ANSI, консоль QEMU) делают `junit.xml` невалидным XML | отчёт не читается именно при падении |
| F-7 | `emulator/cli.py` | `timeout_ms = 0` у `stdout.expect` почти всегда даёт таймаут, даже если текст уже в логе; нехэшируемое значение в `action` даёт `TypeError` вместо `CliError` | мелкие дефекты валидации |
| F-8 | `ci/guard.py` | проверка orphan-файлов по подстроке имени (`a.hpp` засчитывается из-за `data.hpp`); файл не закрывается в `check_file_length` | возможны ложные пропуски |

## 6. Запуск

| Что | Команда |
|---|---|
| Всё быстрое: сборка, ctest, Python-тесты, guard | `make check` (на Mac — `make docker-check`) |
| Только Python-спецификации | `python3 -I -m unittest discover -s emulator/tests -p 'test_*spec.py'` и `… -s ci -p 'test_*spec.py'` |
| Интеграционные сценарии | `make e2e` |
| Android JUnit | Gradle: `./gradlew :app:testDebugUnitTest` в `mobile_app/`. Набор из 267 тестов чистой логики проверен через `javac` + `JUnitCore` (JUnit 4.13.2, Room-аннотации и заглушка `LiveData`) в контейнере `eclipse-temurin:17-jdk`; сам запуск Gradle на этой машине не проверялся (нет Android SDK) |

Какие проверки автоматизируем в первую очередь: Python-спецификации и ctest уже входят в `make test` и `ci.yml`;
следующий шаг — подключить `./gradlew testDebugUnitTest` в `ci.yml` (AC-09.1) и закрыть находки F-1…F-4.
Входят ли тесты в Definition of Done: изменение в `emulator/`, `rpi-app/`, `ci/` считается готовым, только когда
зелёные `make check` и `make e2e`.

## 7. Ответы на контрольные вопросы

1. **Почему тестирование не доказывает отсутствие ошибок?** Входов бесконечно много, проверяется конечная выборка;
   прошедший набор говорит лишь, что на этих данных ошибок нет. Взамен команда получает быстрый сигнал о регрессии
   (CI красный на SHA), документированные ожидания и уверенность при изменении кода: F-1…F-8 найдены именно тестами.
2. **Как критерии приёмки связаны со сценариями?** Критерий «Дано – Когда – Тогда» превращается в проверку:
   «Дано» — исходное состояние и фикстура, «Когда» — вызов функции или событие сценария, «Тогда» — утверждение
   о результате. Например, AC-04.4 дал TS-01/TS-02 (30 и 31 секунда), AC-02.1 — TS-04 (цикл в иерархии).
3. **Классы эквивалентности и граничные значения.** Входы делят на группы с одинаковым поведением и берут по
   представителю (длина кадра: верная, короткая, длинная; версия: 1, прочие). Границы проверяют по обе стороны:
   порт 0/1/65535/65536, возраст позиции 30/31 с, кадр 53/54/55 байт, id 0 и 2^64−1.
4. **Unit-тест и сквозной сценарий.** Unit-тест проверяет одну функцию в изоляции (`lmash_topic`, `encode`,
   `PositionStatusEvaluator`): быстрый, точно указывает место ошибки, поэтому их сотни. E2E-01 проходит весь путь
   эмулятор → edge → брокер → приложение: медленный (брокер, процессы, эмулятор Android), зато показывает, что система
   решает задачу как целое; таких один-два.
5. **Что содержит спецификация unit-теста?** Что проверяем, вход (данные и исходное состояние), ожидаемый выход
   и класс случая. Выход должен быть проверяемым, иначе нельзя однозначно сказать «прошло / не прошло»: вместо
   «корректно обрабатывает» — «`false` и ошибка `frame is 53 bytes, expected 54`, выходной топик не изменён».
