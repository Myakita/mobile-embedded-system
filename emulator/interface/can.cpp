#include "can.hpp"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <string>
#include <utility>

#include <fcntl.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

CAN::CAN(CAN&& other) noexcept
    : socket_(std::exchange(other.socket_, -1)),
      interface_(std::move(other.interface_)),
      last_error_(std::move(other.last_error_))
{
}

CAN& CAN::operator=(CAN&& other) noexcept
{
    if (this != &other)
    {
        close();
        socket_ = std::exchange(other.socket_, -1);
        interface_ = std::move(other.interface_);
        last_error_ = std::move(other.last_error_);
    }

    return *this;
}

bool CAN::open(const std::string& interface)
{
    CANConfig config;
    config.interface = interface;

    return open(config);
}

bool CAN::open(const CANConfig& config)
{
    close();

    socket_ = ::socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (socket_ < 0)
    {
        set_error_from_errno("socket");
        return false;
    }

    if (!set_socket_options(config) || !bind_interface(config.interface))
    {
        close();
        return false;
    }

    interface_ = config.interface;
    last_error_.clear();

    return true;
}

bool CAN::read(CANFrame& frame)
{
    if (!is_open())
    {
        last_error_ = "CAN socket is not open";
        return false;
    }

    can_frame native_frame {};
    const auto bytes = ::recv(socket_, &native_frame, sizeof(native_frame), 0);
    if (bytes < 0)
    {
        set_error_from_errno("recv");
        return false;
    }

    if (static_cast<std::size_t>(bytes) != sizeof(native_frame))
    {
        last_error_ = "received incomplete CAN frame";
        return false;
    }

    frame = from_native_frame(native_frame);
    last_error_.clear();

    return true;
}

bool CAN::write(const CANFrame& frame)
{
    if (!is_open())
    {
        last_error_ = "CAN socket is not open";
        return false;
    }

    if (frame.size > CAN_MAX_DLEN)
    {
        last_error_ = "CAN frame payload is larger than 8 bytes";
        return false;
    }

    const auto native_frame = to_native_frame(frame);
    const auto bytes = ::send(socket_, &native_frame, sizeof(native_frame), 0);
    if (bytes < 0)
    {
        set_error_from_errno("send");
        return false;
    }

    if (static_cast<std::size_t>(bytes) != sizeof(native_frame))
    {
        last_error_ = "sent incomplete CAN frame";
        return false;
    }

    last_error_.clear();

    return true;
}

bool CAN::set_filters(const std::vector<CANFilter>& filters)
{
    if (!is_open())
    {
        last_error_ = "CAN socket is not open";
        return false;
    }

    if (filters.empty())
    {
        can_filter receive_all {};
        receive_all.can_id = 0;
        receive_all.can_mask = 0;

        if (::setsockopt(socket_, SOL_CAN_RAW, CAN_RAW_FILTER, &receive_all, sizeof(receive_all)) < 0)
        {
            set_error_from_errno("setsockopt(CAN_RAW_FILTER)");
            return false;
        }

        last_error_.clear();
        return true;
    }

    std::vector<can_filter> native_filters;
    native_filters.reserve(filters.size());
    for (const auto& filter : filters)
    {
        native_filters.push_back(to_native_filter(filter));
    }

    if (::setsockopt(socket_,
                     SOL_CAN_RAW,
                     CAN_RAW_FILTER,
                     native_filters.data(),
                     native_filters.size() * sizeof(can_filter)) < 0)
    {
        set_error_from_errno("setsockopt(CAN_RAW_FILTER)");
        return false;
    }

    last_error_.clear();

    return true;
}

void CAN::close()
{
    if (socket_ >= 0)
    {
        if (::close(socket_) < 0)
        {
            set_error_from_errno("close");
        }

        socket_ = -1;
    }

    interface_.clear();
}

