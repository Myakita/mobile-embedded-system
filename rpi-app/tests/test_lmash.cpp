// Topic routing of LMash v1 frames; pure functions, needs no broker or privileges. The frames are
// the wireHex values of protocol/vectors/{telemetry,command-return}-v1.json.
#include "../lmash.hpp"

#include <cassert>
#include <vector>

namespace
{
const char* TELEMETRY_HEX = "0100000504d701000080abe0662102aa1900000000e9030000000000000412837a00000000580e54"
                            "007850335f3b21ee7a6c168246"
                            "03";
const char* COMMAND_HEX = "010103000466000000b2abe0662102aa1900000000e9030000000000000412837a0000000000000000"
                          "00000000000000000000000000";

std::vector<uint8_t> from_hex(const std::string& hex)
{
    std::vector<uint8_t> bytes;
    for (std::size_t i = 0; i + 1 < hex.size(); i += 2)
    {
        bytes.push_back(static_cast<uint8_t>(std::stoi(hex.substr(i, 2), nullptr, 16)));
    }
    return bytes;
}

void check_telemetry_topic()
{
    const auto frame = from_hex(TELEMETRY_HEX);
    assert(frame.size() == LMASH_V1_SIZE);
    std::string topic;
    std::string error;
    assert(lmash_topic("mesh-a/7F10/21A0", frame.data(), frame.size(), topic, error));
    assert(topic == "mesh-a/7F10/21A0/telemetry/to/000000007A831204/from/0000000019AA0221");
}

void check_command_topic_and_slashes()
{
    const auto frame = from_hex(COMMAND_HEX);
    std::string topic;
    std::string error;
    assert(lmash_topic("/mesh-a/7F10/", frame.data(), frame.size(), topic, error));
    assert(topic == "mesh-a/7F10/command/to/000000007A831204/from/0000000019AA0221");
}

void check_rejects_bad_frames()
{
    std::string topic = "untouched";
    std::string error;

    auto frame = from_hex(TELEMETRY_HEX);
    assert(!lmash_topic("r", frame.data(), frame.size() - 1, topic, error));
    assert(error.find("53 bytes") != std::string::npos);

    frame[0] = 2;
    assert(!lmash_topic("r", frame.data(), frame.size(), topic, error));
    assert(error.find("version 2") != std::string::npos);

    frame[0] = 1;
    frame[1] = 2;
    assert(!lmash_topic("r", frame.data(), frame.size(), topic, error));
    assert(error.find("messageType 2") != std::string::npos);

    assert(!lmash_topic("r", nullptr, LMASH_V1_SIZE, topic, error));
    assert(topic == "untouched");
}
} // namespace

int main()
{
    check_telemetry_topic();
    check_command_topic_and_slashes();
    check_rejects_bad_frames();
    return 0;
}
