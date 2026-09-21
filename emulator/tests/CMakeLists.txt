add_executable(test_errors test_errors.cpp)
target_link_libraries(test_errors PRIVATE periph)
add_test(NAME errors COMMAND test_errors)

add_executable(test_uart_pty test_uart_pty.cpp)
target_link_libraries(test_uart_pty PRIVATE periph)
add_test(NAME uart_pty COMMAND test_uart_pty)

# Needs vcan/i2c-stub/gpio-sim and root; excluded from `make test`, only
# `make devices` runs it (ctest -L devices). See emulator/README.md.
add_executable(test_devices test_devices.cpp)
target_link_libraries(test_devices PRIVATE periph)
add_test(NAME devices COMMAND test_devices)
set_tests_properties(devices PROPERTIES LABELS "devices")
