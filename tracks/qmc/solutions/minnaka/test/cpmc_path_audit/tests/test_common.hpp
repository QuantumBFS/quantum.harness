#pragma once

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

inline void require_true(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

inline void require_near(double actual, double expected, double tolerance,
                         const std::string& message) {
    if (std::abs(actual - expected) > tolerance) {
        throw std::runtime_error(
            message + ": actual=" + std::to_string(actual) +
            " expected=" + std::to_string(expected));
    }
}

template <typename Function>
int run_test_main(Function&& function) {
    try {
        function();
        std::cout << "PASS\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
