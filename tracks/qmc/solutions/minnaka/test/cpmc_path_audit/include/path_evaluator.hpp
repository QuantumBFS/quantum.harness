#pragma once

#include "walker.hpp"

#include <cstddef>
#include <limits>
#include <vector>

namespace audit {

enum class ProposalKind { SiteBySite, JointSlice };
enum class StepKind { PreHalfK, Site, PostHalfK, JointSlice };
enum class RejectionKind { None, PreHalfK, Site, PostHalfK };

struct StepTrace {
    StepKind kind = StepKind::Site;
    std::size_t slice = 0;
    std::size_t site = std::numeric_limits<std::size_t>::max();
    int selected_field = 0;
    bool alive_before = true;
    bool alive_after = true;
    double overlap_before = 0.0;
    double overlap_after = 0.0;
    double overlap_ratio = 0.0;
    double q_plus = 0.0;
    double q_minus = 0.0;
    double q_selected = 1.0;
    double weight_factor = 1.0;
    double cumulative_log_q = 0.0;
    double cumulative_log_weight = 0.0;
};

struct PathSummary {
    double initial_overlap = 0.0;
    double final_overlap = 0.0;
    SignedLog initial_overlap_signed_log;
    SignedLog final_overlap_signed_log;
    double log_q_prop = 0.0;
    double log_w_ratio = 0.0;
    double log_common_factor = 0.0;
    double min_log_weight = 0.0;
    std::size_t argmin_weight_step = 0;
    std::size_t first_rejected_step =
        std::numeric_limits<std::size_t>::max();
    RejectionKind first_rejection_kind = RejectionKind::None;
    std::size_t first_rejection_slice =
        std::numeric_limits<std::size_t>::max();
    std::size_t first_rejection_site =
        std::numeric_limits<std::size_t>::max();
    std::size_t completed_steps = 0;
    double min_abs_overlap = std::numeric_limits<double>::infinity();
    double min_selected_q = std::numeric_limits<double>::infinity();
    double min_halfk_ratio = std::numeric_limits<double>::infinity();
    bool alive = true;
    std::vector<StepTrace> trace;
};

struct EvaluationState {
    Walker walker;
    PathSummary summary;
};

class PathEvaluator {
public:
    PathEvaluator(HubbardModel model, TrialState trial,
                  std::vector<std::size_t> site_order,
                  ProposalKind proposal,
                  std::size_t stabilization_interval = 0);
    PathEvaluator(HubbardModel model, TrialState initial_state,
                  TrialState guide_trial,
                  std::vector<std::size_t> site_order,
                  ProposalKind proposal,
                  std::size_t stabilization_interval = 0);

    const HubbardModel& model() const noexcept { return model_; }
    const TrialState& trial() const noexcept { return guide_trial_; }
    const TrialState& initial_trial() const noexcept {
        return initial_state_;
    }
    const TrialState& guide_trial() const noexcept {
        return guide_trial_;
    }
    ProposalKind proposal() const noexcept { return proposal_; }
    const std::vector<std::size_t>& site_order() const noexcept {
        return site_order_;
    }

    PathSummary evaluate(const std::vector<int>& fields,
                         std::size_t slices, bool clip) const;
    EvaluationState initial_state() const;
    EvaluationState advance_slice(const EvaluationState& state,
                                  const std::vector<int>& slice_fields,
                                  std::size_t slice, bool clip,
                                  bool keep_trace) const;
    std::vector<EvaluationState> advance_all_slice_fields(
        const EvaluationState& state, std::size_t slice, bool clip,
        bool keep_trace) const;
    PathSummary finish(const EvaluationState& state) const;

private:
    EvaluationState advance_site_by_site(
        const EvaluationState& state,
        const std::vector<int>& slice_fields, std::size_t slice, bool clip,
        bool keep_trace) const;
    EvaluationState advance_joint_slice(
        const EvaluationState& state,
        const std::vector<int>& slice_fields, std::size_t slice, bool clip,
        bool keep_trace) const;

    HubbardModel model_;
    TrialState initial_state_;
    TrialState guide_trial_;
    std::vector<std::size_t> site_order_;
    ProposalKind proposal_;
    std::size_t stabilization_interval_;
};

}  // namespace audit
