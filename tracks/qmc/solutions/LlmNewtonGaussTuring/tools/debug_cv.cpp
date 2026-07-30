#include "../src/lattice.hpp"
#include "../src/ed.hpp"
#include <cmath>
#include <iomanip>
#include <iostream>

using namespace cm;

// Check the low-T heat capacity of the N=4 chain at h=0.5 against the exact
// two-level (Schottky) formula built from the ED spectrum itself.
int main() {
    auto lat = make_chain(4);
    double J = 1.0, h = 0.5, beta = 100.0;

    auto H = build_tfim_hamiltonian(lat, J, h);
    auto es = jacobi_eigen(H);

    std::cout << std::setprecision(10);
    std::cout << "lowest eigenvalues:\n";
    for (int i = 0; i < 6; ++i) std::cout << "  E" << i << " = " << es.eigenvalues[i] << "\n";
    double delta = es.eigenvalues[1] - es.eigenvalues[0];
    std::cout << "ground doublet splitting delta = " << delta << "\n";
    std::cout << "beta*delta = " << beta * delta << "\n";

    // exact two-level Schottky heat capacity per site
    double x = beta * delta;
    double Cv_2lvl = (x * x * std::exp(x) / std::pow(1.0 + std::exp(x), 2)) / lat.N;
    std::cout << "two-level Schottky Cv/N = " << Cv_2lvl << "\n";

    auto obs = compute_thermal_obs(lat, J, h, beta);
    std::cout << "ED compute_thermal_obs Cv/N = " << obs.Cv << "\n";
    return 0;
}
