// Equivalence classes and boundaries of the broker config parser: port, required fields, syntax of
// lines, TLS fields, duplicate keys and file loading. Pure function plus a temp file; no broker.
#include "../broker_config.hpp"
#include "ut.hpp"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <unistd.h>

namespace
{
const std::string REQUIRED = "host=h\ncafile=c\ntopic_root=t\n";

bool parse(const std::string& text, BrokerConfig& config, std::string& error)
{
    std::istringstream in(text);
    return parse_broker_config(in, config, error);
}

// Parses REQUIRED plus one extra line and returns the outcome; `port` is the resulting port.
bool parse_port_line(const std::string& value, uint16_t& port, std::string& error)
{
    BrokerConfig config;
    const bool ok = parse(REQUIRED + "port=" + value + "\n", config, error);
    port = config.port;
    return ok;
}

void port_lower_boundary_valid()
{
    uint16_t port = 0;
    std::string error;
    CHECK(parse_port_line("1", port, error));
    CHECK_EQ(port, uint16_t(1));
}

void port_upper_boundary_valid()
{
    uint16_t port = 0;
    std::string error;
    CHECK(parse_port_line("65535", port, error));
    CHECK_EQ(port, uint16_t(65535));
}

void port_zero_rejected()
{
    uint16_t port = 0;
    std::string error;
    CHECK(!parse_port_line("0", port, error));
    CHECK_EQ(error, std::string("line 4: port: expected 1-65535, got '0'"));
}

void port_65536_rejected()
{
    uint16_t port = 0;
    std::string error;
    CHECK(!parse_port_line("65536", port, error));
    CHECK_EQ(error, std::string("line 4: port: expected 1-65535, got '65536'"));
}

void port_empty_rejected()
{
    uint16_t port = 0;
    std::string error;
    CHECK(!parse_port_line("", port, error));
    CHECK_EQ(error, std::string("line 4: port: expected 1-65535, got ''"));
}

void port_non_numeric_forms_rejected()
{
    const char* bad[] = {"abc", "12ab", "-1", "+1", "8.5", "8 8", "0x50"};
    for (const char* value : bad)
    {
        uint16_t port = 0;
        std::string error;
        CHECK(!parse_port_line(value, port, error));
        CHECK(error.find("port: expected 1-65535") != std::string::npos);
    }
}

void port_longer_than_five_digits_rejected()
{
    uint16_t port = 0;
    std::string error;
    CHECK(!parse_port_line("100000", port, error));
    CHECK(!parse_port_line("000001", port, error)); // six characters, even though the value is 1
    CHECK(!parse_port_line("99999999999999999999", port, error));
}

void port_leading_zeros_within_five_chars_accepted()
{
    uint16_t port = 0;
    std::string error;
    CHECK(parse_port_line("00080", port, error));
    CHECK_EQ(port, uint16_t(80));
}

void port_surrounding_spaces_trimmed()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED + "port =  1883 \n", config, error));
    CHECK_EQ(config.port, uint16_t(1883));
}

void port_default_when_absent()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED, config, error));
    CHECK_EQ(config.port, uint16_t(8883));
}

void port_error_keeps_previous_value()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse(REQUIRED + "port=1883\nport=70000\n", config, error));
    CHECK_EQ(config.port, uint16_t(1883));
    CHECK_EQ(error, std::string("line 5: port: expected 1-65535, got '70000'"));
}

void required_empty_input()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("", config, error));
    CHECK_EQ(error, std::string("host is required"));
}

void required_each_field_missing()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("cafile=c\ntopic_root=t\n", config, error));
    CHECK_EQ(error, std::string("host is required"));
    config = BrokerConfig();
    CHECK(!parse("host=h\ntopic_root=t\n", config, error));
    CHECK_EQ(error, std::string("cafile is required"));
    config = BrokerConfig();
    CHECK(!parse("host=h\ncafile=c\n", config, error));
    CHECK_EQ(error, std::string("topic_root is required"));
}

void required_checked_in_order_host_cafile_topic()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("user=u\n", config, error));
    CHECK_EQ(error, std::string("host is required"));
    config = BrokerConfig();
    CHECK(!parse("host=h\n", config, error));
    CHECK_EQ(error, std::string("cafile is required"));
}

void required_empty_value_counts_as_missing()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("host=\ncafile=c\ntopic_root=t\n", config, error));
    CHECK_EQ(error, std::string("host is required"));
    config = BrokerConfig();
    CHECK(!parse("host=h\ncafile=   \ntopic_root=t\n", config, error));
    CHECK_EQ(error, std::string("cafile is required"));
}

void tls_fields_user_password_cafile()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED + "user=edge\npassword=s3cret\ncafile=/etc/edge/ca.crt\n", config, error));
    CHECK_EQ(config.user, std::string("edge"));
    CHECK_EQ(config.password, std::string("s3cret"));
    CHECK_EQ(config.cafile, std::string("/etc/edge/ca.crt"));
}

void tls_user_and_password_optional_default_empty()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED, config, error));
    CHECK(config.user.empty());
    CHECK(config.password.empty());
}

void tls_empty_user_and_password_allowed()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED + "user=\npassword=\n", config, error));
    CHECK(config.user.empty());
    CHECK(config.password.empty());
}

void value_with_hash_and_spaces_inside_is_kept()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED + "password=pw#1 two\n", config, error));
    CHECK_EQ(config.password, std::string("pw#1 two"));
}

