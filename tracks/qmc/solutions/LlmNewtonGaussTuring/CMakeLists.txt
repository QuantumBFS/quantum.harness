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
    src/berry.cpp
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

# Test: Berry phase
add_executable(test_berry tests/test_berry.cpp)
target_link_libraries(test_berry PRIVATE cm148)
add_test(NAME test_berry COMMAND test_berry)

# Test: Berry phase Stage 1
add_executable(test_berry_stage1 tests/test_berry_stage1.cpp)
target_link_libraries(test_berry_stage1 PRIVATE cm148)
add_test(NAME test_berry_stage1 COMMAND test_berry_stage1)

# Test: ∂θH SSE vs ED cross-validation (Stage 2)
add_executable(test_dthetah tests/test_dthetah.cpp)
target_link_libraries(test_dthetah PRIVATE cm148)
add_test(NAME test_dthetah COMMAND test_dthetah)

# Diagnostic driver (not part of the test suite)
add_executable(debug_sse tools/debug_sse.cpp)
target_link_libraries(debug_sse PRIVATE cm148)

add_executable(debug_cv tools/debug_cv.cpp)
target_link_libraries(debug_cv PRIVATE cm148)

# Stage 3 square-lattice benchmark scan
find_package(Threads REQUIRED)
add_executable(scan_square tools/scan_square.cpp)
target_link_libraries(scan_square PRIVATE cm148 Threads::Threads)

# Stage 4 target-lattice reproduction.  Kept separate from scan_square so the
# Stage 3 benchmark remains exactly rerunnable.
add_executable(scan_stage4 tools/scan_stage4.cpp)
target_link_libraries(scan_stage4 PRIVATE cm148 Threads::Threads)

# Stage 1: Berry curvature scan tools
add_executable(scan_berry_chain tools/scan_berry_chain.cpp)
target_link_libraries(scan_berry_chain PRIVATE cm148)

add_executable(scan_berry_square tools/scan_berry_square.cpp)
target_link_libraries(scan_berry_square PRIVATE cm148)

add_test(
    NAME test_berry_cli_endpoint
    COMMAND scan_berry_chain 4 0 0.001 0.001 1.5 1.501 0.001 1
)
set_tests_properties(
    test_berry_cli_endpoint
    PROPERTIES PASS_REGULAR_EXPRESSION "theta,Omega,F12,F12_per_N"
)

# Enable CTest
enable_testing()

find_program(UV_EXECUTABLE uv)
if(UV_EXECUTABLE)
    add_test(
        NAME test_analysis
        COMMAND ${UV_EXECUTABLE} run --script ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_analysis.py
    )
endif()
