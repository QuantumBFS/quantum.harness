#include "tfim_sse.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct ExactResult {
  double energy = 0.0;
  double mx = 0.0;
  double m2 = 0.0;
};

int spin_at(std::uint64_t state, int site) {
  return ((state >> static_cast<unsigned int>(site)) & 1ULL) == 0ULL ? -1 : 1;
}

// Cyclic Jacobi diagonalization is sufficient for the deliberately small
// finite-temperature oracle clusters (D <= 256) and keeps the build dependency-free.
std::vector<double> diagonalize_symmetric(std::vector<double>& matrix, int dimension) {
  std::vector<double> vectors(static_cast<std::size_t>(dimension * dimension), 0.0);
  for (int index = 0; index < dimension; ++index) {
    vectors[static_cast<std::size_t>(index * dimension + index)] = 1.0;
  }

  constexpr double tolerance = 1.0e-12;
  constexpr int maximum_sweeps = 80;
  for (int sweep = 0; sweep < maximum_sweeps; ++sweep) {
    double maximum_off_diagonal = 0.0;
    for (int first = 0; first < dimension - 1; ++first) {
      for (int second = first + 1; second < dimension; ++second) {
        const std::size_t pq = static_cast<std::size_t>(first * dimension + second);
        const double value = matrix[pq];
        maximum_off_diagonal = std::max(maximum_off_diagonal, std::abs(value));
        if (std::abs(value) < tolerance) {
          continue;
        }
        const double app = matrix[static_cast<std::size_t>(first * dimension + first)];
        const double aqq = matrix[static_cast<std::size_t>(second * dimension + second)];
        const double angle = 0.5 * std::atan2(2.0 * value, aqq - app);
        const double cosine = std::cos(angle);
        const double sine = std::sin(angle);
        for (int row = 0; row < dimension; ++row) {
          if (row == first || row == second) {
            continue;
          }
          const std::size_t rp = static_cast<std::size_t>(row * dimension + first);
          const std::size_t rq = static_cast<std::size_t>(row * dimension + second);
          const double arp = matrix[rp];
          const double arq = matrix[rq];
          matrix[rp] = cosine * arp - sine * arq;
          matrix[rq] = sine * arp + cosine * arq;
          matrix[static_cast<std::size_t>(first * dimension + row)] = matrix[rp];
          matrix[static_cast<std::size_t>(second * dimension + row)] = matrix[rq];
        }
        matrix[static_cast<std::size_t>(first * dimension + first)] =
            cosine * cosine * app - 2.0 * sine * cosine * value + sine * sine * aqq;
        matrix[static_cast<std::size_t>(second * dimension + second)] =
            sine * sine * app + 2.0 * sine * cosine * value + cosine * cosine * aqq;
        matrix[pq] = 0.0;
        matrix[static_cast<std::size_t>(second * dimension + first)] = 0.0;
        for (int row = 0; row < dimension; ++row) {
          const std::size_t vp = static_cast<std::size_t>(row * dimension + first);
          const std::size_t vq = static_cast<std::size_t>(row * dimension + second);
          const double old_vp = vectors[vp];
          const double old_vq = vectors[vq];
          vectors[vp] = cosine * old_vp - sine * old_vq;
          vectors[vq] = sine * old_vp + cosine * old_vq;
        }
      }
    }
    if (maximum_off_diagonal < tolerance) {
      std::vector<double> eigenvalues(static_cast<std::size_t>(dimension));
      for (int index = 0; index < dimension; ++index) {
        eigenvalues[static_cast<std::size_t>(index)] =
            matrix[static_cast<std::size_t>(index * dimension + index)];
      }
      matrix.swap(vectors);
      return eigenvalues;
    }
  }
  throw std::runtime_error("Jacobi ED did not converge");
}

