#pragma once

#include <cstdint>
#include <spandsp.h>
#include <string>

class UART
{
public:
    bool open(const std::string& device,
              uint32_t baudrate);

    std::size_t read(std::span<uint8_t> data);

    std::size_t write(
        std::span<const uint8_t> data);

    void close();

private:
    int fd_ {-1};
};