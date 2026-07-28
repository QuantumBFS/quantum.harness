#include "../src/lattice.hpp"
#include "../src/sse.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <exception>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace cm;

namespace {

struct ScanSpec {
    std::string lattice;
    std::string geometry_version;
    std::vector<int> sizes;
    std::vector<double> fields;
};

struct Cell {
    int L;
    double h;
    double beta;
    std::uint64_t seed;
    SSEResult result;
    double Q = 0.0;
    double xi = 0.0;
    double energy = 0.0;
    int failures = 0;

    Cell(int linear_size, double field, double inverse_temperature,
         std::uint64_t random_seed)
        : L(linear_size), h(field), beta(inverse_temperature), seed(random_seed) {}
};

ScanSpec make_spec(const std::string& lattice) {
    if (lattice == "square") {
        return {
            lattice,
            "square-v1",
            {4, 6, 8, 10, 12, 16},
            {3.00, 3.02, 3.03, 3.04, 3.04438, 3.05, 3.06, 3.08, 3.10}
        };
    }
    if (lattice == "triangular") {
        return {
            lattice,
            "triangular-v1",
            {6, 8, 10, 12, 14, 16, 18, 20},
            {4.70, 4.72, 4.74, 4.75, 4.76, 4.77, 4.78, 4.79, 4.80, 4.82, 4.84}
        };
    }
    if (lattice == "honeycomb") {
        return {
            lattice,
            "honeycomb-v2",
            {10, 12, 14, 16, 18, 20},
            {2.08, 2.10, 2.11, 2.12, 2.13, 2.14, 2.15, 2.16, 2.18}
        };
    }
    throw std::invalid_argument("lattice must be square, triangular, or honeycomb");
}

Lattice make_lattice(const std::string& lattice, int L) {
    if (lattice == "square") return make_square(L, L);
    if (lattice == "triangular") return make_triangular(L, L);
    return make_honeycomb(L, L);
}

double ratio(const std::vector<double>& second, const std::vector<double>& fourth) {
    double m2 = 0.0, m4 = 0.0;
    for (double value : second) m2 += value;
    for (double value : fourth) m4 += value;
    m2 /= std::max<std::size_t>(second.size(), 1);
    m4 /= std::max<std::size_t>(fourth.size(), 1);
    return m2 * m2 / std::max(m4, 1e-30);
}

double xi_over_L(const SSEResult& result, const Lattice& lattice) {
    double s0 = 0.0, sq = 0.0;
    for (double value : result.bin_S0) s0 += value;
    for (double value : result.bin_Sq) sq += value;
    s0 /= std::max<std::size_t>(result.bin_S0.size(), 1);
    sq /= std::max<std::size_t>(result.bin_Sq.size(), 1);
    const double qmin = lattice.smallest_momentum();
    const double denom = 4.0 * std::pow(std::sin(qmin / 2.0), 2);
    if (sq <= 1e-30 || denom <= 1e-30) return 0.0;
    const double xi2 = (s0 / sq - 1.0) / denom;
    return xi2 > 0.0 ? std::sqrt(xi2) / lattice.L[0] : 0.0;
}

void run_cell(const ScanSpec& spec, Cell& cell, int n_thermal, int n_bins,
              int sweeps_per_bin) {
    Lattice lattice = make_lattice(spec.lattice, cell.L);
    std::string diagnostic;
    if (!lattice.verify(&diagnostic))
        throw std::runtime_error("invalid lattice: " + diagnostic);

    SSEParams params;
    params.n_thermal = n_thermal;
    params.n_bins = n_bins;
    params.sweeps_per_bin = sweeps_per_bin;
    params.seed = cell.seed;
    params.check_config = false;
    params.census = false;
    params.stage4_estimators = true;

    SSE sse(lattice, 1.0, cell.h, cell.beta, params);
    cell.result = sse.run();
    cell.Q = ratio(cell.result.bin_spacetime_m2, cell.result.bin_spacetime_m4);
    cell.xi = xi_over_L(cell.result, lattice);
    cell.energy = cell.result.energy;
    cell.failures = cell.result.consistency_failures;
}

unsigned default_thread_count() {
    const unsigned available = std::thread::hardware_concurrency();
    return available > 2 ? available - 2 : 1;
}

std::uint64_t cell_seed(const std::string& lattice, int L,
                        std::size_t field_index, std::uint64_t replica) {
    const std::uint64_t lattice_id = lattice == "square" ? 1 : (lattice == "triangular" ? 2 : 3);
    return lattice_id * 1000000000000ULL
         + static_cast<std::uint64_t>(L) * 100000000ULL
         + static_cast<std::uint64_t>(field_index) * 1000ULL
         + replica;
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: scan_stage4 <square|triangular|honeycomb> "
                     "[thermal] [bins] [sweeps_per_bin] [threads] [tag] [max_L] [min_L]\n";
        return 2;
    }

