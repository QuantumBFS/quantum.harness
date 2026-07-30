#pragma once

#include "dense_matrix.hpp"

namespace audit {

struct SignedLog {
    int sign = 0;
    double log_abs = 0.0;
};

SignedLog signed_log_product(SignedLog left, SignedLog right);
SignedLog signed_log_determinant(const Matrix& matrix);
double signed_log_ratio(SignedLog numerator, SignedLog denominator);
double signed_log_finite_value(SignedLog value);
double logaddexp(double left, double right);

}  // namespace audit