ExactResult exact_thermal_result(const tfim::Lattice& lattice, double interaction,
                                 double transverse_field, double longitudinal_field,
                                 double beta) {
  if (lattice.sites >= 31) {
    throw std::invalid_argument("dense ED oracle requires fewer than 31 sites");
  }
  const int dimension = 1 << lattice.sites;
  std::vector<double> hamiltonian(static_cast<std::size_t>(dimension * dimension), 0.0);
  for (int state = 0; state < dimension; ++state) {
    double diagonal = 0.0;
    for (const tfim::Bond& bond : lattice.bonds) {
      diagonal += interaction * static_cast<double>(spin_at(static_cast<std::uint64_t>(state), bond.first) *
                                                     spin_at(static_cast<std::uint64_t>(state), bond.second));
    }
    for (int site = 0; site < lattice.sites; ++site) {
      diagonal -= longitudinal_field * static_cast<double>(spin_at(static_cast<std::uint64_t>(state), site));
      const int flipped = state ^ (1 << site);
      hamiltonian[static_cast<std::size_t>(state * dimension + flipped)] -= transverse_field;
    }
    hamiltonian[static_cast<std::size_t>(state * dimension + state)] = diagonal;
  }

  const std::vector<double> eigenvalues = diagonalize_symmetric(hamiltonian, dimension);
  const double minimum_energy = *std::min_element(eigenvalues.begin(), eigenvalues.end());
  std::vector<double> weights(static_cast<std::size_t>(dimension));
  for (int eigenstate = 0; eigenstate < dimension; ++eigenstate) {
    weights[static_cast<std::size_t>(eigenstate)] =
        std::exp(-beta * (eigenvalues[static_cast<std::size_t>(eigenstate)] - minimum_energy));
  }
  const double partition = std::accumulate(weights.begin(), weights.end(), 0.0);

  ExactResult result;
  for (int eigenstate = 0; eigenstate < dimension; ++eigenstate) {
    const double weight = weights[static_cast<std::size_t>(eigenstate)] / partition;
    result.energy += weight * eigenvalues[static_cast<std::size_t>(eigenstate)] /
                     static_cast<double>(lattice.sites);
    double mx = 0.0;
    double m2 = 0.0;
    for (int state = 0; state < dimension; ++state) {
      const double amplitude = hamiltonian[static_cast<std::size_t>(state * dimension + eigenstate)];
      int magnetization_sum = 0;
      for (int site = 0; site < lattice.sites; ++site) {
        magnetization_sum += spin_at(static_cast<std::uint64_t>(state), site);
        const int flipped = state ^ (1 << site);
        mx += amplitude * hamiltonian[static_cast<std::size_t>(flipped * dimension + eigenstate)];
      }
      const double magnetization = static_cast<double>(magnetization_sum) /
                                   static_cast<double>(lattice.sites);
      m2 += amplitude * amplitude * magnetization * magnetization;
    }
    result.mx += weight * mx / static_cast<double>(lattice.sites);
    result.m2 += weight * m2;
  }
  return result;
}

struct ValidationCase {
  tfim::LatticeKind lattice;
  int lx;
  int ly;
  double gamma;
};

void validate_case(std::ofstream& output, const ValidationCase& check, std::uint64_t seed) {
  constexpr double beta = 2.0;
  const tfim::Lattice lattice = tfim::build_lattice(check.lattice, check.lx, check.ly);
  const ExactResult exact = exact_thermal_result(lattice, -1.0, check.gamma, 0.0, beta);
  constexpr std::array<const char*, 3> names{{"E", "mx", "m2"}};
  const std::array<double, 3> exact_values{{exact.energy, exact.mx, exact.m2}};
  for (const tfim::UpdateKind update :
       {tfim::UpdateKind::Cluster, tfim::UpdateKind::Loop, tfim::UpdateKind::Line}) {
    tfim::Parameters parameters;
    parameters.lattice = check.lattice;
    parameters.lx = check.lx;
    parameters.ly = check.ly;
    parameters.interaction = -1.0;
    parameters.transverse_field = check.gamma;
    parameters.longitudinal_field = 0.0;
    parameters.beta = beta;
    parameters.thermalization_sweeps = 5000;
    parameters.measurement_sweeps = 20000;
    parameters.bins = 50;
    const std::uint64_t update_offset = update == tfim::UpdateKind::Cluster ? 0ULL :
                                        update == tfim::UpdateKind::Loop ? 100000ULL : 200000ULL;
    parameters.seed = seed + update_offset;
    parameters.update = update;
    parameters.check_configuration = true;
    tfim::Simulation simulation(parameters);
    const tfim::Results qmc = simulation.run();
    for (std::size_t observable = 0; observable < names.size(); ++observable) {
      const double sigma = qmc.standard_error[observable];
      const double z_score = sigma > 0.0 ?
          std::abs(qmc.mean[observable] - exact_values[observable]) / sigma :
          std::numeric_limits<double>::infinity();
      const bool pass = z_score <= 4.0;
      output << tfim::update_kind_name(update) << ','
             << tfim::lattice_kind_name(check.lattice) << ','
             << check.lx << ',' << check.ly << ',' << lattice.sites << ','
             << std::setprecision(12) << check.gamma << ',' << beta << ',' << names[observable] << ','
             << exact_values[observable] << ',' << qmc.mean[observable] << ',' << sigma << ','
             << z_score << ',' << (pass ? 1 : 0) << '\n';
      if (!pass) {
        throw std::runtime_error(std::string("ED validation failed for ") +
                                 tfim::update_kind_name(update) + " " + names[observable]);
      }
    }
    std::cout << tfim::lattice_kind_name(check.lattice) << ' '
              << tfim::update_kind_name(update) << " passed ED comparison\n" << std::flush;
  }
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "Usage: " << argv[0] << " OUTPUT.csv\n";
    return EXIT_FAILURE;
  }
  try {
    std::ofstream output(argv[1]);
    if (!output) {
      throw std::runtime_error(std::string("cannot open output: ") + argv[1]);
    }
    output << "algorithm,lattice,lx,ly,sites,Gamma,beta,observable,exact,qmc_mean,"
              "qmc_stderr,z_score,pass\n";
    validate_case(output, {tfim::LatticeKind::Triangular, 3, 2, 4.76811}, 2026073101ULL);
    validate_case(output, {tfim::LatticeKind::Honeycomb, 2, 2, 2.13250}, 2026074101ULL);
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
