// Exercises the virtual peripherals set up per emulator/README.md: vcan0 (CAN
// loopback), i2c-stub (SMBus register read/write) and gpio-sim (GPIO write+read).
// Needs root and the kernel modules loaded -- run via `make devices`, never
// `make test`. Registered under ctest label "devices" so the fast build+test loop
// never touches it.
#include "../interface/can.hpp"
#include "../interface/gpio.hpp"
#include "../interface/i2c.hpp"

#include <cassert>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>

namespace fs = std::filesystem;

namespace
{

void check_can_vcan_loopback()
{
    CAN can;
    CANConfig config;
    config.interface = "vcan0";
    config.receive_own_messages = true;
    config.receive_timeout = std::chrono::milliseconds {1000};
    assert(can.open(config) && "vcan0 not usable -- see the vcan setup in emulator/README.md");

    CANFrame sent;
    sent.id = 0x123;
    sent.size = 4;
    sent.data = {0x11, 0x22, 0x33, 0x44};
    assert(can.write(sent));

    CANFrame received;
    assert(can.read(received) && "no frame looped back on vcan0");
    assert(received.id == sent.id);
    assert(received.size == sent.size);
    assert(received.data[0] == sent.data[0] && received.data[3] == sent.data[3]);
}

// i2c-stub's bus number depends on how many i2c adapters already exist on the
// machine, so find it by matching the adapter name (see emulator/README.md).
std::optional<int> find_i2c_stub_bus()
{
    const fs::path devices {"/sys/bus/i2c/devices"};
    if (!fs::exists(devices))
    {
        return std::nullopt;
    }

    for (const auto& entry : fs::directory_iterator(devices))
    {
        std::ifstream name_file {entry.path() / "name"};
        std::string name;
        if (!name_file || !std::getline(name_file, name) || name.find("stub") == std::string::npos)
        {
            continue;
        }

        const std::string filename = entry.path().filename().string();
        const auto dash = filename.rfind('-');
        if (dash != std::string::npos)
        {
            return std::stoi(filename.substr(dash + 1));
        }
    }

    return std::nullopt;
}

void check_i2c_stub_register()
{
    const auto bus = find_i2c_stub_bus();
    assert(bus.has_value() && "no i2c-stub bus found -- see the i2c-stub setup in emulator/README.md");

    I2C i2c;
    assert(i2c.open("/dev/i2c-" + std::to_string(*bus), 0x50));

    assert(i2c.write_register_byte(0x10, 0x42));

    uint8_t value {};
    assert(i2c.read_register_byte(0x10, value));
    assert(value == 0x42);
}

// gpio-sim exposes the dynamically assigned chip name as a configfs attribute once
// the bank is made live (see the gpio-sim setup in emulator/README.md).
std::optional<std::string> find_gpio_sim_chip()
{
    const fs::path chip_name_attr {"/sys/kernel/config/gpio-sim/peripheral-emulator/bank0/chip_name"};
    if (!fs::exists(chip_name_attr))
    {
        return std::nullopt;
    }

    std::ifstream file {chip_name_attr};
    std::string name;
    if (!file || !std::getline(file, name) || name.empty())
    {
        return std::nullopt;
    }

    return name;
}

void check_gpio_sim_line()
{
    const auto chip_name = find_gpio_sim_chip();
    assert(chip_name.has_value() &&
           "no live gpio-sim bank found -- see the gpio-sim setup in emulator/README.md");

    GPIO gpio;
    GPIOConfig config;
    config.chip = "/dev/" + *chip_name;
    config.line = 0;
    config.dir = GPIODir::Output;
    config.initial_value = false;
    assert(gpio.open(config));

    assert(gpio.write(true));
    assert(gpio.read() == true);

    assert(gpio.write(false));
    assert(gpio.read() == false);
}

} // namespace

int main()
{
    check_can_vcan_loopback();
    check_i2c_stub_register();
    check_gpio_sim_line();
    return 0;
}
