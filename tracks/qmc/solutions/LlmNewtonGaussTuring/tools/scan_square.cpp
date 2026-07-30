// Stage 3 square-lattice benchmark scan.
//
// Scans the periodic square-lattice TFIM over (L, h) at beta = c_beta * L,
// computes diagnostic per-chain estimates of Q_L = <m^2>^2/<m^4> and xi_L/L,
// and locates approximate (L, L') crossings near h_c/J = 3.04438(2).
//
// Raw bin-level data are the authoritative output.  analyze_crossings.py
// performs chain plus circular-block bootstrap for formal uncertainties.

#include "../src/lattice.hpp"
#include "../src/sse.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

using namespace cm;

namespace {

struct Cell {
    int L; double h; double beta; std::uint64_t seed;
    SSEResult result;
    // results
    double Q = 0, xi = 0, E = 0, m2 = 0;
    bool config_checked = false;
    int bad = -1;

    Cell(int linear_size, double field, double inverse_temperature,
         std::uint64_t random_seed)
        : L(linear_size), h(field), beta(inverse_temperature), seed(random_seed) {}
};

double mean(const std::vector<double>& values) {
    double total = 0.0;
    for (double value : values) total += value;
    return total / std::max<std::size_t>(values.size(), 1);
}

void run_cell(Cell& c, int n_thermal, int n_bins, int sweeps_per_bin) {
    Lattice lat = make_square(c.L, c.L);
    SSEParams p;
    p.n_thermal = n_thermal; p.n_bins = n_bins; p.sweeps_per_bin = sweeps_per_bin;
    p.seed = c.seed;
    p.check_config = false;   // validated in the test suite; O(M) per sweep
    p.census = false;
    SSE sse(lat, 1.0, c.h, c.beta, p);
    c.result = sse.run();

    const double qmin = lat.smallest_momentum();
    const double denom = 4.0 * std::pow(std::sin(qmin / 2.0), 2);
    const double Ld = static_cast<double>(c.L);
    const double m2 = mean(c.result.bin_m2);
    const double m4 = mean(c.result.bin_m4);
    const double s0 = mean(c.result.bin_S0);
    const double sq = mean(c.result.bin_Sq);
    c.Q = m4 > 1e-30 ? m2 * m2 / m4 : 0.0;
    const double xi2 = sq > 1e-30 ? (s0 / sq - 1.0) / denom : 0.0;
    c.xi = xi2 > 0.0 ? std::sqrt(xi2) / Ld : 0.0;
    c.E = mean(c.result.bin_E);
    c.m2 = c.result.m2;
    c.config_checked = c.result.config_checked;
    c.bad = c.result.consistency_failures;
}

unsigned default_thread_count() {
    const unsigned available = std::thread::hardware_concurrency();
    return available > 2 ? available - 2 : 1;
}

std::uint64_t square_seed(int L, std::size_t field_index, std::uint64_t replica) {
    return 1000000000000ULL + static_cast<std::uint64_t>(L) * 100000000ULL
         + static_cast<std::uint64_t>(field_index) * 1000ULL + replica;
}

// Linear fit y = a + b*(h - h0) over the scanned window, per size.
struct LinFit { double a, b; };
LinFit linfit(const std::vector<double>& h, const std::vector<double>& y,
              const std::vector<double>& e, double h0) {
    double Sw = 0, Sx = 0, Sy = 0, Sxx = 0, Sxy = 0;
    for (std::size_t k = 0; k < h.size(); ++k) {
        double w = (e[k] > 0) ? 1.0 / (e[k] * e[k]) : 1.0;
        double x = h[k] - h0;
        Sw += w; Sx += w * x; Sy += w * y[k];
        Sxx += w * x * x; Sxy += w * x * y[k];
    }
    double det = Sw * Sxx - Sx * Sx;
    if (std::abs(det) < 1e-300) return {0, 0};
    return {(Sxx * Sy - Sx * Sxy) / det, (Sw * Sxy - Sx * Sy) / det};
}

} // namespace

