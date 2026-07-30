#include "../src/lattice.hpp"
#include "../src/berry.hpp"
#include "../src/ed.hpp"
#include <cmath>
#include <iostream>
#include <sstream>
#include <vector>

using namespace cm;
static int failures = 0;
static void check(const std::string& n, bool c, const std::string& d = "") {
    if (!c) { std::cerr << "FAIL: " << n; if (!d.empty()) std::cerr << " — " << d; std::cerr << std::endl; ++failures; }
    else std::cout << "  PASS: " << n << std::endl;
}
static void approx_eq(const std::string& n, double g, double e, double tol = 1e-8) {
    if (std::abs(g - e) < tol) std::cout << "  PASS: " << n << " (" << g << ")" << std::endl;
    else { std::ostringstream o; o << "got=" << g << " expected=" << e; check(n, false, o.str()); }
}

// Test 1: theta=0 energy benchmark against real-symmetric Lanczos in ed.cpp
static void test_theta_zero_energy() {
    std::cout << "--- theta=0 energy benchmark ---" << std::endl;
    for (int N : {4, 6, 8}) {
        auto lat = make_chain(N);
        auto gs_berry = solve_ground_state(lat, 1.0, 1.0, 0.0);
        auto lr = lanczos_ground(lat, 1.0, 1.0, 200, 1e-12);
        double diff = std::abs(gs_berry.E0 - lr.E0);
        std::ostringstream o;
        o << "E0 N=" << N << " match";
        check(o.str(), diff < 1e-10);
        check("complex Lanczos converged N=" + std::to_string(N), gs_berry.converged,
              "residual=" + std::to_string(gs_berry.residual));
        check("complex Lanczos residual N=" + std::to_string(N),
              gs_berry.residual < 2e-9,
              "residual=" + std::to_string(gs_berry.residual));
        std::cout << "  N=" << N << " berry=" << gs_berry.E0
                  << " ed=" << lr.E0 << " diff=" << diff << std::endl;
    }
}

// Test 2: Chain grid convergence — check that F12 changes smoothly with step size
// (not oscillating signs or diverging). Use a point with larger F12 for reliable comparison.
static void test_chain_grid_convergence() {
    std::cout << "--- Chain grid convergence ---" << std::endl;
    auto lat = make_chain(4);
    // Use a point away from zero-field: theta=0.3, Omega=1.0 gives larger F12
    auto coarse = fhs_curvature_single(lat, 1.0, 0.3, 1.0, 0.1, 0.1);
    auto fine = fhs_curvature_single(lat, 1.0, 0.3, 1.0, 0.05, 0.05);

    double rel_diff = 0;
    if (std::abs(coarse.F12) > 1e-12)
        rel_diff = std::abs(coarse.F12 - fine.F12) / std::abs(coarse.F12);
    else
        rel_diff = std::abs(coarse.F12 - fine.F12);

    std::cout << "  coarse F12=" << coarse.F12
              << " fine F12=" << fine.F12
              << " rel_diff=" << rel_diff << std::endl;
    check("grid convergence", rel_diff < 0.12,
          "relative change=" + std::to_string(rel_diff));
}

// Test 3: Finite-size convergence — F12/N bounded as N increases
static void test_finite_size_convergence() {
    std::cout << "--- Finite-size convergence (θ=0.3, Ω=2.0, dθ=0.05, dΩ=0.05) ---" << std::endl;
    std::vector<double> densities;
    for (int N : {4, 6, 8}) {
        auto lat = make_chain(N);
        auto bc = fhs_curvature_single(lat, 1.0, 0.3, 2.0, 0.05, 0.05);
        double d = bc.F12 / N;
        densities.push_back(d);
        std::cout << "  N=" << N << " F12/N=" << d
                  << " absU1=" << bc.absU1 << " absU2=" << bc.absU2 << std::endl;
    }
    // F12/N should be bounded (no exponential growth)
    bool bounded = true;
    for (size_t i = 1; i < densities.size(); ++i) {
        if (std::abs(densities[i]) > 1000) bounded = false;
    }
    check("F12/N bounded", bounded);
    check("F12/N finite for N=8", std::isfinite(densities[2]));
}

