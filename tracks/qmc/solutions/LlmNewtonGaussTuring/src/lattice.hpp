#pragma once

#include <array>
#include <cmath>
#include <cstddef>
#include <string>
#include <stdexcept>
#include <vector>

namespace cm {

// ============================================================
// Bond
// ============================================================
struct Bond {
    std::size_t i;
    std::size_t j;
};

// ============================================================
// Lattice
// ============================================================
struct Lattice {
    std::string name;
    std::size_t N = 0;                       // number of sites
    std::size_t Nb = 0;                      // number of undirected bonds
    std::size_t dim = 0;                     // spatial dimension
    std::array<int, 3> L = {};               // linear sizes {Lx, Ly, Lz}
    // Hamiltonian bonds. Small periodic tori can contain parallel bonds with
    // the same endpoints; each entry is one interaction term.
    std::vector<Bond> bonds;
    std::vector<std::array<double, 3>> site_coords;
    std::array<double, 3> prim_vec_a = {};   // primitive vector a
    std::array<double, 3> prim_vec_b = {};   // primitive vector b
    std::array<double, 3> prim_vec_c = {};   // primitive vector c (2D lattices: zero)
    std::array<double, 3> recip_a = {};      // reciprocal vector a
    std::array<double, 3> recip_b = {};      // reciprocal vector b
    std::array<double, 3> recip_c = {};      // reciprocal vector c
    int expected_coordination = 0;           // coordination number expected

    // Build site coordinates from primitive vectors and L.
    void build_site_coords();

    // Verify invariants and return false with diagnostic on failure.
    bool verify(std::string* diag = nullptr) const;

    // Compute coordination for each site.
    std::vector<int> get_coordination() const;

    // Smallest non-zero reciprocal-lattice momentum.
    double smallest_momentum() const;

    // All symmetry-related shortest non-zero momenta allowed by the periodic
    // torus.  Unlike smallest_momentum(), this retains their directions.
    std::vector<std::array<double, 3>> smallest_momentum_vectors() const;

    // Return a copy with bond indices permuted.  Used to verify index
    // independence of the build.
    Lattice with_permuted_index(const std::vector<std::size_t>& perm) const;
};

// ============================================================
// Factory functions
// ============================================================

// 1D periodic chain: N = Lx, Nb = Lx.
Lattice make_chain(int Lx);

// 2D square lattice: N = Lx * Ly, Nb = 2 * N.
Lattice make_square(int Lx, int Ly);

// 2D triangular lattice: N = Lx * Ly, Nb = 3 * N.
//    prim_a = (1, 0)
//    prim_b = (0.5, sqrt(3)/2)
Lattice make_triangular(int Lx, int Ly);

// 2D honeycomb lattice: two-site basis, N = 2 * Lx * Ly, Nb = 3 * Ly * Lx.
//    prim_a = (1/2, sqrt(3)/2), prim_b = (-1/2, sqrt(3)/2).
//    Sublattice A at (0, 0), sublattice B at (0, 1/sqrt(3)).
Lattice make_honeycomb(int Lx, int Ly);

} // namespace cm
