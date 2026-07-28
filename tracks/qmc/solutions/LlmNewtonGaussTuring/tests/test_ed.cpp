#include "../src/lattice.hpp"
#include "../src/ed.hpp"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>

using namespace cm;

static int failures = 0;

static void check(const std::string& name, bool cond, const std::string& diag = "") {
    if (!cond) {
        std::cerr << "FAIL: " << name;
        if (!diag.empty()) std::cerr << " | " << diag;
        std::cerr << std::endl;
        ++failures;
    } else {
        std::cout << "  PASS: " << name << std::endl;
    }
}

// ============================================================
// Test: Hamiltonian symmetry
// ============================================================
static void test_hamiltonian_symmetry() {
    std::cout << "--- Hamiltonian symmetry ---" << std::endl;
    auto lat = make_chain(6);
    auto H = build_tfim_hamiltonian(lat, 1.0, 0.5);

    for (std::size_t i = 0; i < H.dim; ++i) {
        for (std::size_t j = 0; j < i; ++j) {
            if (std::abs(H(i, j) - H(j, i)) > 1e-14) {
                check("symmetry", false,
                      "H(" + std::to_string(i) + "," + std::to_string(j) +
                      ") != H(" + std::to_string(j) + "," + std::to_string(i) + ")");
                return;
            }
        }
    }
    check("symmetry", true);
}

// ============================================================
// Test: J=0 independent spins
// ============================================================
static void test_independent_spins() {
    std::cout << "--- J=0 independent spins ---" << std::endl;
    int N = 6;
    double h = 1.5;
    auto lat = make_chain(N);
    auto H = build_tfim_hamiltonian(lat, 0.0, h);
    auto es = jacobi_eigen(H);

    // Expected spectrum: eigenvalues form binomial distribution
    // Each spin contributes ±h, so total energies are
    // E = -N*h, -(N-2)*h, ..., (N-2)*h, N*h
    // Degeneracy of E = (N-2k)*h is C(N, k) where k = number of "+h" (spin-up in sigma^z)

    std::map<double, int> expected;
    for (int k = 0; k <= N; ++k) {
        double E = static_cast<double>(N - 2 * k) * (-1.0) * h;
        // Combinatorial degeneracy: C(N, k)
        int deg = 1;
        for (int i = 1; i <= k; ++i) deg = deg * (N - i + 1) / i;
        expected[E] = deg;
    }

    // Check that ground energy matches
    double E0_expected = -static_cast<double>(N) * h;
    check("J=0 E0", std::abs(es.eigenvalues[0] - E0_expected) < 1e-12,
          "got " + std::to_string(es.eigenvalues[0]) +
          " expected " + std::to_string(E0_expected));

    // Count degeneracies from computed spectrum
    std::map<double, int> computed;
    for (std::size_t i = 0; i < es.eigenvalues.size(); ++i) {
        // Round to deal with floating point
        double E = std::round(es.eigenvalues[i] * 1e10) / 1e10;
        computed[E]++;
    }

    for (const auto& [E, deg] : expected) {
        double Ekey = std::round(E * 1e10) / 1e10;
        auto it = computed.find(Ekey);
        if (it == computed.end()) {
            check("J=0 E=" + std::to_string(E), false, "energy level missing");
        } else {
            check("J=0 E=" + std::to_string(E) + " deg=" + std::to_string(deg),
                  it->second == deg,
                  "got deg=" + std::to_string(it->second));
        }
    }
}

// ============================================================
// Test: h=0 classical Ising
// ============================================================
static void test_classical_ising() {
    std::cout << "--- h=0 classical Ising ---" << std::endl;
    int L = 2;
    auto lat = make_square(L, L);
    auto H = build_tfim_hamiltonian(lat, 1.0, 0.0);
    auto es = jacobi_eigen(H);

    // Diagonal only: check that all off-diagonal elements are zero
    bool all_offdiag_zero = true;
    for (std::size_t i = 0; i < H.dim && all_offdiag_zero; ++i)
        for (std::size_t j = 0; j < H.dim && all_offdiag_zero; ++j)
            if (i != j && std::abs(H(i, j)) > 1e-15)
                all_offdiag_zero = false;
    check("h=0 offdiagonal zero", all_offdiag_zero);

    // Ground state: all up or all down, energy = -J * Nb
    double E0_expected = -1.0 * static_cast<double>(lat.Nb);
    check("h=0 E0", std::abs(es.eigenvalues[0] - E0_expected) < 1e-12,
          "got " + std::to_string(es.eigenvalues[0]) +
          " expected " + std::to_string(E0_expected));

    // Ground state degeneracy should be 2 (all up, all down)
    int gs_degeneracy = 0;
    for (std::size_t i = 0; i < es.eigenvalues.size(); ++i) {
        if (std::abs(es.eigenvalues[i] - E0_expected) < 1e-12)
            ++gs_degeneracy;
    }
    check("h=0 GS degeneracy", gs_degeneracy == 2,
          "got " + std::to_string(gs_degeneracy));
}

