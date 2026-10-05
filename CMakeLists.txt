cmake_minimum_required(VERSION 3.16)
project(mes CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_compile_options(-Wall -Wextra -Wpedantic)
if(DEFINED ENV{CI})
    add_compile_options(-Werror)
endif()

enable_testing()
add_subdirectory(emulator)
add_subdirectory(rpi-app)
