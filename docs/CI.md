# CI (эмулятор)

Инфраструктура для `emulator/` из [issue #2](https://github.com/Myakita/mobile-embedded-system/issues/2).
Android и `protocol/` сюда не входят — у Android свой пайплайн.

## Что уже работает

`.github/workflows/ci.yml` запускается на каждый push и PR, которые трогают `emulator/`, `Makefile`,
`ci/` или `.clang-format`. Изменение только `docs/` или обновление указателя `mobile_app`/`protocol`
CI не запускает. Ничего не блокирует технически — прямой push в `main` проходит всегда, красный статус
на коммите — сигнал, а не преграда.

Две параллельные джобы:

- **`build`** — `make build test`: CMake-сборка `emulator/` (библиотека `periph` из четырёх
  `interface/*.cpp`) и `ctest` (сейчас: `errors` — привилегий не требует, проверяет пути отказа
  `open()` на всех четырёх интерфейсах и безопасность move; `uart_pty` — гоняет UART через pty-пару).
- **`guard`** — `python3 ci/guard.py`: форма кода, не объём. См. ниже.

## Локальное воспроизведение

```bash
git submodule update --init --recursive
make check          # build + test + guard, ровно то, что делает CI
```

Полная сборка требует Linux (`libgpiod` v2 через `ci/install-libgpiod-v2.sh`, ядерные заголовки
`linux/can.h`, `linux/i2c-dev.h` — их нет на macOS). На маке без Linux-VM/Docker доступны
`make guard` целиком и просмотр исходников; для реальной сборки — Docker:

```bash
docker run --rm -v "$(pwd)":/repo -w /repo ubuntu:24.04 bash -c '
  apt-get update -qq && apt-get install -y --no-install-recommends \
    cmake g++ make pkg-config meson ninja-build sudo &&
  bash ci/install-libgpiod-v2.sh &&
  make check'
```

## `ci/guard.py` — почему без бюджетов по строкам

Ранний вариант этого файла держал лимиты строк по каталогам и список разрешённых каталогов верхнего
уровня. От них отказались: они требуют подкручивания ровно тогда, когда проект растёт, то есть
постоянно, и это слишком дорого для учебного проекта. Вместо объёма гейт контролирует **форму** —
семь проверок, которые либо верны всегда, либо не нужны вовсе, без файла-конфига:

| Проверка | Что делает |
|---|---|
| `format` | `clang-format --dry-run --Werror` по `.clang-format`. `make fmt` чинит. |
| `duplicates` | Свой, без сторонних инструментов: хэширует тело каждой функции (границы строк — из `lizard`) и ловит буквальную копипасту между разными функциями. Не ловит копию с переименованными переменными — осознанное ограничение, ловит именно сценарий `uart_v2.cpp` рядом с `uart.cpp`. |
| `complexity` | `lizard -w` (только нарушения, в формате предупреждений clang) с порогами `MAX_FUNCTION_LINES=80`, `MAX_CCN=15`. Уважает `// #lizard forgives` **внутри тела функции** (не над сигнатурой — иначе не работает). Две функции в `uart.cpp` помечены так осознанно: таблица бодрейтов и последовательная настройка `termios` — легитимно длинные/ветвящиеся, не слоп. |
| `file-length` | Файл длиннее `MAX_FILE_LINES=600` строк — падение. Защита от файла на тысячи строк, не инструмент управления объёмом. |
| `orphan-files` | `.cpp` вне всех `CMakeLists.txt` или `.hpp`, который никто не инклюдит и не собирает. |
| `paired-tests` | Для каждого `interface/X.cpp` — хоть один файл в `tests/` инклюдит `interface/X.hpp`. Не требует одного файла теста на один интерфейс: `test_errors.cpp` осознанно покрывает все четыре сразу. |
| `dependency-allowlist` | `pkg_check_modules`/`find_package`/`FetchContent_Declare` вне блока `# guard:deps:start` / `# guard:deps:end` в том же `CMakeLists.txt` — падение. Новая зависимость — однострочный ревьюируемый diff, а не побочный эффект PR с фичей. |
| `submodule-pointers` | Указатель `protocol`/`mobile_app` должен быть предком (или верхушкой) `origin/main` своего репозитория — иначе он либо не запушен, либо потерян при rebase. **Важно:** `git ls-remote <url> <sha>` для этого не годится — `ls-remote` matches ref *names*, не содержимое коммита, и молча возвращает пусто даже для реально запушенного коммита. Проверка идёт через `git fetch` + `merge-base --is-ancestor` внутри уже инициализированного сабмодуля. |
| диффstat (не блокирует) | Таблица «+добавлено/-удалено» по каталогам в `$GITHUB_STEP_SUMMARY`. Только показывает рост, не судит его. |

Три числовые константы (`MAX_FILE_LINES`, `MAX_FUNCTION_LINES`, `MAX_CCN`) — в шапке `ci/guard.py`,
трогать раз в семестр, не на каждый PR.

## `ci/install-libgpiod-v2.sh` — почему он есть

`emulator/interface/gpio.cpp` использует **libgpiod v2** C++ API (`chip::prepare_request()`,
`line_settings`). Ubuntu 24.04 в apt даёт только v1.6, где этого API нет вообще. Скрипт идемпотентен:
проверяет версию через `pkg-config` и, если она младше 2.0, собирает `v2.3.1` из исходников (Meson,
не autotools — актуальная ветка libgpiod перешла на Meson). На реальном GitHub-раннере занимает
десятки секунд; локально на Linux, где v2 уже стоит, пропускается мгновенно.

## `full.yml` — виртуальная периферия и MQTT-стенд, по тегу

Не идёт на каждый push — дороже и завязан на вещи, которые ломаются не по вине кода. Триггер:

```bash
git tag full-1 <sha> && git push origin full-1     # без ветки, на любом существующем коммите
git push origin :refs/tags/full-1                  # удалить тег после прогона, если не нужен
```

Плюс еженедельно по расписанию (Monday 03:00 UTC) и вручную через `workflow_dispatch`, чтобы не
протухал незаметно, если тег никто не пушит месяцами.

Две независимые джобы:

- **`devices`** — `make devices` (`ctest -L devices`, `emulator/tests/test_devices.cpp`): CAN
  loopback на `vcan0` (`CAN_RAW_LOOPBACK`+`CAN_RAW_RECV_OWN_MSGS`, без внешнего собеседника), запись
  и чтение регистра на `i2c-stub` (бюс ищется по имени адаптера в `/sys/bus/i2c/devices/*/name`,
  номер не детерминирован), GPIO write+read на `gpio-sim` (чип берётся из configfs-атрибута
  `bank0/chip_name`, назначается ядром динамически). Требует root и ядерные модули — **непроверяемо
  локально на macOS/Docker Desktop**: у LinuxKit-ядра там просто нет `/lib/modules`, `modprobe`
  ни для одного из трёх модулей не находит их вообще. Джоба идёт с `continue-on-error: true` —
  `linux-modules-extra-$(uname -r)` на раннере может разойтись с ядром сразу после обновления
  образа, и это не должно портить `full`, пока не станет ясно, что нестабильность реальная.
- **`stand`** — `make stand` (`emulator/stand/smoke.sh`): поднимает `eclipse-mosquitto` с TLS
  (самоподписанный CA, генерируется заново при каждом запуске в `generated/`, не коммитится) и ACL
  (`acl.conf` — у пользователя `authorized` есть `mes/smoke/#`, у `stranger` нет ничего). Публикует
  `wireHex` из `protocol/vectors/telemetry-v1.json`, сверяет байт в байт у `authorized`-подписчика,
  затем двумя отдельными проверками — что `stranger` не получает **и** не может опубликовать в тот
  же топик. Проверка ACL идёт по факту доставки, не по exit-коду клиента: у QoS 0 нет ack, так что
  запрещённый publish у `mosquitto_pub` всё равно выглядит успехом — что реально имеет значение,
  доходит ли сообщение до подписчика. Не требует ядерных модулей, чисто userspace — проверено
  end-to-end локально, включая намеренную порчу `acl.conf` для подтверждения, что скрипт ловит
  регрессию.

Когда появится C++-кодек протокола, туда же добавится джоба соответствия векторам (кодирование полей
→ `wireHex` и обратно) — в этом заходе не реализовано.

## Дальше (не реализовано в этом заходе)

- **`image.yml`** — Yocto + QEMU, `workflow_dispatch` и еженедельно.
- **`release.yml`** — по тегу `v*`.

См. план: `docs/User stories и MVP.md` §7, AC-09–AC-12.
