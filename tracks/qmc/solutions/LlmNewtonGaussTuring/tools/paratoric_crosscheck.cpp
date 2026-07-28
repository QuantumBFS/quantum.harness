#include "ed.hpp"
#include "lattice.hpp"

#include <paratoric/mcmc/extended_toric_code.hpp>
#include <paratoric/types/types.hpp>

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

namespace {

int parse_int(const char* text, const char* name) {
    std::size_t used = 0;
    const int value = std::stoi(text, &used);
    if (text[used] != '\0') throw std::invalid_argument(std::string(name) + " must be an integer");
    return value;
}

double parse_double(const char* text, const char* name) {
    std::size_t used = 0;
    const double value = std::stod(text, &used);
    if (text[used] != '\0' || !std::isfinite(value))
        throw std::invalid_argument(std::string(name) + " must be finite");
    return value;
}

double real_sample(const paratoric::Result& result, std::size_t observable,
                   std::size_t sample) {
    if (observable >= result.series.size() || sample >= result.series[observable].size())
        throw std::runtime_error("ParaToric returned an incomplete observable series");
    if (!std::holds_alternative<double>(result.series[observable][sample]))
        throw std::runtime_error("ParaToric returned a complex value for a real observable");
    return std::get<double>(result.series[observable][sample]);
}

cm::Lattice target_lattice(const std::string& name, int L) {
    if (name == "square") return cm::make_square(L, L);
    if (name == "triangular") return cm::make_triangular(L, L);
    if (name == "honeycomb") return cm::make_honeycomb(L, L);
    throw std::invalid_argument("target lattice must be square, triangular, or honeycomb");
}

std::string dual_gauge_lattice(const std::string& target) {
    if (target == "square") return "square";
    if (target == "triangular") return "honeycomb";
    if (target == "honeycomb") return "triangular";
    throw std::invalid_argument("target lattice must be square, triangular, or honeycomb");
}

void write_row(const std::string& record, const std::string& target,
               const std::string& gauge, int L, std::size_t sites, double beta,
               double field, double mu, int seed, long long index,
               double exchange, double transverse, double star,
               double even_fraction) {
    std::cout << record << ',' << target << ',' << gauge << ',' << L << ','
              << sites << ',' << beta << ',' << field << ',' << mu << ','
              << seed << ',' << index << ',' << exchange << ',' << transverse
              << ',' << exchange + transverse << ',' << star << ','
              << even_fraction << '\n';
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 10) {
        std::cerr << "usage: paratoric_crosscheck <square|triangular|honeycomb> <L> "
                     "<field> <beta> <mu> <seed> <thermal> <samples> <between>\n";
        return 2;
    }

    try {
        const std::string target = argv[1];
        const int L = parse_int(argv[2], "L");
        const double field = parse_double(argv[3], "field");
        const double beta = parse_double(argv[4], "beta");
        const double mu = parse_double(argv[5], "mu");
        const int seed = parse_int(argv[6], "seed");
        const int thermal = parse_int(argv[7], "thermal");
        const int samples = parse_int(argv[8], "samples");
        const int between = parse_int(argv[9], "between");
        if (L < 2 || field <= 0.0 || beta <= 0.0 || mu <= 0.0 || seed == 0
            || thermal <= 0 || samples <= 0 || between <= 0)
            throw std::invalid_argument("all numeric arguments must be positive and seed must be nonzero");

        const cm::Lattice lattice = target_lattice(target, L);
        const std::string gauge = dual_gauge_lattice(target);
        const auto even = cm::compute_parity_thermal_energy(
            lattice, 1.0, field, beta, +1);
        const auto odd = cm::compute_parity_thermal_energy(
            lattice, 1.0, field, beta, -1);
        const double log_scale = std::max(even.log_partition, odd.log_partition);
        const double even_weight = std::exp(even.log_partition - log_scale);
        const double odd_weight = std::exp(odd.log_partition - log_scale);
        const double weight_sum = even_weight + odd_weight;
        const double even_fraction = even_weight / weight_sum;
        const double full_exchange =
            (even_weight * even.exchange_energy + odd_weight * odd.exchange_energy)
            / weight_sum;
        const double full_field =
            (even_weight * even.field_energy + odd_weight * odd.field_energy)
            / weight_sum;

        paratoric::Config config;
        config.lat_spec = paratoric::LatSpec{
            'x', gauge, L, beta, "periodic", +1};
        // H_eTC = -mu sum A_v - field sum B_p - sum sigma^x_e.
        // The local duality gives the target TFIM
        // H = -sum <pq> tau^z_p tau^z_q - field sum_p tau^x_p.  The periodic
        // trace is qualified separately against full-sector ED below.
        config.param_spec = paratoric::ParamSpec{
            .mu = mu, .h = 1.0, .J = field, .lmbda = 0.0};
        config.sim_spec = paratoric::SimSpec{
            .N_samples = samples,
            .N_thermalization = thermal,
            .N_between_samples = between,
            .N_resamples = 100,
            .custom_therm = false,
            .seed = seed,
            .observables = {"energy_h", "energy_J", "star_x"}};
        config.out_spec = paratoric::OutSpec{
            .path_out = {}, .paths_out = {}, .folder_name = {},
            .folder_names = {}, .save_snapshots = false,
            .full_time_series = false};

        const paratoric::Result result =
            paratoric::ExtendedToricCode::get_sample(config);
        if (result.series.size() != 3)
            throw std::runtime_error("ParaToric returned the wrong observable count");

        std::cout << std::setprecision(17);
        std::cout << "record,target_lattice,gauge_lattice,L,N,beta,field,mu,seed,"
                     "sample,exchange_energy,field_energy,total_energy,star_x,"
                     "even_partition_fraction\n";
        write_row("exact_full", target, gauge, L, lattice.N, beta, field, mu,
                  seed, -1, full_exchange, full_field, 1.0, even_fraction);
        write_row("exact_even_diagnostic", target, gauge, L, lattice.N, beta,
                  field, mu, seed, -1, even.exchange_energy, even.field_energy,
                  1.0, even_fraction);
        for (int sample = 0; sample < samples; ++sample) {
            write_row("paratoric", target, gauge, L, lattice.N, beta, field, mu,
                      seed, sample,
                      real_sample(result, 0, static_cast<std::size_t>(sample)),
                      real_sample(result, 1, static_cast<std::size_t>(sample)),
                      real_sample(result, 2, static_cast<std::size_t>(sample)),
                      even_fraction);
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "paratoric_crosscheck: " << error.what() << '\n';
        return 1;
    }
}
