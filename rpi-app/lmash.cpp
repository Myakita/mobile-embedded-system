#include "lmash.hpp"

#include <cstdio>

namespace
{
// Offsets from emulator/lmash_v1.py: version, messageType, commandType, flags, ttl (1 byte each),
// sequence and timestamp (4 each), then three 8-byte ids.
constexpr std::size_t VERSION_AT = 0;
constexpr std::size_t MESSAGE_TYPE_AT = 1;
constexpr std::size_t DEVICE_SERIAL_AT = 13;
constexpr std::size_t DESTINATION_AT = 29;

uint64_t read_u64_le(const uint8_t* data)
{
    uint64_t value = 0;
    for (int i = 7; i >= 0; --i)
    {
        value = (value << 8) | data[i];
    }
    return value;
}

std::string hex_id(uint64_t id)
{
    char buf[17];
    std::snprintf(buf, sizeof buf, "%016llX", static_cast<unsigned long long>(id));
    return buf;
}

std::string trim_slashes(const std::string& text)
{
    std::size_t begin = 0;
    std::size_t end = text.size();
    while (begin < end && text[begin] == '/')
    {
        ++begin;
    }
    while (end > begin && text[end - 1] == '/')
    {
        --end;
    }
    return text.substr(begin, end - begin);
}
} // namespace

bool lmash_topic(
    const std::string& root, const uint8_t* frame, std::size_t size, std::string& topic, std::string& error)
{
    if (frame == nullptr || size != LMASH_V1_SIZE)
    {
        error = "frame is " + std::to_string(size) + " bytes, expected " + std::to_string(LMASH_V1_SIZE);
        return false;
    }
    if (frame[VERSION_AT] != 1)
    {
        error = "unsupported LMash version " + std::to_string(frame[VERSION_AT]);
        return false;
    }
    const char* type = nullptr;
    if (frame[MESSAGE_TYPE_AT] == 0)
    {
        type = "telemetry";
    }
    else if (frame[MESSAGE_TYPE_AT] == 1)
    {
        type = "command";
    }
    else
    {
        error = "unknown messageType " + std::to_string(frame[MESSAGE_TYPE_AT]);
        return false;
    }
    topic = trim_slashes(root) + "/" + type + "/to/" + hex_id(read_u64_le(frame + DESTINATION_AT)) +
            "/from/" + hex_id(read_u64_le(frame + DEVICE_SERIAL_AT));
    return true;
}
