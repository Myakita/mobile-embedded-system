#include "i2c.hpp"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <string>
#include <utility>

#include <fcntl.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>
#include <unistd.h>

I2C::I2C(I2C&& other) noexcept
    : fd_(std::exchange(other.fd_, -1)),
      address_(std::exchange(other.address_, 0)),
      device_(std::move(other.device_)),
      last_error_(std::move(other.last_error_))
{
}

I2C& I2C::operator=(I2C&& other) noexcept
{
    if (this != &other)
    {
        close();
        fd_ = std::exchange(other.fd_, -1);
        address_ = std::exchange(other.address_, 0);
        device_ = std::move(other.device_);
        last_error_ = std::move(other.last_error_);
    }

    return *this;
}

bool I2C::open(const std::string& device, uint16_t address)
{
    I2CConfig config;
    config.device = device;
    config.address = address;

    return open(config);
}

bool I2C::open(const I2CConfig& config)
{
    close();

    fd_ = ::open(config.device.c_str(), O_RDWR);
    if (fd_ < 0)
    {
        set_error_from_errno("open");
        return false;
    }

    if (!configure(config))
    {
        close();
        return false;
    }

    address_ = config.address;
    device_ = config.device;
    last_error_.clear();

    return true;
}

std::size_t I2C::read(uint8_t* data, std::size_t size)
{
    if (!is_open())
    {
        last_error_ = "I2C device is not open";
        return 0;
    }

    if (data == nullptr || size == 0)
    {
        last_error_ = "I2C read buffer is empty";
        return 0;
    }

    const auto bytes = ::read(fd_, data, size);
    if (bytes < 0)
    {
        set_error_from_errno("read");
        return 0;
    }

    last_error_.clear();

    return static_cast<std::size_t>(bytes);
}

std::size_t I2C::write(const uint8_t* data, std::size_t size)
{
    if (!is_open())
    {
        last_error_ = "I2C device is not open";
        return 0;
    }

    if (data == nullptr || size == 0)
    {
        last_error_ = "I2C write buffer is empty";
        return 0;
    }

    const auto bytes = ::write(fd_, data, size);
    if (bytes < 0)
    {
        set_error_from_errno("write");
        return 0;
    }

    last_error_.clear();

    return static_cast<std::size_t>(bytes);
}

bool I2C::read_register_byte(uint8_t reg, uint8_t& value)
{
    i2c_smbus_data data {};
    if (!smbus_access(I2C_SMBUS_READ, reg, I2C_SMBUS_BYTE_DATA, &data))
    {
        return false;
    }

    value = data.byte;
    last_error_.clear();

    return true;
}

bool I2C::write_register_byte(uint8_t reg, uint8_t value)
{
    i2c_smbus_data data {};
    data.byte = value;

    if (!smbus_access(I2C_SMBUS_WRITE, reg, I2C_SMBUS_BYTE_DATA, &data))
    {
        return false;
    }

    last_error_.clear();

    return true;
}

bool I2C::read_register_word(uint8_t reg, uint16_t& value)
{
    i2c_smbus_data data {};
    if (!smbus_access(I2C_SMBUS_READ, reg, I2C_SMBUS_WORD_DATA, &data))
    {
        return false;
    }

    value = data.word;
    last_error_.clear();

    return true;
}

bool I2C::write_register_word(uint8_t reg, uint16_t value)
{
    i2c_smbus_data data {};
    data.word = value;

    if (!smbus_access(I2C_SMBUS_WRITE, reg, I2C_SMBUS_WORD_DATA, &data))
    {
        return false;
    }

    last_error_.clear();

    return true;
}

