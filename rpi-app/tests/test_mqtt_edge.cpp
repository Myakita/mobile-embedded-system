// States of the MQTT client reachable without a broker: fresh object, publish before open, close
// when not open, open that fails during setup (missing CA file).
#include "../mqtt.hpp"
#include "ut.hpp"

namespace
{
BrokerConfig config_with_cafile(const std::string& cafile)
{
    BrokerConfig config;
    config.host = "127.0.0.1";
    config.port = 1; // nothing listens here; setup must fail earlier anyway
    config.cafile = cafile;
    config.topic_root = "t";
    return config;
}

void fresh_client_is_closed_without_error()
{
    Mqtt mqtt;
    CHECK(!mqtt.is_open());
    CHECK(mqtt.last_error().empty());
}

void publish_before_open_fails()
{
    Mqtt mqtt;
    const uint8_t byte = 1;
    CHECK(!mqtt.publish("t/telemetry/to/0/from/0", &byte, 1));
    CHECK_EQ(mqtt.last_error(), std::string("MQTT client is not open"));
}

void publish_empty_payload_before_open_fails()
{
    Mqtt mqtt;
    CHECK(!mqtt.publish("t", nullptr, 0));
    CHECK_EQ(mqtt.last_error(), std::string("MQTT client is not open"));
}

void close_when_not_open_is_idempotent()
{
    Mqtt mqtt;
    mqtt.close();
    mqtt.close();
    CHECK(!mqtt.is_open());
}

void open_with_missing_cafile_fails_in_setup()
{
    Mqtt mqtt;
    CHECK(!mqtt.open(config_with_cafile("/nonexistent/ca.crt"), std::chrono::milliseconds(200)));
    CHECK(!mqtt.is_open());
    CHECK(mqtt.last_error().rfind("setup: ", 0) == 0);
}

void publish_after_failed_open_still_fails()
{
    Mqtt mqtt;
    CHECK(!mqtt.open(config_with_cafile("/nonexistent/ca.crt"), std::chrono::milliseconds(200)));
    const uint8_t byte = 1;
    CHECK(!mqtt.publish("t", &byte, 1));
    CHECK_EQ(mqtt.last_error(), std::string("MQTT client is not open"));
}
} // namespace

int main()
{
    static const ut::Case cases[] = {
        {"fresh_client_is_closed_without_error", fresh_client_is_closed_without_error},
        {"publish_before_open_fails", publish_before_open_fails},
        {"publish_empty_payload_before_open_fails", publish_empty_payload_before_open_fails},
        {"close_when_not_open_is_idempotent", close_when_not_open_is_idempotent},
        {"open_with_missing_cafile_fails_in_setup", open_with_missing_cafile_fails_in_setup},
        {"publish_after_failed_open_still_fails", publish_after_failed_open_still_fails},
    };
    return ut::run(cases);
}
