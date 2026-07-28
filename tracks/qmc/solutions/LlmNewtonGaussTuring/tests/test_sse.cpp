#include "../src/lattice.hpp"
#include "../src/ed.hpp"
#include "../src/sse.hpp"
#include <cmath>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace cm;

static int failures = 0;
static void check(const std::string& name, bool cond, const std::string& detail = "") {
    if (!cond) { std::cerr << "FAIL: " << name; if (!detail.empty()) std::cerr << " — " << detail; std::cerr << std::endl; ++failures; }
    else std::cout << "  PASS: " << name << std::endl;
}
static void approx_eq(const std::string& name, double got, double expected, double tol_rel = 0.05, double floor = 0.03) {
    double tol = tol_rel * (std::abs(expected) + floor);
    if (std::abs(got - expected) < tol)
        std::cout << "  PASS: " << name << " (got=" << got << " expected=" << expected << ")" << std::endl;
    else { std::ostringstream oss; oss << "got=" << got << " expected=" << expected << " tol=" << tol; check(name, false, oss.str()); }
}

// J=0: independent spins in a transverse field.  Stage 2 flagged this as a
// "known limitation"; the cluster update resolves it.
//   E/N = -h tanh(beta h),   <m^2> = 1/N.
static void test_j0_limit() {
    std::cout << "--- J=0 independent spins ---" << std::endl;
    int N = 6; double h = 1.0, beta = 2.0;
    auto lat = make_chain(N);
    SSEParams p; p.n_thermal = 4000; p.n_bins = 6000; p.sweeps_per_bin = 2; p.seed = 20240728;
    SSE sse(lat, 0.0, h, beta, p);
    auto res = sse.run();
    approx_eq("E/N = -h tanh(bh)", res.energy, -h * std::tanh(beta * h), 0.05);
    approx_eq("m2 = 1/N", res.m2, 1.0 / N, 0.08);
    std::cout << "  E/N=" << res.energy << " m2=" << res.m2 << " n/N=" << res.n_op_avg << std::endl;
}

// For independent spins, the single-world-line moments are
// mu2=tanh(a)/a and mu4=3(a-tanh(a))/a^3, a=beta*h.  Independence then gives
// <mbar^2>=mu2/N and <mbar^4>=[mu4+3(N-1)mu2^2]/N^3.
static void test_j0_spacetime_moment() {
    std::cout << "--- J=0 space-time magnetisation ---" << std::endl;
    int N = 4; double h = 1.0, beta = 2.0;
    auto lat = make_chain(N);
    SSEParams p; p.n_thermal = 4000; p.n_bins = 8000; p.sweeps_per_bin = 2;
    p.seed = 20260729; p.stage4_estimators = true;
    SSE sse(lat, 0.0, h, beta, p);
    auto res = sse.run();
    const double a = beta * h;
    const double mu2 = std::tanh(a) / a;
    const double mu4 = 3.0 * (a - std::tanh(a)) / (a * a * a);
    const double expected_m2 = mu2 / N;
    const double expected_m4 = (mu4 + 3.0 * (N - 1) * mu2 * mu2)
                             / (N * N * N);
    approx_eq("spacetime m2", res.spacetime_m2, expected_m2, 0.06, 0.0);
    approx_eq("spacetime m4", res.spacetime_m4, expected_m4, 0.08, 0.0);
    approx_eq("spacetime Binder ratio", res.spacetime_Q,
              expected_m2 * expected_m2 / expected_m4, 0.10, 0.0);
}

// Near-classical ordered phase (h << J): the previously-broken observable.
// Stage 2 gave m2 ~ 0.036; the correct value is close to 1.
static void test_near_classical() {
    std::cout << "--- Near-classical ordered (h=0.1J) ---" << std::endl;
    auto lat = make_chain(8);
    SSEParams p; p.n_thermal = 5000; p.n_bins = 4000; p.sweeps_per_bin = 3; p.seed = 456;
    SSE sse(lat, 1.0, 0.1, 5.0, p);
    auto res = sse.run();
    check("sign", std::abs(res.sign_avg - 1.0) < 1e-12);
    check("E near -J", res.energy < -0.9, "got=" + std::to_string(res.energy));
    check("m2 ordered (>0.9)", res.m2 > 0.9, "got=" + std::to_string(res.m2));
    std::cout << "  E/N=" << res.energy << " m2=" << res.m2 << " n/N=" << res.n_op_avg << std::endl;
}

// Full observable vector vs ED on the 1D chain.
static void test_sse_vs_ed_chain() {
    std::cout << "--- SSE vs ED: chain (E, m2, m4, Q) ---" << std::endl;
    for (int N : {4, 6, 8}) {
        double J = 1.0, h = 0.75, beta = 4.0;
        auto lat = make_chain(N);
        auto ed = compute_thermal_obs(lat, J, h, beta);
        SSEParams p; p.n_thermal = 6000; p.n_bins = 8000; p.sweeps_per_bin = 2; p.seed = 789 + N;
        SSE sse(lat, J, h, beta, p);
        auto res = sse.run();
        std::string t = " N=" + std::to_string(N);
        check("sign" + t, std::abs(res.sign_avg - 1.0) < 1e-12);
        approx_eq("E" + t, res.energy, ed.E, 0.03);
        approx_eq("m2" + t, res.m2, ed.m2, 0.06);
        approx_eq("m4" + t, res.m4, ed.m4, 0.08);
        approx_eq("Q" + t, res.Q, ed.Q, 0.08);
        std::cout << "  N=" << N << " E " << res.energy << "/" << ed.E
                  << " m2 " << res.m2 << "/" << ed.m2
                  << " Q " << res.Q << "/" << ed.Q << std::endl;
    }
}

