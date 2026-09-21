# Интеграционный эмулятор

Эмулятор — часть основного репозитория, а не Git submodule. Здесь будут располагаться сценарии, которые запускают edge-компоненты, тестовый MQTT-брокер и мобильный клиент для проверки общего контура.

Он использует закреплённый в `../protocol/` контракт. Перед изменением сценариев, формата пакетов или ожидаемых результатов нужно обновить соответствующие спецификации и тестовые векторы в репозитории протокола.

Минимальные сценарии: доставка TELEMETRY, обработка COMMAND, дедупликация по `(deviceSerial, sequence)`, ограничение TTL, потеря канала, восстановление соединения и смена доступного канала.

## Виртуальные устройства

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
./build/emulator-example
```