    try {
        ScanSpec spec = make_spec(argv[1]);
        const int n_thermal = argc > 2 ? std::atoi(argv[2]) : 10000;
        const int n_bins = argc > 3 ? std::atoi(argv[3]) : 200;
        const int sweeps_per_bin = argc > 4 ? std::atoi(argv[4]) : 50;
        unsigned n_threads = argc > 5
            ? static_cast<unsigned>(std::max(1, std::atoi(argv[5])))
            : default_thread_count();
        const std::string tag = argc > 6 ? argv[6] : "";
        const int max_L = argc > 7 ? std::atoi(argv[7]) : 20;
        const int min_L = argc > 8 ? std::atoi(argv[8]) : 0;
        if (n_thermal < 0 || n_bins <= 0 || sweeps_per_bin <= 0)
            throw std::invalid_argument("thermal must be >= 0; bins and sweeps_per_bin must be > 0");
        if (min_L < 0 || max_L < min_L)
            throw std::invalid_argument("require 0 <= min_L <= max_L");

        spec.sizes.erase(
            std::remove_if(spec.sizes.begin(), spec.sizes.end(),
                           [min_L, max_L](int L) { return L < min_L || L > max_L; }),
            spec.sizes.end());
        if (spec.sizes.empty()) throw std::invalid_argument("max_L excludes every historical size");

        const std::vector<std::uint64_t> replicas = {101, 202, 303, 404};
        std::vector<Cell> cells;
        for (int L : spec.sizes)
            for (std::size_t field_index = 0; field_index < spec.fields.size(); ++field_index)
                for (std::uint64_t replica : replicas) {
                    const double h = spec.fields[field_index];
                    cells.emplace_back(
                        L, h, static_cast<double>(L) / h,
                        cell_seed(spec.lattice, L, field_index, replica));
                }

        const std::string stem = spec.lattice + "_stage4" + tag;
        std::ofstream raw(stem + "_bins.csv");
        if (!raw) throw std::runtime_error("cannot open raw-bin output");
        raw << "lattice,geometry_version,L,N,Nb,h,beta,seed,bin,n_thermal,n_bins,sweeps_per_bin,"
               "E,equal_m2,equal_m4,"
               "spacetime_m2,spacetime_m4,S0,Sq,q_norm,q_count\n";
        raw << std::setprecision(17);

        std::ofstream geometry(stem + "_geometry.csv");
        if (!geometry) throw std::runtime_error("cannot open geometry output");
        geometry << "lattice,geometry_version,L,N,Nb,coordination,prim_a_x,prim_a_y,"
                    "prim_b_x,prim_b_y,recip_a_x,recip_a_y,recip_b_x,recip_b_y,"
                    "basis_a_x,basis_a_y,basis_b_x,basis_b_y\n";
        geometry << std::setprecision(17);
        std::ofstream momenta(stem + "_momenta.csv");
        if (!momenta) throw std::runtime_error("cannot open momentum output");
        momenta << "lattice,geometry_version,L,q_index,q_x,q_y,q_z,q_norm\n";
        momenta << std::setprecision(17);
        for (int L : spec.sizes) {
            const Lattice lattice = make_lattice(spec.lattice, L);
            const std::size_t basis_b = spec.lattice == "honeycomb"
                ? static_cast<std::size_t>(L) * L : 0;
            const double nan = std::numeric_limits<double>::quiet_NaN();
            geometry << spec.lattice << ',' << spec.geometry_version << ',' << L << ','
                     << lattice.N << ',' << lattice.Nb << ',' << lattice.expected_coordination << ','
                     << lattice.prim_vec_a[0] << ',' << lattice.prim_vec_a[1] << ','
                     << lattice.prim_vec_b[0] << ',' << lattice.prim_vec_b[1] << ','
                     << lattice.recip_a[0] << ',' << lattice.recip_a[1] << ','
                     << lattice.recip_b[0] << ',' << lattice.recip_b[1] << ','
                     << lattice.site_coords[0][0] << ',' << lattice.site_coords[0][1] << ','
                     << (spec.lattice == "honeycomb" ? lattice.site_coords[basis_b][0] : nan) << ','
                     << (spec.lattice == "honeycomb" ? lattice.site_coords[basis_b][1] : nan) << '\n';
            const auto qvectors = lattice.smallest_momentum_vectors();
            for (std::size_t q = 0; q < qvectors.size(); ++q) {
                const double qnorm = std::sqrt(qvectors[q][0] * qvectors[q][0]
                                             + qvectors[q][1] * qvectors[q][1]
                                             + qvectors[q][2] * qvectors[q][2]);
                momenta << spec.lattice << ',' << spec.geometry_version << ',' << L << ',' << q << ','
                        << qvectors[q][0] << ',' << qvectors[q][1] << ',' << qvectors[q][2] << ','
                        << qnorm << '\n';
            }
        }

        std::cerr << "lattice=" << spec.lattice << " geometry=" << spec.geometry_version
                  << " cells=" << cells.size() << " threads=" << n_threads
                  << " thermal=" << n_thermal << " bins=" << n_bins
                  << " sweeps/bin=" << sweeps_per_bin << std::endl;

        std::atomic<std::size_t> next{0}, done{0};
        std::exception_ptr worker_error;
        std::mutex error_mutex;
        std::vector<std::thread> pool;
        for (unsigned thread = 0; thread < n_threads; ++thread) {
            pool.emplace_back([&] {
                for (;;) {
                    const std::size_t index = next++;
                    if (index >= cells.size()) break;
                    try {
                        run_cell(spec, cells[index], n_thermal, n_bins, sweeps_per_bin);
                    } catch (...) {
                        std::lock_guard<std::mutex> lock(error_mutex);
                        if (!worker_error) worker_error = std::current_exception();
                        break;
                    }
                    const std::size_t completed = ++done;
                    if (completed % 4 == 0 || completed == cells.size())
                        std::cerr << "completed=" << completed << '/' << cells.size() << std::endl;
                }
            });
        }
        for (auto& thread : pool) thread.join();
        if (worker_error) std::rethrow_exception(worker_error);

        for (const Cell& cell : cells) {
            const Lattice lattice = make_lattice(spec.lattice, cell.L);
            const double qnorm = lattice.smallest_momentum();
            const std::size_t qcount = lattice.smallest_momentum_vectors().size();
            for (std::size_t bin = 0; bin < cell.result.bin_E.size(); ++bin) {
                raw << spec.lattice << ',' << spec.geometry_version << ','
                    << cell.L << ',' << lattice.N << ',' << lattice.Nb << ','
                    << cell.h << ',' << cell.beta << ',' << cell.seed << ',' << bin << ','
                    << n_thermal << ',' << n_bins << ',' << sweeps_per_bin << ','
                    << cell.result.bin_E[bin] << ',' << cell.result.bin_m2[bin] << ','
                    << cell.result.bin_m4[bin] << ','
                    << cell.result.bin_spacetime_m2[bin] << ','
                    << cell.result.bin_spacetime_m4[bin] << ','
                    << cell.result.bin_S0[bin] << ',' << cell.result.bin_Sq[bin] << ','
                    << qnorm << ',' << qcount << '\n';
            }
        }
        raw.close();
        if (!raw) throw std::runtime_error("failed while writing raw-bin output");

        std::ofstream summary(stem + "_summary.csv");
        if (!summary) throw std::runtime_error("cannot open summary output");
        summary << "lattice,geometry_version,L,h,beta,seed,Q_spacetime,xi_over_L,E,failures\n";
        summary << std::setprecision(17);
        for (const Cell& cell : cells)
            summary << spec.lattice << ',' << spec.geometry_version << ','
                    << cell.L << ',' << cell.h << ',' << cell.beta << ',' << cell.seed << ','
                    << cell.Q << ',' << cell.xi << ',' << cell.energy << ','
                    << cell.failures << '\n';

        std::cout << "raw=" << stem << "_bins.csv\n"
                  << "summary=" << stem << "_summary.csv\n"
                  << "geometry=" << stem << "_geometry.csv\n"
                  << "momenta=" << stem << "_momenta.csv\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "scan_stage4: " << error.what() << '\n';
        return 1;
    }
}
