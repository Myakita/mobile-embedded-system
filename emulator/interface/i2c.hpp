#pragma once

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <string>

struct I2CConfig
{
    std::string device {"/dev/i2c-1"};
    uint16_t address {};
    bool force_address {false};
    bool ten_bit_address {false};
    uint32_t retries {0};
    std::chrono::milliseconds timeout {0};
};

class I2C
{
public:
    I2C() = default;
    ~I2C() { close(); }

    I2C(const I2C&) = delete;
    I2C& operator=(const I2C&) = delete;

    I2C(I2C&& other) noexcept;
    I2C& operator=(I2C&& other) noexcept;

    bool open(const std::string& device, uint16_t address);
    bool open(const I2CConfig& config);

    std::size_t read(uint8_t* data, std::size_t size);
    std::size_t write(const uint8_t* data, std::size_t size);

    bool read_register_byte(uint8_t reg, uint8_t& value);
    bool write_register_byte(uint8_t reg, uint8_t value);

    bool read_register_word(uint8_t reg, uint16_t& value);
    bool write_register_word(uint8_t reg, uint16_t value);

    std::size_t read_register_block(uint8_t reg, uint8_t* data, std::size_t size);
    std::size_t write_register_block(uint8_t reg, const uint8_t* data, std::size_t size);

    bool get_functions(unsigned long& functions) const;
    void close();

    bool is_open() const noexcept { return fd_ >= 0; }
    int fd() const noexcept { return fd_; }
    uint16_t address() const noexcept { return address_; }
    const std::string& device() const noexcept { return device_; }
    const std::string& last_error() const noexcept { return last_error_; }

private:
    bool configure(const I2CConfig& config);
    bool smbus_access(uint8_t read_write, uint8_t command, uint32_t size, void* data) const;
    void set_error_from_errno(const std::string& operation) const;

    int fd_ {-1};
    uint16_t address_ {};
    std::string device_;
    mutable std::string last_error_;
};
