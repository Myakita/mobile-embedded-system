#include "broker_config.hpp"

#include <cctype>
#include <fstream>

namespace
{
std::string trim(const std::string& text)
{
    std::size_t begin = 0;
    std::size_t end = text.size();
    while (begin < end && std::isspace(static_cast<unsigned char>(text[begin])))
    {
        ++begin;
    }
    while (end > begin && std::isspace(static_cast<unsigned char>(text[end - 1])))
    {
        --end;
    }
    return text.substr(begin, end - begin);
}

bool parse_port(const std::string& value, uint16_t& port)
{
    if (value.empty() || value.size() > 5)
    {
        return false;
    }
    unsigned number = 0;
    for (const char c : value)
    {
        if (!std::isdigit(static_cast<unsigned char>(c)))
        {
            return false;
        }
        number = number * 10 + static_cast<unsigned>(c - '0');
    }
    if (number == 0 || number > 65535)
    {
        return false;
    }
    port = static_cast<uint16_t>(number);
    return true;
}

bool assign(BrokerConfig& config, const std::string& key, const std::string& value, std::string& error)
{
    if (key == "port")
    {
        if (!parse_port(value, config.port))
        {
            error = "port: expected 1-65535, got '" + value + "'";
            return false;
        }
        return true;
    }
    std::string* target = nullptr;
    if (key == "host")
    {
        target = &config.host;
    }
    else if (key == "user")
    {
        target = &config.user;
    }
    else if (key == "password")
    {
        target = &config.password;
    }
    else if (key == "cafile")
    {
        target = &config.cafile;
    }
    else if (key == "topic_root")
    {
        target = &config.topic_root;
    }
    else if (key == "client_id")
    {
        target = &config.client_id;
    }
    if (target == nullptr)
    {
        error = "unknown key '" + key + "'";
        return false;
    }
    *target = value;
    return true;
}

bool check_required(const BrokerConfig& config, std::string& error)
{
    if (config.host.empty())
    {
        error = "host is required";
    }
    else if (config.cafile.empty())
    {
        error = "cafile is required";
    }
    else if (config.topic_root.empty())
    {
        error = "topic_root is required";
    }
    return error.empty();
}
} // namespace

bool parse_broker_config(std::istream& in, BrokerConfig& config, std::string& error)
{
    error.clear();
    std::string line;
    for (int number = 1; std::getline(in, line); ++number)
    {
        const std::string text = trim(line);
        if (text.empty() || text[0] == '#')
        {
            continue;
        }
        const auto eq = text.find('=');
        if (eq == std::string::npos)
        {
            error = "line " + std::to_string(number) + ": expected key=value";
            return false;
        }
        std::string problem;
        if (!assign(config, trim(text.substr(0, eq)), trim(text.substr(eq + 1)), problem))
        {
            error = "line " + std::to_string(number) + ": " + problem;
            return false;
        }
    }
    return check_required(config, error);
}

bool load_broker_config(const std::string& path, BrokerConfig& config, std::string& error)
{
    std::ifstream in(path);
    if (!in)
    {
        error = "cannot open " + path;
        return false;
    }
    if (!parse_broker_config(in, config, error))
    {
        error = path + ": " + error;
        return false;
    }
    return true;
}
