#include "berry.hpp"
#include <cmath>
#include <stdexcept>

namespace cm {

using cplx = std::complex<double>;

static inline int sv(int st, int site) { return (st >> site) & 1; }

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

// Krylov-subspace (Lanczos-like) for ground state
static cplx cplx_dot(const std::vector<cplx>& x, const std::vector<cplx>& y, int n) {
    cplx s(0, 0);
    for (int i = 0; i < n; ++i) s += std::conj(x[i]) * y[i];
    return s;
}

GroundState solve_ground_state(const Lattice& lattice, double J, double Omega, double theta)
{
    int N = static_cast<int>(lattice.N), dim = 1 << N;
    if (dim > 256) throw std::runtime_error("dim too large (>256)");

    auto H = build_kolodrubetz_hamiltonian(lattice, J, Omega, theta);
    int K = std::min(16, dim);
    std::vector<std::vector<cplx>> V(K, std::vector<cplx>(dim));

    // random init
    for (int i = 0; i < dim; ++i) V[0][i] = cplx((i*12345+67890)%1000/1000.0, (i*54321+9876)%1000/1000.0);
    double nr = 0;
    for (auto& z : V[0]) nr += std::norm(z);
    nr = std::sqrt(nr);
    for (auto& z : V[0]) z /= nr;

    std::vector<cplx> tmp(dim);
    for (int k = 1; k < K; ++k) {
        for (int i = 0; i < dim; ++i) { tmp[i] = cplx(0,0); for (int j = 0; j < dim; ++j) tmp[i] += H[i*dim + j] * V[k-1][j]; }
        for (int j = 0; j < k; ++j) { cplx a = cplx_dot(V[j], tmp, dim); for (int i = 0; i < dim; ++i) tmp[i] -= a * V[j][i]; }
        double n2 = 0; for (auto& z : tmp) n2 += std::norm(z);
        if (n2 < 1e-30) break;
        n2 = std::sqrt(n2);
        for (int i = 0; i < dim; ++i) V[k][i] = tmp[i] / n2;
    }

    // projected matrix T = V† H V
    std::vector<cplx> T(K * K, cplx(0,0));
    for (int a = 0; a < K; ++a) {
        for (int i = 0; i < dim; ++i) { tmp[i] = cplx(0,0); for (int j = 0; j < dim; ++j) tmp[i] += H[i*dim + j] * V[a][j]; }
        for (int b = 0; b < K; ++b) T[a*K + b] = cplx_dot(V[b], tmp, dim);
    }

    // power iteration on T for smallest eigenvalue
    std::vector<cplx> x(K, cplx(0,0)); for (int i = 0; i < K; ++i) x[i] = cplx(1.0/K, 0);
    for (int iter = 0; iter < 100; ++iter) {
        std::vector<cplx> y(K, cplx(0,0));
        for (int a = 0; a < K; ++a) for (int b = 0; b < K; ++b) y[a] += T[a*K + b] * x[b];
        double ny = 0; for (auto& z : y) ny += std::norm(z);
        if (ny < 1e-30) break;
        ny = std::sqrt(ny);
        for (int a = 0; a < K; ++a) x[a] = y[a] / ny;
    }
    std::vector<cplx> Hx(K, cplx(0,0));
    for (int a = 0; a < K; ++a) for (int b = 0; b < K; ++b) Hx[a] += T[a*K + b] * x[b];
    cplx E0p = cplx_dot(x, Hx, K);

    std::vector<cplx> psi0(dim, cplx(0,0));
    for (int a = 0; a < K; ++a) for (int i = 0; i < dim; ++i) psi0[i] += x[a] * V[a][i];
    double nf = 0; for (auto& z : psi0) nf += std::norm(z);
    nf = std::sqrt(nf);
    for (auto& z : psi0) z /= nf;

    return {std::move(psi0), dim, std::real(E0p)};
}

cplx overlap(const GroundState& a, const GroundState& b) {
    cplx s(0,0);
    for (int i = 0; i < a.dim; ++i) s += std::conj(a.eigenvector[i]) * b.eigenvector[i];
    return s;
}

BerryCurvature fhs_curvature(const GroundState& gs00, const GroundState& gs10,
                              const GroundState& gs11, const GroundState& gs01)
{
    BerryCurvature bc;
    // FHS formula: F₁₂ = arg[U₁ U₂ U₁^* U₂^*]
    // U₁ = ⟨ψ₀₀|ψ₁₀⟩ / |...|,  U₂ = ⟨ψ₁₀|ψ₁₁⟩ / |...|
    // U₁^* = ⟨ψ₁₁|ψ₀₁⟩ / |...|, U₂^* = ⟨ψ₀₁|ψ₀₀⟩ / |...|
    auto U1 = overlap(gs00, gs10);
    auto U2 = overlap(gs10, gs11);
    auto U1star = overlap(gs11, gs01);  // ⟨ψ₁₁|ψ₀₁⟩ = conj(⟨ψ₀₁|ψ₁₁⟩)
    auto U2star = overlap(gs01, gs00);  // ⟨ψ₀₁|ψ₀₀⟩ = conj(⟨ψ₀₀|ψ₀₁⟩)

    bc.absU1 = std::abs(U1);
    bc.absU2 = std::abs(U2star);
    if (bc.absU1 > 1e-30) U1 /= bc.absU1; else U1 = cplx(1,0);
    if (std::abs(U2) > 1e-30) U2 /= std::abs(U2); else U2 = cplx(1,0);
    if (std::abs(U1star) > 1e-30) U1star /= std::abs(U1star); else U1star = cplx(1,0);
    if (bc.absU2 > 1e-30) U2star /= bc.absU2; else U2star = cplx(1,0);

    bc.F12 = std::arg(U1 * U2 * U1star * U2star);
    return bc;
}

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

} // namespace cm
