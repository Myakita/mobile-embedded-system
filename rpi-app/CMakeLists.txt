add_library(edge_core telemetry.cpp)
target_include_directories(edge_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(edge_core PUBLIC periph)

add_executable(edge main.cpp)
target_link_libraries(edge PRIVATE edge_core)

add_subdirectory(tests)
