#include "trial_io.hpp"

#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <stdexcept>
#include <string>

namespace audit {

namespace {

double parse_finite_double(const std::string& token,
                           const std::string& path) {
    std::size_t consumed = 0;
    double value = 0.0;
    try {
        value = std::stod(token, &consumed);
    } catch (const std::exception&) {
        throw std::runtime_error("invalid orbital value in " + path);
    }
    if (consumed != token.size() || !std::isfinite(value)) {
        throw std::runtime_error("nonfinite or malformed orbital value in " +
                                 path);
    }
    return value;
}

}  // namespace

Matrix read_real_orbitals(const std::string& path, std::size_t rows,
                          std::size_t cols) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open orbital file: " + path);
    }
    std::size_t file_rows = 0;
    std::size_t file_cols = 0;
    if (!(input >> file_rows >> file_cols) || file_rows != rows ||
        file_cols != cols) {
        throw std::runtime_error("orbital shape mismatch in " + path);
    }
    Matrix result(rows, cols);
    std::string token;
    for (std::size_t index = 0; index < rows * cols; ++index) {
        if (!(input >> token)) {
            throw std::runtime_error("orbital file ended early: " + path);
        }
        result.values().at(index) = parse_finite_double(token, path);
    }
    if (input >> token) {
        throw std::runtime_error("orbital file has extra values: " + path);
    }
    return result;
}

void write_real_orbitals(const std::string& path,
                         const Matrix& orbitals) {
    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("cannot write orbital file: " + path);
    }
    output << orbitals.rows() << ' ' << orbitals.cols() << '\n'
           << std::scientific << std::setprecision(17);
    for (std::size_t row = 0; row < orbitals.rows(); ++row) {
        for (std::size_t col = 0; col < orbitals.cols(); ++col) {
            const double value = orbitals(row, col);
            if (!std::isfinite(value)) {
                throw std::runtime_error(
                    "cannot write nonfinite orbital value");
            }
            if (col != 0) {
                output << ' ';
            }
            output << value;
        }
        output << '\n';
    }
    if (!output) {
        throw std::runtime_error("failed while writing orbital file: " +
                                 path);
    }
}

double orthonormality_residual(const Matrix& orbitals) {
    if (orbitals.rows() < orbitals.cols() || orbitals.cols() == 0) {
        throw std::invalid_argument("invalid orbital matrix shape");
    }
    const Matrix gram =
        multiply(transpose(orbitals), orbitals);
    return max_abs_difference(gram, identity(orbitals.cols()));
}

double particle_hole_projector_residual(
    const Matrix& up, const Matrix& down, const HubbardModel& model) {
    if (up.rows() != model.sites() ||
        down.rows() != model.sites() ||
        up.cols() != model.n_up() ||
        down.cols() != model.n_down()) {
        throw std::invalid_argument(
            "particle-hole residual orbital shape mismatch");
    }
    const Matrix projector_up = multiply(up, transpose(up));
    const Matrix projector_down = multiply(down, transpose(down));
    double residual = 0.0;
    for (std::size_t row = 0; row < model.sites(); ++row) {
        for (std::size_t col = 0; col < model.sites(); ++col) {
            const double identity_value = row == col ? 1.0 : 0.0;
            const double expected =
                identity_value -
                model.sublattice(row) * projector_up(row, col) *
                    model.sublattice(col);
            residual =
                std::max(residual,
                         std::abs(projector_down(row, col) - expected));
        }
    }
    return residual;
}

double orient_overlap_positive(Matrix& trial, const Matrix& initial) {
    if (trial.rows() != initial.rows() ||
        trial.cols() != initial.cols() || trial.cols() == 0) {
        throw std::invalid_argument("trial/initial orbital shape mismatch");
    }
    double overlap =
        determinant(multiply(transpose(trial), initial));
    if (!std::isfinite(overlap) || std::abs(overlap) <= 1.0e-10) {
        throw std::runtime_error("trial/initial overlap is singular");
    }
    if (overlap < 0.0) {
        const std::size_t last = trial.cols() - 1;
        for (std::size_t row = 0; row < trial.rows(); ++row) {
            trial(row, last) *= -1.0;
        }
        overlap =
            determinant(multiply(transpose(trial), initial));
    }
    if (!(overlap > 1.0e-10)) {
        throw std::runtime_error("failed to orient trial overlap");
    }
    return overlap;
}

}  // namespace audit
