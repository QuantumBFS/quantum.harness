#include "../src/lattice.hpp"
#include "../src/berry.hpp"
#include "../src/sse.hpp"
#include <cmath>
#include <complex>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>

using namespace cm;

static int failures = 0;

static void check(const std::string& name, bool cond, const std::string& diag = "") {
    if (!cond) {
        std::cerr << "FAIL: " << name;
        if (!diag.empty()) std::cerr << " | " << diag;
        std::cerr << std::endl;
        ++failures;
    } else {
        std::cout << "  PASS: " << name << std::endl;
    }
}

static void approx_eq(const std::string& name, double got, double expected,
                       double tol_rel = 0.05, double floor = 0.01) {
    double tol = tol_rel * (std::abs(expected) + floor);
    if (std::abs(got - expected) < tol)
        std::cout << "  PASS: " << name << " (got=" << got << " expected="
                  << expected << " tol=" << tol << ")" << std::endl;
    else {
        std::ostringstream oss;
        oss << "got=" << got << " expected=" << expected << " tol=" << tol;
        check(name, false, oss.str());
    }
}

// ============================================================
// Test: ∂θH_diag vanishes at θ=0 (symmetry check)
// ============================================================
static void test_dthetah_zero_at_theta_zero() {
    std::cout << "--- ∂θH = 0 at θ=0 (time-reversal symmetry) ---" << std::endl;
    for (int N : {4, 6}) {
        auto lat = make_chain(N);
        double J = 1.0, Omega = 1.0;

        // ED: expect exactly zero from the diagonal formula
        double ed_val = compute_dthetah_diagonal_ed(lat, J, Omega, 0.0, 8.0);
        check("ED dthetah(θ=0) N=" + std::to_string(N),
              std::abs(ed_val) < 1e-12,
              "got=" + std::to_string(ed_val));

        // SSE: should be zero within statistical error
        SSEParams p;
        p.n_thermal = 2000; p.n_bins = 1000; p.sweeps_per_bin = 2;
        p.seed = 300 + N;
        p.measure_rotated_bond_diagonal = true; p.rotation_theta = 0.0;
        SSE sse(lat, J, Omega, 8.0, p);
        auto res = sse.run();
        check("SSE dthetah(θ=0) ≈ 0 N=" + std::to_string(N),
              std::abs(res.dthetah_diagonal) < 0.05,
              "got=" + std::to_string(res.dthetah_diagonal));
        std::cout << "  N=" << N << " dthetah(SSE)=" << res.dthetah_diagonal
                  << " dthetah(ED)=" << ed_val << std::endl;
    }
}

// ============================================================
// Test: ∂θH_diag at finite θ — SSE vs ED
// ============================================================
static void test_dthetah_sse_vs_ed() {
    std::cout << "--- ∂θH_diag SSE vs ED ---" << std::endl;
    const double theta = M_PI / 8.0; // sin(2θ) = sin(π/4) = √2/2 ≈ 0.7071

    struct Case {
        int N;
        double J;
        double Omega;
        double beta;
    };

    for (auto c : {Case{4, 1.0, 1.0, 4.0},
                   Case{4, 1.0, 1.0, 8.0},
                   Case{6, 1.0, 1.0, 4.0},
                   Case{6, 1.0, 1.0, 8.0}}) {
        auto lat = make_chain(c.N);
        double ed_val = compute_dthetah_diagonal_ed(lat, c.J, c.Omega, theta, c.beta);

        SSEParams p;
        p.n_thermal = 3000; p.n_bins = 6000; p.sweeps_per_bin = 2;
        p.seed = 4000 + 100 * c.N + static_cast<int>(c.beta);
        p.measure_rotated_bond_diagonal = true; p.rotation_theta = theta;
        SSE sse(lat, c.J, c.Omega, c.beta, p);
        auto res = sse.run();

        std::ostringstream tag;
        tag << " N=" << c.N << " β=" << c.beta;
        std::string t = tag.str();

        check("sign" + t, std::abs(res.sign_avg - 1.0) < 1e-12);
        check("nonzero ED" + t, std::abs(ed_val) > 1e-8,
              "ED expects non-zero at θ≠0, got=" + std::to_string(ed_val));

        // At large β the statistical error shrinks; 5% tolerant for β=4,
        // tighter for β=8 (better sampling quality).
        double tol = (c.beta > 6.0) ? 0.05 : 0.08;
        approx_eq("dthetah" + t, res.dthetah_diagonal, ed_val, tol);

        std::cout << "  N=" << c.N << " β=" << c.beta
                  << " θ=π/8 dthetah(SSE)=" << res.dthetah_diagonal
                  << " dthetah(ED)=" << ed_val << std::endl;
    }
}

