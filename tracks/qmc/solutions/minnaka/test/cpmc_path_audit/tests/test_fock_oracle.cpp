#include "fock_oracle.hpp"
#include "path_evaluator.hpp"
#include "test_common.hpp"

#include <cmath>
#include <vector>

namespace {

std::vector<int> fields_from_mask(std::size_t mask, std::size_t count) {
    std::vector<int> result(count);
    for (std::size_t i = 0; i < count; ++i) {
        result.at(i) = ((mask >> i) & 1U) ? +1 : -1;
    }
    return result;
}

}  // namespace

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto rhf = audit::TrialState::rhf_x(model);
        const audit::FockOracle oracle(model);
        require_true(oracle.dimension() == 36,
                     "2x2 half-filled Fock dimension");

        const auto trial_vector = oracle.slater_vector(rhf);
        double norm = 0.0;
        for (double value : trial_vector) {
            norm += value * value;
        }
        require_near(norm, 1.0, 1e-12, "Slater-to-Fock normalization");

        const std::vector<int> fields = {+1, -1, -1, +1};
        const auto determinant_result =
            audit::PathEvaluator(model, rhf, model.row_major_order(),
                                 audit::ProposalKind::SiteBySite)
                .evaluate(fields, 1, true);
        const double determinant_amplitude =
            std::pow(0.5, 4.0) * model.slice_constant() *
            determinant_result.final_overlap;
        require_near(oracle.path_amplitude(rhf, rhf, fields, 1),
                     determinant_amplitude, 1e-11,
                     "Fock and determinant path amplitudes");

        audit::Matrix summed_slice(oracle.dimension(), oracle.dimension());
        double summed_amplitude = 0.0;
        for (std::size_t mask = 0; mask < 16; ++mask) {
            const auto path = fields_from_mask(mask, 4);
            const auto field_operator = oracle.path_operator(path, 1);
            for (std::size_t i = 0; i < summed_slice.values().size(); ++i) {
                summed_slice.values().at(i) += field_operator.values().at(i);
            }
            summed_amplitude += oracle.path_amplitude(rhf, rhf, path, 1);
        }
        require_true(audit::max_abs_difference(
                         summed_slice, oracle.trotter_slice()) <
                         1e-10,
                     "summed HS paths recover one Trotter slice");
        require_near(summed_amplitude,
                     oracle.projected_amplitude(rhf, rhf, 1), 1e-10,
                     "M=1 summed path amplitude");

        double summed_m2 = 0.0;
        for (std::size_t mask = 0; mask < 256; ++mask) {
            summed_m2 += oracle.path_amplitude(
                rhf, rhf, fields_from_mask(mask, 8), 2);
        }
        require_near(summed_m2,
                     oracle.projected_amplitude(rhf, rhf, 2), 1e-9,
                     "M=2 summed path amplitude");

        const auto guide = oracle.dominant_guide();
        require_true(guide.eigenvalue > 0.0,
                     "dominant Trotter eigenvalue is positive");
        require_true(guide.vector.size() == oracle.dimension(),
                     "dominant guide dimension");
        require_near(
            oracle.guide_slice_normalization(guide.vector, trial_vector),
            guide.eigenvalue, 1e-11,
            "exact guide gives walker-independent slice normalization");
        const auto propagated =
            oracle.apply_path_to_state(fields, 1, trial_vector);
        require_near(
            oracle.guide_slice_normalization(guide.vector, propagated),
            guide.eigenvalue, 1e-11,
            "exact guide normalization remains constant after propagation");
        const double approximate_before =
            oracle.guide_slice_normalization(trial_vector, trial_vector);
        const double approximate_after =
            oracle.guide_slice_normalization(trial_vector, propagated);
        require_true(std::abs(approximate_before - approximate_after) >
                         1e-6,
                     "approximate Slater guide normalization depends on walker");
    });
}
