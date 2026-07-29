#include "matchgate_rbim_cylinder.h"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    if (argc != 2) {
        std::cerr << "usage: fixed_driver BONDS.txt\n";
        return 2;
    }
    std::ifstream input(argv[1]);
    int length = 0;
    int circumference = 0;
    int stabilization = 0;
    double coupling = 0.0;
    input >> length >> circumference >> coupling >> stabilization;
    if (!input || length < 2 || circumference < 2 || stabilization < 1) {
        std::cerr << "invalid header\n";
        return 3;
    }

    MatrixXd vertical(length, circumference);
    MatrixXd horizontal(length - 1, circumference);
    for (int row = 0; row < length; ++row) {
        for (int column = 0; column < circumference; ++column) {
            input >> vertical(row, column);
        }
    }
    for (int row = 0; row < length - 1; ++row) {
        for (int column = 0; column < circumference; ++column) {
            input >> horizontal(row, column);
        }
    }
    if (!input) {
        std::cerr << "incomplete bond payload\n";
        return 4;
    }

    MATCHGATE_RBIM_CYLINDER baseline(
        length, circumference, stabilization, 0, false
    );
    const double log_partition = baseline.logZ(
        coupling,
        horizontal,
        vertical,
        baseline.psi_free,
        baseline.psi_free,
        1,
        stabilization
    );
    std::cout << std::setprecision(17) << log_partition << "\n";
    return 0;
}
