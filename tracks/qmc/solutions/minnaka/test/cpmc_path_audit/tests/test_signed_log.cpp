#include "signed_log.hpp"
#include "test_common.hpp"
#include "trial.hpp"
#include "walker.hpp"

#include <cmath>

int main() {
    return run_test_main([] {
        const audit::Matrix diagonal(
            2, 2, {std::exp(700.0), 0.0, 0.0, -std::exp(-700.0)}
        );
        const auto determinant = audit::signed_log_determinant(diagonal);
        require_true(determinant.sign == -1, "signed determinant sign");
        require_near(determinant.log_abs, 0.0, 1e-12,
                     "signed determinant cancels logarithms");

        const audit::SignedLog first{1, 800.0};
        const audit::SignedLog second{-1, -100.0};
        const auto product = audit::signed_log_product(first, second);
        require_true(product.sign == -1, "signed-log product sign");
        require_near(product.log_abs, 700.0, 1e-12,
                     "signed-log product scale");

        require_near(
            audit::logaddexp(1000.0, 999.0),
            1000.0 + std::log1p(std::exp(-1.0)),
            1e-12,
            "stable logaddexp"
        );
        require_near(
            audit::signed_log_ratio({-1, 1000.0}, {1, 999.0}),
            -std::exp(1.0), 1e-12, "stable signed-log ratio"
        );
        require_true(
            std::isfinite(
                audit::signed_log_finite_value({1, 1000.0})
            ),
            "large signed-log conversion saturates"
        );

        const auto trial = audit::TrialState::from_orbitals(
            "one", audit::Matrix(1, 1, {1.0}),
            audit::Matrix(1, 1, {1.0})
        );
        audit::Walker walker(
            audit::Matrix(1, 1, {std::exp(700.0)}),
            audit::Matrix(1, 1, {std::exp(700.0)})
        );
        walker.stabilize();
        require_true(!std::isfinite(walker.overlap(trial)),
                     "legacy absolute overlap overflows");
        const auto stable = walker.overlap_signed_log(trial);
        require_true(stable.sign == 1, "stable walker overlap sign");
        require_near(stable.log_abs, 1400.0, 1e-10,
                     "stable walker overlap log scale");
    });
}
