#include "gpio.hpp"

#include <exception>
#include <filesystem>
#include <utility>

namespace
{
bool is_output(GPIODir dir) { return dir == GPIODir::Output; }
} // namespace

bool GPIO::open(const std::string& chip, const uint16_t line, const GPIODir dir)
{
    GPIOConfig config;
    config.chip = chip;
    config.line = line;
    config.dir = dir;

    return open(config);
}

bool GPIO::open(const GPIOConfig& config)
{
    close();

    try
    {
        auto chip = std::make_unique<gpiod::chip>(std::filesystem::path {config.chip});
        auto settings = make_line_settings(
            config.dir, config.pull, config.active_low, config.debounce, config.initial_value);

        auto request = std::make_unique<gpiod::line_request>(
            chip->prepare_request()
                .set_consumer(config.consumer)
                .add_line_settings(gpiod::line::offset {config.line}, settings)
                .do_request());

        chip_ = std::move(chip);
        request_ = std::move(request);

        line_ = config.line;
        dir_ = config.dir;
        pull_ = config.pull;
        active_low_ = config.active_low;
        debounce_ = config.debounce;
        consumer_ = config.consumer;
        last_error_.clear();

        return true;
    }
    catch (const std::exception& error)
    {
        last_error_ = error.what();
        close();
        return false;
    }
}

bool GPIO::read() const
{
    if (!is_open())
    {
        return false;
    }

    try
    {
        return request_->get_value(gpiod::line::offset {line_}) == gpiod::line::value::ACTIVE;
    }
    catch (const std::exception& error)
    {
        last_error_ = error.what();
        return false;
    }
}

bool GPIO::write(bool value)
{
    if (!is_open() || !is_output(dir_))
    {
        return false;
    }

    try
    {
        request_->set_value(gpiod::line::offset {line_}, to_gpiod_value(value));
        last_error_.clear();
        return true;
    }
    catch (const std::exception& error)
    {
        last_error_ = error.what();
        return false;
    }
}

bool GPIO::reconfigure(const GPIODir dir,
                       const GPIOPull pull,
                       const bool active_low,
                       const std::chrono::microseconds debounce)
{
    if (!is_open())
    {
        return false;
    }

    try
    {
        gpiod::line_config line_config;
        line_config.add_line_settings(gpiod::line::offset {line_},
                                      make_line_settings(dir, pull, active_low, debounce, read()));

        request_->reconfigure_lines(line_config);

        dir_ = dir;
        pull_ = pull;
        active_low_ = active_low;
        debounce_ = debounce;
        last_error_.clear();

        return true;
    }
    catch (const std::exception& error)
    {
        last_error_ = error.what();
        return false;
    }
}

void GPIO::close()
{
    try
    {
        if (request_)
        {
            request_->release();
        }

        if (chip_)
        {
            chip_->close();
        }
    }
    catch (const std::exception& error)
    {
        last_error_ = error.what();
    }

    request_.reset();
    chip_.reset();
}

bool GPIO::is_open() const noexcept
{
    return chip_ && request_ && static_cast<bool>(*chip_) && static_cast<bool>(*request_);
}

gpiod::line::bias GPIO::to_gpiod_bias(GPIOPull pull)
{
    switch (pull)
    {
    case GPIOPull::Disabled:
        return gpiod::line::bias::DISABLED;
    case GPIOPull::PullUp:
        return gpiod::line::bias::PULL_UP;
    case GPIOPull::PullDown:
        return gpiod::line::bias::PULL_DOWN;
    case GPIOPull::AsIs:
    default:
        return gpiod::line::bias::AS_IS;
    }
}

gpiod::line::direction GPIO::to_gpiod_direction(GPIODir dir)
{
    return is_output(dir) ? gpiod::line::direction::OUTPUT : gpiod::line::direction::INPUT;
}

gpiod::line::value GPIO::to_gpiod_value(bool value)
{
    return value ? gpiod::line::value::ACTIVE : gpiod::line::value::INACTIVE;
}

gpiod::line_settings GPIO::make_line_settings(const GPIODir dir,
                                              const GPIOPull pull,
                                              const bool active_low,
                                              const std::chrono::microseconds debounce,
                                              const bool initial_value) const
{
    gpiod::line_settings settings;
    settings.set_direction(to_gpiod_direction(dir))
        .set_bias(to_gpiod_bias(pull))
        .set_active_low(active_low)
        .set_debounce_period(debounce);

    if (is_output(dir))
    {
        settings.set_output_value(to_gpiod_value(initial_value));
    }

    return settings;
}