// ============================================================
// Test: Lanczos vs ED for small systems
// ============================================================
static void test_lanczos_vs_ed() {
    std::cout << "--- Lanczos vs ED ---" << std::endl;
    auto lat = make_chain(8);
    double J = 1.0, h = 1.0;

    auto H = build_tfim_hamiltonian(lat, J, h);
    auto es = jacobi_eigen(H);
    double E0_ed = es.eigenvalues[0];

    auto lr = lanczos_ground(lat, J, h, 300, 1e-10);
    check("lanczos converged", lr.converged);
    check("lanczos E0 vs ED",
          std::abs(lr.E0 - E0_ed) < 1e-8,
          "lanczos=" + std::to_string(lr.E0) +
          " ED=" + std::to_string(E0_ed));
    const double norm = std::inner_product(
        lr.psi0.begin(), lr.psi0.end(), lr.psi0.begin(), 0.0);
    check("lanczos Ritz vector normalized", std::abs(norm - 1.0) < 1e-12,
          "norm2=" + std::to_string(norm));
    std::vector<double> Hpsi(H.dim);
    H.matvec(lr.psi0.data(), Hpsi.data());
    const double rayleigh = std::inner_product(
        lr.psi0.begin(), lr.psi0.end(), Hpsi.begin(), 0.0);
    check("lanczos energy is Rayleigh quotient",
          std::abs(rayleigh - lr.E0) < 1e-12,
          "rayleigh=" + std::to_string(rayleigh));
    double residual2 = 0.0;
    for (std::size_t index = 0; index < H.dim; ++index) {
        const double value = Hpsi[index] - lr.E0 * lr.psi0[index];
        residual2 += value * value;
    }
    const double residual = std::sqrt(residual2);
    check("reported Lanczos residual is physical residual",
          std::abs(residual - lr.residual) < 1e-13,
          "reported=" + std::to_string(lr.residual)
          + " direct=" + std::to_string(residual));
    check("Lanczos residual meets tolerance", residual < 2e-9,
          "residual=" + std::to_string(residual));
    std::cout << "  E0 (ED)     = " << E0_ed << std::endl;
    std::cout << "  E0 (Lanczos)= " << lr.E0 << std::endl;
    std::cout << "  iterations   = " << lr.niter << std::endl;
}

static void test_input_guards() {
    std::cout << "--- input guards ---" << std::endl;
    Lattice oversized;
    oversized.N = std::numeric_limits<std::size_t>::digits;
    bool shift_guarded = false;
    try {
        (void)build_tfim_hamiltonian(oversized, 1.0, 1.0);
    } catch (const std::length_error&) {
        shift_guarded = true;
    }
    check("basis shift overflow rejected", shift_guarded);

    bool matrix_guarded = false;
    try {
        DenseSymMatrix matrix(std::numeric_limits<std::size_t>::max());
        (void)matrix;
    } catch (const std::length_error&) {
        matrix_guarded = true;
    }
    check("dense matrix product overflow rejected", matrix_guarded);

    auto invalid = make_chain(4);
    invalid.bonds.front().i = invalid.N;
    bool endpoint_guarded = false;
    try {
        (void)lanczos_ground(invalid, 1.0, 1.0);
    } catch (const std::out_of_range&) {
        endpoint_guarded = true;
    }
    check("Lanczos invalid bond rejected", endpoint_guarded);

    bool tolerance_guarded = false;
    try {
        (void)lanczos_ground(make_chain(2), 1.0, 1.0, 20,
                             std::numeric_limits<double>::infinity());
    } catch (const std::invalid_argument&) {
        tolerance_guarded = true;
    }
    check("non-finite Lanczos tolerance rejected", tolerance_guarded);

    bool beta_guarded = false;
    try {
        (void)compute_thermal_obs(make_chain(2), 1.0, 1.0,
                                  std::numeric_limits<double>::infinity());
    } catch (const std::invalid_argument&) {
        beta_guarded = true;
    }
    check("non-finite inverse temperature rejected", beta_guarded);

    bool momentum_guarded = false;
    try {
        (void)compute_structure_factor(
            make_chain(2), 1.0, 1.0, 1.0,
            {std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0});
    } catch (const std::invalid_argument&) {
        momentum_guarded = true;
    }
    check("non-finite structure-factor momentum rejected", momentum_guarded);
}

