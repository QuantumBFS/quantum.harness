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

// Krylov-subspace ground-state solver (dim ≤ 2^8).
GroundState solve_ground_state(const Lattice& lattice, double J,
                               double Omega, double theta);

// Overlap between two ground states.
std::complex<double> overlap(const GroundState& a, const GroundState& b);

// FHS Berry curvature on one plaquette.
BerryCurvature fhs_curvature(const GroundState& gs00, const GroundState& gs10,
                              const GroundState& gs11, const GroundState& gs01);

// Compute curvature on full grid.
std::vector<std::vector<BerryCurvature>> compute_berry_curvature_grid(
    const Lattice& lattice, double J, const ParamGrid& grid);

} // namespace cm
