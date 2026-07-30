#include "physical_path.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace audit {
namespace {

struct StableSlater {
    Matrix orbitals;
    SignedLog scale{1, 0.0};
    std::size_t applied_slices = 0;
};

void stabilize(StableSlater& state) {
    auto qr = thin_qr(state.orbitals);
    auto transformation = signed_log_determinant(qr.r);
    transformation.sign *= qr.permutation_sign;
    state.scale = signed_log_product(state.scale, transformation);
    state.orbitals = std::move(qr.q);
}

void apply_slice(
    StableSlater& state,
    const HubbardModel& model,
    FieldView fields,
    std::size_t slice,
    bool spin_up,
    std::size_t stabilization_interval
) {
    state.orbitals = multiply(model.kinetic_half(), state.orbitals);
    for (std::size_t site = 0; site < model.sites(); ++site) {
        const double factor = model.hs_multiplier(
            spin_up, fields.at(slice * model.sites() + site)
        );
        for (std::size_t orbital = 0;
             orbital < state.orbitals.cols(); ++orbital) {
            state.orbitals(site, orbital) *= factor;
        }
    }
    state.orbitals = multiply(model.kinetic_half(), state.orbitals);
    ++state.applied_slices;
    if (stabilization_interval != 0
        && state.applied_slices % stabilization_interval == 0) {
        stabilize(state);
    }
}

void apply_alf_slice(
    StableSlater& state,
    const HubbardModel& model,
    FieldView fields,
    std::size_t slice,
    bool spin_up,
    std::size_t stabilization_interval
) {
    // ALF's WRAPUR applies the full kinetic propagator first and the
    // diagonal Hirsch field second: B_l^ALF = V_l K.
    state.orbitals = multiply(model.kinetic_half(), state.orbitals);
    state.orbitals = multiply(model.kinetic_half(), state.orbitals);
    for (std::size_t site = 0; site < model.sites(); ++site) {
        const double factor = model.hs_multiplier(
            spin_up, fields.at(slice * model.sites() + site)
        );
        for (std::size_t orbital = 0;
             orbital < state.orbitals.cols(); ++orbital) {
            state.orbitals(site, orbital) *= factor;
        }
    }
    ++state.applied_slices;
    if (stabilization_interval != 0
        && state.applied_slices % stabilization_interval == 0) {
        stabilize(state);
    }
}

SignedLog overlap(
    const StableSlater& left, const StableSlater& right
) {
    auto result = signed_log_determinant(multiply(
        transpose(left.orbitals), right.orbitals
    ));
    result = signed_log_product(result, left.scale);
    result = signed_log_product(result, right.scale);
    return result;
}

Matrix transition_density(
    const StableSlater& left, const StableSlater& right
) {
    const Matrix left_transpose = transpose(left.orbitals);
    const Matrix overlap_matrix = multiply(
        left_transpose, right.orbitals
    );
    return multiply(
        right.orbitals, solve(overlap_matrix, left_transpose)
    );
}

LocalEnergy local_energy(
    const HubbardModel& model,
    const StableSlater& left_up,
    const StableSlater& left_down,
    const StableSlater& right_up,
    const StableSlater& right_down
) {
    const Matrix density_up = transition_density(left_up, right_up);
    const Matrix density_down = transition_density(left_down, right_down);
    LocalEnergy result;
    for (std::size_t row = 0; row < model.sites(); ++row) {
        result.particle_number +=
            density_up(row, row) + density_down(row, row);
        result.interaction += model.u()
            * density_up(row, row) * density_down(row, row);
        for (std::size_t col = 0; col < model.sites(); ++col) {
            result.kinetic += model.kinetic()(row, col)
                * (density_up(col, row) + density_down(col, row));
        }
    }
    result.total = result.kinetic + result.interaction;
    return result;
}

StableSlater state_from(const Matrix& orbitals) {
    return {orbitals, {1, 0.0}, 0};
}

SignedLog add_common(SignedLog value, double common) {
    if (value.sign != 0) {
        value.log_abs += common;
    }
    return value;
}

}  // namespace

int FieldView::at(std::size_t index) const {
    if (packed == nullptr || index >= nfield) {
        throw std::out_of_range("packed field index out of range");
    }
    return (packed[index / 8U] & (1U << (index % 8U))) ? 1 : -1;
}

