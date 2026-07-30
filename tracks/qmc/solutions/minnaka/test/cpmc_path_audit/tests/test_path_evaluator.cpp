#include "path_evaluator.hpp"
#include "test_common.hpp"

#include <cstdint>
#include <cmath>
#include <vector>

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto rhf = audit::TrialState::rhf_x(model);
        const auto guide = audit::TrialState::solve_uhf(model, 8.0);
        const audit::PathEvaluator separated(
            model, rhf, guide, model.row_major_order(),
            audit::ProposalKind::SiteBySite
        );
        const auto separated_initial = separated.initial_state();
        require_true(
            audit::max_abs_difference(
                separated_initial.walker.up(), rhf.up_orbitals()
            ) < 1e-14,
            "initial walker uses the right-boundary determinant"
        );
        require_near(
            separated_initial.summary.initial_overlap,
            guide.overlap(rhf.up_orbitals(), rhf.down_orbitals()),
            1e-12,
            "importance overlap uses the separate guide determinant"
        );
        const audit::PathEvaluator evaluator(
            model, rhf, model.row_major_order(),
            audit::ProposalKind::SiteBySite);

        const std::vector<int> fields = {+1, -1, +1, -1};
        const auto result = evaluator.evaluate(fields, 1, true);
        require_true(result.trace.size() == 6,
                     "site proposal records two half-K and four site steps");
        require_true(result.trace.front().kind == audit::StepKind::PreHalfK,
                     "first split-operator step is marked pre-half-K");
        require_true(result.trace.back().kind == audit::StepKind::PostHalfK,
                     "last split-operator step is marked post-half-K");
        require_true(
            result.first_rejection_kind == audit::RejectionKind::None,
            "alive path has no rejection kind"
        );
        require_true(
            result.first_rejection_slice ==
                std::numeric_limits<std::size_t>::max(),
            "alive path has no rejection slice"
        );
        require_true(result.min_selected_q > 0.0,
                     "alive path records its minimum selected proposal");
        require_true(result.min_halfk_ratio > 0.0,
                     "alive path records its minimum half-K ratio");
        require_near(result.initial_overlap, 1.0, 1e-12,
                     "trial starts with unit overlap");
        require_true(std::isfinite(result.final_overlap),
                     "final overlap is finite");

        auto state = evaluator.initial_state();
        state = evaluator.advance_slice(state, fields, 0, true, false);
        const auto incremental = evaluator.finish(state);
        require_true(incremental.trace.empty(),
                     "trace-free incremental propagation");
        require_near(incremental.final_overlap, result.final_overlap, 1e-12,
                     "incremental and complete final overlap");
        require_near(incremental.log_q_prop, result.log_q_prop, 1e-12,
                     "incremental and complete proposal probability");
        require_near(incremental.log_w_ratio, result.log_w_ratio, 1e-12,
                     "incremental and complete walker weight");

        audit::Walker stabilized_walker = audit::Walker::from_trial(rhf);
        stabilized_walker.apply_half_kinetic(model);
        for (std::size_t site = 0; site < model.sites(); ++site) {
            stabilized_walker.apply_site_field(model, site,
                                               fields.at(site));
        }
        const double overlap_before_stabilization =
            stabilized_walker.overlap(rhf);
        stabilized_walker.stabilize();
        require_near(stabilized_walker.overlap(rhf),
                     overlap_before_stabilization, 1e-11,
                     "QR stabilization preserves physical overlap");
        require_near(
            stabilized_walker.up_log_abs_scale() +
                stabilized_walker.down_log_abs_scale(),
            stabilized_walker.log_abs_scale(), 1e-14,
            "spin-resolved QR scales reconstruct combined scale");

        const std::vector<int> fields_m2 = {
            +1, -1, +1, -1, -1, +1, -1, +1};
        const auto unstabilized_m2 =
            evaluator.evaluate(fields_m2, 2, true);
        const auto stabilized_m2 =
            audit::PathEvaluator(model, rhf, model.row_major_order(),
                                 audit::ProposalKind::SiteBySite, 1)
                .evaluate(fields_m2, 2, true);
        require_near(stabilized_m2.final_overlap,
                     unstabilized_m2.final_overlap, 1e-10,
                     "periodic QR preserves final path overlap");
        require_near(stabilized_m2.log_q_prop,
                     unstabilized_m2.log_q_prop, 1e-11,
                     "periodic QR preserves proposal probability");
        require_near(stabilized_m2.log_w_ratio,
                     unstabilized_m2.log_w_ratio, 1e-11,
                     "periodic QR preserves walker weight");

        const auto all_next =
            evaluator.advance_all_slice_fields(evaluator.initial_state(), 0,
                                               true, false);
        require_true(all_next.size() == 16,
                     "all 2^4 next-slice states are generated");
        std::size_t selected_mask = 0;
        for (std::size_t site = 0; site < fields.size(); ++site) {
            if (fields.at(site) == +1) {
                selected_mask |= std::size_t{1}
                                 << (fields.size() - 1U - site);
            }
        }
        const auto batched = evaluator.finish(all_next.at(selected_mask));
        require_near(batched.final_overlap, result.final_overlap, 1e-12,
                     "batched and single-slice final overlap");
        require_near(batched.log_q_prop, result.log_q_prop, 1e-12,
                     "batched and single-slice proposal probability");

        for (const auto& step : result.trace) {
            if (step.kind == audit::StepKind::Site && step.alive_before) {
                require_near(step.q_plus + step.q_minus, 1.0, 1e-12,
                             "site proposal is normalized");
            }
        }

        if (result.alive) {
            const double reconstructed =
                std::exp(result.log_q_prop + result.log_w_ratio +
                         result.log_common_factor) *
                result.initial_overlap;
            const double direct =
                std::pow(0.5, static_cast<double>(fields.size())) *
                result.final_overlap *
                std::pow(model.slice_constant(), 1.0);
            require_near(reconstructed, direct, 1e-11,
                         "site-by-site QW identity");
        }

        const audit::PathEvaluator joint_evaluator(
            model, rhf, model.row_major_order(),
            audit::ProposalKind::JointSlice);
        const auto joint = joint_evaluator.evaluate(fields, 1, true);
        require_true(joint.trace.size() == 1,
                     "joint proposal records one step per slice");
        if (joint.alive) {
            const double reconstructed =
                std::exp(joint.log_q_prop + joint.log_w_ratio +
                         joint.log_common_factor) *
                joint.initial_overlap;
            const double direct =
                std::pow(0.5, static_cast<double>(fields.size())) *
                joint.final_overlap * model.slice_constant();
            require_near(reconstructed, direct, 1e-11,
                         "joint-slice QW identity");
        }

        const auto reverse_result = audit::PathEvaluator(
                                        model, rhf, model.reverse_order(),
                                        audit::ProposalKind::SiteBySite)
                                        .evaluate(fields, 1, true);
        require_near(reverse_result.final_overlap, result.final_overlap,
                     1e-11,
                     "full-slice overlap is invariant under site order");

        bool wrong_length_rejected = false;
        try {
            (void)evaluator.evaluate({+1, -1}, 1, true);
        } catch (const std::invalid_argument&) {
            wrong_length_rejected = true;
        }
        require_true(wrong_length_rejected,
                     "field sequence length mismatch is rejected");

        bool found_pre_halfk_rejection = false;
        bool found_post_halfk_rejection = false;
        std::uint64_t rng_state = UINT64_C(0x6a09e667f3bcc909);
        const auto next_random = [&rng_state]() {
            rng_state ^= rng_state << 13U;
            rng_state ^= rng_state >> 7U;
            rng_state ^= rng_state << 17U;
            return rng_state;
        };
        const auto random_value = [&next_random]() {
            constexpr double denominator =
                static_cast<double>(UINT64_C(0x1fffff));
            return 2.0 *
                       static_cast<double>(next_random() &
                                           UINT64_C(0x1fffff)) /
                       denominator -
                   1.0;
        };
        const audit::PathEvaluator nodal_evaluator(
            model, rhf, guide, model.row_major_order(),
            audit::ProposalKind::SiteBySite);
        for (std::size_t sample = 0; sample < 10000U; ++sample) {
            audit::Matrix walker_up(model.sites(), model.n_up());
            audit::Matrix walker_down(model.sites(), model.n_down());
            for (std::size_t row = 0; row < model.sites(); ++row) {
                for (std::size_t col = 0; col < model.n_up(); ++col) {
                    walker_up(row, col) = random_value();
                }
                for (std::size_t col = 0; col < model.n_down(); ++col) {
                    walker_down(row, col) = random_value();
                }
            }
            audit::EvaluationState node{
                audit::Walker(walker_up, walker_down),
                audit::PathSummary{}};
            node.summary.initial_overlap =
                node.walker.overlap(guide);
            if (node.summary.initial_overlap < 0.0) {
                for (std::size_t row = 0; row < model.sites(); ++row) {
                    walker_up(row, 0) = -walker_up(row, 0);
                }
                node.walker = audit::Walker(walker_up, walker_down);
                node.summary.initial_overlap =
                    node.walker.overlap(guide);
            }
            if (!(node.summary.initial_overlap > 1e-10)) {
                continue;
            }
            node.summary.min_abs_overlap =
                std::abs(node.summary.initial_overlap);
            std::vector<int> search_fields(model.sites());
            for (auto& field : search_fields) {
                field = (next_random() & 1U) != 0U ? +1 : -1;
            }
            const auto search = nodal_evaluator.finish(
                nodal_evaluator.advance_slice(
                    node, search_fields, 7, true, true));
            found_pre_halfk_rejection =
                found_pre_halfk_rejection ||
                search.first_rejection_kind ==
                    audit::RejectionKind::PreHalfK;
            found_post_halfk_rejection =
                found_post_halfk_rejection ||
                search.first_rejection_kind ==
                    audit::RejectionKind::PostHalfK;
            if (found_pre_halfk_rejection &&
                found_post_halfk_rejection) {
                break;
            }
        }
        require_true(found_pre_halfk_rejection,
                     "pre-half-K rejection is classified");
        require_true(found_post_halfk_rejection,
                     "post-half-K rejection is classified");
    });
}
