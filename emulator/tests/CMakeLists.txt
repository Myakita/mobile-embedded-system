add_executable(test_errors test_errors.cpp)
target_link_libraries(test_errors PRIVATE periph)
add_test(NAME errors COMMAND test_errors)

add_executable(test_uart_pty test_uart_pty.cpp)
target_link_libraries(test_uart_pty PRIVATE periph)
add_test(NAME uart_pty COMMAND test_uart_pty)
