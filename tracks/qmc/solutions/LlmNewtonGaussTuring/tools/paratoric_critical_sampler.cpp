#include <paratoric/mcmc/extended_toric_code.hpp>
#include <paratoric/types/types.hpp>

#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <variant>

namespace {

int parse_int(const char* text, const char* name) {
    std::size_t used = 0;
    const int value = std::stoi(text, &used);
    if (text[used] != '\0')
        throw std::invalid_argument(std::string(name) + " must be an integer");
    return value;
}

double parse_double(const char* text, const char* name) {
    std::size_t used = 0;
    const double value = std::stod(text, &used);
    if (text[used] != '\0' || !std::isfinite(value))
        throw std::invalid_argument(std::string(name) + " must be finite");
    return value;
}

std::string dual_gauge_lattice(const std::string& target) {
    if (target == "triangular") return "honeycomb";
    if (target == "honeycomb") return "triangular";
    throw std::invalid_argument("target lattice must be triangular or honeycomb");
}

double real_sample(const paratoric::Result& result, std::size_t observable,
                   std::size_t sample) {
    if (observable >= result.series.size()
        || sample >= result.series[observable].size())
        throw std::runtime_error("ParaToric returned an incomplete observable series");
    if (!std::holds_alternative<double>(result.series[observable][sample]))
        throw std::runtime_error("ParaToric returned a complex value for a real observable");
    return std::get<double>(result.series[observable][sample]);
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 9) {
        std::cerr
            << "usage: paratoric_critical_sampler <triangular|honeycomb> <L> "
               "<target-field> <mu> <seed> <thermal> <samples> <between>\n";
        return 2;
    }

    try {
        const std::string target = argv[1];
        const int L = parse_int(argv[2], "L");
        const double field = parse_double(argv[3], "target-field");
        const double mu = parse_double(argv[4], "mu");
        const int seed = parse_int(argv[5], "seed");
        const int thermal = parse_int(argv[6], "thermal");
        const int samples = parse_int(argv[7], "samples");
        const int between = parse_int(argv[8], "between");
        if (L < 4 || field <= 0.0 || mu <= 0.0 || seed == 0
            || thermal <= 0 || samples <= 1 || between <= 0)
            throw std::invalid_argument(
                "L must be at least four, all other numeric arguments must be "
                "positive, samples must exceed one, and seed must be nonzero");

        const std::string gauge = dual_gauge_lattice(target);
        const double beta = static_cast<double>(L) / field;
        paratoric::Config config;
        config.lat_spec = paratoric::LatSpec{
            'x', gauge, L, beta, "periodic", +1};
        config.param_spec = paratoric::ParamSpec{
            .mu = mu, .h = 1.0, .J = field, .lmbda = 0.0};
        config.sim_spec = paratoric::SimSpec{
            .N_samples = samples,
            .N_thermalization = thermal,
            .N_between_samples = between,
            .N_resamples = 100,
            .custom_therm = false,
            .seed = seed,
            .observables = {
                "percolation_probability", "staggered_imaginary_times", "star_x"}};
        config.out_spec = paratoric::OutSpec{
            .path_out = {}, .paths_out = {}, .folder_name = {},
            .folder_names = {}, .save_snapshots = false,
            .full_time_series = false};

        const paratoric::Result result =
            paratoric::ExtendedToricCode::get_sample(config);
        if (result.series.size() != 3 || result.tau_int.size() != 3)
            throw std::runtime_error("ParaToric returned the wrong observable count");

        std::cout << std::setprecision(17);
        std::cout
            << "raw_schema,target_lattice,gauge_lattice,L,beta,field,mu,seed,"
               "sample,n_thermal,n_samples,updates_between,"
               "percolation_probability,staggered_imaginary_times,star_x,"
               "package_tau_percolation,package_tau_sit,package_tau_star\n";
        for (int sample = 0; sample < samples; ++sample) {
            const double percolation =
                real_sample(result, 0, static_cast<std::size_t>(sample));
            const double sit =
                real_sample(result, 1, static_cast<std::size_t>(sample));
            const double star =
                real_sample(result, 2, static_cast<std::size_t>(sample));
            if ((percolation != 0.0 && percolation != 1.0)
                || !std::isfinite(sit) || std::abs(sit) > 1.0 + 1e-12
                || !std::isfinite(star))
                throw std::runtime_error("ParaToric returned an invalid critical observable");
            std::cout << "challenge148-paratoric-critical-v1," << target << ','
                      << gauge << ',' << L << ',' << beta << ',' << field << ','
                      << mu << ',' << seed << ',' << sample << ',' << thermal << ','
                      << samples << ',' << between << ',' << percolation << ','
                      << sit << ',' << star << ',' << result.tau_int[0] << ','
                      << result.tau_int[1] << ',' << result.tau_int[2] << '\n';
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "paratoric_critical_sampler: " << error.what() << '\n';
        return 1;
    }
}
