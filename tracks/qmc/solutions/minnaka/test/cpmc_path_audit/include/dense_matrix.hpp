#pragma once

#include <cstddef>
#include <initializer_list>
#include <utility>
#include <vector>

namespace audit {

class Matrix {
public:
    Matrix() = default;
    Matrix(std::size_t rows, std::size_t cols);
    Matrix(std::size_t rows, std::size_t cols,
           std::initializer_list<double> values);
    Matrix(std::size_t rows, std::size_t cols, std::vector<double> values);

    std::size_t rows() const noexcept { return rows_; }
    std::size_t cols() const noexcept { return cols_; }
    double* data() noexcept { return values_.data(); }
    const double* data() const noexcept { return values_.data(); }
    std::vector<double>& values() noexcept { return values_; }
    const std::vector<double>& values() const noexcept { return values_; }

    double& operator()(std::size_t row, std::size_t col);
    double operator()(std::size_t row, std::size_t col) const;

private:
    std::size_t rows_ = 0;
    std::size_t cols_ = 0;
    std::vector<double> values_;
};

struct ThinQr {
    Matrix q;
    Matrix r;
    std::vector<std::size_t> pivoted_column_by_position;
    int permutation_sign = 1;
};

Matrix identity(std::size_t size);
Matrix transpose(const Matrix& matrix);
Matrix multiply(const Matrix& left, const Matrix& right);
Matrix solve(const Matrix& matrix, const Matrix& right);
Matrix inverse(const Matrix& matrix);
double determinant(const Matrix& matrix);
std::pair<std::vector<double>, Matrix> symmetric_eigh(const Matrix& matrix);
Matrix symmetric_exponential(const Matrix& matrix, double scale);
ThinQr thin_qr(const Matrix& matrix);
double max_abs_difference(const Matrix& left, const Matrix& right);

}  // namespace audit
