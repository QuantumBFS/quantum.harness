#include "trial.hpp"
#include "test_common.hpp"

#include <algorithm>
#include <numeric>

namespace {

audit::Matrix gram(const audit::Matrix& orbitals) {
    return audit::multiply(audit::transpose(orbitals), orbitals);
}

}  // namespace

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto rhf_x = audit::TrialState::rhf_x(model);
        const auto rhf_y = audit::TrialState::rhf_y(model);

        require_true(audit::max_abs_difference(
                         gram(rhf_x.up_orbitals()), audit::identity(2)) <
                         1e-12,
                     "RHF-x orbitals are orthonormal");
        require_true(audit::max_abs_difference(
                         gram(rhf_y.up_orbitals()), audit::identity(2)) <
                         1e-12,
                     "RHF-y orbitals are orthonormal");

        const auto k_phi =
            audit::multiply(model.kinetic(), rhf_x.up_orbitals());
        require_near(k_phi(0, 0), -4.0 * rhf_x.up_orbitals()(0, 0),
                     1e-12, "(0,0) orbital energy");
        require_near(
            audit::determinant(audit::multiply(
                audit::transpose(rhf_x.up_orbitals()),
                rhf_x.up_orbitals())),
            1.0, 1e-12, "RHF overlap normalization");

        const auto uhf = audit::TrialState::solve_uhf(model, 8.0);
        require_true(uhf.scf_converged(), "UHF converged");
        require_true(uhf.scf_residual() < 1e-12, "UHF residual");
        require_true(uhf.scf_iterations() < 10000, "UHF iteration limit");

        const double up_particles =
            std::accumulate(uhf.up_density().begin(),
                            uhf.up_density().end(), 0.0);
        const double down_particles =
            std::accumulate(uhf.down_density().begin(),
                            uhf.down_density().end(), 0.0);
        require_near(up_particles, 2.0, 1e-11, "UHF up particle count");
        require_near(down_particles, 2.0, 1e-11,
                     "UHF down particle count");

        double staggered = 0.0;
        for (std::size_t site = 0; site < model.sites(); ++site) {
            staggered += model.sublattice(site) *
                         (uhf.up_density().at(site) -
                          uhf.down_density().at(site));
        }
        staggered /= static_cast<double>(model.sites());
        require_true(staggered > 0.5, "UHF develops Neel magnetization");

        const auto flipped = uhf.spin_flipped();
        require_near(flipped.scf_energy(), uhf.scf_energy(), 1e-11,
                     "spin-flipped UHF energy");
        require_near(flipped.up_density().at(0),
                     uhf.down_density().at(0), 1e-12,
                     "spin-flipped density");

        require_near(rhf_x.overlap(rhf_x.up_orbitals(),
                                   rhf_x.down_orbitals()),
                     1.0, 1e-12, "normalized RHF self overlap");
    });
}
