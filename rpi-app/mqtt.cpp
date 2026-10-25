#include "mqtt.hpp"

#include <mosquitto.h>

namespace
{
void ensure_library()
{
    static const int initialised = mosquitto_lib_init();
    (void)initialised;
}

constexpr int KEEPALIVE_SECONDS = 30;
} // namespace

void Mqtt::on_connect(mosquitto*, void* self, int rc)
{
    auto* mqtt = static_cast<Mqtt*>(self);
    {
        std::lock_guard<std::mutex> lock(mqtt->mutex_);
        mqtt->connack_seen_ = true;
        mqtt->connack_rc_ = rc;
    }
    mqtt->changed_.notify_all();
}

void Mqtt::on_publish(mosquitto*, void* self, int mid)
{
    auto* mqtt = static_cast<Mqtt*>(self);
    {
        std::lock_guard<std::mutex> lock(mqtt->mutex_);
        mqtt->acked_mid_ = mid;
    }
    mqtt->changed_.notify_all();
}

// libmosquitto reports TLS and socket failures only here; open() would otherwise just time out.
void Mqtt::on_log(mosquitto*, void* self, int level, const char* text)
{
    if ((level & (MOSQ_LOG_ERR | MOSQ_LOG_WARNING)) == 0)
    {
        return;
    }
    auto* mqtt = static_cast<Mqtt*>(self);
    std::lock_guard<std::mutex> lock(mqtt->mutex_);
    mqtt->last_log_ = text;
}

bool Mqtt::open(const BrokerConfig& config, std::chrono::milliseconds timeout)
{
    close();
    ensure_library();

    mosq_ = mosquitto_new(config.client_id.c_str(), true, this);
    if (mosq_ == nullptr)
    {
        last_error_ = "mosquitto_new failed";
        return false;
    }
    mosquitto_connect_callback_set(mosq_, on_connect);
    mosquitto_publish_callback_set(mosq_, on_publish);
    mosquitto_log_callback_set(mosq_, on_log);
    mosquitto_reconnect_delay_set(mosq_, 1, 5, false);

    int rc = mosquitto_tls_set(mosq_, config.cafile.c_str(), nullptr, nullptr, nullptr, nullptr);
    if (rc == MOSQ_ERR_SUCCESS && !config.user.empty())
    {
        rc = mosquitto_username_pw_set(mosq_, config.user.c_str(), config.password.c_str());
    }
    if (rc == MOSQ_ERR_SUCCESS)
    {
        rc = mosquitto_connect_async(mosq_, config.host.c_str(), config.port, KEEPALIVE_SECONDS);
    }
    if (rc == MOSQ_ERR_SUCCESS)
    {
        rc = mosquitto_loop_start(mosq_);
    }
    if (rc != MOSQ_ERR_SUCCESS)
    {
        last_error_ = std::string("setup: ") + mosquitto_strerror(rc);
        close();
        return false;
    }

    std::unique_lock<std::mutex> lock(mutex_);
    if (!changed_.wait_for(lock, timeout, [this] { return connack_seen_; }))
    {
        last_error_ = "no CONNACK from " + config.host + ":" + std::to_string(config.port) + " within " +
                      std::to_string(timeout.count()) + " ms";
        if (!last_log_.empty())
        {
            last_error_ += " (" + last_log_ + ")";
        }
        lock.unlock();
        close();
        return false;
    }
    if (connack_rc_ != 0)
    {
        last_error_ = std::string("broker refused the connection: ") + mosquitto_connack_string(connack_rc_);
        lock.unlock();
        close();
        return false;
    }
    last_error_.clear();
    return true;
}

bool Mqtt::publish(const std::string& topic,
                   const uint8_t* data,
                   std::size_t size,
                   std::chrono::milliseconds timeout)
{
    if (mosq_ == nullptr)
    {
        last_error_ = "MQTT client is not open";
        return false;
    }
    int mid = 0;
    const int rc = mosquitto_publish(mosq_, &mid, topic.c_str(), static_cast<int>(size), data, 1, false);
    if (rc != MOSQ_ERR_SUCCESS)
    {
        last_error_ = std::string("publish: ") + mosquitto_strerror(rc);
        return false;
    }
    std::unique_lock<std::mutex> lock(mutex_);
    if (!changed_.wait_for(lock, timeout, [this, mid] { return acked_mid_ == mid; }))
    {
        last_error_ = "publish: no PUBACK within " + std::to_string(timeout.count()) + " ms";
        return false;
    }
    last_error_.clear();
    return true;
}

void Mqtt::close()
{
    if (mosq_ == nullptr)
    {
        return;
    }
    mosquitto_disconnect(mosq_);
    mosquitto_loop_stop(mosq_, true);
    mosquitto_destroy(mosq_);
    mosq_ = nullptr;
    std::lock_guard<std::mutex> lock(mutex_);
    connack_seen_ = false;
    connack_rc_ = 0;
    acked_mid_ = -1;
    last_log_.clear();
}
