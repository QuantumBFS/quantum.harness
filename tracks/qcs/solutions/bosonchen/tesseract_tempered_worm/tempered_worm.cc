#include "tempered_worm.h"

#include <algorithm>
#include <cmath>
#include <iterator>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace tempered_worm {
namespace {

struct VectorHash {
  size_t operator()(const std::vector<uint32_t>& values) const {
    size_t hash = 0xcbf29ce484222325ULL;
    for (uint32_t value : values) {
      hash ^= static_cast<size_t>(value) + 0x9e3779b97f4a7c15ULL + (hash << 6) + (hash >> 2);
    }
    return hash;
  }
};

size_t random_index(std::mt19937_64& rng, size_t size) {
  if (size == 0) {
    throw std::invalid_argument("Cannot choose from an empty collection.");
  }
  return std::uniform_int_distribution<size_t>(0, size - 1)(rng);
}

uint32_t random_set_element(std::mt19937_64& rng, const std::set<uint32_t>& values) {
  auto it = values.begin();
  std::advance(it, random_index(rng, values.size()));
  return *it;
}

void toggle(std::set<uint32_t>& values, uint32_t value) {
  auto [it, inserted] = values.insert(value);
  if (!inserted) {
    values.erase(it);
  }
}

std::vector<uint32_t> as_sorted_vector(const std::set<uint32_t>& values) {
  return {values.begin(), values.end()};
}

std::vector<uint32_t> xor_sorted(const std::vector<uint32_t>& a,
                                 const std::vector<uint32_t>& b) {
  std::vector<uint32_t> output;
  output.reserve(a.size() + b.size());
  std::set_symmetric_difference(a.begin(), a.end(), b.begin(), b.end(),
                                std::back_inserter(output));
  return output;
}

bool metropolis_accept(std::mt19937_64& rng, double log_acceptance) {
  if (log_acceptance >= 0) {
    return true;
  }
  double u = std::generate_canonical<double, 64>(rng);
  return std::log(std::max(u, std::numeric_limits<double>::min())) < log_acceptance;
}

double fermi(double exponent) {
  if (exponent > 0) {
    double value = std::exp(-exponent);
    return value / (1 + value);
  }
  return 1 / (1 + std::exp(exponent));
}

double indicator_effective_sample_size(const std::vector<uint64_t>& series,
                                       uint64_t top_sector) {
  const size_t n = series.size();
  if (n < 2) {
    return static_cast<double>(n);
  }
  std::vector<double> values(n);
  for (size_t i = 0; i < n; ++i) {
    values[i] = series[i] == top_sector ? 1.0 : 0.0;
  }
  double mean = std::accumulate(values.begin(), values.end(), 0.0) / n;
  double variance = 0;
  for (double value : values) {
    variance += (value - mean) * (value - mean);
  }
  variance /= n;
  if (variance == 0) {
    return 0;
  }
  double tau = 1;
  const size_t max_lag = std::min<size_t>(1000, n / 2);
  for (size_t lag = 1; lag <= max_lag; ++lag) {
    double covariance = 0;
    for (size_t i = 0; i + lag < n; ++i) {
      covariance += (values[i] - mean) * (values[i + lag] - mean);
    }
    covariance /= n - lag;
    double rho = covariance / variance;
    if (rho <= 0) {
      break;
    }
    tau += 2 * rho;
  }
  return std::max(1.0, static_cast<double>(n) / tau);
}

}  // namespace

Model::Model(size_t detector_count, size_t observable_count,
             std::vector<ErrorTerm> error_terms)
    : num_detectors(detector_count),
      num_observables(observable_count),
      errors(std::move(error_terms)),
      detector_to_errors(detector_count) {
  if (num_observables > 64) {
    throw std::invalid_argument("Phase-0 supports at most 64 logical observables.");
  }
  for (size_t error_index = 0; error_index < errors.size(); ++error_index) {
    auto& detectors = errors[error_index].detectors;
    std::sort(detectors.begin(), detectors.end());
    if (std::adjacent_find(detectors.begin(), detectors.end()) != detectors.end()) {
      throw std::invalid_argument("An error term contains a duplicate detector.");
    }
    for (uint32_t detector : detectors) {
      if (detector >= num_detectors) {
        throw std::invalid_argument("An error term references an out-of-range detector.");
      }
      detector_to_errors[detector].push_back(static_cast<uint32_t>(error_index));
    }
  }
}

