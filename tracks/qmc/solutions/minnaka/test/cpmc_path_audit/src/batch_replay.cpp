#include "batch_replay.hpp"

#include "path_format.hpp"
#include "replay.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <tuple>
#include <utility>

namespace audit {

namespace {

const char* step_name(StepKind kind) {
    switch (kind) {
        case StepKind::PreHalfK:
            return "pre_half_k";
        case StepKind::Site:
            return "site";
        case StepKind::PostHalfK:
            return "post_half_k";
        case StepKind::JointSlice:
            return "joint_slice";
    }
    throw std::logic_error("unknown step kind");
}

std::vector<std::string> split_csv_line(const std::string& line) {
    std::vector<std::string> fields;
    std::stringstream stream(line);
    std::string field;
    while (std::getline(stream, field, ',')) {
        fields.push_back(field);
    }
    if (!line.empty() && line.back() == ',') {
        fields.emplace_back();
    }
    return fields;
}

std::uint64_t site_mask_from_fields(
    const std::vector<int>& fields) {
    if (fields.size() > 64) {
        throw std::invalid_argument("site mask exceeds uint64");
    }
    std::uint64_t mask = 0;
    for (std::size_t site = 0; site < fields.size(); ++site) {
        if (fields.at(site) == +1) {
            mask |= std::uint64_t{1} << site;
        }
    }
    return mask;
}

std::uint64_t chronological_to_site_mask(
    std::uint64_t chronological_mask, std::size_t sites) {
    std::uint64_t result = 0;
    for (std::size_t site = 0; site < sites; ++site) {
        const std::size_t chronological_bit = sites - 1U - site;
        if (((chronological_mask >> chronological_bit) & 1U) != 0U) {
            result |= std::uint64_t{1} << site;
        }
    }
    return result;
}

int hamming_distance(std::uint64_t left, std::uint64_t right) {
    std::uint64_t different = left ^ right;
    int result = 0;
    while (different != 0) {
        different &= different - 1U;
        ++result;
    }
    return result;
}

double minimum_sigma(const SubspaceDiagnostic& diagnostic) {
    return std::min(diagnostic.up.sigma_min,
                    diagnostic.down.sigma_min);
}

std::pair<std::uint64_t, SubspaceDiagnostic> greedy_prediction(
    const PathEvaluator& evaluator, const EvaluationState& state) {
    Walker walker = state.walker;
    walker.apply_half_kinetic(evaluator.model());
    std::uint64_t mask = 0;
    for (const std::size_t site : evaluator.site_order()) {
        const SiteRatioDiagnostic ratios = diagnose_site_ratios(
            evaluator.model(), evaluator.trial(), walker, site);
        const double plus_score =
            ratios.predicted_plus_ratio > 0.0
                ? ratios.predicted_plus_ratio
                : std::numeric_limits<double>::infinity();
        const double minus_score =
            ratios.predicted_minus_ratio > 0.0
                ? ratios.predicted_minus_ratio
                : std::numeric_limits<double>::infinity();
        int field = plus_score < minus_score ? +1 : -1;
        if (!std::isfinite(plus_score) &&
            !std::isfinite(minus_score)) {
            field = ratios.direct_plus_ratio <
                            ratios.direct_minus_ratio
                        ? +1
                        : -1;
        }
        if (field == +1) {
            mask |= std::uint64_t{1} << site;
        }
        walker.apply_site_field(evaluator.model(), site, field);
    }
    walker.apply_half_kinetic(evaluator.model());
    return {mask, diagnose_subspace(evaluator.trial(), walker)};
}

MaskPrediction predict_next_slice(
    const PathEvaluator& evaluator, const EvaluationState& state,
    const std::vector<int>& realized_fields, std::size_t slice,
    bool clip) {
    MaskPrediction result;
    result.slice = slice;
    result.realized_mask = site_mask_from_fields(realized_fields);
    const auto [greedy_mask, greedy_diagnostic] =
        greedy_prediction(evaluator, state);
    result.greedy_mask = greedy_mask;
    result.greedy_sigma_min = minimum_sigma(greedy_diagnostic);
    result.greedy_log_normalized_overlap =
        greedy_diagnostic.log_abs_normalized_overlap;
    result.hamming_greedy =
        hamming_distance(result.realized_mask, result.greedy_mask);

    if (!exhaustive_mask_prediction_available(
            evaluator.model().sites())) {
        const auto realized = evaluator.advance_slice(
            state, realized_fields, slice, clip, false);
        const auto diagnostic =
            diagnose_subspace(evaluator.trial(), realized.walker);
        result.realized_sigma_min = minimum_sigma(diagnostic);
        result.realized_log_normalized_overlap =
            diagnostic.log_abs_normalized_overlap;
        return result;
    }

    result.exhaustive_available = true;
    const auto candidates = evaluator.advance_all_slice_fields(
        state, slice, clip, false);
    result.candidate_count = candidates.size();
    struct Candidate {
        std::size_t chronological_mask = 0;
        std::uint64_t site_mask = 0;
        SubspaceDiagnostic diagnostic;
    };
    std::vector<Candidate> ranked;
    ranked.reserve(candidates.size());
    for (std::size_t mask = 0; mask < candidates.size(); ++mask) {
        ranked.push_back(
            {mask, chronological_to_site_mask(mask, 4),
             diagnose_subspace(evaluator.trial(),
                               candidates.at(mask).walker)});
    }
    std::sort(
        ranked.begin(), ranked.end(),
        [](const Candidate& left, const Candidate& right) {
            return std::tuple<double, double, std::uint64_t>{
                       minimum_sigma(left.diagnostic),
                       left.diagnostic.log_abs_normalized_overlap,
                       left.site_mask} <
                   std::tuple<double, double, std::uint64_t>{
                       minimum_sigma(right.diagnostic),
                       right.diagnostic.log_abs_normalized_overlap,
                       right.site_mask};
        });
    const auto& best = ranked.front();
    result.best_mask = best.site_mask;
    result.best_sigma_min = minimum_sigma(best.diagnostic);
    result.best_log_normalized_overlap =
        best.diagnostic.log_abs_normalized_overlap;
    result.hamming_best =
        hamming_distance(result.realized_mask, result.best_mask);
    for (std::size_t rank = 0; rank < ranked.size(); ++rank) {
        if (ranked.at(rank).site_mask == result.realized_mask) {
            result.realized_rank = rank + 1U;
            result.realized_sigma_min =
                minimum_sigma(ranked.at(rank).diagnostic);
            result.realized_log_normalized_overlap =
                ranked.at(rank).diagnostic.log_abs_normalized_overlap;
            break;
        }
    }
    if (result.realized_rank == 0) {
        throw std::runtime_error(
            "realized mask is absent from exhaustive candidates");
    }
    return result;
}

void require_overlap_consistency(double actual, double expected) {
    const double scale =
        std::max({1.0, std::abs(actual), std::abs(expected)});
    if (std::abs(actual - expected) > 1.0e-9 * scale) {
        throw std::runtime_error(
            "diagnostic walker diverged from PathEvaluator trace");
    }
}

DetailedStep make_detailed_step(
    std::size_t event_index, const StepTrace& trace,
    double previous_log_q, double previous_log_weight,
    const SubspaceDiagnostic& subspace,
    const SiteRatioDiagnostic& ratios) {
    DetailedStep result;
    result.event_index = event_index;
    result.trace = trace;
    result.delta_log_q =
        trace.cumulative_log_q - previous_log_q;
    result.delta_log_weight =
        trace.cumulative_log_weight - previous_log_weight;
    result.subspace = subspace;
    result.site_ratios = ratios;
    return result;
}

void write_step_header(std::ostream& stream) {
    stream
        << "path_id,role,case_id,config_id,score,log_d_over_mean,"
           "weight_bin,event_index,kind,slice,site,field,q_selected,"
           "c_factor,delta_log_q,delta_log_w,cumulative_log_q,"
           "cumulative_log_w,overlap_before,overlap_after,overlap_ratio,"
           "sigma_min_up,sigma_max_up,sigma_min_down,sigma_max_down,"
           "angle_max_up,angle_max_down,condition_g_up,condition_g_down,"
           "log_det_s_up,log_det_s_down,log_normalized_overlap,"
           "log_orbital_scale_up,log_orbital_scale_down,"
           "log_orbital_scale,g_up,g_down,predicted_r_plus,"
           "predicted_r_minus,direct_r_plus,direct_r_minus,"
           "ratio_residual,predicted_low_field\n";
}

void write_manifest_prefix(std::ostream& stream,
                           const BatchManifestRow& row) {
    stream << row.path_id << ',' << row.role << ',' << row.case_id << ',';
    if (row.config_id.has_value()) {
        stream << *row.config_id;
    }
    stream << ',' << row.score << ',' << row.log_d_over_mean << ','
           << row.weight_bin;
}

void write_step(std::ostream& stream, const BatchManifestRow& row,
                const DetailedStep& step) {
    write_manifest_prefix(stream, row);
    const StepTrace& trace = step.trace;
    stream << ',' << step.event_index << ',' << step_name(trace.kind)
           << ',' << trace.slice << ',';
    if (trace.site == std::numeric_limits<std::size_t>::max()) {
        stream << -1;
    } else {
        stream << trace.site;
    }
    const auto& up = step.subspace.up;
    const auto& down = step.subspace.down;
    const auto& ratios = step.site_ratios;
    stream
        << ',' << trace.selected_field << ',' << trace.q_selected << ','
        << trace.weight_factor << ',' << step.delta_log_q << ','
        << step.delta_log_weight << ',' << trace.cumulative_log_q << ','
        << trace.cumulative_log_weight << ',' << trace.overlap_before
        << ',' << trace.overlap_after << ',' << trace.overlap_ratio << ','
        << up.sigma_min << ',' << up.sigma_max << ',' << down.sigma_min
        << ',' << down.sigma_max << ',' << up.principal_angle_max << ','
        << down.principal_angle_max << ',' << up.condition_g << ','
        << down.condition_g << ',' << up.log_abs_det_s << ','
        << down.log_abs_det_s << ','
        << step.subspace.log_abs_normalized_overlap << ','
        << up.log_abs_orbital_scale << ','
        << down.log_abs_orbital_scale << ','
        << step.subspace.log_abs_orbital_scale << ',' << ratios.g_up << ','
        << ratios.g_down << ',' << ratios.predicted_plus_ratio << ','
        << ratios.predicted_minus_ratio << ',' << ratios.direct_plus_ratio
        << ',' << ratios.direct_minus_ratio << ','
        << ratios.max_abs_residual << ','
        << ratios.predicted_low_overlap_field << '\n';
}

void write_mask_header(std::ostream& stream) {
    stream
        << "path_id,role,case_id,config_id,score,log_d_over_mean,"
           "weight_bin,slice,exhaustive_available,realized_mask,best_mask,"
           "greedy_mask,realized_rank,candidate_count,hamming_best,"
           "hamming_greedy,best_sigma_min,realized_sigma_min,"
           "greedy_sigma_min,best_log_normalized_overlap,"
           "realized_log_normalized_overlap,"
           "greedy_log_normalized_overlap\n";
}

void write_mask(std::ostream& stream, const BatchManifestRow& row,
                const MaskPrediction& prediction) {
    write_manifest_prefix(stream, row);
    stream << ',' << prediction.slice << ','
           << static_cast<int>(prediction.exhaustive_available) << ','
           << prediction.realized_mask << ',';
    if (prediction.exhaustive_available) {
        stream << prediction.best_mask;
    }
    stream << ',' << prediction.greedy_mask << ',';
    if (prediction.exhaustive_available) {
        stream << prediction.realized_rank;
    }
    stream << ',' << prediction.candidate_count << ',';
    if (prediction.exhaustive_available) {
        stream << prediction.hamming_best;
    }
    stream << ',' << prediction.hamming_greedy << ',';
    if (prediction.exhaustive_available) {
        stream << prediction.best_sigma_min;
    }
    stream << ',' << prediction.realized_sigma_min << ','
           << prediction.greedy_sigma_min << ',';
    if (prediction.exhaustive_available) {
        stream << prediction.best_log_normalized_overlap;
    }
    stream << ',' << prediction.realized_log_normalized_overlap << ','
           << prediction.greedy_log_normalized_overlap << '\n';
}

}  // namespace

bool exhaustive_mask_prediction_available(std::size_t sites) noexcept {
    return sites == 4;
}

DetailedPathDiagnostic diagnose_path(
    const PathEvaluator& evaluator, const std::vector<int>& fields,
    std::size_t slices, bool clip) {
    if (evaluator.proposal() != ProposalKind::SiteBySite) {
        throw std::invalid_argument(
            "detailed path diagnosis requires site proposal");
    }
    if (fields.size() != slices * evaluator.model().sites()) {
        throw std::invalid_argument(
            "field count does not match slices times sites");
    }
    DetailedPathDiagnostic result;
    EvaluationState state = evaluator.initial_state();
    for (std::size_t slice = 0; slice < slices; ++slice) {
        const auto first =
            fields.begin() +
            static_cast<std::ptrdiff_t>(
                slice * evaluator.model().sites());
        const std::vector<int> slice_fields(
            first,
            first + static_cast<std::ptrdiff_t>(
                        evaluator.model().sites()));
        result.mask_predictions.push_back(predict_next_slice(
            evaluator, state, slice_fields, slice, clip));

        const std::size_t trace_begin = state.summary.trace.size();
        const EvaluationState next = evaluator.advance_slice(
            state, slice_fields, slice, clip, true);
        const std::size_t expected_events =
            evaluator.model().sites() + 2U;
        if (next.summary.trace.size() !=
            trace_begin + expected_events) {
            throw std::runtime_error(
                "unexpected site-proposal event count");
        }

        Walker diagnostic_walker = state.walker;
        double previous_log_q = state.summary.log_q_prop;
        double previous_log_weight = state.summary.log_w_ratio;
        std::size_t trace_index = trace_begin;
        const auto append = [&](const SiteRatioDiagnostic& ratios) {
            const StepTrace& trace =
                next.summary.trace.at(trace_index);
            const double overlap =
                diagnostic_walker.overlap(evaluator.trial());
            require_overlap_consistency(overlap, trace.overlap_after);
            const SubspaceDiagnostic subspace =
                diagnose_subspace(evaluator.trial(),
                                  diagnostic_walker);
            result.steps.push_back(make_detailed_step(
                result.steps.size(), trace, previous_log_q,
                previous_log_weight, subspace, ratios));
            previous_log_q = trace.cumulative_log_q;
            previous_log_weight = trace.cumulative_log_weight;
            ++trace_index;
        };

        diagnostic_walker.apply_half_kinetic(evaluator.model());
        append(SiteRatioDiagnostic{});
        for (const std::size_t site : evaluator.site_order()) {
            const SiteRatioDiagnostic ratios = diagnose_site_ratios(
                evaluator.model(), evaluator.trial(),
                diagnostic_walker, site);
            diagnostic_walker.apply_site_field(
                evaluator.model(), site, slice_fields.at(site));
            append(ratios);
        }
        diagnostic_walker.apply_half_kinetic(evaluator.model());
        append(SiteRatioDiagnostic{});
        require_overlap_consistency(
            diagnostic_walker.overlap(evaluator.trial()),
            next.walker.overlap(evaluator.trial()));
        state = next;
    }
    result.summary = evaluator.finish(state);
    return result;
}

std::vector<BatchManifestRow> read_batch_manifest(
    const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot open batch manifest: " + path);
    }
    std::string line;
    if (!std::getline(stream, line)) {
        throw std::runtime_error("batch manifest is empty");
    }
    const std::string expected_header =
        "path_id,role,case_id,config_id,fields_file,score,"
        "log_d_over_mean,weight_bin";
    if (line != expected_header) {
        throw std::runtime_error("unexpected batch manifest header");
    }
    std::vector<BatchManifestRow> rows;
    std::set<std::string> path_ids;
    while (std::getline(stream, line)) {
        if (line.empty()) {
            continue;
        }
        const auto fields = split_csv_line(line);
        if (fields.size() != 8) {
            throw std::runtime_error(
                "batch manifest row must contain eight fields");
        }
        BatchManifestRow row;
        row.path_id = fields.at(0);
        row.role = fields.at(1);
        row.case_id = std::stoull(fields.at(2));
        if (!fields.at(3).empty()) {
            row.config_id = std::stoull(fields.at(3));
        }
        row.fields_file = fields.at(4);
        row.score = std::stod(fields.at(5));
        row.log_d_over_mean = std::stod(fields.at(6));
        row.weight_bin = fields.at(7);
        if (row.path_id.empty() || row.role.empty() ||
            row.weight_bin.empty()) {
            throw std::runtime_error(
                "batch manifest contains an empty required field");
        }
        if (row.config_id.has_value() == !row.fields_file.empty()) {
            throw std::runtime_error(
                "manifest row must set exactly one field source");
        }
        if (!path_ids.insert(row.path_id).second) {
            throw std::runtime_error(
                "duplicate path_id in batch manifest");
        }
        rows.push_back(std::move(row));
    }
    return rows;
}

