add_executable(test_telemetry test_telemetry.cpp)
target_link_libraries(test_telemetry PRIVATE edge_core)
add_test(NAME telemetry COMMAND test_telemetry)
