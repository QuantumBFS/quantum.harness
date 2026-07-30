#include "tfim_sse.hpp"

#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {

void print_usage(const char* program) {
  std::cerr
      << "Usage: " << program
      << " triangular|honeycomb|square Lx Ly J Gamma B beta "
         "thermalization_sweeps measurement_sweeps seed [Gamma_start] [bins] [cluster|loop|line]\n\n"
      << "Hamiltonian: H = J sum_<ij> sigma_z(i)sigma_z(j)"
         " - B sum_i sigma_z(i) - Gamma sum_i sigma_x(i)\n"
      << "Use J=-1 for the ferromagnetic convention used by this project.\n";
}

int parse_int(const char* text, const char* name) {
  std::size_t consumed = 0;
  const std::string value(text);
  const long parsed = std::stol(value, &consumed);
  if (consumed != value.size() || parsed < static_cast<long>(std::numeric_limits<int>::min()) ||
      parsed > static_cast<long>(std::numeric_limits<int>::max())) {
    throw std::invalid_argument(std::string("invalid ") + name + ": " + value);
  }
  return static_cast<int>(parsed);
}

std::uint64_t parse_seed(const char* text) {
  std::size_t consumed = 0;
  const std::string value(text);
  const unsigned long long parsed = std::stoull(value, &consumed);
  if (consumed != value.size()) {
    throw std::invalid_argument("invalid seed: " + value);
  }
  return static_cast<std::uint64_t>(parsed);
}

double parse_double(const char* text, const char* name) {
  std::size_t consumed = 0;
  const std::string value(text);
  const double parsed = std::stod(value, &consumed);
  if (consumed != value.size()) {
    throw std::invalid_argument(std::string("invalid ") + name + ": " + value);
  }
  return parsed;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--help") {
    print_usage(argv[0]);
    return EXIT_SUCCESS;
  }
  if (argc < 11 || argc > 14) {
    print_usage(argv[0]);
    return EXIT_FAILURE;
  }

  try {
    tfim::Parameters parameters;
    parameters.lattice = tfim::parse_lattice_kind(argv[1]);
    parameters.lx = parse_int(argv[2], "Lx");
    parameters.ly = parse_int(argv[3], "Ly");
    parameters.interaction = parse_double(argv[4], "J");
    parameters.transverse_field = parse_double(argv[5], "Gamma");
    parameters.longitudinal_field = parse_double(argv[6], "B");
    parameters.beta = parse_double(argv[7], "beta");
    parameters.thermalization_sweeps = parse_int(argv[8], "thermalization_sweeps");
    parameters.measurement_sweeps = parse_int(argv[9], "measurement_sweeps");
    parameters.seed = parse_seed(argv[10]);
    if (argc >= 12) {
      parameters.anneal_start_field = parse_double(argv[11], "Gamma_start");
    }
    if (argc >= 13) {
      parameters.bins = parse_int(argv[12], "bins");
    }
    if (argc == 14) {
      parameters.update = tfim::parse_update_kind(argv[13]);
    }

    const auto start = std::chrono::steady_clock::now();
    tfim::Simulation simulation(parameters);
    const tfim::Results results = simulation.run();
    const auto stop = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(stop - start).count();
    const int sweeps = parameters.thermalization_sweeps + parameters.measurement_sweeps;

    std::cout << std::fixed << std::setprecision(6) << results.mean[0] << ','
              << results.standard_error[0] << ',' << results.mean[1] << ','
              << results.standard_error[1] << ',' << results.mean[2] << ','
              << results.standard_error[2] << ',' << results.mean[3] << ','
              << results.standard_error[3] << ',' << results.binder << ','
              << results.binder_standard_error << '\n';
    std::cerr << std::setprecision(12) << "elapsed_seconds=" << seconds
              << " sweeps_per_second=" << static_cast<double>(sweeps) / seconds
              << " worm_steps=" << results.worm_steps
              << " update=" << tfim::update_kind_name(parameters.update)
              << " operators=" << results.operator_count
              << " list_length=" << results.operator_list_length << '\n';
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
