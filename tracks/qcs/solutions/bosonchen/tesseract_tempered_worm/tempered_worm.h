#ifndef BOSONCHEN_TEMPERED_WORM_H
#define BOSONCHEN_TEMPERED_WORM_H

#include <cstddef>
#include <cstdint>
#include <random>
#include <unordered_map>
#include <vector>

namespace tempered_worm {

struct ErrorTerm {
  double cost = 0;
  std::vector<uint32_t> detectors;
  uint64_t logical_mask = 0;
};

struct Model {
  size_t num_detectors = 0;
  size_t num_observables = 0;
  std::vector<ErrorTerm> errors;
  std::vector<std::vector<uint32_t>> detector_to_errors;

  Model() = default;
  Model(size_t detector_count, size_t observable_count, std::vector<ErrorTerm> error_terms);

  std::vector<uint8_t> syndrome_of(const std::vector<uint32_t>& selected_errors) const;
  bool is_kernel_move(const std::vector<uint32_t>& selected_errors) const;
  uint64_t logical_mask_of(const std::vector<uint32_t>& selected_errors) const;
};

struct KernelMove {
  std::vector<uint32_t> errors;
  uint64_t logical_mask = 0;
};

struct CycleBuildConfig {
  size_t random_attempts = 4000;
  size_t logical_seed_attempts = 2000;
  size_t max_steps = 64;
  size_t max_moves = 20000;
  double closure_bias = 0.7;
  uint64_t seed = 1;
};

struct CycleBuildStats {
  size_t duplicate_signature_moves = 0;
  size_t zero_detector_moves = 0;
  size_t random_closed_moves = 0;
  size_t random_failed_attempts = 0;
  size_t logical_seed_closed_moves = 0;
  size_t logical_seed_failed_attempts = 0;
  size_t duplicate_moves_discarded = 0;
  size_t logical_sector_moves = 0;
};

struct CycleLibrary {
  std::vector<KernelMove> moves;
  CycleBuildStats stats;

  static CycleLibrary build(const Model& model, const CycleBuildConfig& config);
};

struct AlgebraicBuildStats {
  size_t basis_sources_considered = 0;
  size_t detector_basis_rank = 0;
  size_t local_dependencies_found = 0;
  size_t local_moves_added = 0;
  size_t logical_targets_considered = 0;
  size_t logical_targets_closed = 0;
  size_t moves_added = 0;
};

AlgebraicBuildStats add_algebraic_logical_moves(
    const Model& model, CycleLibrary& library, size_t max_basis_sources,
    size_t max_new_logical_moves, size_t max_new_local_moves);

struct State {
  std::vector<uint8_t> selected;
  double energy = 0;
  uint64_t logical_mask = 0;

  static State from_errors(const Model& model, const std::vector<uint32_t>& selected_errors);
  double delta_energy(const Model& model, const KernelMove& move) const;
  void apply(const KernelMove& move, double delta);
  std::vector<uint32_t> selected_errors() const;
};

struct SamplerConfig {
  std::vector<double> betas{0.0, 0.02, 0.05, 0.1, 0.2, 0.35, 0.55, 0.75, 1.0};
  size_t burn_in_sweeps = 500;
  size_t measurement_sweeps = 2000;
  size_t moves_per_sweep = 2;
  size_t exchange_interval = 1;
  double logical_move_probability = 0.1;
  uint64_t seed = 1;
};

struct SamplerResult {
  uint64_t predicted_logical_mask = 0;
  std::unordered_map<uint64_t, size_t> logical_counts;
  size_t target_samples = 0;
  size_t distinct_logical_sectors = 0;
  double top_sector_fraction = 0;
  double top_two_margin = 0;
  double effective_sample_size = 0;
  size_t move_attempts = 0;
  size_t move_accepts = 0;
  size_t logical_move_attempts = 0;
  size_t logical_move_accepts = 0;
  size_t target_logical_transitions = 0;
  size_t exchange_attempts = 0;
  size_t exchange_accepts = 0;
  size_t completed_temperature_round_trips = 0;
  double minimum_energy_seen = 0;
};

SamplerResult sample_logical_sector(const Model& model, const CycleLibrary& library,
                                    const State& initial_state, const SamplerConfig& config);

struct BarConfig {
  size_t burn_in_sweeps = 500;
  size_t measurement_sweeps = 2000;
  size_t moves_per_sweep = 2;
  uint64_t seed = 1;
};

struct BarResult {
  double delta_free_energy = 0;
  double overlap_score = 0;
  size_t forward_samples = 0;
  size_t reverse_samples = 0;
  size_t local_move_attempts = 0;
  size_t local_move_accepts = 0;
};

BarResult compare_logical_sectors_bar(const Model& model,
                                      const CycleLibrary& library,
                                      const State& reference_state,
                                      const KernelMove& logical_move,
                                      const BarConfig& config);

}  // namespace tempered_worm

#endif