PhysicalPathResult evaluate_physical_path(
    const HubbardModel& model,
    const TrialState& initial,
    const TrialState& guide,
    FieldView fields,
    std::size_t ltrot,
    std::size_t center_slice,
    std::size_t stabilization_interval
) {
    if (fields.nfield != ltrot * model.sites()) {
        throw std::invalid_argument("physical path field count mismatch");
    }
    if (center_slice > ltrot) {
        throw std::invalid_argument("center slice exceeds Ltrot");
    }
    StableSlater right_up = state_from(initial.up_orbitals());
    StableSlater right_down = state_from(initial.down_orbitals());
    StableSlater center_right_up;
    StableSlater center_right_down;
    if (center_slice == 0) {
        center_right_up = right_up;
        center_right_down = right_down;
    }
    for (std::size_t slice = 0; slice < ltrot; ++slice) {
        apply_slice(
            right_up, model, fields, slice, true,
            stabilization_interval
        );
        apply_slice(
            right_down, model, fields, slice, false,
            stabilization_interval
        );
        if (slice + 1 == center_slice) {
            center_right_up = right_up;
            center_right_down = right_down;
        }
    }

    auto make_center_left = [&](const TrialState& trial, bool spin_up) {
        StableSlater state = state_from(
            spin_up ? trial.up_orbitals() : trial.down_orbitals()
        );
        for (std::size_t slice = ltrot; slice > center_slice; --slice) {
            apply_slice(
                state, model, fields, slice - 1, spin_up,
                stabilization_interval
            );
        }
        return state;
    };
    const auto center_i_up = make_center_left(initial, true);
    const auto center_i_down = make_center_left(initial, false);
    const auto center_t_up = make_center_left(guide, true);
    const auto center_t_down = make_center_left(guide, false);
    const auto endpoint_i_up = state_from(initial.up_orbitals());
    const auto endpoint_i_down = state_from(initial.down_orbitals());
    const auto endpoint_t_up = state_from(guide.up_orbitals());
    const auto endpoint_t_down = state_from(guide.down_orbitals());

    const auto endpoint_ii = signed_log_product(
        overlap(endpoint_i_up, right_up),
        overlap(endpoint_i_down, right_down)
    );
    const auto endpoint_ti = signed_log_product(
        overlap(endpoint_t_up, right_up),
        overlap(endpoint_t_down, right_down)
    );
    StableSlater alf_right_up = state_from(initial.up_orbitals());
    StableSlater alf_right_down = state_from(initial.down_orbitals());
    for (std::size_t slice = 0; slice < ltrot; ++slice) {
        apply_alf_slice(
            alf_right_up, model, fields, slice, true,
            stabilization_interval
        );
        apply_alf_slice(
            alf_right_down, model, fields, slice, false,
            stabilization_interval
        );
    }
    const auto alf_endpoint_ii = signed_log_product(
        overlap(endpoint_i_up, alf_right_up),
        overlap(endpoint_i_down, alf_right_down)
    );
    const auto alf_endpoint_ti = signed_log_product(
        overlap(endpoint_t_up, alf_right_up),
        overlap(endpoint_t_down, alf_right_down)
    );
    const double common =
        -static_cast<double>(fields.nfield) * std::log(2.0)
        + static_cast<double>(ltrot) * std::log(model.slice_constant());
    PhysicalPathResult result;
    result.endpoint_overlap_ii = endpoint_ii;
    result.endpoint_overlap_ti = endpoint_ti;
    result.d_ii = add_common(endpoint_ii, common);
    result.d_ti = add_common(endpoint_ti, common);
    result.alf_d_ii = add_common(alf_endpoint_ii, common);
    result.alf_d_ti = add_common(alf_endpoint_ti, common);
    result.central_ii = local_energy(
        model, center_i_up, center_i_down,
        center_right_up, center_right_down
    );
    result.central_ti = local_energy(
        model, center_t_up, center_t_down,
        center_right_up, center_right_down
    );
    result.endpoint_i = local_energy(
        model, endpoint_i_up, endpoint_i_down, right_up, right_down
    );
    result.endpoint_t = local_energy(
        model, endpoint_t_up, endpoint_t_down, right_up, right_down
    );
    return result;
}

}  // namespace audit
