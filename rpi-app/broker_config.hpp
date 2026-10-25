#pragma once

#include <cstdint>
#include <istream>
#include <string>

// Where and how edge reaches the MQTT broker. The same key=value file is generated once for the
// whole stand (emulator/stand/lib.sh), so broker parameters have a single source.
struct BrokerConfig
{
    std::string host;
    uint16_t port {8883};
    std::string user;
    std::string password;
    std::string cafile;
    // Network root and hierarchy path joined, e.g. "mesh-a/7F10/21A0" (see the app's MqttTopicBuilder).
    std::string topic_root;
    std::string client_id {"edge"};
};

// One "key=value" per line; blank lines and lines starting with '#' are skipped, the value is
// everything after the first '='. host, cafile and topic_root are required (the stand is always
// TLS), unknown keys are errors so a typo fails loudly instead of silently using a default.
bool parse_broker_config(std::istream& in, BrokerConfig& config, std::string& error);

bool load_broker_config(const std::string& path, BrokerConfig& config, std::string& error);
