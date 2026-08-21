#include "../src/lattice.hpp"
#include "../src/berry.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace cm;

namespace {

using Complex = std::complex<double>;

int failures = 0;

void check(const std::string& name, bool condition, const std::string& detail = "") {
    if (condition) {
        std::cout << "  PASS: " << name << std::endl;
        return;
    }
    std::cerr << "FAIL: " << name;
    if (!detail.empty()) std::cerr << " - " << detail;
    std::cerr << std::endl;
    ++failures;
}

void approx_equal(const std::string& name, double actual, double expected,
                  double tolerance) {
    std::ostringstream detail;
    detail << "actual=" << actual << " expected=" << expected
           << " tolerance=" << tolerance;
    check(name, std::isfinite(actual) && std::abs(actual - expected) <= tolerance,
          detail.str());
}

GroundState spinor(double polar_angle, double azimuth) {
    GroundState state;
    state.dim = 2;
    state.eigenvector = {
        Complex(std::cos(0.5 * polar_angle), 0.0),
        std::polar(std::sin(0.5 * polar_angle), azimuth),
    };
    state.converged = true;
    return state;
}

double transverse_magnetization(const GroundState& state, std::size_t sites) {
    Complex total(0.0, 0.0);
    for (int basis = 0; basis < state.dim; ++basis)
        for (std::size_t site = 0; site < sites; ++site)
            total += std::conj(state.eigenvector[basis])
                   * state.eigenvector[basis ^ (1 << site)];
    check("transverse magnetization is real", std::abs(total.imag()) < 1e-11);
    return total.real();
}

void test_synthetic_fhs_curvature() {
    std::cout << "--- synthetic spinor FHS curvature ---" << std::endl;
    const double polar_angle = 0.7;
    const double azimuth = 0.2;
    const double dpolar = 0.01;
    const double dazimuth = 0.008;
    auto g00 = spinor(polar_angle, azimuth);
    auto g10 = spinor(polar_angle + dpolar, azimuth);
    auto g11 = spinor(polar_angle + dpolar, azimuth + dazimuth);
    auto g01 = spinor(polar_angle, azimuth + dazimuth);

    const auto curvature = fhs_curvature(g00, g10, g11, g01, dpolar, dazimuth);
    const double cell_average =
        (std::cos(polar_angle + dpolar) - std::cos(polar_angle)) / (2.0 * dpolar);
    check("synthetic plaquette valid", curvature.valid);
    approx_equal("FHS sign and area normalization", curvature.F12, cell_average, 3e-5);
    approx_equal("flux equals curvature times oriented area", curvature.flux,
                 curvature.F12 * dpolar * dazimuth, 1e-15);
    approx_equal("physical flux is minus Wilson phase", curvature.flux,
                 -curvature.wilson_phase, 1e-15);

    for (auto& value : g00.eigenvector) value *= std::polar(1.0, 0.3);
    for (auto& value : g10.eigenvector) value *= std::polar(1.0, -0.7);
    for (auto& value : g11.eigenvector) value *= std::polar(1.0, 1.2);
    for (auto& value : g01.eigenvector) value *= std::polar(1.0, -2.1);
    const auto gauge_rotated = fhs_curvature(
        g00, g10, g11, g01, dpolar, dazimuth);
    approx_equal("FHS gauge invariance", gauge_rotated.F12, curvature.F12, 1e-10);

    GroundState orthogonal_a = spinor(0.0, 0.0);
    GroundState orthogonal_b = spinor(M_PI, 0.0);
    const auto singular = fhs_curvature(
        orthogonal_a, orthogonal_b, orthogonal_b, orthogonal_a, dpolar, dazimuth);
    check("zero-overlap plaquette rejected",
          !singular.valid && std::isnan(singular.F12));

    bool zero_area_rejected = false;
    try {
        (void)fhs_curvature(g00, g10, g11, g01, 0.0, dazimuth);
    } catch (const std::invalid_argument&) {
        zero_area_rejected = true;
    }
    check("zero-area plaquette rejected", zero_area_rejected);
}

void test_rotated_hamiltonian_identity() {
    std::cout << "--- rotated Hamiltonian identity ---" << std::endl;
    const auto lattice = make_chain(2);
    const double J = 0.73;
    const double omega = 1.17;
    const double theta = 0.41;
    const int dimension = 1 << static_cast<int>(lattice.N);
    const auto unrotated = build_kolodrubetz_hamiltonian(lattice, J, omega, 0.0);
    const auto rotated = build_kolodrubetz_hamiltonian(lattice, J, omega, theta);

    std::vector<Complex> unitary(static_cast<std::size_t>(dimension) * dimension);
    const double cosine = std::cos(0.5 * theta);
    const Complex flip(0.0, -std::sin(0.5 * theta));
    for (int row = 0; row < dimension; ++row) {
        for (int column = 0; column < dimension; ++column) {
            Complex amplitude(1.0, 0.0);
            for (std::size_t site = 0; site < lattice.N; ++site) {
                const bool same = ((row >> site) & 1) == ((column >> site) & 1);
                amplitude *= same ? Complex(cosine, 0.0) : flip;
            }
            unitary[row * dimension + column] = amplitude;
        }
    }

    double maximum_error = 0.0;
    double maximum_hermiticity_error = 0.0;
    for (int row = 0; row < dimension; ++row) {
        for (int column = 0; column < dimension; ++column) {
            Complex transformed(0.0, 0.0);
            for (int left = 0; left < dimension; ++left)
                for (int right = 0; right < dimension; ++right)
                    transformed += unitary[row * dimension + left]
                                 * unrotated[left * dimension + right]
                                 * std::conj(unitary[column * dimension + right]);
            maximum_error = std::max(
                maximum_error,
                std::abs(rotated[row * dimension + column] - transformed));
            maximum_hermiticity_error = std::max(
                maximum_hermiticity_error,
                std::abs(rotated[row * dimension + column]
                         - std::conj(rotated[column * dimension + row])));
        }
    }
    check("H(theta) = R_x H(0) R_x^dagger", maximum_error < 1e-12,
          "maximum error=" + std::to_string(maximum_error));
    check("rotated Hamiltonian is Hermitian", maximum_hermiticity_error < 1e-13,
          "maximum error=" + std::to_string(maximum_hermiticity_error));
}

void test_grid_order_and_magnetization_response() {
    std::cout << "--- grid order and magnetization response ---" << std::endl;
    const auto lattice = make_chain(4);
    const double J = 1.0;
    const double theta = 0.23;
    const double omega = 1.6;
    const double dtheta = 0.002;
    const double domega = 0.002;

    ParamGrid grid;
    grid.theta_values = {theta, theta + dtheta};
    grid.omega_values = {omega, omega + domega};
    const auto from_grid = compute_berry_curvature_grid(lattice, J, grid);
    const auto direct = fhs_curvature_single(
        lattice, J, theta, omega, dtheta, domega);
    approx_equal("grid axes map theta then omega", from_grid[0][0].F12,
                 direct.F12, 1e-11);

    const auto lower = solve_ground_state(lattice, J, omega, 0.0);
    const auto upper = solve_ground_state(lattice, J, omega + domega, 0.0);
    const double finite_difference = -0.5
        * (transverse_magnetization(upper, lattice.N)
           - transverse_magnetization(lower, lattice.N)) / domega;
    const auto plaquette = fhs_curvature_single(
        lattice, J, 0.0, omega, dtheta, domega);
    approx_equal("F_thetaOmega = -1/2 d<X>/dOmega", plaquette.F12,
                 finite_difference, 2e-4);
}

void test_jordan_wigner_oracle() {
    std::cout << "--- Jordan-Wigner thermodynamic oracle ---" << std::endl;
    const double exact = tfim_chain_berry_curvature_density_exact(1.0, 1.5);
    check("JW curvature density has fixed negative sign",
          std::isfinite(exact) && exact < 0.0,
          "value=" + std::to_string(exact));
    const double large_field = tfim_chain_berry_curvature_density_exact(1.0, 20.0);
    const double asymptotic = -1.0 / (4.0 * std::pow(20.0, 3));
    approx_equal("JW large-field asymptotic", large_field, asymptotic,
                 0.02 * std::abs(asymptotic));
    check("JW critical point is logarithmically divergent",
          std::isinf(tfim_chain_berry_curvature_density_exact(1.0, 1.0))
          && tfim_chain_berry_curvature_density_exact(1.0, 1.0) < 0.0);
    approx_equal("independent-spin curvature vanishes",
                 tfim_chain_berry_curvature_density_exact(0.0, 1.0), 0.0, 0.0);

    const double expected_values[] = {
        -0.1142859610355, -0.1105501748728,
        -0.1031471502195, -0.09783932245726,
    };
    const std::size_t sizes[] = {4, 6, 8, 10};
    for (std::size_t index = 0; index < 4; ++index)
        approx_equal("finite JW N=" + std::to_string(sizes[index]),
                     tfim_chain_berry_curvature_density_finite(
                         sizes[index], 1.0, 1.5),
                     expected_values[index], 5e-13);

    const auto lattice = make_chain(6);
    const double finite_exact = tfim_chain_berry_curvature_density_finite(
        lattice.N, 1.0, 1.5);
    const auto centered_plaquette = [&lattice](double step) {
        return fhs_curvature_single(
            lattice, 1.0, -0.5 * step, 1.5 - 0.5 * step, step, step);
    };
    const auto coarse = centered_plaquette(0.004);
    const auto medium = centered_plaquette(0.002);
    const auto fine = centered_plaquette(0.001);
    check("finite-chain refinement plaquettes valid",
          coarse.valid && medium.valid && fine.valid);
    const double coarse_error = std::abs(coarse.F12 / lattice.N - finite_exact);
    const double medium_error = std::abs(medium.F12 / lattice.N - finite_exact);
    const double fine_error = std::abs(fine.F12 / lattice.N - finite_exact);
    check("FHS grid refinement approaches finite-size JW oracle",
          medium_error < coarse_error && fine_error < medium_error,
          "coarse=" + std::to_string(coarse_error)
          + " medium=" + std::to_string(medium_error)
          + " fine=" + std::to_string(fine_error));
    check("fine FHS agrees with finite-size JW within discretisation budget",
          fine_error < 3e-4, "error=" + std::to_string(fine_error));

    check("finite JW approaches thermodynamic oracle off criticality",
          std::abs(tfim_chain_berry_curvature_density_finite(
                       64, 1.0, 1.5) - exact) < 1e-10);
}

void test_response_cross_validation() {
    std::cout << "--- response cross-validation: FHS vs ED response vs JW oracle ---" << std::endl;

    // 1D: ED response must match finite-size JW oracle to machine precision
    for (int N : {4, 6}) {
        auto lat = make_chain(N);
        for (double Omega : {0.5, 1.0, 1.5, 2.0}) {
            double resp = compute_berry_curvature_response_ed(lat, 1.0, Omega, 0.1);
            double jw = tfim_chain_berry_curvature_density_finite(N, 1.0, Omega);
            approx_equal("1D N=" + std::to_string(N) + " Omega=" + std::to_string(Omega)
                         + " ED-response vs JW",
                         resp, jw, 1e-12);

            double dtheta = 0.05, dOmega = 0.05;
            auto bc = fhs_curvature_single(lat, 1.0, 0.1, Omega, dtheta, dOmega);
            double fhs = bc.F12 / static_cast<double>(N);
            double diff = std::abs(fhs - resp);
            check("1D N=" + std::to_string(N) + " Omega=" + std::to_string(Omega)
                  + " FHS vs ED-response within discretisation budget",
                  diff < 2e-2, "diff=" + std::to_string(diff));
        }
    }

    // 2D square L=2: FHS vs ED response agreement
    auto sq2 = make_square(2, 2);
    for (double Omega : {1.0, 2.0, 3.0}) {
        double resp = compute_berry_curvature_response_ed(sq2, 1.0, Omega, 0.1);
        double dtheta = 0.05, dOmega = 0.05;
        auto bc = fhs_curvature_single(sq2, 1.0, 0.1, Omega, dtheta, dOmega);
        double fhs = bc.F12 / static_cast<double>(4);
        double diff = std::abs(fhs - resp);
        check("2D L=2 Omega=" + std::to_string(Omega)
              + " FHS vs ED-response within discretisation budget",
              diff < 1e-2, "FHS=" + std::to_string(fhs)
              + " RSP=" + std::to_string(resp) + " diff=" + std::to_string(diff));
    }

    // Theta-independence: F_{θΩ} must be independent of rotation angle
    auto lat4 = make_chain(4);
    double ref = compute_berry_curvature_response_ed(lat4, 1.0, 1.0, 0.0);
    for (double theta : {0.0, 0.3, 0.7, 1.0}) {
        double resp = compute_berry_curvature_response_ed(lat4, 1.0, 1.0, theta);
        approx_equal("theta-independence theta=" + std::to_string(theta),
                     resp, ref, 1e-14);
    }

    // Large system: verify solver correctly rejects N > 6 (dim > 64)
    bool large_rejected = false;
    try {
        auto lat8 = make_chain(8);
        (void)compute_berry_curvature_response_ed(lat8, 1.0, 1.0, 0.0);
    } catch (const std::length_error&) {
        large_rejected = true;
    }
    check("N=8 correctly rejected by ED response solver", large_rejected);
}

void test_berry_input_guards() {
    const auto lattice = make_chain(4);
    bool coupling_rejected = false;
    try {
        (void)build_kolodrubetz_hamiltonian(
            lattice, 1.0, 1.0, std::numeric_limits<double>::quiet_NaN());
    } catch (const std::invalid_argument&) {
        coupling_rejected = true;
    }
    check("non-finite rotated-Hamiltonian angle rejected", coupling_rejected);

    auto g00 = spinor(0.4, 0.1);
    auto g10 = spinor(0.5, 0.1);
    auto g11 = spinor(0.5, 0.2);
    auto g01 = spinor(0.4, 0.2);
    g11.converged = false;
    bool unconverged_rejected = false;
    try {
        (void)fhs_curvature(g00, g10, g11, g01, 0.1, 0.1);
    } catch (const std::runtime_error&) {
        unconverged_rejected = true;
    }
    check("unconverged FHS corner rejected", unconverged_rejected);

    bool odd_size_rejected = false;
    try {
        (void)tfim_chain_berry_curvature_density_finite(5, 1.0, 1.5);
    } catch (const std::invalid_argument&) {
        odd_size_rejected = true;
    }
    check("unsupported odd-size JW sector rejected", odd_size_rejected);
}

} // namespace

int main() {
    try {
        test_synthetic_fhs_curvature();
        test_rotated_hamiltonian_identity();
        test_grid_order_and_magnetization_response();
        test_jordan_wigner_oracle();
        test_response_cross_validation();
        test_berry_input_guards();
    } catch (const std::exception& error) {
        std::cerr << "Exception: " << error.what() << std::endl;
        ++failures;
    }

    std::cout << std::endl;
    if (failures == 0) std::cout << "All Berry-phase tests passed." << std::endl;
    else std::cerr << failures << " test(s) FAILED." << std::endl;
    return failures == 0 ? 0 : 1;
}
