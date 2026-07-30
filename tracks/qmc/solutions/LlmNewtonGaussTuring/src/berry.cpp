#include "berry.hpp"
#include "ed.hpp"
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <random>
#include <stdexcept>

namespace cm {

using cplx = std::complex<double>;

static inline int sv(int st, int site) { return (st >> site) & 1; }

static int checked_dimension(const Lattice& lattice, int maximum, const char* context) {
    if (lattice.N == 0)
        throw std::invalid_argument(std::string(context) + ": lattice has no sites");
    if (lattice.N >= static_cast<std::size_t>(std::numeric_limits<int>::digits))
        throw std::length_error(std::string(context) + ": site count overflows basis index");
    const int dim = 1 << static_cast<int>(lattice.N);
    if (dim > maximum)
        throw std::length_error(std::string(context) + ": Hilbert space exceeds solver limit");
    for (const auto& bond : lattice.bonds)
        if (bond.i >= lattice.N || bond.j >= lattice.N)
            throw std::out_of_range(std::string(context) + ": bond endpoint outside lattice");
    return dim;
}

// ──────────────────────────────────────────────────────────────
// Hamiltonian builder
// ──────────────────────────────────────────────────────────────

std::vector<cplx> build_kolodrubetz_hamiltonian(
    const Lattice& lattice, double J, double Omega, double theta)
{
    if (!std::isfinite(J) || !std::isfinite(Omega) || !std::isfinite(theta))
        throw std::invalid_argument(
            "build_kolodrubetz_hamiltonian: couplings and angle must be finite");
    const int dim = checked_dimension(lattice, 1024, "build_kolodrubetz_hamiltonian");
    const int N = static_cast<int>(lattice.N);
    const int Nb = static_cast<int>(lattice.bonds.size());
    double c = std::cos(theta), s = std::sin(theta);
    std::vector<cplx> H(static_cast<std::size_t>(dim) * dim, cplx(0, 0));

    for (int bi = 0; bi < Nb; ++bi) {
        int i = static_cast<int>(lattice.bonds[bi].i);
        int j = static_cast<int>(lattice.bonds[bi].j);
        int mi = 1 << i, mj = 1 << j;
        for (int st = 0; st < dim; ++st) {
            int si = sv(st, i), sj = sv(st, j);
            const double zi = 1 - 2 * si;
            const double zj = 1 - 2 * sj;
            const double zz = zi * zj;
            H[st*dim + st] += -J * c * c * zz;

            int st2 = st ^ mj;
            H[st*dim + st2] += cplx(0, -J * s * c * zz);

            int st3 = st ^ mi;
            H[st*dim + st3] += cplx(0, -J * s * c * zz);

            int st4 = st ^ mi ^ mj;
            H[st*dim + st4] += J * s * s * zz;
        }
    }
    for (int si = 0; si < N; ++si) {
        int m = 1 << si;
        for (int st = 0; st < dim; ++st) {
            H[st*dim + (st ^ m)] += -Omega;
        }
    }
    return H;
}

// ──────────────────────────────────────────────────────────────
// Rydberg laser-phase Hamiltonian builder
// ──────────────────────────────────────────────────────────────

std::vector<cplx> build_rydberg_hamiltonian(
    const Lattice& lattice, double J, double Omega, double phi)
{
    if (!std::isfinite(J) || !std::isfinite(Omega) || !std::isfinite(phi))
        throw std::invalid_argument(
            "build_rydberg_hamiltonian: couplings and angle must be finite");
    const int dim = checked_dimension(lattice, 65536, "build_rydberg_hamiltonian");
    const int N = static_cast<int>(lattice.N);
    const int Nb = static_cast<int>(lattice.bonds.size());

    std::vector<cplx> H(static_cast<std::size_t>(dim) * dim, cplx(0, 0));

    // Diagonal: -J Σ ZZ
    for (int st = 0; st < dim; ++st) {
        for (int bi = 0; bi < Nb; ++bi) {
            int i = static_cast<int>(lattice.bonds[bi].i);
            int j = static_cast<int>(lattice.bonds[bi].j);
            int si = (st >> i) & 1, sj = (st >> j) & 1;
            H[st*dim + st] += -J * (1 - 2*si) * (1 - 2*sj);
        }
    }

    // Off-diagonal: -Ω Σ (cos φ X_i + sin φ Y_i)
    // X: connects |s⟩ ↔ |s⊕e_i⟩ with real amplitude 1
    // Y: connects with ±i depending on spin:
    //   s_i=0: ⟨1|Y|0⟩ = i   → -iΩ sin φ
    //   s_i=1: ⟨0|Y|1⟩ = -i  → +iΩ sin φ
    // Total: -Ω (cos φ + i·(-1)^{s_i}·sin φ) = -Ω exp(i·(-1)^{s_i}·φ)
    double cphi = std::cos(phi), sphi = std::sin(phi);
    for (int si_idx = 0; si_idx < N; ++si_idx) {
        int m = 1 << si_idx;
        for (int st = 0; st < dim; ++st) {
            int si = (st >> si_idx) & 1;
            cplx amplitude;
            if (si == 0) {
                // s_i=0 → ⟨1|H|0⟩ = -Ω(cos φ + i sin φ) = -Ω exp(i·φ)
                amplitude = cplx(-Omega * cphi, -Omega * sphi);
            } else {
                // s_i=1 → ⟨0|H|1⟩ = -Ω(cos φ - i sin φ) = -Ω exp(-i·φ)
                amplitude = cplx(-Omega * cphi, Omega * sphi);
            }
            H[(st ^ m)*dim + st] += amplitude;
        }
    }
    return H;
}

// ──────────────────────────────────────────────────────────────
// Linear algebra helpers
// ──────────────────────────────────────────────────────────────

static inline cplx cplx_dot(const std::vector<cplx>& x,
                             const std::vector<cplx>& y, int n) {
    cplx s(0, 0);
    for (int i = 0; i < n; ++i) s += std::conj(x[i]) * y[i];
    return s;
}

static inline double cplx_abs_sq(const std::vector<cplx>& x, int n) {
    double s = 0;
    for (int i = 0; i < n; ++i) s += std::norm(x[i]);
    return s;
}

static void cplx_matvec(const cplx* H, int dim,
                         const cplx* x, cplx* y) {
    for (int i = 0; i < dim; ++i) {
        y[i] = cplx(0, 0);
        for (int j = 0; j < dim; ++j)
            y[i] += H[i*dim + j] * x[j];
    }
}

// ──────────────────────────────────────────────────────────────
// Matrix-free H(θ)·v via R_x(θ) H_0 R_x^†(θ)
// ──────────────────────────────────────────────────────────────

static void apply_rx(double theta, cplx* vec, int dim, int N) {
    if (theta == 0.0) return;
    double c = std::cos(theta * 0.5);
    double s = std::sin(theta * 0.5);
    cplx neg_is(0.0, -s);
    for (int q = 0; q < N; ++q) {
        int mask = 1 << q;
        for (int st = 0; st < dim; ++st) {
            if ((st >> q) & 1) continue;
            int st1 = st | mask;
            cplx a = vec[st], b = vec[st1];
            vec[st]  = c * a + neg_is * b;
            vec[st1] = neg_is * a + c * b;
        }
    }
}

static void apply_h0(const Lattice& lattice, double J, double Omega,
                     const cplx* src, cplx* dst, int dim) {
    int N = static_cast<int>(lattice.N);
    int Nb = static_cast<int>(lattice.bonds.size());
    for (int st = 0; st < dim; ++st) dst[st] = cplx(0, 0);

    // Diagonal ZZ terms: H0_ii * src[i]
    for (int st = 0; st < dim; ++st) {
        double zz_sum = 0.0;
        for (int bi = 0; bi < Nb; ++bi) {
            int i = static_cast<int>(lattice.bonds[bi].i);
            int j = static_cast<int>(lattice.bonds[bi].j);
            zz_sum += (1 - 2 * ((st >> i) & 1)) * (1 - 2 * ((st >> j) & 1));
        }
        dst[st] += cplx(-J * zz_sum, 0.0) * src[st];
    }

    // Off-diagonal X terms: -Omega * src[st ^ (1<<si)]
    for (int st = 0; st < dim; ++st) {
        for (int si = 0; si < N; ++si)
            dst[st] += cplx(-Omega, 0.0) * src[st ^ (1 << si)];
    }
}

static void kolodrubetz_matvec(const Lattice& lattice, double J,
                                double Omega, double theta,
                                const cplx* v, cplx* w, int dim) {
    int N = static_cast<int>(lattice.N);
    std::vector<cplx> tmp(v, v + dim);
    apply_rx(-theta, tmp.data(), dim, N);       // R_x^† v
    std::vector<cplx> h0tmp(dim);
    apply_h0(lattice, J, Omega, tmp.data(), h0tmp.data(), dim); // H_0 (R_x^† v)
    std::copy(h0tmp.begin(), h0tmp.end(), w);
    apply_rx(theta, w, dim, N);                 // R_x (H_0 R_x^† v)
}

using MatvecFn = std::function<void(const cplx* v, cplx* w)>;

static GroundState matrix_free_lanczos(int dim, const MatvecFn& matvec, int m_max) {
    if (m_max <= 0)
        throw std::invalid_argument("matrix_free_lanczos: m_max must be positive");
    if (m_max > dim) m_max = dim;

    std::vector<std::vector<cplx>> Q;
    Q.reserve(m_max + 1);

    std::mt19937 rng(42);
    std::uniform_real_distribution<double> dist(-1, 1);
    Q.push_back(std::vector<cplx>(dim));
    double nr = 0;
    for (int i = 0; i < dim; ++i) {
        Q[0][i] = cplx(dist(rng), dist(rng));
        nr += std::norm(Q[0][i]);
    }
    nr = std::sqrt(nr);
    if (nr < 1e-30) { Q[0][0] = cplx(1, 0); nr = 1.0; }
    for (auto& z : Q[0]) z /= nr;

    std::vector<double> alpha, beta;
    alpha.reserve(m_max); beta.reserve(m_max);
    beta.push_back(0);

    std::vector<cplx> w(dim);
    int m = 0;
    bool converged = false;

    for (int k = 0; k < m_max; ++k) {
        matvec(Q[k].data(), w.data());
        double ak = std::real(cplx_dot(Q[k], w, dim));
        alpha.push_back(ak);
        if (k > 0)
            for (int i = 0; i < dim; ++i) w[i] -= beta[k] * Q[k-1][i];
        for (int i = 0; i < dim; ++i) w[i] -= ak * Q[k][i];
        for (int pass = 0; pass < 2; ++pass)
            for (int j = 0; j <= k; ++j) {
                cplx proj = cplx_dot(Q[j], w, dim);
                for (int i = 0; i < dim; ++i) w[i] -= proj * Q[j][i];
            }
        double bkp1 = std::sqrt(cplx_abs_sq(w, dim));
        beta.push_back(bkp1);
        m = k + 1;
        bool breakdown = bkp1 <= 1e-14;
        if (m >= 2 && (m % 5 == 0 || breakdown || m == m_max)) {
            DenseSymMatrix T(static_cast<std::size_t>(m));
            for (int i = 0; i < m; ++i) {
                T(i, i) = alpha[i];
                if (i > 0) { T(i, i-1) = beta[i]; T(i-1, i) = beta[i]; }
            }
            auto eigsys = jacobi_eigen(T, 50, 1e-12);
            double residual = bkp1 * std::abs(eigsys.eigenvectors[(m-1) * m]);
            converged = residual <= 1e-11 * (1.0 + std::abs(eigsys.eigenvalues[0]));
        }
        if (converged || breakdown) break;
        Q.push_back(std::vector<cplx>(dim));
        for (int i = 0; i < dim; ++i) Q[k+1][i] = w[i] / bkp1;
    }

    DenseSymMatrix Tm(static_cast<std::size_t>(m));
    for (int i = 0; i < m; ++i) {
        Tm(i, i) = alpha[i];
        if (i > 0) { Tm(i, i-1) = beta[i]; Tm(i-1, i) = beta[i]; }
    }
    auto eigsys = jacobi_eigen(Tm, 50, 1e-12);
    double E0 = eigsys.eigenvalues[0];

    std::vector<cplx> psi0(dim, cplx(0,0));
    for (int j = 0; j < m; ++j) {
        double y0j = eigsys.eigenvectors[j * m];
        for (int i = 0; i < dim; ++i) psi0[i] += y0j * Q[j][i];
    }
    nr = std::sqrt(cplx_abs_sq(psi0, dim));
    if (nr > 1e-30)
        for (auto& z : psi0) z /= nr;

    std::vector<cplx> Hpsi(dim);
    matvec(psi0.data(), Hpsi.data());
    E0 = std::real(cplx_dot(psi0, Hpsi, dim));
    double residual2 = 0.0;
    for (int i = 0; i < dim; ++i) residual2 += std::norm(Hpsi[i] - E0 * psi0[i]);

    GroundState result;
    result.eigenvector = std::move(psi0);
    result.dim = dim;
    result.E0 = E0;
    result.residual = std::sqrt(residual2);
    result.converged = result.residual <= 1e-10 * (1.0 + std::abs(E0));
    return result;
}

// ──────────────────────────────────────────────────────────────
// Complex Hermitian Lanczos with auto-dispatch
// ──────────────────────────────────────────────────────────────

GroundState solve_ground_state_lanczos(
    const Lattice& lattice, double J, double Omega, double theta,
    int m_max)
{
    const int dim = checked_dimension(lattice, 65536, "solve_ground_state_lanczos");
    if (m_max <= 0)
        throw std::invalid_argument("solve_ground_state_lanczos: m_max must be positive");

    if (dim <= 1024) {
        // Dense complex Hermitian Lanczos (N ≤ 10)
        auto Hmat = build_kolodrubetz_hamiltonian(lattice, J, Omega, theta);
        if (m_max > dim) m_max = dim;

        std::vector<std::vector<cplx>> Q;
        Q.reserve(m_max + 1);
        std::mt19937 rng(42);
        std::uniform_real_distribution<double> dist(-1, 1);
        Q.push_back(std::vector<cplx>(dim));
        double nr = 0;
        for (int i = 0; i < dim; ++i) {
            Q[0][i] = cplx(dist(rng), dist(rng));
            nr += std::norm(Q[0][i]);
        }
        nr = std::sqrt(nr);
        for (auto& z : Q[0]) z /= nr;

        std::vector<double> alpha, beta;
        alpha.reserve(m_max); beta.reserve(m_max);
        beta.push_back(0);
        std::vector<cplx> w(dim);
        int m = 0;
        bool converged = false;

        for (int k = 0; k < m_max; ++k) {
            cplx_matvec(Hmat.data(), dim, Q[k].data(), w.data());
            double ak = std::real(cplx_dot(Q[k], w, dim));
            alpha.push_back(ak);
            if (k > 0)
                for (int i = 0; i < dim; ++i) w[i] -= beta[k] * Q[k-1][i];
            for (int i = 0; i < dim; ++i) w[i] -= ak * Q[k][i];
            for (int pass = 0; pass < 2; ++pass)
                for (int j = 0; j <= k; ++j) {
                    cplx proj = cplx_dot(Q[j], w, dim);
                    for (int i = 0; i < dim; ++i) w[i] -= proj * Q[j][i];
                }
            double bkp1 = std::sqrt(cplx_abs_sq(w, dim));
            beta.push_back(bkp1);
            m = k + 1;
            const bool breakdown = bkp1 <= 1e-14;
            if (m >= 2 && (m % 5 == 0 || breakdown || m == m_max)) {
                DenseSymMatrix T(static_cast<std::size_t>(m));
                for (int i = 0; i < m; ++i) {
                    T(i, i) = alpha[i];
                    if (i > 0) { T(i, i-1) = beta[i]; T(i-1, i) = beta[i]; }
                }
                auto eigsys = jacobi_eigen(T, 50, 1e-12);
                double residual = bkp1 * std::abs(eigsys.eigenvectors[(m-1) * m]);
                converged = residual <= 1e-11 * (1.0 + std::abs(eigsys.eigenvalues[0]));
            }
            if (converged || breakdown) break;
            Q.push_back(std::vector<cplx>(dim));
            for (int i = 0; i < dim; ++i) Q[k+1][i] = w[i] / bkp1;
        }

        DenseSymMatrix Tm(static_cast<std::size_t>(m));
        for (int i = 0; i < m; ++i) {
            Tm(i, i) = alpha[i];
            if (i > 0) { Tm(i, i-1) = beta[i]; Tm(i-1, i) = beta[i]; }
        }
        auto eigsys = jacobi_eigen(Tm, 50, 1e-12);
        double E0 = eigsys.eigenvalues[0];
        std::vector<cplx> psi0(dim, cplx(0,0));
        for (int j = 0; j < m; ++j) {
            double y0j = eigsys.eigenvectors[j * m];
            for (int i = 0; i < dim; ++i) psi0[i] += y0j * Q[j][i];
        }
        nr = std::sqrt(cplx_abs_sq(psi0, dim));
        if (nr > 1e-30)
            for (auto& z : psi0) z /= nr;
        std::vector<cplx> Hpsi(dim);
        cplx_matvec(Hmat.data(), dim, psi0.data(), Hpsi.data());
        E0 = std::real(cplx_dot(psi0, Hpsi, dim));
        double residual2 = 0.0;
        for (int i = 0; i < dim; ++i) residual2 += std::norm(Hpsi[i] - E0 * psi0[i]);

        GroundState result;
        result.eigenvector = std::move(psi0);
        result.dim = dim; result.E0 = E0;
        result.residual = std::sqrt(residual2);
        result.converged = result.residual <= 1e-10 * (1.0 + std::abs(E0));
        return result;
    }

    // Matrix-free path (N ≥ 11, dim > 1024)
    MatvecFn matvec = [&](const cplx* v, cplx* w) {
        kolodrubetz_matvec(lattice, J, Omega, theta, v, w, dim);
    };
    return matrix_free_lanczos(dim, matvec, m_max);
}

// ──────────────────────────────────────────────────────────────
// Auto-dispatch (delegates to Lanczos)
// ──────────────────────────────────────────────────────────────

GroundState solve_ground_state(
    const Lattice& lattice, double J, double Omega, double theta)
{
    return solve_ground_state_lanczos(lattice, J, Omega, theta);
}

// ──────────────────────────────────────────────────────────────
// Rydberg solver and grid
// ──────────────────────────────────────────────────────────────

GroundState solve_ground_state_rydberg(
    const Lattice& lattice, double J, double Omega, double phi)
{
    const int dim = checked_dimension(lattice, 1024, "solve_ground_state_rydberg");
    auto Hmat = build_rydberg_hamiltonian(lattice, J, Omega, phi);

    // Dense Lanczos (same algorithm as Kolodrubetz dense path)
    int m_max = 150;
    if (m_max > dim) m_max = dim;

    std::vector<std::vector<cplx>> Q;
    Q.reserve(m_max + 1);
    std::mt19937 rng(42);
    std::uniform_real_distribution<double> dist(-1, 1);
    Q.push_back(std::vector<cplx>(dim));
    double nr = 0;
    for (int i = 0; i < dim; ++i) {
        Q[0][i] = cplx(dist(rng), dist(rng));
        nr += std::norm(Q[0][i]);
    }
    nr = std::sqrt(nr);
    for (auto& z : Q[0]) z /= nr;

    std::vector<double> alpha, beta;
    alpha.reserve(m_max); beta.reserve(m_max);
    beta.push_back(0);
    std::vector<cplx> w(dim);
    int m = 0;
    bool converged = false;

    for (int k = 0; k < m_max; ++k) {
        cplx_matvec(Hmat.data(), dim, Q[k].data(), w.data());
        double ak = std::real(cplx_dot(Q[k], w, dim));
        alpha.push_back(ak);
        if (k > 0)
            for (int i = 0; i < dim; ++i) w[i] -= beta[k] * Q[k-1][i];
        for (int i = 0; i < dim; ++i) w[i] -= ak * Q[k][i];
        for (int pass = 0; pass < 2; ++pass)
            for (int j = 0; j <= k; ++j) {
                cplx proj = cplx_dot(Q[j], w, dim);
                for (int i = 0; i < dim; ++i) w[i] -= proj * Q[j][i];
            }
        double bkp1 = std::sqrt(cplx_abs_sq(w, dim));
        beta.push_back(bkp1);
        m = k + 1;
        const bool breakdown = bkp1 <= 1e-14;
        if (m >= 2 && (m % 5 == 0 || breakdown || m == m_max)) {
            DenseSymMatrix T(static_cast<std::size_t>(m));
            for (int i = 0; i < m; ++i) {
                T(i, i) = alpha[i];
                if (i > 0) { T(i, i-1) = beta[i]; T(i-1, i) = beta[i]; }
            }
            auto eigsys = jacobi_eigen(T, 50, 1e-12);
            double residual = bkp1 * std::abs(eigsys.eigenvectors[(m-1) * m]);
            converged = residual <= 1e-11 * (1.0 + std::abs(eigsys.eigenvalues[0]));
        }
        if (converged || breakdown) break;
        Q.push_back(std::vector<cplx>(dim));
        for (int i = 0; i < dim; ++i) Q[k+1][i] = w[i] / bkp1;
    }

    DenseSymMatrix Tm(static_cast<std::size_t>(m));
    for (int i = 0; i < m; ++i) {
        Tm(i, i) = alpha[i];
        if (i > 0) { Tm(i, i-1) = beta[i]; Tm(i-1, i) = beta[i]; }
    }
    auto eigsys = jacobi_eigen(Tm, 50, 1e-12);
    double E0 = eigsys.eigenvalues[0];
    std::vector<cplx> psi0(dim, cplx(0,0));
    for (int j = 0; j < m; ++j) {
        double y0j = eigsys.eigenvectors[j * m];
        for (int i = 0; i < dim; ++i) psi0[i] += y0j * Q[j][i];
    }
    nr = std::sqrt(cplx_abs_sq(psi0, dim));
    if (nr > 1e-30)
        for (auto& z : psi0) z /= nr;
    std::vector<cplx> Hpsi(dim);
    cplx_matvec(Hmat.data(), dim, psi0.data(), Hpsi.data());
    E0 = std::real(cplx_dot(psi0, Hpsi, dim));
    double residual2 = 0.0;
    for (int i = 0; i < dim; ++i) residual2 += std::norm(Hpsi[i] - E0 * psi0[i]);

    GroundState result;
    result.eigenvector = std::move(psi0);
    result.dim = dim; result.E0 = E0;
    result.residual = std::sqrt(residual2);
    result.converged = result.residual <= 1e-10 * (1.0 + std::abs(E0));
    return result;
}

std::vector<std::vector<BerryCurvature>> compute_berry_curvature_grid_rydberg(
    const Lattice& lattice, double J, const ParamGrid& grid)
{
    const int n1 = static_cast<int>(grid.theta_values.size()); // interpreted as phi
    const int n2 = static_cast<int>(grid.omega_values.size());
    if (n1 < 2 || n2 < 2)
        throw std::invalid_argument(
            "compute_berry_curvature_grid_rydberg: each axis needs at least two points");
    std::vector<std::vector<GroundState>> gs(n1, std::vector<GroundState>(n2));
    for (int i = 0; i < n1; ++i) for (int j = 0; j < n2; ++j)
        gs[i][j] = solve_ground_state_rydberg(
            lattice, J, grid.omega_values[j], grid.theta_values[i]);
    std::vector<std::vector<BerryCurvature>> r(n1-1, std::vector<BerryCurvature>(n2-1));
    for (int i = 0; i < n1-1; ++i) for (int j = 0; j < n2-1; ++j) {
        const double dphi     = grid.theta_values[i + 1] - grid.theta_values[i];
        const double dOmega   = grid.omega_values[j + 1] - grid.omega_values[j];
        r[i][j] = fhs_curvature(gs[i][j], gs[i+1][j], gs[i+1][j+1], gs[i][j+1],
                                dphi, dOmega);
    }
    return r;
}

// ──────────────────────────────────────────────────────────────
// Overlap and FHS curvature
// ──────────────────────────────────────────────────────────────

cplx overlap(const GroundState& a, const GroundState& b) {
    if (a.dim != b.dim || a.dim <= 0
        || a.eigenvector.size() != static_cast<std::size_t>(a.dim)
        || b.eigenvector.size() != static_cast<std::size_t>(b.dim))
        throw std::invalid_argument("overlap: incompatible ground-state dimensions");
    cplx s(0,0);
    for (int i = 0; i < a.dim; ++i) s += std::conj(a.eigenvector[i]) * b.eigenvector[i];
    return s;
}

static void validate_fhs_ground_state(const GroundState& state,
                                      const char* label) {
    if (!state.converged)
        throw std::runtime_error(std::string("fhs_curvature: unconverged ") + label);
    if (!std::isfinite(state.E0) || !std::isfinite(state.residual)
        || state.residual < 0.0)
        throw std::invalid_argument(
            std::string("fhs_curvature: invalid solver metadata for ") + label);
    for (const auto& amplitude : state.eigenvector)
        if (!std::isfinite(amplitude.real()) || !std::isfinite(amplitude.imag()))
            throw std::invalid_argument(
                std::string("fhs_curvature: non-finite amplitude in ") + label);
}

BerryCurvature fhs_curvature(const GroundState& gs00, const GroundState& gs10,
                              const GroundState& gs11, const GroundState& gs01,
                              double dlambda1, double dlambda2)
{
    const double area = dlambda1 * dlambda2;
    if (!std::isfinite(area) || area == 0.0)
        throw std::invalid_argument("fhs_curvature: plaquette steps must have non-zero finite area");
    validate_fhs_ground_state(gs00, "gs00");
    validate_fhs_ground_state(gs10, "gs10");
    validate_fhs_ground_state(gs11, "gs11");
    validate_fhs_ground_state(gs01, "gs01");

    BerryCurvature bc;
    auto U1 = overlap(gs00, gs10);
    auto U2 = overlap(gs10, gs11);
    auto U1star = overlap(gs11, gs01);
    auto U2star = overlap(gs01, gs00);

    bc.absU1 = std::abs(U1);
    bc.absU2 = std::abs(U2star);
    bc.min_overlap = std::min({bc.absU1, std::abs(U2), std::abs(U1star), bc.absU2});
    if (!(bc.min_overlap > 1e-12)) {
        bc.wilson_phase = std::numeric_limits<double>::quiet_NaN();
        bc.flux = std::numeric_limits<double>::quiet_NaN();
        bc.F12 = std::numeric_limits<double>::quiet_NaN();
        return bc;
    }
    U1 /= std::abs(U1);
    U2 /= std::abs(U2);
    U1star /= std::abs(U1star);
    U2star /= std::abs(U2star);

    bc.wilson_phase = std::arg(U1 * U2 * U1star * U2star);
    bc.flux = -bc.wilson_phase;
    bc.F12 = bc.flux / area;
    bc.valid = true;
    return bc;
}

// ──────────────────────────────────────────────────────────────
// Convenience wrapper
// ──────────────────────────────────────────────────────────────

BerryCurvature fhs_curvature_single(const Lattice& lattice, double J,
                                     double theta, double Omega,
                                     double dtheta, double dOmega)
{
    auto g00 = solve_ground_state(lattice, J, Omega, theta);
    auto g10 = solve_ground_state(lattice, J, Omega, theta + dtheta);
    auto g11 = solve_ground_state(lattice, J, Omega + dOmega, theta + dtheta);
    auto g01 = solve_ground_state(lattice, J, Omega + dOmega, theta);
    return fhs_curvature(g00, g10, g11, g01, dtheta, dOmega);
}

// ──────────────────────────────────────────────────────────────
// Grid computation
// ──────────────────────────────────────────────────────────────

std::vector<std::vector<BerryCurvature>> compute_berry_curvature_grid(
    const Lattice& lattice, double J, const ParamGrid& grid)
{
    const int n1 = static_cast<int>(grid.theta_values.size());
    const int n2 = static_cast<int>(grid.omega_values.size());
    if (n1 < 2 || n2 < 2)
        throw std::invalid_argument("compute_berry_curvature_grid: each axis needs at least two points");
    std::vector<std::vector<GroundState>> gs(n1, std::vector<GroundState>(n2));
    for (int i = 0; i < n1; ++i) for (int j = 0; j < n2; ++j)
        gs[i][j] = solve_ground_state(lattice, J, grid.omega_values[j], grid.theta_values[i]);
    std::vector<std::vector<BerryCurvature>> r(n1-1, std::vector<BerryCurvature>(n2-1));
    for (int i = 0; i < n1-1; ++i) for (int j = 0; j < n2-1; ++j) {
        const double dtheta = grid.theta_values[i + 1] - grid.theta_values[i];
        const double dOmega = grid.omega_values[j + 1] - grid.omega_values[j];
        r[i][j] = fhs_curvature(gs[i][j], gs[i+1][j], gs[i+1][j+1], gs[i][j+1],
                                dtheta, dOmega);
    }
    return r;
}

// ──────────────────────────────────────────────────────────────
// ∂θH expectation via ED thermal average (for SSE cross-check)
// ──────────────────────────────────────────────────────────────

double compute_dthetah_diagonal_ed(const Lattice& lattice, double J, double Omega,
                                   double theta, double beta)
{
    const int dim = checked_dimension(lattice, 64, "compute_dthetah_diagonal_ed");
    const int N = static_cast<int>(lattice.N);
    if (!std::isfinite(J) || !std::isfinite(Omega) || !std::isfinite(theta))
        throw std::invalid_argument(
            "compute_dthetah_diagonal_ed: couplings and angle must be finite");
    if (!std::isfinite(beta) || beta < 0.0)
        throw std::invalid_argument(
            "compute_dthetah_diagonal_ed: beta must be finite and non-negative");

    // Build H = -J Σ ZZ - Omega Σ X (real symmetric TFIM, θ=0)
    DenseSymMatrix H(static_cast<std::size_t>(dim));
    for (int st = 0; st < dim; ++st) {
        for (int bi = 0; bi < static_cast<int>(lattice.bonds.size()); ++bi) {
            int i = static_cast<int>(lattice.bonds[bi].i);
            int j = static_cast<int>(lattice.bonds[bi].j);
            int si = (st >> i) & 1, sj = (st >> j) & 1;
            H(st, st) += -J * (1 - 2*si) * (1 - 2*sj);
        }
        for (int si = 0; si < N; ++si)
            H(st, st ^ (1 << si)) += -Omega;
    }

    auto eigsys = jacobi_eigen(H, 50, 1e-12);

    // Compute the H0 thermal expectation of Σ ZZ for the diagnostic.
    double Z = 0.0, sum_ZZ = 0.0;
    for (int n = 0; n < dim; ++n) {
        double E_n = eigsys.eigenvalues[n];
        double w = std::exp(-beta * (E_n - eigsys.eigenvalues[0])); // shift for numerics
        Z += w;

        // Compute ⟨ψ_n| Σ_bonds ZZ |ψ_n⟩
        double zz_n = 0.0;
        auto& psi_n = eigsys.eigenvectors;
        for (int st = 0; st < dim; ++st) {
            double psi2 = psi_n[st * dim + n] * psi_n[st * dim + n]; // |⟨st|ψ_n⟩|²
            for (int bi = 0; bi < static_cast<int>(lattice.bonds.size()); ++bi) {
                int i = static_cast<int>(lattice.bonds[bi].i);
                int j = static_cast<int>(lattice.bonds[bi].j);
                int si = (st >> i) & 1, sj = (st >> j) & 1;
                zz_n += psi2 * (1 - 2*si) * (1 - 2*sj);
            }
        }
        sum_ZZ += w * zz_n;
    }

    // Historical name: dthetah_diagonal. This is the H0-ensemble diagnostic,
    // not a rotated-state expectation or an equilibrium generalized force.
    double zz_exp = sum_ZZ / Z; // thermal expectation of Σ_bonds ZZ
    double dthetah_diagonal = J * std::sin(2 * theta) * zz_exp / N;

    return dthetah_diagonal;
}

namespace {

double adaptive_simpson(const std::function<double(double)>& function,
                        double left, double right, double f_left, double f_mid,
                        double f_right, double whole, double tolerance, int depth) {
    const double midpoint = 0.5 * (left + right);
    const double left_midpoint = 0.5 * (left + midpoint);
    const double right_midpoint = 0.5 * (midpoint + right);
    const double f_left_midpoint = function(left_midpoint);
    const double f_right_midpoint = function(right_midpoint);
    const double left_value = (midpoint - left) * (f_left + 4.0 * f_left_midpoint + f_mid) / 6.0;
    const double right_value = (right - midpoint) * (f_mid + 4.0 * f_right_midpoint + f_right) / 6.0;
    const double refined = left_value + right_value;
    if (depth == 0 || std::abs(refined - whole) <= 15.0 * tolerance)
        return refined + (refined - whole) / 15.0;
    return adaptive_simpson(function, left, midpoint, f_left, f_left_midpoint, f_mid,
                            left_value, 0.5 * tolerance, depth - 1)
         + adaptive_simpson(function, midpoint, right, f_mid, f_right_midpoint, f_right,
                            right_value, 0.5 * tolerance, depth - 1);
}

} // namespace

// ──────────────────────────────────────────────────────────────
// Direct ED spectral-response Berry curvature
// ──────────────────────────────────────────────────────────────

double compute_berry_curvature_response_ed(const Lattice& lattice, double J,
                                           double Omega, double /*theta*/)
{
    // F_{θΩ} is independent of θ by the unitary-rotation argument:
    // H(θ) = R_x(θ) H_0 R_x^†(θ) → ⟨ψ(θ)|∂H(θ)|ψ(θ)⟩ = ⟨ψ(0)|∂H(0)|ψ(0)⟩.
    // We therefore work in the real symmetric H_0 = -J Σ ZZ - Ω Σ X.
    const int dim = checked_dimension(lattice, 64, "compute_berry_curvature_response_ed");
    if (dim < 2) return 0.0; // single site has no curvature
    const int N = static_cast<int>(lattice.N);

    // Build H_0 as real symmetric matrix (same as ED infrastructure)
    DenseSymMatrix H0(static_cast<std::size_t>(dim));
    for (int st = 0; st < dim; ++st) {
        for (int bi = 0; bi < static_cast<int>(lattice.bonds.size()); ++bi) {
            int i = static_cast<int>(lattice.bonds[bi].i);
            int j = static_cast<int>(lattice.bonds[bi].j);
            int si = (st >> i) & 1, sj = (st >> j) & 1;
            H0(st, st) += -J * (1 - 2*si) * (1 - 2*sj);
        }
        for (int si = 0; si < N; ++si)
            H0(st, st ^ (1 << si)) += -Omega;
    }

    auto eigsys = jacobi_eigen(H0, 50, 1e-12);
    const double E0 = eigsys.eigenvalues[0];

    // Precompute degree (number of neighbours) for each site
    std::vector<int> neighbour_count(N, 0);
    for (const auto& bond : lattice.bonds) {
        neighbour_count[static_cast<int>(bond.i)]++;
        neighbour_count[static_cast<int>(bond.j)]++;
    }

    // Reserve work arrays
    std::vector<int> degree(N, 0);
    for (int s = 0; s < N; ++s)
        degree[s] = neighbour_count[s];

    // Sum over excited states n ≥ 1
    double F_total = 0.0;
    for (int n = 1; n < dim; ++n) {
        const double dE = eigsys.eigenvalues[n] - E0;
        if (std::abs(dE) < 1e-14) continue;

        // ── Compute ⟨ψ₀|∂_θ H|ψ_n⟩ / i  (real, anti-symmetric) ──
        //
        // ∂_θ H(0) = J Σ_{⟨i,j⟩} (Y_i Z_j + Z_i Y_j)
        // Each bond (i,j) contributes to pairs (a,b) that differ at i or j
        // with amplitude  iJ·(1-2b_i)·(1-2b_j).
        //
        // We accumulate the anti-symmetrised real matrix element:
        //   ⟨ψ₀|∂_θ H/i|ψ_n⟩ = Σ_{a<b} dtheta_real(a,b)·(ψ₀(a)ψ_n(b)-ψ₀(b)ψ_n(a))
        double dtheta_over_i = 0.0;
        for (const auto& bond : lattice.bonds) {
            const int i = static_cast<int>(bond.i);
            const int j = static_cast<int>(bond.j);
            const int mi = 1 << i, mj = 1 << j;

            for (int b = 0; b < dim; ++b) {
                const int bi_spin = (b >> i) & 1;
                const int bj_spin = (b >> j) & 1;
                const double pre = J * (1 - 2*bi_spin) * (1 - 2*bj_spin);

                // Y_i Z_j term: flips i
                {
                    const int a = b ^ mi;
                    if (a > b) { // count each unordered pair once (a > b)
                        // Pair (a,b) where a has bit i flipped relative to b
                        dtheta_over_i += pre * (eigsys.eigenvectors[a * dim]
                            * eigsys.eigenvectors[b * dim + n]
                            - eigsys.eigenvectors[b * dim]
                            * eigsys.eigenvectors[a * dim + n]);
                    }
                }
                // Z_i Y_j term: flips j
                {
                    const int a = b ^ mj;
                    if (a > b) {
                        dtheta_over_i += pre * (eigsys.eigenvectors[a * dim]
                            * eigsys.eigenvectors[b * dim + n]
                            - eigsys.eigenvectors[b * dim]
                            * eigsys.eigenvectors[a * dim + n]);
                    }
                }
            }
        }

        // ── Compute ⟨ψ_n|∂_Ω H|ψ₀⟩  (real, symmetric) ──
        //
        // ∂_Ω H(0) = -Σ_s X_s.  X_s connects |b⟩ ↔ |b⊕e_s⟩ with amplitude 1.
        // Anti-symmetrise because ∂_Ω H is real symmetric but we use
        // the same anti-symmetric pair-sum form.
        double domega = 0.0;
        for (int s = 0; s < N; ++s) {
            const int m = 1 << s;
            for (int b = 0; b < dim; ++b) {
                const int a = b ^ m;
                if (a > b) {
                    // ∂_Ω H = -Σ X_i is real SYMMETRIC (diagonal-free).
                    // Symmetric form: ψ_n(a)ψ₀(b) + ψ_n(b)ψ₀(a).
                    const double val = -1.0;
                    domega += val * (eigsys.eigenvectors[a * dim + n]
                        * eigsys.eigenvectors[b * dim]
                        + eigsys.eigenvectors[b * dim + n]
                        * eigsys.eigenvectors[a * dim]);
                }
            }
        }

        // F_{θΩ} = -2 Im Σ ⟨ψ₀|∂_θ H|ψ_n⟩⟨ψ_n|∂_Ω H|ψ₀⟩ / (E_n-E₀)^2
        // ⟨ψ₀|∂_θ H|ψ_n⟩ = i·dtheta_over_i, ⟨ψ_n|∂_Ω H|ψ₀⟩ = domega (real)
        // product = i·dtheta_over_i·domega → Im(product) = dtheta_over_i·domega
        F_total -= 2.0 * dtheta_over_i * domega / (dE * dE);
    }

    return F_total / static_cast<double>(N);
}

double tfim_chain_berry_curvature_density_finite(std::size_t sites, double J,
                                                 double Omega) {
    if (sites < 2 || sites % 2 != 0)
        throw std::invalid_argument(
            "tfim_chain_berry_curvature_density_finite: sites must be even and >= 2");
    if (!(J >= 0.0) || !std::isfinite(J) || !std::isfinite(Omega))
        throw std::invalid_argument(
            "tfim_chain_berry_curvature_density_finite: invalid coupling");
    if (J == 0.0) return 0.0;

    double sum = 0.0;
    for (std::size_t mode = 0; mode < sites; ++mode) {
        const double momentum = M_PI * (2.0 * static_cast<double>(mode) + 1.0)
                              / static_cast<double>(sites);
        const double sine = std::sin(momentum);
        const double dispersion2 = J * J + Omega * Omega
                                 - 2.0 * J * Omega * std::cos(momentum);
        sum += sine * sine / std::pow(dispersion2, 1.5);
    }
    return -J * J * sum / (2.0 * static_cast<double>(sites));
}

double tfim_chain_berry_curvature_density_exact(double J, double Omega,
                                                double tolerance) {
    if (!(J >= 0.0) || !std::isfinite(J) || !std::isfinite(Omega))
        throw std::invalid_argument("tfim_chain_berry_curvature_density_exact: invalid coupling");
    if (!(tolerance > 0.0) || !std::isfinite(tolerance))
        throw std::invalid_argument("tfim_chain_berry_curvature_density_exact: invalid tolerance");
    if (J == 0.0) return 0.0;
    if (std::abs(std::abs(Omega) - J) <= 8.0 * std::numeric_limits<double>::epsilon()
                                            * std::max({1.0, J, std::abs(Omega)}))
        return -std::numeric_limits<double>::infinity();

    const auto integrand = [J, Omega](double momentum) {
        const double sine = std::sin(momentum);
        const double dispersion2 = J * J + Omega * Omega
                                 - 2.0 * J * Omega * std::cos(momentum);
        return sine * sine / std::pow(dispersion2, 1.5);
    };
    const double left = 0.0;
    const double right = M_PI;
    const double midpoint = 0.5 * (left + right);
    const double f_left = integrand(left);
    const double f_mid = integrand(midpoint);
    const double f_right = integrand(right);
    const double whole = (right - left) * (f_left + 4.0 * f_mid + f_right) / 6.0;
    const double integral = adaptive_simpson(integrand, left, right, f_left, f_mid, f_right,
                                             whole, tolerance, 24);
    return -J * J * integral / (2.0 * M_PI);
}

} // namespace cm
