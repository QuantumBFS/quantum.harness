#include "lattice.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
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

    // Bond entries are Hamiltonian terms, so parallel edges are legitimate on
    // small periodic tori (for example, the two bonds of an L=2 chain).
    bool bond_indices_valid = true;
    for (const auto& b : bonds) {
        if (b.i >= N || b.j >= N) {
            fail("bond (" + std::to_string(b.i) + "," + std::to_string(b.j) +
                 ") out of range N=" + std::to_string(N));
            bond_indices_valid = false;
            continue;
        }
        if (b.i == b.j)
            fail("self-loop at site " + std::to_string(b.i));
    }

    // coordination
    if (bond_indices_valid) {
        auto coord = get_coordination();
        for (std::size_t s = 0; s < N; ++s) {
            if (coord[s] != expected_coordination)
                fail("site " + std::to_string(s) + " coordination " +
                     std::to_string(coord[s]) + " expected " +
                     std::to_string(expected_coordination));
        }
    }

    // connectivity (all sites reachable via BFS)
    if (N > 0 && bond_indices_valid) {
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
        if (b.i >= N || b.j >= N)
            throw std::out_of_range("bond endpoint outside lattice");
        ++c[b.i];
        ++c[b.j];
    }
    return c;
}

// ============================================================
// Lattice::smallest_momentum
// ============================================================
double Lattice::smallest_momentum() const {
    const auto momenta = smallest_momentum_vectors();
    if (momenta.empty()) return 0.0;
    const auto& k = momenta.front();
    return std::sqrt(k[0] * k[0] + k[1] * k[1] + k[2] * k[2]);
}

std::vector<std::array<double, 3>> Lattice::smallest_momentum_vectors() const {
    if (dim == 0) return {};
    if (dim > 3) throw std::invalid_argument("lattice dimension must be <= 3");

    // Momenta allowed on an La x Lb periodic torus are
    //   k = sum_i (n_i/L_i) b_i,   n_i integers.
    // Let G contain the scaled reciprocal vectors as columns. If |G n| is no
    // larger than an initial basis-vector candidate k0, then
    //   |n| <= ||G^+||_F |k0|.
    // This gives a finite, geometry-dependent search bound and avoids a fixed
    // coefficient window that fails for sufficiently skewed tori.
    const std::array<std::array<double, 3>, 3> reciprocal = {recip_a, recip_b, recip_c};
    std::array<std::array<double, 3>, 3> basis{};
    double k_min = std::numeric_limits<double>::infinity();
    for (std::size_t axis = 0; axis < dim; ++axis) {
        if (L[axis] <= 0)
            throw std::invalid_argument("periodic lattice extent must be positive");
        double norm2 = 0.0;
        for (std::size_t component = 0; component < 3; ++component) {
            basis[axis][component] = reciprocal[axis][component] / static_cast<double>(L[axis]);
            norm2 += basis[axis][component] * basis[axis][component];
        }
        if (norm2 <= 1e-24)
            throw std::invalid_argument("active reciprocal vector is zero");
        k_min = std::min(k_min, std::sqrt(norm2));
    }

    double augmented[3][6] = {};
    for (std::size_t row = 0; row < dim; ++row) {
        for (std::size_t col = 0; col < dim; ++col) {
            for (std::size_t component = 0; component < 3; ++component)
                augmented[row][col] += basis[row][component] * basis[col][component];
        }
        augmented[row][dim + row] = 1.0;
    }
    for (std::size_t col = 0; col < dim; ++col) {
        std::size_t pivot = col;
        for (std::size_t row = col + 1; row < dim; ++row)
            if (std::abs(augmented[row][col]) > std::abs(augmented[pivot][col])) pivot = row;
        if (std::abs(augmented[pivot][col]) <= 1e-18)
            throw std::invalid_argument("reciprocal vectors are linearly dependent");
        if (pivot != col)
            for (std::size_t entry = 0; entry < 2 * dim; ++entry)
                std::swap(augmented[pivot][entry], augmented[col][entry]);
        const double scale = augmented[col][col];
        for (std::size_t entry = 0; entry < 2 * dim; ++entry) augmented[col][entry] /= scale;
        for (std::size_t row = 0; row < dim; ++row) {
            if (row == col) continue;
            const double factor = augmented[row][col];
            for (std::size_t entry = 0; entry < 2 * dim; ++entry)
                augmented[row][entry] -= factor * augmented[col][entry];
        }
    }
    double pseudoinverse_frobenius2 = 0.0;
    for (std::size_t axis = 0; axis < dim; ++axis)
        pseudoinverse_frobenius2 += augmented[axis][dim + axis];
    const int bound = std::max(1, static_cast<int>(
        std::ceil(k_min * std::sqrt(std::max(0.0, pseudoinverse_frobenius2)) + 1e-12)));

    std::vector<std::array<double, 3>> momenta;
    const int b_lower = dim >= 2 ? -bound : 0;
    const int b_upper = dim >= 2 ? bound : 0;
    const int c_lower = dim >= 3 ? -bound : 0;
    const int c_upper = dim >= 3 ? bound : 0;
    for (int na = -bound; na <= bound; ++na) {
        for (int nb = b_lower; nb <= b_upper; ++nb) {
            for (int nc = c_lower; nc <= c_upper; ++nc) {
                if (na == 0 && nb == 0 && nc == 0) continue;
                std::array<double, 3> k = {
                    na * basis[0][0] + nb * basis[1][0] + nc * basis[2][0],
                    na * basis[0][1] + nb * basis[1][1] + nc * basis[2][1],
                    na * basis[0][2] + nb * basis[1][2] + nc * basis[2][2]
                };
                double kn = std::sqrt(k[0] * k[0] + k[1] * k[1] + k[2] * k[2]);
                if (kn <= 1e-12) continue;
                const double tolerance = 1e-10 * std::max(1.0, k_min);
                if (kn < k_min - tolerance) {
                    k_min = kn;
                    momenta.clear();
                    momenta.push_back(k);
                } else if (std::abs(kn - k_min) <= tolerance) {
                    momenta.push_back(k);
                }
            }
        }
    }
    return momenta;
}

