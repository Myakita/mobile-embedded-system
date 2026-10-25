#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

// LMash v1 frame (protocol/spec/lmash-v1.md): 54 bytes, little-endian. Only the header fields edge
// needs to route a frame are read here; the payload is forwarded untouched.
constexpr std::size_t LMASH_V1_SIZE = 54;

// MQTT topic for one frame, the same scheme as the Android app's MqttTopicBuilder:
//   <root>/<telemetry|command>/to/<destinationId %016X>/from/<deviceSerial %016X>
// Rejects a frame of the wrong size, a version other than 1 or an unknown messageType; `error`
// says which, and `topic` is left untouched.
bool lmash_topic(
    const std::string& root, const uint8_t* frame, std::size_t size, std::string& topic, std::string& error);
