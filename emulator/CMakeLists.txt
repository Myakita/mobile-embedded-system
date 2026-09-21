cmake_minimum_required(VERSION 3.16)
project(mes-emulator CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# guard:deps:start -- ci/guard.py fails a PR that adds a dependency outside this
# block. Widening it is a one-line, reviewed decision, not something that
# happens as a side effect of a feature PR.
find_package(PkgConfig REQUIRED)
# GPIO wrapper uses the libgpiod v2 C++ API (gpiod::chip::prepare_request(), line_settings).
# Ubuntu 24.04's apt package still ships v1.6; ci/install-libgpiod-v2.sh builds v2 from
# upstream source when the installed version is too old. See docs/CI.md.
# The C++ bindings ship as their own pkg-config module on some distros
# (libgpiodcxx) and are folded into libgpiod on others; try both names.
pkg_check_modules(GPIODCXX libgpiodcxx>=2.0)
if(NOT GPIODCXX_FOUND)
    pkg_check_modules(GPIODCXX REQUIRED libgpiod>=2.0)
endif()
# guard:deps:end

add_compile_options(-Wall -Wextra -Wpedantic)
if(DEFINED ENV{CI})
    add_compile_options(-Werror)
endif()

add_library(periph
    interface/gpio.cpp
    interface/can.cpp
    interface/uart.cpp
    interface/i2c.cpp
)
target_include_directories(periph PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${GPIODCXX_INCLUDE_DIRS})
target_link_libraries(periph PUBLIC ${GPIODCXX_LIBRARIES})
target_compile_options(periph PUBLIC ${GPIODCXX_CFLAGS_OTHER})

add_executable(emulator-example example.cpp)
target_link_libraries(emulator-example PRIVATE periph)

enable_testing()
add_subdirectory(tests)
