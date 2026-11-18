add_executable(test_telemetry test_telemetry.cpp)
target_link_libraries(test_telemetry PRIVATE edge_core)
add_test(NAME telemetry COMMAND test_telemetry)

add_executable(test_broker_config test_broker_config.cpp)
target_link_libraries(test_broker_config PRIVATE edge_core)
add_test(NAME broker_config COMMAND test_broker_config)

add_executable(test_lmash test_lmash.cpp)
target_link_libraries(test_lmash PRIVATE edge_core)
add_test(NAME lmash COMMAND test_lmash)

add_executable(test_telemetry_edge test_telemetry_edge.cpp)
target_link_libraries(test_telemetry_edge PRIVATE edge_core)
add_test(NAME telemetry_edge COMMAND test_telemetry_edge)

add_executable(test_broker_config_edge test_broker_config_edge.cpp)
target_link_libraries(test_broker_config_edge PRIVATE edge_core)
add_test(NAME broker_config_edge COMMAND test_broker_config_edge)

add_executable(test_lmash_edge test_lmash_edge.cpp)
target_link_libraries(test_lmash_edge PRIVATE edge_core)
target_compile_definitions(test_lmash_edge PRIVATE PROTOCOL_VECTORS_DIR="${PROJECT_SOURCE_DIR}/protocol/vectors")
add_test(NAME lmash_edge COMMAND test_lmash_edge)

add_executable(test_mqtt_edge test_mqtt_edge.cpp)
target_link_libraries(test_mqtt_edge PRIVATE edge_core)
add_test(NAME mqtt_edge COMMAND test_mqtt_edge)
