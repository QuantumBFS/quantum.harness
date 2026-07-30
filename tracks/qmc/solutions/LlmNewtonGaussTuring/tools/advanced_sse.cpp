#include "tfim_sse.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace tfim {
namespace {

int positive_mod(int value, int modulus) {
  const int remainder = value % modulus;
  return remainder < 0 ? remainder + modulus : remainder;
}

double standard_error(const std::vector<double>& values) {
  if (values.size() < 2U) {
    return 0.0;
  }
  const double count = static_cast<double>(values.size());
  const double mean = std::accumulate(values.begin(), values.end(), 0.0) / count;
  double squared_deviation = 0.0;
  for (const double value : values) {
    const double difference = value - mean;
    squared_deviation += difference * difference;
  }
  return std::sqrt(squared_deviation / ((count - 1.0) * count));
}

}  // namespace

int Lattice::incident_bond(int site, int neighbor_index) const {
  if (site < 0 || site >= sites || neighbor_index < 0 ||
      neighbor_index >= coordination) {
    throw std::out_of_range("incident-bond index out of range");
  }
  return site_bonds[static_cast<std::size_t>(site * coordination + neighbor_index)];
}

LatticeKind parse_lattice_kind(const std::string& name) {
  if (name == "triangular") {
    return LatticeKind::Triangular;
  }
  if (name == "honeycomb") {
    return LatticeKind::Honeycomb;
  }
  if (name == "square") {
    return LatticeKind::Square;
  }
  throw std::invalid_argument("unknown lattice '" + name +
                              "' (expected triangular, honeycomb, or square)");
}

std::string lattice_kind_name(LatticeKind kind) {
  switch (kind) {
    case LatticeKind::Triangular:
      return "triangular";
    case LatticeKind::Honeycomb:
      return "honeycomb";
    case LatticeKind::Square:
      return "square";
  }
  throw std::logic_error("invalid lattice kind");
}

UpdateKind parse_update_kind(const std::string& name) {
  if (name == "cluster") {
    return UpdateKind::Cluster;
  }
  if (name == "loop") {
    return UpdateKind::Loop;
  }
  if (name == "line") {
    return UpdateKind::Line;
  }
  throw std::invalid_argument("unknown update '" + name +
                              "' (expected cluster, loop, or line)");
}

std::string update_kind_name(UpdateKind kind) {
  switch (kind) {
    case UpdateKind::Cluster:
      return "cluster";
    case UpdateKind::Loop:
      return "loop";
    case UpdateKind::Line:
      return "line";
  }
  throw std::logic_error("invalid update kind");
}

Lattice build_lattice(LatticeKind kind, int lx, int ly) {
  if (lx <= 0 || ly <= 0) {
    throw std::invalid_argument("lattice dimensions must be positive");
  }

  if (kind == LatticeKind::Triangular) {
    const int sites = lx * ly;
    Lattice lattice{kind, lx, ly, sites, 6, {}, {}};
    lattice.bonds.resize(static_cast<std::size_t>(3 * sites));
    lattice.site_bonds.resize(static_cast<std::size_t>(6 * sites));
    constexpr std::array<std::array<int, 2>, 3> directions{{
        {{1, 0}},
        {{0, 1}},
        {{-1, 1}},
    }};
    const auto site_id = [lx, ly](int x, int y) {
      return positive_mod(x, lx) + positive_mod(y, ly) * lx;
    };
    for (int y = 0; y < ly; ++y) {
      for (int x = 0; x < lx; ++x) {
        const int site = site_id(x, y);
        for (int direction = 0; direction < 3; ++direction) {
          const int bond_index = site * 3 + direction;
          lattice.bonds[static_cast<std::size_t>(bond_index)] = {
              site, site_id(x + directions[static_cast<std::size_t>(direction)][0],
                            y + directions[static_cast<std::size_t>(direction)][1])};
          lattice.site_bonds[static_cast<std::size_t>(site * 6 + direction)] =
              bond_index;
          const int source = site_id(
              x - directions[static_cast<std::size_t>(direction)][0],
              y - directions[static_cast<std::size_t>(direction)][1]);
          lattice.site_bonds[static_cast<std::size_t>(site * 6 + direction + 3)] =
              source * 3 + direction;
        }
      }
    }
    return lattice;
  }

  if (kind == LatticeKind::Honeycomb) {
    const int cells = lx * ly;
    Lattice lattice{kind, lx, ly, 2 * cells, 3, {}, {}};
    lattice.bonds.resize(static_cast<std::size_t>(3 * cells));
    lattice.site_bonds.resize(static_cast<std::size_t>(6 * cells));
    const auto a_site = [lx, ly](int x, int y) {
      return 2 * (positive_mod(x, lx) + positive_mod(y, ly) * lx);
    };
    const auto b_site = [&a_site](int x, int y) { return a_site(x, y) + 1; };
    for (int y = 0; y < ly; ++y) {
      for (int x = 0; x < lx; ++x) {
        const int cell = x + y * lx;
        const int a = a_site(x, y);
        lattice.bonds[static_cast<std::size_t>(cell * 3)] = {a, b_site(x, y)};
        lattice.bonds[static_cast<std::size_t>(cell * 3 + 1)] = {a,
                                                                 b_site(x - 1, y)};
        lattice.bonds[static_cast<std::size_t>(cell * 3 + 2)] = {a,
                                                                 b_site(x, y - 1)};
        for (int direction = 0; direction < 3; ++direction) {
          lattice.site_bonds[static_cast<std::size_t>(a * 3 + direction)] =
              cell * 3 + direction;
        }
      }
    }
    for (int y = 0; y < ly; ++y) {
      for (int x = 0; x < lx; ++x) {
        const int b = b_site(x, y);
        lattice.site_bonds[static_cast<std::size_t>(b * 3)] = (x + y * lx) * 3;
        lattice.site_bonds[static_cast<std::size_t>(b * 3 + 1)] =
            (positive_mod(x + 1, lx) + y * lx) * 3 + 1;
        lattice.site_bonds[static_cast<std::size_t>(b * 3 + 2)] =
            (x + positive_mod(y + 1, ly) * lx) * 3 + 2;
      }
    }
    return lattice;
  }

  const int sites = lx * ly;
  Lattice lattice{kind, lx, ly, sites, 4, {}, {}};
  lattice.bonds.resize(static_cast<std::size_t>(2 * sites));
  lattice.site_bonds.resize(static_cast<std::size_t>(4 * sites));
  const auto site_id = [lx, ly](int x, int y) {
    return positive_mod(x, lx) + positive_mod(y, ly) * lx;
  };
  constexpr std::array<std::array<int, 2>, 2> directions{{{{1, 0}}, {{0, 1}}}};
  for (int y = 0; y < ly; ++y) {
    for (int x = 0; x < lx; ++x) {
      const int site = site_id(x, y);
      for (int direction = 0; direction < 2; ++direction) {
        const int bond_index = site * 2 + direction;
        lattice.bonds[static_cast<std::size_t>(bond_index)] = {
            site, site_id(x + directions[static_cast<std::size_t>(direction)][0],
                          y + directions[static_cast<std::size_t>(direction)][1])};
        lattice.site_bonds[static_cast<std::size_t>(site * 4 + direction)] =
            bond_index;
        const int source = site_id(
            x - directions[static_cast<std::size_t>(direction)][0],
            y - directions[static_cast<std::size_t>(direction)][1]);
        lattice.site_bonds[static_cast<std::size_t>(site * 4 + direction + 2)] =
            source * 2 + direction;
      }
    }
  }
  return lattice;
}

