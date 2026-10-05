// Edge skeleton: reads CAN frames from a (virtual) interface and prints one telemetry
// line per frame. Real logic (LMesh, MQTT) lands here later; see issues #7-#12.
#include "interface/can.hpp"
#include "telemetry.hpp"

#include <cstdio>

int main(int argc, char** argv)
{
    CANConfig config;
    if (argc > 1)
    {
        config.interface = argv[1];
    }

    CAN can;
    if (!can.open(config))
    {
        std::fprintf(
            stderr, "edge: cannot open %s: %s\n", config.interface.c_str(), can.last_error().c_str());
        return 1;
    }

    CANFrame frame;
    while (can.read(frame))
    {
        std::puts(to_telemetry_line(frame).c_str());
        std::fflush(stdout);
    }
    std::fprintf(stderr, "edge: read failed: %s\n", can.last_error().c_str());
    return 1;
}
