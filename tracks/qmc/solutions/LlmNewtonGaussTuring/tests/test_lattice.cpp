#include "../src/lattice.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
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
    check("k_min > 0", lat.smallest_momentum() > 0);
    std::cout << "  k_min = " << lat.smallest_momentum() << std::endl;
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