std::vector<uint8_t> Model::syndrome_of(
    const std::vector<uint32_t>& selected_errors) const {
  std::vector<uint8_t> syndrome(num_detectors, 0);
  for (uint32_t error_index : selected_errors) {
    if (error_index >= errors.size()) {
      throw std::invalid_argument("Selected error index is out of range.");
    }
    for (uint32_t detector : errors[error_index].detectors) {
      syndrome[detector] ^= 1;
    }
  }
  return syndrome;
}

bool Model::is_kernel_move(const std::vector<uint32_t>& selected_errors) const {
  const auto syndrome = syndrome_of(selected_errors);
  return std::none_of(syndrome.begin(), syndrome.end(), [](uint8_t bit) { return bit != 0; });
}

uint64_t Model::logical_mask_of(
    const std::vector<uint32_t>& selected_errors) const {
  uint64_t mask = 0;
  for (uint32_t error_index : selected_errors) {
    if (error_index >= errors.size()) {
      throw std::invalid_argument("Selected error index is out of range.");
    }
    mask ^= errors[error_index].logical_mask;
  }
  return mask;
}

CycleLibrary CycleLibrary::build(const Model& model, const CycleBuildConfig& config) {
  CycleLibrary output;
  std::unordered_set<std::vector<uint32_t>, VectorHash> seen;
  auto add_move = [&](std::vector<uint32_t> selected, int source) {
    std::sort(selected.begin(), selected.end());
    selected.erase(std::unique(selected.begin(), selected.end()), selected.end());
    if (selected.empty() || !model.is_kernel_move(selected)) {
      return false;
    }
    if (!seen.insert(selected).second) {
      ++output.stats.duplicate_moves_discarded;
      return false;
    }
    KernelMove move{selected, model.logical_mask_of(selected)};
    if (move.logical_mask != 0) {
      ++output.stats.logical_sector_moves;
    }
    output.moves.push_back(std::move(move));
    if (source == 0) {
      ++output.stats.zero_detector_moves;
    } else if (source == 1) {
      ++output.stats.duplicate_signature_moves;
    } else if (source == 2) {
      ++output.stats.random_closed_moves;
    } else {
      ++output.stats.logical_seed_closed_moves;
    }
    return true;
  };

  std::unordered_map<std::vector<uint32_t>, std::vector<uint32_t>, VectorHash>
      errors_by_detector_signature;
  for (size_t error_index = 0; error_index < model.errors.size(); ++error_index) {
    const auto& detectors = model.errors[error_index].detectors;
    if (detectors.empty()) {
      add_move({static_cast<uint32_t>(error_index)}, 0);
    } else {
      errors_by_detector_signature[detectors].push_back(static_cast<uint32_t>(error_index));
    }
  }
  for (const auto& [detectors, group] : errors_by_detector_signature) {
    for (size_t i = 0; i < group.size(); ++i) {
      for (size_t j = i + 1; j < group.size(); ++j) {
        add_move({group[i], group[j]}, 1);
        if (output.moves.size() >= config.max_moves) {
          return output;
        }
      }
    }
  }

  std::mt19937_64 rng(config.seed);
  if (model.errors.empty()) {
    return output;
  }
  auto try_close_worm = [&](uint32_t first_error, int source) {
    std::set<uint32_t> selected;
    std::set<uint32_t> defects;
    selected.insert(first_error);
    for (uint32_t detector : model.errors[first_error].detectors) {
      toggle(defects, detector);
    }

    size_t steps = 1;
    while (!defects.empty() && steps < config.max_steps) {
      uint32_t detector = random_set_element(rng, defects);
      const auto& candidates = model.detector_to_errors[detector];
      if (candidates.empty()) {
        break;
      }

      std::vector<double> weights(candidates.size(), 0);
      double total_weight = 0;
      for (size_t k = 0; k < candidates.size(); ++k) {
        uint32_t candidate = candidates[k];
        size_t next_defect_count = defects.size();
        for (uint32_t touched : model.errors[candidate].detectors) {
          if (defects.count(touched)) {
            --next_defect_count;
          } else {
            ++next_defect_count;
          }
        }
        double closure_gain =
            static_cast<double>(defects.size()) - static_cast<double>(next_defect_count);
        double revisit_penalty = selected.count(candidate) ? 0.25 : 1.0;
        weights[k] = revisit_penalty *
                     std::exp(config.closure_bias * closure_gain -
                              0.03 * std::max(0.0, model.errors[candidate].cost));
        total_weight += weights[k];
      }
      double draw = std::generate_canonical<double, 64>(rng) * total_weight;
      size_t chosen = candidates.size() - 1;
      for (size_t k = 0; k < candidates.size(); ++k) {
        draw -= weights[k];
        if (draw <= 0) {
          chosen = k;
          break;
        }
      }
      uint32_t error_index = candidates[chosen];
      toggle(selected, error_index);
      for (uint32_t touched : model.errors[error_index].detectors) {
        toggle(defects, touched);
      }
      ++steps;
    }

    if (defects.empty() && !selected.empty()) {
      return add_move(as_sorted_vector(selected), source);
    }
    return false;
  };

  std::vector<uint32_t> logical_errors;
  logical_errors.reserve(model.errors.size());
  for (size_t error_index = 0; error_index < model.errors.size(); ++error_index) {
    if (model.errors[error_index].logical_mask != 0) {
      logical_errors.push_back(static_cast<uint32_t>(error_index));
    }
  }
  for (size_t attempt = 0;
       attempt < config.logical_seed_attempts && output.moves.size() < config.max_moves &&
       !logical_errors.empty();
       ++attempt) {
    uint32_t first_error = logical_errors[random_index(rng, logical_errors.size())];
    if (!try_close_worm(first_error, 3)) {
      ++output.stats.logical_seed_failed_attempts;
    }
  }

  for (size_t attempt = 0;
       attempt < config.random_attempts && output.moves.size() < config.max_moves; ++attempt) {
    uint32_t first_error = static_cast<uint32_t>(random_index(rng, model.errors.size()));
    if (!try_close_worm(first_error, 2)) {
      ++output.stats.random_failed_attempts;
    }
  }
  return output;
}

