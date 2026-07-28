#include "../src/lattice.hpp"
#include "../src/ed.hpp"
#include "../src/sse.hpp"
#include <cmath>
#include <iostream>
#include <sstream>
#include <string>

using namespace cm;

static int failures = 0;

static void check(const std::string& name, bool cond, const std::string& detail = "") {
    if (!cond) {
        std::cerr << "FAIL: " << name;
        if (!detail.empty()) std::cerr << " — " << detail;
        std::cerr << std::endl;
        ++failures;
    } else std::cout << "  PASS: " << name << std::endl;
}

static void approx_eq(const std::string& name, double got, double expected,
                      double tol_rel = 0.05) {
    double tol = tol_rel * (std::abs(expected) + 0.03);
    double diff = std::abs(got - expected);
    if (diff < tol)
        std::cout << "  PASS: " << name << " (got=" << got << " expected=" << expected << ")" << std::endl;
    else {
        std::ostringstream oss;
        oss << "got=" << got << " expected=" << expected << " diff=" << diff << " tol=" << tol;
        check(name, false, oss.str());
    }
}

// ============================================================
// J=0 is a known limitation of the line update (no BOND ops
// to walk through — self-loop means no net CONST↔OFFDIAG
// toggle).  J>0, h>0 are the physically relevant cases.
// ============================================================

// ============================================================
// Test 1: near-classical Ising (very small h)
// ============================================================
static void test_near_classical() {
    std::cout << "--- Near-classical (h≪J) ---" << std::endl;
    int N = 8;
    auto lat = make_chain(N);
    SSEParams p; p.n_thermal = 5000; p.n_bins = 300; p.sweeps_per_bin = 20; p.seed = 456;

    for (double h : {0.01, 0.1}) {
        SSE sse(lat, 1.0, h, 5.0, p);
        auto res = sse.run();
        check("sign h=" + std::to_string(h), std::abs(res.sign_avg - 1.0) < 1e-12);
        std::cout << "  h=" << h << " E/N=" << res.energy << " m2=" << res.m2
                  << " Q=" << res.Q << " n/N=" << res.n_op_avg << std::endl;
        // At small h, should approach classical Ising (E/N → -J, m2 → 1)
        check("E near -J", res.energy < -0.7);
    }
}

// ============================================================
// Test 2: SSE vs ED for small systems (J>0, h>0)
// ============================================================
static void test_sse_vs_ed() {
    std::cout << "--- SSE vs ED ---" << std::endl;
    for (int N : {4, 6}) {
        double J = 1.0, h = 0.75, beta = 4.0;
        auto lat = make_chain(N);
        auto ed = compute_thermal_obs(lat, J, h, beta);

        SSEParams p; p.n_thermal = 5000; p.n_bins = 500; p.sweeps_per_bin = 30; p.seed = 789 + N;
        SSE sse(lat, J, h, beta, p);
        auto res = sse.run();

        check("sign N=" + std::to_string(N), std::abs(res.sign_avg - 1.0) < 1e-12);
        approx_eq("E N=" + std::to_string(N), res.energy, ed.E, 0.05);
        approx_eq("m2 N=" + std::to_string(N), res.m2, ed.m2, 0.25);
        approx_eq("Q N=" + std::to_string(N),  res.Q, ed.Q, 0.20);

        std::cout << "  N=" << N << " E(SSE)=" << res.energy << " E(ED)=" << ed.E
                  << " m2(SSE)=" << res.m2 << " m2(ED)=" << ed.m2
                  << " n/N=" << res.n_op_avg << std::endl;
    }
}

// ============================================================
// Test 3: Sweep convergence
// ============================================================
static void test_sweep_convergence() {
    std::cout << "--- Sweep convergence ---" << std::endl;
    auto lat = make_chain(6);
    double J = 1.0, h = 0.5, beta = 3.0;
    auto ed = compute_thermal_obs(lat, J, h, beta);

    for (int n_thermal : {500, 2000, 5000}) {
        SSEParams p; p.n_thermal = n_thermal; p.n_bins = 300; p.sweeps_per_bin = 20; p.seed = 999;
        SSE sse(lat, J, h, beta, p);
        auto res = sse.run();
        double diff = std::abs(res.energy - ed.E);
        std::cout << "  thermal=" << n_thermal << " E=" << res.energy
                  << " diff=" << diff << " n/N=" << res.n_op_avg << std::endl;
        if (n_thermal >= 2000)
            approx_eq("converge thermal=" + std::to_string(n_thermal),
                      res.energy, ed.E, 0.08);
    }
}

// ============================================================
// Test 4: 1D critical chain (h=J=1) energy approach
// ============================================================
static void test_1d_critical_chain() {
    std::cout << "--- 1D critical chain (h=J=1) ---" << std::endl;
    const double exact_E0_N = -4.0 / M_PI;

    for (int N : {4, 6, 8, 10}) {
        auto lat = make_chain(N);
        SSEParams p; p.n_thermal = 3000; p.n_bins = 300; p.sweeps_per_bin = 30; p.seed = 100 + N;
        SSE sse(lat, 1.0, 1.0, 4.0, p);
        auto res = sse.run();

        std::cout << "  N=" << N << " E/N=" << res.energy
                  << " (thermo ≈ " << exact_E0_N << "), n/N=" << res.n_op_avg
                  << ", m2=" << res.m2 << std::endl;
        check("sign N=" + std::to_string(N), std::abs(res.sign_avg - 1.0) < 1e-12);
    }
}

int main() {
    test_near_classical();
    test_sse_vs_ed();
    test_sweep_convergence();
    test_1d_critical_chain();

    std::cout << std::endl;
    if (failures == 0)
        std::cout << "All SSE tests passed." << std::endl;
    else
        std::cerr << failures << " test(s) FAILED." << std::endl;
    return failures ? 1 : 0;
}
