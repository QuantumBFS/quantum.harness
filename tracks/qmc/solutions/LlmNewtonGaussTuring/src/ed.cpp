#include "ed.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>

namespace cm {

namespace {

std::size_t checked_spin_dimension(std::size_t sites, std::size_t maximum,
                                   const char* context) {
    if (sites == 0)
        throw std::invalid_argument(std::string(context) + ": lattice has no sites");
    if (sites >= std::numeric_limits<std::size_t>::digits)
        throw std::length_error(std::string(context) + ": site count overflows basis index");
    const std::size_t dimension = std::size_t{1} << sites;
    if (dimension > maximum)
        throw std::length_error(std::string(context) + ": Hilbert space exceeds solver limit");
    return dimension;
}

void validate_bond_indices(const Lattice& lattice, const char* context) {
    for (const auto& bond : lattice.bonds)
        if (bond.i >= lattice.N || bond.j >= lattice.N)
            throw std::out_of_range(std::string(context) + ": bond endpoint outside lattice");
}

} // namespace

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
    if (!std::isfinite(J) || !std::isfinite(h))
        throw std::invalid_argument("build_tfim_hamiltonian: couplings must be finite");
    const std::size_t dim = checked_spin_dimension(lattice.N, std::size_t{1} << 13,
                                                   "build_tfim_hamiltonian");
    validate_bond_indices(lattice, "build_tfim_hamiltonian");

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
    if (!std::isfinite(J) || !std::isfinite(h))
        throw std::invalid_argument("lanczos_ground: couplings must be finite");
    const std::size_t dim = checked_spin_dimension(lattice.N, std::size_t{1} << 20,
                                                   "lanczos_ground");
    validate_bond_indices(lattice, "lanczos_ground");
    if (max_iter <= 0) throw std::invalid_argument("lanczos_ground: max_iter must be positive");
    if (!(tol > 0.0) || !std::isfinite(tol))
        throw std::invalid_argument("lanczos_ground: tol must be finite and positive");
    const int iteration_limit = std::min<int>(max_iter, static_cast<int>(dim));

    LanczosResult result;

    // Random initial vector
    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(0.0, 1.0);
    std::vector<double> initial(dim);
    double norm = 0.0;
    for (std::size_t i = 0; i < dim; ++i) {
        initial[i] = dist(rng);
        norm += initial[i] * initial[i];
    }
    norm = std::sqrt(norm);
    for (auto& value : initial) value /= norm;

    auto apply_hamiltonian = [&](const std::vector<double>& input,
                                 std::vector<double>& output) {
        std::fill(output.begin(), output.end(), 0.0);
        for (std::size_t state = 0; state < dim; ++state)
            if (std::abs(input[state]) > 1e-30)
                hamiltonian_vec(lattice, J, h, state, input[state], output);
    };

    std::vector<double> q = initial;
    std::vector<double> q_previous(dim, 0.0);
    std::vector<double> w(dim);
    std::vector<double> alpha;
    std::vector<double> beta(1, 0.0);
    alpha.reserve(iteration_limit);
    beta.reserve(iteration_limit + 1);

    // Lanczos iteration
    for (int k = 0; k < iteration_limit; ++k) {
        apply_hamiltonian(q, w);
        if (k > 0)
            for (std::size_t i = 0; i < dim; ++i) w[i] -= beta[k] * q_previous[i];

        double ak = 0.0;
        for (std::size_t i = 0; i < dim; ++i) ak += q[i] * w[i];
        alpha.push_back(ak);
        for (std::size_t i = 0; i < dim; ++i) w[i] -= ak * q[i];

        double bk = 0.0;
        for (double value : w) bk += value * value;
        bk = std::sqrt(bk);
        beta.push_back(bk);

        result.niter = k + 1;
        const bool breakdown = bk <= 1e-14;
        const bool check_now = result.niter >= 2
            && (result.niter % 5 == 0 || breakdown || result.niter == iteration_limit);
        if (check_now) {
            DenseSymMatrix tridiagonal(static_cast<std::size_t>(result.niter));
            for (int i = 0; i < result.niter; ++i) {
                tridiagonal(i, i) = alpha[i];
                if (i + 1 < result.niter) {
                    tridiagonal(i, i + 1) = beta[i + 1];
                    tridiagonal(i + 1, i) = beta[i + 1];
                }
            }
            const auto eigensystem = jacobi_eigen(tridiagonal);
            const double last_component = eigensystem.eigenvectors[
                static_cast<std::size_t>(result.niter - 1) * result.niter];
            const double ritz_residual = bk * std::abs(last_component);
            if (ritz_residual <= tol * (1.0 + std::abs(eigensystem.eigenvalues[0])))
                result.converged = true;
        }
        if (result.converged || breakdown) break;

        q_previous.swap(q);
        for (std::size_t i = 0; i < dim; ++i) q[i] = w[i] / bk;
    }

