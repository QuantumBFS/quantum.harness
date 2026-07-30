#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "nlohmann/json.hpp"
#include "src/tesseract.h"
#include "src/utils.h"
#include "stim.h"
#include "tempered_worm.h"

namespace tw = tempered_worm;
using json = nlohmann::json;

namespace {

constexpr double kBarMinimumOverlap = 0.01;

struct Arguments {
  std::string circuit_path;
  std::string output_path;
  size_t shots = 10;
  uint64_t sample_seed = 1;
  uint64_t mc_seed = 2;
  int beam = 15;
  size_t pqlimit = 200000;
  size_t num_det_orders = 16;
  size_t seed_detector_order = 2;
  size_t seed_beam = 2;
  size_t cycle_attempts = 4000;
  size_t logical_seed_attempts = 2000;
  size_t cycle_max_steps = 64;
  size_t cycle_max_moves = 20000;
  size_t algebraic_basis_sources = 0;
  size_t algebraic_max_moves = 4096;
  size_t algebraic_max_local_moves = 4096;
  size_t burn_in = 500;
  size_t measurements = 2000;
  size_t moves_per_sweep = 2;
  size_t bar_max_sectors = 64;
  size_t bar_max_enumerated_sectors = 65536;
  size_t bar_min_local_accepts = 50;
  size_t bar_trigger_energy = 20;
};

size_t parse_size(const std::string& name, const std::string& value) {
  size_t consumed = 0;
  unsigned long long parsed = std::stoull(value, &consumed);
  if (consumed != value.size()) {
    throw std::invalid_argument("Invalid integer for " + name + ": " + value);
  }
  return static_cast<size_t>(parsed);
}

Arguments parse_arguments(int argc, char** argv) {
  Arguments args;
  std::map<std::string, std::string*> string_options{
      {"--circuit", &args.circuit_path},
      {"--out", &args.output_path},
  };
  std::map<std::string, size_t*> size_options{
      {"--shots", &args.shots},
      {"--pqlimit", &args.pqlimit},
      {"--num-det-orders", &args.num_det_orders},
      {"--seed-detector-order", &args.seed_detector_order},
      {"--seed-beam", &args.seed_beam},
      {"--cycle-attempts", &args.cycle_attempts},
      {"--logical-seed-attempts", &args.logical_seed_attempts},
      {"--cycle-max-steps", &args.cycle_max_steps},
      {"--cycle-max-moves", &args.cycle_max_moves},
      {"--algebraic-basis-sources", &args.algebraic_basis_sources},
      {"--algebraic-max-moves", &args.algebraic_max_moves},
      {"--algebraic-max-local-moves",
       &args.algebraic_max_local_moves},
      {"--burn-in", &args.burn_in},
      {"--measurements", &args.measurements},
      {"--moves-per-sweep", &args.moves_per_sweep},
      {"--bar-max-sectors", &args.bar_max_sectors},
      {"--bar-max-enumerated-sectors",
       &args.bar_max_enumerated_sectors},
      {"--bar-min-local-accepts", &args.bar_min_local_accepts},
      {"--bar-trigger-energy", &args.bar_trigger_energy},
  };
  for (int i = 1; i < argc; ++i) {
    std::string option = argv[i];
    if (i + 1 >= argc) {
      throw std::invalid_argument("Missing value for " + option);
    }
    std::string value = argv[++i];
    if (auto it = string_options.find(option); it != string_options.end()) {
      *it->second = value;
    } else if (auto it = size_options.find(option); it != size_options.end()) {
      *it->second = parse_size(option, value);
    } else if (option == "--sample-seed") {
      args.sample_seed = parse_size(option, value);
    } else if (option == "--mc-seed") {
      args.mc_seed = parse_size(option, value);
    } else if (option == "--beam") {
      args.beam = static_cast<int>(parse_size(option, value));
    } else {
      throw std::invalid_argument("Unknown option: " + option);
    }
  }
  if (args.circuit_path.empty() || args.output_path.empty()) {
    throw std::invalid_argument("--circuit and --out are required.");
  }
  if (args.shots == 0 || args.num_det_orders == 0 || args.measurements == 0) {
    throw std::invalid_argument("shots, num-det-orders, and measurements must be positive.");
  }
  return args;
}

stim::Circuit read_circuit(const std::string& path) {
  FILE* file = fopen(path.c_str(), "r");
  if (file == nullptr) {
    throw std::invalid_argument("Could not open circuit: " + path);
  }
  stim::Circuit circuit = stim::Circuit::from_file(file);
  fclose(file);
  return circuit;
}

uint64_t logical_mask_from_indices(const std::vector<int>& observables) {
  uint64_t mask = 0;
  for (int observable : observables) {
    if (observable < 0 || observable >= 64) {
      throw std::invalid_argument("Observable index does not fit in a uint64 mask.");
    }
    mask ^= uint64_t{1} << observable;
  }
  return mask;
}

uint64_t logical_mask_from_shot(const stim::SparseShot& shot, size_t num_observables) {
  if (num_observables > 64) {
    throw std::invalid_argument("Phase-0 supports at most 64 logical observables.");
  }
  uint64_t mask = 0;
  for (size_t observable = 0; observable < num_observables; ++observable) {
    if (shot.obs_mask[observable]) {
      mask |= uint64_t{1} << observable;
    }
  }
  return mask;
}

std::vector<uint32_t> internal_errors_from_prediction(
    const TesseractDecoder& decoder, const std::vector<size_t>& predicted_errors) {
  std::vector<uint8_t> parity(decoder.errors.size(), 0);
  for (size_t dem_error_index : predicted_errors) {
    size_t internal = decoder.dem_error_to_error.at(dem_error_index);
    if (internal == std::numeric_limits<size_t>::max()) {
      throw std::runtime_error("Tesseract prediction references a removed error.");
    }
    parity.at(internal) ^= 1;
  }
  std::vector<uint32_t> output;
  for (size_t error_index = 0; error_index < parity.size(); ++error_index) {
    if (parity[error_index]) {
      output.push_back(static_cast<uint32_t>(error_index));
    }
  }
  return output;
}

std::vector<uint8_t> syndrome_from_hits(size_t num_detectors,
                                        const std::vector<uint64_t>& hits) {
  std::vector<uint8_t> syndrome(num_detectors, 0);
  for (uint64_t detector : hits) {
    if (detector >= num_detectors) {
      throw std::invalid_argument("Shot references an out-of-range detector.");
    }
    syndrome[detector] ^= 1;
  }
  return syndrome;
}

tw::Model model_from_decoder(const TesseractDecoder& decoder) {
  std::vector<tw::ErrorTerm> terms;
  terms.reserve(decoder.errors.size());
  for (const auto& error : decoder.errors) {
    tw::ErrorTerm term;
    term.cost = error.likelihood_cost;
    term.detectors.assign(error.symptom.detectors.begin(), error.symptom.detectors.end());
    term.logical_mask = logical_mask_from_indices(error.symptom.observables);
    terms.push_back(std::move(term));
  }
  return tw::Model(decoder.num_detectors, decoder.num_observables, std::move(terms));
}

template <typename Function>
double timed_seconds(Function&& function) {
  auto start = std::chrono::steady_clock::now();
  function();
  auto end = std::chrono::steady_clock::now();
  return std::chrono::duration<double>(end - start).count();
}

json logical_counts_to_json(const std::unordered_map<uint64_t, size_t>& counts) {
  json output = json::object();
  for (const auto& [logical, count] : counts) {
    output[std::to_string(logical)] = count;
  }
  return output;
}

size_t binary_rank(const std::vector<uint64_t>& values) {
  std::vector<uint64_t> basis(64, 0);
  size_t rank = 0;
  for (uint64_t value : values) {
    while (value != 0) {
      size_t pivot = 63 - static_cast<size_t>(__builtin_clzll(value));
      if (basis[pivot] == 0) {
        basis[pivot] = value;
        ++rank;
        break;
      }
      value ^= basis[pivot];
    }
  }
  return rank;
}

std::vector<uint32_t> xor_error_sets(const std::vector<uint32_t>& a,
                                     const std::vector<uint32_t>& b) {
  std::vector<uint32_t> output;
  output.reserve(a.size() + b.size());
  std::set_symmetric_difference(a.begin(), a.end(), b.begin(), b.end(),
                                std::back_inserter(output));
  return output;
}

std::vector<tw::KernelMove> logical_move_basis(
    const tw::Model& model, const tw::CycleLibrary& library,
    const tw::State& reference_state) {
  std::vector<size_t> ordered;
  for (size_t move_index = 0; move_index < library.moves.size(); ++move_index) {
    if (library.moves[move_index].logical_mask != 0) {
      ordered.push_back(move_index);
    }
  }
  std::sort(ordered.begin(), ordered.end(), [&](size_t a, size_t b) {
    double a_delta =
        std::abs(reference_state.delta_energy(model, library.moves[a]));
    double b_delta =
        std::abs(reference_state.delta_energy(model, library.moves[b]));
    return a_delta < b_delta || (a_delta == b_delta && a < b);
  });

  std::vector<uint64_t> masks(64, 0);
  std::vector<tw::KernelMove> output;
  for (size_t move_index : ordered) {
    uint64_t reduced = library.moves[move_index].logical_mask;
    while (reduced != 0) {
      size_t pivot = 63 - static_cast<size_t>(__builtin_clzll(reduced));
      if (masks[pivot] == 0) {
        masks[pivot] = reduced;
        output.push_back(library.moves[move_index]);
        break;
      }
      reduced ^= masks[pivot];
    }
  }
  return output;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    Arguments args = parse_arguments(argc, argv);
    stim::Circuit circuit = read_circuit(args.circuit_path);
    stim::DetectorErrorModel dem = stim::ErrorAnalyzer::circuit_to_detector_error_model(
        circuit, /*decompose_errors=*/false, /*fold_loops=*/true,
        /*allow_gauge_detectors=*/true,
        /*approximate_disjoint_errors_threshold=*/1,
        /*ignore_decomposition_failures=*/false,
        /*block_decomposition_from_introducing_remnant_edges=*/false);

    TesseractConfig decoder_config{dem};
    decoder_config.det_beam = args.beam;
    decoder_config.beam_climbing = true;
    decoder_config.no_revisit_dets = true;
    decoder_config.pqlimit = args.pqlimit;
    decoder_config.det_orders =
        build_det_orders(dem, args.num_det_orders, DetOrder::DetIndex, 2384753);
    TesseractDecoder baseline_decoder(decoder_config);
    TesseractDecoder seed_decoder(decoder_config);
    tw::Model model = model_from_decoder(seed_decoder);

    std::vector<stim::SparseShot> shots;
    sample_shots(args.sample_seed, circuit, args.shots, shots);

    tw::CycleBuildConfig cycle_config;
    cycle_config.random_attempts = args.cycle_attempts;
    cycle_config.logical_seed_attempts = args.logical_seed_attempts;
    cycle_config.max_steps = args.cycle_max_steps;
    cycle_config.max_moves = args.cycle_max_moves;
    cycle_config.seed = args.mc_seed;
    tw::CycleLibrary library;
    tw::AlgebraicBuildStats algebraic_stats;
    size_t algebraic_basis_sources =
        args.algebraic_basis_sources > 0
            ? args.algebraic_basis_sources
            : std::max<size_t>(20000, 8 * model.num_detectors);
    double preprocessing_seconds = timed_seconds([&] {
      library = tw::CycleLibrary::build(model, cycle_config);
      algebraic_stats = tw::add_algebraic_logical_moves(
          model, library, algebraic_basis_sources,
          args.algebraic_max_moves, args.algebraic_max_local_moves);
    });
    std::vector<uint64_t> logical_move_masks;
    logical_move_masks.reserve(library.stats.logical_sector_moves);
    for (const auto& move : library.moves) {
      if (move.logical_mask != 0) {
        logical_move_masks.push_back(move.logical_mask);
      }
    }
    std::sort(logical_move_masks.begin(), logical_move_masks.end());
    logical_move_masks.erase(
        std::unique(logical_move_masks.begin(), logical_move_masks.end()),
        logical_move_masks.end());
    size_t logical_move_rank = binary_rank(logical_move_masks);

    std::cout << "phase0 model errors=" << model.errors.size()
              << " detectors=" << model.num_detectors
              << " observables=" << model.num_observables
              << " moves=" << library.moves.size()
              << " sector_moves=" << library.stats.logical_sector_moves
              << " sector_rank=" << logical_move_rank
              << " algebraic_moves=" << algebraic_stats.moves_added
              << " preprocessing_seconds=" << preprocessing_seconds << std::endl;

    json shot_reports = json::array();
    size_t baseline_errors = 0;
    size_t seed_errors = 0;
    size_t mc_errors = 0;
    size_t bar_errors = 0;
    size_t prediction_mismatches = 0;
    size_t bar_prediction_mismatches = 0;
    size_t seed_fallbacks = 0;
    size_t seed_retries = 0;
    double baseline_seconds = 0;
    double seed_seconds = 0;
    double sampler_seconds = 0;
    double bar_seconds = 0;

    for (size_t shot_index = 0; shot_index < shots.size(); ++shot_index) {
      const auto& shot = shots[shot_index];
      uint64_t actual_logical =
          logical_mask_from_shot(shot, model.num_observables);

      baseline_seconds += timed_seconds(
          [&] { baseline_decoder.decode_to_errors(shot.hits); });
      uint64_t baseline_logical = logical_mask_from_indices(
          baseline_decoder.get_flipped_observables(
              baseline_decoder.predicted_errors_buffer));
      bool baseline_failed = baseline_decoder.low_confidence_flag;
      baseline_errors += baseline_failed || baseline_logical != actual_logical;

      auto seed_start = std::chrono::steady_clock::now();
      seed_decoder.decode_to_errors(
          shot.hits, args.seed_detector_order % args.num_det_orders,
          args.seed_beam);
      bool seed_initial_low_confidence =
          seed_decoder.low_confidence_flag;
      std::vector<size_t> seed_prediction = seed_decoder.predicted_errors_buffer;
      std::vector<uint32_t> seed_internal;
      size_t this_seed_retries = 0;
      bool this_seed_full_fallback = false;
      auto capture_valid_seed = [&]() {
        try {
          seed_prediction = seed_decoder.predicted_errors_buffer;
          seed_internal =
              internal_errors_from_prediction(seed_decoder, seed_prediction);
          return model.syndrome_of(seed_internal) ==
                 syndrome_from_hits(model.num_detectors, shot.hits);
        } catch (const std::exception&) {
          seed_internal.clear();
          return false;
        }
      };
      bool seed_valid = capture_valid_seed();
      for (size_t retry = 0; !seed_valid && retry < 6; ++retry) {
        size_t retry_order =
            (args.seed_detector_order + retry) % args.num_det_orders;
        size_t retry_beam = retry < 3 ? 4 : 8;
        seed_decoder.decode_to_errors(
            shot.hits, retry_order, retry_beam);
        ++seed_retries;
        ++this_seed_retries;
        seed_valid = capture_valid_seed();
      }
      if (!seed_valid) {
        seed_decoder.decode_to_errors(shot.hits);
        ++seed_fallbacks;
        this_seed_full_fallback = true;
        seed_valid = capture_valid_seed();
      }
      if (!seed_valid) {
        throw std::runtime_error(
            "Independent seed escalation did not reproduce the shot syndrome.");
      }
      bool seed_failed = seed_decoder.low_confidence_flag;
      uint64_t seed_logical = logical_mask_from_indices(
          seed_decoder.get_flipped_observables(seed_prediction));
      seed_errors += seed_logical != actual_logical;
      tw::State initial = tw::State::from_errors(model, seed_internal);
      if (initial.logical_mask != seed_logical) {
        throw std::runtime_error(
            "Internal seed logical mask disagrees with the DEM prediction.");
      }
      auto seed_end = std::chrono::steady_clock::now();
      seed_seconds +=
          std::chrono::duration<double>(seed_end - seed_start).count();

      tw::SamplerConfig sampler_config;
      sampler_config.burn_in_sweeps = args.burn_in;
      sampler_config.measurement_sweeps = args.measurements;
      sampler_config.moves_per_sweep = args.moves_per_sweep;
      sampler_config.seed =
          args.mc_seed + 0x9e3779b97f4a7c15ULL * (shot_index + 1);
      tw::SamplerResult sampler_result;
      double this_sampler_seconds = timed_seconds([&] {
        sampler_result =
            tw::sample_logical_sector(model, library, initial, sampler_config);
      });
      sampler_seconds += this_sampler_seconds;

      uint64_t mc_logical = sampler_result.predicted_logical_mask;
      mc_errors += mc_logical != actual_logical;
      prediction_mismatches += mc_logical != baseline_logical;

      auto bar_start = std::chrono::steady_clock::now();
      std::unordered_map<uint64_t, tw::KernelMove> bridge_by_mask;
      auto consider_bridge = [&](const tw::KernelMove& move) {
        if (move.logical_mask == 0) {
          return;
        }
        auto [it, inserted] =
            bridge_by_mask.emplace(move.logical_mask, move);
        if (!inserted &&
            initial.delta_energy(model, move) <
                initial.delta_energy(model, it->second)) {
          it->second = move;
        }
      };
      for (const auto& move : library.moves) {
        consider_bridge(move);
      }

      std::vector<tw::KernelMove> sector_basis =
          logical_move_basis(model, library, initial);
      bool sector_enumeration_complete = true;
      std::vector<tw::KernelMove> generated_bridges(1);
      for (const auto& basis_move : sector_basis) {
        if (generated_bridges.size() >
            args.bar_max_enumerated_sectors / 2) {
          sector_enumeration_complete = false;
          break;
        }
        size_t prior_size = generated_bridges.size();
        for (size_t i = 0; i < prior_size; ++i) {
          tw::KernelMove combined;
          combined.errors =
              xor_error_sets(generated_bridges[i].errors, basis_move.errors);
          combined.logical_mask =
              generated_bridges[i].logical_mask ^ basis_move.logical_mask;
          generated_bridges.push_back(std::move(combined));
        }
      }
      if (sector_enumeration_complete) {
        for (size_t i = 1; i < generated_bridges.size(); ++i) {
          if (!model.is_kernel_move(generated_bridges[i].errors)) {
            throw std::runtime_error(
                "A composed logical bridge is not in the detector kernel.");
          }
          consider_bridge(generated_bridges[i]);
        }
      }

      size_t bar_reachable_sectors = bridge_by_mask.size();
      std::vector<tw::KernelMove> bridges;
      bridges.reserve(bridge_by_mask.size());
      for (auto& [logical_mask, move] : bridge_by_mask) {
        (void)logical_mask;
        bridges.push_back(std::move(move));
      }
      std::sort(bridges.begin(), bridges.end(), [&](const auto& a, const auto& b) {
        return initial.delta_energy(model, a) <
               initial.delta_energy(model, b);
      });
      double minimum_bridge_energy =
          bridges.empty() ? std::numeric_limits<double>::infinity()
                          : initial.delta_energy(model, bridges.front());
      bool bar_triggered =
          seed_initial_low_confidence ||
          minimum_bridge_energy <
              static_cast<double>(args.bar_trigger_energy);
      bool bar_candidates_truncated = bridges.size() > args.bar_max_sectors;
      if (bar_candidates_truncated) {
        bridges.resize(args.bar_max_sectors);
      }

      uint64_t bar_logical = seed_logical;
      double best_relative_free_energy = 0;
      size_t bar_reliable_comparisons = 0;
      json bar_comparisons = json::array();
      if (bar_triggered) {
        for (size_t candidate_index = 0; candidate_index < bridges.size();
             ++candidate_index) {
          const auto& bridge = bridges[candidate_index];
          uint64_t logical_mask = bridge.logical_mask;
          tw::BarConfig bar_config;
          bar_config.burn_in_sweeps = args.burn_in;
          bar_config.measurement_sweeps = args.measurements;
          bar_config.moves_per_sweep = args.moves_per_sweep;
          bar_config.seed =
              args.mc_seed + 0xd1b54a32d192ed03ULL * (shot_index + 1) +
              candidate_index;
          tw::BarResult bar_result = tw::compare_logical_sectors_bar(
              model, library, initial, bridge, bar_config);
          double bridge_energy_delta =
              initial.delta_energy(model, bridge);
          bool bar_reliable =
              bar_result.overlap_score >= kBarMinimumOverlap &&
              bar_result.local_move_accepts >= args.bar_min_local_accepts;
          bool selection_eligible = bar_reliable || bridge_energy_delta < 0;
          bar_reliable_comparisons += bar_reliable;
          double selection_score =
              bar_reliable ? bar_result.delta_free_energy
                           : bridge_energy_delta;
          if (selection_eligible &&
              selection_score < best_relative_free_energy) {
            best_relative_free_energy = selection_score;
            bar_logical = seed_logical ^ logical_mask;
          }
          bar_comparisons.push_back({
              {"logical_mask_delta", logical_mask},
              {"bridge_move_errors", bridge.errors.size()},
              {"bridge_energy_delta", bridge_energy_delta},
              {"delta_free_energy", bar_result.delta_free_energy},
              {"overlap_score", bar_result.overlap_score},
              {"bar_reliable", bar_reliable},
              {"selection_eligible", selection_eligible},
              {"selection_score", selection_score},
              {"local_move_attempts", bar_result.local_move_attempts},
              {"local_move_accepts", bar_result.local_move_accepts},
          });
        }
      }
      auto bar_end = std::chrono::steady_clock::now();
      double this_bar_seconds =
          std::chrono::duration<double>(bar_end - bar_start).count();
      bar_seconds += this_bar_seconds;
      bar_errors += bar_logical != actual_logical;
      bar_prediction_mismatches += bar_logical != baseline_logical;

      shot_reports.push_back({
          {"shot", shot_index},
          {"num_detections", shot.hits.size()},
          {"actual_logical_mask", actual_logical},
          {"baseline_logical_mask", baseline_logical},
          {"baseline_low_confidence", baseline_failed},
          {"seed_logical_mask", seed_logical},
          {"seed_initial_low_confidence",
           seed_initial_low_confidence},
          {"seed_low_confidence", seed_failed},
          {"seed_retries", this_seed_retries},
          {"seed_full_fallback", this_seed_full_fallback},
          {"seed_num_errors", seed_internal.size()},
          {"mc_logical_mask", mc_logical},
          {"mc_matches_baseline", mc_logical == baseline_logical},
          {"mc_is_logical_error", mc_logical != actual_logical},
          {"bar_logical_mask", bar_logical},
          {"bar_matches_baseline", bar_logical == baseline_logical},
          {"bar_is_logical_error", bar_logical != actual_logical},
          {"bar_best_relative_free_energy", best_relative_free_energy},
          {"bar_triggered", bar_triggered},
          {"bar_minimum_bridge_energy", minimum_bridge_energy},
          {"bar_reliable_comparisons", bar_reliable_comparisons},
          {"bar_candidate_sectors", bridges.size()},
          {"bar_reachable_sectors", bar_reachable_sectors},
          {"bar_sector_basis_rank", sector_basis.size()},
          {"bar_sector_enumeration_complete",
           sector_enumeration_complete},
          {"bar_candidates_truncated", bar_candidates_truncated},
          {"bar_comparisons", bar_comparisons},
          {"bar_seconds", this_bar_seconds},
          {"logical_counts", logical_counts_to_json(sampler_result.logical_counts)},
          {"distinct_logical_sectors", sampler_result.distinct_logical_sectors},
          {"top_sector_fraction", sampler_result.top_sector_fraction},
          {"top_two_margin", sampler_result.top_two_margin},
          {"effective_sample_size", sampler_result.effective_sample_size},
          {"move_attempts", sampler_result.move_attempts},
          {"move_accepts", sampler_result.move_accepts},
          {"logical_move_attempts", sampler_result.logical_move_attempts},
          {"logical_move_accepts", sampler_result.logical_move_accepts},
          {"target_logical_transitions",
           sampler_result.target_logical_transitions},
          {"exchange_attempts", sampler_result.exchange_attempts},
          {"exchange_accepts", sampler_result.exchange_accepts},
          {"temperature_round_trips",
           sampler_result.completed_temperature_round_trips},
          {"minimum_energy_seen", sampler_result.minimum_energy_seen},
          {"sampler_seconds", this_sampler_seconds},
      });
      std::cout << "shot=" << shot_index
                << " detections=" << shot.hits.size()
                << " baseline=" << baseline_logical
                << " seed=" << seed_logical
                << " mc=" << mc_logical
                << " bar=" << bar_logical
                << " actual=" << actual_logical
                << " sectors=" << sampler_result.distinct_logical_sectors
                << " margin=" << sampler_result.top_two_margin
                << " ess=" << sampler_result.effective_sample_size
                << " round_trips="
                << sampler_result.completed_temperature_round_trips
                << std::endl;
    }

    const double candidate_seconds = seed_seconds + bar_seconds;
    json report{
        {"schema_version", 1},
        {"status", "phase0_mixing_diagnostic"},
        {"timing_protocol", "exploratory_preprocessing_excluded_no_warmup_exclusion"},
        {"circuit", args.circuit_path},
        {"shots", shots.size()},
        {"sample_seed", args.sample_seed},
        {"mc_seed", args.mc_seed},
        {"model",
         {
             {"num_errors", model.errors.size()},
             {"num_detectors", model.num_detectors},
             {"num_observables", model.num_observables},
         }},
        {"cycle_library",
         {
             {"moves", library.moves.size()},
             {"logical_sector_moves", library.stats.logical_sector_moves},
             {"unique_logical_masks", logical_move_masks.size()},
             {"logical_mask_rank", logical_move_rank},
             {"duplicate_signature_moves",
              library.stats.duplicate_signature_moves},
             {"zero_detector_moves", library.stats.zero_detector_moves},
             {"random_closed_moves", library.stats.random_closed_moves},
             {"random_failed_attempts",
              library.stats.random_failed_attempts},
             {"logical_seed_closed_moves",
              library.stats.logical_seed_closed_moves},
             {"logical_seed_failed_attempts",
              library.stats.logical_seed_failed_attempts},
             {"algebraic_basis_sources_considered",
              algebraic_stats.basis_sources_considered},
             {"algebraic_detector_basis_rank",
              algebraic_stats.detector_basis_rank},
             {"algebraic_local_dependencies_found",
              algebraic_stats.local_dependencies_found},
             {"algebraic_local_moves_added",
              algebraic_stats.local_moves_added},
             {"algebraic_logical_targets_considered",
              algebraic_stats.logical_targets_considered},
             {"algebraic_logical_targets_closed",
              algebraic_stats.logical_targets_closed},
             {"algebraic_moves_added", algebraic_stats.moves_added},
             {"duplicates_discarded",
              library.stats.duplicate_moves_discarded},
             {"preprocessing_seconds", preprocessing_seconds},
         }},
        {"sampler",
         {
             {"betas", tw::SamplerConfig{}.betas},
             {"burn_in_sweeps", args.burn_in},
             {"measurement_sweeps", args.measurements},
             {"moves_per_sweep", args.moves_per_sweep},
             {"logical_move_probability",
              tw::SamplerConfig{}.logical_move_probability},
         }},
        {"bar",
         {
             {"burn_in_sweeps", args.burn_in},
             {"measurement_sweeps", args.measurements},
             {"moves_per_sweep", args.moves_per_sweep},
             {"max_candidate_sectors", args.bar_max_sectors},
             {"max_enumerated_sectors",
              args.bar_max_enumerated_sectors},
             {"minimum_overlap", kBarMinimumOverlap},
             {"minimum_local_accepts",
              args.bar_min_local_accepts},
             {"trigger_energy", args.bar_trigger_energy},
         }},
        {"summary",
         {
             {"baseline_errors", baseline_errors},
             {"seed_errors", seed_errors},
             {"mc_errors", mc_errors},
             {"mc_baseline_prediction_mismatches", prediction_mismatches},
             {"bar_errors", bar_errors},
             {"bar_baseline_prediction_mismatches",
              bar_prediction_mismatches},
             {"seed_retries", seed_retries},
             {"seed_fallbacks", seed_fallbacks},
             {"baseline_seconds", baseline_seconds},
             {"seed_seconds", seed_seconds},
             {"sampler_seconds", sampler_seconds},
             {"bar_seconds", bar_seconds},
             {"candidate_seconds", candidate_seconds},
             {"exploratory_speedup",
              candidate_seconds > 0 ? baseline_seconds / candidate_seconds : 0},
         }},
        {"shot_results", shot_reports},
    };

    std::ofstream output(args.output_path);
    if (!output) {
      throw std::runtime_error("Could not open output path: " + args.output_path);
    }
    output << report.dump(2) << '\n';
    std::cout << "phase0 complete baseline_errors=" << baseline_errors
              << " mc_errors=" << mc_errors
              << " bar_errors=" << bar_errors
              << " bar_mismatches=" << bar_prediction_mismatches
              << " exploratory_speedup="
              << report["summary"]["exploratory_speedup"] << std::endl;
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "phase0 failed: " << ex.what() << std::endl;
    return 1;
  }
}
