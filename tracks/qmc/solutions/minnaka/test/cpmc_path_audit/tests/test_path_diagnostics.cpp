#include "path_diagnostics.hpp"

#include "test_common.hpp"

#include <cmath>
#include <limits>

namespace {

audit::Matrix scaled_orbitals(const audit::Matrix& input, double first,
                              double second) {
    audit::Matrix result = input;
    for (std::size_t row = 0; row < result.rows(); ++row) {
        result(row, 0) *= first;
        result(row, 1) *= second;
    }
    return result;
}

}  // namespace

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto trial = audit::TrialState::rhf_x(model);

        {
            const auto walker = audit::Walker::from_trial(trial);
            const auto diagnostic =
                audit::diagnose_subspace(trial, walker);
            require_near(diagnostic.up.sigma_min, 1.0, 1e-12,
                         "trial up subspace matches itself");
            require_near(diagnostic.down.sigma_min, 1.0, 1e-12,
                         "trial down subspace matches itself");
            require_near(diagnostic.log_abs_normalized_overlap, 0.0,
                         1e-12, "normalized trial overlap is one");
            require_near(
                diagnostic.log_abs_normalized_overlap,
                diagnostic.up.log_abs_det_s +
                    diagnostic.down.log_abs_det_s,
                1e-12, "normalized determinant factorizes by spin");
        }

        {
            const audit::Matrix basis_trial(
                4, 2, {1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0});
            const audit::Matrix basis_orthogonal(
                4, 2, {1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0});
            const auto exact_trial = audit::TrialState::from_orbitals(
                "exact", basis_trial, basis_trial);
            const audit::Walker walker(basis_orthogonal, basis_trial);
            const auto diagnostic =
                audit::diagnose_subspace(exact_trial, walker);
            require_true(diagnostic.up.sigma_min < 1e-12,
                         "orthogonal occupied orbital has zero cosine");
            require_near(diagnostic.up.principal_angle_max,
                         std::acos(-1.0) / 2.0, 1e-12,
                         "orthogonal occupied orbital has pi/2 angle");
            require_true(
                diagnostic.log_abs_normalized_overlap ==
                    -std::numeric_limits<double>::infinity(),
                "orthogonal determinant has zero normalized overlap");
        }

        {
            const audit::Walker walker(
                scaled_orbitals(trial.up_orbitals(), 2.0, 3.0),
                scaled_orbitals(trial.down_orbitals(), 4.0, 5.0));
            const auto diagnostic =
                audit::diagnose_subspace(trial, walker);
            require_near(diagnostic.up.log_abs_orbital_scale,
                         std::log(6.0), 1e-12,
                         "up orbital scale is separate from orientation");
            require_near(diagnostic.down.log_abs_orbital_scale,
                         std::log(20.0), 1e-12,
                         "down orbital scale is separate from orientation");
        }

        audit::Walker propagated = audit::Walker::from_trial(trial);
        propagated.apply_half_kinetic(model);
        propagated.apply_site_field(model, 0, +1);
        for (std::size_t site = 0; site < model.sites(); ++site) {
            const auto ratios = audit::diagnose_site_ratios(
                model, trial, propagated, site);
            require_near(ratios.predicted_plus_ratio,
                         ratios.direct_plus_ratio, 1e-11,
                         "determinant lemma predicts plus field");
            require_near(ratios.predicted_minus_ratio,
                         ratios.direct_minus_ratio, 1e-11,
                         "determinant lemma predicts minus field");
            require_true(ratios.max_abs_residual < 1e-10,
                         "determinant lemma residual is small");
            require_true(
                ratios.predicted_low_overlap_field == -1 ||
                    ratios.predicted_low_overlap_field == +1,
                "low-overlap field prediction is physical");
        }
    });
}
