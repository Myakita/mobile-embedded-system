#include "uart.hpp"

#include <cerrno>
#include <cstring>
#include <string>
#include <utility>

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

UART::UART(UART&& other) noexcept
    : fd_(std::exchange(other.fd_, -1)),
      device_(std::move(other.device_)),
      last_error_(std::move(other.last_error_))
{
}

UART& UART::operator=(UART&& other) noexcept
{
    if (this != &other)
    {
        close();
        fd_ = std::exchange(other.fd_, -1);
        device_ = std::move(other.device_);
        last_error_ = std::move(other.last_error_);
    }

    return *this;
}

bool UART::open(const std::string& device, uint32_t baudrate)
{
    UARTConfig config;
    config.device = device;
    config.baudrate = baudrate;

    return open(config);
}

bool UART::open(const UARTConfig& config)
{
    close();

    int flags = O_RDWR | O_NOCTTY;
    if (config.non_blocking)
    {
        flags |= O_NONBLOCK;
    }

    fd_ = ::open(config.device.c_str(), flags);
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

    device_ = config.device;
    last_error_.clear();

    return true;
}

std::size_t UART::read(std::span<uint8_t> data)
{
    if (!is_open())
    {
        last_error_ = "UART device is not open";
        return 0;
    }

    const auto bytes = ::read(fd_, data.data(), data.size());
    if (bytes < 0)
    {
        set_error_from_errno("read");
        return 0;
    }

    last_error_.clear();

    return static_cast<std::size_t>(bytes);
}

std::size_t UART::write(std::span<const uint8_t> data)
{
    if (!is_open())
    {
        last_error_ = "UART device is not open";
        return 0;
    }

    const auto bytes = ::write(fd_, data.data(), data.size());
    if (bytes < 0)
    {
        set_error_from_errno("write");
        return 0;
    }

    last_error_.clear();

    return static_cast<std::size_t>(bytes);
}

void UART::close()
{
    if (fd_ >= 0)
    {
        if (::close(fd_) < 0)
        {
            set_error_from_errno("close");
        }

        fd_ = -1;
    }

    device_.clear();
}

bool UART::baudrate_to_speed(uint32_t baudrate, uint32_t& speed)
{
    switch (baudrate)
    {
    case 50:
        speed = B50;
        return true;
    case 75:
        speed = B75;
        return true;
    case 110:
        speed = B110;
        return true;
    case 134:
        speed = B134;
        return true;
    case 150:
        speed = B150;
        return true;
    case 200:
        speed = B200;
        return true;
    case 300:
        speed = B300;
        return true;
    case 600:
        speed = B600;
        return true;
    case 1200:
        speed = B1200;
        return true;
    case 1800:
        speed = B1800;
        return true;
    case 2400:
        speed = B2400;
        return true;
    case 4800:
        speed = B4800;
        return true;
    case 9600:
        speed = B9600;
        return true;
    case 19200:
        speed = B19200;
        return true;
    case 38400:
        speed = B38400;
        return true;
    case 57600:
        speed = B57600;
        return true;
    case 115200:
        speed = B115200;
        return true;
    case 230400:
        speed = B230400;
        return true;
    default:
        return false;
    }
}

bool UART::configure(const UARTConfig& config)
{
    termios options {};
    if (::tcgetattr(fd_, &options) < 0)
    {
        set_error_from_errno("tcgetattr");
        return false;
    }

    uint32_t speed {};
    if (!baudrate_to_speed(config.baudrate, speed))
    {
        last_error_ = "unsupported UART baudrate";
        return false;
    }

    ::cfmakeraw(&options);

    if (::cfsetispeed(&options, speed) < 0 || ::cfsetospeed(&options, speed) < 0)
    {
        set_error_from_errno("cfsetspeed");
        return false;
    }

    options.c_cflag &= ~CSIZE;
    switch (config.data_bits)
    {
    case 5:
        options.c_cflag |= CS5;
        break;
    case 6:
        options.c_cflag |= CS6;
        break;
    case 7:
        options.c_cflag |= CS7;
        break;
    case 8:
        options.c_cflag |= CS8;
        break;
    default:
        last_error_ = "unsupported UART data bits";
        return false;
    }

    if (config.stop_bits == 2)
    {
        options.c_cflag |= CSTOPB;
    }
    else if (config.stop_bits == 1)
    {
        options.c_cflag &= ~CSTOPB;
    }
    else
    {
        last_error_ = "unsupported UART stop bits";
        return false;
    }

    options.c_cflag &= ~(PARENB | PARODD);
    if (config.parity == UARTParity::Even)
    {
        options.c_cflag |= PARENB;
    }
    else if (config.parity == UARTParity::Odd)
    {
        options.c_cflag |= PARENB | PARODD;
    }

    options.c_iflag &= ~(IXON | IXOFF | IXANY);
    options.c_cflag &= ~CRTSCTS;
    if (config.flow_control == UARTFlowControl::Software)
    {
        options.c_iflag |= IXON | IXOFF;
    }
    else if (config.flow_control == UARTFlowControl::Hardware)
    {
        options.c_cflag |= CRTSCTS;
    }

    options.c_cflag |= CLOCAL | CREAD;

    options.c_cc[VMIN] = 0;
    options.c_cc[VTIME] = static_cast<cc_t>(
        config.read_timeout.count() <= 0 ? 0 : (config.read_timeout.count() + 99) / 100);

    if (::tcsetattr(fd_, TCSANOW, &options) < 0)
    {
        set_error_from_errno("tcsetattr");
        return false;
    }

    if (::tcflush(fd_, TCIOFLUSH) < 0)
    {
        set_error_from_errno("tcflush");
        return false;
    }

    return true;
}

void UART::set_error_from_errno(const std::string& operation)
{
    last_error_ = operation + ": " + std::strerror(errno);
}
