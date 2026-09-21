// Opens a pty pair (no root, no socat) and drives UART through the slave end:
// a write on the wrapper must arrive on the master fd byte-for-byte, and changing
// the configured baudrate must actually change the fd's termios speed.
#include "../interface/uart.hpp"

#include <array>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <string>

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

namespace
{
bool open_pty_pair(int& master_fd, std::string& slave_path)
{
    master_fd = ::posix_openpt(O_RDWR | O_NOCTTY);
    if (master_fd < 0)
    {
        return false;
    }

    if (::grantpt(master_fd) != 0 || ::unlockpt(master_fd) != 0)
    {
        ::close(master_fd);
        return false;
    }

    const char* name = ::ptsname(master_fd);
    if (name == nullptr)
    {
        ::close(master_fd);
        return false;
    }

    slave_path = name;
    return true;
}
} // namespace

int main()
{
    int master_fd = -1;
    std::string slave_path;
    assert(open_pty_pair(master_fd, slave_path) && "failed to allocate a pty pair");

    UART uart;
    assert(uart.open(slave_path, 115200) && "UART failed to open the pty slave");
    assert(uart.is_open());

    termios initial_tio {};
    assert(::tcgetattr(uart.fd(), &initial_tio) == 0);
    assert(::cfgetispeed(&initial_tio) == B115200);
    assert(::cfgetospeed(&initial_tio) == B115200);

    const std::array<uint8_t, 5> message {'h', 'e', 'l', 'l', 'o'};
    const auto written = uart.write(message.data(), message.size());
    assert(written == message.size());

    std::array<uint8_t, 5> received {};
    const auto bytes_read = ::read(master_fd, received.data(), received.size());
    assert(bytes_read == static_cast<ssize_t>(message.size()));
    assert(received == message);

    // Reopening the same wrapper at a different baudrate must apply it.
    assert(uart.open(slave_path, 9600) && "UART failed to reopen the pty slave");
    termios changed_tio {};
    assert(::tcgetattr(uart.fd(), &changed_tio) == 0);
    assert(::cfgetispeed(&changed_tio) == B9600);
    assert(::cfgetospeed(&changed_tio) == B9600);

    ::close(master_fd);
    return 0;
}