AlgebraicBuildStats add_algebraic_logical_moves(
    const Model& model, CycleLibrary& library, size_t max_basis_sources,
    size_t max_new_logical_moves, size_t max_new_local_moves) {
  struct BasisEntry {
    std::vector<uint32_t> detectors;
    std::vector<uint32_t> errors;
  };

  AlgebraicBuildStats stats;
  std::vector<uint32_t> basis_sources;
  std::vector<uint32_t> logical_targets;
  basis_sources.reserve(model.errors.size());
  logical_targets.reserve(model.errors.size());
  for (size_t error_index = 0; error_index < model.errors.size(); ++error_index) {
    if (model.errors[error_index].logical_mask == 0) {
      basis_sources.push_back(static_cast<uint32_t>(error_index));
    } else {
      logical_targets.push_back(static_cast<uint32_t>(error_index));
    }
  }
  std::sort(basis_sources.begin(), basis_sources.end(),
            [&](uint32_t a, uint32_t b) {
              return model.errors[a].cost < model.errors[b].cost ||
                     (model.errors[a].cost == model.errors[b].cost && a < b);
            });
  std::sort(logical_targets.begin(), logical_targets.end(),
            [&](uint32_t a, uint32_t b) {
              return model.errors[a].cost < model.errors[b].cost ||
                     (model.errors[a].cost == model.errors[b].cost && a < b);
            });
  if (max_basis_sources > 0 && basis_sources.size() > max_basis_sources) {
    basis_sources.resize(max_basis_sources);
  }

  std::vector<BasisEntry> basis(model.num_detectors);
  auto reduce = [&](std::vector<uint32_t> detectors,
                    std::vector<uint32_t> errors) {
    while (!detectors.empty()) {
      uint32_t pivot = detectors.back();
      if (basis[pivot].detectors.empty()) {
        break;
      }
      detectors = xor_sorted(detectors, basis[pivot].detectors);
      errors = xor_sorted(errors, basis[pivot].errors);
    }
    return std::make_pair(std::move(detectors), std::move(errors));
  };

  std::unordered_set<std::vector<uint32_t>, VectorHash> seen;
  seen.reserve(library.moves.size() + logical_targets.size());
  for (const auto& move : library.moves) {
    seen.insert(move.errors);
  }
  for (uint32_t error_index : basis_sources) {
    ++stats.basis_sources_considered;
    auto [detectors, errors] =
        reduce(model.errors[error_index].detectors, {error_index});
    if (!detectors.empty()) {
      uint32_t pivot = detectors.back();
      basis[pivot] = {std::move(detectors), std::move(errors)};
      ++stats.detector_basis_rank;
    } else if (!errors.empty()) {
      ++stats.local_dependencies_found;
      if ((max_new_local_moves == 0 ||
           stats.local_moves_added < max_new_local_moves) &&
          seen.insert(errors).second) {
        if (!model.is_kernel_move(errors) ||
            model.logical_mask_of(errors) != 0) {
          throw std::runtime_error(
              "Algebraic local-move construction violated its invariants.");
        }
        library.moves.push_back({std::move(errors), 0});
        ++stats.local_moves_added;
      }
    }
  }

  for (uint32_t target : logical_targets) {
    if (max_new_logical_moves > 0 &&
        stats.moves_added >= max_new_logical_moves) {
      break;
    }
    ++stats.logical_targets_considered;
    auto [remaining_detectors, closure] =
        reduce(model.errors[target].detectors, {});
    if (!remaining_detectors.empty()) {
      continue;
    }
    ++stats.logical_targets_closed;
    std::vector<uint32_t> selected = xor_sorted(closure, {target});
    if (selected.empty() || !seen.insert(selected).second) {
      continue;
    }
    KernelMove move{selected, model.logical_mask_of(selected)};
    if (move.logical_mask == 0 || !model.is_kernel_move(move.errors)) {
      throw std::runtime_error(
          "Algebraic logical-move construction violated its invariants.");
    }
    library.moves.push_back(std::move(move));
    ++library.stats.logical_sector_moves;
    ++stats.moves_added;
  }
  return stats;
}

