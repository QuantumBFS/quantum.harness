#include "../src/lattice.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using namespace cm;

static int failures = 0;

static void check(const std::string& name, bool cond, const std::string& diag = "") {
    if (!cond) {
        std::cerr << "FAIL: " << name;
        if (!diag.empty()) std::cerr << " — " << diag;
        std::cerr << std::endl;
        ++failures;
    } else {
        std::cout << "  PASS: " << name << std::endl;
    }
}

static void test_chain() {
    std::cout << "--- chain ---" << std::endl;
    auto lat = make_chain(8);
    check("name", lat.name == "chain");
    check("N", lat.N == 8);
    check("Nb", lat.Nb == 8);
    check("coord", lat.expected_coordination == 2);

    std::string diag;
    check("verify", lat.verify(&diag), diag);

    auto coord = lat.get_coordination();
    for (std::size_t s = 0; s < lat.N; ++s)
        check("site " + std::to_string(s) + " coord=2", coord[s] == 2);

    check("k_min > 0", lat.smallest_momentum() > 0);
    std::cout << "  k_min = " << lat.smallest_momentum() << std::endl;
}

static void test_square() {
    std::cout << "--- square ---" << std::endl;
    auto lat = make_square(4, 4);
    check("name", lat.name == "square");
    check("N", lat.N == 16);
    check("Nb", lat.Nb == 32);
    check("coord", lat.expected_coordination == 4);

    std::string diag;
    check("verify", lat.verify(&diag), diag);
    check("k_min > 0", lat.smallest_momentum() > 0);
    std::cout << "  k_min = " << lat.smallest_momentum() << std::endl;

    // Permutation invariance
    std::vector<std::size_t> perm(lat.N);
    for (std::size_t i = 0; i < lat.N; ++i) perm[i] = lat.N - 1 - i;
    auto lat2 = lat.with_permuted_index(perm);
    std::string diag2;
    check("permuted verify", lat2.verify(&diag2), diag2);
}

static void test_triangular() {
    std::cout << "--- triangular ---" << std::endl;
    auto lat = make_triangular(4, 4);
    check("name", lat.name == "triangular");
    check("N", lat.N == 16);
    check("Nb", lat.Nb == 48);
    check("coord", lat.expected_coordination == 6);

    std::string diag;
    check("verify", lat.verify(&diag), diag);
    check("k_min > 0", lat.smallest_momentum() > 0);
    std::cout << "  k_min = " << lat.smallest_momentum() << std::endl;
}

static void test_honeycomb() {
    std::cout << "--- honeycomb ---" << std::endl;
    auto lat = make_honeycomb(3, 3);
    check("name", lat.name == "honeycomb");
    // Nuc = 3*3 = 9, N = 18, Nb = 3*9 = 27
    check("N", lat.N == 18);
    check("Nb", lat.Nb == 27);
    check("coord", lat.expected_coordination == 3);

    std::string diag;
    check("verify", lat.verify(&diag), diag);
    const auto momenta = lat.smallest_momentum_vectors();
    check("six shortest momenta", momenta.size() == 6,
          "count=" + std::to_string(momenta.size()));
    check("k_min > 0", lat.smallest_momentum() > 0);
    std::cout << "  k_min = " << lat.smallest_momentum() << std::endl;

    const double expected_bond2 = 1.0 / 3.0;
    bool equal_lengths = true;
    for (const auto& bond : lat.bonds) {
        const double dx0 = lat.site_coords[bond.j][0] - lat.site_coords[bond.i][0];
        const double dy0 = lat.site_coords[bond.j][1] - lat.site_coords[bond.i][1];
        double min_length2 = std::numeric_limits<double>::max();
        for (int a = -1; a <= 1; ++a)
            for (int b = -1; b <= 1; ++b) {
                const double dx = dx0 + a * lat.L[0] * lat.prim_vec_a[0]
                                      + b * lat.L[1] * lat.prim_vec_b[0];
                const double dy = dy0 + a * lat.L[0] * lat.prim_vec_a[1]
                                      + b * lat.L[1] * lat.prim_vec_b[1];
                min_length2 = std::min(min_length2, dx * dx + dy * dy);
            }
        equal_lengths = equal_lengths && std::abs(min_length2 - expected_bond2) < 1e-12;
    }
    check("all embedded bonds have equal length", equal_lengths);

    // The corrected embedding deliberately preserves the historical site and
    // bond ordering, so code and stored configurations that use indices remain
    // compatible with Stages 1-3.
    auto ordered = make_honeycomb(3, 2);
    const std::size_t unit_cells = 6;
    std::size_t bond_index = 0;
    bool ordering_compatible = true;
    auto site_b = [unit_cells](int x, int y) {
        const int wrapped_x = (x % 3 + 3) % 3;
        const int wrapped_y = (y % 2 + 2) % 2;
        return unit_cells + static_cast<std::size_t>(wrapped_x * 2 + wrapped_y);
    };
    for (int x = 0; x < 3; ++x) {
        for (int y = 0; y < 2; ++y) {
            const std::size_t site_a = static_cast<std::size_t>(x * 2 + y);
            const std::array<std::size_t, 3> expected = {
                site_b(x, y), site_b(x - 1, y), site_b(x, y - 1)
            };
            for (std::size_t neighbor : expected) {
                const Bond& bond = ordered.bonds[bond_index++];
                ordering_compatible = ordering_compatible
                    && bond.i == site_a && bond.j == neighbor;
            }
        }
    }
    check("historical site and bond ordering preserved", ordering_compatible);
}