// Same, on the 2D square lattice — validates the *graph-agnostic* cluster
// update (Stage 2's A/B line update was 1D-only).
static void test_sse_vs_ed_square() {
    std::cout << "--- SSE vs ED: square (E, m2, Q) ---" << std::endl;
    struct Case { int Lx, Ly; double h; };
    for (auto c : {Case{2, 3, 2.0}, Case{3, 3, 2.0}, Case{3, 3, 3.0}}) {
        double J = 1.0, beta = 4.0;
        auto lat = make_square(c.Lx, c.Ly);
        auto ed = compute_thermal_obs(lat, J, c.h, beta);
        SSEParams p; p.n_thermal = 6000; p.n_bins = 8000; p.sweeps_per_bin = 2;
        p.seed = 4000 + 100 * c.Lx + 10 * c.Ly + static_cast<int>(c.h);
        SSE sse(lat, J, c.h, beta, p);
        auto res = sse.run();
        std::ostringstream tag; tag << " " << c.Lx << "x" << c.Ly << " h=" << c.h;
        std::string t = tag.str();
        check("sign" + t, std::abs(res.sign_avg - 1.0) < 1e-12);
        approx_eq("E" + t, res.energy, ed.E, 0.03);
        approx_eq("m2" + t, res.m2, ed.m2, 0.07);
        approx_eq("Q" + t, res.Q, ed.Q, 0.10);
        std::cout << "  " << c.Lx << "x" << c.Ly << " h=" << c.h
                  << " E " << res.energy << "/" << ed.E
                  << " m2 " << res.m2 << "/" << ed.m2
                  << " Q " << res.Q << "/" << ed.Q << std::endl;
    }
}

// Second-moment correlation length vs ED (exercises the fixed smallest_momentum).
static void test_xi_vs_ed() {
    std::cout << "--- xi/L vs ED ---" << std::endl;
    auto lat = make_square(3, 3);
    double J = 1.0, h = 3.0, beta = 4.0;
    auto ed_xi = compute_xi_over_L(lat, J, h, beta);
    SSEParams p; p.n_thermal = 6000; p.n_bins = 10000; p.sweeps_per_bin = 2; p.seed = 33;
    SSE sse(lat, J, h, beta, p);
    auto res = sse.run();
    check("ED xi/L nondegenerate", ed_xi > 1e-6, "ed_xi=" + std::to_string(ed_xi));
    approx_eq("xi/L", res.xi_over_L, ed_xi, 0.12, 0.02);
    std::cout << "  xi/L(SSE)=" << res.xi_over_L << " xi/L(ED)=" << ed_xi << std::endl;
}

// 1D critical chain energy trends to the Jordan-Wigner thermodynamic value.
static void test_1d_critical() {
    std::cout << "--- 1D critical (h=J=1) ---" << std::endl;
    const double E0 = -4.0 / M_PI;
    for (int N : {4, 6, 8, 10}) {
        auto lat = make_chain(N);
        auto ed = compute_thermal_obs(lat, 1.0, 1.0, 4.0);
        SSEParams p; p.n_thermal = 4000; p.n_bins = 6000; p.sweeps_per_bin = 2; p.seed = 100 + N;
        SSE sse(lat, 1.0, 1.0, 4.0, p);
        auto res = sse.run();
        approx_eq("E vs ED N=" + std::to_string(N), res.energy, ed.E, 0.03);
        std::cout << "  N=" << N << " E/N=" << res.energy << " ED=" << ed.E
                  << " thermo=" << E0 << " Q=" << res.Q << "/" << ed.Q << std::endl;
    }
}

// Exact SSE operator-sector identity.  H_const = h*1 has <H_const> = h
// independently of the state, so <n_const> = beta*h*N exactly.  This pins the
// diagonal update on its own, with no reference to ED.
static void test_operator_identity() {
    std::cout << "--- <n_const> = beta*h*N identity ---" << std::endl;
    struct Case { const char* tag; Lattice lat; double h; };
    std::vector<Case> cases;
    cases.push_back({"chain8", make_chain(8), 0.75});
    cases.push_back({"square3x3", make_square(3, 3), 2.0});
    cases.push_back({"tri3x3", make_triangular(3, 3), 4.0});
    cases.push_back({"honey2x2", make_honeycomb(2, 2), 2.0});
    for (auto& c : cases) {
        double beta = 3.0;
        SSEParams p; p.n_thermal = 3000; p.n_bins = 8000; p.sweeps_per_bin = 2; p.seed = 555;
        SSE sse(c.lat, 1.0, c.h, beta, p);
        auto res = sse.run();
        approx_eq(std::string("<n_const> ") + c.tag, res.n_const_avg,
                  beta * c.h * c.lat.N, 0.02, 0.0);
        check(std::string("valid configs ") + c.tag, res.consistency_failures == 0,
              "failures=" + std::to_string(res.consistency_failures));
    }
}

int main() {
    test_operator_identity();
    test_j0_limit();
    test_j0_spacetime_moment();
    test_near_classical();
    test_sse_vs_ed_chain();
    test_sse_vs_ed_square();
    test_xi_vs_ed();
    test_1d_critical();
    std::cout << std::endl;
    if (failures == 0) std::cout << "All SSE tests passed." << std::endl;
    else std::cerr << failures << " test(s) FAILED." << std::endl;
    return failures ? 1 : 0;
}
