#pragma once

#include <array>
#include <cstdint>
#include <random>
#include <string>
#include <vector>

namespace tfim {

enum class LatticeKind { Triangular, Honeycomb, Square };
enum class UpdateKind { Cluster, Loop, Line };

struct Bond {
  int first;
  int second;
};

struct Lattice {
  LatticeKind kind;
  int lx;
  int ly;
  int sites;
  int coordination;
  std::vector<Bond> bonds;
  std::vector<int> site_bonds;

  int incident_bond(int site, int neighbor_index) const;
};

LatticeKind parse_lattice_kind(const std::string& name);
std::string lattice_kind_name(LatticeKind kind);
Lattice build_lattice(LatticeKind kind, int lx, int ly);
UpdateKind parse_update_kind(const std::string& name);
std::string update_kind_name(UpdateKind kind);

struct Parameters {
  LatticeKind lattice = LatticeKind::Triangular;
  int lx = 4;
  int ly = 4;
  double interaction = -1.0;
  double transverse_field = 4.768;
  double longitudinal_field = 0.0;
  double beta = 8.0;
  int thermalization_sweeps = 1000;
  int measurement_sweeps = 5000;
  std::uint64_t seed = 12345;
  double anneal_start_field = 0.0;
  int bins = 50;
  UpdateKind update = UpdateKind::Loop;
  bool record_sweeps = false;
  bool check_configuration = false;
};

struct Results {
  std::array<double, 4> mean{};
  std::array<double, 4> standard_error{};
  double binder = 0.0;
  double binder_standard_error = 0.0;
  std::uint64_t worm_steps = 0;
  int operator_count = 0;
  int operator_list_length = 0;
  double measurement_seconds = 0.0;
  std::array<std::vector<double>, 4> sweep_values;
};

class Simulation {
 public:
  explicit Simulation(Parameters parameters);
  Results run();

  const Lattice& lattice() const { return lattice_; }
  const Parameters& parameters() const { return parameters_; }

 private:
  struct Operator {
    std::int8_t type = 0;
    int index = 0;
  };

  Parameters parameters_;
  Lattice lattice_;
  std::mt19937_64 rng_;
  double bond_shift_ = 0.0;
  std::array<double, 4> bond_weights_{};
  int maximum_list_length_ = 0;
  int list_length_ = 10;
  int operator_count_ = 0;
  std::vector<Operator> operators_;
  std::vector<std::uint8_t> spins_;

  std::vector<std::int8_t> vertex_type_;
  std::vector<int> vertex_bond_;
  std::vector<std::uint8_t> vertex_spins_;
  std::vector<int> leg_link_;
  std::vector<int> first_leg_;
  std::vector<int> last_leg_;
  std::vector<int> single_vertices_;
  std::vector<std::uint8_t> measure_spins_;
  struct LineEntry {
    int position;
    std::uint8_t leg;
  };
  std::vector<std::vector<LineEntry>> line_lists_;
  std::vector<std::vector<int>> cluster_site_positions_;
  std::vector<int> cluster_segment_base_;
  std::vector<int> cluster_segment_cursor_;
  std::vector<int> cluster_parent_;
  std::vector<std::uint8_t> cluster_flip_;
  std::uint64_t worm_steps_ = 0;

  double unit_random();
  int random_index(int upper_exclusive);
  void diagonal_update();
  void cluster_update();
  void loop_update();
  void segment_line_update();
  void update();
  void grow_operator_list();
  bool configuration_consistent() const;
  int cluster_find(int segment);
  void cluster_union(int first, int second);
  std::array<double, 4> measure();
  void validate_parameters() const;
};

}  // namespace tfim