int main(int argc, char** argv) {
    // pilot configuration:
    //   scan_square <n_thermal> <n_bins> <sweeps_per_bin> <threads> <c_beta> <tag>
    int n_thermal = (argc > 1) ? std::atoi(argv[1]) : 20000;
    int n_bins = (argc > 2) ? std::atoi(argv[2]) : 200;
    int spb = (argc > 3) ? std::atoi(argv[3]) : 50;
    double c_beta = (argc > 5) ? std::atof(argv[5]) : 1.0;  // beta = c_beta * L
    std::string tag = (argc > 6) ? argv[6] : "";
    int maxL = (argc > 7) ? std::atoi(argv[7]) : 1000;
    if (n_thermal < 0 || n_bins <= 0 || spb <= 0 || !(c_beta > 0.0) || maxL < 2) {
        std::cerr << "scan_square: invalid sampling or size arguments\n";
        return 2;
    }

    std::vector<int> Ls;
    for (int L : {4, 6, 8, 10, 12, 16}) if (L <= maxL) Ls.push_back(L);
    const std::vector<double> hs = {2.90, 2.95, 3.00, 3.02, 3.04, 3.06, 3.08, 3.12, 3.18};
    if (Ls.empty()) {
        std::cerr << "scan_square: maxL excludes every configured size\n";
        return 2;
    }
    const std::vector<std::uint64_t> replicas = {101, 202, 303, 404};
    const double h_ref = 3.04438;           // published square-lattice h_c/J

    std::vector<Cell> cells;
    for (int L : Ls)
        for (std::size_t field_index = 0; field_index < hs.size(); ++field_index)
            for (std::uint64_t replica : replicas)
                cells.emplace_back(L, hs[field_index], c_beta * L,
                                   square_seed(L, field_index, replica));

    std::cerr << "cells=" << cells.size()
              << "  thermal=" << n_thermal << " bins=" << n_bins
              << " sweeps/bin=" << spb << "\n";

    std::ofstream raw("square_bins" + tag + ".csv");
    if (!raw) {
        std::cerr << "scan_square: cannot open raw-bin output\n";
        return 1;
    }
    raw << "L,h,beta,seed,bin,config_checked,consistency_failures,E,m2,m4,S0,Sq\n";
    raw << std::setprecision(17);

    const int requested_threads = argc > 4 ? std::atoi(argv[4]) : 0;
    unsigned nthreads = argc > 4
        ? static_cast<unsigned>(std::max(1, requested_threads))
        : default_thread_count();
    std::cerr << "threads=" << nthreads << "\n";
    std::atomic<std::size_t> next{0};
    std::atomic<std::size_t> done{0};
    std::exception_ptr worker_error;
    std::mutex error_mutex;
    std::vector<std::thread> pool;
    for (unsigned t = 0; t < nthreads; ++t) {
        pool.emplace_back([&] {
            for (;;) {
                std::size_t k = next++;
                if (k >= cells.size()) break;
                try {
                    run_cell(cells[k], n_thermal, n_bins, spb);
                } catch (...) {
                    std::lock_guard<std::mutex> lock(error_mutex);
                    if (!worker_error) worker_error = std::current_exception();
                    break;
                }
                std::size_t d = ++done;
                if (d % 10 == 0) std::cerr << "  " << d << "/" << cells.size() << "\n";
            }
        });
    }
    for (auto& th : pool) th.join();
    if (worker_error) {
        try {
            std::rethrow_exception(worker_error);
        } catch (const std::exception& error) {
            std::cerr << "scan_square worker: " << error.what() << '\n';
            return 1;
        }
    }
    for (const auto& cell : cells)
        for (std::size_t bin = 0; bin < cell.result.bin_m2.size(); ++bin)
            raw << cell.L << ',' << cell.h << ',' << cell.beta << ',' << cell.seed << ','
                << bin << ',' << (cell.config_checked ? 1 : 0) << ',' << cell.bad << ','
                << cell.result.bin_E[bin] << ',' << cell.result.bin_m2[bin] << ','
                << cell.result.bin_m4[bin] << ',' << cell.result.bin_S0[bin] << ','
                << cell.result.bin_Sq[bin] << '\n';
    raw.close();
    if (!raw) {
        std::cerr << "scan_square: failed while writing raw-bin output\n";
        return 1;
    }

    // ---- combine seeds per (L,h) ----
    struct Agg { double Q=0,Q2=0,Qe=0,xi=0,xi2=0,xie=0,E=0,E2=0,Ee=0; int n=0; };
    std::vector<std::vector<Agg>> agg(Ls.size(), std::vector<Agg>(hs.size()));
    for (const auto& c : cells) {
        std::size_t li = std::find(Ls.begin(), Ls.end(), c.L) - Ls.begin();
        std::size_t hi = std::find_if(hs.begin(), hs.end(),
                          [&](double x){ return std::abs(x - c.h) < 1e-12; }) - hs.begin();
        Agg& a = agg[li][hi];
        a.Q += c.Q; a.Q2 += c.Q*c.Q;
        a.xi += c.xi; a.xi2 += c.xi*c.xi;
        a.E += c.E; a.E2 += c.E*c.E; a.n++;
    }
    for (auto& row : agg) for (auto& a : row) {
        if (!a.n) continue;
        const double qsum = a.Q, xisum = a.xi, esum = a.E;
        a.Q = qsum / a.n; a.xi = xisum / a.n; a.E = esum / a.n;
        if (a.n > 1) {
            a.Qe = std::sqrt(std::max(0.0, a.Q2 - qsum*qsum/a.n) / (a.n*(a.n-1.0)));
            a.xie = std::sqrt(std::max(0.0, a.xi2 - xisum*xisum/a.n) / (a.n*(a.n-1.0)));
            a.Ee = std::sqrt(std::max(0.0, a.E2 - esum*esum/a.n) / (a.n*(a.n-1.0)));
        }
    }

    std::ofstream summ("square_summary" + tag + ".csv");
    if (!summ) {
        std::cerr << "scan_square: cannot open summary output\n";
        return 1;
    }
    summ << "L,h,beta,Q,Q_err,xi_over_L,xi_err,E,E_err\n";
    std::cout << std::fixed << std::setprecision(5);
    std::cout << "\n=== square lattice, beta = " << c_beta << "*L ===\n";
    for (std::size_t li = 0; li < Ls.size(); ++li) {
        std::cout << "L=" << Ls[li] << "\n";
        for (std::size_t hi = 0; hi < hs.size(); ++hi) {
            const Agg& a = agg[li][hi];
            std::cout << "   h=" << hs[hi]
                      << "  Q=" << a.Q << " +/- " << a.Qe
                      << "   xi/L=" << a.xi << " +/- " << a.xie
                      << "   E=" << a.E << "\n";
            summ << Ls[li] << ',' << hs[hi] << ',' << c_beta*Ls[li] << ','
                 << a.Q << ',' << a.Qe << ',' << a.xi << ',' << a.xie << ','
                 << a.E << ',' << a.Ee << '\n';
        }
    }
    summ.close();

    // ---- crossings between successive sizes ----
    auto crossings = [&](const char* label, bool useQ) {
        std::cout << "\n--- " << label << " crossings (linear fit near h_ref) ---\n";
        for (std::size_t li = 0; li + 1 < Ls.size(); ++li) {
            std::vector<double> hv, y1, e1, y2, e2;
            for (std::size_t hi = 0; hi < hs.size(); ++hi) {
                if (std::abs(hs[hi] - h_ref) > 0.09) continue;   // local window
                hv.push_back(hs[hi]);
                y1.push_back(useQ ? agg[li][hi].Q  : agg[li][hi].xi);
                e1.push_back(useQ ? agg[li][hi].Qe : agg[li][hi].xie);
                y2.push_back(useQ ? agg[li+1][hi].Q  : agg[li+1][hi].xi);
                e2.push_back(useQ ? agg[li+1][hi].Qe : agg[li+1][hi].xie);
            }
            if (hv.size() < 2) continue;
            LinFit f1 = linfit(hv, y1, e1, h_ref);
            LinFit f2 = linfit(hv, y2, e2, h_ref);
            double db = f2.b - f1.b;
            if (std::abs(db) < 1e-12) continue;
            double hx = h_ref + (f1.a - f2.a) / db;
            std::cout << "   L=" << Ls[li] << " vs " << Ls[li+1]
                      << " :  h_cross = " << hx
                      << "   (published h_c = " << h_ref << ",  diff = "
                      << hx - h_ref << ")\n";
        }
    };
    crossings("Q_L", true);
    crossings("xi_L/L", false);

    const bool configs_checked = std::all_of(
        cells.begin(), cells.end(), [](const Cell& cell) { return cell.config_checked; });
    if (configs_checked) {
        int total_failures = 0;
        for (const auto& cell : cells) total_failures += cell.bad;
        std::cout << "\nconsistency failures: " << total_failures << "\n";
    } else {
        std::cout << "\nconsistency check: not performed\n";
    }
    std::cout << "raw bins -> square_bins" << tag
              << ".csv ; diagnostic summary -> square_summary" << tag << ".csv\n";
    return 0;
}