void client_id_default_and_override()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED, config, error));
    CHECK_EQ(config.client_id, std::string("edge"));
    config = BrokerConfig();
    CHECK(parse(REQUIRED + "client_id=edge-7\n", config, error));
    CHECK_EQ(config.client_id, std::string("edge-7"));
}

void duplicate_key_last_wins()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse(REQUIRED + "host=first\nhost=second\n", config, error));
    CHECK_EQ(config.host, std::string("second"));
}

void comments_and_blank_lines_skipped_but_counted()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("# a\n\n   \n  # indented\nhost=h\nbogus=1\n", config, error));
    CHECK_EQ(error, std::string("line 6: unknown key 'bogus'"));
}

void line_without_equals_rejected()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("host\n", config, error));
    CHECK_EQ(error, std::string("line 1: expected key=value"));
}

void unknown_and_case_different_keys_rejected()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("Host=h\n", config, error));
    CHECK_EQ(error, std::string("line 1: unknown key 'Host'"));
    CHECK(!parse("=value\n", config, error));
    CHECK_EQ(error, std::string("line 1: unknown key ''"));
}

void crlf_line_endings_and_missing_final_newline()
{
    BrokerConfig config;
    std::string error;
    CHECK(parse("host=h\r\ncafile=c\r\ntopic_root=t", config, error));
    CHECK_EQ(config.host, std::string("h"));
    CHECK_EQ(config.topic_root, std::string("t"));
}

void error_is_cleared_on_success()
{
    BrokerConfig config;
    std::string error = "stale";
    CHECK(parse(REQUIRED, config, error));
    CHECK(error.empty());
}

void first_error_stops_parsing()
{
    BrokerConfig config;
    std::string error;
    CHECK(!parse("bogus=1\nport=0\n", config, error));
    CHECK_EQ(error, std::string("line 1: unknown key 'bogus'"));
}

void load_from_file_ok()
{
    char path[] = "/tmp/edge-broker-XXXXXX";
    const int fd = mkstemp(path);
    CHECK(fd >= 0);
    if (fd < 0)
    {
        return;
    }
    close(fd);
    {
        std::ofstream out(path);
        out << REQUIRED << "port=1\n";
    }
    BrokerConfig config;
    std::string error;
    CHECK(load_broker_config(path, config, error));
    CHECK_EQ(config.port, uint16_t(1));
    CHECK_EQ(config.topic_root, std::string("t"));
    std::remove(path);
}

void load_from_file_error_has_path_prefix()
{
    char path[] = "/tmp/edge-broker-XXXXXX";
    const int fd = mkstemp(path);
    CHECK(fd >= 0);
    if (fd < 0)
    {
        return;
    }
    close(fd);
    {
        std::ofstream out(path);
        out << "host=h\n";
    }
    BrokerConfig config;
    std::string error;
    CHECK(!load_broker_config(path, config, error));
    CHECK_EQ(error, std::string(path) + ": cafile is required");
    std::remove(path);
}

void load_empty_path_cannot_open()
{
    BrokerConfig config;
    std::string error;
    CHECK(!load_broker_config("", config, error));
    CHECK_EQ(error, std::string("cannot open "));
}
} // namespace

int main()
{
    static const ut::Case cases[] = {
        {"port_lower_boundary_valid", port_lower_boundary_valid},
        {"port_upper_boundary_valid", port_upper_boundary_valid},
        {"port_zero_rejected", port_zero_rejected},
        {"port_65536_rejected", port_65536_rejected},
        {"port_empty_rejected", port_empty_rejected},
        {"port_non_numeric_forms_rejected", port_non_numeric_forms_rejected},
        {"port_longer_than_five_digits_rejected", port_longer_than_five_digits_rejected},
        {"port_leading_zeros_within_five_chars_accepted", port_leading_zeros_within_five_chars_accepted},
        {"port_surrounding_spaces_trimmed", port_surrounding_spaces_trimmed},
        {"port_default_when_absent", port_default_when_absent},
        {"port_error_keeps_previous_value", port_error_keeps_previous_value},
        {"required_empty_input", required_empty_input},
        {"required_each_field_missing", required_each_field_missing},
        {"required_checked_in_order_host_cafile_topic", required_checked_in_order_host_cafile_topic},
        {"required_empty_value_counts_as_missing", required_empty_value_counts_as_missing},
        {"tls_fields_user_password_cafile", tls_fields_user_password_cafile},
        {"tls_user_and_password_optional_default_empty", tls_user_and_password_optional_default_empty},
        {"tls_empty_user_and_password_allowed", tls_empty_user_and_password_allowed},
        {"value_with_hash_and_spaces_inside_is_kept", value_with_hash_and_spaces_inside_is_kept},
        {"client_id_default_and_override", client_id_default_and_override},
        {"duplicate_key_last_wins", duplicate_key_last_wins},
        {"comments_and_blank_lines_skipped_but_counted", comments_and_blank_lines_skipped_but_counted},
        {"line_without_equals_rejected", line_without_equals_rejected},
        {"unknown_and_case_different_keys_rejected", unknown_and_case_different_keys_rejected},
        {"crlf_line_endings_and_missing_final_newline", crlf_line_endings_and_missing_final_newline},
        {"error_is_cleared_on_success", error_is_cleared_on_success},
        {"first_error_stops_parsing", first_error_stops_parsing},
        {"load_from_file_ok", load_from_file_ok},
        {"load_from_file_error_has_path_prefix", load_from_file_error_has_path_prefix},
        {"load_empty_path_cannot_open", load_empty_path_cannot_open},
    };
    return ut::run(cases);
}
