#pragma once

#include "hubbard.hpp"
#include "signed_log.hpp"
#include "trial.hpp"

#include <cstddef>
#include <cstdint>

namespace audit {

struct FieldView {
    const std::uint8_t* packed = nullptr;
    std::size_t nfield = 0;

    int at(std::size_t index) const;
};

struct LocalEnergy {
    double kinetic = 0.0;
    double interaction = 0.0;
    double total = 0.0;
    double particle_number = 0.0;
};

struct PhysicalPathResult {
    // Symmetric CP cut: K^(1/2) V_l K ... V_1 K^(1/2).
    SignedLog d_ii;
    SignedLog d_ti;
    // ALF archive cut: V_l K ... V_1 K.
    SignedLog alf_d_ii;
    SignedLog alf_d_ti;
    SignedLog endpoint_overlap_ii;
    SignedLog endpoint_overlap_ti;
    LocalEnergy central_ii;
    LocalEnergy central_ti;
    LocalEnergy endpoint_i;
    LocalEnergy endpoint_t;
};

PhysicalPathResult evaluate_physical_path(
    const HubbardModel& model,
    const TrialState& initial,
    const TrialState& guide,
    FieldView fields,
    std::size_t ltrot,
    std::size_t center_slice,
    std::size_t stabilization_interval
);

}  // namespace audit
