// Equivalence classes and boundaries of the telemetry line format (id width, payload length,
// hex case); pure function, needs no vcan.
#include "../telemetry.hpp"
#include "ut.hpp"

namespace
{
CANFrame make(uint32_t id, bool extended, uint8_t size, std::initializer_list<uint8_t> bytes)
{
    CANFrame frame;
    frame.id = id;
    frame.extended = extended;
    frame.size = size;
    std::size_t i = 0;
    for (const uint8_t b : bytes)
    {
        frame.data[i++] = b;
    }
    return frame;
}

void standard_min_id_empty() { CHECK_EQ(to_telemetry_line(make(0, false, 0, {})), std::string("000 ")); }

void standard_max_id_full_payload()
{
    CHECK_EQ(to_telemetry_line(make(0x7FF, false, 8, {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF})),
             std::string("7FF FFFFFFFFFFFFFFFF"));
}

void standard_id_padded_to_three_digits()
{
    CHECK_EQ(to_telemetry_line(make(0x001, false, 1, {0x00})), std::string("001 00"));
    CHECK_EQ(to_telemetry_line(make(0x0AB, false, 1, {0x01})), std::string("0AB 01"));
}

void standard_id_above_11_bits_not_truncated()
{
    CHECK_EQ(to_telemetry_line(make(0x800, false, 1, {0x01})), std::string("800 01"));
    CHECK_EQ(to_telemetry_line(make(0x1000, false, 1, {0x01})), std::string("1000 01"));
}

void extended_min_id() { CHECK_EQ(to_telemetry_line(make(0, true, 0, {})), std::string("00000000 x ")); }

void extended_max_29_bit_id_full_payload()
{
    CHECK_EQ(to_telemetry_line(make(0x1FFFFFFF, true, 8, {0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF})),
             std::string("1FFFFFFF x 0123456789ABCDEF"));
}

void extended_small_id_keeps_eight_digits()
{
    CHECK_EQ(to_telemetry_line(make(0x7FF, true, 1, {0x01})), std::string("000007FF x 01"));
}

void extended_id_32_bit_max()
{
    CHECK_EQ(to_telemetry_line(make(0xFFFFFFFFu, true, 1, {0x00})), std::string("FFFFFFFF x 00"));
}

void payload_bytes_are_zero_padded_uppercase()
{
    CHECK_EQ(to_telemetry_line(make(0x100, false, 4, {0x0A, 0x00, 0xF0, 0xab})), std::string("100 0A00F0AB"));
}

void payload_length_boundaries()
{
    std::initializer_list<uint8_t> bytes = {0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88};
    CHECK_EQ(to_telemetry_line(make(0x1, false, 1, bytes)), std::string("001 11"));
    CHECK_EQ(to_telemetry_line(make(0x1, false, 7, bytes)), std::string("001 11223344556677"));
    CHECK_EQ(to_telemetry_line(make(0x1, false, 8, bytes)), std::string("001 1122334455667788"));
    CHECK_EQ(to_telemetry_line(make(0x1, false, 9, bytes)), std::string("001 1122334455667788"));
}

void payload_size_255_clamped_to_buffer()
{
    CHECK_EQ(to_telemetry_line(make(0x1, true, 255, {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x01, 0x02})),
             std::string("00000001 x AABBCCDDEEFF0102"));
}

void bytes_beyond_size_are_ignored()
{
    CHECK_EQ(to_telemetry_line(make(0x2, false, 2, {0xDE, 0xAD, 0xBE, 0xEF, 0x01, 0x02, 0x03, 0x04})),
             std::string("002 DEAD"));
}

void remote_and_error_flags_do_not_change_line()
{
    CANFrame plain = make(0x321, false, 2, {0x01, 0x02});
    CANFrame flagged = plain;
    flagged.remote_request = true;
    flagged.error = true;
    CHECK_EQ(to_telemetry_line(flagged), to_telemetry_line(plain));
    CHECK_EQ(to_telemetry_line(flagged), std::string("321 0102"));
}

void standard_and_extended_with_same_id_differ()
{
    const std::string standard = to_telemetry_line(make(0x123, false, 1, {0x01}));
    const std::string extended = to_telemetry_line(make(0x123, true, 1, {0x01}));
    CHECK_EQ(standard, std::string("123 01"));
    CHECK_EQ(extended, std::string("00000123 x 01"));
}

void empty_payload_line_ends_with_space_only()
{
    const std::string line = to_telemetry_line(make(0x5, false, 0, {}));
    CHECK_EQ(line, std::string("005 "));
    CHECK_EQ(line.size(), std::size_t(4));
}
} // namespace

int main()
{
    static const ut::Case cases[] = {
        {"standard_min_id_empty", standard_min_id_empty},
        {"standard_max_id_full_payload", standard_max_id_full_payload},
        {"standard_id_padded_to_three_digits", standard_id_padded_to_three_digits},
        {"standard_id_above_11_bits_not_truncated", standard_id_above_11_bits_not_truncated},
        {"extended_min_id", extended_min_id},
        {"extended_max_29_bit_id_full_payload", extended_max_29_bit_id_full_payload},
        {"extended_small_id_keeps_eight_digits", extended_small_id_keeps_eight_digits},
        {"extended_id_32_bit_max", extended_id_32_bit_max},
        {"payload_bytes_are_zero_padded_uppercase", payload_bytes_are_zero_padded_uppercase},
        {"payload_length_boundaries", payload_length_boundaries},
        {"payload_size_255_clamped_to_buffer", payload_size_255_clamped_to_buffer},
        {"bytes_beyond_size_are_ignored", bytes_beyond_size_are_ignored},
        {"remote_and_error_flags_do_not_change_line", remote_and_error_flags_do_not_change_line},
        {"standard_and_extended_with_same_id_differ", standard_and_extended_with_same_id_differ},
        {"empty_payload_line_ends_with_space_only", empty_payload_line_ends_with_space_only},
    };
    return ut::run(cases);
}
