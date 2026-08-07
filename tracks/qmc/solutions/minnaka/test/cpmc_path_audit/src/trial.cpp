#include "trial.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace audit {

namespace {

Matrix first_columns(const Matrix& vectors, std::size_t count) {
    if (count > vectors.cols()) {
        throw std::invalid_argument("requested too many occupied orbitals");
    }
    Matrix result(vectors.rows(), count);
    for (std::size_t row = 0; row < vectors.rows(); ++row) {
        for (std::size_t col = 0; col < count; ++col) {
            result(row, col) = vectors(row, col);
        }
    }
    return result;
}

Matrix fock_matrix(const Matrix& kinetic,
                   const std::vector<double>& opposite_density,
                   double interaction) {
    if (kinetic.rows() != opposite_density.size()) {
        throw std::invalid_argument("Fock density dimension mismatch");
    }
    Matrix result = kinetic;
    for (std::size_t site = 0; site < opposite_density.size(); ++site) {
        result(site, site) += interaction * opposite_density.at(site);
    }
    return result;
}

double kinetic_energy(const Matrix& kinetic, const Matrix& orbitals) {
    const Matrix density =
        multiply(orbitals, transpose(orbitals));
    double result = 0.0;
    for (std::size_t row = 0; row < kinetic.rows(); ++row) {
        for (std::size_t col = 0; col < kinetic.cols(); ++col) {
            result += kinetic(row, col) * density(col, row);
        }
    }
    return result;
}

}  // namespace

TrialState::TrialState(std::string name, Matrix up, Matrix down)
    : name_(std::move(name)), up_(std::move(up)), down_(std::move(down)) {
    if (up_.rows() != down_.rows()) {
        throw std::invalid_argument("trial spin sectors have different sites");
    }
    up_density_ = orbital_density(up_);
    down_density_ = orbital_density(down_);
}

TrialState TrialState::from_orbitals(std::string name, Matrix up,
                                     Matrix down) {
    return TrialState(std::move(name), std::move(up), std::move(down));
}

TrialState TrialState::rhf_x(const HubbardModel& model) {
    if (model.lx() != 2 || model.ly() != 2 || model.n_up() != 2 ||
        model.n_down() != 2) {
        throw std::invalid_argument("rhf_x is defined for the 2x2 half-filled audit");
    }
    Matrix orbitals(4, 2);
    const double normalization = 0.5;
    for (std::size_t site = 0; site < 4; ++site) {
        const std::size_t x = site % 2;
        orbitals(site, 0) = normalization;
        orbitals(site, 1) = normalization * (x == 0 ? 1.0 : -1.0);
    }
    return TrialState("rhf_x", orbitals, orbitals);
}

TrialState TrialState::rhf_y(const HubbardModel& model) {
    if (model.lx() != 2 || model.ly() != 2 || model.n_up() != 2 ||
        model.n_down() != 2) {
        throw std::invalid_argument("rhf_y is defined for the 2x2 half-filled audit");
    }
    Matrix orbitals(4, 2);
    const double normalization = 0.5;
    for (std::size_t site = 0; site < 4; ++site) {
        const std::size_t y = site / 2;
        orbitals(site, 0) = normalization;
        orbitals(site, 1) = normalization * (y == 0 ? 1.0 : -1.0);
    }
    return TrialState("rhf_y", orbitals, orbitals);
}

