// Privilege-free error-path checks for every emulated interface: opening a device
// that cannot exist must fail cleanly (false + a non-empty message), and moving a
// closed/failed instance must not double-close a file descriptor it doesn't own.
// Deliberately does not touch vcan/i2c-stub/gpio-sim — those need modprobe and are
// covered separately once the "devices" CI job exists.
#include "../interface/can.hpp"
#include "../interface/gpio.hpp"
#include "../interface/i2c.hpp"
#include "../interface/uart.hpp"

#include <cassert>
#include <utility>

namespace
{
void check_uart_open_failure()
{
    UART uart;
    assert(!uart.open("/dev/mes-emulator-test-does-not-exist", 9600));
    assert(!uart.is_open());
    assert(!uart.last_error().empty());
}

void check_i2c_open_failure()
{
    I2C i2c;
    assert(!i2c.open("/dev/mes-emulator-test-does-not-exist", 0x50));
    assert(!i2c.is_open());
    assert(!i2c.last_error().empty());
}

void check_can_open_failure()
{
    CAN can;
    assert(!can.open("mes-emulator-test-does-not-exist"));
    assert(!can.is_open());
    assert(!can.last_error().empty());
}

void check_gpio_open_failure()
{
    GPIO gpio;
    assert(!gpio.open("/dev/mes-emulator-test-does-not-exist", 0, GPIODir::Input));
    assert(!gpio.is_open());
    assert(!gpio.last_error().empty());
}

// A default-constructed (unopened) instance holds no fd. Moving it must leave both
// the source and the destination closed, never a double-close on ~T().
void check_move_of_unopened_is_safe()
{
    UART uart_a;
    UART uart_b(std::move(uart_a));
    UART uart_c;
    uart_c = std::move(uart_b);
    assert(!uart_c.is_open());

    I2C i2c_a;
    I2C i2c_b(std::move(i2c_a));
    I2C i2c_c;
    i2c_c = std::move(i2c_b);
    assert(!i2c_c.is_open());

    CAN can_a;
    CAN can_b(std::move(can_a));
    CAN can_c;
    can_c = std::move(can_b);
    assert(!can_c.is_open());

    GPIO gpio_a;
    GPIO gpio_b(std::move(gpio_a));
    GPIO gpio_c;
    gpio_c = std::move(gpio_b);
    assert(!gpio_c.is_open());
}
} // namespace

int main()
{
    check_uart_open_failure();
    check_i2c_open_failure();
    check_can_open_failure();
    check_gpio_open_failure();
    check_move_of_unopened_is_safe();
    return 0;
}
