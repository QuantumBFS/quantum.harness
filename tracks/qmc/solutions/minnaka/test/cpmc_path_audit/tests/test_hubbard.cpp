#include "hubbard.hpp"
#include "test_common.hpp"

#include <algorithm>
#include <array>
#include <vector>

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);

        const auto [eigenvalues, eigenvectors] =
            audit::symmetric_eigh(model.kinetic());
        (void)eigenvectors;
        const std::array<double, 4> expected = {-4.0, 0.0, 0.0, 4.0};
        for (std::size_t i = 0; i < expected.size(); ++i) {
            require_near(eigenvalues.at(i), expected.at(i), 1e-12,
                         "2x2 PBC kinetic spectrum");
        }

        require_near(model.gamma(),
                     std::acosh(std::exp(model.dt() * model.u() / 2.0)),
                     1e-14, "Hirsch gamma");

        for (int n_up = 0; n_up <= 1; ++n_up) {
            for (int n_down = 0; n_down <= 1; ++n_down) {
                double hs_sum = 0.0;
                for (int field : {-1, +1}) {
                    hs_sum += 0.5 * model.local_hs_weight(
                                        n_up, n_down, field);
                }
                require_near(
                    hs_sum, std::exp(-model.dt() * model.u() * n_up *
                                     n_down),
                    1e-12, "local Hirsch identity");
            }
        }

        require_true(model.row_major_order() ==
                         std::vector<std::size_t>({0, 1, 2, 3}),
                     "row-major order");
        require_true(model.reverse_order() ==
                         std::vector<std::size_t>({3, 2, 1, 0}),
                     "reverse order");
        const auto sublattice_order = model.sublattice_order();
        require_true(sublattice_order ==
                         std::vector<std::size_t>({0, 3, 1, 2}),
                     "A then B order");

        const auto kh = model.kinetic_half();
        const auto reconstructed = audit::multiply(kh, kh);
        const auto exact =
            audit::symmetric_exponential(model.kinetic(), -model.dt());
        require_true(audit::max_abs_difference(reconstructed, exact) < 1e-12,
                     "two half kinetic propagators equal one full propagator");
    });
}
