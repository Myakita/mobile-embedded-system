// Equivalence classes and boundaries of LMash v1 routing (protocol/spec/lmash-v1.md): frame length,
// version, messageType, id byte order, root normalisation, protocol vectors and a table of
// encode -> topic -> decode round trips. Pure functions, no broker.
#include "../lmash.hpp"
#include "ut.hpp"

#include <array>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <vector>

#ifndef PROTOCOL_VECTORS_DIR
#error "PROTOCOL_VECTORS_DIR must point at protocol/vectors"
#endif

namespace
{
using Frame = std::array<uint8_t, LMASH_V1_SIZE>;

struct Header
{
    uint8_t version {1};
    uint8_t message_type {0};
    uint8_t command_type {0};
    uint8_t flags {0};
    uint8_t ttl {0};
    uint32_t sequence {0};
    uint32_t timestamp {0};
    uint64_t device_serial {0};
    uint64_t user_id {0};
    uint64_t destination_id {0};
};

void put_le(Frame& frame, std::size_t at, uint64_t value, int bytes)
{
    for (int i = 0; i < bytes; ++i)
    {
        frame[at + i] = static_cast<uint8_t>(value >> (8 * i));
    }
}

// Encoder written from the field table of the spec (offsets 0,1,2,3,4,5,9,13,21,29).
Frame encode(const Header& h)
{
    Frame frame {};
    frame[0] = h.version;
    frame[1] = h.message_type;
    frame[2] = h.command_type;
    frame[3] = h.flags;
    frame[4] = h.ttl;
    put_le(frame, 5, h.sequence, 4);
    put_le(frame, 9, h.timestamp, 4);
    put_le(frame, 13, h.device_serial, 8);
    put_le(frame, 21, h.user_id, 8);
    put_le(frame, 29, h.destination_id, 8);
    return frame;
}

std::string hex16(uint64_t value)
{
    char buf[17];
    std::snprintf(buf, sizeof buf, "%016llX", static_cast<unsigned long long>(value));
    return buf;
}

std::string topic_for(const Header& h, const std::string& root = "r")
{
    const Frame frame = encode(h);
    std::string topic = "untouched";
    std::string error;
    return lmash_topic(root, frame.data(), frame.size(), topic, error) ? topic : "REJECTED:" + error;
}

std::string error_for(const uint8_t* data, std::size_t size, std::string* topic_out = nullptr)
{
    std::string topic = "untouched";
    std::string error;
    const bool ok = lmash_topic("r", data, size, topic, error);
    CHECK(!ok);
    if (topic_out != nullptr)
    {
        *topic_out = topic;
    }
    return error;
}

std::string read_file(const std::string& name)
{
    std::ifstream in(std::string(PROTOCOL_VECTORS_DIR) + "/" + name);
    std::ostringstream text;
    text << in.rdbuf();
    return text.str();
}

std::string json_string(const std::string& text, const std::string& key)
{
    const auto at = text.find("\"" + key + "\"");
    const auto open = text.find('"', text.find(':', at) + 1);
    return text.substr(open + 1, text.find('"', open + 1) - open - 1);
}

uint64_t json_number(const std::string& text, const std::string& key)
{
    const auto at = text.find("\"" + key + "\"");
    return std::stoull(text.substr(text.find(':', at) + 1));
}

std::vector<uint8_t> from_hex(const std::string& hex)
{
    std::vector<uint8_t> bytes(hex.size() / 2);
    for (std::size_t i = 0; i < bytes.size(); ++i)
    {
        bytes[i] = static_cast<uint8_t>(std::strtoul(hex.substr(2 * i, 2).c_str(), nullptr, 16));
    }
    return bytes;
}

void check_vector(const char* file, const char* type_word)
{
    const std::string json = read_file(file);
    CHECK(!json.empty());
    const auto wire = from_hex(json_string(json, "wireHex"));
    CHECK_EQ(wire.size(), LMASH_V1_SIZE);
    CHECK_EQ(json_number(json, "payloadSize"), uint64_t(LMASH_V1_SIZE));
    std::string topic;
    std::string error;
    CHECK(lmash_topic("net/path", wire.data(), wire.size(), topic, error));
    const std::string expected = std::string("net/path/") + type_word + "/to/" +
                                 hex16(json_number(json, "destinationId")) + "/from/" +
                                 hex16(json_number(json, "deviceSerial"));
    CHECK_EQ(topic, expected);
    // Re-encoding the vector's header fields reproduces the vector's id bytes at the spec offsets.
    Header h;
    h.version = static_cast<uint8_t>(json_number(json, "version"));
    h.message_type = type_word == std::string("telemetry") ? 0 : 1;
    h.device_serial = json_number(json, "deviceSerial");
    h.destination_id = json_number(json, "destinationId");
    const Frame re = encode(h);
    CHECK(std::memcmp(re.data() + 13, wire.data() + 13, 8) == 0);
    CHECK(std::memcmp(re.data() + 29, wire.data() + 29, 8) == 0);
}

void vector_telemetry_topic() { check_vector("telemetry-v1.json", "telemetry"); }
void vector_command_return_topic() { check_vector("command-return-v1.json", "command"); }

void valid_telemetry_minimal_frame()
{
    CHECK_EQ(topic_for(Header {}), std::string("r/telemetry/to/0000000000000000/from/0000000000000000"));
}

void valid_command_frame()
{
    Header h;
    h.message_type = 1;
    h.device_serial = 0xA;
    h.destination_id = 0xB;
    CHECK_EQ(topic_for(h), std::string("r/command/to/000000000000000B/from/000000000000000A"));
}

void length_zero_rejected()
{
    uint8_t byte = 0;
    std::string topic;
    CHECK_EQ(error_for(&byte, 0, &topic), std::string("frame is 0 bytes, expected 54"));
    CHECK_EQ(topic, std::string("untouched"));
}

void length_one_rejected()
{
    const Frame frame = encode(Header {});
    CHECK_EQ(error_for(frame.data(), 1), std::string("frame is 1 bytes, expected 54"));
}

void length_53_rejected()
{
    const Frame frame = encode(Header {});
    std::string topic;
    CHECK_EQ(error_for(frame.data(), 53, &topic), std::string("frame is 53 bytes, expected 54"));
    CHECK_EQ(topic, std::string("untouched"));
}

void length_55_rejected()
{
    std::array<uint8_t, 55> buffer {};
    buffer[0] = 1;
    std::string topic;
    CHECK_EQ(error_for(buffer.data(), 55, &topic), std::string("frame is 55 bytes, expected 54"));
    CHECK_EQ(topic, std::string("untouched"));
}

void length_108_double_frame_rejected()
{
    std::array<uint8_t, 108> buffer {};
    buffer[0] = 1;
    CHECK_EQ(error_for(buffer.data(), 108), std::string("frame is 108 bytes, expected 54"));
}

void null_pointer_rejected_with_size_message()
{
    std::string topic;
    CHECK_EQ(error_for(nullptr, 54, &topic), std::string("frame is 54 bytes, expected 54"));
    CHECK_EQ(topic, std::string("untouched"));
    CHECK_EQ(error_for(nullptr, 0), std::string("frame is 0 bytes, expected 54"));
}

void version_zero_rejected()
{
    Header h;
    h.version = 0;
    CHECK_EQ(topic_for(h), std::string("REJECTED:unsupported LMash version 0"));
}

void version_one_accepted()
{
    Header h;
    h.version = 1;
    CHECK(topic_for(h).rfind("r/telemetry/", 0) == 0);
}

void version_two_rejected()
{
    Header h;
    h.version = 2;
    CHECK_EQ(topic_for(h), std::string("REJECTED:unsupported LMash version 2"));
}

void version_255_rejected()
{
    Header h;
    h.version = 255;
    CHECK_EQ(topic_for(h), std::string("REJECTED:unsupported LMash version 255"));
}

void every_version_except_one_rejected()
{
    for (int v = 0; v < 256; ++v)
    {
        Header h;
        h.version = static_cast<uint8_t>(v);
        const bool accepted = topic_for(h).rfind("REJECTED:", 0) != 0;
        CHECK(accepted == (v == 1));
    }
}

void message_type_two_rejected()
{
    Header h;
    h.message_type = 2;
    CHECK_EQ(topic_for(h), std::string("REJECTED:unknown messageType 2"));
}

void message_type_255_rejected()
{
    Header h;
    h.message_type = 255;
    CHECK_EQ(topic_for(h), std::string("REJECTED:unknown messageType 255"));
}

void message_type_only_zero_and_one_accepted()
{
    for (int t = 0; t < 256; ++t)
    {
        Header h;
        h.message_type = static_cast<uint8_t>(t);
        const bool accepted = topic_for(h).rfind("REJECTED:", 0) != 0;
        CHECK(accepted == (t <= 1));
    }
}

void size_error_wins_over_version_error()
{
    std::array<uint8_t, 53> buffer {};
    buffer[0] = 9;
    CHECK(error_for(buffer.data(), 53).find("53 bytes") != std::string::npos);
}

void version_error_wins_over_message_type_error()
{
    Header h;
    h.version = 7;
    h.message_type = 9;
    CHECK_EQ(topic_for(h), std::string("REJECTED:unsupported LMash version 7"));
}

void failed_frames_leave_topic_untouched()
{
    Header bad_version;
    bad_version.version = 3;
    Header bad_type;
    bad_type.message_type = 3;
    for (const Header& h : {bad_version, bad_type})
    {
        const Frame frame = encode(h);
        std::string topic = "keep";
        std::string error;
        CHECK(!lmash_topic("r", frame.data(), frame.size(), topic, error));
        CHECK_EQ(topic, std::string("keep"));
        CHECK(!error.empty());
    }
}

void id_min_zero_formats_sixteen_zeros()
{
    CHECK_EQ(topic_for(Header {}, "x"), std::string("x/telemetry/to/0000000000000000/from/0000000000000000"));
}

void id_max_u64_formats_sixteen_f()
{
    Header h;
    h.destination_id = UINT64_MAX;
    h.device_serial = UINT64_MAX;
    CHECK_EQ(topic_for(h, "x"), std::string("x/telemetry/to/FFFFFFFFFFFFFFFF/from/FFFFFFFFFFFFFFFF"));
}

void id_sign_bit_is_unsigned()
{
    Header h;
    h.destination_id = 0x8000000000000000ull;
    h.device_serial = 0x7FFFFFFFFFFFFFFFull;
    CHECK_EQ(topic_for(h, "x"), std::string("x/telemetry/to/8000000000000000/from/7FFFFFFFFFFFFFFF"));
}

void id_is_little_endian_asymmetric_pattern()
{
    Header h;
    h.destination_id = 0x0123456789ABCDEFull;
    h.device_serial = 0xFEDCBA9876543210ull;
    CHECK_EQ(topic_for(h, "x"), std::string("x/telemetry/to/0123456789ABCDEF/from/FEDCBA9876543210"));
}

void id_single_byte_positions()
{
    Frame frame = encode(Header {});
    for (int i = 0; i < 8; ++i)
    {
        Frame f = frame;
        f[29 + i] = 0xAB; // destination byte i
        f[13 + i] = 0xCD; // serial byte i
        std::string topic;
        std::string error;
        CHECK(lmash_topic("x", f.data(), f.size(), topic, error));
        const uint64_t dest = 0xABull << (8 * i);
        const uint64_t serial = 0xCDull << (8 * i);
        CHECK_EQ(topic, "x/telemetry/to/" + hex16(dest) + "/from/" + hex16(serial));
    }
}

void other_header_fields_do_not_affect_topic()
{
    Header base;
    base.device_serial = 0x1122334455667788ull;
    base.destination_id = 0x99AABBCCDDEEFF00ull;
    Header noisy = base;
    noisy.command_type = 255;
    noisy.flags = 255;
    noisy.ttl = 255;
    noisy.sequence = UINT32_MAX;
    noisy.timestamp = UINT32_MAX;
    noisy.user_id = UINT64_MAX;
    CHECK_EQ(topic_for(noisy), topic_for(base));
}

void payload_tail_does_not_affect_topic()
{
    Frame frame = encode(Header {});
    std::string a;
    std::string b;
    std::string error;
    CHECK(lmash_topic("r", frame.data(), frame.size(), a, error));
    for (std::size_t i = 37; i < LMASH_V1_SIZE; ++i)
    {
        frame[i] = 0xFF;
    }
    CHECK(lmash_topic("r", frame.data(), frame.size(), b, error));
    CHECK_EQ(a, b);
}

void unaligned_buffer_pointer_is_handled()
{
    Header h;
    h.destination_id = 0x0102030405060708ull;
    const Frame frame = encode(h);
    std::array<uint8_t, LMASH_V1_SIZE + 3> shifted {};
    std::memcpy(shifted.data() + 1, frame.data(), frame.size());
    std::string topic;
    std::string error;
    CHECK(lmash_topic("r", shifted.data() + 1, LMASH_V1_SIZE, topic, error));
    CHECK_EQ(topic, topic_for(h));
}

void root_slashes_trimmed_at_both_ends_only()
{
    const std::string tail = "/telemetry/to/0000000000000000/from/0000000000000000";
    CHECK_EQ(topic_for(Header {}, "a/b"), "a/b" + tail);
    CHECK_EQ(topic_for(Header {}, "/a/b/"), "a/b" + tail);
    CHECK_EQ(topic_for(Header {}, "///a///"), "a" + tail);
    CHECK_EQ(topic_for(Header {}, "a//b"), "a//b" + tail);
}

void root_empty_or_only_slashes_gives_leading_slash()
{
    const std::string tail = "/telemetry/to/0000000000000000/from/0000000000000000";
    CHECK_EQ(topic_for(Header {}, ""), tail);
    CHECK_EQ(topic_for(Header {}, "///"), tail);
}

void roundtrip_table_ids_and_types()
{
    const uint64_t ids[] = {0,
                            1,
                            0xFF,
                            0x100,
                            0xFFFFFFFFull,
                            0x100000000ull,
                            0x7FFFFFFFFFFFFFFFull,
                            0x8000000000000000ull,
                            0xFFFFFFFFFFFFFFFFull,
                            0x0123456789ABCDEFull};
    for (const uint64_t dest : ids)
    {
        for (const uint64_t serial : ids)
        {
            for (uint8_t type = 0; type <= 1; ++type)
            {
                Header h;
                h.message_type = type;
                h.device_serial = serial;
                h.destination_id = dest;
                const std::string expected = std::string("m/") + (type == 0 ? "telemetry" : "command") +
                                             "/to/" + hex16(dest) + "/from/" + hex16(serial);
                CHECK_EQ(topic_for(h, "m"), expected);
            }
        }
    }
}

void roundtrip_pseudo_random_ids_parse_back()
{
    uint64_t state = 0x9E3779B97F4A7C15ull;
    auto next = [&state]
    {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        return state;
    };
    for (int i = 0; i < 500; ++i)
    {
        Header h;
        h.message_type = static_cast<uint8_t>(next() & 1);
        h.device_serial = next();
        h.destination_id = next();
        h.sequence = static_cast<uint32_t>(next());
        const std::string topic = topic_for(h, "p");
        const auto to = topic.find("/to/");
        const auto from = topic.find("/from/");
        CHECK(to != std::string::npos && from != std::string::npos);
        const uint64_t dest = std::stoull(topic.substr(to + 4, 16), nullptr, 16);
        const uint64_t serial = std::stoull(topic.substr(from + 6, 16), nullptr, 16);
        CHECK(dest == h.destination_id);
        CHECK(serial == h.device_serial);
    }
}
} // namespace

