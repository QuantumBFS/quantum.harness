#include "fock_oracle.hpp"

#include <mkl_cblas.h>

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace audit {

namespace {

std::vector<std::size_t> occupied_sites(std::uint64_t mask,
                                        std::size_t sites) {
    std::vector<std::size_t> result;
    for (std::size_t site = 0; site < sites; ++site) {
        if ((mask >> site) & std::uint64_t{1}) {
            result.push_back(site);
        }
    }
    return result;
}

Matrix selected_submatrix(const Matrix& matrix,
                          const std::vector<std::size_t>& rows,
                          const std::vector<std::size_t>& cols) {
    Matrix result(rows.size(), cols.size());
    for (std::size_t row = 0; row < rows.size(); ++row) {
        for (std::size_t col = 0; col < cols.size(); ++col) {
            result(row, col) =
                matrix(rows.at(row), cols.at(col));
        }
    }
    return result;
}

std::vector<double> matrix_vector(const Matrix& matrix,
                                  const std::vector<double>& vector) {
    if (matrix.cols() != vector.size()) {
        throw std::invalid_argument("matrix-vector dimension mismatch");
    }
    std::vector<double> result(matrix.rows(), 0.0);
    cblas_dgemv(CblasRowMajor, CblasNoTrans,
                static_cast<MKL_INT>(matrix.rows()),
                static_cast<MKL_INT>(matrix.cols()), 1.0, matrix.data(),
                static_cast<MKL_INT>(matrix.cols()), vector.data(), 1, 0.0,
                result.data(), 1);
    return result;
}

double dot(const std::vector<double>& left,
           const std::vector<double>& right) {
    if (left.size() != right.size()) {
        throw std::invalid_argument("dot-product dimension mismatch");
    }
    return cblas_ddot(static_cast<MKL_INT>(left.size()), left.data(), 1,
                      right.data(), 1);
}

}  // namespace

FockOracle::FockOracle(HubbardModel model)
    : model_(std::move(model)),
      up_masks_(masks_with_particles(model_.n_up())),
      down_masks_(masks_with_particles(model_.n_down())),
      full_kinetic_half_(full_one_body(model_.kinetic_half())),
      trotter_slice_(dimension(), dimension()) {
    Matrix interaction(dimension(), dimension());
    for (std::size_t up = 0; up < up_masks_.size(); ++up) {
        for (std::size_t down = 0; down < down_masks_.size(); ++down) {
            const std::size_t index = up * down_masks_.size() + down;
            const int double_occupancy = __builtin_popcountll(
                up_masks_.at(up) & down_masks_.at(down));
            interaction(index, index) =
                std::exp(-model_.dt() * model_.u() *
                         static_cast<double>(double_occupancy));
        }
    }
    trotter_slice_ =
        multiply(multiply(full_kinetic_half_, interaction),
                 full_kinetic_half_);
}

std::vector<std::uint64_t> FockOracle::masks_with_particles(
    std::size_t particles) const {
    if (model_.sites() >= 63) {
        throw std::invalid_argument("Fock oracle supports fewer than 63 sites");
    }
    std::vector<std::uint64_t> result;
    const std::uint64_t limit = std::uint64_t{1} << model_.sites();
    for (std::uint64_t mask = 0; mask < limit; ++mask) {
        if (static_cast<std::size_t>(__builtin_popcountll(mask)) ==
            particles) {
            result.push_back(mask);
        }
    }
    return result;
}

Matrix FockOracle::lift_one_body(
    const Matrix& one_body,
    const std::vector<std::uint64_t>& masks) const {
    Matrix result(masks.size(), masks.size());
    for (std::size_t output = 0; output < masks.size(); ++output) {
        const auto output_sites =
            occupied_sites(masks.at(output), model_.sites());
        for (std::size_t input = 0; input < masks.size(); ++input) {
            const auto input_sites =
                occupied_sites(masks.at(input), model_.sites());
            result(output, input) =
                determinant(selected_submatrix(one_body, output_sites,
                                               input_sites));
        }
    }
    return result;
}

Matrix FockOracle::full_one_body(const Matrix& one_body) const {
    const Matrix up_operator = lift_one_body(one_body, up_masks_);
    const Matrix down_operator = lift_one_body(one_body, down_masks_);
    Matrix result(dimension(), dimension());
    for (std::size_t output_up = 0; output_up < up_masks_.size();
         ++output_up) {
        for (std::size_t output_down = 0;
             output_down < down_masks_.size(); ++output_down) {
            const std::size_t output =
                output_up * down_masks_.size() + output_down;
            for (std::size_t input_up = 0; input_up < up_masks_.size();
                 ++input_up) {
                for (std::size_t input_down = 0;
                     input_down < down_masks_.size(); ++input_down) {
                    const std::size_t input =
                        input_up * down_masks_.size() + input_down;
                    result(output, input) =
                        up_operator(output_up, input_up) *
                        down_operator(output_down, input_down);
                }
            }
        }
    }
    return result;
}

Matrix FockOracle::hs_diagonal(
    const std::vector<int>& slice_fields) const {
    if (slice_fields.size() != model_.sites()) {
        throw std::invalid_argument("HS slice has wrong site count");
    }
    Matrix result(dimension(), dimension());
    for (std::size_t up = 0; up < up_masks_.size(); ++up) {
        for (std::size_t down = 0; down < down_masks_.size(); ++down) {
            double exponent = 0.0;
            for (std::size_t site = 0; site < model_.sites(); ++site) {
                const int n_up = static_cast<int>(
                    (up_masks_.at(up) >> site) & std::uint64_t{1});
                const int n_down = static_cast<int>(
                    (down_masks_.at(down) >> site) & std::uint64_t{1});
                exponent += model_.gamma() * slice_fields.at(site) *
                            (n_up - n_down);
            }
            const std::size_t index = up * down_masks_.size() + down;
            result(index, index) =
                model_.slice_constant() * std::exp(exponent);
        }
    }
    return result;
}

std::vector<double> FockOracle::slater_vector(
    const TrialState& trial) const {
    std::vector<double> result(dimension(), 0.0);
    for (std::size_t up = 0; up < up_masks_.size(); ++up) {
        const auto up_sites =
            occupied_sites(up_masks_.at(up), model_.sites());
        const double up_coefficient = determinant(selected_submatrix(
            trial.up_orbitals(), up_sites,
            [&] {
                std::vector<std::size_t> columns(model_.n_up());
                for (std::size_t i = 0; i < columns.size(); ++i) {
                    columns.at(i) = i;
                }
                return columns;
            }()));
        for (std::size_t down = 0; down < down_masks_.size(); ++down) {
            const auto down_sites =
                occupied_sites(down_masks_.at(down), model_.sites());
            std::vector<std::size_t> columns(model_.n_down());
            for (std::size_t i = 0; i < columns.size(); ++i) {
                columns.at(i) = i;
            }
            const double down_coefficient = determinant(selected_submatrix(
                trial.down_orbitals(), down_sites, columns));
            result.at(up * down_masks_.size() + down) =
                up_coefficient * down_coefficient;
        }
    }
    return result;
}

Matrix FockOracle::path_operator(const std::vector<int>& fields,
                                 std::size_t slices) const {
    if (fields.size() != slices * model_.sites()) {
        throw std::invalid_argument("path field count does not match slices");
    }
    Matrix result = identity(dimension());
    const double prior =
        std::pow(0.5, static_cast<double>(model_.sites()));
    for (std::size_t slice = 0; slice < slices; ++slice) {
        std::vector<int> slice_fields(model_.sites());
        for (std::size_t site = 0; site < model_.sites(); ++site) {
            slice_fields.at(site) =
                fields.at(slice * model_.sites() + site);
        }
        Matrix slice_operator = multiply(
            multiply(full_kinetic_half_, hs_diagonal(slice_fields)),
            full_kinetic_half_);
        for (double& value : slice_operator.values()) {
            value *= prior;
        }
        result = multiply(slice_operator, result);
    }
    return result;
}

double FockOracle::path_amplitude(
    const TrialState& left, const TrialState& right,
    const std::vector<int>& fields, std::size_t slices) const {
    const auto left_vector = slater_vector(left);
    const auto right_vector = slater_vector(right);
    return dot(left_vector,
               matrix_vector(path_operator(fields, slices), right_vector));
}

double FockOracle::projected_amplitude(
    const TrialState& left, const TrialState& right,
    std::size_t slices) const {
    Matrix projector = identity(dimension());
    for (std::size_t slice = 0; slice < slices; ++slice) {
        projector = multiply(trotter_slice_, projector);
    }
    return dot(slater_vector(left),
               matrix_vector(projector, slater_vector(right)));
}

std::vector<double> FockOracle::apply_path_to_state(
    const std::vector<int>& fields, std::size_t slices,
    const std::vector<double>& state) const {
    if (state.size() != dimension()) {
        throw std::invalid_argument("Fock state has wrong dimension");
    }
    return matrix_vector(path_operator(fields, slices), state);
}

double FockOracle::guide_slice_normalization(
    const std::vector<double>& guide,
    const std::vector<double>& state) const {
    if (guide.size() != dimension() || state.size() != dimension()) {
        throw std::invalid_argument("guide or Fock state has wrong dimension");
    }
    const double overlap = dot(guide, state);
    if (overlap == 0.0) {
        throw std::runtime_error("guide-state overlap is zero");
    }
    return dot(guide, matrix_vector(trotter_slice_, state)) / overlap;
}

DominantGuide FockOracle::dominant_guide() const {
    const auto [eigenvalues, eigenvectors] =
        symmetric_eigh(trotter_slice_);
    DominantGuide result;
    result.eigenvalue = eigenvalues.back();
    result.vector.resize(dimension());
    for (std::size_t row = 0; row < dimension(); ++row) {
        result.vector.at(row) =
            eigenvectors(row, dimension() - 1);
    }
    return result;
}

}  // namespace audit
