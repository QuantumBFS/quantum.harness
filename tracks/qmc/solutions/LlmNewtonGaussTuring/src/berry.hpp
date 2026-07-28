#pragma once

#include "lattice.hpp"
#include <cstddef>
#include <complex>
#include <vector>

namespace cm {

struct GroundState {
    std::vector<std::complex<double>> eigenvector;
    int dim = 0;
    double E0 = 0.0;
    double residual = 0.0;
    bool converged = false;
};

struct ParamGrid {
    std::vector<double> theta_values;
    std::vector<double> omega_values;
};

struct BerryCurvature {
    double wilson_phase = 0.0; // arg product of normalized overlaps
    double flux = 0.0;         // integral F12 d(lambda1) d(lambda2)
    double F12 = 0.0;          // local curvature = flux / oriented area
    double absU1 = 0.0, absU2 = 0.0;
    double min_overlap = 0.0;
    bool valid = false;
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

// FHS Berry curvature on one plaquette. With A_mu = i<psi|partial_mu psi>,
// the normalized-overlap Wilson loop has phase -integral F12 d lambda1 d lambda2.
BerryCurvature fhs_curvature(const GroundState& gs00, const GroundState& gs10,
                              const GroundState& gs11, const GroundState& gs01,
                              double dlambda1, double dlambda2);

// Convenience: compute F12 for a single parameter-space plaquette.
BerryCurvature fhs_curvature_single(const Lattice& lattice, double J,
                                     double theta, double Omega,
                                     double dtheta, double dOmega);

// Compute curvature on full grid.
std::vector<std::vector<BerryCurvature>> compute_berry_curvature_grid(
    const Lattice& lattice, double J, const ParamGrid& grid);

// Prefactor-weighted ZZ diagnostic in the unrotated H0 thermal ensemble:
// J sin(2 theta) <sum_bonds Z_i Z_j>_{H0}/N. The historical API name is kept
// for compatibility; this is neither the physical rotated-state expectation of
// the diagonal operator nor the full generalized force.
double compute_dthetah_diagonal_ed(const Lattice& lattice, double J, double Omega,
                                   double theta, double beta);

// Exact finite-size 1D oracle for an even periodic spin chain. The ground state
// lies in the antiperiodic Jordan-Wigner sector k_m=(2m+1)pi/N.
double tfim_chain_berry_curvature_density_finite(std::size_t sites, double J,
                                                double Omega);

// Thermodynamic-limit 1D oracle at fixed J for the convention above.
// It is independent of theta and diverges to -infinity at |Omega| = J.
double tfim_chain_berry_curvature_density_exact(double J, double Omega,
                                                double tolerance = 1e-10);

} // namespace cm