int main()
{
    static const ut::Case cases[] = {
        {"vector_telemetry_topic", vector_telemetry_topic},
        {"vector_command_return_topic", vector_command_return_topic},
        {"valid_telemetry_minimal_frame", valid_telemetry_minimal_frame},
        {"valid_command_frame", valid_command_frame},
        {"length_zero_rejected", length_zero_rejected},
        {"length_one_rejected", length_one_rejected},
        {"length_53_rejected", length_53_rejected},
        {"length_55_rejected", length_55_rejected},
        {"length_108_double_frame_rejected", length_108_double_frame_rejected},
        {"null_pointer_rejected_with_size_message", null_pointer_rejected_with_size_message},
        {"version_zero_rejected", version_zero_rejected},
        {"version_one_accepted", version_one_accepted},
        {"version_two_rejected", version_two_rejected},
        {"version_255_rejected", version_255_rejected},
        {"every_version_except_one_rejected", every_version_except_one_rejected},
        {"message_type_two_rejected", message_type_two_rejected},
        {"message_type_255_rejected", message_type_255_rejected},
        {"message_type_only_zero_and_one_accepted", message_type_only_zero_and_one_accepted},
        {"size_error_wins_over_version_error", size_error_wins_over_version_error},
        {"version_error_wins_over_message_type_error", version_error_wins_over_message_type_error},
        {"failed_frames_leave_topic_untouched", failed_frames_leave_topic_untouched},
        {"id_min_zero_formats_sixteen_zeros", id_min_zero_formats_sixteen_zeros},
        {"id_max_u64_formats_sixteen_f", id_max_u64_formats_sixteen_f},
        {"id_sign_bit_is_unsigned", id_sign_bit_is_unsigned},
        {"id_is_little_endian_asymmetric_pattern", id_is_little_endian_asymmetric_pattern},
        {"id_single_byte_positions", id_single_byte_positions},
        {"other_header_fields_do_not_affect_topic", other_header_fields_do_not_affect_topic},
        {"payload_tail_does_not_affect_topic", payload_tail_does_not_affect_topic},
        {"unaligned_buffer_pointer_is_handled", unaligned_buffer_pointer_is_handled},
        {"root_slashes_trimmed_at_both_ends_only", root_slashes_trimmed_at_both_ends_only},
        {"root_empty_or_only_slashes_gives_leading_slash", root_empty_or_only_slashes_gives_leading_slash},
        {"roundtrip_table_ids_and_types", roundtrip_table_ids_and_types},
        {"roundtrip_pseudo_random_ids_parse_back", roundtrip_pseudo_random_ids_parse_back},
    };
    return ut::run(cases);
}
