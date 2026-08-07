#include "dense_matrix.hpp"

#include <mkl_cblas.h>
#include <mkl_lapacke.h>

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

namespace audit {

namespace {

void require_square(const Matrix& matrix, const char* operation) {
    if (matrix.rows() != matrix.cols()) {
        throw std::invalid_argument(std::string(operation) +
                                    " requires a square matrix");
    }
}

lapack_int lapack_size(std::size_t size) {
    if (size > static_cast<std::size_t>(
                   std::numeric_limits<lapack_int>::max())) {
        throw std::overflow_error("matrix dimension exceeds LAPACK integer");
    }
    return static_cast<lapack_int>(size);
}

}  // namespace

Matrix::Matrix(std::size_t rows, std::size_t cols)
    : rows_(rows), cols_(cols), values_(rows * cols, 0.0) {}

Matrix::Matrix(std::size_t rows, std::size_t cols,
               std::initializer_list<double> values)
    : Matrix(rows, cols, std::vector<double>(values)) {}

Matrix::Matrix(std::size_t rows, std::size_t cols,
               std::vector<double> values)
    : rows_(rows), cols_(cols), values_(std::move(values)) {
    if (values_.size() != rows_ * cols_) {
        throw std::invalid_argument("matrix value count does not match shape");
    }
}

double& Matrix::operator()(std::size_t row, std::size_t col) {
    return values_.at(row * cols_ + col);
}

double Matrix::operator()(std::size_t row, std::size_t col) const {
    return values_.at(row * cols_ + col);
}

Matrix identity(std::size_t size) {
    Matrix result(size, size);
    for (std::size_t i = 0; i < size; ++i) {
        result(i, i) = 1.0;
    }
    return result;
}

Matrix transpose(const Matrix& matrix) {
    Matrix result(matrix.cols(), matrix.rows());
    for (std::size_t row = 0; row < matrix.rows(); ++row) {
        for (std::size_t col = 0; col < matrix.cols(); ++col) {
            result(col, row) = matrix(row, col);
        }
    }
    return result;
}

Matrix multiply(const Matrix& left, const Matrix& right) {
    if (left.cols() != right.rows()) {
        throw std::invalid_argument("matrix multiplication dimension mismatch");
    }
    Matrix result(left.rows(), right.cols());
    cblas_dgemm(CblasRowMajor, CblasNoTrans, CblasNoTrans,
                static_cast<MKL_INT>(left.rows()),
                static_cast<MKL_INT>(right.cols()),
                static_cast<MKL_INT>(left.cols()), 1.0, left.data(),
                static_cast<MKL_INT>(left.cols()), right.data(),
                static_cast<MKL_INT>(right.cols()), 0.0, result.data(),
                static_cast<MKL_INT>(result.cols()));
    return result;
}

double determinant(const Matrix& matrix) {
    require_square(matrix, "determinant");
    Matrix lu = matrix;
    const lapack_int n = lapack_size(matrix.rows());
    std::vector<lapack_int> pivots(static_cast<std::size_t>(n));
    const lapack_int info =
        LAPACKE_dgetrf(LAPACK_ROW_MAJOR, n, n, lu.data(), n, pivots.data());
    if (info < 0) {
        throw std::runtime_error("LAPACKE_dgetrf received an invalid argument");
    }
    if (info > 0) {
        return 0.0;
    }
    double result = 1.0;
    for (lapack_int i = 0; i < n; ++i) {
        result *= lu(static_cast<std::size_t>(i),
                     static_cast<std::size_t>(i));
        if (pivots.at(static_cast<std::size_t>(i)) != i + 1) {
            result = -result;
        }
    }
    return result;
}

Matrix solve(const Matrix& matrix, const Matrix& right) {
    require_square(matrix, "solve");
    if (matrix.rows() != right.rows()) {
        throw std::invalid_argument("solve right-hand side dimension mismatch");
    }
    Matrix lu = matrix;
    Matrix result = right;
    const lapack_int n = lapack_size(matrix.rows());
    const lapack_int nrhs = lapack_size(right.cols());
    std::vector<lapack_int> pivots(static_cast<std::size_t>(n));
    const lapack_int info = LAPACKE_dgesv(
        LAPACK_ROW_MAJOR, n, nrhs, lu.data(), n, pivots.data(),
        result.data(), nrhs
    );
    if (info < 0) {
        throw std::runtime_error("LAPACKE_dgesv received an invalid argument");
    }
    if (info > 0) {
        throw std::runtime_error("cannot solve singular matrix");
    }
    return result;
}

Matrix inverse(const Matrix& matrix) {
    require_square(matrix, "inverse");
    Matrix result = matrix;
    const lapack_int n = lapack_size(matrix.rows());
    std::vector<lapack_int> pivots(static_cast<std::size_t>(n));
    lapack_int info =
        LAPACKE_dgetrf(LAPACK_ROW_MAJOR, n, n, result.data(), n,
                       pivots.data());
    if (info != 0) {
        throw std::runtime_error("cannot invert singular matrix");
    }
    info = LAPACKE_dgetri(LAPACK_ROW_MAJOR, n, result.data(), n,
                          pivots.data());
    if (info != 0) {
        throw std::runtime_error("LAPACKE_dgetri failed");
    }
    return result;
}

std::pair<std::vector<double>, Matrix> symmetric_eigh(
    const Matrix& matrix) {
    require_square(matrix, "symmetric eigendecomposition");
    Matrix eigenvectors = matrix;
    const lapack_int n = lapack_size(matrix.rows());
    std::vector<double> eigenvalues(static_cast<std::size_t>(n));
    const lapack_int info =
        LAPACKE_dsyev(LAPACK_ROW_MAJOR, 'V', 'U', n,
                      eigenvectors.data(), n, eigenvalues.data());
    if (info != 0) {
        throw std::runtime_error("LAPACKE_dsyev failed");
    }
    return {std::move(eigenvalues), std::move(eigenvectors)};
}

Matrix symmetric_exponential(const Matrix& matrix, double scale) {
    const auto [eigenvalues, eigenvectors] = symmetric_eigh(matrix);
    Matrix scaled_diagonal(matrix.rows(), matrix.cols());
    for (std::size_t i = 0; i < eigenvalues.size(); ++i) {
        scaled_diagonal(i, i) = std::exp(scale * eigenvalues.at(i));
    }
    return multiply(multiply(eigenvectors, scaled_diagonal),
                    transpose(eigenvectors));
}

ThinQr thin_qr(const Matrix& matrix) {
    if (matrix.rows() < matrix.cols() || matrix.cols() == 0) {
        throw std::invalid_argument(
            "thin QR requires a nonempty matrix with rows >= columns");
    }
    Matrix packed = matrix;
    const lapack_int rows = lapack_size(matrix.rows());
    const lapack_int cols = lapack_size(matrix.cols());
    std::vector<double> tau(static_cast<std::size_t>(cols));
    std::vector<lapack_int> pivots(static_cast<std::size_t>(cols), 0);
    lapack_int info = LAPACKE_dgeqp3(
        LAPACK_ROW_MAJOR, rows, cols, packed.data(), cols,
        pivots.data(), tau.data());
    if (info != 0) {
        throw std::runtime_error("LAPACKE_dgeqp3 failed");
    }
    Matrix r(matrix.cols(), matrix.cols());
    for (std::size_t row = 0; row < matrix.cols(); ++row) {
        for (std::size_t col = row; col < matrix.cols(); ++col) {
            r(row, col) = packed(row, col);
        }
    }
    info = LAPACKE_dorgqr(LAPACK_ROW_MAJOR, rows, cols, cols,
                          packed.data(), cols, tau.data());
    if (info != 0) {
        throw std::runtime_error("LAPACKE_dorgqr failed");
    }
    std::vector<std::size_t> pivoted_column_by_position;
    pivoted_column_by_position.reserve(static_cast<std::size_t>(cols));
    int permutation_sign = 1;
    for (lapack_int position = 0; position < cols; ++position) {
        const lapack_int original = pivots.at(
            static_cast<std::size_t>(position)
        ) - 1;
        if (original < 0 || original >= cols) {
            throw std::runtime_error("LAPACKE_dgeqp3 returned bad pivots");
        }
        pivoted_column_by_position.push_back(
            static_cast<std::size_t>(original)
        );
        for (lapack_int previous = 0; previous < position; ++previous) {
            if (pivots.at(static_cast<std::size_t>(previous)) >
                pivots.at(static_cast<std::size_t>(position))) {
                permutation_sign = -permutation_sign;
            }
        }
    }
    return {
        std::move(packed), std::move(r),
        std::move(pivoted_column_by_position), permutation_sign,
    };
}

double max_abs_difference(const Matrix& left, const Matrix& right) {
    if (left.rows() != right.rows() || left.cols() != right.cols()) {
        throw std::invalid_argument("matrix difference dimension mismatch");
    }
    double result = 0.0;
    for (std::size_t i = 0; i < left.values().size(); ++i) {
        result = std::max(
            result, std::abs(left.values().at(i) - right.values().at(i)));
    }
    return result;
}

}  // namespace audit