State State::from_errors(const Model& model,
                         const std::vector<uint32_t>& selected_errors) {
  State state;
  state.selected.assign(model.errors.size(), 0);
  for (uint32_t error_index : selected_errors) {
    if (error_index >= model.errors.size()) {
      throw std::invalid_argument("Initial-state error index is out of range.");
    }
    state.selected[error_index] ^= 1;
  }
  for (size_t error_index = 0; error_index < state.selected.size(); ++error_index) {
    if (state.selected[error_index]) {
      state.energy += model.errors[error_index].cost;
      state.logical_mask ^= model.errors[error_index].logical_mask;
    }
  }
  return state;
}

double State::delta_energy(const Model& model, const KernelMove& move) const {
  double delta = 0;
  for (uint32_t error_index : move.errors) {
    delta += selected.at(error_index) ? -model.errors[error_index].cost
                                      : model.errors[error_index].cost;
  }
  return delta;
}

void State::apply(const KernelMove& move, double delta) {
  for (uint32_t error_index : move.errors) {
    selected.at(error_index) ^= 1;
  }
  energy += delta;
  logical_mask ^= move.logical_mask;
}

std::vector<uint32_t> State::selected_errors() const {
  std::vector<uint32_t> output;
  for (size_t error_index = 0; error_index < selected.size(); ++error_index) {
    if (selected[error_index]) {
      output.push_back(static_cast<uint32_t>(error_index));
    }
  }
  return output;
}

