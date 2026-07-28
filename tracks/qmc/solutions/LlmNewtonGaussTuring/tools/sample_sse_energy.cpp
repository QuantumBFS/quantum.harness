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

using namespace cm;

namespace {

Lattice make_lattice(const std::string& name, int L) {
    if (name == "square") return make_square(L, L);
    if (name == "triangular") return make_triangular(L, L);
    if (name == "honeycomb") return make_honeycomb(L, L);
    throw std::invalid_argument("lattice must be square, triangular, or honeycomb");
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

InitialState parse_initial_state(const std::string& value) {
    if (value == "hot") return InitialState::RANDOM;
    if (value == "cold") return InitialState::ORDERED_UP;
    throw std::invalid_argument("initial_state must be hot or cold");
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 11) {
        std::cerr << "usage: sample_sse_energy <lattice> <L> <field> <beta> <seed> "
                     "<hot|cold> <thermal> <bins> <sweeps_per_bin> <output.csv>\n";
        return 2;
    }

    try {
        const std::string lattice_name = argv[1];
        const int L = parse_int(argv[2], "L");
        const double field = parse_double(argv[3], "field");
        const double beta = parse_double(argv[4], "beta");
        const std::uint64_t seed = parse_seed(argv[5]);
        const std::string initial_state = argv[6];
        const int thermal = parse_int(argv[7], "thermal");
        const int bins = parse_int(argv[8], "bins");
        const int sweeps_per_bin = parse_int(argv[9], "sweeps_per_bin");
        if (L < 2 || field <= 0.0 || beta <= 0.0 || seed == 0)
            throw std::invalid_argument("require L >= 2, field > 0, beta > 0, and nonzero seed");

        const Lattice lattice = make_lattice(lattice_name, L);
        SSEParams params;
        params.n_thermal = thermal;
        params.n_bins = bins;
        params.sweeps_per_bin = sweeps_per_bin;
        params.seed = seed;
        params.initial_state = parse_initial_state(initial_state);
        params.progress_every_bins = std::max(1, bins / 20);
        params.check_config = false;
        params.census = true;
        params.stage4_estimators = false;

        const SSEResult result = SSE(lattice, 1.0, field, beta, params).run();
        if (result.bin_exchange_energy.size() != static_cast<std::size_t>(bins)
            || result.bin_field_energy.size() != static_cast<std::size_t>(bins))
            throw std::runtime_error("SSE did not return per-bin energy components");

        std::ofstream output(argv[10]);
        if (!output) throw std::runtime_error("cannot open raw-bin output");
        output << "raw_schema,method,lattice,L,N,beta,field,seed,initial_state,bin,"
                  "n_thermal,n_bins,sweeps_per_bin,exchange_energy,field_energy,"
                  "component_total,expansion_total,sign_avg\n";
        output << std::setprecision(17);
        for (int bin = 0; bin < bins; ++bin) {
            const double exchange = result.bin_exchange_energy[bin] * lattice.N;
            const double transverse = result.bin_field_energy[bin] * lattice.N;
            output << "challenge148-sse-energy-v1,direct-SSE," << lattice_name << ','
                   << L << ',' << lattice.N << ',' << beta << ',' << field << ','
                   << seed << ',' << initial_state << ',' << bin << ',' << thermal
                   << ',' << bins << ',' << sweeps_per_bin << ',' << exchange << ','
                   << transverse << ',' << exchange + transverse << ','
                   << result.bin_E[bin] * lattice.N << ',' << result.sign_avg << '\n';
        }
        output.close();
        if (!output) throw std::runtime_error("failed while writing raw-bin output");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "sample_sse_energy: " << error.what() << '\n';
        return 1;
    }
}
