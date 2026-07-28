cmake_minimum_required(VERSION 3.16)
project(cm-challenge148 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Optimisation flags
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    add_compile_options(-O3 -march=native -DNDEBUG)
else()
    add_compile_options(-O2 -g)
endif()

# Warning flags
add_compile_options(-Wall -Wextra -Wpedantic)

# Source files
set(LIB_SOURCES
    src/lattice.cpp
    src/ed.cpp
    src/sse.cpp
)

# Static library
add_library(cm148 STATIC ${LIB_SOURCES})
target_include_directories(cm148 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

# Test: lattice
add_executable(test_lattice tests/test_lattice.cpp)
target_link_libraries(test_lattice PRIVATE cm148)
add_test(NAME test_lattice COMMAND test_lattice)

# Test: ED
add_executable(test_ed tests/test_ed.cpp)
target_link_libraries(test_ed PRIVATE cm148)
add_test(NAME test_ed COMMAND test_ed)

# Test: SSE
add_executable(test_sse tests/test_sse.cpp)
target_link_libraries(test_sse PRIVATE cm148)
add_test(NAME test_sse COMMAND test_sse)

# Enable CTest
enable_testing()