Simulation::Simulation(Parameters parameters)
    : parameters_(parameters),
      lattice_(build_lattice(parameters.lattice, parameters.lx, parameters.ly)),
      rng_(parameters.seed) {
  validate_parameters();
  bond_shift_ = std::abs(parameters_.interaction) +
                2.0 * std::abs(parameters_.longitudinal_field) /
                    static_cast<double>(lattice_.coordination) +
                0.5;
  for (int type = 0; type < 4; ++type) {
    const int first_bit = type & 1;
    const int second_bit = (type >> 1) & 1;
    const double first_spin = static_cast<double>(2 * first_bit - 1);
    const double second_spin = static_cast<double>(2 * second_bit - 1);
    bond_weights_[static_cast<std::size_t>(type)] =
        -parameters_.interaction * first_spin * second_spin +
        (parameters_.longitudinal_field /
         static_cast<double>(lattice_.coordination)) *
            (first_spin + second_spin) +
        bond_shift_;
  }

  const double estimated_maximum =
      std::ceil(6.0 * parameters_.beta *
                static_cast<double>(lattice_.bonds.size() +
                                    static_cast<std::size_t>(lattice_.sites)));
  if (estimated_maximum > static_cast<double>(std::numeric_limits<int>::max())) {
    throw std::overflow_error("operator-list size exceeds int range");
  }
  maximum_list_length_ = std::max(1000, static_cast<int>(estimated_maximum));
  operators_.resize(static_cast<std::size_t>(maximum_list_length_));
  spins_.resize(static_cast<std::size_t>(lattice_.sites));
  for (std::uint8_t& spin : spins_) {
    spin = static_cast<std::uint8_t>(random_index(2));
  }

  vertex_type_.resize(static_cast<std::size_t>(maximum_list_length_));
  vertex_bond_.resize(static_cast<std::size_t>(maximum_list_length_));
  vertex_spins_.resize(static_cast<std::size_t>(4 * maximum_list_length_));
  leg_link_.resize(static_cast<std::size_t>(4 * maximum_list_length_));
  first_leg_.resize(static_cast<std::size_t>(lattice_.sites));
  last_leg_.resize(static_cast<std::size_t>(lattice_.sites));
  single_vertices_.resize(static_cast<std::size_t>(maximum_list_length_));
  measure_spins_.resize(static_cast<std::size_t>(lattice_.sites));
  line_lists_.resize(static_cast<std::size_t>(lattice_.sites));
  cluster_site_positions_.resize(static_cast<std::size_t>(lattice_.sites));
  cluster_segment_base_.resize(static_cast<std::size_t>(lattice_.sites));
  cluster_segment_cursor_.resize(static_cast<std::size_t>(lattice_.sites));
}

