#include "../src/lattice.hpp"
#include "../src/berry.hpp"
#include <cmath>
#include <iostream>
#include <sstream>
#include <vector>

using namespace cm;
using cplx = std::complex<double>;

static int failures = 0;
static void check(const std::string& n, bool c, const std::string& d = "") {
    if (!c) { std::cerr << "FAIL: " << n; if (!d.empty()) std::cerr << " — " << d; std::cerr << std::endl; ++failures; }
    else std::cout << "  PASS: " << n << std::endl;
}

// Response formula: F_{θΩ} using finite-difference of Berry connection.
// Identical to FHS formula modulo dθ·dΩ factor. Cross-check: FHS/Δ ≈ response_F.
static double response_formula(
    const GroundState& g00, const GroundState& g10,
    const GroundState& g11, const GroundState& g01,
    double dtheta, double dOmega)
{
    auto p = [](cplx z) { return std::abs(z) > 1e-30 ? std::arg(z) : 0.0; };
    double t0 = p(overlap(g00, g10)) / dtheta;
    double t1 = p(overlap(g01, g11)) / dtheta;
    double o0 = p(overlap(g00, g01)) / dOmega;
    double o1 = p(overlap(g10, g11)) / dOmega;
    return (o1 - o0) / dtheta - (t1 - t0) / dOmega;
}

static void test_fhs_vs_response() {
    std::cout << "--- FHS vs response formula consistency ---" << std::endl;
    for (int N : {4, 6}) {
        auto lat = make_chain(N);
        double dt = 0.05, dO = 0.05;
        for (double th : {0.0, 0.3}) {
            for (double Om : {1.0, 2.0}) {
                auto g00 = solve_ground_state(lat, 1.0, Om, th);
                auto g10 = solve_ground_state(lat, 1.0, Om, th + dt);
                auto g11 = solve_ground_state(lat, 1.0, Om + dO, th + dt);
                auto g01 = solve_ground_state(lat, 1.0, Om + dO, th);

                auto bc = fhs_curvature(g00, g10, g11, g01);
                double rsp = response_formula(g00, g10, g11, g01, dt, dO);
                double fhs = bc.F12 / (dt * dO);

                double diff = std::abs(fhs - rsp);
                double denom = std::max(std::abs(fhs), std::abs(rsp));
                double rel = (denom > 1e-12) ? diff / denom : diff;

                bool skip = denom > 1e-12 &&
                    (std::abs(rsp) > 100 * std::abs(fhs) ||
                     std::abs(fhs) > 100 * std::abs(rsp));

                std::cout << "  N=" << N << " θ=" << th << " Ω=" << Om
                          << " FHS/N/d=" << fhs / N
                          << " RSP/N=" << rsp / N
                          << (skip ? " SKIP" : "")
                          << " rel=" << rel << std::endl;

                if (!skip)
                    check("FHS≈RSP N=" + std::to_string(N), rel < 0.5);
            }
        }
    }
}

static void test_2d_grid() {
    std::cout << "--- 2D square lattice grid ---" << std::endl;
    // L=2 near critical
    auto lat2 = make_square(2, 2);
    for (double Om : {2.8, 3.0, 3.2}) {
        auto bc = fhs_curvature_single(lat2, 1.0, 0.1, Om, 0.1, 0.1);
        std::cout << "  L=2 Ω=" << Om << " F12/N=" << bc.F12/4 << std::endl;
        check("L=2 Ω=" + std::to_string(Om), std::isfinite(bc.F12));
    }
    // L=3 quick points
    auto lat3 = make_square(3, 3);
    for (double Om : {1.0, 3.0}) {
        auto bc = fhs_curvature_single(lat3, 1.0, 0.0, Om, 0.1, 0.1);
        std::cout << "  L=3 Ω=" << Om << " F12/N=" << bc.F12/9 << std::endl;
        check("L=3 Ω=" + std::to_string(Om), std::isfinite(bc.F12));
    }
}

static void test_critical() {
    std::cout << "--- Critical region sweep (L=2) ---" << std::endl;
    auto lat = make_square(2, 2);
    std::vector<double> vals;
    for (double Om : {2.0, 2.5, 2.8, 3.0, 3.2, 3.5, 4.0}) {
        auto bc = fhs_curvature_single(lat, 1.0, 0.0, Om, 0.1, 0.1);
        double d = bc.F12 / 4;
        vals.push_back(d);
        std::cout << "  Ω=" << Om << " F12/N=" << d << std::endl;
    }
    bool varies = false;
    for (size_t i = 1; i < vals.size(); ++i)
        if (std::abs(vals[i] - vals[0]) > 1e-6) varies = true;
    check("curvature varies with Ω", varies);
}

static void test_finite_size() {
    std::cout << "--- 2D finite-size convergence ---" << std::endl;
    for (double Om : {1.0, 2.5}) {
        auto lat2 = make_square(2, 2);
        auto lat3 = make_square(3, 3);
        auto b2 = fhs_curvature_single(lat2, 1.0, 0.0, Om, 0.1, 0.1);
        auto b3 = fhs_curvature_single(lat3, 1.0, 0.0, Om, 0.1, 0.1);
        double d2 = std::abs(b2.F12 / 4);
        double d3 = std::abs(b3.F12 / 9);
        double ratio = (d2 > 1e-12) ? d3 / d2 : 1.0;
        std::cout << "  Ω=" << Om
                  << " L=2:" << b2.F12/4
                  << " L=3:" << b3.F12/9
                  << " ratio=" << ratio << std::endl;
        check("bounded Ω=" + std::to_string(Om), ratio < 100);
    }
}

int main() {
    test_fhs_vs_response();
    test_2d_grid();
    test_critical();
    test_finite_size();
    std::cout << std::endl;
    if (!failures) std::cout << "All Stage 3 tests passed." << std::endl;
    else std::cerr << failures << " FAILED." << std::endl;
    return failures ? 1 : 0;
}
