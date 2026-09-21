#pragma once

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <array>
#include <string>
#include <vector>

#include <linux/can.h>
#include <linux/can/raw.h>

struct CANFrame
{
    uint32_t id {};
    uint8_t size {};
    std::array<uint8_t, 8> data {};
    bool extended {false};
    bool remote_request {false};
    bool error {false};
};

struct CANFilter
{
    uint32_t id {};
    uint32_t mask {CAN_SFF_MASK};
    bool extended {false};
};

struct CANConfig
{
    std::string interface {"vcan0"};
    bool loopback {true};
    bool receive_own_messages {false};
    bool non_blocking {false};
    std::chrono::milliseconds receive_timeout {0};
    std::vector<CANFilter> filters;
};

class CAN
{
public:
    CAN() = default;
    ~CAN() { close(); }

    CAN(const CAN&) = delete;
    CAN& operator=(const CAN&) = delete;

    CAN(CAN&& other) noexcept;
    CAN& operator=(CAN&& other) noexcept;

    bool open(const std::string& interface);
    bool open(const CANConfig& config);

    bool read(CANFrame& frame);
    bool write(const CANFrame& frame);

    bool set_filters(const std::vector<CANFilter>& filters);
    void close();

    bool is_open() const noexcept { return socket_ >= 0; }
    int fd() const noexcept { return socket_; }
    const std::string& interface() const noexcept { return interface_; }
    const std::string& last_error() const noexcept { return last_error_; }

private:
    static can_frame to_native_frame(const CANFrame& frame);
    static CANFrame from_native_frame(const can_frame& frame);
    static can_filter to_native_filter(const CANFilter& filter);

    bool set_socket_options(const CANConfig& config);
    bool bind_interface(const std::string& interface);
    void set_error_from_errno(const std::string& operation);

    int socket_ {-1};
    std::string interface_;
    std::string last_error_;
};
