#pragma once

#include "hubbard.hpp"

#include <cstddef>
#include <string>
#include <vector>

namespace audit {

class TrialState {
public:
    static TrialState rhf_x(const HubbardModel& model);
    static TrialState rhf_y(const HubbardModel& model);
    static TrialState solve_uhf(const HubbardModel& model, double uhf_u,
                                double initial_magnetization = 0.5,
                                double mixing = 0.2,
                                double tolerance = 1e-12,
                                std::size_t max_iterations = 10000);
    static TrialState from_orbitals(std::string name, Matrix up,
                                    Matrix down);

    const std::string& name() const noexcept { return name_; }
    const Matrix& up_orbitals() const noexcept { return up_; }
    const Matrix& down_orbitals() const noexcept { return down_; }
    const std::vector<double>& up_density() const noexcept {
        return up_density_;
    }
    const std::vector<double>& down_density() const noexcept {
        return down_density_;
    }
    bool scf_converged() const noexcept { return scf_converged_; }
    std::size_t scf_iterations() const noexcept { return scf_iterations_; }
    double scf_residual() const noexcept { return scf_residual_; }
    double scf_energy() const noexcept { return scf_energy_; }

    double overlap(const Matrix& walker_up, const Matrix& walker_down) const;
    TrialState spin_flipped() const;

private:
    TrialState(std::string name, Matrix up, Matrix down);

    std::string name_;
    Matrix up_;
    Matrix down_;
    std::vector<double> up_density_;
    std::vector<double> down_density_;
    bool scf_converged_ = false;
    std::size_t scf_iterations_ = 0;
    double scf_residual_ = 0.0;
    double scf_energy_ = 0.0;
};

std::vector<double> orbital_density(const Matrix& orbitals);
double slater_energy(const HubbardModel& model, const Matrix& up,
                     const Matrix& down);

}  // namespace audit