void Simulation::validate_parameters() const {
  if (!std::isfinite(parameters_.interaction) ||
      !std::isfinite(parameters_.transverse_field) ||
      !std::isfinite(parameters_.longitudinal_field) ||
      !std::isfinite(parameters_.beta) ||
      !std::isfinite(parameters_.anneal_start_field)) {
    throw std::invalid_argument("couplings, fields, and beta must be finite");
  }
  if (parameters_.transverse_field <= 0.0 || parameters_.beta <= 0.0) {
    throw std::invalid_argument("transverse field and beta must be positive");
  }
  if (parameters_.thermalization_sweeps < 0 || parameters_.measurement_sweeps < 2) {
    throw std::invalid_argument("thermalization must be nonnegative and measurements >= 2");
  }
  if (parameters_.bins < 2 || parameters_.bins > parameters_.measurement_sweeps) {
    throw std::invalid_argument("bins must be in [2, measurement_sweeps]");
  }
  if (parameters_.anneal_start_field < 0.0) {
    throw std::invalid_argument("anneal start field must be nonnegative");
  }
  if (parameters_.update == UpdateKind::Cluster &&
      parameters_.longitudinal_field != 0.0) {
    throw std::invalid_argument("cluster update requires zero longitudinal field");
  }
}

double Simulation::unit_random() {
  return std::generate_canonical<double, 53>(rng_);
}

int Simulation::random_index(int upper_exclusive) {
  if (upper_exclusive <= 0) {
    throw std::logic_error("random index requested from an empty range");
  }
  std::uniform_int_distribution<int> distribution(0, upper_exclusive - 1);
  return distribution(rng_);
}

void Simulation::diagonal_update() {
  const int bond_count = static_cast<int>(lattice_.bonds.size());
  const int insertion_choices = bond_count + lattice_.sites;
  for (int position = 0; position < list_length_; ++position) {
    Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type == 0) {
      const int candidate = random_index(insertion_choices);
      const int empty_slots = list_length_ - operator_count_;
      if (candidate < bond_count) {
        const Bond& bond = lattice_.bonds[static_cast<std::size_t>(candidate)];
        const int type = static_cast<int>(spins_[static_cast<std::size_t>(bond.first)]) +
                         2 * static_cast<int>(
                                 spins_[static_cast<std::size_t>(bond.second)]) +
                         1;
        const double probability =
            bond_weights_[static_cast<std::size_t>(type - 1)] * parameters_.beta *
            static_cast<double>(insertion_choices) / static_cast<double>(empty_slots);
        if (unit_random() < probability) {
          op.type = static_cast<std::int8_t>(type);
          op.index = candidate;
          ++operator_count_;
        }
      } else {
        const int site = candidate - bond_count;
        const double probability =
            parameters_.transverse_field * parameters_.beta *
            static_cast<double>(insertion_choices) / static_cast<double>(empty_slots);
        if (unit_random() < probability) {
          op.type = static_cast<std::int8_t>(
              static_cast<int>(spins_[static_cast<std::size_t>(site)]) * 3 + 5);
          op.index = site;
          ++operator_count_;
        }
      }
    } else if (op.type != 6 && op.type != 7) {
      const double weight = op.type < 5
                                ? bond_weights_[static_cast<std::size_t>(op.type - 1)]
                                : parameters_.transverse_field;
      const double probability =
          static_cast<double>(list_length_ - operator_count_ + 1) /
          (weight * parameters_.beta * static_cast<double>(insertion_choices));
      if (unit_random() < probability) {
        op = {};
        --operator_count_;
      }
    } else {
      std::uint8_t& spin = spins_[static_cast<std::size_t>(op.index)];
      spin = static_cast<std::uint8_t>(1U - spin);
    }
  }
}

int Simulation::cluster_find(int segment) {
  while (cluster_parent_[static_cast<std::size_t>(segment)] != segment) {
    const int parent = cluster_parent_[static_cast<std::size_t>(segment)];
    cluster_parent_[static_cast<std::size_t>(segment)] =
        cluster_parent_[static_cast<std::size_t>(parent)];
    segment = parent;
  }
  return segment;
}

void Simulation::cluster_union(int first, int second) {
  const int first_root = cluster_find(first);
  const int second_root = cluster_find(second);
  if (first_root != second_root) {
    cluster_parent_[static_cast<std::size_t>(first_root)] = second_root;
  }
}