TrialState TrialState::solve_uhf(const HubbardModel& model, double uhf_u,
                                 double initial_magnetization, double mixing,
                                 double tolerance,
                                 std::size_t max_iterations) {
    if (!(mixing > 0.0 && mixing <= 1.0) ||
        !(initial_magnetization >= 0.0 &&
          initial_magnetization <= 1.0) ||
        !(tolerance > 0.0) || max_iterations == 0) {
        throw std::invalid_argument("invalid UHF solver parameter");
    }
    std::vector<double> density_up(model.sites());
    std::vector<double> density_down(model.sites());
    for (std::size_t site = 0; site < model.sites(); ++site) {
        const double staggered =
            initial_magnetization * model.sublattice(site);
        density_up.at(site) = 0.5 * (1.0 + staggered);
        density_down.at(site) = 0.5 * (1.0 - staggered);
    }

    Matrix occupied_up;
    Matrix occupied_down;
    double residual = 0.0;
    std::size_t iteration = 0;
    bool converged = false;
    for (iteration = 1; iteration <= max_iterations; ++iteration) {
        const auto [values_up, vectors_up] =
            symmetric_eigh(fock_matrix(model.kinetic(), density_down, uhf_u));
        const auto [values_down, vectors_down] =
            symmetric_eigh(fock_matrix(model.kinetic(), density_up, uhf_u));
        (void)values_up;
        (void)values_down;
        occupied_up = first_columns(vectors_up, model.n_up());
        occupied_down = first_columns(vectors_down, model.n_down());
        const auto output_up = orbital_density(occupied_up);
        const auto output_down = orbital_density(occupied_down);

        residual = 0.0;
        for (std::size_t site = 0; site < model.sites(); ++site) {
            residual = std::max(
                residual, std::abs(output_up.at(site) - density_up.at(site)));
            residual = std::max(
                residual,
                std::abs(output_down.at(site) - density_down.at(site)));
        }
        if (residual < tolerance) {
            density_up = output_up;
            density_down = output_down;
            converged = true;
            break;
        }
        for (std::size_t site = 0; site < model.sites(); ++site) {
            density_up.at(site) =
                (1.0 - mixing) * density_up.at(site) +
                mixing * output_up.at(site);
            density_down.at(site) =
                (1.0 - mixing) * density_down.at(site) +
                mixing * output_down.at(site);
        }
    }
    if (!converged) {
        throw std::runtime_error("UHF failed to converge");
    }

    TrialState result("uhf_u8", occupied_up, occupied_down);
    result.up_density_ = density_up;
    result.down_density_ = density_down;
    result.scf_converged_ = true;
    result.scf_iterations_ = iteration;
    result.scf_residual_ = residual;
    result.scf_energy_ =
        slater_energy(model, result.up_, result.down_);
    return result;
}

double TrialState::overlap(const Matrix& walker_up,
                           const Matrix& walker_down) const {
    if (walker_up.rows() != up_.rows() ||
        walker_down.rows() != down_.rows()) {
        throw std::invalid_argument("walker and trial site counts differ");
    }
    return determinant(multiply(transpose(up_), walker_up)) *
           determinant(multiply(transpose(down_), walker_down));
}

TrialState TrialState::spin_flipped() const {
    TrialState result(name_ + "_spin_flipped", down_, up_);
    result.up_density_ = down_density_;
    result.down_density_ = up_density_;
    result.scf_converged_ = scf_converged_;
    result.scf_iterations_ = scf_iterations_;
    result.scf_residual_ = scf_residual_;
    result.scf_energy_ = scf_energy_;
    return result;
}

std::vector<double> orbital_density(const Matrix& orbitals) {
    std::vector<double> result(orbitals.rows(), 0.0);
    for (std::size_t site = 0; site < orbitals.rows(); ++site) {
        for (std::size_t orbital = 0; orbital < orbitals.cols(); ++orbital) {
            result.at(site) += orbitals(site, orbital) *
                               orbitals(site, orbital);
        }
    }
    return result;
}

double slater_energy(const HubbardModel& model, const Matrix& up,
                     const Matrix& down) {
    const auto density_up = orbital_density(up);
    const auto density_down = orbital_density(down);
    double interaction = 0.0;
    for (std::size_t site = 0; site < model.sites(); ++site) {
        interaction +=
            model.u() * density_up.at(site) * density_down.at(site);
    }
    return kinetic_energy(model.kinetic(), up) +
           kinetic_energy(model.kinetic(), down) + interaction;
}

}  // namespace audit