static void test_small_tori_and_validation() {
    std::cout << "--- small tori and validation ---" << std::endl;
    auto chain = make_chain(2);
    std::string diagnostic;
    check("L=2 parallel bonds are valid", chain.verify(&diagnostic), diagnostic);
    check("L=2 chain retains two interaction terms",
          chain.bonds.size() == 2
          && chain.bonds[0].i == chain.bonds[1].j
          && chain.bonds[0].j == chain.bonds[1].i);
    const auto coordination = chain.get_coordination();
    check("parallel bonds contribute twice to coordination",
          coordination[0] == 2 && coordination[1] == 2);

    auto invalid = make_chain(4);
    invalid.bonds[0].j = invalid.N + 3;
    diagnostic.clear();
    bool verify_returned = false;
    try {
        verify_returned = invalid.verify(&diagnostic);
    } catch (...) {
        check("verify handles invalid endpoints without access", false);
    }
    check("invalid endpoint rejected", !verify_returned,
          "diagnostic=" + diagnostic);
    bool coordination_threw = false;
    try {
        (void)invalid.get_coordination();
    } catch (const std::out_of_range&) {
        coordination_threw = true;
    }
    check("coordination rejects invalid endpoint", coordination_threw);

    auto square = make_square(3, 3);
    std::vector<std::size_t> duplicate(square.N, 0);
    bool duplicate_threw = false;
    try {
        (void)square.with_permuted_index(duplicate);
    } catch (const std::invalid_argument&) {
        duplicate_threw = true;
    }
    check("duplicate permutation rejected", duplicate_threw);

    std::vector<std::size_t> out_of_range(square.N);
    for (std::size_t site = 0; site < square.N; ++site) out_of_range[site] = site;
    out_of_range.back() = square.N;
    bool range_threw = false;
    try {
        (void)square.with_permuted_index(out_of_range);
    } catch (const std::invalid_argument&) {
        range_threw = true;
    }
    check("out-of-range permutation rejected", range_threw);
}

static void test_skew_torus_momentum() {
    std::cout << "--- skew torus momentum ---" << std::endl;
    Lattice skew;
    skew.dim = 2;
    skew.L = {1, 1, 1};
    skew.recip_a = {1.0, 0.0, 0.0};
    skew.recip_b = {5.01, 0.1, 0.0};
    const auto momenta = skew.smallest_momentum_vectors();
    const double expected = std::sqrt(0.01 * 0.01 + 0.1 * 0.1);
    check("short vector outside fixed coefficient window found",
          momenta.size() == 2 && std::abs(skew.smallest_momentum() - expected) < 1e-12,
          "count=" + std::to_string(momenta.size())
          + " norm=" + std::to_string(skew.smallest_momentum()));
}

static void test_bond_formulas() {
    std::cout << "--- bond formulas ---" << std::endl;
    for (int L = 2; L <= 12; L += 2) {
        auto ch = make_chain(L);
        check("chain L=" + std::to_string(L) + " Nb=N", ch.Nb == ch.N);

        auto sq = make_square(L, L);
        check("square L=" + std::to_string(L) + " Nb=2N", sq.Nb == 2 * sq.N);

        auto tri = make_triangular(L, L);
        check("triangular L=" + std::to_string(L) + " Nb=3N", tri.Nb == 3 * tri.N);

        auto hc = make_honeycomb(L, L);
        check("honeycomb L=" + std::to_string(L) + " Nb=3N/2",
              hc.Nb == 3 * hc.N / 2);
    }
}

int main() {
    test_chain();
    test_square();
    test_triangular();
    test_honeycomb();
    test_small_tori_and_validation();
    test_skew_torus_momentum();
    test_bond_formulas();

    std::cout << std::endl;
    if (failures == 0) {
        std::cout << "All lattice tests passed." << std::endl;
        return 0;
    } else {
        std::cerr << failures << " test(s) FAILED." << std::endl;
        return 1;
    }
}