// Rejection-free Swendsen-Wang-style TFIM cluster update.  The bond operator
// joins the two worldline segments it touches; an entire connected component
// flips together, preserving every bond weight at B=0.
void Simulation::cluster_update() {
  for (auto& positions : cluster_site_positions_) {
    positions.clear();
  }
  for (int position = 0; position < list_length_; ++position) {
    const Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type >= 5) {
      cluster_site_positions_[static_cast<std::size_t>(op.index)].push_back(position);
    }
  }

  int segment_count = 0;
  for (int site = 0; site < lattice_.sites; ++site) {
    cluster_segment_base_[static_cast<std::size_t>(site)] = segment_count;
    const int cuts = static_cast<int>(cluster_site_positions_[static_cast<std::size_t>(site)].size());
    segment_count += std::max(cuts, 1);
  }
  cluster_parent_.resize(static_cast<std::size_t>(segment_count));
  for (int segment = 0; segment < segment_count; ++segment) {
    cluster_parent_[static_cast<std::size_t>(segment)] = segment;
  }

  const auto segment_at = [this](int site, int position) {
    const auto& positions = cluster_site_positions_[static_cast<std::size_t>(site)];
    const int count = static_cast<int>(positions.size());
    if (count == 0) {
      return cluster_segment_base_[static_cast<std::size_t>(site)];
    }
    int& cursor = cluster_segment_cursor_[static_cast<std::size_t>(site)];
    while (cursor < count && positions[static_cast<std::size_t>(cursor)] < position) {
      ++cursor;
    }
    const int local = (cursor == 0 || cursor == count) ? count - 1 : cursor - 1;
    return cluster_segment_base_[static_cast<std::size_t>(site)] + local;
  };

  std::fill(cluster_segment_cursor_.begin(), cluster_segment_cursor_.end(), 0);
  for (int position = 0; position < list_length_; ++position) {
    const Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type >= 1 && op.type < 5) {
      const Bond& bond = lattice_.bonds[static_cast<std::size_t>(op.index)];
      cluster_union(segment_at(bond.first, position), segment_at(bond.second, position));
    }
  }

  cluster_flip_.assign(static_cast<std::size_t>(segment_count), 2U);
  for (int segment = 0; segment < segment_count; ++segment) {
    const int root = cluster_find(segment);
    if (cluster_flip_[static_cast<std::size_t>(root)] == 2U) {
      cluster_flip_[static_cast<std::size_t>(root)] = unit_random() < 0.5 ? 1U : 0U;
    }
    cluster_flip_[static_cast<std::size_t>(segment)] =
        cluster_flip_[static_cast<std::size_t>(root)];
  }

  std::fill(cluster_segment_cursor_.begin(), cluster_segment_cursor_.end(), 0);
  for (int position = 0; position < list_length_; ++position) {
    Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type >= 1 && op.type < 5) {
      const Bond& bond = lattice_.bonds[static_cast<std::size_t>(op.index)];
      const int segment = segment_at(bond.first, position);
      if (cluster_flip_[static_cast<std::size_t>(segment)] != 0U) {
        op.type = static_cast<std::int8_t>((static_cast<int>(op.type) - 1) ^ 3);
        ++op.type;
      }
    }
  }

  for (int site = 0; site < lattice_.sites; ++site) {
    const auto& positions = cluster_site_positions_[static_cast<std::size_t>(site)];
    const int count = static_cast<int>(positions.size());
    const int base = cluster_segment_base_[static_cast<std::size_t>(site)];
    for (int cut = 0; cut < count; ++cut) {
      const int below = base + (cut - 1 + count) % count;
      const int above = base + cut;
      Operator& op = operators_[static_cast<std::size_t>(positions[static_cast<std::size_t>(cut)])];
      int bits = static_cast<int>(op.type) - 5;
      if (cluster_flip_[static_cast<std::size_t>(below)] != 0U) {
        bits ^= 1;
      }
      if (cluster_flip_[static_cast<std::size_t>(above)] != 0U) {
        bits ^= 2;
      }
      op.type = static_cast<std::int8_t>(bits + 5);
    }
    const int wrap = base + (count == 0 ? 0 : count - 1);
    if (cluster_flip_[static_cast<std::size_t>(wrap)] != 0U) {
      spins_[static_cast<std::size_t>(site)] =
          static_cast<std::uint8_t>(1U - spins_[static_cast<std::size_t>(site)]);
    }
  }
}