// Test 4: 2D square lattice
static void test_2d_square() {
    std::cout << "--- 2D square lattice ---" << std::endl;

    // L=2 (2x2, N=4, dim=16) — quick
    {
        auto lat = make_square(2, 2);
        auto bc = fhs_curvature_single(lat, 1.0, 0.0, 2.0, 0.1, 0.1);
        check("2x2 F12 finite", std::isfinite(bc.F12));
        std::cout << "  L=2 F12=" << bc.F12 << " F12/N=" << bc.F12/4
                  << " absU1=" << bc.absU1 << " absU2=" << bc.absU2 << std::endl;
    }

    // L=3 (3x3, N=9, dim=512) — slow, minimal check
    {
        std::cout << "  Computing L=3 3x3 (N=9, dim=512; this may take a moment)..." << std::endl;
        auto lat = make_square(3, 3);
        auto bc = fhs_curvature_single(lat, 1.0, 0.0, 2.0, 0.1, 0.1);
        check("3x3 F12 finite", std::isfinite(bc.F12));
        std::cout << "  L=3 F12=" << bc.F12 << " F12/N=" << bc.F12/9
                  << " absU1=" << bc.absU1 << " absU2=" << bc.absU2 << std::endl;
    }
}

// Test 5: N=10 chain convergence (largest 1D system)
static void test_n10_chain() {
    std::cout << "--- 1D N=10 chain (dim=1024) ---" << std::endl;
    auto lat = make_chain(10);
    auto bc = fhs_curvature_single(lat, 1.0, 0.0, 1.0, 0.1, 0.1);
    check("N=10 F12 finite", bc.valid && std::isfinite(bc.F12));
    const auto ground_state = solve_ground_state(lat, 1.0, 1.0, 0.0);
    check("N=10 ground state converged", ground_state.converged,
          "residual=" + std::to_string(ground_state.residual));
    std::cout << "  N=10 F12=" << bc.F12 << " F12/N=" << bc.F12/10 << std::endl;
}

// Test 6: Gauge invariance still holds with new solver
static void test_gauge_stage1() {
    std::cout << "--- Gauge invariance (Stage 1) ---" << std::endl;
    auto lat = make_chain(4);
    auto g00 = solve_ground_state(lat, 1.0, 2.0, 0.1);
    auto g10 = solve_ground_state(lat, 1.0, 2.0, 0.2);
    auto g11 = solve_ground_state(lat, 1.0, 2.1, 0.2);
    auto g01 = solve_ground_state(lat, 1.0, 2.1, 0.1);
    auto bc1 = fhs_curvature(g00, g10, g11, g01, 0.1, 0.1);
    for (auto& z : g00.eigenvector) z *= std::polar(1.0, 1.5);
    for (auto& z : g10.eigenvector) z *= std::polar(1.0, -0.3);
    for (auto& z : g11.eigenvector) z *= std::polar(1.0, 2.7);
    for (auto& z : g01.eigenvector) z *= std::polar(1.0, -1.8);
    auto bc2 = fhs_curvature(g00, g10, g11, g01, 0.1, 0.1);
    approx_eq("F12 gauge invariant (N=4)", bc1.F12, bc2.F12);
}

int main() {
    try {
        test_theta_zero_energy();
        test_chain_grid_convergence();
        test_finite_size_convergence();
        test_2d_square();
        test_n10_chain();
        test_gauge_stage1();
    } catch (const std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        ++failures;
    }

    std::cout << std::endl;
    if (!failures)
        std::cout << "All Stage 1 Berry-phase tests passed." << std::endl;
    else
        std::cerr << failures << " FAILED." << std::endl;
    return failures ? 1 : 0;
}
