# CLI виртуальных интерфейсов (`emu>`)

CLI запускается из корня репозитория на Linux:

```bash
python3 emulator/cli.py shell
```

Команда `help` показывает синтаксис. Интерфейсы живут в течение одной сессии:
`up` создаёт или подключает их, `list` показывает пути, `down` освобождает
ресурс. При выходе CLI закрывает PTY и удаляет созданные им vcan/gpio-sim.
Существующие до запуска устройства остаются на месте. Для vcan, i2c-stub и
gpio-sim нужны модули ядра и обычно права root; для UART достаточно обычного
пользователя.

## Готовые моки

Каталог `emulator/mocks/` содержит:

| Файл | Назначение |
|---|---|
| `telemetry-v1.json` | TELEMETRY в формате вектора протокола v1 |
| `command-return-v1.json` | COMMAND RETURN в формате вектора v1 |
| `uart-telemetry.json` | сценарий отправки сообщения v1 через UART |
| `can-frame.json` | классический CAN-кадр с ID `0x123` |
| `i2c-register.json` | запись и проверка регистра `0x10` |
| `gpio-input.json` | высокий уровень на линии 0 и его проверка |

Два JSON-вектора повторяют закреплённые значения из
`protocol/vectors/`; каноническая спецификация лежит в
`protocol/spec/lmash-v1.md`. Каждый вектор содержит `fields`, `payloadSize` и
`wireHex`. CLI собирает байты из `fields` по little-endian и отклоняет
вектор, если `wireHex` или длина не совпадают. Можно передать и один объект
`fields` без обёртки.

## Быстрая проверка UART

В первом терминале:

```text
$ python3 emulator/cli.py shell
emu> up uart sensor
uart:sensor: /tmp/mes-uart-.../sensor
```

Во втором терминале откройте **напечатанный** путь до отправки. Например:

```bash
python3 -c 'import sys; print(open(sys.argv[1], "rb", buffering=0).read(54).hex())' /tmp/mes-uart-.../sensor
```

Затем в первом терминале:

```text
emu> load emulator/mocks/telemetry-v1.json sensor
sent LMash v1 (54 bytes) to uart:sensor
emu> down uart sensor
emu> quit
```

Во втором терминале появится тот же hex, что в `wireHex` мока. Файл
`command-return-v1.json` проверяется аналогично.

## Сценарии для всех интерфейсов

`load <путь.json>` создаёт устройства из `devices` и последовательно
выполняет `events`. Для повторного воспроизведения можно вызвать `load` ещё
раз: активные устройства сохраняются. Синтаксис сценария показан в
`emulator/mocks/uart-telemetry.json` и остальных файлах каталога. Поле
`after_ms` добавляет задержку перед событием. Для UART событие `uart.send`
принимает ровно одно из `message` (поля v1 или вектор), `hex`, `text`.

Примеры:

```text
emu> load emulator/mocks/uart-telemetry.json
emu> load emulator/mocks/can-frame.json
emu> load emulator/mocks/i2c-register.json
emu> load emulator/mocks/gpio-input.json
```

Для CAN можно наблюдать результат через `candump vcan0`. Полное сообщение
LMash v1 занимает 54 байта и отправляется через UART. Текущий CAN-интерфейс
использует классические кадры до 8 байт; схема разбиения сообщения v1 между
кадрами пока не определена.

## Автоматическая проверка

```bash
make test
make check
```

`make test` запускает C++-тесты и тесты CLI без привилегий, включая проверку
обоих протокольных векторов, всех JSON-моков и передачу через настоящий PTY.
`make check` дополнительно запускает `ci/guard.py`; для него нужен Python-пакет
`lizard` (устанавливается в CI). Проверка vcan, i2c-stub и gpio-sim на Linux
требует доступных модулей ядра и прав root.
