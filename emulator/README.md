# Интеграционный эмулятор

Эмулятор — часть основного репозитория, а не Git submodule. Здесь будут располагаться сценарии, которые запускают edge-компоненты, тестовый MQTT-брокер и мобильный клиент для проверки общего контура.

Он использует закреплённый в `../protocol/` контракт. Перед изменением сценариев, формата пакетов или ожидаемых результатов нужно обновить соответствующие спецификации и тестовые векторы в репозитории протокола.

Минимальные сценарии: доставка TELEMETRY, обработка COMMAND, дедупликация по `(deviceSerial, sequence)`, ограничение TTL, потеря канала, восстановление соединения и смена доступного канала.

## Виртуальные устройства

Подробная инструкция по `emu>` и готовым JSON-мокам: [docs/EMULATOR_CLI.md](../docs/EMULATOR_CLI.md).

### Интерактивный CLI

На Linux запустите `python3 emulator/cli.py shell` из корня репозитория. Команды
показывает `help`; приглашение — `emu>`. Пример без привилегий:

```text
emu> up uart sensor
uart:sensor: /tmp/mes-uart-.../sensor
emu> load protocol/vectors/telemetry-v1.json sensor
sent LMash v1 (54 bytes) to uart:sensor
emu> list
emu> down uart sensor
emu> quit
```

Путь PTY после `up uart` передайте тестируемой программе. Он существует до
`down` или выхода из CLI. `load <файл> <uart>` принимает JSON-вектор протокола
(`fields`, необязательные `wireHex` и `payloadSize`) или объект `fields` без
обёртки. CLI кодирует поля в 54 байта по LMash v1 и сверяет `wireHex`, если он
задан. Запускать следует в checkout с инициализированным submodule `protocol`.

`load <сценарий.json>` поднимает описанные устройства и выполняет события.
Например:

```json
{
  "devices": {"uart": {"sensor": {}}},
  "events": [
    {"action": "uart.send", "port": "sensor", "message": {
      "version": 1, "messageType": "TELEMETRY", "commandType": "NONE",
      "flags": 0, "ttl": 4, "sequence": 1, "timestamp": 1726000000,
      "deviceSerial": 1, "userId": 1, "destinationId": 1,
      "temperatureX100": 3670, "pulseBpm": 80,
      "pressureSys": 120, "pressureDia": 80,
      "latitudeE7": 0, "longitudeE7": 0,
      "headingCdeg": 0, "positionQuality": 0
    }}
  ]
}
```

Для CAN доступны отдельные кадры `can.send` (`id`, `hex`, `extended`), для
I2C — `i2c.set`/`i2c.expect` (`register`, `value`), для GPIO —
`gpio.set`/`gpio.expect` (`line`, `value`). Полный пакет LMash v1 содержит
54 байта и поэтому отправляется через UART: текущий CAN-интерфейс использует
классические кадры максимум по 8 байт, а разбиение пакета между ними протокол
v1 не задаёт. `up can`, `up i2c`, `up gpio` требуют Linux, соответствующие
модули ядра и обычно права root. CLI освобождает созданные vcan и gpio-sim при
`down`/выходе; уже существующие устройства оставляет доступными.

Команды ниже рассчитаны на Linux и обычно требуют `root`. Для удобства нужны пакеты `iproute2`, `i2c-tools`, `socat`, `libgpiod` и заголовки `libgpiodcxx`.

### CAN через vcan

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

Проверка:

```bash
candump vcan0
cansend vcan0 123#11223344
```

### UART через псевдотерминалы

```bash
socat -d -d pty,raw,echo=0,link=/tmp/uart-a pty,raw,echo=0,link=/tmp/uart-b
```

После запуска один конец можно открыть из эмулятора как `/tmp/uart-a`, а во второй писать тестовые данные:

```bash
printf 'hello\n' > /tmp/uart-b
```

### I2C через i2c-stub

`i2c-stub` создаёт виртуальный I2C-адаптер с одним или несколькими slave-адресами. Пример ниже поднимает устройство на адресе `0x50`.

```bash
sudo modprobe i2c-dev
sudo modprobe i2c-stub chip_addr=0x50
```

Найти номер созданной шины:

```bash
for bus in /sys/bus/i2c/devices/i2c-*; do
  printf '%s: ' "$bus"
  cat "$bus/name"
done
```

Нужна строка со `SMBus stub driver`; если это, например, `i2c-3`, то устройство будет `/dev/i2c-3`.

Проверка регистров:

```bash
i2cset -y 3 0x50 0x10 0x42
i2cget -y 3 0x50 0x10
```

### GPIO через gpio-sim

`gpio-sim` создаёт виртуальный `gpiochip`, совместимый с `libgpiod`.

```bash
sudo modprobe gpio-sim
sudo mount -t configfs none /sys/kernel/config

sudo mkdir -p /sys/kernel/config/gpio-sim/peripheral-emulator/bank0
echo 8 | sudo tee /sys/kernel/config/gpio-sim/peripheral-emulator/bank0/num_lines
echo 1 | sudo tee /sys/kernel/config/gpio-sim/peripheral-emulator/live
```

Найти созданный chip:

```bash
gpioinfo
```

После этого в `GPIOConfig::chip` нужно передать найденный путь вида `/dev/gpiochipN`, а в `GPIOConfig::line` — номер линии, например `0`.

Остановить симулятор:

```bash
echo 0 | sudo tee /sys/kernel/config/gpio-sim/peripheral-emulator/live
sudo rmdir /sys/kernel/config/gpio-sim/peripheral-emulator/bank0
sudo rmdir /sys/kernel/config/gpio-sim/peripheral-emulator
```

## Общий пример

`example.cpp` открывает все локальные интерфейсы: GPIO, CAN, UART и I2C. Перед запуском замените
`/dev/gpiochipN` и `/dev/i2c-X` на устройства, которые появились у вас после команд выше.

Сборка и запуск из корня репозитория (см. `docs/CI.md` про CI и `make check`):

```bash
make build
./build/emulator/emulator-example
```
