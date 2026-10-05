#pragma once

#include <string>

#include "interface/can.hpp"

// One CAN frame as a single text line: "<id hex> [x] <payload hex>". No I/O, so it can be
// tested without vcan. This is where the LMesh/telemetry encoding plugs in later.
std::string to_telemetry_line(const CANFrame& frame);