    const int n = result.niter;
    DenseSymMatrix T(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        T(i, i) = alpha[i];
        if (i + 1 < n) {
            T(i, i + 1) = beta[i + 1];
            T(i + 1, i) = beta[i + 1];
        }
    }
    const auto t_eig = jacobi_eigen(T);

    // Deterministic second Lanczos pass reconstructs Q_n y without retaining
    // every Krylov vector from the first pass.
    result.psi0.assign(dim, 0.0);
    q = initial;
    std::fill(q_previous.begin(), q_previous.end(), 0.0);
    for (int k = 0; k < n; ++k) {
        const double coefficient = t_eig.eigenvectors[static_cast<std::size_t>(k) * n];
        for (std::size_t i = 0; i < dim; ++i) result.psi0[i] += coefficient * q[i];
        if (k + 1 == n) break;
        apply_hamiltonian(q, w);
        if (k > 0)
            for (std::size_t i = 0; i < dim; ++i) w[i] -= beta[k] * q_previous[i];
        for (std::size_t i = 0; i < dim; ++i) w[i] -= alpha[k] * q[i];
        q_previous.swap(q);
        for (std::size_t i = 0; i < dim; ++i) q[i] = w[i] / beta[k + 1];
    }

    norm = 0.0;
    for (double value : result.psi0) norm += value * value;
    norm = std::sqrt(norm);
    if (!(norm > 0.0)) throw std::runtime_error("lanczos_ground: zero Ritz vector");
    for (double& value : result.psi0) value /= norm;

    apply_hamiltonian(result.psi0, w);
    result.E0 = std::inner_product(result.psi0.begin(), result.psi0.end(), w.begin(), 0.0);
    double residual2 = 0.0;
    for (std::size_t i = 0; i < dim; ++i) {
        const double difference = w[i] - result.E0 * result.psi0[i];
        residual2 += difference * difference;
    }
    result.residual = std::sqrt(residual2);
    result.converged = result.residual <= tol * (1.0 + std::abs(result.E0));

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

// ------------------------------------------------------------
// Cached eigensystem
// ------------------------------------------------------------
// compute_thermal_obs / compute_structure_factor / compute_xi_over_L are each
// called repeatedly at the same (lattice, J, h) in the test suite.  The Jacobi
// solve is O(dim^3) per sweep, so a one-entry cache keyed on the Hamiltonian
// inputs avoids re-diagonalising the same matrix several times.
namespace {

struct EDCache {
    bool valid = false;
    std::string name;
    std::size_t N = 0;
    double J = 0.0, h = 0.0;
    std::vector<Bond> bonds;
    EigenSystem es;

