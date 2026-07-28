// Stage 3 square-lattice benchmark scan.
//
// Scans the periodic square-lattice TFIM over (L, h) at beta = c_beta * L,
// computes the registered dimensionless observables Q_L = <m^2>^2/<m^4> and
// xi_L/L with jackknife errors over raw bins, and locates the (L, L') crossings
// that should sit at the published h_c/J = 3.04438(2).
//
// Raw bin-level data are written to CSV; the crossing analysis reads only the
// per-cell estimates and their jackknife errors.

#include "../src/lattice.hpp"
#include "../src/sse.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
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
    int L; double h; double beta; int seed;
    // results
    double Q = 0, Qerr = 0, xi = 0, xierr = 0;
    double E = 0, Eerr = 0, m2 = 0;
    int bad = 0;
};

// Jackknife over bins for an arbitrary function of bin-averaged quantities.
template <typename F>
void jackknife(const std::vector<std::vector<double>>& obs, F f,
               double& val, double& err) {
    const std::size_t nb = obs[0].size();
    const std::size_t nq = obs.size();
    std::vector<double> tot(nq, 0.0);
    for (std::size_t q = 0; q < nq; ++q)
        for (std::size_t b = 0; b < nb; ++b) tot[q] += obs[q][b];

    std::vector<double> full(nq);
    for (std::size_t q = 0; q < nq; ++q) full[q] = tot[q] / nb;
    val = f(full);

    if (nb < 2) { err = 0.0; return; }
    std::vector<double> loo(nq), samples(nb);
    double mean = 0.0;
    for (std::size_t b = 0; b < nb; ++b) {
        for (std::size_t q = 0; q < nq; ++q)
            loo[q] = (tot[q] - obs[q][b]) / (nb - 1);
        samples[b] = f(loo);
        mean += samples[b];
    }
    mean /= nb;
    double var = 0.0;
    for (std::size_t b = 0; b < nb; ++b) var += (samples[b] - mean) * (samples[b] - mean);
    err = std::sqrt(var * (nb - 1) / nb);
}

void run_cell(Cell& c, int n_thermal, int n_bins, int sweeps_per_bin,
              std::ofstream* raw, std::mutex* raw_mu) {
    Lattice lat = make_square(c.L, c.L);
    SSEParams p;
    p.n_thermal = n_thermal; p.n_bins = n_bins; p.sweeps_per_bin = sweeps_per_bin;
    p.seed = c.seed;
    p.check_config = false;   // validated in the test suite; O(M) per sweep
    p.census = false;
    SSE sse(lat, 1.0, c.h, c.beta, p);
    SSEResult r = sse.run();

    const double qmin = lat.smallest_momentum();
    const double denom = 4.0 * std::pow(std::sin(qmin / 2.0), 2);
    const double Ld = static_cast<double>(c.L);

    jackknife({r.bin_m2, r.bin_m4},
              [](const std::vector<double>& v) {
                  return v[1] > 1e-30 ? v[0] * v[0] / v[1] : 0.0;
              }, c.Q, c.Qerr);

    jackknife({r.bin_S0, r.bin_Sq},
              [denom, Ld](const std::vector<double>& v) {
                  if (v[1] < 1e-30) return 0.0;
                  double xi2 = (v[0] / v[1] - 1.0) / denom;
                  return xi2 > 0 ? std::sqrt(xi2) / Ld : 0.0;
              }, c.xi, c.xierr);

    jackknife({r.bin_E},
              [](const std::vector<double>& v) { return v[0]; }, c.E, c.Eerr);

    c.m2 = r.m2;
    c.bad = r.consistency_failures;

    if (raw) {
        std::lock_guard<std::mutex> lk(*raw_mu);
        for (std::size_t b = 0; b < r.bin_m2.size(); ++b)
            (*raw) << c.L << ',' << c.h << ',' << c.beta << ',' << c.seed << ','
                   << b << ',' << r.bin_E[b] << ',' << r.bin_m2[b] << ','
                   << r.bin_m4[b] << ',' << r.bin_S0[b] << ',' << r.bin_Sq[b] << '\n';
    }
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

    std::vector<int> Ls;
    for (int L : {4, 6, 8, 10, 12, 16}) if (L <= maxL) Ls.push_back(L);
    const std::vector<double> hs = {2.90, 2.95, 3.00, 3.02, 3.04, 3.06, 3.08, 3.12, 3.18};
    const std::vector<int> seeds = {101, 202, 303, 404};
    const double h_ref = 3.04438;           // published square-lattice h_c/J

    std::vector<Cell> cells;
    for (int L : Ls)
        for (double h : hs)
            for (int s : seeds)
                cells.push_back({L, h, c_beta * L, s + 1000 * L});

    std::cerr << "cells=" << cells.size()
              << "  thermal=" << n_thermal << " bins=" << n_bins
              << " sweeps/bin=" << spb << "\n";

    std::ofstream raw("square_bins" + tag + ".csv");
    raw << "L,h,beta,seed,bin,E,m2,m4,S0,Sq\n";
    std::mutex raw_mu;

    unsigned nthreads = (argc > 4) ? static_cast<unsigned>(std::atoi(argv[4]))
                                   : std::max(1u, std::thread::hardware_concurrency() - 2);
    if (nthreads < 1) nthreads = 1;
    std::cerr << "threads=" << nthreads << "\n";
    std::atomic<std::size_t> next{0};
    std::atomic<std::size_t> done{0};
    std::vector<std::thread> pool;
    for (unsigned t = 0; t < nthreads; ++t) {
        pool.emplace_back([&] {
            for (;;) {
                std::size_t k = next++;
                if (k >= cells.size()) break;
                run_cell(cells[k], n_thermal, n_bins, spb, &raw, &raw_mu);
                std::size_t d = ++done;
                if (d % 10 == 0) std::cerr << "  " << d << "/" << cells.size() << "\n";
            }
        });
    }
    for (auto& th : pool) th.join();
    raw.close();

    // ---- combine seeds per (L,h) ----
    struct Agg { double Q=0,Qe=0,xi=0,xie=0,E=0,Ee=0; int n=0; };
    std::vector<std::vector<Agg>> agg(Ls.size(), std::vector<Agg>(hs.size()));
    for (const auto& c : cells) {
        std::size_t li = std::find(Ls.begin(), Ls.end(), c.L) - Ls.begin();
        std::size_t hi = std::find_if(hs.begin(), hs.end(),
                          [&](double x){ return std::abs(x - c.h) < 1e-12; }) - hs.begin();
        Agg& a = agg[li][hi];
        a.Q += c.Q; a.Qe += c.Qerr*c.Qerr; a.xi += c.xi; a.xie += c.xierr*c.xierr;
        a.E += c.E; a.Ee += c.Eerr*c.Eerr; a.n++;
    }
    for (auto& row : agg) for (auto& a : row) {
        if (!a.n) continue;
        a.Q /= a.n; a.xi /= a.n; a.E /= a.n;
        a.Qe = std::sqrt(a.Qe)/a.n; a.xie = std::sqrt(a.xie)/a.n; a.Ee = std::sqrt(a.Ee)/a.n;
    }

    std::ofstream summ("square_summary" + tag + ".csv");
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

    int totbad = 0; for (const auto& c : cells) totbad += c.bad;
    std::cout << "\nconsistency failures: " << totbad << "\n";
    std::cout << "raw bins -> square_bins.csv ; summary -> square_summary.csv\n";
    return 0;
}