SamplerResult sample_logical_sector(const Model& model, const CycleLibrary& library,
                                    const State& initial_state,
                                    const SamplerConfig& config) {
  if (config.betas.empty()) {
    throw std::invalid_argument("At least one inverse temperature is required.");
  }
  if (config.logical_move_probability < 0 || config.logical_move_probability > 1) {
    throw std::invalid_argument("Logical-move probability must lie in [0, 1].");
  }
  auto target_it = std::find(config.betas.begin(), config.betas.end(), 1.0);
  if (target_it == config.betas.end()) {
    throw std::invalid_argument("The inverse-temperature ladder must contain beta=1.");
  }
  const size_t target_index = target_it - config.betas.begin();
  std::mt19937_64 rng(config.seed);
  std::vector<State> replicas(config.betas.size(), initial_state);
  std::vector<size_t> labels(config.betas.size());
  std::iota(labels.begin(), labels.end(), 0);
  std::vector<uint8_t> visited_hot(config.betas.size(), 0);
  std::vector<uint8_t> visited_cold_after_hot(config.betas.size(), 0);
  std::vector<size_t> logical_move_indices;
  std::vector<size_t> local_move_indices;
  for (size_t move_index = 0; move_index < library.moves.size(); ++move_index) {
    if (library.moves[move_index].logical_mask != 0) {
      logical_move_indices.push_back(move_index);
    } else {
      local_move_indices.push_back(move_index);
    }
  }

  SamplerResult result;
  result.minimum_energy_seen = initial_state.energy;
  std::vector<uint64_t> target_series;
  target_series.reserve(config.measurement_sweeps);
  const size_t total_sweeps = config.burn_in_sweeps + config.measurement_sweeps;

  for (size_t sweep = 0; sweep < total_sweeps; ++sweep) {
    if (!library.moves.empty()) {
      for (size_t replica_index = 0; replica_index < replicas.size(); ++replica_index) {
        for (size_t update = 0; update < config.moves_per_sweep; ++update) {
          bool propose_logical =
              !logical_move_indices.empty() &&
              (local_move_indices.empty() ||
               std::generate_canonical<double, 64>(rng) <
                   config.logical_move_probability);
          const auto& proposal_pool =
              propose_logical ? logical_move_indices : local_move_indices;
          const KernelMove& move =
              library.moves[proposal_pool[random_index(rng, proposal_pool.size())]];
          double delta = replicas[replica_index].delta_energy(model, move);
          ++result.move_attempts;
          if (propose_logical) {
            ++result.logical_move_attempts;
          }
          if (metropolis_accept(rng, -config.betas[replica_index] * delta)) {
            replicas[replica_index].apply(move, delta);
            ++result.move_accepts;
            if (propose_logical) {
              ++result.logical_move_accepts;
            }
            result.minimum_energy_seen =
                std::min(result.minimum_energy_seen, replicas[replica_index].energy);
          }
        }
      }
    }

    if (replicas.size() > 1 && config.exchange_interval > 0 &&
        (sweep + 1) % config.exchange_interval == 0) {
      const size_t parity = sweep & 1;
      for (size_t i = parity; i + 1 < replicas.size(); i += 2) {
        double log_acceptance =
            (config.betas[i] - config.betas[i + 1]) *
            (replicas[i].energy - replicas[i + 1].energy);
        ++result.exchange_attempts;
        if (metropolis_accept(rng, log_acceptance)) {
          std::swap(replicas[i], replicas[i + 1]);
          std::swap(labels[i], labels[i + 1]);
          ++result.exchange_accepts;
        }
      }
    }

    if (!labels.empty()) {
      visited_hot[labels.front()] = 1;
      size_t cold_label = labels.back();
      if (visited_hot[cold_label]) {
        visited_cold_after_hot[cold_label] = 1;
      }
      size_t hot_label = labels.front();
      if (visited_cold_after_hot[hot_label]) {
        ++result.completed_temperature_round_trips;
        visited_hot[hot_label] = 0;
        visited_cold_after_hot[hot_label] = 0;
      }
    }

    if (sweep >= config.burn_in_sweeps) {
      uint64_t logical = replicas[target_index].logical_mask;
      if (!target_series.empty() && target_series.back() != logical) {
        ++result.target_logical_transitions;
      }
      ++result.logical_counts[logical];
      target_series.push_back(logical);
    }
  }

  result.target_samples = target_series.size();
  result.distinct_logical_sectors = result.logical_counts.size();
  std::vector<std::pair<size_t, uint64_t>> ranked;
  ranked.reserve(result.logical_counts.size());
  for (const auto& [logical, count] : result.logical_counts) {
    ranked.emplace_back(count, logical);
  }
  std::sort(ranked.begin(), ranked.end(),
            [](const auto& a, const auto& b) {
              return a.first > b.first || (a.first == b.first && a.second < b.second);
            });
  if (!ranked.empty()) {
    result.predicted_logical_mask = ranked.front().second;
    result.top_sector_fraction =
        static_cast<double>(ranked.front().first) / result.target_samples;
    size_t second = ranked.size() > 1 ? ranked[1].first : 0;
    result.top_two_margin =
        static_cast<double>(ranked.front().first - second) / result.target_samples;
    result.effective_sample_size =
        indicator_effective_sample_size(target_series, result.predicted_logical_mask);
  }
  return result;
}