void Simulation::loop_update() {
  std::fill(first_leg_.begin(), first_leg_.end(), -1);
  std::fill(last_leg_.begin(), last_leg_.end(), -1);

  int vertex_count = 0;
  int single_count = 0;
  for (int position = 0; position < list_length_; ++position) {
    const Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type == 0) {
      continue;
    }
    const int vertex = vertex_count++;
    const int base = 4 * vertex;
    int bond_index = op.index;
    if (op.type < 5) {
      vertex_type_[static_cast<std::size_t>(vertex)] = op.type;
      const Bond& bond = lattice_.bonds[static_cast<std::size_t>(bond_index)];
      vertex_spins_[static_cast<std::size_t>(base)] =
          spins_[static_cast<std::size_t>(bond.first)];
      vertex_spins_[static_cast<std::size_t>(base + 1)] =
          spins_[static_cast<std::size_t>(bond.second)];
      vertex_spins_[static_cast<std::size_t>(base + 2)] =
          vertex_spins_[static_cast<std::size_t>(base)];
      vertex_spins_[static_cast<std::size_t>(base + 3)] =
          vertex_spins_[static_cast<std::size_t>(base + 1)];
    } else {
      const int site = op.index;
      bond_index = lattice_.incident_bond(site, random_index(lattice_.coordination));
      const Bond& bond = lattice_.bonds[static_cast<std::size_t>(bond_index)];
      vertex_spins_[static_cast<std::size_t>(base)] =
          spins_[static_cast<std::size_t>(bond.first)];
      vertex_spins_[static_cast<std::size_t>(base + 1)] =
          spins_[static_cast<std::size_t>(bond.second)];
      if (op.type == 6 || op.type == 7) {
        vertex_type_[static_cast<std::size_t>(vertex)] = -1;
        std::uint8_t& spin = spins_[static_cast<std::size_t>(site)];
        spin = static_cast<std::uint8_t>(1U - spin);
      } else {
        vertex_type_[static_cast<std::size_t>(vertex)] = 0;
      }
      vertex_spins_[static_cast<std::size_t>(base + 2)] =
          spins_[static_cast<std::size_t>(bond.first)];
      vertex_spins_[static_cast<std::size_t>(base + 3)] =
          spins_[static_cast<std::size_t>(bond.second)];
      single_vertices_[static_cast<std::size_t>(single_count++)] = vertex;
    }
    vertex_bond_[static_cast<std::size_t>(vertex)] = bond_index;

    const Bond& bond = lattice_.bonds[static_cast<std::size_t>(bond_index)];
    const std::array<int, 2> sites{{bond.first, bond.second}};
    for (int endpoint = 0; endpoint < 2; ++endpoint) {
      const int site = sites[static_cast<std::size_t>(endpoint)];
      const int incoming_leg = base + endpoint;
      const int outgoing_leg = base + endpoint + 2;
      if (first_leg_[static_cast<std::size_t>(site)] == -1) {
        first_leg_[static_cast<std::size_t>(site)] = incoming_leg;
      }
      const int previous = last_leg_[static_cast<std::size_t>(site)];
      if (previous != -1) {
        leg_link_[static_cast<std::size_t>(previous)] = incoming_leg;
        leg_link_[static_cast<std::size_t>(incoming_leg)] = previous;
      }
      last_leg_[static_cast<std::size_t>(site)] = outgoing_leg;
    }
  }

  for (int site = 0; site < lattice_.sites; ++site) {
    const int first = first_leg_[static_cast<std::size_t>(site)];
    if (first != -1) {
      const int last = last_leg_[static_cast<std::size_t>(site)];
      leg_link_[static_cast<std::size_t>(first)] = last;
      leg_link_[static_cast<std::size_t>(last)] = first;
    }
  }

  constexpr std::array<int, 4> pass_leg{{2, 3, 0, 1}};
  for (int chain = 0; chain < single_count; ++chain) {
    const int start_vertex =
        single_vertices_[static_cast<std::size_t>(random_index(single_count))];
    const int start_base = 4 * start_vertex;
    const std::int8_t start_type =
        vertex_type_[static_cast<std::size_t>(start_vertex)];
    int outgoing_leg = 0;
    if (start_type == 0) {
      outgoing_leg = random_index(4);
    } else if (vertex_spins_[static_cast<std::size_t>(start_base)] !=
               vertex_spins_[static_cast<std::size_t>(start_base + 2)]) {
      outgoing_leg = 2 * random_index(2);
    } else {
      outgoing_leg = 2 * random_index(2) + 1;
    }
    vertex_type_[static_cast<std::size_t>(start_vertex)] =
        static_cast<std::int8_t>(-1 - start_type);
    int current_leg = start_base + outgoing_leg;
    std::uint8_t& initial_spin = vertex_spins_[static_cast<std::size_t>(current_leg)];
    initial_spin = static_cast<std::uint8_t>(1U - initial_spin);

    bool running = true;
    std::uint64_t chain_steps = 0;
    while (running) {
      ++worm_steps_;
      ++chain_steps;
      if (chain_steps > 100000000ULL) {
        throw std::runtime_error("line update exceeded the worm-step safety limit");
      }
      const int incoming = leg_link_[static_cast<std::size_t>(current_leg)];
      const int incoming_leg = incoming & 3;
      const int vertex = incoming >> 2;
      const int base = 4 * vertex;
      const std::int8_t type = vertex_type_[static_cast<std::size_t>(vertex)];
      if (type > 0) {
        const int first = static_cast<int>(vertex_spins_[static_cast<std::size_t>(base)]);
        const int second =
            static_cast<int>(vertex_spins_[static_cast<std::size_t>(base + 1)]);
        const int new_type = (incoming_leg % 2 == 0)
                                 ? (1 - first) + 2 * second + 1
                                 : first + 2 * (1 - second) + 1;
        const double ratio =
            bond_weights_[static_cast<std::size_t>(new_type - 1)] /
            bond_weights_[static_cast<std::size_t>(type - 1)];
        if (unit_random() < ratio) {
          std::uint8_t& incoming_spin =
              vertex_spins_[static_cast<std::size_t>(incoming)];
          incoming_spin = static_cast<std::uint8_t>(1U - incoming_spin);
          const int passed_leg = pass_leg[static_cast<std::size_t>(incoming_leg)];
          current_leg = base + passed_leg;
          std::uint8_t& passed_spin =
              vertex_spins_[static_cast<std::size_t>(current_leg)];
          passed_spin = static_cast<std::uint8_t>(1U - passed_spin);
          vertex_type_[static_cast<std::size_t>(vertex)] =
              static_cast<std::int8_t>(new_type);
        } else {
          current_leg = incoming;
        }
      } else if (type == 0) {
        std::uint8_t& incoming_spin =
            vertex_spins_[static_cast<std::size_t>(incoming)];
        incoming_spin = static_cast<std::uint8_t>(1U - incoming_spin);
        if (unit_random() <= 0.25) {
          vertex_type_[static_cast<std::size_t>(vertex)] = -1;
          running = false;
        } else {
          const int passed_leg = pass_leg[static_cast<std::size_t>(incoming_leg)];
          current_leg = base + passed_leg;
          std::uint8_t& passed_spin =
              vertex_spins_[static_cast<std::size_t>(current_leg)];
          passed_spin = static_cast<std::uint8_t>(1U - passed_spin);
        }
      } else {
        const bool left_active =
            vertex_spins_[static_cast<std::size_t>(base)] !=
            vertex_spins_[static_cast<std::size_t>(base + 2)];
        std::uint8_t& incoming_spin =
            vertex_spins_[static_cast<std::size_t>(incoming)];
        incoming_spin = static_cast<std::uint8_t>(1U - incoming_spin);
        const bool can_stop = left_active ? incoming_leg % 2 == 0
                                          : incoming_leg % 2 != 0;
        if (can_stop && unit_random() <= 0.5) {
          vertex_type_[static_cast<std::size_t>(vertex)] = 0;
          running = false;
        } else {
          int candidate = random_index(3);
          if (candidate >= incoming_leg) {
            ++candidate;
          }
          current_leg = base + candidate;
          std::uint8_t& outgoing_spin =
              vertex_spins_[static_cast<std::size_t>(current_leg)];
          outgoing_spin = static_cast<std::uint8_t>(1U - outgoing_spin);
        }
      }
    }
  }

  for (int site = 0; site < lattice_.sites; ++site) {
    const int first = first_leg_[static_cast<std::size_t>(site)];
    if (first != -1) {
      spins_[static_cast<std::size_t>(site)] =
          vertex_spins_[static_cast<std::size_t>(first)];
    }
  }

  int vertex = 0;
  for (int position = 0; position < list_length_; ++position) {
    Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type == 0) {
      continue;
    }
    const int base = 4 * vertex;
    const std::int8_t type = vertex_type_[static_cast<std::size_t>(vertex)];
    if (op.type < 5) {
      if (type <= 0) {
        throw std::runtime_error("bond vertex became a single-site vertex");
      }
      op.type = type;
    } else {
      const int bond_index = vertex_bond_[static_cast<std::size_t>(vertex)];
      const Bond& bond = lattice_.bonds[static_cast<std::size_t>(bond_index)];
      if (type == 0) {
        const int endpoint = random_index(2);
        const int spin = static_cast<int>(
            vertex_spins_[static_cast<std::size_t>(base + endpoint)]);
        op.type = static_cast<std::int8_t>(spin * 3 + 5);
        op.index = endpoint == 0 ? bond.first : bond.second;
      } else if (type == -1) {
        const bool left_active =
            vertex_spins_[static_cast<std::size_t>(base)] !=
            vertex_spins_[static_cast<std::size_t>(base + 2)];
        const int endpoint = left_active ? 0 : 1;
        const int spin = static_cast<int>(
            vertex_spins_[static_cast<std::size_t>(base + endpoint)]);
        op.type = static_cast<std::int8_t>(7 - spin);
        op.index = endpoint == 0 ? bond.first : bond.second;
      } else {
        throw std::runtime_error("single-site vertex became a bond vertex");
      }
    }
    ++vertex;
    if (vertex == operator_count_) {
      break;
    }
  }
  if (vertex != operator_count_ || vertex_count != operator_count_) {
    throw std::runtime_error("operator/vertex count mismatch after line update");
  }
}

