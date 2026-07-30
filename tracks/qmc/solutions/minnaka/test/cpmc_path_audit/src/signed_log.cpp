#include "signed_log.hpp"

#include <mkl_lapacke.h>

#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

namespace audit {

SignedLog signed_log_product(SignedLog left, SignedLog right) {
    if (left.sign == 0 || right.sign == 0) {
        return {0, -std::numeric_limits<double>::infinity()};
    }
    if (std::abs(left.sign) != 1 || std::abs(right.sign) != 1) {
        throw std::invalid_argument("SignedLog sign must be -1, 0, or +1");
    }
    return {left.sign * right.sign, left.log_abs + right.log_abs};
}

SignedLog signed_log_determinant(const Matrix& matrix) {
    if (matrix.rows() != matrix.cols()) {
        throw std::invalid_argument(
            "signed_log_determinant requires a square matrix"
        );
    }
    if (matrix.rows() == 0) {
        return {1, 0.0};
    }
    Matrix lu = matrix;
    const auto n = static_cast<lapack_int>(matrix.rows());
    std::vector<lapack_int> pivots(matrix.rows());
    const lapack_int info = LAPACKE_dgetrf(
        LAPACK_ROW_MAJOR, n, n, lu.data(), n, pivots.data()
    );
    if (info < 0) {
        throw std::runtime_error("LAPACKE_dgetrf invalid argument");
    }
    if (info > 0) {
        return {0, -std::numeric_limits<double>::infinity()};
    }
    int sign = 1;
    double log_abs = 0.0;
    for (lapack_int index = 0; index < n; ++index) {
        const double diagonal = lu(
            static_cast<std::size_t>(index),
            static_cast<std::size_t>(index)
        );
        if (diagonal == 0.0) {
            return {0, -std::numeric_limits<double>::infinity()};
        }
        sign *= diagonal < 0.0 ? -1 : 1;
        if (pivots.at(static_cast<std::size_t>(index)) != index + 1) {
            sign = -sign;
        }
        log_abs += std::log(std::abs(diagonal));
    }
    return {sign, log_abs};
}

double signed_log_ratio(SignedLog numerator, SignedLog denominator) {
    if (denominator.sign == 0) {
        throw std::runtime_error("signed-log ratio has zero denominator");
    }
    if (numerator.sign == 0) {
        return 0.0;
    }
    return static_cast<double>(numerator.sign * denominator.sign)
           * std::exp(numerator.log_abs - denominator.log_abs);
}

double signed_log_finite_value(SignedLog value) {
    if (value.sign == 0) {
        return 0.0;
    }
    const double maximum = std::numeric_limits<double>::max();
    const double magnitude =
        value.log_abs >= std::log(maximum)
            ? maximum
            : std::exp(value.log_abs);
    return static_cast<double>(value.sign) * magnitude;
}

double logaddexp(double left, double right) {
    if (left == -std::numeric_limits<double>::infinity()) {
        return right;
    }
    if (right == -std::numeric_limits<double>::infinity()) {
        return left;
    }
    const double maximum = std::max(left, right);
    return maximum + std::log(
        std::exp(left - maximum) + std::exp(right - maximum)
    );
}

}  // namespace audit
