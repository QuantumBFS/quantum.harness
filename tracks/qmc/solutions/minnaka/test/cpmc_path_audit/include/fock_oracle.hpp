#pragma once

#include "trial.hpp"

#include <cstddef>
#include <cstdint>
#include <vector>

namespace audit {

struct DominantGuide {
    double eigenvalue = 0.0;
    std::vector<double> vector;
};

class FockOracle {
public:
    explicit FockOracle(HubbardModel model);

    std::size_t dimension() const noexcept {
        return up_masks_.size() * down_masks_.size();
    }
    const Matrix& trotter_slice() const noexcept { return trotter_slice_; }

    std::vector<double> slater_vector(const TrialState& trial) const;
    Matrix path_operator(const std::vector<int>& fields,
                         std::size_t slices) const;
    double path_amplitude(const TrialState& left, const TrialState& right,
                          const std::vector<int>& fields,
                          std::size_t slices) const;
    double projected_amplitude(const TrialState& left,
                               const TrialState& right,
                               std::size_t slices) const;
    std::vector<double> apply_path_to_state(
        const std::vector<int>& fields, std::size_t slices,
        const std::vector<double>& state) const;
    double guide_slice_normalization(
        const std::vector<double>& guide,
        const std::vector<double>& state) const;
    DominantGuide dominant_guide() const;

private:
    std::vector<std::uint64_t> masks_with_particles(
        std::size_t particles) const;
    Matrix lift_one_body(const Matrix& one_body,
                         const std::vector<std::uint64_t>& masks) const;
    Matrix full_one_body(const Matrix& one_body) const;
    Matrix hs_diagonal(const std::vector<int>& slice_fields) const;

    HubbardModel model_;
    std::vector<std::uint64_t> up_masks_;
    std::vector<std::uint64_t> down_masks_;
    Matrix full_kinetic_half_;
    Matrix trotter_slice_;
};

}  // namespace audit