// Local worldline-segment update.  A single-site operator delimits segments
// on one worldline; a heat-bath segment flip changes only the incident bond
// legs and the delimiter bits.  This is distinct from loop_update() above.
void Simulation::segment_line_update() {
  for (auto& entries : line_lists_) {
    entries.clear();
  }
  for (int position = 0; position < list_length_; ++position) {
    const Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type == 0) {
      continue;
    }
    if (op.type < 5) {
      const Bond& bond = lattice_.bonds[static_cast<std::size_t>(op.index)];
      line_lists_[static_cast<std::size_t>(bond.first)].push_back({position, 1U});
      line_lists_[static_cast<std::size_t>(bond.second)].push_back({position, 2U});
    } else {
      line_lists_[static_cast<std::size_t>(op.index)].push_back({position, 0U});
    }
  }

  for (int site = 0; site < lattice_.sites; ++site) {
    const auto& entries = line_lists_[static_cast<std::size_t>(site)];
    if (entries.empty()) {
      if (unit_random() < 0.5) {
        spins_[static_cast<std::size_t>(site)] =
            static_cast<std::uint8_t>(1U - spins_[static_cast<std::size_t>(site)]);
      }
      continue;
    }

    std::vector<int> delimiters;
    delimiters.reserve(entries.size());
    for (std::size_t index = 0; index < entries.size(); ++index) {
      if (entries[index].leg == 0U) {
        delimiters.push_back(static_cast<int>(index));
      }
    }

    const auto flip_entries = [&](int first, int last) {
      int index = first;
      while (index != last) {
        const LineEntry& entry = entries[static_cast<std::size_t>(index)];
        if (entry.leg != 0U) {
          Operator& bond = operators_[static_cast<std::size_t>(entry.position)];
          bond.type = static_cast<std::int8_t>(
              ((static_cast<int>(bond.type) - 1) ^ static_cast<int>(entry.leg)) + 1);
        }
        index = (index + 1) % static_cast<int>(entries.size());
      }
    };

    const auto heat_bath_accept = [&](int first, int last) {
      long double ratio = 1.0L;
      int index = first;
      while (index != last) {
        const LineEntry& entry = entries[static_cast<std::size_t>(index)];
        if (entry.leg != 0U) {
          const Operator& bond = operators_[static_cast<std::size_t>(entry.position)];
          const int old_type = static_cast<int>(bond.type);
          const int new_type = ((old_type - 1) ^ static_cast<int>(entry.leg)) + 1;
          ratio *= static_cast<long double>(bond_weights_[static_cast<std::size_t>(new_type - 1)]) /
                   static_cast<long double>(bond_weights_[static_cast<std::size_t>(old_type - 1)]);
        }
        index = (index + 1) % static_cast<int>(entries.size());
      }
      const long double probability = ratio / (1.0L + ratio);
      return static_cast<long double>(unit_random()) < probability;
    };

    if (delimiters.empty()) {
      long double ratio = 1.0L;
      for (const LineEntry& entry : entries) {
        const Operator& bond = operators_[static_cast<std::size_t>(entry.position)];
        const int old_type = static_cast<int>(bond.type);
        const int new_type = ((old_type - 1) ^ static_cast<int>(entry.leg)) + 1;
        ratio *= static_cast<long double>(bond_weights_[static_cast<std::size_t>(new_type - 1)]) /
                 static_cast<long double>(bond_weights_[static_cast<std::size_t>(old_type - 1)]);
      }
      if (static_cast<long double>(unit_random()) < ratio / (1.0L + ratio)) {
        for (const LineEntry& entry : entries) {
          Operator& bond = operators_[static_cast<std::size_t>(entry.position)];
          bond.type = static_cast<std::int8_t>(
              ((static_cast<int>(bond.type) - 1) ^ static_cast<int>(entry.leg)) + 1);
        }
        spins_[static_cast<std::size_t>(site)] =
            static_cast<std::uint8_t>(1U - spins_[static_cast<std::size_t>(site)]);
      }
      continue;
    }

    for (std::size_t segment = 0; segment < delimiters.size(); ++segment) {
      const int left = delimiters[segment];
      const int right = delimiters[(segment + 1U) % delimiters.size()];
      const int first = (left + 1) % static_cast<int>(entries.size());
      if (!heat_bath_accept(first, right)) {
        continue;
      }
      flip_entries(first, right);
      Operator& left_delimiter =
          operators_[static_cast<std::size_t>(entries[static_cast<std::size_t>(left)].position)];
      Operator& right_delimiter =
          operators_[static_cast<std::size_t>(entries[static_cast<std::size_t>(right)].position)];
      if (left == right) {
        left_delimiter.type = static_cast<std::int8_t>(
            ((static_cast<int>(left_delimiter.type) - 5) ^ 3) + 5);
      } else {
        left_delimiter.type = static_cast<std::int8_t>(
            ((static_cast<int>(left_delimiter.type) - 5) ^ 2) + 5);
        right_delimiter.type = static_cast<std::int8_t>(
            ((static_cast<int>(right_delimiter.type) - 5) ^ 1) + 5);
      }
      if (left >= right) {
        spins_[static_cast<std::size_t>(site)] =
            static_cast<std::uint8_t>(1U - spins_[static_cast<std::size_t>(site)]);
      }
    }
  }
}

