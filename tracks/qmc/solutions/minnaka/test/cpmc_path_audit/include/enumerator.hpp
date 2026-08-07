#pragma once

#include "path_evaluator.hpp"
#include "path_format.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace audit {

struct EnumerationOptions {
    std::size_t slices = 0;
    TrialCode trial_code = TrialCode::RhfX;
    ProposalCode proposal_code = ProposalCode::SiteBySite;
    SiteOrderCode site_order_code = SiteOrderCode::RowMajor;
    std::string output_path;
    std::size_t progress_updates = 16;
};

struct EnumerationResult {
    std::uint64_t records = 0;
    std::uint64_t alive_records = 0;
    std::uint64_t negative_records = 0;
    double signed_sum_d = 0.0;
    double absolute_sum_d = 0.0;
    double alive_absolute_sum_d = 0.0;
    double max_alive_identity_residual = 0.0;
    double elapsed_seconds = 0.0;
    double paths_per_second = 0.0;
};

struct LinearBottleneck {
    double depth = 0.0;
    std::size_t slice = 0;
};

LinearBottleneck linear_bottleneck(
    const std::vector<double>& slice_log_weights);
EnumerationResult enumerate_paths(const PathEvaluator& evaluator,
                                  const EnumerationOptions& options);

}  // namespace audit
