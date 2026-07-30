#pragma once

#include "path_diagnostics.hpp"
#include "path_evaluator.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace audit {

struct DetailedStep {
    std::size_t event_index = 0;
    StepTrace trace;
    double delta_log_q = 0.0;
    double delta_log_weight = 0.0;
    SubspaceDiagnostic subspace;
    SiteRatioDiagnostic site_ratios;
};

struct MaskPrediction {
    std::size_t slice = 0;
    bool exhaustive_available = false;
    std::uint64_t realized_mask = 0;
    std::uint64_t best_mask = 0;
    std::uint64_t greedy_mask = 0;
    std::size_t realized_rank = 0;
    std::size_t candidate_count = 0;
    int hamming_best = -1;
    int hamming_greedy = -1;
    double best_sigma_min = 0.0;
    double realized_sigma_min = 0.0;
    double greedy_sigma_min = 0.0;
    double best_log_normalized_overlap = 0.0;
    double realized_log_normalized_overlap = 0.0;
    double greedy_log_normalized_overlap = 0.0;
};

struct DetailedPathDiagnostic {
    PathSummary summary;
    std::vector<DetailedStep> steps;
    std::vector<MaskPrediction> mask_predictions;
};

struct BatchManifestRow {
    std::string path_id;
    std::string role;
    std::uint64_t case_id = 0;
    std::optional<std::uint64_t> config_id;
    std::string fields_file;
    double score = 0.0;
    double log_d_over_mean = 0.0;
    std::string weight_bin;
};

bool exhaustive_mask_prediction_available(std::size_t sites) noexcept;

DetailedPathDiagnostic diagnose_path(
    const PathEvaluator& evaluator, const std::vector<int>& fields,
    std::size_t slices, bool clip);

std::vector<BatchManifestRow> read_batch_manifest(
    const std::string& path);

void run_batch_replay(
    const PathEvaluator& evaluator, std::size_t slices,
    const std::vector<BatchManifestRow>& rows,
    const std::string& steps_output, const std::string& masks_output,
    std::size_t progress_updates);

}  // namespace audit
