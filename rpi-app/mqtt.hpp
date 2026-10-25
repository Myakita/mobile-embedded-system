#pragma once

#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <string>

#include "broker_config.hpp"

struct mosquitto;

// Blocking MQTT client over libmosquitto, in the style of emulator/interface: bool results and
// last_error(). libmosquitto's own thread runs the network loop and reconnects after a drop, so
// open() succeeds once and publish() fails (and is retried by the caller's next frame) while the
// broker is away.
class Mqtt
{
public:
    Mqtt() = default;
    ~Mqtt() { close(); }

    // Callbacks hold `this`; the object must not move.
    Mqtt(const Mqtt&) = delete;
    Mqtt& operator=(const Mqtt&) = delete;

    // TLS with config.cafile (server certificate and host name are verified), password login if
    // config.user is set. Returns true after the broker's CONNACK, false on a refusal or after `timeout`.
    bool open(const BrokerConfig& config, std::chrono::milliseconds timeout = std::chrono::seconds(10));

    // QoS 1: returns true once the broker acknowledged the message.
    bool publish(const std::string& topic,
                 const uint8_t* data,
                 std::size_t size,
                 std::chrono::milliseconds timeout = std::chrono::seconds(10));

    void close();

    bool is_open() const noexcept { return mosq_ != nullptr; }
    const std::string& last_error() const noexcept { return last_error_; }

private:
    static void on_connect(mosquitto* mosq, void* self, int rc);
    static void on_publish(mosquitto* mosq, void* self, int mid);
    static void on_log(mosquitto* mosq, void* self, int level, const char* text);

    mosquitto* mosq_ {nullptr};
    std::string last_error_;

    std::mutex mutex_;
    std::condition_variable changed_;
    bool connack_seen_ {false};
    int connack_rc_ {0};
    int acked_mid_ {-1};
    std::string last_log_;
};
