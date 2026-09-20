#pragma once

#include <chrono>
#include <cstdint>
#include <memory>
#include <string>

#include <gpiod.hpp>

enum class GPIODir 
{
    Input = 0,
    Output = 1
};

enum class GPIOPull
{
    AsIs,
    Disabled,
    PullUp,
    PullDown
};

struct GPIOConfig
{
    std::string chip;
    uint16_t line {};
    GPIODir dir {GPIODir::Input};
    GPIOPull pull {GPIOPull::AsIs};
    bool active_low {false};
    bool initial_value {false};
    std::chrono::microseconds debounce {0};
    std::string consumer {"peripheral-emulator"};
};

class GPIO 
{
public:
    GPIO() = default;
    ~GPIO() { close(); }

    GPIO(const GPIO&) = delete;
    GPIO& operator=(const GPIO&) = delete;

    GPIO(GPIO&&) noexcept = default;
    GPIO& operator=(GPIO&&) noexcept = default;

    bool open(const std::string& chip,
              const uint16_t line, 
              const GPIODir dir);
    bool open(const GPIOConfig& config);

    bool read() const;
    bool write(bool value);
    bool reconfigure(const GPIODir dir,
                     const GPIOPull pull = GPIOPull::AsIs,
                     const bool active_low = false,
                     const std::chrono::microseconds debounce = std::chrono::microseconds {0});

    void close();

    bool is_open() const noexcept;
    uint16_t line() const noexcept { return line_; }
    GPIODir direction() const noexcept { return dir_; }
    GPIOPull pull() const noexcept { return pull_; }
    bool active_low() const noexcept { return active_low_; }
    std::chrono::microseconds debounce() const noexcept { return debounce_; }
    const std::string& last_error() const noexcept { return last_error_; }

private:
    static gpiod::line::bias to_gpiod_bias(GPIOPull pull);
    static gpiod::line::direction to_gpiod_direction(GPIODir dir);
    static gpiod::line::value to_gpiod_value(bool value);

    gpiod::line_settings make_line_settings(const GPIODir dir,
                                            const GPIOPull pull,
                                            const bool active_low,
                                            const std::chrono::microseconds debounce,
                                            const bool initial_value) const;

    std::unique_ptr<gpiod::chip> chip_;
    mutable std::unique_ptr<gpiod::line_request> request_;

    uint16_t line_ {};
    GPIODir dir_ {GPIODir::Input};
    GPIOPull pull_ {GPIOPull::AsIs};
    bool active_low_ {false};
    std::chrono::microseconds debounce_ {0};
    std::string consumer_ {"peripheral-emulator"};
    mutable std::string last_error_;
};
