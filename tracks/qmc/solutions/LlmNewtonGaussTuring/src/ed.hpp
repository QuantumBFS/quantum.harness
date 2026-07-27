#pragma once

#include "lattice.hpp"
#include <array>
#include <complex>
#include <cstddef>
#include <string>
#include <vector>

namespace cm {

// ============================================================
// Spin-1/2 basis
// ============================================================
// State |i> = bit representation: bit b = 0 means down (-1), 1 means up (+1).
// Hilbert space dimension = 2^N.

// ============================================================
// Dense real symmetric matrix
// ============================================================
struct DenseSymMatrix {
    std::size_t dim;
    std::vector<double> data;   // row-major, dim*dim

    DenseSymMatrix() : dim(0) {}
    DenseSymMatrix(std::size_t d) : dim(d), data(d * d, 0.0) {}

    double& operator()(std::size_t i, std::size_t j) { return data[i * dim + j]; }
    double  operator()(std::size_t i, std::size_t j) const { return data[i * dim + j]; }

    // y = A * x
    void matvec(const double* x, double* y) const;
};

// ============================================================
// Jacobi eigenvalue solver for real symmetric matrix
// ============================================================
struct EigenSystem {
    std::vector<double> eigenvalues;    // ascending
    std::vector<double> eigenvectors;   // column-major, dim*dim
};

EigenSystem jacobi_eigen(const DenseSymMatrix& A, int max_sweeps = 50,
                         double tol = 1e-14);

// ============================================================
// TFIM Hamiltonian builder
// ============================================================
// H = -J sum_<i,j> sigma^z_i sigma^z_j - h sum_i sigma^x_i
//
// This builds the full 2^N x 2^N matrix in the sigma^z basis.
// For ferromagnetic J > 0, sign-problem-free.
DenseSymMatrix build_tfim_hamiltonian(const Lattice& lattice, double J, double h);

// ============================================================
// Lanczos ground-state solver
// ============================================================
struct LanczosResult {
    double E0;                              // ground-state energy
    std::vector<double> psi0;               // ground-state wavefunction, dim entries
    int niter;                              // number of iterations used
    bool converged;
};

// Matrix-free Lanczos for H|psi> in the spin-1/2 basis.
// Provided Hvec(basis state → amplitude), dimension dim = 2^N.
// Uses random initial vector.
LanczosResult lanczos_ground(const Lattice& lattice, double J, double h,
                             int max_iter = 200, double tol = 1e-12);

// ============================================================
// Observables from full eigensystem (small N, thermal)
// ============================================================
struct ThermalObs {
    double E;      // <E> / N
    double Cv;     // heat capacity / N
    double m;      // <|m|> / N
    double m2;     // <m^2> / N^2
    double m4;     // <m^4> / N^4
    double Q;      // <m^2>^2 / <m^4>   (Binder ratio per Blote-Deng)
};

// Compute thermal observables at inverse temperature beta from full spectrum.
// N_sites = lattice.N.
ThermalObs compute_thermal_obs(const Lattice& lattice, double J, double h,
                               double beta);

// ============================================================
// Structure factor S(q) = (1/N^2) sum_{i,j} <sigma^z_i sigma^z_j> e^{iq·(r_i-r_j)}
// ============================================================

// Compute S(q) from full eigensystem for a given q-vector.
double compute_structure_factor(const Lattice& lattice, double J, double h,
                                double beta,
                                const std::array<double, 3>& q);

// Second-moment correlation length xi_L/L estimation.
// xi^2 = (S(0)/S(q_min) - 1) / (4 sin^2(q_min/2))
// for the smallest compatible momentum q_min.
double compute_xi_over_L(const Lattice& lattice, double J, double h, double beta);

} // namespace cm
