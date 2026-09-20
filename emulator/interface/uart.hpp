#pragma once

#include <chrono>
#include <cstdint>
#include <cstddef>
#include <string>

enum class UARTParity
{
    None,
    Even,
    Odd
};

enum class UARTFlowControl
{
    None,
    Software,
    Hardware
};

struct UARTConfig
{
    std::string device;
    uint32_t baudrate {9600};
    uint8_t data_bits {8};
    uint8_t stop_bits {1};
    UARTParity parity {UARTParity::None};
    UARTFlowControl flow_control {UARTFlowControl::None};
    bool non_blocking {false};
    std::chrono::milliseconds read_timeout {0};
};

class UART
{
public:
    UART() = default;
    ~UART() { close(); }

    UART(const UART&) = delete;
    UART& operator=(const UART&) = delete;

    UART(UART&& other) noexcept;
    UART& operator=(UART&& other) noexcept;

    bool open(const std::string& device,
              uint32_t baudrate);
    bool open(const UARTConfig& config);

    std::size_t read(uint8_t* data, std::size_t size);

    std::size_t write(const uint8_t* data, std::size_t size);

    void close();

    bool is_open() const noexcept { return fd_ >= 0; }
    int fd() const noexcept { return fd_; }
    const std::string& device() const noexcept { return device_; }
    const std::string& last_error() const noexcept { return last_error_; }

private:
    static bool baudrate_to_speed(uint32_t baudrate, uint32_t& speed);

    bool configure(const UARTConfig& config);
    void set_error_from_errno(const std::string& operation);

    int fd_ {-1};
    std::string device_;
    std::string last_error_;
};