can_frame CAN::to_native_frame(const CANFrame& frame)
{
    can_frame native_frame {};
    native_frame.can_id = frame.id;
    native_frame.can_dlc = frame.size;

    if (frame.extended)
    {
        native_frame.can_id |= CAN_EFF_FLAG;
    }

    if (frame.remote_request)
    {
        native_frame.can_id |= CAN_RTR_FLAG;
    }

    if (frame.error)
    {
        native_frame.can_id |= CAN_ERR_FLAG;
    }

    std::copy(frame.data.begin(), frame.data.begin() + frame.size, native_frame.data);

    return native_frame;
}

CANFrame CAN::from_native_frame(const can_frame& frame)
{
    CANFrame result;
    result.extended = (frame.can_id & CAN_EFF_FLAG) != 0;
    result.remote_request = (frame.can_id & CAN_RTR_FLAG) != 0;
    result.error = (frame.can_id & CAN_ERR_FLAG) != 0;
    result.id = frame.can_id & (result.extended ? CAN_EFF_MASK : CAN_SFF_MASK);
    result.size = frame.can_dlc;

    std::copy(frame.data, frame.data + result.size, result.data.begin());

    return result;
}

can_filter CAN::to_native_filter(const CANFilter& filter)
{
    can_filter native_filter {};
    native_filter.can_id = filter.id;
    native_filter.can_mask = filter.mask;

    if (filter.extended)
    {
        native_filter.can_id |= CAN_EFF_FLAG;
        native_filter.can_mask |= CAN_EFF_FLAG;
    }

    return native_filter;
}

bool CAN::set_socket_options(const CANConfig& config)
{
    const int loopback = config.loopback ? 1 : 0;
    if (::setsockopt(socket_, SOL_CAN_RAW, CAN_RAW_LOOPBACK, &loopback, sizeof(loopback)) < 0)
    {
        set_error_from_errno("setsockopt(CAN_RAW_LOOPBACK)");
        return false;
    }

    const int receive_own_messages = config.receive_own_messages ? 1 : 0;
    if (::setsockopt(socket_,
                     SOL_CAN_RAW,
                     CAN_RAW_RECV_OWN_MSGS,
                     &receive_own_messages,
                     sizeof(receive_own_messages)) < 0)
    {
        set_error_from_errno("setsockopt(CAN_RAW_RECV_OWN_MSGS)");
        return false;
    }

    if (config.receive_timeout.count() > 0)
    {
        timeval timeout {};
        timeout.tv_sec = static_cast<time_t>(config.receive_timeout.count() / 1000);
        timeout.tv_usec = static_cast<suseconds_t>((config.receive_timeout.count() % 1000) * 1000);

        if (::setsockopt(socket_, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0)
        {
            set_error_from_errno("setsockopt(SO_RCVTIMEO)");
            return false;
        }
    }

    if (config.non_blocking)
    {
        const int flags = ::fcntl(socket_, F_GETFL, 0);
        if (flags < 0 || ::fcntl(socket_, F_SETFL, flags | O_NONBLOCK) < 0)
        {
            set_error_from_errno("fcntl(O_NONBLOCK)");
            return false;
        }
    }

    return set_filters(config.filters);
}

bool CAN::bind_interface(const std::string& interface)
{
    ifreq request {};
    std::strncpy(request.ifr_name, interface.c_str(), IFNAMSIZ - 1);

    if (::ioctl(socket_, SIOCGIFINDEX, &request) < 0)
    {
        set_error_from_errno("ioctl(SIOCGIFINDEX)");
        return false;
    }

    sockaddr_can address {};
    address.can_family = AF_CAN;
    address.can_ifindex = request.ifr_ifindex;

    if (::bind(socket_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0)
    {
        set_error_from_errno("bind");
        return false;
    }

    return true;
}

void CAN::set_error_from_errno(const std::string& operation)
{
    last_error_ = operation + ": " + std::strerror(errno);
}
