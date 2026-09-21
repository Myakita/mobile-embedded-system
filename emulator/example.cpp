// Opens every emulated interface and exercises it once. Not a test: this is the
// runnable walkthrough referenced from emulator/README.md, kept alive by `make build`
// instead of living only as an untested markdown snippet.
//
// Replace the placeholders below with devices created by the setup commands in
// emulator/README.md (vcan0, an i2c-stub bus, a gpio-sim chip, a pty pair).
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
