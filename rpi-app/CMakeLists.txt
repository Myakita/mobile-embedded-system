# guard:deps:start -- ci/guard.py fails a PR that adds a dependency outside this block.
# libmosquitto is edge's MQTT client (Debian/Ubuntu: libmosquitto-dev; Yocto: mosquitto, built
# with PACKAGECONFIG ssl so TLS works).
find_package(PkgConfig REQUIRED)
pkg_check_modules(MOSQUITTO REQUIRED libmosquitto)
# guard:deps:end

add_library(edge_core telemetry.cpp broker_config.cpp lmash.cpp mqtt.cpp)
target_include_directories(edge_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${MOSQUITTO_INCLUDE_DIRS})
target_link_libraries(edge_core PUBLIC periph ${MOSQUITTO_LIBRARIES})
target_link_directories(edge_core PUBLIC ${MOSQUITTO_LIBRARY_DIRS})
target_compile_options(edge_core PUBLIC ${MOSQUITTO_CFLAGS_OTHER})

add_executable(edge main.cpp)
target_link_libraries(edge PRIVATE edge_core)

add_subdirectory(tests)