Lattice Lattice::with_permuted_index(const std::vector<std::size_t>& perm) const {
    if (perm.size() != N)
        throw std::invalid_argument("permutation size must equal lattice.N");
    std::vector<bool> seen(N, false);
    for (std::size_t value : perm) {
        if (value >= N || seen[value])
            throw std::invalid_argument("permutation must be a bijection on [0,N)");
        seen[value] = true;
    }
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

    lat.prim_vec_a = {0.5, sqrt3 / 2.0, 0.0};
    lat.prim_vec_b = {-0.5, sqrt3 / 2.0, 0.0};
    lat.recip_a = {2.0 * M_PI, 2.0 * M_PI / sqrt3, 0.0};
    lat.recip_b = {-2.0 * M_PI, 2.0 * M_PI / sqrt3, 0.0};

    const std::array<double, 3> offset_B = {0.0, 1.0 / sqrt3, 0.0};
    auto site = [Nuc, Lx, Ly](int sub, int x, int y) -> std::size_t {
        const int wx = (x % Lx + Lx) % Lx;
        const int wy = (y % Ly + Ly) % Ly;
        const std::size_t uc = static_cast<std::size_t>(wx) * Ly + static_cast<std::size_t>(wy);
        return (sub == 0 ? 0 : Nuc) + uc;
    };

    lat.site_coords.resize(lat.N);
    for (int x = 0; x < Lx; ++x) {
        for (int y = 0; y < Ly; ++y) {
            const std::size_t uc = static_cast<std::size_t>(x) * Ly + static_cast<std::size_t>(y);
            const std::array<double, 3> r = {
                x * lat.prim_vec_a[0] + y * lat.prim_vec_b[0],
                x * lat.prim_vec_a[1] + y * lat.prim_vec_b[1],
                0.0
            };
            lat.site_coords[uc] = r;
            lat.site_coords[Nuc + uc] = {r[0] + offset_B[0], r[1] + offset_B[1], 0.0};

            const std::size_t a = site(0, x, y);
            lat.bonds.push_back({a, site(1, x, y)});
            lat.bonds.push_back({a, site(1, x - 1, y)});
            lat.bonds.push_back({a, site(1, x, y - 1)});
        }
    }
    return lat;
}

} // namespace cm
