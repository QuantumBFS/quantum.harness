#include "lattice.hpp"
#include <algorithm>
#include <cmath>
#include <set>
#include <sstream>

namespace cm {

// ============================================================
// Lattice::build_site_coords
// ============================================================
void Lattice::build_site_coords() {
    site_coords.resize(N, {0, 0, 0});
    // Default: simple cubic / rectangular tiling.
    // Override for honeycomb and any multi-basis lattice.
}

// ============================================================
// Lattice::verify
// ============================================================
bool Lattice::verify(std::string* diag) const {
    std::ostringstream oss;
    bool ok = true;

    auto fail = [&](const std::string& msg) {
        ok = false;
        if (diag)
            oss << msg << "\n";
    };

    // site count
    if (N == 0)
        fail("N = 0");
    if (bonds.size() != Nb)
        fail("bonds.size() = " + std::to_string(bonds.size()) +
             " != Nb = " + std::to_string(Nb));

    // bond uniqueness and index range
    std::set<std::pair<std::size_t, std::size_t>> bond_set;
    for (const auto& b : bonds) {
        if (b.i >= N || b.j >= N)
            fail("bond (" + std::to_string(b.i) + "," + std::to_string(b.j) +
                 ") out of range N=" + std::to_string(N));
        if (b.i == b.j)
            fail("self-loop at site " + std::to_string(b.i));
        auto p = std::minmax(b.i, b.j);
        if (!bond_set.insert(p).second)
            fail("duplicate bond (" + std::to_string(p.first) + "," +
                 std::to_string(p.second) + ")");
    }

    // coordination
    auto coord = get_coordination();
    for (std::size_t s = 0; s < N; ++s) {
        if (coord[s] != expected_coordination)
            fail("site " + std::to_string(s) + " coordination " +
                 std::to_string(coord[s]) + " expected " +
                 std::to_string(expected_coordination));
    }

    // connectivity (all sites reachable via BFS)
    if (N > 0) {
        std::vector<bool> visited(N, false);
        std::vector<std::size_t> stack{0};
        visited[0] = true;
        while (!stack.empty()) {
            auto v = stack.back();
            stack.pop_back();
            for (const auto& b : bonds) {
                std::size_t nb = (b.i == v) ? b.j : (b.j == v ? b.i : v);
                if (nb != v && !visited[nb]) {
                    visited[nb] = true;
                    stack.push_back(nb);
                }
            }
        }
        for (std::size_t s = 0; s < N; ++s)
            if (!visited[s])
                fail("site " + std::to_string(s) + " disconnected");
    }

    // site coordinates count
    if (!site_coords.empty() && site_coords.size() != N)
        fail("site_coords.size() mismatch");

    if (diag)
        *diag = oss.str();
    return ok;
}

// ============================================================
// Lattice::get_coordination
// ============================================================
std::vector<int> Lattice::get_coordination() const {
    std::vector<int> c(N, 0);
    for (const auto& b : bonds) {
        ++c[b.i];
        ++c[b.j];
    }
    return c;
}

// ============================================================
// Lattice::smallest_momentum
// ============================================================
double Lattice::smallest_momentum() const {
    if (dim == 0) return 0.0;
    double k_min = std::numeric_limits<double>::max();
    // For 2D: scan small multiples of recip_a, recip_b.
    for (int na = -1; na <= 1; ++na) {
        for (int nb = -1; nb <= 1; ++nb) {
            if (na == 0 && nb == 0) continue;
            std::array<double, 3> k = {
                na * recip_a[0] + nb * recip_b[0],
                na * recip_a[1] + nb * recip_b[1],
                0.0
            };
            double kn = std::sqrt(k[0] * k[0] + k[1] * k[1]);
            if (kn > 1e-12 && kn < k_min)
                k_min = kn;
        }
    }
    return (k_min < std::numeric_limits<double>::max()) ? k_min : 0.0;
}

Lattice Lattice::with_permuted_index(const std::vector<std::size_t>& perm) const {
    Lattice out = *this;
    for (auto& b : out.bonds) {
        b.i = perm[b.i];
        b.j = perm[b.j];
    }
    if (!out.site_coords.empty()) {
        for (std::size_t s = 0; s < N; ++s)
            out.site_coords[perm[s]] = site_coords[s];
    }
    return out;
}

// ============================================================
// Factory: 1D chain
// ============================================================
Lattice make_chain(int Lx) {
    if (Lx < 2)
        throw std::invalid_argument("chain Lx must be >= 2");

    Lattice lat;
    lat.name = "chain";
    lat.N = static_cast<std::size_t>(Lx);
    lat.Nb = lat.N;                      // periodic
    lat.dim = 1;
    lat.L = {Lx, 1, 1};
    lat.expected_coordination = 2;

    // prim_vec_a = (1, 0, 0)
    lat.prim_vec_a = {1.0, 0.0, 0.0};
    lat.recip_a = {2.0 * M_PI, 0.0, 0.0};

    for (std::size_t x = 0; x < lat.N; ++x) {
        lat.bonds.push_back({x, (x + 1) % lat.N});
        lat.site_coords.push_back({static_cast<double>(x), 0.0, 0.0});
    }
    return lat;
}

// ============================================================
// Factory: 2D square
// ============================================================
Lattice make_square(int Lx, int Ly) {
    if (Lx < 2 || Ly < 2)
        throw std::invalid_argument("square Lx, Ly must be >= 2");

    Lattice lat;
    lat.name = "square";
    lat.N = static_cast<std::size_t>(Lx) * static_cast<std::size_t>(Ly);
    lat.Nb = 2 * lat.N;                  // right + up bonds
    lat.dim = 2;
    lat.L = {Lx, Ly, 1};
    lat.expected_coordination = 4;

    lat.prim_vec_a = {1.0, 0.0, 0.0};
    lat.prim_vec_b = {0.0, 1.0, 0.0};
    lat.recip_a = {2.0 * M_PI, 0.0, 0.0};
    lat.recip_b = {0.0, 2.0 * M_PI, 0.0};

    auto idx = [Lx, Ly](int x, int y) -> std::size_t {
        return static_cast<std::size_t>((x % Lx + Lx) % Lx) * Ly +
               static_cast<std::size_t>((y % Ly + Ly) % Ly);
    };

    for (int x = 0; x < Lx; ++x) {
        for (int y = 0; y < Ly; ++y) {
            lat.bonds.push_back({idx(x, y), idx(x + 1, y)});         // right
            lat.bonds.push_back({idx(x, y), idx(x, y + 1)});         // up
            lat.site_coords.push_back({static_cast<double>(x),
                                       static_cast<double>(y), 0.0});
        }
    }
    return lat;
}

// ============================================================
// Factory: 2D triangular
// ============================================================
Lattice make_triangular(int Lx, int Ly) {
    if (Lx < 2 || Ly < 2)
        throw std::invalid_argument("triangular Lx, Ly must be >= 2");

    const double sqrt3 = std::sqrt(3.0);

    Lattice lat;
    lat.name = "triangular";
    lat.N = static_cast<std::size_t>(Lx) * static_cast<std::size_t>(Ly);
    lat.Nb = 3 * lat.N;
    lat.dim = 2;
    lat.L = {Lx, Ly, 1};
    lat.expected_coordination = 6;

    lat.prim_vec_a = {1.0, 0.0, 0.0};
    lat.prim_vec_b = {0.5, sqrt3 / 2.0, 0.0};
    // reciprocal: b1 = 2pi (1, -1/sqrt3), b2 = 2pi (0, 2/sqrt3)
    lat.recip_a = {2.0 * M_PI, -2.0 * M_PI / sqrt3, 0.0};
    lat.recip_b = {0.0, 4.0 * M_PI / sqrt3, 0.0};

    auto idx = [Lx, Ly](int x, int y) -> std::size_t {
        return static_cast<std::size_t>((x % Lx + Lx) % Lx) * Ly +
               static_cast<std::size_t>((y % Ly + Ly) % Ly);
    };

    for (int x = 0; x < Lx; ++x) {
        for (int y = 0; y < Ly; ++y) {
            lat.bonds.push_back({idx(x, y), idx(x + 1, y)});         // a1
            lat.bonds.push_back({idx(x, y), idx(x, y + 1)});         // a2
            lat.bonds.push_back({idx(x, y), idx(x + 1, y - 1)});     // a1 - a2
            lat.site_coords.push_back({
                static_cast<double>(x) + 0.5 * static_cast<double>(y),
                sqrt3 / 2.0 * static_cast<double>(y),
                0.0
            });
        }
    }
    return lat;
}

// ============================================================
// Factory: 2D honeycomb
// ============================================================
Lattice make_honeycomb(int Lx, int Ly) {
    if (Lx < 2 || Ly < 2)
        throw std::invalid_argument("honeycomb Lx, Ly must be >= 2");

    const double sqrt3 = std::sqrt(3.0);
    const std::size_t Nuc = static_cast<std::size_t>(Lx) * static_cast<std::size_t>(Ly);

    Lattice lat;
    lat.name = "honeycomb";
    lat.N = 2 * Nuc;                              // two sites per unit cell
    lat.Nb = 3 * Nuc;                             // 3 bonds per unit cell
    lat.dim = 2;
    lat.L = {Lx, Ly, 1};
    lat.expected_coordination = 3;

    lat.prim_vec_a = {1.0, 0.0, 0.0};
    lat.prim_vec_b = {0.5, sqrt3 / 2.0, 0.0};
    lat.recip_a = {2.0 * M_PI, -2.0 * M_PI / sqrt3, 0.0};
    lat.recip_b = {0.0, 4.0 * M_PI / sqrt3, 0.0};

    // Sublattice offsets within unit cell
    const std::array<double, 2> offset_A = {0.0, 0.0};
    const std::array<double, 2> offset_B = {0.0, 1.0 / sqrt3};

    // Index function: site = sub * Nuc + uc
    auto site = [Nuc](int sub, int uc_x, int uc_y, int Lx, int Ly) -> std::size_t {
        int x = (uc_x % Lx + Lx) % Lx;
        int y = (uc_y % Ly + Ly) % Ly;
        std::size_t uc = static_cast<std::size_t>(x) * Ly + static_cast<std::size_t>(y);
        return (sub == 0 ? 0 : Nuc) + uc;
    };

    auto uc_coord = [](int x, int y, double ax, double ay, double bx, double by)
        -> std::array<double, 2> {
        return {x * ax + y * bx, x * ay + y * by};
    };

    // Neighbor vectors: A→B
    // n1 = (0, 0) [B in same cell]; n2 = (-1, 0) [B in cell to left];
    // n3 = (0, -1) [B in cell down]
    const int dn[3][2] = {{0, 0}, {-1, 0}, {0, -1}};

    for (int x = 0; x < Lx; ++x) {
        for (int y = 0; y < Ly; ++y) {
            // A site in this cell
            std::size_t sA = site(0, x, y, Lx, Ly);

            for (int n = 0; n < 3; ++n) {
                int bx = x + dn[n][0];
                int by = y + dn[n][1];
                std::size_t sB = site(1, bx, by, Lx, Ly);
                // Ensure unique edge: sA < sB
                if (sA < sB)
                    lat.bonds.push_back({sA, sB});
                else
                    lat.bonds.push_back({sB, sA});
            }

            // Coords
            auto coord_A = uc_coord(x, y,
                lat.prim_vec_a[0], lat.prim_vec_a[1],
                lat.prim_vec_b[0], lat.prim_vec_b[1]);
            lat.site_coords.push_back({coord_A[0] + offset_A[0],
                                       coord_A[1] + offset_A[1], 0.0});

            auto coord_B = uc_coord(x, y,
                lat.prim_vec_a[0], lat.prim_vec_a[1],
                lat.prim_vec_b[0], lat.prim_vec_b[1]);
            lat.site_coords.push_back({coord_B[0] + offset_B[0],
                                       coord_B[1] + offset_B[1], 0.0});
        }
    }

    // Re-sort site_coords to match the site ordering (A first, then B)
    // Currently was appended in interleaved order — need to fix.
    // Sites are {A_0, B_0, A_1, B_1, ...} but index is A_0...A_{Nuc-1}, B_0...B_{Nuc-1}
    {
        auto sc = lat.site_coords;
        lat.site_coords.clear();
        lat.site_coords.resize(lat.N);
        for (int x = 0; x < Lx; ++x) {
            for (int y = 0; y < Ly; ++y) {
                std::size_t ucidx = static_cast<std::size_t>(x) * Ly + static_cast<std::size_t>(y);
                auto coord_A2 = uc_coord(x, y,
                    lat.prim_vec_a[0], lat.prim_vec_a[1],
                    lat.prim_vec_b[0], lat.prim_vec_b[1]);
                lat.site_coords[ucidx] = {coord_A2[0] + offset_A[0],
                                          coord_A2[1] + offset_A[1], 0.0};
                lat.site_coords[Nuc + ucidx] = {coord_A2[0] + offset_B[0],
                                                coord_A2[1] + offset_B[1], 0.0};
            }
        }
    }

    return lat;
}

} // namespace cm