std::size_t I2C::read_register_block(uint8_t reg, uint8_t* data, std::size_t size)
{
    if (data == nullptr || size == 0)
    {
        last_error_ = "I2C block read buffer is empty";
        return 0;
    }

    i2c_smbus_data smbus_data {};
    smbus_data.block[0] = static_cast<__u8>(std::min<std::size_t>(size, I2C_SMBUS_BLOCK_MAX));

    if (!smbus_access(I2C_SMBUS_READ, reg, I2C_SMBUS_I2C_BLOCK_DATA, &smbus_data))
    {
        return 0;
    }

    const auto count = std::min<std::size_t>(smbus_data.block[0], size);
    std::copy(smbus_data.block + 1, smbus_data.block + 1 + count, data);
    last_error_.clear();

    return count;
}

std::size_t I2C::write_register_block(uint8_t reg, const uint8_t* data, std::size_t size)
{
    if (data == nullptr || size == 0)
    {
        last_error_ = "I2C block write buffer is empty";
        return 0;
    }

    const auto count = std::min<std::size_t>(size, I2C_SMBUS_BLOCK_MAX);

    i2c_smbus_data smbus_data {};
    smbus_data.block[0] = static_cast<__u8>(count);
    std::copy(data, data + count, smbus_data.block + 1);

    if (!smbus_access(I2C_SMBUS_WRITE, reg, I2C_SMBUS_I2C_BLOCK_DATA, &smbus_data))
    {
        return 0;
    }

    last_error_.clear();

    return count;
}

bool I2C::get_functions(unsigned long& functions) const
{
    if (!is_open())
    {
        last_error_ = "I2C device is not open";
        return false;
    }

    if (::ioctl(fd_, I2C_FUNCS, &functions) < 0)
    {
        set_error_from_errno("ioctl(I2C_FUNCS)");
        return false;
    }

    last_error_.clear();

    return true;
}

void I2C::close()
{
    if (fd_ >= 0)
    {
        if (::close(fd_) < 0)
        {
            set_error_from_errno("close");
        }

        fd_ = -1;
    }

    address_ = 0;
    device_.clear();
}

bool I2C::configure(const I2CConfig& config)
{
    if (config.address > (config.ten_bit_address ? 0x03ff : 0x007f))
    {
        last_error_ = "I2C address is out of range";
        return false;
    }

    if (::ioctl(fd_, I2C_TENBIT, config.ten_bit_address ? 1 : 0) < 0)
    {
        set_error_from_errno("ioctl(I2C_TENBIT)");
        return false;
    }

    if (config.retries > 0 && ::ioctl(fd_, I2C_RETRIES, config.retries) < 0)
    {
        set_error_from_errno("ioctl(I2C_RETRIES)");
        return false;
    }

    if (config.timeout.count() > 0)
    {
        const auto timeout_units = (config.timeout.count() + 9) / 10;
        if (::ioctl(fd_, I2C_TIMEOUT, timeout_units) < 0)
        {
            set_error_from_errno("ioctl(I2C_TIMEOUT)");
            return false;
        }
    }

    const auto slave_ioctl = config.force_address ? I2C_SLAVE_FORCE : I2C_SLAVE;
    if (::ioctl(fd_, slave_ioctl, config.address) < 0)
    {
        set_error_from_errno(config.force_address ? "ioctl(I2C_SLAVE_FORCE)" : "ioctl(I2C_SLAVE)");
        return false;
    }

    return true;
}

bool I2C::smbus_access(uint8_t read_write, uint8_t command, uint32_t size, void* data) const
{
    if (!is_open())
    {
        last_error_ = "I2C device is not open";
        return false;
    }

    i2c_smbus_ioctl_data args {};
    args.read_write = read_write;
    args.command = command;
    args.size = size;
    args.data = static_cast<i2c_smbus_data*>(data);

    if (::ioctl(fd_, I2C_SMBUS, &args) < 0)
    {
        set_error_from_errno("ioctl(I2C_SMBUS)");
        return false;
    }

    return true;
}

void I2C::set_error_from_errno(const std::string& operation) const
{
    last_error_ = operation + ": " + std::strerror(errno);
}
