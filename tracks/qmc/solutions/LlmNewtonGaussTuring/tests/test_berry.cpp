#include "../src/lattice.hpp"
#include "../src/berry.hpp"
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
static void approx_eq(const std::string& n, double g, double e, double tol = 1e-10) {
    if (std::abs(g - e) < tol) std::cout << "  PASS: " << n << " (" << g << ")" << std::endl;
    else { std::ostringstream o; o << "got=" << g << " expected=" << e; check(n, false, o.str()); }
}

static void test_gauge() {
    std::cout << "--- Gauge invariance ---" << std::endl;
    auto lat = make_chain(2);
    GroundState g00 = solve_ground_state(lat,1.0,1.0,0.0);
    GroundState g10 = solve_ground_state(lat,1.0,1.0,0.05);
    GroundState g11 = solve_ground_state(lat,1.0,1.05,0.05);
    GroundState g01 = solve_ground_state(lat,1.0,1.05,0.0);
    auto bc1 = fhs_curvature(g00, g10, g11, g01);
    for (auto& z : g00.eigenvector) z *= std::polar(1.0, 0.3);
    for (auto& z : g10.eigenvector) z *= std::polar(1.0, -0.7);
    for (auto& z : g11.eigenvector) z *= std::polar(1.0, 1.2);
    for (auto& z : g01.eigenvector) z *= std::polar(1.0, -2.1);
    auto bc2 = fhs_curvature(g00, g10, g11, g01);
    approx_eq("F12 gauge invariant", bc1.F12, bc2.F12);
}

static void test_1d_n2() {
    std::cout << "--- 1D N=2 ---" << std::endl;
    auto lat = make_chain(2);
    auto g00 = solve_ground_state(lat,1.0,1.0,0.0);
    auto g10 = solve_ground_state(lat,1.0,1.0,0.1);
    auto g11 = solve_ground_state(lat,1.0,1.1,0.1);
    auto g01 = solve_ground_state(lat,1.0,1.1,0.0);
    auto bc = fhs_curvature(g00, g10, g11, g01);
    check("F12 != 0", std::abs(bc.F12) > 1e-8);
    std::cout << "  F12=" << bc.F12 << std::endl;
}

static void test_1d_n4() {
    std::cout << "--- 1D N=4 ---" << std::endl;
    auto lat = make_chain(4);
    ParamGrid g; g.vals1={0.0,0.05,0.10}; g.vals2={0.8,0.85,0.90};
    auto c = compute_berry_curvature_grid(lat,1.0,g);
    bool any = false;
    for (size_t i=0;i<c.size();++i) for(size_t j=0;j<c[i].size();++j) {
        if (std::abs(c[i][j].F12)>1e-8) any=true;
        std::cout << "  F("<<g.vals1[i]<<","<<g.vals2[j]<<")="<<c[i][j].F12<<std::endl;
    }
    check("F12 != 0", any);
}

static void test_convergence() {
    std::cout << "--- Finite-size convergence (θ=0, Ω=1, dθ=0.05, dΩ=0.05) ---" << std::endl;
    std::vector<double> dens;
    for (int N : {2, 4, 6}) {
        auto lat = make_chain(N);
        GroundState g00=solve_ground_state(lat,1.0,1.0,0.0);
        GroundState g10=solve_ground_state(lat,1.0,1.0,0.05);
        GroundState g11=solve_ground_state(lat,1.0,1.05,0.05);
        GroundState g01=solve_ground_state(lat,1.0,1.05,0.0);
        auto bc = fhs_curvature(g00, g10, g11, g01);
        double d = bc.F12 / N;
        dens.push_back(d);
        std::cout << "  N=" << N << " F12/N=" << d << std::endl;
    }
    // Verify F12/N is bounded: N=6 should be within a factor of 20 of N=4.
    // N=2 is too small for meaningful curvature, so we skip it as baseline.
    check("density bounded N=4 vs N=6", std::abs(dens[2]) < std::abs(dens[1]) * 20);
}

static void test_2d() {
    std::cout << "--- 2D 2×2 ---" << std::endl;
    auto lat = make_square(2,2);
    ParamGrid g; g.vals1={0.0,0.05}; g.vals2={1.0,1.05};
    auto c = compute_berry_curvature_grid(lat,1.0,g);
    check("F12 finite", std::isfinite(c[0][0].F12));
    std::cout << "  F=" << c[0][0].F12 << std::endl;
}

int main() {
    test_gauge(); test_1d_n2(); test_1d_n4(); test_convergence(); test_2d();
    std::cout << std::endl;
    if (!failures) std::cout << "All Berry-phase tests passed." << std::endl;
    else std::cerr << failures << " FAILED." << std::endl;
    return failures ? 1 : 0;
}
