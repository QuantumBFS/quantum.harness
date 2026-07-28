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
    if (!cond) { std::cerr << "FAIL: " << name; if (!detail.empty()) std::cerr << " — " << detail; std::cerr << std::endl; ++failures; }
    else std::cout << "  PASS: " << name << std::endl;
}
static void approx_eq(const std::string& name, double got, double expected, double tol_rel = 0.05) {
    double tol = tol_rel * (std::abs(expected) + 0.03);
    if (std::abs(got - expected) < tol)
        std::cout << "  PASS: " << name << " (got=" << got << " expected=" << expected << ")" << std::endl;
    else { std::ostringstream oss; oss << "got=" << got << " expected=" << expected; check(name, false, oss.str()); }
}

// Test 1: near-classical (moderate h)
static void test_near_classical() {
    std::cout << "--- Near-classical ---" << std::endl;
    auto lat = make_chain(8);
    SSEParams p; p.n_thermal = 5000; p.n_bins = 300; p.sweeps_per_bin = 20; p.seed = 456;
    SSE sse(lat, 1.0, 0.1, 5.0, p);
    auto res = sse.run();
    check("sign", std::abs(res.sign_avg - 1.0) < 1e-12);
    check("E near -J", res.energy < -0.7, "got=" + std::to_string(res.energy));
    std::cout << "  E/N=" << res.energy << " m2=" << res.m2 << " n/N=" << res.n_op_avg << std::endl;
}

// Test 2: SSE vs ED — energy (primary observable)
static void test_sse_vs_ed() {
    std::cout << "--- SSE vs ED (energy) ---" << std::endl;
    for (int N : {4, 6}) {
        double J = 1.0, h = 0.75, beta = 4.0;
        auto lat = make_chain(N);
        auto ed = compute_thermal_obs(lat, J, h, beta);
        SSEParams p; p.n_thermal = 5000; p.n_bins = 500; p.sweeps_per_bin = 30; p.seed = 789 + N;
        SSE sse(lat, J, h, beta, p);
        auto res = sse.run();
        check("sign N=" + std::to_string(N), std::abs(res.sign_avg - 1.0) < 1e-12);
        approx_eq("E N=" + std::to_string(N), res.energy, ed.E, 0.05);
        std::cout << "  N=" << N << " E(SSE)=" << res.energy << " E(ED)=" << ed.E
                  << " m2=" << res.m2 << " n/N=" << res.n_op_avg << std::endl;
    }
}

// Test 3: convergence with sweeps
static void test_sweep_convergence() {
    std::cout << "--- Sweep convergence ---" << std::endl;
    auto lat = make_chain(6);
    double J = 1.0, h = 0.5, beta = 3.0;
    auto ed = compute_thermal_obs(lat, J, h, beta);
    for (int nt : {500, 2000, 5000}) {
        SSEParams p; p.n_thermal = nt; p.n_bins = 300; p.sweeps_per_bin = 20; p.seed = 999;
        SSE sse(lat, J, h, beta, p);
        auto res = sse.run();
        std::cout << "  thermal=" << nt << " E=" << res.energy << " diff=" << std::abs(res.energy - ed.E) << " n/N=" << res.n_op_avg << std::endl;
        if (nt >= 2000) approx_eq("converge", res.energy, ed.E, 0.08);
    }
}

// Test 4: 1D critical chain
static void test_1d_critical() {
    std::cout << "--- 1D critical (h=J=1) ---" << std::endl;
    const double E0 = -4.0 / M_PI;
    for (int N : {4, 6, 8, 10}) {
        auto lat = make_chain(N);
        SSEParams p; p.n_thermal = 3000; p.n_bins = 300; p.sweeps_per_bin = 30; p.seed = 100 + N;
        SSE sse(lat, 1.0, 1.0, 4.0, p);
        auto res = sse.run();
        std::cout << "  N=" << N << " E/N=" << res.energy << " thermo=" << E0 << " n/N=" << res.n_op_avg << std::endl;
        check("sign", std::abs(res.sign_avg - 1.0) < 1e-12);
    }
}

int main() {
    test_near_classical();
    test_sse_vs_ed();
    test_sweep_convergence();
    test_1d_critical();
    std::cout << std::endl;
    if (failures == 0) std::cout << "All SSE tests passed." << std::endl;
    else std::cerr << failures << " test(s) FAILED." << std::endl;
    return failures ? 1 : 0;
}
