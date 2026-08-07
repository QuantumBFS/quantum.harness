#include "batch_replay.hpp"

#include "test_common.hpp"

#include <cmath>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

namespace {

std::size_t line_count(const std::string& path) {
    std::ifstream stream(path);
    require_true(static_cast<bool>(stream), "batch output exists");
    std::size_t result = 0;
    std::string line;
    while (std::getline(stream, line)) {
        ++result;
    }
    return result;
}

}  // namespace

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto trial = audit::TrialState::rhf_x(model);
        const audit::PathEvaluator evaluator(
            model, trial, model.row_major_order(),
            audit::ProposalKind::SiteBySite);
        const std::vector<int> fields{+1, +1, -1, -1};
        require_true(audit::exhaustive_mask_prediction_available(4),
                     "2x2 uses exhaustive next-slice prediction");
        require_true(!audit::exhaustive_mask_prediction_available(16),
                     "4x4 uses greedy-only next-slice prediction");

        const auto diagnostic =
            audit::diagnose_path(evaluator, fields, 1, true);
        require_true(diagnostic.steps.size() == 6,
                     "one slice has six detailed events");
        require_true(diagnostic.mask_predictions.size() == 1,
                     "one next-slice prediction is recorded");
        const auto& prediction = diagnostic.mask_predictions.front();
        require_true(prediction.exhaustive_available,
                     "2x2 mask prediction is exhaustive");
        require_true(prediction.realized_rank >= 1 &&
                         prediction.realized_rank <= 16,
                     "realized mask rank is one based");
        require_true(prediction.realized_mask == 0b0011,
                     "written mask uses site-index bits");
        for (const auto& step : diagnostic.steps) {
            require_true(
                std::isfinite(
                    step.subspace.log_abs_normalized_overlap),
                "subspace overlap is recorded after every event");
        }

        const std::string manifest_path = "build/test_batch_manifest.csv";
        const std::string fields_path = "build/test_batch_fields.txt";
        const std::string steps_path = "build/test_batch_steps.csv";
        const std::string masks_path = "build/test_batch_masks.csv";
        {
            std::ofstream field_stream(fields_path);
            field_stream << "+1 +1 -1 -1\n";
        }
        {
            std::ofstream manifest(manifest_path);
            manifest
                << "path_id,role,case_id,config_id,fields_file,score,"
                   "log_d_over_mean,weight_bin\n"
                << "p0,case,12,12,,3.0,0.2,important\n"
                << "p1,low_weight_reference,12,," << fields_path
                << ",2.9,-2.0,below_half\n";
        }
        const auto rows = audit::read_batch_manifest(manifest_path);
        require_true(rows.size() == 2, "two manifest rows are parsed");
        audit::run_batch_replay(evaluator, 1, rows, steps_path,
                                masks_path, 2);
        require_true(line_count(steps_path) == 13,
                     "two paths write twelve step rows plus header");
        require_true(line_count(masks_path) == 3,
                     "two paths write two mask rows plus header");

        const auto model_4x4 =
            audit::HubbardModel::square_periodic(
                4, 4, 1.0, 8.0, 0.1, 8, 8);
        const auto trial_4x4 =
            audit::TrialState::solve_uhf(model_4x4, 8.0);
        const audit::PathEvaluator evaluator_4x4(
            model_4x4, trial_4x4, model_4x4.row_major_order(),
            audit::ProposalKind::SiteBySite);
        const std::vector<int> fields_4x4{
            +1, -1, +1, -1, -1, +1, -1, +1,
            +1, -1, +1, -1, -1, +1, -1, +1};
        const auto diagnostic_4x4 =
            audit::diagnose_path(evaluator_4x4, fields_4x4, 1, true);
        require_true(diagnostic_4x4.steps.size() == 18,
                     "4x4 slice has sixteen sites and two half-K events");
        require_true(
            !diagnostic_4x4.mask_predictions.front().exhaustive_available,
            "4x4 skips exhaustive next-slice expansion");
        require_true(
            diagnostic_4x4.mask_predictions.front().candidate_count == 0,
            "4x4 creates no exhaustive candidate states");

        std::remove(manifest_path.c_str());
        std::remove(fields_path.c_str());
        std::remove(steps_path.c_str());
        std::remove(masks_path.c_str());
    });
}
