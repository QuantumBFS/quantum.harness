#include "../src/lattice.hpp"
#include "../src/berry.hpp"
#include <iomanip>
#include <iostream>
#include <cmath>
#include <cstddef>

int main(int argc, char** argv) {
    if (argc != 9) {
        std::cerr << "Usage: scan_berry_chain <N> <theta_min> <theta_max> <dtheta> "
                  << "<Omega_min> <Omega_max> <dOmega> <J>\n";
        return 1;
    }

    int N = std::stoi(argv[1]);
    double theta_min = std::stod(argv[2]);
    double theta_max = std::stod(argv[3]);
    double dtheta = std::stod(argv[4]);
    double Omega_min = std::stod(argv[5]);
    double Omega_max = std::stod(argv[6]);
    double dOmega = std::stod(argv[7]);
    double J = std::stod(argv[8]);
    if (N < 2 || N > 10 || !(dtheta > 0.0) || !(dOmega > 0.0)
        || theta_max <= theta_min || Omega_max <= Omega_min) {
        std::cerr << "scan_berry_chain: require 2 <= N <= 10, positive steps, and increasing ranges\n";
        return 2;
    }

    auto lat = cm::make_chain(N);

    int n_theta = static_cast<int>((theta_max - theta_min) / dtheta) + 1;
    int n_Omega = static_cast<int>((Omega_max - Omega_min) / dOmega) + 1;

    std::cerr << "Chain N=" << N << " (dim=" << (std::size_t{1} << N) << ")\n";
    std::cerr << "theta: " << theta_min << " .. " << theta_max << " step " << dtheta
              << " (" << n_theta << " points)\n";
    std::cerr << "Omega: " << Omega_min << " .. " << Omega_max << " step " << dOmega
              << " (" << n_Omega << " points)\n";
    std::cerr << "J=" << J << std::endl;

    cm::ParamGrid grid;
    grid.theta_values.resize(n_theta);
    for (int i = 0; i < n_theta; ++i)
        grid.theta_values[i] = theta_min + i * dtheta;
    grid.omega_values.resize(n_Omega);
    for (int j = 0; j < n_Omega; ++j)
        grid.omega_values[j] = Omega_min + j * dOmega;

    auto curv = cm::compute_berry_curvature_grid(lat, J, grid);

    std::cout << std::scientific << std::setprecision(12);
    std::cout << "theta,Omega,F12,F12_per_N,absU1,absU2\n";
    for (int i = 0; i < n_theta - 1; ++i) {
        for (int j = 0; j < n_Omega - 1; ++j) {
            double theta = grid.theta_values[i] + 0.5 * dtheta;
            double Omega = grid.omega_values[j] + 0.5 * dOmega;
            std::cout << theta << "," << Omega << ","
                      << curv[i][j].F12 << ","
                      << curv[i][j].F12 / N << ","
                      << curv[i][j].absU1 << ","
                      << curv[i][j].absU2 << "\n";
        }
    }

    return 0;
}
