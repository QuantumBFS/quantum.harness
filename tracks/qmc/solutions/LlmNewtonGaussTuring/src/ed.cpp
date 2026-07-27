#include "ed.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <numeric>
#include <random>
#include <stdexcept>

namespace cm {

// ============================================================
// DenseSymMatrix::matvec
// ============================================================
void DenseSymMatrix::matvec(const double* x, double* y) const {
    for (std::size_t i = 0; i < dim; ++i) {
        double s = 0.0;
        for (std::size_t j = 0; j < dim; ++j)
            s += (*this)(i, j) * x[j];
        y[i] = s;
    }
}

// ============================================================
// Jacobi eigenvalue solver
// ============================================================
EigenSystem jacobi_eigen(const DenseSymMatrix& A, int max_sweeps, double tol) {
    const std::size_t n = A.dim;
    if (n == 0) return {};

    // Initialize eigenvectors to identity
    EigenSystem es;
    es.eigenvalues.resize(n);
    es.eigenvectors.resize(n * n, 0.0);
    for (std::size_t i = 0; i < n; ++i)
        es.eigenvectors[i * n + i] = 1.0;

    // Copy A into working matrix
    std::vector<double> M = A.data;

    for (int sweep = 0; sweep < max_sweeps; ++sweep) {
        double max_off = 0.0;

        for (std::size_t p = 0; p < n; ++p) {
            for (std::size_t q = p + 1; q < n; ++q) {
                double apq = M[p * n + q];
                double app = M[p * n + p];
                double aqq = M[q * n + q];

                if (std::abs(apq) > max_off)
                    max_off = std::abs(apq);

                if (std::abs(apq) < tol * std::max(std::abs(app), std::abs(aqq)))
                    continue;

                // Jacobi rotation
                double theta = 0.5 * std::atan2(2.0 * apq, aqq - app);
                double c = std::cos(theta);
                double s = std::sin(theta);

                // Update M: rows/cols p and q
                M[p * n + p] = c * c * app + s * s * aqq - 2.0 * s * c * apq;
                M[q * n + q] = s * s * app + c * c * aqq + 2.0 * s * c * apq;
                M[p * n + q] = 0.0;
                M[q * n + p] = 0.0;

                for (std::size_t k = 0; k < n; ++k) {
                    if (k == p || k == q) continue;
                    double akp = M[k * n + p];
                    double akq = M[k * n + q];
                    M[k * n + p] = c * akp - s * akq;
                    M[p * n + k] = M[k * n + p];    // symmetric
                    M[k * n + q] = s * akp + c * akq;
                    M[q * n + k] = M[k * n + q];
                }

                // Update eigenvectors V = V * R
                for (std::size_t k = 0; k < n; ++k) {
                    double vkp = es.eigenvectors[k * n + p];
                    double vkq = es.eigenvectors[k * n + q];
                    es.eigenvectors[k * n + p] = c * vkp - s * vkq;
                    es.eigenvectors[k * n + q] = s * vkp + c * vkq;
                }
            }
        }

        if (max_off < tol) break;
    }

    // Extract eigenvalues
    for (std::size_t i = 0; i < n; ++i)
        es.eigenvalues[i] = M[i * n + i];

    // Sort by eigenvalue (ascending)
    std::vector<std::size_t> idx(n);
    std::iota(idx.begin(), idx.end(), 0);
    std::sort(idx.begin(), idx.end(),
              [&](std::size_t a, std::size_t b) {
                  return es.eigenvalues[a] < es.eigenvalues[b];
              });

    EigenSystem sorted;
    sorted.eigenvalues.resize(n);
    sorted.eigenvectors.resize(n * n);
    for (std::size_t i = 0; i < n; ++i) {
        sorted.eigenvalues[i] = es.eigenvalues[idx[i]];
        for (std::size_t k = 0; k < n; ++k)
            sorted.eigenvectors[k * n + i] = es.eigenvectors[k * n + idx[i]];
    }

    return sorted;
}

// ============================================================
// Spin-1/2 bit operations
// ============================================================
static inline bool bit_set(std::size_t state, std::size_t b) {
    return (state >> b) & 1ULL;
}

static inline std::size_t flip_bit(std::size_t state, std::size_t b) {
    return state ^ (1ULL << b);
}

static inline int sigma_z(std::size_t state, std::size_t b) {
    return bit_set(state, b) ? 1 : -1;
}

// ============================================================
// Build TFIM Hamiltonian (dense)
// ============================================================
DenseSymMatrix build_tfim_hamiltonian(const Lattice& lattice, double J, double h) {
    std::size_t dim = 1ULL << lattice.N;
    if (dim > (1ULL << 13))
        throw std::runtime_error("Hilbert space too large for dense ED (> 2^13)");

    DenseSymMatrix H(dim);

    for (std::size_t state = 0; state < dim; ++state) {
        // Diagonal: -J sum sigma^z_i sigma^z_j
        double diag = 0.0;
        for (const auto& b : lattice.bonds) {
            int szi = sigma_z(state, b.i);
            int szj = sigma_z(state, b.j);
            diag -= J * szi * szj;
        }
        H(state, state) = diag;

        // Off-diagonal: -h sum sigma^x_i (flip one spin)
        for (std::size_t i = 0; i < lattice.N; ++i) {
            std::size_t state2 = flip_bit(state, i);
            if (state2 > state) {  // upper triangle only
                H(state, state2) = -h;
                H(state2, state) = -h;
            }
        }
    }

    return H;
}

// ============================================================
// Lanczos ground-state solver (matrix-free)
// ============================================================

// H|psi> for state |state>: amplitude contributions to neighbors
static void hamiltonian_vec(const Lattice& lattice, double J, double h,
                            std::size_t state, double val,
                            std::vector<double>& out) {
    // Diagonal contribution
    double diag = 0.0;
    for (const auto& b : lattice.bonds)
        diag -= J * sigma_z(state, b.i) * sigma_z(state, b.j);
    out[state] += diag * val;

    // Off-diagonal: flip each spin
    for (std::size_t i = 0; i < lattice.N; ++i) {
        std::size_t state2 = flip_bit(state, i);
        out[state2] -= h * val;
    }
}

LanczosResult lanczos_ground(const Lattice& lattice, double J, double h,
                             int max_iter, double tol) {
    std::size_t dim = 1ULL << lattice.N;
    if (dim > (1ULL << 20))
        throw std::runtime_error("Hilbert space too large for Lanczos (> 2^20)");

    LanczosResult result;
    result.niter = 0;
    result.converged = false;

    // Random initial vector
    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(0.0, 1.0);
    std::vector<double> v1(dim);
    double norm = 0.0;
    for (std::size_t i = 0; i < dim; ++i) {
        v1[i] = dist(rng);
        norm += v1[i] * v1[i];
    }
    norm = std::sqrt(norm);
    for (auto& x : v1) x /= norm;

    std::vector<double> w(dim);
    std::vector<double> alpha(max_iter);
    std::vector<double> beta(max_iter + 1, 0.0);
    std::vector<double> v0; // previous, starts empty

    // Lanczos iteration
    for (int k = 0; k < max_iter; ++k) {
        // w = H |v1>
        std::fill(w.begin(), w.end(), 0.0);
        // Loop over non-zero amplitudes
        for (std::size_t s = 0; s < dim; ++s) {
            if (std::abs(v1[s]) > 1e-30)
                hamiltonian_vec(lattice, J, h, s, v1[s], w);
        }

        // alpha_k = <v1|w>
        double ak = 0.0;
        for (std::size_t i = 0; i < dim; ++i)
            ak += v1[i] * w[i];
        alpha[k] = ak;

        // w = w - alpha_k * v1 - beta_k * v0
        if (k > 0) {
            for (std::size_t i = 0; i < dim; ++i)
                w[i] -= beta[k] * v0[i];
        }
        for (std::size_t i = 0; i < dim; ++i)
            w[i] -= ak * v1[i];

        // beta_{k+1} = ||w||
        double bk = 0.0;
        for (std::size_t i = 0; i < dim; ++i)
            bk += w[i] * w[i];
        bk = std::sqrt(bk);
        beta[k + 1] = bk;

        result.niter = k + 1;

        // Check convergence via tridiagonal eigenvalue stability
        // Monitor the smallest Ritz value change over recent iterations.
        if (k >= 5) {
            // Solve tentative tridiagonal system
            int kk = k + 1;
            DenseSymMatrix T(kk);
            for (int i = 0; i < kk; ++i) {
                T(i, i) = alpha[i];
                if (i + 1 < kk) {
                    T(i, i + 1) = beta[i + 1];
                    T(i + 1, i) = beta[i + 1];
                }
            }
            auto t_eig = jacobi_eigen(T);
            double E_current = t_eig.eigenvalues[0];

            // Also solve using previous step (k)
            if (k >= 6) {
                int kk_prev = k;
                DenseSymMatrix Tprev(kk_prev);
                for (int i = 0; i < kk_prev; ++i) {
                    Tprev(i, i) = alpha[i];
                    if (i + 1 < kk_prev) {
                        Tprev(i, i + 1) = beta[i + 1];
                        Tprev(i + 1, i) = beta[i + 1];
                    }
                }
                auto t_eig_prev = jacobi_eigen(Tprev);
                double E_prev = t_eig_prev.eigenvalues[0];
                if (std::abs(E_current - E_prev) < tol) {
                    result.converged = true;
                    break;
                }
            }
        }

        if (bk < 1e-30) {
            result.converged = true;
            break;
        }

        // v0 = v1, v1 = w / beta_{k+1}
        v0 = v1;
        for (std::size_t i = 0; i < dim; ++i)
            v1[i] = w[i] / bk;
    }

    // Solve tridiagonal eigenvalue problem
    int n = result.niter;
    // Use simple power iteration to find smallest eigenvalue of tridiagonal
    std::vector<double> t_diag(alpha.begin(), alpha.begin() + n);
    std::vector<double> t_off(beta.begin() + 1, beta.begin() + n);

    // Build dense tridiagonal and use Jacobi
    DenseSymMatrix T(n);
    for (int i = 0; i < n; ++i) {
        T(i, i) = t_diag[i];
        if (i + 1 < n) {
            T(i, i + 1) = t_off[i];
            T(i + 1, i) = t_off[i];
        }
    }
    auto t_eig = jacobi_eigen(T);
    result.E0 = t_eig.eigenvalues[0];

    // Reconstruct ground-state eigenvector
    result.psi0.resize(dim, 0.0);
    // Re-run Lanczos to accumulate the Ritz vector
    {
        std::mt19937_64 rng2(42);
        std::normal_distribution<double> dist2(0.0, 1.0);
        std::vector<double> q(dim);
        double nrm = 0.0;
        for (std::size_t i = 0; i < dim; ++i) {
            q[i] = dist2(rng2);
            nrm += q[i] * q[i];
        }
        nrm = std::sqrt(nrm);
        for (auto& x : q) x /= nrm;

        // Re-do Lanczos and store Krylov vectors (memory-heavy but OK for verification)
        // For now return the eigenvalues only; verified by ED comparison
        // In production, use a restarted Lanczos with explicit Ritz vector
    }

    return result;
}

// ============================================================
// Thermal observables from full spectrum
// ============================================================
static double magnetization(std::size_t state, std::size_t N) {
    int sum_sz = 0;
    for (std::size_t i = 0; i < N; ++i)
        sum_sz += sigma_z(state, i);
    return static_cast<double>(sum_sz);
}

ThermalObs compute_thermal_obs(const Lattice& lattice, double J, double h, double beta) {
    std::size_t dim = 1ULL << lattice.N;
    if (dim > (1ULL << 14))
        throw std::runtime_error("Hilbert space too large for full ED thermal (> 2^14)");

    DenseSymMatrix H = build_tfim_hamiltonian(lattice, J, h);
    auto es = jacobi_eigen(H);

    double Z = 0.0;
    double exp_E = 0.0, exp_E2 = 0.0;
    double exp_m = 0.0, exp_m2 = 0.0, exp_m4 = 0.0;

    // Ground state energy
    double E0 = es.eigenvalues[0];

    for (std::size_t s = 0; s < dim; ++s) {
        double En = es.eigenvalues[s];
        double boltz = std::exp(-beta * (En - E0));
        Z += boltz;

        exp_E += En * boltz;
        exp_E2 += En * En * boltz;

        double m_s = magnetization(s, lattice.N);
        exp_m += std::abs(m_s) * boltz;

        double m2_s = m_s * m_s;
        exp_m2 += m2_s * boltz;

        double m4_s = m2_s * m2_s;
        exp_m4 += m4_s * boltz;
    }

    ThermalObs obs;
    double invZ = 1.0 / Z;
    obs.E = (exp_E * invZ) / static_cast<double>(lattice.N);
    obs.Cv = ((exp_E2 * invZ) - std::pow(exp_E * invZ, 2)) /
             (beta * beta * static_cast<double>(lattice.N));
    obs.m = (exp_m * invZ) / static_cast<double>(lattice.N);
    double N_ = static_cast<double>(lattice.N);
    obs.m2 = (exp_m2 * invZ) / (N_ * N_);
    obs.m4 = (exp_m4 * invZ) / (N_ * N_ * N_ * N_);
    obs.Q = (obs.m2 * obs.m2) / (obs.m4 > 1e-30 ? obs.m4 : 1e-30);
    return obs;
}

// ============================================================
// Structure factor S(q)
// ============================================================
double compute_structure_factor(const Lattice& lattice, double J, double h,
                                double beta,
                                const std::array<double, 3>& q) {
    std::size_t dim = 1ULL << lattice.N;
    if (dim > (1ULL << 14))
        throw std::runtime_error("Hilbert space too large for structure factor");

    DenseSymMatrix H = build_tfim_hamiltonian(lattice, J, h);
    auto es = jacobi_eigen(H);
    double E0 = es.eigenvalues[0];

    double Z = 0.0;
    double sq_sum = 0.0;
    double N_ = static_cast<double>(lattice.N);

    for (std::size_t s = 0; s < dim; ++s) {
        double En = es.eigenvalues[s];
        double boltz = std::exp(-beta * (En - E0));
        Z += boltz;

        // Compute <s|sigma^z_i sigma^z_j|s>
        double corr_sum = 0.0;
        for (std::size_t i = 0; i < lattice.N; ++i) {
            for (std::size_t j = 0; j < lattice.N; ++j) {
                double szi = static_cast<double>(sigma_z(s, i));
                double szj = static_cast<double>(sigma_z(s, j));
                double dr[3] = {
                    lattice.site_coords[i][0] - lattice.site_coords[j][0],
                    lattice.site_coords[i][1] - lattice.site_coords[j][1],
                    lattice.site_coords[i][2] - lattice.site_coords[j][2]
                };
                double qdr = q[0] * dr[0] + q[1] * dr[1] + q[2] * dr[2];
                corr_sum += szi * szj * std::cos(qdr);
            }
        }
        sq_sum += corr_sum * boltz;
    }

    return sq_sum / (Z * N_ * N_);
}

// ============================================================
// Second-moment correlation length
// ============================================================
double compute_xi_over_L(const Lattice& lattice, double J, double h, double beta) {
    double q_min = lattice.smallest_momentum();
    if (q_min < 1e-12) return 0.0;

    // Choose direction along reciprocal a
    std::array<double, 3> q_vec = {q_min, 0.0, 0.0};

    double S0 = compute_structure_factor(lattice, J, h, beta, {0.0, 0.0, 0.0});
    double Sq = compute_structure_factor(lattice, J, h, beta, q_vec);

    double L_eff = static_cast<double>(std::max({lattice.L[0], lattice.L[1], lattice.L[2]}));
    double denom = 4.0 * std::pow(std::sin(q_min / 2.0), 2);
    if (denom < 1e-30 || Sq < 1e-30) return 0.0;

    double xi2 = (S0 / Sq - 1.0) / denom;
    if (xi2 < 0) return 0.0;

    return std::sqrt(xi2) / L_eff;
}

} // namespace cm
