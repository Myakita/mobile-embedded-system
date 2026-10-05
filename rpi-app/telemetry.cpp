#include "telemetry.hpp"

#include <cstdio>

std::string to_telemetry_line(const CANFrame& frame)
{
    char buf[16];
    std::snprintf(buf, sizeof buf, frame.extended ? "%08X" : "%03X", static_cast<unsigned>(frame.id));
    std::string line = buf;
    if (frame.extended)
    {
        line += " x";
    }
    line += ' ';
    for (uint8_t i = 0; i < frame.size && i < frame.data.size(); ++i)
    {
        std::snprintf(buf, sizeof buf, "%02X", static_cast<unsigned>(frame.data[i]));
        line += buf;
    }
    return line;
}
