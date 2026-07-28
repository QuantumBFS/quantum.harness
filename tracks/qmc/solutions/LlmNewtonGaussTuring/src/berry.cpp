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
    const int dim = checked_dimension(lattice, 1024, "solve_ground_state_lanczos");
    if (m_max <= 0)
        throw std::invalid_argument("solve_ground_state_lanczos: m_max must be positive");

    auto Hmat = build_kolodrubetz_hamiltonian(lattice, J, Omega, theta);

    // Adaptive m_max for small dim
    if (m_max > dim) m_max = dim;

    std::vector<std::vector<cplx>> Q;  // Lanczos vectors
    Q.reserve(m_max + 1);

    // Deterministic random initial vector
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

    std::vector<double> alpha;
    std::vector<double> beta;
    alpha.reserve(m_max);
    beta.reserve(m_max);
    beta.push_back(0);

    std::vector<cplx> w(dim);
    int m = 0;
    bool converged = false;

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

        // Two-pass full reorthogonalisation keeps the Krylov basis stable near
        // small gaps and makes the Ritz residual meaningful.
        for (int pass = 0; pass < 2; ++pass)
            for (int j = 0; j <= k; ++j) {
                cplx proj = cplx_dot(Q[j], w, dim);
                for (int i = 0; i < dim; ++i) w[i] -= proj * Q[j][i];
            }

        double bkp1 = std::sqrt(cplx_abs_sq(w, dim));
        beta.push_back(bkp1);

        m = k + 1;
        const bool breakdown = bkp1 <= 1e-14;
        const bool check_now = m >= 2 && (m % 5 == 0 || breakdown || m == m_max);
        if (check_now) {
            int curr_m = m;
            DenseSymMatrix T(static_cast<std::size_t>(curr_m));
            for (int i = 0; i < curr_m; ++i) {
                T(i, i) = alpha[i];
                if (i > 0) { T(i, i-1) = beta[i]; T(i-1, i) = beta[i]; }
            }
            auto eigsys = jacobi_eigen(T, 50, 1e-12);
            const double last_component = eigsys.eigenvectors[(curr_m - 1) * curr_m];
            const double residual = bkp1 * std::abs(last_component);
            converged = residual <= 1e-11 * (1.0 + std::abs(eigsys.eigenvalues[0]));
        }
        if (converged || breakdown) break;

        Q.push_back(std::vector<cplx>(dim));
        for (int i = 0; i < dim; ++i) Q[k+1][i] = w[i] / bkp1;
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

    std::vector<cplx> Hpsi(dim);
    cplx_matvec(Hmat.data(), dim, psi0.data(), Hpsi.data());
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
    if (a.dim != b.dim || a.dim <= 0
        || a.eigenvector.size() != static_cast<std::size_t>(a.dim)
        || b.eigenvector.size() != static_cast<std::size_t>(b.dim))
        throw std::invalid_argument("overlap: incompatible ground-state dimensions");
    cplx s(0,0);
    for (int i = 0; i < a.dim; ++i) s += std::conj(a.eigenvector[i]) * b.eigenvector[i];
    return s;
}

BerryCurvature fhs_curvature(const GroundState& gs00, const GroundState& gs10,
                              const GroundState& gs11, const GroundState& gs01,
                              double dlambda1, double dlambda2)
{
    const double area = dlambda1 * dlambda2;
    if (!std::isfinite(area) || area == 0.0)
        throw std::invalid_argument("fhs_curvature: plaquette steps must have non-zero finite area");

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
            for (int bi = 0; bi < static_cast<int>(lattice.bonds.size()); ++bi) {
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