void Simulation::update() {
  switch (parameters_.update) {
    case UpdateKind::Cluster:
      cluster_update();
      return;
    case UpdateKind::Loop:
      loop_update();
      return;
    case UpdateKind::Line:
      segment_line_update();
      return;
  }
  throw std::logic_error("invalid update kind");
}

bool Simulation::configuration_consistent() const {
  std::vector<std::uint8_t> propagated = spins_;
  for (int position = 0; position < list_length_; ++position) {
    const Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type == 0) {
      continue;
    }
    if (op.type < 5) {
      const Bond& bond = lattice_.bonds[static_cast<std::size_t>(op.index)];
      const int expected = static_cast<int>(propagated[static_cast<std::size_t>(bond.first)]) +
                           2 * static_cast<int>(propagated[static_cast<std::size_t>(bond.second)]) + 1;
      if (op.type != expected) {
        return false;
      }
    } else {
      const int in_spin = (static_cast<int>(op.type) - 5) & 1;
      if (static_cast<int>(propagated[static_cast<std::size_t>(op.index)]) != in_spin) {
        return false;
      }
      propagated[static_cast<std::size_t>(op.index)] =
          static_cast<std::uint8_t>((static_cast<int>(op.type) - 5) >> 1);
    }
  }
  return propagated == spins_;
}

void Simulation::grow_operator_list() {
  const int target = static_cast<int>(1.25 * static_cast<double>(operator_count_));
  if (target > maximum_list_length_) {
    throw std::runtime_error("operator list overflow; increase the allocation factor");
  }
  if (target > list_length_) {
    list_length_ = target;
  }
}