void run_batch_replay(
    const PathEvaluator& evaluator, std::size_t slices,
    const std::vector<BatchManifestRow>& rows,
    const std::string& steps_output, const std::string& masks_output,
    std::size_t progress_updates) {
    if (rows.empty()) {
        throw std::invalid_argument("batch manifest contains no paths");
    }
    if (progress_updates == 0) {
        throw std::invalid_argument("progress updates must be positive");
    }
    std::ofstream steps(steps_output);
    std::ofstream masks(masks_output);
    if (!steps || !masks) {
        throw std::runtime_error("cannot open batch replay output");
    }
    steps << std::setprecision(17);
    masks << std::setprecision(17);
    write_step_header(steps);
    write_mask_header(masks);
    const std::size_t interval =
        std::max<std::size_t>(1, rows.size() / progress_updates);
    for (std::size_t index = 0; index < rows.size(); ++index) {
        const auto& row = rows.at(index);
        const std::vector<int> fields =
            row.config_id.has_value()
                ? decode_fields(
                      *row.config_id,
                      slices * evaluator.model().sites())
                : read_text_fields(row.fields_file);
        if (fields.size() != slices * evaluator.model().sites()) {
            throw std::runtime_error(
                "manifest field count does not match model");
        }
        const auto diagnostic =
            diagnose_path(evaluator, fields, slices, true);
        for (const auto& step : diagnostic.steps) {
            write_step(steps, row, step);
        }
        for (const auto& prediction :
             diagnostic.mask_predictions) {
            write_mask(masks, row, prediction);
        }
        if ((index + 1U) % interval == 0U ||
            index + 1U == rows.size()) {
            std::cout << "batch replay " << index + 1U << '/'
                      << rows.size() << " paths\n"
                      << std::flush;
        }
    }
    steps.flush();
    masks.flush();
    if (!steps || !masks) {
        throw std::runtime_error("failed to write batch replay output");
    }
}

}  // namespace audit
