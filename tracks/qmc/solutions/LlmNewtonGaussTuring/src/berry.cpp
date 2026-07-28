#include "berry.hpp"
#include "ed.hpp"
#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>

namespace cm {

using cplx = std::complex<double>;

static inline int sv(int st, int site) { return (st >> site) & 1; }

// ──────────────────────────────────────────────────────────────
// Hamiltonian builder
// ──────────────────────────────────────────────────────────────

std::vector<cplx> build_kolodrubetz_hamiltonian(
    const Lattice& lattice, double J, double Omega, double theta)
{
    int N = static_cast<int>(lattice.N), dim = 1 << N, Nb = static_cast<int>(lattice.Nb);
    double c = std::cos(theta), s = std::sin(theta);
    std::vector<cplx> H(dim * dim, cplx(0, 0));

    for (int bi = 0; bi < Nb; ++bi) {
        int i = static_cast<int>(lattice.bonds[bi].i);
        int j = static_cast<int>(lattice.bonds[bi].j);
        int mi = 1 << i, mj = 1 << j;
        for (int st = 0; st < dim; ++st) {
            int si = sv(st, i), sj = sv(st, j);
            double zz = (1 - 2*si) * (1 - 2*sj);
            H[st*dim + st] += -J * c * c * zz;

            int st2 = st ^ mj;
            double zi = (1 - 2*si);
            H[st*dim + st2] += J * s * c * cplx(0, 1) * zi * (sj ? -1.0 : 1.0);

            int st3 = st ^ mi;
            double zj = (1 - 2*sj);
            H[st*dim + st3] += J * s * c * cplx(0, 1) * (si ? -1.0 : 1.0) * zj;

            int st4 = st ^ mi ^ mj;
            H[st*dim + st4] += -J * s * s * ((si == sj) ? -1.0 : 1.0);
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
// Complex Hermitian Lanczos with full reorthogonalisation
// ──────────────────────────────────────────────────────────────

GroundState solve_ground_state_lanczos(
    const Lattice& lattice, double J, double Omega, double theta,
    int m_max)
{
    int N = static_cast<int>(lattice.N), dim = 1 << N;
    if (dim > 1024)
        throw std::runtime_error("solve_ground_state_lanczos: dim > 1024");

    auto Hmat = build_kolodrubetz_hamiltonian(lattice, J, Omega, theta);

    // Adaptive m_max for small dim
    if (m_max > dim) m_max = dim;

    std::vector<std::vector<cplx>> Q;  // Lanczos vectors
    Q.reserve(m_max + 1);

    // Deterministic random initial vector
    std::mt19937 rng(static_cast<unsigned>(
        std::hash<double>{}(theta * 1e9 + Omega * 1e6 + J * 1e3 + N + 42)));
    std::uniform_real_distribution<double> dist(-1, 1);

    Q.push_back(std::vector<cplx>(dim));
    double nr = 0;
    for (int i = 0; i < dim; ++i) {
        Q[0][i] = cplx(dist(rng), dist(rng));
        nr += std::norm(Q[0][i]);
    }
    nr = std::sqrt(nr);
    for (auto& z : Q[0]) z /= nr;

    std::vector<double> alpha;
    std::vector<double> beta;
    alpha.reserve(m_max);
    beta.reserve(m_max);
    beta.push_back(0);

    std::vector<cplx> w(dim);
    int m = 0;

    for (int k = 0; k < m_max; ++k) {
        cplx_matvec(Hmat.data(), dim, Q[k].data(), w.data());
        double ak = std::real(cplx_dot(Q[k], w, dim));
        alpha.push_back(ak);

        if (k > 0) {
            for (int i = 0; i < dim; ++i)
                w[i] -= beta[k] * Q[k-1][i];
        }
        for (int i = 0; i < dim; ++i)
            w[i] -= ak * Q[k][i];

        // Full reorthogonalisation
        for (int j = 0; j <= k; ++j) {
            cplx proj = cplx_dot(Q[j], w, dim);
            for (int i = 0; i < dim; ++i)
                w[i] -= proj * Q[j][i];
        }

        double bkp1 = std::sqrt(cplx_abs_sq(w, dim));
        beta.push_back(bkp1);

        if (bkp1 < 1e-14) {
            m = k + 1;
            break;
        }

        Q.push_back(std::vector<cplx>(dim));
        for (int i = 0; i < dim; ++i)
            Q[k+1][i] = w[i] / bkp1;

        // Convergence check every 5 iterations
        if (k >= 9 && (k + 1) % 5 == 0) {
            int curr_m = k + 1;
            DenseSymMatrix T(static_cast<std::size_t>(curr_m));
            for (int i = 0; i < curr_m; ++i) {
                T(i, i) = alpha[i];
                if (i > 0) { T(i, i-1) = beta[i]; T(i-1, i) = beta[i]; }
            }
            auto eigsys = jacobi_eigen(T, 50, 1e-12);
            double E0_curr = eigsys.eigenvalues[0];

            if (curr_m >= 15) {
                int prev_m = curr_m - 5;
                DenseSymMatrix Tprev(static_cast<std::size_t>(prev_m));
                for (int i = 0; i < prev_m; ++i) {
                    Tprev(i, i) = alpha[i];
                    if (i > 0) { Tprev(i, i-1) = beta[i]; Tprev(i-1, i) = beta[i]; }
                }
                auto eigsys_prev = jacobi_eigen(Tprev, 50, 1e-12);
                if (std::abs(E0_curr - eigsys_prev.eigenvalues[0]) < 1e-10) {
                    m = curr_m;
                    break;
                }
            }
        }
        m = k + 1;
    }

    // Diagonalise final T_m
    DenseSymMatrix Tm(static_cast<std::size_t>(m));
    for (int i = 0; i < m; ++i) {
        Tm(i, i) = alpha[i];
        if (i > 0) { Tm(i, i-1) = beta[i]; Tm(i-1, i) = beta[i]; }
    }
    auto eigsys = jacobi_eigen(Tm, 50, 1e-12);
    double E0 = eigsys.eigenvalues[0];

    // Reconstruct ground-state eigenvector
    std::vector<cplx> psi0(dim, cplx(0, 0));
    for (int j = 0; j < m; ++j) {
        double y0j = eigsys.eigenvectors[j * m];
        for (int i = 0; i < dim; ++i)
            psi0[i] += y0j * Q[j][i];
    }

    nr = std::sqrt(cplx_abs_sq(psi0, dim));
    if (nr > 1e-30)
        for (auto& z : psi0) z /= nr;

    return {std::move(psi0), dim, E0};
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
// Overlap and FHS curvature
// ──────────────────────────────────────────────────────────────

cplx overlap(const GroundState& a, const GroundState& b) {
    cplx s(0,0);
    for (int i = 0; i < a.dim; ++i) s += std::conj(a.eigenvector[i]) * b.eigenvector[i];
    return s;
}

BerryCurvature fhs_curvature(const GroundState& gs00, const GroundState& gs10,
                              const GroundState& gs11, const GroundState& gs01)
{
    BerryCurvature bc;
    auto U1 = overlap(gs00, gs10);
    auto U2 = overlap(gs10, gs11);
    auto U1star = overlap(gs11, gs01);
    auto U2star = overlap(gs01, gs00);

    bc.absU1 = std::abs(U1);
    bc.absU2 = std::abs(U2star);
    if (bc.absU1 > 1e-30) U1 /= bc.absU1; else U1 = cplx(1,0);
    if (std::abs(U2) > 1e-30) U2 /= std::abs(U2); else U2 = cplx(1,0);
    if (std::abs(U1star) > 1e-30) U1star /= std::abs(U1star); else U1star = cplx(1,0);
    if (bc.absU2 > 1e-30) U2star /= bc.absU2; else U2star = cplx(1,0);

    bc.F12 = std::arg(U1 * U2 * U1star * U2star);
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
    return fhs_curvature(g00, g10, g11, g01);
}

// ──────────────────────────────────────────────────────────────
// Grid computation
// ──────────────────────────────────────────────────────────────

std::vector<std::vector<BerryCurvature>> compute_berry_curvature_grid(
    const Lattice& lattice, double J, const ParamGrid& grid)
{
    int n1 = static_cast<int>(grid.vals1.size()), n2 = static_cast<int>(grid.vals2.size());
    std::vector<std::vector<GroundState>> gs(n1, std::vector<GroundState>(n2));
    for (int i = 0; i < n1; ++i) for (int j = 0; j < n2; ++j)
        gs[i][j] = solve_ground_state(lattice, J, grid.vals1[i], grid.vals2[j]);
    std::vector<std::vector<BerryCurvature>> r(n1-1, std::vector<BerryCurvature>(n2-1));
    for (int i = 0; i < n1-1; ++i) for (int j = 0; j < n2-1; ++j)
        r[i][j] = fhs_curvature(gs[i][j], gs[i+1][j], gs[i+1][j+1], gs[i][j+1]);
    return r;
}

// ──────────────────────────────────────────────────────────────
// ∂θH expectation via ED thermal average (for SSE cross-check)
// ──────────────────────────────────────────────────────────────

double compute_dthetah_ed(const Lattice& lattice, double J, double Omega,
                          double theta, double beta)
{
    int N = static_cast<int>(lattice.N), dim = 1 << N;
    if (dim > 64) throw std::runtime_error("compute_dthetah_ed: dim > 64");

    // Build H = -J Σ ZZ - Omega Σ X (real symmetric TFIM, θ=0)
    DenseSymMatrix H(static_cast<std::size_t>(dim));
    for (int st = 0; st < dim; ++st) {
        for (int bi = 0; bi < static_cast<int>(lattice.Nb); ++bi) {
            int i = static_cast<int>(lattice.bonds[bi].i);
            int j = static_cast<int>(lattice.bonds[bi].j);
            int si = (st >> i) & 1, sj = (st >> j) & 1;
            H(st, st) += -J * (1 - 2*si) * (1 - 2*sj);
        }
        for (int si = 0; si < N; ++si)
            H(st, st ^ (1 << si)) += -Omega;
    }

    auto eigsys = jacobi_eigen(H, 50, 1e-12);

    // Compute thermal expectation of Σ ZZ (per-site, for ∂θH diag)
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
            for (int bi = 0; bi < static_cast<int>(lattice.Nb); ++bi) {
                int i = static_cast<int>(lattice.bonds[bi].i);
                int j = static_cast<int>(lattice.bonds[bi].j);
                int si = (st >> i) & 1, sj = (st >> j) & 1;
                zz_n += psi2 * (1 - 2*si) * (1 - 2*sj);
            }
        }
        sum_ZZ += w * zz_n;
    }

    // ∂θH_diag(θ) = J sin(2θ) × ⟨Σ_{bonds} ZZ⟩ / N  (per-site)
    double zz_exp = sum_ZZ / Z; // thermal expectation of Σ_bonds ZZ
    double dthetah_diag = J * std::sin(2 * theta) * zz_exp / N;

    return dthetah_diag;
}

} // namespace cm
