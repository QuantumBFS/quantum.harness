#include "path_evaluator.hpp"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <stdexcept>

namespace audit {

namespace {

constexpr double negative_infinity =
    -std::numeric_limits<double>::infinity();

double finite_overlap(const Walker& walker, const TrialState& trial) {
    return signed_log_finite_value(walker.overlap_signed_log(trial));
}

void validate_order(const std::vector<std::size_t>& order,
                    std::size_t sites) {
    if (order.size() != sites) {
        throw std::invalid_argument("site order has wrong length");
    }
    auto sorted = order;
    std::sort(sorted.begin(), sorted.end());
    for (std::size_t site = 0; site < sites; ++site) {
        if (sorted.at(site) != site) {
            throw std::invalid_argument("site order is not a permutation");
        }
    }
}

void validate_fields(const std::vector<int>& fields, std::size_t expected) {
    if (fields.size() != expected) {
        throw std::invalid_argument("field sequence length mismatch");
    }
    for (int field : fields) {
        if (field != -1 && field != +1) {
            throw std::invalid_argument("field value must be -1 or +1");
        }
    }
}

void reject(PathSummary& summary, RejectionKind kind, std::size_t slice,
            std::size_t site = std::numeric_limits<std::size_t>::max()) {
    if (summary.alive) {
        summary.first_rejected_step = summary.completed_steps;
        summary.first_rejection_kind = kind;
        summary.first_rejection_slice = slice;
        summary.first_rejection_site = site;
    }
    summary.alive = false;
    summary.log_q_prop = negative_infinity;
    summary.log_w_ratio = negative_infinity;
}

void finish_step(PathSummary& summary, const StepTrace& trace,
                 bool keep_trace) {
    if (keep_trace) {
        summary.trace.push_back(trace);
    }
    ++summary.completed_steps;
    if (summary.alive && summary.log_w_ratio < summary.min_log_weight) {
        summary.min_log_weight = summary.log_w_ratio;
        summary.argmin_weight_step = summary.completed_steps;
    }
}

void apply_half_kinetic(EvaluationState& state, const TrialState& trial,
                        const HubbardModel& model, std::size_t slice,
                        StepKind kind, bool clip, bool keep_trace) {
    auto& summary = state.summary;
    StepTrace trace;
    trace.kind = kind;
    trace.slice = slice;
    trace.alive_before = summary.alive;
    const Walker before = state.walker;
    trace.overlap_before = finite_overlap(before, trial);
    state.walker.apply_half_kinetic(model);
    trace.overlap_after = finite_overlap(state.walker, trial);
    trace.overlap_ratio = state.walker.overlap_ratio(trial, before);
    trace.weight_factor = trace.overlap_ratio;
    if (summary.alive) {
        if (trace.overlap_ratio > 0.0) {
            summary.log_w_ratio += std::log(trace.overlap_ratio);
            summary.min_halfk_ratio =
                std::min(summary.min_halfk_ratio, trace.overlap_ratio);
        } else if (clip) {
            reject(summary,
                   kind == StepKind::PreHalfK
                       ? RejectionKind::PreHalfK
                       : RejectionKind::PostHalfK,
                   slice);
        } else {
            throw std::runtime_error(
                "unclipped real proposal encountered nonpositive half-K ratio");
        }
    }
    trace.alive_after = summary.alive;
    trace.cumulative_log_q = summary.log_q_prop;
    trace.cumulative_log_weight = summary.log_w_ratio;
    summary.min_abs_overlap =
        std::min(summary.min_abs_overlap, std::abs(trace.overlap_after));
    finish_step(summary, trace, keep_trace);
}

std::vector<int> fields_from_mask(std::size_t mask, std::size_t sites) {
    std::vector<int> result(sites);
    for (std::size_t site = 0; site < sites; ++site) {
        result.at(site) = ((mask >> site) & 1U) ? +1 : -1;
    }
    return result;
}

}  // namespace

PathEvaluator::PathEvaluator(HubbardModel model, TrialState trial,
                             std::vector<std::size_t> site_order,
                             ProposalKind proposal,
                             std::size_t stabilization_interval)
    : PathEvaluator(
          std::move(model), trial, trial,
          std::move(site_order), proposal, stabilization_interval
      ) {}

PathEvaluator::PathEvaluator(HubbardModel model, TrialState initial_state,
                             TrialState guide_trial,
                             std::vector<std::size_t> site_order,
                             ProposalKind proposal,
                             std::size_t stabilization_interval)
    : model_(std::move(model)),
      initial_state_(std::move(initial_state)),
      guide_trial_(std::move(guide_trial)),
      site_order_(std::move(site_order)),
      proposal_(proposal),
      stabilization_interval_(stabilization_interval) {
    validate_order(site_order_, model_.sites());
}

EvaluationState PathEvaluator::initial_state() const {
    EvaluationState state{Walker::from_trial(initial_state_), PathSummary{}};
    state.summary.initial_overlap_signed_log =
        state.walker.overlap_signed_log(guide_trial_);
    state.summary.initial_overlap = signed_log_finite_value(
        state.summary.initial_overlap_signed_log
    );
    state.summary.min_abs_overlap =
        std::abs(state.summary.initial_overlap);
    return state;
}

PathSummary PathEvaluator::finish(const EvaluationState& state) const {
    PathSummary result = state.summary;
    result.final_overlap_signed_log =
        state.walker.overlap_signed_log(guide_trial_);
    result.final_overlap =
        signed_log_finite_value(result.final_overlap_signed_log);
    return result;
}

PathSummary PathEvaluator::evaluate(const std::vector<int>& fields,
                                    std::size_t slices, bool clip) const {
    validate_fields(fields, slices * model_.sites());
    auto state = initial_state();
    for (std::size_t slice = 0; slice < slices; ++slice) {
        const auto first =
            fields.begin() +
            static_cast<std::ptrdiff_t>(slice * model_.sites());
        const std::vector<int> slice_fields(
            first, first + static_cast<std::ptrdiff_t>(model_.sites()));
        state = advance_slice(state, slice_fields, slice, clip, true);
    }
    return finish(state);
}

EvaluationState PathEvaluator::advance_slice(
    const EvaluationState& state, const std::vector<int>& slice_fields,
    std::size_t slice, bool clip, bool keep_trace) const {
    validate_fields(slice_fields, model_.sites());
    EvaluationState result =
        proposal_ == ProposalKind::SiteBySite
            ? advance_site_by_site(state, slice_fields, slice, clip,
                                   keep_trace)
            : advance_joint_slice(state, slice_fields, slice, clip,
                                  keep_trace);
    if (stabilization_interval_ != 0 &&
        ((slice + 1U) % stabilization_interval_) == 0U) {
        result.walker.stabilize();
    }
    return result;
}

std::vector<EvaluationState> PathEvaluator::advance_all_slice_fields(
    const EvaluationState& state, std::size_t slice, bool clip,
    bool keep_trace) const {
    const std::size_t configurations = std::size_t{1} << model_.sites();
    if (proposal_ == ProposalKind::JointSlice) {
        StepTrace base_trace;
        base_trace.kind = StepKind::JointSlice;
        base_trace.slice = slice;
        base_trace.alive_before = state.summary.alive;
        base_trace.overlap_before =
            finite_overlap(state.walker, guide_trial_);

        std::vector<Walker> candidates;
        std::vector<double> overlaps(configurations);
        std::vector<double> positive_ratios(configurations);
        candidates.reserve(configurations);
        double normalization = 0.0;
        for (std::size_t internal_mask = 0;
             internal_mask < configurations; ++internal_mask) {
            Walker candidate = state.walker;
            candidate.apply_half_kinetic(model_);
            const auto candidate_fields =
                fields_from_mask(internal_mask, model_.sites());
            for (std::size_t site = 0; site < model_.sites(); ++site) {
                candidate.apply_site_field(model_, site,
                                           candidate_fields.at(site));
            }
            candidate.apply_half_kinetic(model_);
            overlaps.at(internal_mask) =
                finite_overlap(candidate, guide_trial_);
            positive_ratios.at(internal_mask) = std::max(
                candidate.overlap_ratio(guide_trial_, state.walker), 0.0
            );
            normalization += positive_ratios.at(internal_mask);
            candidates.push_back(std::move(candidate));
        }

        std::vector<EvaluationState> result;
        result.reserve(configurations);
        for (std::size_t mask = 0; mask < configurations; ++mask) {
            std::size_t internal_mask = 0;
            for (std::size_t site = 0; site < model_.sites(); ++site) {
                const std::size_t bit = model_.sites() - 1U - site;
                if (((mask >> bit) & 1U) != 0U) {
                    internal_mask |= std::size_t{1} << site;
                }
            }
            EvaluationState child = state;
            StepTrace trace = base_trace;
            trace.q_selected =
                normalization > 0.0
                    ? positive_ratios.at(internal_mask) / normalization
                    : 0.0;
            trace.weight_factor =
                normalization / static_cast<double>(configurations);
            trace.overlap_after = overlaps.at(internal_mask);
            trace.overlap_ratio = candidates.at(internal_mask).overlap_ratio(
                guide_trial_, state.walker
            );
            child.walker = candidates.at(internal_mask);
            child.summary.log_common_factor +=
                std::log(model_.slice_constant());
            if (child.summary.alive) {
                if (normalization > 0.0 && trace.q_selected > 0.0) {
                    child.summary.log_q_prop += std::log(trace.q_selected);
                    child.summary.log_w_ratio +=
                        std::log(trace.weight_factor);
                    child.summary.min_selected_q = std::min(
                        child.summary.min_selected_q, trace.q_selected);
                } else if (clip) {
                    reject(child.summary, RejectionKind::Site, slice);
                } else {
                    throw std::runtime_error(
                        "unclipped real joint proposal encountered nonpositive ratio");
                }
            }
            trace.alive_after = child.summary.alive;
            trace.cumulative_log_q = child.summary.log_q_prop;
            trace.cumulative_log_weight = child.summary.log_w_ratio;
            child.summary.min_abs_overlap =
                std::min(child.summary.min_abs_overlap,
                         std::abs(trace.overlap_after));
            finish_step(child.summary, trace, keep_trace);
            if (stabilization_interval_ != 0 &&
                ((slice + 1U) % stabilization_interval_) == 0U) {
                child.walker.stabilize();
            }
            result.push_back(std::move(child));
        }
        return result;
    }

    EvaluationState root = state;
    root.summary.log_common_factor += std::log(model_.slice_constant());
    apply_half_kinetic(root, guide_trial_, model_, slice,
                       StepKind::PreHalfK, clip, keep_trace);
    std::vector<std::pair<std::size_t, EvaluationState>> leaves;
    leaves.reserve(configurations);

    const std::function<void(const EvaluationState&, std::size_t,
                             std::size_t)>
        branch = [&](const EvaluationState& node, std::size_t order_index,
                     std::size_t chronological_mask) {
            if (order_index == site_order_.size()) {
                EvaluationState leaf = node;
                apply_half_kinetic(leaf, guide_trial_, model_, slice,
                                   StepKind::PostHalfK, clip, keep_trace);
                if (stabilization_interval_ != 0 &&
                    ((slice + 1U) % stabilization_interval_) == 0U) {
                    leaf.walker.stabilize();
                }
                leaves.emplace_back(chronological_mask, std::move(leaf));
                return;
            }

            const std::size_t site = site_order_.at(order_index);
            const double overlap_before =
                finite_overlap(node.walker, guide_trial_);
            Walker plus = node.walker;
            Walker minus = node.walker;
            plus.apply_site_field(model_, site, +1);
            minus.apply_site_field(model_, site, -1);
            const double plus_overlap =
                finite_overlap(plus, guide_trial_);
            const double minus_overlap =
                finite_overlap(minus, guide_trial_);
            const double plus_ratio =
                plus.overlap_ratio(guide_trial_, node.walker);
            const double minus_ratio =
                minus.overlap_ratio(guide_trial_, node.walker);
            const double plus_positive = std::max(plus_ratio, 0.0);
            const double minus_positive = std::max(minus_ratio, 0.0);
            const double normalization =
                plus_positive + minus_positive;

            for (int field : {-1, +1}) {
                EvaluationState child = node;
                StepTrace trace;
                trace.kind = StepKind::Site;
                trace.slice = slice;
                trace.site = site;
                trace.selected_field = field;
                trace.alive_before = child.summary.alive;
                trace.overlap_before = overlap_before;
                trace.q_plus =
                    normalization > 0.0
                        ? plus_positive / normalization
                        : 0.0;
                trace.q_minus =
                    normalization > 0.0
                        ? minus_positive / normalization
                        : 0.0;
                trace.q_selected =
                    field == +1 ? trace.q_plus : trace.q_minus;
                trace.weight_factor = 0.5 * normalization;
                child.walker = field == +1 ? plus : minus;
                trace.overlap_after =
                    field == +1 ? plus_overlap : minus_overlap;
                trace.overlap_ratio =
                    field == +1 ? plus_ratio : minus_ratio;
                if (child.summary.alive) {
                    if (normalization > 0.0 &&
                        trace.q_selected > 0.0) {
                        child.summary.log_q_prop +=
                            std::log(trace.q_selected);
                        child.summary.log_w_ratio +=
                            std::log(trace.weight_factor);
                        child.summary.min_selected_q = std::min(
                            child.summary.min_selected_q,
                            trace.q_selected);
                    } else if (clip) {
                        reject(child.summary, RejectionKind::Site, slice,
                               site);
                    } else {
                        throw std::runtime_error(
                            "unclipped real proposal encountered nonpositive site ratio");
                    }
                }
                trace.alive_after = child.summary.alive;
                trace.cumulative_log_q = child.summary.log_q_prop;
                trace.cumulative_log_weight =
                    child.summary.log_w_ratio;
                child.summary.min_abs_overlap =
                    std::min(child.summary.min_abs_overlap,
                             std::abs(trace.overlap_after));
                finish_step(child.summary, trace, keep_trace);
                std::size_t child_mask = chronological_mask;
                if (field == +1) {
                    child_mask |= std::size_t{1}
                                  << (model_.sites() - 1U - site);
                }
                branch(child, order_index + 1U, child_mask);
            }
        };
    branch(root, 0, 0);
    std::sort(leaves.begin(), leaves.end(),
              [](const auto& left, const auto& right) {
                  return left.first < right.first;
              });
    std::vector<EvaluationState> result;
    result.reserve(configurations);
    for (auto& leaf : leaves) {
        result.push_back(std::move(leaf.second));
    }
    return result;
}

EvaluationState PathEvaluator::advance_site_by_site(
    const EvaluationState& input, const std::vector<int>& slice_fields,
    std::size_t slice, bool clip, bool keep_trace) const {
    EvaluationState state = input;
    auto& summary = state.summary;
    summary.log_common_factor += std::log(model_.slice_constant());
    apply_half_kinetic(state, guide_trial_, model_, slice,
                       StepKind::PreHalfK, clip, keep_trace);

    for (const std::size_t site : site_order_) {
        StepTrace trace;
        trace.kind = StepKind::Site;
        trace.slice = slice;
        trace.site = site;
        trace.selected_field = slice_fields.at(site);
        trace.alive_before = summary.alive;
        trace.overlap_before =
            finite_overlap(state.walker, guide_trial_);

        Walker plus = state.walker;
        Walker minus = state.walker;
        plus.apply_site_field(model_, site, +1);
        minus.apply_site_field(model_, site, -1);
        const double plus_overlap = finite_overlap(plus, guide_trial_);
        const double minus_overlap = finite_overlap(minus, guide_trial_);
        const double plus_ratio =
            plus.overlap_ratio(guide_trial_, state.walker);
        const double minus_ratio =
            minus.overlap_ratio(guide_trial_, state.walker);
        const double plus_positive = std::max(plus_ratio, 0.0);
        const double minus_positive = std::max(minus_ratio, 0.0);
        const double normalization = plus_positive + minus_positive;
        trace.q_plus =
            normalization > 0.0 ? plus_positive / normalization : 0.0;
        trace.q_minus =
            normalization > 0.0 ? minus_positive / normalization : 0.0;
        trace.q_selected =
            trace.selected_field == +1 ? trace.q_plus : trace.q_minus;
        trace.weight_factor = 0.5 * normalization;

        state.walker = trace.selected_field == +1 ? plus : minus;
        trace.overlap_after =
            trace.selected_field == +1 ? plus_overlap : minus_overlap;
        trace.overlap_ratio = trace.overlap_after / trace.overlap_before;

        if (summary.alive) {
            if (normalization > 0.0 && trace.q_selected > 0.0) {
                summary.log_q_prop += std::log(trace.q_selected);
                summary.log_w_ratio += std::log(trace.weight_factor);
                summary.min_selected_q =
                    std::min(summary.min_selected_q, trace.q_selected);
            } else if (clip) {
                reject(summary, RejectionKind::Site, slice, site);
            } else {
                throw std::runtime_error(
                    "unclipped real proposal encountered nonpositive site ratio");
            }
        }
        trace.alive_after = summary.alive;
        trace.cumulative_log_q = summary.log_q_prop;
        trace.cumulative_log_weight = summary.log_w_ratio;
        summary.min_abs_overlap =
            std::min(summary.min_abs_overlap,
                     std::abs(trace.overlap_after));
        finish_step(summary, trace, keep_trace);
    }
    apply_half_kinetic(state, guide_trial_, model_, slice,
                       StepKind::PostHalfK, clip, keep_trace);
    return state;
}

EvaluationState PathEvaluator::advance_joint_slice(
    const EvaluationState& input, const std::vector<int>& slice_fields,
    std::size_t slice, bool clip, bool keep_trace) const {
    EvaluationState state = input;
    auto& summary = state.summary;
    StepTrace trace;
    trace.kind = StepKind::JointSlice;
    trace.slice = slice;
    trace.alive_before = summary.alive;
    trace.overlap_before = finite_overlap(state.walker, guide_trial_);
    const std::size_t configurations = std::size_t{1} << model_.sites();

    std::vector<Walker> candidates;
    std::vector<double> overlaps(configurations);
    std::vector<double> positive_ratios(configurations);
    candidates.reserve(configurations);
    double normalization = 0.0;
    for (std::size_t mask = 0; mask < configurations; ++mask) {
        Walker candidate = state.walker;
        candidate.apply_half_kinetic(model_);
        const auto candidate_fields =
            fields_from_mask(mask, model_.sites());
        for (std::size_t site = 0; site < model_.sites(); ++site) {
            candidate.apply_site_field(model_, site,
                                       candidate_fields.at(site));
        }
        candidate.apply_half_kinetic(model_);
        overlaps.at(mask) = finite_overlap(candidate, guide_trial_);
        positive_ratios.at(mask) = std::max(
            candidate.overlap_ratio(guide_trial_, state.walker), 0.0
        );
        normalization += positive_ratios.at(mask);
        candidates.push_back(std::move(candidate));
    }

    std::size_t selected_mask = 0;
    for (std::size_t site = 0; site < model_.sites(); ++site) {
        if (slice_fields.at(site) == +1) {
            selected_mask |= std::size_t{1} << site;
        }
    }
    trace.q_selected =
        normalization > 0.0
            ? positive_ratios.at(selected_mask) / normalization
            : 0.0;
    trace.weight_factor =
        normalization / static_cast<double>(configurations);
    trace.overlap_after = overlaps.at(selected_mask);
    trace.overlap_ratio = candidates.at(selected_mask).overlap_ratio(
        guide_trial_, state.walker
    );
    state.walker = std::move(candidates.at(selected_mask));
    summary.log_common_factor += std::log(model_.slice_constant());

    if (summary.alive) {
        if (normalization > 0.0 && trace.q_selected > 0.0) {
            summary.log_q_prop += std::log(trace.q_selected);
            summary.log_w_ratio += std::log(trace.weight_factor);
            summary.min_selected_q =
                std::min(summary.min_selected_q, trace.q_selected);
        } else if (clip) {
            reject(summary, RejectionKind::Site, slice);
        } else {
            throw std::runtime_error(
                "unclipped real joint proposal encountered nonpositive ratio");
        }
    }
    trace.alive_after = summary.alive;
    trace.cumulative_log_q = summary.log_q_prop;
    trace.cumulative_log_weight = summary.log_w_ratio;
    summary.min_abs_overlap =
        std::min(summary.min_abs_overlap, std::abs(trace.overlap_after));
    finish_step(summary, trace, keep_trace);
    return state;
}

}  // namespace audit
