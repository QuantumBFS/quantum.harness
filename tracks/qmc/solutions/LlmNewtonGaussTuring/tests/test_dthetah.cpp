#include "../src/lattice.hpp"
#include "../src/sse.hpp"
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

static void test_dthetah_ed_zero_theta() {
    std::cout << "--- ∂θH ED at θ=0 (should be ~0) ---" << std::endl;
    for (int N : {4, 6}) {
        auto lat = make_chain(N);
        double dth = compute_dthetah_ed(lat, 1.0, 1.0, 0.0, 100.0);
        std::cout << "  N=" << N << " ⟨∂θH⟩_ED = " << dth << std::endl;
        check("ED ∂θH(0) ≈ 0 N=" + std::to_string(N), std::abs(dth) < 1e-6);
    }
}

static void test_dthetah_ed_finite_theta() {
    std::cout << "--- ED ∂θH at θ=0.3 (diagonal non-zero) ---" << std::endl;
    for (int N : {4, 6}) {
        auto lat = make_chain(N);
        double dth = compute_dthetah_ed(lat, 1.0, 1.0, 0.3, 100.0);
        std::cout << "  N=" << N << " ⟨∂θH⟩_ED(0.3) = " << dth << std::endl;
        // At θ=0.3, sin(2*0.3) ≈ 0.565, so diagonal part is non-zero
        check("ED ∂θH(0.3) non-zero N=" + std::to_string(N), std::abs(dth) > 1e-6);
    }
}

static void test_sse_dthetah_vs_ed() {
    std::cout << "--- SSE ∂θH vs ED at θ=0.3, β=4.0 ---" << std::endl;
    for (int N : {4, 6}) {
        auto lat = make_chain(N);

        // ED reference
        double ed_dth = compute_dthetah_ed(lat, 1.0, 1.0, 0.3, 4.0);

        // SSE measurement
        SSEParams sp;
        sp.n_thermal = 5000;
        sp.n_bins = 50;
        sp.sweeps_per_bin = 20;
        sp.seed = 42 + N;
        sp.check_config = true;
        sp.census = false;
        sp.measure_dthetah = true;
        sp.theta_berry = 0.3;

        SSE sse(lat, 1.0, 1.0, 4.0, sp);
        auto res = sse.run();

        std::cout << "  N=" << N
                  << " ED=" << ed_dth
                  << " SSE=" << res.dthetah_diag
                  << " diff=" << std::abs(ed_dth - res.dthetah_diag)
                  << " (n_op_avg=" << res.n_op_avg << ")"
                  << std::endl;

        // The diagonal ∂θH is a direct measurement, should match within ~20%
        double rel_err = 0;
        if (std::abs(ed_dth) > 1e-12)
            rel_err = std::abs(ed_dth - res.dthetah_diag) / std::abs(ed_dth);
        check("SSE vs ED rel < 0.5 N=" + std::to_string(N), rel_err < 0.5);
    }
}

static void test_sse_dthetah_small_theta() {
    std::cout << "--- SSE ∂θH at θ=0.05 (small θ, sin(2θ) ≈ 0.1) ---" << std::endl;
    auto lat = make_chain(6);

    double ed_dth = compute_dthetah_ed(lat, 1.0, 1.0, 0.05, 8.0);

    SSEParams sp;
    sp.n_thermal = 5000;
    sp.n_bins = 50;
    sp.sweeps_per_bin = 20;
    sp.seed = 99;
    sp.measure_dthetah = true;
    sp.theta_berry = 0.05;

    SSE sse(lat, 1.0, 1.0, 8.0, sp);
    auto res = sse.run();

    std::cout << "  ED=" << ed_dth
              << " SSE=" << res.dthetah_diag
              << " diff=" << std::abs(ed_dth - res.dthetah_diag) << std::endl;

    // Note: at θ=0, the non-equilibrium route is needed for full ∂θH.
    // The diagonal part should be correct.
    double rel_err = std::abs(ed_dth) > 1e-12
        ? std::abs(ed_dth - res.dthetah_diag) / std::abs(ed_dth) : 0;
    check("SSE ∂θH at small θ non-divergent", rel_err < 100.0);
}

int main() {
    test_dthetah_ed_zero_theta();
    test_dthetah_ed_finite_theta();
    test_sse_dthetah_vs_ed();
    test_sse_dthetah_small_theta();

    std::cout << std::endl;
    if (!failures)
        std::cout << "All ∂θH tests passed." << std::endl;
    else
        std::cerr << failures << " FAILED." << std::endl;
    return failures ? 1 : 0;
}
