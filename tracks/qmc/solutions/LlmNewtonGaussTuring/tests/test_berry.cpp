#include "../src/lattice.hpp"
#include "../src/berry.hpp"
#include <cmath>
#include <iostream>
#include <sstream>

using namespace cm;
static int failures = 0;
static void check(const std::string& n, bool c, const std::string& d = "") {
    if (!c) { std::cerr << "FAIL: " << n; if (!d.empty()) std::cerr << " — " << d; std::cerr << std::endl; ++failures; }
    else std::cout << "  PASS: " << n << std::endl;
}

// 1D chain N=2 — FHS gives non-zero curvature
static void test_1d_n2() {
    std::cout << "--- 1D chain N=2 ---" << std::endl;
    auto lat = make_chain(2);
    auto gs00 = solve_ground_state(lat, 1.0, 1.0, 0.0);
    auto gs10 = solve_ground_state(lat, 1.0, 1.0, 0.1);
    auto gs11 = solve_ground_state(lat, 1.0, 1.1, 0.1);
    auto gs01 = solve_ground_state(lat, 1.0, 1.1, 0.0);
    auto bc = fhs_curvature(gs00, gs10, gs11, gs01);
    check("E0 finite", std::isfinite(gs00.E0));
    check("F12 != 0", std::abs(bc.F12) > 1e-8);
    check("U1 ~ 1", bc.absU1 > 0.7);
    std::cout << "  E0(0,1)=" << gs00.E0 << " F12=" << bc.F12 << std::endl;
}

// 1D N=4 — grid produces smoothly varying curvature
static void test_1d_n4_grid() {
    std::cout << "--- 1D N=4 grid ---" << std::endl;
    auto lat = make_chain(4);
    ParamGrid g; g.vals1={0.0,0.05,0.10}; g.vals2={0.8,0.85,0.90};
    auto curv = compute_berry_curvature_grid(lat, 1.0, g);
    bool any = false;
    for (size_t i = 0; i < curv.size(); ++i)
        for (size_t j = 0; j < curv[i].size(); ++j) {
            if (std::abs(curv[i][j].F12) > 1e-8) any = true;
            std::cout << "  F(" << g.vals1[i] << "," << g.vals2[j] << ") = " << curv[i][j].F12 << std::endl;
        }
    check("F12 non-zero", any);
}

// 2D square 2×2
static void test_2d_square() {
    std::cout << "--- 2D square 2×2 ---" << std::endl;
    auto lat = make_square(2, 2);
    ParamGrid g; g.vals1 = {0.0, 0.05}; g.vals2 = {1.0, 1.05};
    auto curv = compute_berry_curvature_grid(lat, 1.0, g);
    check("2D F12 finite", std::isfinite(curv[0][0].F12));
    check("U1 > 0.7", curv[0][0].absU1 > 0.7);
    std::cout << "  F(2×2) = " << curv[0][0].F12 << "   U1=" << curv[0][0].absU1 << std::endl;
}

int main() {
    test_1d_n2(); test_1d_n4_grid(); test_2d_square();
    std::cout << std::endl;
    if (failures == 0) std::cout << "All Berry-phase tests passed." << std::endl;
    else std::cerr << failures << " FAILED." << std::endl;
    return failures ? 1 : 0;
}
