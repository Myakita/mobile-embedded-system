// Edge service: prints one telemetry line per CAN frame, and forwards LMash v1 frames read from a
// UART (the emulator's pty on a host, /dev/ttyS1 in the Yocto image) to the MQTT broker.
//   edge [<can-iface>] [--uart <device> --config <broker.conf>]
// With only --uart the CAN interface is skipped; with no arguments it is vcan0 as before.
#include "broker_config.hpp"
#include "interface/can.hpp"
#include "interface/uart.hpp"
#include "lmash.hpp"
#include "mqtt.hpp"
#include "telemetry.hpp"

#include <poll.h>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace
{
struct Options
{
    bool use_can {true};
    std::string can_interface;
    std::string uart_device;
    std::string config_path;
};

bool parse_options(int argc, char** argv, Options& options)
{
    bool can_named = false;
    for (int i = 1; i < argc; ++i)
    {
        const std::string arg = argv[i];
        if ((arg == "--uart" || arg == "--config") && i + 1 < argc)
        {
            (arg == "--uart" ? options.uart_device : options.config_path) = argv[++i];
        }
        else if (!arg.empty() && arg[0] != '-' && !can_named)
        {
            options.can_interface = arg;
            can_named = true;
        }
        else
        {
            std::fprintf(stderr, "edge: unexpected argument '%s'\n", arg.c_str());
            return false;
        }
    }
    if (options.uart_device.empty() != options.config_path.empty())
    {
        std::fprintf(stderr, "edge: --uart and --config go together\n");
        return false;
    }
    options.use_can = can_named || options.uart_device.empty();
    return true;
}

bool open_can(CAN& can, const Options& options)
{
    CANConfig config;
    if (!options.can_interface.empty())
    {
        config.interface = options.can_interface;
    }
    if (!can.open(config))
    {
        std::fprintf(
            stderr, "edge: cannot open %s: %s\n", config.interface.c_str(), can.last_error().c_str());
        return false;
    }
    // image.yml waits for this line in the QEMU boot log; keep the wording in sync.
    std::printf("edge: listening on %s\n", config.interface.c_str());
    std::fflush(stdout);
    return true;
}

bool handle_can(CAN& can)
{
    CANFrame frame;
    if (!can.read(frame))
    {
        std::fprintf(stderr, "edge: read failed: %s\n", can.last_error().c_str());
        return false;
    }
    std::puts(to_telemetry_line(frame).c_str());
    std::fflush(stdout);
    return true;
}

// Cuts the UART byte stream into 54-byte LMash v1 frames and publishes each one, unchanged, to the
// topic its header names. A frame that is not valid LMash v1 is dropped whole (no resync search).
class UartForwarder
{
public:
    bool open(const Options& options)
    {
        std::string error;
        if (!load_broker_config(options.config_path, config_, error))
        {
            std::fprintf(stderr, "edge: %s\n", error.c_str());
            return false;
        }
        if (!mqtt_.open(config_))
        {
            std::fprintf(stderr, "edge: cannot connect to broker: %s\n", mqtt_.last_error().c_str());
            return false;
        }
        std::printf("edge: connected to %s:%u\n", config_.host.c_str(), static_cast<unsigned>(config_.port));
        if (!uart_.open(options.uart_device, 115200))
        {
            std::fprintf(stderr,
                         "edge: cannot open %s: %s\n",
                         options.uart_device.c_str(),
                         uart_.last_error().c_str());
            return false;
        }
        std::printf("edge: reading frames from %s\n", options.uart_device.c_str());
        std::fflush(stdout);
        return true;
    }

    bool is_open() const { return uart_.is_open(); }
    int fd() const { return uart_.fd(); }

    // Call when fd() is readable. False once the UART is gone.
    bool pump()
    {
        uint8_t buffer[256];
        const std::size_t count = uart_.read(buffer, sizeof buffer);
        if (count == 0)
        {
            std::fprintf(stderr,
                         "edge: uart %s: %s\n",
                         uart_.device().c_str(),
                         uart_.last_error().empty() ? "closed" : uart_.last_error().c_str());
            return false;
        }
        pending_.insert(pending_.end(), buffer, buffer + count);
        while (pending_.size() >= LMASH_V1_SIZE)
        {
            forward(pending_.data());
            pending_.erase(pending_.begin(), pending_.begin() + LMASH_V1_SIZE);
        }
        return true;
    }

private:
    void forward(const uint8_t* frame)
    {
        std::string topic;
        std::string error;
        if (!lmash_topic(config_.topic_root, frame, LMASH_V1_SIZE, topic, error))
        {
            std::fprintf(stderr, "edge: dropped frame: %s\n", error.c_str());
        }
        else if (!mqtt_.publish(topic, frame, LMASH_V1_SIZE))
        {
            std::fprintf(stderr, "edge: publish failed: %s\n", mqtt_.last_error().c_str());
        }
        else
        {
            std::printf("edge: published %zu bytes to %s\n", LMASH_V1_SIZE, topic.c_str());
            std::fflush(stdout);
        }
    }

    UART uart_;
    Mqtt mqtt_;
    BrokerConfig config_;
    std::vector<uint8_t> pending_;
};

int run(CAN& can, UartForwarder& forwarder)
{
    pollfd fds[2];
    int count = 0;
    int can_slot = -1;
    int uart_slot = -1;
    if (can.is_open())
    {
        can_slot = count;
        fds[count++] = {can.fd(), POLLIN, 0};
    }
    if (forwarder.is_open())
    {
        uart_slot = count;
        fds[count++] = {forwarder.fd(), POLLIN, 0};
    }
    for (;;)
    {
        if (poll(fds, static_cast<nfds_t>(count), -1) < 0)
        {
            if (errno == EINTR)
            {
                continue;
            }
            std::fprintf(stderr, "edge: poll failed: %s\n", std::strerror(errno));
            return 1;
        }
        if (can_slot >= 0 && fds[can_slot].revents != 0 && !handle_can(can))
        {
            return 1;
        }
        if (uart_slot >= 0 && fds[uart_slot].revents != 0 && !forwarder.pump())
        {
            return 1;
        }
    }
}
} // namespace

int main(int argc, char** argv)
{
    Options options;
    if (!parse_options(argc, argv, options))
    {
        std::fprintf(stderr, "usage: edge [<can-iface>] [--uart <device> --config <broker.conf>]\n");
        return 2;
    }

    CAN can;
    UartForwarder forwarder;
    if (options.use_can && !open_can(can, options))
    {
        return 1;
    }
    if (!options.uart_device.empty() && !forwarder.open(options))
    {
        return 1;
    }
    return run(can, forwarder);
}