BarResult compare_logical_sectors_bar(const Model& model,
                                      const CycleLibrary& library,
                                      const State& reference_state,
                                      const KernelMove& logical_move,
                                      const BarConfig& config) {
  if (logical_move.logical_mask == 0 || !model.is_kernel_move(logical_move.errors)) {
    throw std::invalid_argument(
        "BAR comparison requires a valid logical-sector-changing kernel move.");
  }
  if (config.measurement_sweeps == 0) {
    throw std::invalid_argument("BAR comparison requires measurement samples.");
  }

  std::vector<size_t> local_move_indices;
  for (size_t move_index = 0; move_index < library.moves.size(); ++move_index) {
    if (library.moves[move_index].logical_mask == 0) {
      local_move_indices.push_back(move_index);
    }
  }

  State forward_state = reference_state;
  State reverse_state = reference_state;
  reverse_state.apply(logical_move,
                      reverse_state.delta_energy(model, logical_move));
  std::mt19937_64 rng(config.seed);
  BarResult result;
  std::vector<double> forward_work;
  std::vector<double> reverse_work;
  forward_work.reserve(config.measurement_sweeps);
  reverse_work.reserve(config.measurement_sweeps);

  auto update_chain = [&](State& state) {
    if (local_move_indices.empty()) {
      return;
    }
    for (size_t update = 0; update < config.moves_per_sweep; ++update) {
      const KernelMove& move =
          library.moves[local_move_indices[random_index(rng, local_move_indices.size())]];
      double delta = state.delta_energy(model, move);
      ++result.local_move_attempts;
      if (metropolis_accept(rng, -delta)) {
        state.apply(move, delta);
        ++result.local_move_accepts;
      }
    }
  };

  const size_t total_sweeps =
      config.burn_in_sweeps + config.measurement_sweeps;
  for (size_t sweep = 0; sweep < total_sweeps; ++sweep) {
    update_chain(forward_state);
    update_chain(reverse_state);
    if (sweep >= config.burn_in_sweeps) {
      forward_work.push_back(
          forward_state.delta_energy(model, logical_move));
      reverse_work.push_back(
          reverse_state.delta_energy(model, logical_move));
    }
  }
  result.forward_samples = forward_work.size();
  result.reverse_samples = reverse_work.size();

  auto bar_residual = [&](double delta_free_energy) {
    double forward_sum = 0;
    for (double work : forward_work) {
      forward_sum += fermi(work - delta_free_energy);
    }
    double reverse_sum = 0;
    for (double work : reverse_work) {
      reverse_sum += fermi(work + delta_free_energy);
    }
    return forward_sum / forward_work.size() -
           reverse_sum / reverse_work.size();
  };

  double lower = -1;
  double upper = 1;
  while (bar_residual(lower) > 0) {
    lower *= 2;
  }
  while (bar_residual(upper) < 0) {
    upper *= 2;
  }
  for (size_t iteration = 0; iteration < 100; ++iteration) {
    double midpoint = 0.5 * (lower + upper);
    if (bar_residual(midpoint) < 0) {
      lower = midpoint;
    } else {
      upper = midpoint;
    }
  }
  result.delta_free_energy = 0.5 * (lower + upper);

  double overlap = 0;
  for (double work : forward_work) {
    double value = fermi(work - result.delta_free_energy);
    overlap += value * (1 - value);
  }
  for (double work : reverse_work) {
    double value = fermi(work + result.delta_free_energy);
    overlap += value * (1 - value);
  }
  result.overlap_score =
      4 * overlap / (forward_work.size() + reverse_work.size());
  return result;
}

}  // namespace tempered_worm