// ============================================================
// Test: Thermal observables (high T → classical limits)
// ============================================================
static void test_thermal_limits() {
    std::cout << "--- Thermal limits ---" << std::endl;
    // Small 1D chain for quick computation
    auto lat = make_chain(4);
    double J = 1.0, h = 0.5;

    // High temperature (beta = 0.01): all states equally weighted
    auto obs_high = compute_thermal_obs(lat, J, h, 0.01);
    check("high-T E finite", std::isfinite(obs_high.E));
    check("high-T Cv finite", std::isfinite(obs_high.Cv));
    check("high-T Q finite", std::isfinite(obs_high.Q));
    std::cout << "  beta=0.01: E=" << obs_high.E
              << " m=" << obs_high.m << " Q=" << obs_high.Q << std::endl;

    // Low temperature.  The N=4 FM chain at h=0.5 has a near-degenerate ground
    // doublet (split by delta = 0.0355 here), so at beta=100 we sit at
    // beta*delta = 3.55 — right on the two-level Schottky peak.  Cv/N is
    // therefore O(0.1), NOT small; asserting "Cv small" at this beta only
    // passed while Cv was mis-normalised (divided by beta^2 instead of
    // multiplied).  Check it against the exact two-level formula instead.
    auto H = build_tfim_hamiltonian(lat, J, h);
    auto es = jacobi_eigen(H);
    double delta = es.eigenvalues[1] - es.eigenvalues[0];

    auto obs_low = compute_thermal_obs(lat, J, h, 100.0);
    check("low-T E reasonable", std::isfinite(obs_low.E));
    {
        double x = 100.0 * delta;
        double schottky = (x * x * std::exp(x) / std::pow(1.0 + std::exp(x), 2)) / lat.N;
        check("low-T Cv = two-level Schottky",
              std::abs(obs_low.Cv - schottky) < 1e-9 * (1.0 + std::abs(schottky)),
              "got=" + std::to_string(obs_low.Cv) + " schottky=" + std::to_string(schottky));
    }
    std::cout << "  beta=100: E=" << obs_low.E
              << " Cv=" << obs_low.Cv << " Q=" << obs_low.Q
              << " (doublet split delta=" << delta << ")" << std::endl;

    // Deep in the gap (beta*delta >> 1) the heat capacity really does vanish.
    auto obs_vlow = compute_thermal_obs(lat, J, h, 1000.0);
    check("deep low-T Cv -> 0", obs_vlow.Cv < 1e-9,
          "got=" + std::to_string(obs_vlow.Cv));
    std::cout << "  beta=1000: Cv=" << obs_vlow.Cv << std::endl;
}

// ============================================================
// Test: Structure factor at q=0 equals magnetization^2
// ============================================================
static void test_structure_factor() {
    std::cout << "--- Structure factor ---" << std::endl;
    auto lat = make_chain(4);
    double J = 1.0, h = 1.0;

    // At q=0, S(0) = <(sum_i sigma^z_i)^2>/N^2 = <m_total^2>/N^2 = m2
    double S0 = compute_structure_factor(lat, J, h, 10.0, {0, 0, 0});
    auto obs = compute_thermal_obs(lat, J, h, 10.0);
    check("S(0) = m2", std::abs(S0 - obs.m2) < 1e-10,
          "S0=" + std::to_string(S0) + " m2=" + std::to_string(obs.m2));

    // q>0: structure factor should be smaller
    double q_min = lat.smallest_momentum();
    double Sq = compute_structure_factor(lat, J, h, 10.0, {q_min, 0, 0});
    check("S(q_min) < S(0)", Sq <= S0 + 1e-12,
          "Sq=" + std::to_string(Sq) + " S0=" + std::to_string(S0));
    std::cout << "  S(0)=" << S0 << " S(q_min)=" << Sq << std::endl;

    // xi/L computation
    double xiL = compute_xi_over_L(lat, J, h, 10.0);
    check("xi/L finite", std::isfinite(xiL));
    std::cout << "  xi/L = " << xiL << std::endl;
}

// ============================================================
// Test: 1D TFIM critical point h/J = 1
// ============================================================
static void test_1d_critical_point() {
    std::cout << "--- 1D critical h=J ---" << std::endl;

    // For 1D TFIM with J=h, the exact thermodynamic ground-state energy
    // per site is E0/N = -4/pi ≈ -1.27323954... (derived from JW)
    // Check that finite-size results approach this value

    const double exact_E0_per_site = -4.0 / M_PI;

    for (int N : {4, 6, 8, 10}) {
        auto lat = make_chain(N);
        auto H = build_tfim_hamiltonian(lat, 1.0, 1.0);
        auto es = jacobi_eigen(H);
        double E0_per_site = es.eigenvalues[0] / static_cast<double>(N);
        std::cout << "  N=" << N << " E0/N=" << E0_per_site
                  << " (exact=" << exact_E0_per_site << ")" << std::endl;

        // Finite-size: should be below exact value and converging
        check("E0/N below exact for N=" + std::to_string(N),
              E0_per_site < exact_E0_per_site + 0.01);
    }
}

int main() {
    test_hamiltonian_symmetry();
    test_independent_spins();
    test_classical_ising();
    test_lanczos_vs_ed();
    test_input_guards();
    test_thermal_limits();
    test_structure_factor();
    test_1d_critical_point();

    std::cout << std::endl;
    if (failures == 0) {
        std::cout << "All ED tests passed." << std::endl;
        return 0;
    } else {
        std::cerr << failures << " test(s) FAILED." << std::endl;
        return 1;
    }
}
