add_executable(test_telemetry test_telemetry.cpp)
target_link_libraries(test_telemetry PRIVATE edge_core)
add_test(NAME telemetry COMMAND test_telemetry)

add_executable(test_broker_config test_broker_config.cpp)
target_link_libraries(test_broker_config PRIVATE edge_core)
add_test(NAME broker_config COMMAND test_broker_config)

add_executable(test_lmash test_lmash.cpp)
target_link_libraries(test_lmash PRIVATE edge_core)
add_test(NAME lmash COMMAND test_lmash)
