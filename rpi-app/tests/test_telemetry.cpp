// Pure-function checks for the telemetry line format; needs no vcan or privileges.
#include "../telemetry.hpp"

#include <cassert>

namespace
{
void check_standard_frame()
{
    CANFrame frame;
    frame.id = 0x123;
    frame.size = 3;
    frame.data = {0xDE, 0xAD, 0x01};
    assert(to_telemetry_line(frame) == "123 DEAD01");
}

void check_extended_frame()
{
    CANFrame frame;
    frame.id = 0x1ABCDEF;
    frame.extended = true;
    frame.size = 1;
    frame.data = {0xFF};
    assert(to_telemetry_line(frame) == "01ABCDEF x FF");
}

void check_empty_and_oversized_payload()
{
    CANFrame frame;
    frame.id = 0x7FF;
    assert(to_telemetry_line(frame) == "7FF ");
    frame.size = 255; // clamped to the 8-byte buffer
    assert(to_telemetry_line(frame) == "7FF 0000000000000000");
}
} // namespace

int main()
{
    check_standard_frame();
    check_extended_frame();
    check_empty_and_oversized_payload();
    return 0;
}
