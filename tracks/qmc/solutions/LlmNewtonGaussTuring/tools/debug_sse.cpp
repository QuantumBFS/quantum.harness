#include "../src/lattice.hpp"
#include "../src/ed.hpp"
#include "../src/sse.hpp"
#include <cmath>
#include <iomanip>
#include <iostream>

using namespace cm;

static void probe(const Lattice& lat, double J, double h, double beta, const char* tag) {
    auto ed = compute_thermal_obs(lat, J, h, beta);
    SSEParams p; p.n_thermal = 4000; p.n_bins = 20000; p.sweeps_per_bin = 1; p.seed = 7;
    SSE sse(lat, J, h, beta, p);
    auto res = sse.run();

    std::cout << "=== " << tag << "  N=" << lat.N << " Nb=" << lat.Nb
              << " J=" << J << " h=" << h << " beta=" << beta << "\n";
    std::cout << std::fixed << std::setprecision(5);
    std::cout << "  E    SSE=" << res.energy << "   ED=" << ed.E << "\n";
    std::cout << "  m2   SSE=" << res.m2     << "   ED=" << ed.m2 << "\n";
    std::cout << "  m4   SSE=" << res.m4     << "   ED=" << ed.m4 << "\n";
    std::cout << "  Q    SSE=" << res.Q      << "   ED=" << ed.Q  << "\n";
    std::cout << "  consistency_failures = " << res.consistency_failures << "\n";
    std::cout << "  <n_const>=" << res.n_const_avg
              << "  <n_flip>=" << res.n_flip_avg
              << "  <n_bond>=" << res.n_bond_avg << "\n";
    // Exact SSE identities for this decomposition:
    //   <n_const> = beta*h*N            (H_const = h*1, so <H_const> = h)
    //   <n_flip>  = beta*h*N*<sigma^x>  (not independently pinned here)
    std::cout << "  identity: <n_const> = " << res.n_const_avg
              << "   expected beta*h*N = " << beta * h * lat.N << "\n\n";
}

int main() {
    probe(make_chain(4), 1.0, 0.75, 4.0, "chain");
    probe(make_square(3, 3), 1.0, 3.0, 4.0, "square (worst m2 case)");
    probe(make_square(3, 3), 1.0, 2.0, 4.0, "square");
    return 0;
}