// ============================================================
// Test: ∂θH_diag at varying θ — consistency
// ============================================================
static void test_dthetah_theta_scan() {
    std::cout << "--- ∂θH_diag θ-dependence (ED) ---" << std::endl;
    auto lat = make_chain(4);
    double J = 1.0, Omega = 1.0, beta = 8.0;

    // sin(2θ) peaks at θ=π/4, is symmetric, and vanishes at 0,π/2.
    double v0  = compute_dthetah_diagonal_ed(lat, J, Omega, 0.0, beta);
    double v1  = compute_dthetah_diagonal_ed(lat, J, Omega, M_PI / 8.0, beta);
    double v2  = compute_dthetah_diagonal_ed(lat, J, Omega, M_PI / 4.0, beta);
    double v3  = compute_dthetah_diagonal_ed(lat, J, Omega, M_PI / 2.0, beta);

    check("θ=0 vanishes", std::abs(v0) < 1e-12);
    check("θ=π/2 vanishes", std::abs(v3) < 1e-12);
    check("0 < θ=π/8 < θ=π/4", std::abs(v1) > 0 && std::abs(v2) > std::abs(v1),
          "v1=" + std::to_string(v1) + " v2=" + std::to_string(v2));
    check("dthetah(π/8) / dthetah(π/4) ≈ sin(π/4)/sin(π/2) = 0.707",
          std::abs(std::abs(v1 / v2) - M_SQRT1_2) < 1e-10,
          "ratio=" + std::to_string(std::abs(v1 / v2)));

    std::cout << "  θ=0:       " << v0 << std::endl;
    std::cout << "  θ=π/8:     " << v1 << std::endl;
    std::cout << "  θ=π/4:     " << v2 << std::endl;
    std::cout << "  θ=π/2:     " << v3 << std::endl;
}

// ============================================================
// Test: ∂θH_diag sign from bond expectation
// ============================================================
static void test_dthetah_bond_correlation() {
    std::cout << "--- ∂θH bond correlation check ---" << std::endl;
    auto lat = make_chain(4);
    double J = 1.0, Omega = 1.0, beta = 8.0, theta = M_PI / 8.0;

    // In the ferromagnetic ground state, all spins tend to align,
    // so <σ^z_i σ^z_j> > 0 for each bond.  ∂θH_diag ∝ sin(2θ)>0 at
    // θ∈(0,π/2), so dthetah should be positive.
    double ed_val = compute_dthetah_diagonal_ed(lat, J, Omega, theta, beta);
    check("dthetah > 0 in FM phase", ed_val > 0.0,
          "got=" + std::to_string(ed_val));

    // Near the paramagnetic phase (Omega >> J), <ZZ> → 0 and dthetah → 0.
    double ed_para = compute_dthetah_diagonal_ed(lat, 1.0, 5.0, theta, beta);
    check("dthetah → 0 for large Omega",
          std::abs(ed_para) < std::abs(ed_val) * 0.5,
          "FM=" + std::to_string(ed_val) + " PM=" + std::to_string(ed_para));
    std::cout << "  FM (Ω=1):  " << ed_val
              << "  PM (Ω=5):  " << ed_para << std::endl;
}

// The diagonal ZZ term is only one basis component of dH/dtheta.  For the
// unitarily rotated Hamiltonian the complete equilibrium expectation is zero
// at every theta; the off-diagonal ZY/YZ/YY terms cancel the diagonal piece.
static void test_full_equilibrium_derivative_zero() {
    std::cout << "--- full equilibrium dH/dtheta ---" << std::endl;
    const auto lat = make_chain(4);
    const double J = 1.0;
    const double Omega = 1.4;
    const double theta = 0.37;
    const double step = 1e-6;
    const auto ground = solve_ground_state(lat, J, Omega, theta);
    const auto plus = build_kolodrubetz_hamiltonian(lat, J, Omega, theta + step);
    const auto minus = build_kolodrubetz_hamiltonian(lat, J, Omega, theta - step);

    std::complex<double> expectation(0.0, 0.0);
    for (int row = 0; row < ground.dim; ++row)
        for (int column = 0; column < ground.dim; ++column)
            expectation += std::conj(ground.eigenvector[row])
                         * (plus[row * ground.dim + column]
                            - minus[row * ground.dim + column])
                         * ground.eigenvector[column] / (2.0 * step);

    const double diagonal = compute_dthetah_diagonal_ed(
        lat, J, Omega, theta, 20.0);
    check("diagonal component is non-zero", std::abs(diagonal) > 1e-3,
          "value=" + std::to_string(diagonal));
    check("complete equilibrium expectation vanishes",
          std::abs(expectation) < 2e-8,
          "value=" + std::to_string(expectation.real())
          + "+i" + std::to_string(expectation.imag()));
}

static void test_diagnostic_input_guards() {
    bool rejected = false;
    try {
        (void)compute_dthetah_diagonal_ed(
            make_chain(4), 1.0, 1.0,
            std::numeric_limits<double>::quiet_NaN(), 4.0);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    check("non-finite diagnostic angle rejected by ED", rejected);
}

int main() {
    test_diagnostic_input_guards();
    test_dthetah_zero_at_theta_zero();
    test_dthetah_sse_vs_ed();
    test_dthetah_theta_scan();
    test_dthetah_bond_correlation();
    test_full_equilibrium_derivative_zero();

    std::cout << std::endl;
    if (failures == 0) {
        std::cout << "All ∂θH tests passed." << std::endl;
        return 0;
    } else {
        std::cerr << failures << " test(s) FAILED." << std::endl;
        return 1;
    }
}
