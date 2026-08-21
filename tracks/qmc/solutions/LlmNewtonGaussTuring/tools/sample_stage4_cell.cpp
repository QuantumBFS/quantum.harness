#include "../src/lattice.hpp"
#include "../src/sse.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

#ifndef CM_BUILD_TYPE
#define CM_BUILD_TYPE "unknown"
#endif
#ifndef CM_CXX_COMPILER_ID
#define CM_CXX_COMPILER_ID "unknown"
#endif
#ifndef CM_CXX_COMPILER_VERSION
#define CM_CXX_COMPILER_VERSION "unknown"
#endif

using namespace cm;

namespace {

constexpr const char* RAW_SCHEMA = "challenge148-raw-v1";

Lattice make_lattice(const std::string& name, int L) {
    if (name == "square") return make_square(L, L);
    if (name == "triangular") return make_triangular(L, L);
    if (name == "honeycomb") return make_honeycomb(L, L);
    throw std::invalid_argument("lattice must be square, triangular, or honeycomb");
}

std::string geometry_version(const std::string& name) {
    if (name == "square") return "square-v1";
    if (name == "triangular") return "triangular-v1";
    if (name == "honeycomb") return "honeycomb-v2";
    throw std::invalid_argument("unsupported lattice");
}

InitialState parse_initial_state(const std::string& value) {
    if (value == "hot") return InitialState::RANDOM;
    if (value == "cold") return InitialState::ORDERED_UP;
    throw std::invalid_argument("initial_state must be hot or cold");
}

int parse_int(const char* text, const char* label) {
    std::size_t parsed = 0;
    const long long value = std::stoll(text, &parsed);
    if (text[parsed] != '\0' || value < std::numeric_limits<int>::min()
        || value > std::numeric_limits<int>::max())
        throw std::invalid_argument(std::string("invalid ") + label);
    return static_cast<int>(value);
}

double parse_double(const char* text, const char* label) {
    std::size_t parsed = 0;
    const double value = std::stod(text, &parsed);
    if (text[parsed] != '\0' || !std::isfinite(value))
        throw std::invalid_argument(std::string("invalid ") + label);
    return value;
}

std::uint64_t parse_seed(const char* text) {
    std::size_t parsed = 0;
    const unsigned long long value = std::stoull(text, &parsed);
    if (text[parsed] != '\0') throw std::invalid_argument("invalid seed");
    return static_cast<std::uint64_t>(value);
}

} // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--build-info") {
        std::cout << "raw_schema=" << RAW_SCHEMA << '\n'
                  << "compiler_id=" << CM_CXX_COMPILER_ID << '\n'
                  << "compiler_version=" << CM_CXX_COMPILER_VERSION << '\n'
                  << "compiler_runtime=" << __VERSION__ << '\n'
                  << "build_type=" << CM_BUILD_TYPE << '\n';
        return 0;
    }
    if (argc != 11) {
        std::cerr << "usage: sample_stage4_cell <lattice> <L> <h> <c_tau> <seed> "
                     "<hot|cold> <thermal> <bins> <sweeps_per_bin> <output.csv>\n";
        return 2;
    }

    try {
        const std::string lattice_name = argv[1];
        const int L = parse_int(argv[2], "L");
        const double h = parse_double(argv[3], "h");
        const double c_tau = parse_double(argv[4], "c_tau");
        const std::uint64_t seed = parse_seed(argv[5]);
        const std::string initial_state = argv[6];
        const int n_thermal = parse_int(argv[7], "thermal");
        const int n_bins = parse_int(argv[8], "bins");
        const int sweeps_per_bin = parse_int(argv[9], "sweeps_per_bin");
        if (L < 2 || h <= 0.0 || c_tau <= 0.0)
            throw std::invalid_argument("require L >= 2, h > 0, and c_tau > 0");

        Lattice lattice = make_lattice(lattice_name, L);
        std::string diagnostic;
        if (!lattice.verify(&diagnostic))
            throw std::runtime_error("invalid lattice: " + diagnostic);

        SSEParams params;
        params.n_thermal = n_thermal;
        params.n_bins = n_bins;
        params.sweeps_per_bin = sweeps_per_bin;
        params.seed = seed;
        params.initial_state = parse_initial_state(initial_state);
        params.progress_every_bins = std::max(1, n_bins / 20);
        params.check_config = false;
        params.census = false;
        params.stage4_estimators = true;

        const double beta = c_tau * static_cast<double>(L) / h;
        SSE solver(lattice, 1.0, h, beta, params);
        const SSEResult result = solver.run();

        std::ofstream output(argv[10]);
        if (!output) throw std::runtime_error("cannot open raw-bin output");
        output << "raw_schema,lattice,geometry_version,L,N,Nb,h,beta,c_tau,seed,"
                  "initial_state,bin,n_thermal,n_bins,sweeps_per_bin,update_algorithm,"
                  "sign_avg,config_checked,consistency_failures,E,equal_m2,equal_m4,"
                  "spacetime_m2,spacetime_m4,S0,Sq,q_norm,q_count\n";
        output << std::setprecision(17);
        const double q_norm = lattice.smallest_momentum();
        const std::size_t q_count = lattice.smallest_momentum_vectors().size();
        for (std::size_t bin = 0; bin < result.bin_E.size(); ++bin) {
            output << RAW_SCHEMA << ',' << lattice_name << ','
                   << geometry_version(lattice_name) << ',' << L << ','
                   << lattice.N << ',' << lattice.Nb << ',' << h << ',' << beta << ','
                   << c_tau << ',' << seed << ',' << initial_state << ',' << bin << ','
                   << n_thermal << ',' << n_bins << ',' << sweeps_per_bin << ','
                   << "sandvik-tfim-cluster-v1" << ',' << result.sign_avg << ','
                   << (result.config_checked ? 1 : 0) << ','
                   << result.consistency_failures << ',' << result.bin_E[bin] << ','
                   << result.bin_m2[bin] << ',' << result.bin_m4[bin] << ','
                   << result.bin_spacetime_m2[bin] << ','
                   << result.bin_spacetime_m4[bin] << ',' << result.bin_S0[bin] << ','
                   << result.bin_Sq[bin] << ',' << q_norm << ',' << q_count << '\n';
        }
        output.close();
        if (!output) throw std::runtime_error("failed while writing raw-bin output");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "sample_stage4_cell: " << error.what() << '\n';
        return 1;
    }
}
