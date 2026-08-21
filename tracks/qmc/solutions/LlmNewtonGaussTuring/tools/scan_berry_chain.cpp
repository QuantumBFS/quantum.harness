#include "../src/lattice.hpp"
#include "../src/berry.hpp"
#include "berry_scan_common.hpp"
#include <iomanip>
#include <iostream>
#include <cstddef>

int main(int argc, char** argv) {
    if (argc != 9) {
        std::cerr << "Usage: scan_berry_chain <N> <theta_min> <theta_max> <dtheta> "
                  << "<Omega_min> <Omega_max> <dOmega> <J>\n";
        return 1;
    }

    try {
        int N = std::stoi(argv[1]);
        double theta_min = std::stod(argv[2]);
        double theta_max = std::stod(argv[3]);
        double dtheta = std::stod(argv[4]);
        double Omega_min = std::stod(argv[5]);
        double Omega_max = std::stod(argv[6]);
        double dOmega = std::stod(argv[7]);
        double J = std::stod(argv[8]);
        if (N < 2 || N > 10)
            throw std::invalid_argument("require 2 <= N <= 10");

        auto lat = cm::make_chain(N);
        cm::ParamGrid grid;
        grid.theta_values = cm::scan::uniform_axis(
            theta_min, theta_max, dtheta, "theta");
        grid.omega_values = cm::scan::uniform_axis(
            Omega_min, Omega_max, dOmega, "Omega");
        const std::size_t n_theta = grid.theta_values.size();
        const std::size_t n_omega = grid.omega_values.size();

        std::cerr << "Chain N=" << N << " (dim=" << (std::size_t{1} << N) << ")\n";
        std::cerr << "theta: " << theta_min << " .. " << theta_max << " step " << dtheta
                  << " (" << n_theta << " points)\n";
        std::cerr << "Omega: " << Omega_min << " .. " << Omega_max << " step " << dOmega
                  << " (" << n_omega << " points)\n";
        std::cerr << "J=" << J << std::endl;

        auto curv = cm::compute_berry_curvature_grid(lat, J, grid);

        std::cout << std::scientific << std::setprecision(12);
        std::cout << "theta,Omega,F12,F12_per_N,absU1,absU2\n";
        for (std::size_t i = 0; i + 1 < n_theta; ++i) {
            for (std::size_t j = 0; j + 1 < n_omega; ++j) {
                const double theta = 0.5 * (grid.theta_values[i] + grid.theta_values[i + 1]);
                const double omega = 0.5 * (grid.omega_values[j] + grid.omega_values[j + 1]);
                std::cout << theta << "," << omega << ","
                          << curv[i][j].F12 << ","
                          << curv[i][j].F12 / N << ","
                          << curv[i][j].absU1 << ","
                          << curv[i][j].absU2 << "\n";
            }
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "scan_berry_chain: " << error.what() << '\n';
        return 2;
    }
}
