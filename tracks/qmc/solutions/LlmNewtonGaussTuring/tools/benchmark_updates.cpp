#include "tfim_sse.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct TauEstimate {
  double value;
  int window;
  bool converged;
};

TauEstimate tau_int_sokal(const std::vector<double>& values) {
  const int count = static_cast<int>(values.size());
  if (count < 20) {
    throw std::invalid_argument("tau_int requires at least 20 measurements");
  }
  const double mean = std::accumulate(values.begin(), values.end(), 0.0) /
                      static_cast<double>(count);
  double variance = 0.0;
  for (const double value : values) {
    const double delta = value - mean;
    variance += delta * delta;
  }
  variance /= static_cast<double>(count);
  if (variance == 0.0) {
    return {0.5, 0, true};
  }

  double tau = 0.5;
  const int maximum_lag = std::min(count / 2, 5000);
  for (int lag = 1; lag <= maximum_lag; ++lag) {
    double covariance = 0.0;
    for (int index = 0; index + lag < count; ++index) {
      covariance += (values[static_cast<std::size_t>(index)] - mean) *
                    (values[static_cast<std::size_t>(index + lag)] - mean);
    }
    covariance /= static_cast<double>(count - lag);
    tau += covariance / variance;
    if (lag >= 3 && static_cast<double>(lag) >= 5.0 * std::max(tau, 0.5)) {
      return {std::max(tau, 0.5), lag, true};
    }
  }
  return {std::max(tau, 0.5), maximum_lag, false};
}

int parse_positive(const char* text, const char* name) {
  const std::string value(text);
  std::size_t consumed = 0;
  const long parsed = std::stol(value, &consumed);
  if (consumed != value.size() || parsed <= 0 || parsed > 1000000000L) {
    throw std::invalid_argument(std::string("invalid ") + name + ": " + value);
  }
  return static_cast<int>(parsed);
}

struct BenchmarkCase {
  tfim::LatticeKind lattice;
  int lx;
  int ly;
  double gamma;
  double beta;
};

void run_case(std::ofstream& output, const BenchmarkCase& problem, int repeats,
              int thermalization, int measurements, std::uint64_t base_seed) {
  constexpr std::array<const char*, 4> observable_names{{"E", "mx", "m2", "m4"}};
  for (const tfim::UpdateKind update :
       {tfim::UpdateKind::Cluster, tfim::UpdateKind::Loop, tfim::UpdateKind::Line}) {
    for (int repeat = 0; repeat < repeats; ++repeat) {
      tfim::Parameters parameters;
      parameters.lattice = problem.lattice;
      parameters.lx = problem.lx;
      parameters.ly = problem.ly;
      parameters.interaction = -1.0;
      parameters.transverse_field = problem.gamma;
      parameters.longitudinal_field = 0.0;
      parameters.beta = problem.beta;
      parameters.thermalization_sweeps = thermalization;
      parameters.measurement_sweeps = measurements;
      parameters.bins = std::min(50, measurements);
      const std::uint64_t update_offset = update == tfim::UpdateKind::Cluster ? 0ULL :
                                          update == tfim::UpdateKind::Loop ? 100000ULL : 200000ULL;
      parameters.seed = base_seed + static_cast<std::uint64_t>(1000 * repeat) + update_offset;
      parameters.update = update;
      parameters.record_sweeps = true;

      tfim::Simulation simulation(parameters);
      const tfim::Results result = simulation.run();
      const double sweep_seconds = result.measurement_seconds /
                                   static_cast<double>(parameters.measurement_sweeps);
      for (std::size_t observable = 0; observable < observable_names.size(); ++observable) {
        const TauEstimate tau = tau_int_sokal(result.sweep_values[observable]);
        const double ess_per_second = 1.0 / (2.0 * tau.value * sweep_seconds);
        output << tfim::update_kind_name(update) << ','
               << tfim::lattice_kind_name(problem.lattice) << ','
               << problem.lx << ',' << problem.ly << ',' << simulation.lattice().sites << ','
               << std::setprecision(12) << problem.gamma << ',' << problem.beta << ','
               << thermalization << ',' << measurements << ',' << parameters.seed << ','
               << (repeat + 1) << ',' << observable_names[observable] << ','
               << result.mean[observable] << ',' << tau.value << ',' << tau.window << ','
               << (tau.converged ? 1 : 0) << ',' << sweep_seconds << ',' << ess_per_second << '\n';
      }
      std::cout << tfim::lattice_kind_name(problem.lattice) << ' '
                << tfim::update_kind_name(update) << " repeat=" << (repeat + 1)
                << " measurement_s=" << result.measurement_seconds << '\n';
    }
  }
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2 || argc > 5) {
    std::cerr << "Usage: " << argv[0]
              << " OUTPUT.csv [repeats=3] [thermalization=5000] [measurements=20000]\n";
    return EXIT_FAILURE;
  }
  try {
    const int repeats = argc >= 3 ? parse_positive(argv[2], "repeats") : 3;
    const int thermalization = argc >= 4 ? parse_positive(argv[3], "thermalization") : 5000;
    const int measurements = argc >= 5 ? parse_positive(argv[4], "measurements") : 20000;
    std::ofstream output(argv[1]);
    if (!output) {
      throw std::runtime_error(std::string("cannot open output: ") + argv[1]);
    }
    output << "algorithm,lattice,lx,ly,sites,Gamma,beta,thermalization_sweeps,"
              "measurement_sweeps,seed,repeat,observable,mean,tau_int,tau_window,"
              "tau_converged,sweep_seconds,ess_per_second\n";
    run_case(output, {tfim::LatticeKind::Triangular, 12, 12, 4.76811, 24.0},
             repeats, thermalization, measurements, 2026073001ULL);
    run_case(output, {tfim::LatticeKind::Honeycomb, 8, 8, 2.13250, 16.0},
             repeats, thermalization, measurements, 2026074001ULL);
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