std::array<double, 4> Simulation::measure() {
  int single_site_operators = 0;
  std::copy(spins_.begin(), spins_.end(), measure_spins_.begin());
  int spin_sum = 0;
  for (const std::uint8_t spin : measure_spins_) {
    spin_sum += 2 * static_cast<int>(spin) - 1;
  }
  double second_moment = 0.0;
  double fourth_moment = 0.0;
  const double inverse_sites = 1.0 / static_cast<double>(lattice_.sites);
  for (int position = 0; position < list_length_; ++position) {
    const Operator& op = operators_[static_cast<std::size_t>(position)];
    if (op.type == 6 || op.type == 7) {
      std::uint8_t& spin = measure_spins_[static_cast<std::size_t>(op.index)];
      spin = static_cast<std::uint8_t>(1U - spin);
      spin_sum += 2 * (2 * static_cast<int>(spin) - 1);
      ++single_site_operators;
    } else if (op.type == 5 || op.type == 8) {
      ++single_site_operators;
    }
    const double magnetization = static_cast<double>(spin_sum) * inverse_sites;
    const double square = magnetization * magnetization;
    second_moment += square;
    fourth_moment += square * square;
  }

  const double energy =
      -static_cast<double>(operator_count_) / parameters_.beta +
      static_cast<double>(lattice_.bonds.size()) * bond_shift_ +
      parameters_.transverse_field * static_cast<double>(lattice_.sites);
  const double transverse_magnetization =
      static_cast<double>(single_site_operators) /
          (parameters_.beta * parameters_.transverse_field *
           static_cast<double>(lattice_.sites)) -
      1.0;
  return {{energy / static_cast<double>(lattice_.sites),
           transverse_magnetization,
           second_moment / static_cast<double>(list_length_),
           fourth_moment / static_cast<double>(list_length_)}};
}

Results Simulation::run() {
  const double target_field = parameters_.transverse_field;
  for (int sweep = 0; sweep < parameters_.thermalization_sweeps; ++sweep) {
    if (parameters_.anneal_start_field > 0.0) {
      const double denominator =
          0.8 * static_cast<double>(parameters_.thermalization_sweeps);
      const double fraction =
          denominator > 0.0
              ? std::min(static_cast<double>(sweep + 1) / denominator, 1.0)
              : 1.0;
      parameters_.transverse_field =
          parameters_.anneal_start_field +
          (target_field - parameters_.anneal_start_field) * fraction;
    }
    diagonal_update();
    update();
    if (parameters_.check_configuration && !configuration_consistent()) {
      throw std::runtime_error("worldline consistency check failed during thermalization");
    }
    grow_operator_list();
  }
  parameters_.transverse_field = target_field;

  const int sweeps_per_bin =
      std::max(1, parameters_.measurement_sweeps / parameters_.bins);
  std::array<double, 4> total{};
  std::array<double, 4> bin_total{};
  std::array<std::vector<double>, 4> bin_values;
  std::vector<double> binder_values;
  Results results;
  for (auto& values : bin_values) {
    values.reserve(static_cast<std::size_t>(parameters_.bins));
  }
  if (parameters_.record_sweeps) {
    for (auto& values : results.sweep_values) {
      values.reserve(static_cast<std::size_t>(parameters_.measurement_sweeps));
    }
  }
  binder_values.reserve(static_cast<std::size_t>(parameters_.bins));
  const auto measurement_start = std::chrono::steady_clock::now();

  for (int sweep = 1; sweep <= parameters_.measurement_sweeps; ++sweep) {
    diagonal_update();
    update();
    if (parameters_.check_configuration && !configuration_consistent()) {
      throw std::runtime_error("worldline consistency check failed during measurement");
    }
    const std::array<double, 4> observable = measure();
    for (std::size_t index = 0; index < observable.size(); ++index) {
      total[index] += observable[index];
      bin_total[index] += observable[index];
    }
    if (parameters_.record_sweeps) {
      for (std::size_t index = 0; index < observable.size(); ++index) {
        results.sweep_values[index].push_back(observable[index]);
      }
    }
    if (sweep % sweeps_per_bin == 0) {
      std::array<double, 4> bin_mean{};
      for (std::size_t index = 0; index < bin_mean.size(); ++index) {
        bin_mean[index] = bin_total[index] / static_cast<double>(sweeps_per_bin);
        bin_values[index].push_back(bin_mean[index]);
        bin_total[index] = 0.0;
      }
      binder_values.push_back(
          1.0 - bin_mean[3] / (3.0 * bin_mean[2] * bin_mean[2]));
    }
  }
  results.measurement_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - measurement_start).count();

  for (std::size_t index = 0; index < results.mean.size(); ++index) {
    results.mean[index] =
        total[index] / static_cast<double>(parameters_.measurement_sweeps);
    results.standard_error[index] = standard_error(bin_values[index]);
  }
  results.binder = std::accumulate(binder_values.begin(), binder_values.end(), 0.0) /
                   static_cast<double>(binder_values.size());
  results.binder_standard_error = standard_error(binder_values);
  results.worm_steps = worm_steps_;
  results.operator_count = operator_count_;
  results.operator_list_length = list_length_;
  return results;
}

}  // namespace tfim