    bool matches(const Lattice& lat, double J_, double h_) const {
        if (!valid || name != lat.name || N != lat.N || J != J_ || h != h_) return false;
        if (bonds.size() != lat.bonds.size()) return false;
        for (std::size_t k = 0; k < bonds.size(); ++k)
            if (bonds[k].i != lat.bonds[k].i || bonds[k].j != lat.bonds[k].j) return false;
        return true;
    }
};

const EigenSystem& cached_eigen(const Lattice& lat, double J, double h) {
    thread_local EDCache cache;
    if (!cache.matches(lat, J, h)) {
        DenseSymMatrix H = build_tfim_hamiltonian(lat, J, h);
        cache.es = jacobi_eigen(H);
        cache.name = lat.name; cache.N = lat.N; cache.J = J; cache.h = h;
        cache.bonds = lat.bonds; cache.valid = true;
    }
    return cache.es;
}

// Boltzmann-weighted probability of each basis state:
//   p(c) = (1/Z) sum_n e^{-beta(E_n-E_0)} |<c|psi_n>|^2
// This is the piece the previous implementation got wrong: it used the
// eigenvalue loop index directly as a basis-state label, never touching the
// eigenvectors, which corrupted every diagonal observable (m, m2, m4, Q, S(q))
// while leaving the eigenvalue-only quantities (E, Cv) correct.
std::vector<double> basis_probabilities(const EigenSystem& es, std::size_t dim,
                                        double beta, double* Z_out = nullptr,
                                        double* E_out = nullptr, double* E2_out = nullptr) {
    const double E0 = es.eigenvalues[0];
    std::vector<double> p(dim, 0.0);
    double Z = 0.0, sE = 0.0, sE2 = 0.0;
    for (std::size_t n = 0; n < dim; ++n) {
        const double En = es.eigenvalues[n];
        const double w = std::exp(-beta * (En - E0));
        Z += w; sE += En * w; sE2 += En * En * w;
        if (w < 1e-300) continue;
        for (std::size_t c = 0; c < dim; ++c) {
            const double amp = es.eigenvectors[c * dim + n];
            p[c] += w * amp * amp;
        }
    }
    const double invZ = 1.0 / Z;
    for (std::size_t c = 0; c < dim; ++c) p[c] *= invZ;
    if (Z_out) *Z_out = Z;
    if (E_out) *E_out = sE * invZ;
    if (E2_out) *E2_out = sE2 * invZ;
    return p;
}

} // namespace

ThermalObs compute_thermal_obs(const Lattice& lattice, double J, double h, double beta) {
    const std::size_t dim = checked_spin_dimension(lattice.N, std::size_t{1} << 14,
                                                   "compute_thermal_obs");
    if (!std::isfinite(beta) || beta < 0.0)
        throw std::invalid_argument("compute_thermal_obs: beta must be finite and non-negative");

    const EigenSystem& es = cached_eigen(lattice, J, h);

    double avgE = 0.0, avgE2 = 0.0;
    std::vector<double> p = basis_probabilities(es, dim, beta, nullptr, &avgE, &avgE2);

    double exp_m = 0.0, exp_m2 = 0.0, exp_m4 = 0.0;
    for (std::size_t c = 0; c < dim; ++c) {
        if (p[c] == 0.0) continue;
        const double m_c = magnetization(c, lattice.N);   // raw sum of sigma^z
        const double m2_c = m_c * m_c;
        exp_m  += std::abs(m_c) * p[c];
        exp_m2 += m2_c * p[c];
        exp_m4 += m2_c * m2_c * p[c];
    }

    const double N_ = static_cast<double>(lattice.N);
    ThermalObs obs;
    obs.E = avgE / N_;
    // heat capacity C = beta^2 (<E^2> - <E>^2); previously this divided by
    // beta^2 instead of multiplying.
    obs.Cv = beta * beta * (avgE2 - avgE * avgE) / N_;
    obs.m  = exp_m / N_;
    obs.m2 = exp_m2 / (N_ * N_);
    obs.m4 = exp_m4 / (N_ * N_ * N_ * N_);
    obs.Q  = (obs.m2 * obs.m2) / (obs.m4 > 1e-30 ? obs.m4 : 1e-30);
    return obs;
}

// ============================================================
// Structure factor S(q)
// ============================================================
double compute_structure_factor(const Lattice& lattice, double J, double h,
                                double beta,
                                const std::array<double, 3>& q) {
    const std::size_t dim = checked_spin_dimension(lattice.N, std::size_t{1} << 14,
                                                   "compute_structure_factor");
    if (lattice.site_coords.size() != lattice.N)
        throw std::invalid_argument("compute_structure_factor: missing site coordinates");
    if (!std::isfinite(beta) || beta < 0.0)
        throw std::invalid_argument("compute_structure_factor: beta must be finite and non-negative");
    if (!std::all_of(q.begin(), q.end(), [](double component) {
            return std::isfinite(component);
        }))
        throw std::invalid_argument("compute_structure_factor: momentum must be finite");

    const EigenSystem& es = cached_eigen(lattice, J, h);
    std::vector<double> p = basis_probabilities(es, dim, beta);

    // S(q) = (1/N^2) < |sum_i sigma^z_i e^{i q.r_i}|^2 >
    std::vector<double> cosq(lattice.N), sinq(lattice.N);
    for (std::size_t i = 0; i < lattice.N; ++i) {
        const double qr = q[0] * lattice.site_coords[i][0]
                        + q[1] * lattice.site_coords[i][1]
                        + q[2] * lattice.site_coords[i][2];
        cosq[i] = std::cos(qr);
        sinq[i] = std::sin(qr);
    }

    const double N_ = static_cast<double>(lattice.N);
    double acc = 0.0;
    for (std::size_t c = 0; c < dim; ++c) {
        if (p[c] == 0.0) continue;
        double re = 0.0, im = 0.0;
        for (std::size_t i = 0; i < lattice.N; ++i) {
            const double s = static_cast<double>(sigma_z(c, i));
            re += s * cosq[i];
            im += s * sinq[i];
        }
        acc += (re * re + im * im) * p[c];
    }
    return acc / (N_ * N_);
}

// ============================================================
// Second-moment correlation length
// ============================================================
double compute_xi_over_L(const Lattice& lattice, double J, double h, double beta) {
    const auto momenta = lattice.smallest_momentum_vectors();
    if (momenta.empty()) return 0.0;
    const auto& first = momenta.front();
    const double q_min = std::sqrt(first[0] * first[0] + first[1] * first[1]
                                 + first[2] * first[2]);

    double S0 = compute_structure_factor(lattice, J, h, beta, {0.0, 0.0, 0.0});
    double Sq = 0.0;
    for (const auto& momentum : momenta)
        Sq += compute_structure_factor(lattice, J, h, beta, momentum);
    Sq /= static_cast<double>(momenta.size());

    double L_eff = static_cast<double>(std::max({lattice.L[0], lattice.L[1], lattice.L[2]}));
    double denom = 4.0 * std::pow(std::sin(q_min / 2.0), 2);
    if (denom < 1e-30 || Sq < 1e-30) return 0.0;

    double xi2 = (S0 / Sq - 1.0) / denom;
    if (xi2 < 0) return 0.0;

    return std::sqrt(xi2) / L_eff;
}

} // namespace cm
