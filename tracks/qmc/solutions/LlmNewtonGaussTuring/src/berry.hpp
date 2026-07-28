#pragma once

#include "lattice.hpp"
#include <complex>
#include <vector>

namespace cm {

struct GroundState {
    std::vector<std::complex<double>> eigenvector;
    int dim = 0;
    double E0 = 0.0;
};

struct ParamGrid {
    std::string name1, name2;
    std::vector<double> vals1, vals2;
};

struct BerryCurvature {
    double F12 = 0.0;
    double absU1 = 0.0, absU2 = 0.0;
};

// Kolodrubetz x-axis rotated TFIM (complex Hermitian).
// R_x(θ) = exp(-i(θ/2) Σ X_i): Z → cZ - sY, Y → sZ + cY, X → X
std::vector<std::complex<double>> build_kolodrubetz_hamiltonian(
    const Lattice& lattice, double J, double Omega, double theta);

// Complex Hermitian Lanczos ground-state solver (dim ≤ 1024).
// Uses full reorthogonalisation; reliable for N ≤ 10.
GroundState solve_ground_state(const Lattice& lattice, double J,
                               double Omega, double theta);

// Synonymous with solve_ground_state (kept for API clarity).
GroundState solve_ground_state_lanczos(const Lattice& lattice, double J,
                                        double Omega, double theta,
                                        int m_max = 150);

// Overlap between two ground states.
std::complex<double> overlap(const GroundState& a, const GroundState& b);

// FHS Berry curvature on one plaquette.
BerryCurvature fhs_curvature(const GroundState& gs00, const GroundState& gs10,
                              const GroundState& gs11, const GroundState& gs01);

// Convenience: compute F12 for a single parameter-space plaquette.
BerryCurvature fhs_curvature_single(const Lattice& lattice, double J,
                                     double theta, double Omega,
                                     double dtheta, double dOmega);

// Compute curvature on full grid.
std::vector<std::vector<BerryCurvature>> compute_berry_curvature_grid(
    const Lattice& lattice, double J, const ParamGrid& grid);

// Compute ⟨∂θH⟩ at given (θ,Ω) via full ED spectrum at finite β.
// At θ=0: ∂θH = J Σ_{bonds} (Y_i Z_j + Z_i Y_j), purely off-diagonal.
// Returns the expectation value (diagonal part only for now).
// For T=0, pass a large β (e.g. 100.0).
double compute_dthetah_ed(const Lattice& lattice, double J, double Omega,
                          double theta, double beta);

} // namespace cm
