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

Пример ниже открывает все локальные интерфейсы: GPIO, CAN, UART и I2C. Перед запуском замените `/dev/gpiochipN` и `/dev/i2c-X` на устройства, которые появились у вас после команд выше.

```cpp
#include "interface/can.hpp"
#include "interface/gpio.hpp"
#include "interface/i2c.hpp"
#include "interface/uart.hpp"

#include <array>
#include <cstdint>
#include <iostream>

int main()
{
    GPIO led;
    GPIOConfig gpio_config;
    gpio_config.chip = "/dev/gpiochipN";
    gpio_config.line = 0;
    gpio_config.dir = GPIODir::Output;
    gpio_config.initial_value = false;

    if (!led.open(gpio_config))
    {
        std::cerr << "GPIO: " << led.last_error() << '\n';
        return 1;
    }

    CAN can;
    CANConfig can_config;
    can_config.interface = "vcan0";
    can_config.receive_own_messages = true;

    if (!can.open(can_config))
    {
        std::cerr << "CAN: " << can.last_error() << '\n';
        return 1;
    }

    UART uart;
    UARTConfig uart_config;
    uart_config.device = "/tmp/uart-a";
    uart_config.baudrate = 115200;

    if (!uart.open(uart_config))
    {
        std::cerr << "UART: " << uart.last_error() << '\n';
        return 1;
    }

    I2C i2c;
    I2CConfig i2c_config;
    i2c_config.device = "/dev/i2c-X";
    i2c_config.address = 0x50;

    if (!i2c.open(i2c_config))
    {
        std::cerr << "I2C: " << i2c.last_error() << '\n';
        return 1;
    }

    led.write(true);

    CANFrame frame;
    frame.id = 0x123;
    frame.size = 4;
    frame.data = {0x11, 0x22, 0x33, 0x44};
    can.write(frame);

    const std::array<uint8_t, 5> message {'h', 'e', 'l', 'l', 'o'};
    uart.write(message.data(), message.size());

    i2c.write_register_byte(0x10, 0x42);

    uint8_t value {};
    if (i2c.read_register_byte(0x10, value))
    {
        std::cout << "I2C register 0x10 = 0x" << std::hex << static_cast<int>(value) << '\n';
    }
    else
    {
        std::cerr << "I2C read: " << i2c.last_error() << '\n';
    }

    led.write(false);

    return 0;
}
```

Сборка из корня `emulator`:

```bash
g++ -std=c++17 -Wall -Wextra -pedantic \
  example.cpp \
  interface/gpio.cpp interface/can.cpp interface/uart.cpp interface/i2c.cpp \
  -lgpiodcxx \
  -o emulator-example
```
