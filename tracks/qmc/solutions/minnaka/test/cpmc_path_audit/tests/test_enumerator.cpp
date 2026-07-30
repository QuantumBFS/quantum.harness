#include "enumerator.hpp"
#include "fock_oracle.hpp"

#include "test_common.hpp"

#include <cmath>
#include <cstdio>
#include <string>

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto trial = audit::TrialState::rhf_x(model);

        audit::EnumerationOptions options;
        options.slices = 2;
        options.trial_code = audit::TrialCode::RhfX;
        options.proposal_code = audit::ProposalCode::SiteBySite;
        options.site_order_code = audit::SiteOrderCode::RowMajor;
        options.output_path = "build/test_enumeration.bin";
        options.progress_updates = 0;

        const audit::PathEvaluator evaluator(
            model, trial, model.row_major_order(),
            audit::ProposalKind::SiteBySite);
        const auto result = audit::enumerate_paths(evaluator, options);
        require_true(result.records == 256, "M=2 record count");
        require_true(result.negative_records == 0,
                     "half-filled records must be nonnegative");
        require_true(result.max_alive_identity_residual < 1e-10,
                     "pathwise QW identity");

        const auto bottleneck =
            audit::linear_bottleneck({0.0, -3.0, 4.0});
        require_near(bottleneck.depth, 5.0, 1e-12,
                     "linear-detrended bottleneck depth");
        require_true(bottleneck.slice == 1,
                     "linear-detrended bottleneck location");
        const auto shifted =
            audit::linear_bottleneck({0.0, -5.0, 0.0});
        require_near(shifted.depth, bottleneck.depth, 1e-12,
                     "bottleneck is invariant to per-slice energy shift");

        const audit::FockOracle oracle(model);
        const double expected =
            oracle.projected_amplitude(trial, trial, options.slices);
        require_near(result.signed_sum_d, expected, 1e-10,
                     "enumerated sum equals direct projection");

        audit::PathRecordReader reader(options.output_path);
        require_true(reader.header().actual_records == 256,
                     "finalized binary record count");
        audit::PathRecord record;
        for (std::uint64_t id = 0; id <= 37; ++id) {
            require_true(reader.read(record), "read selected record");
        }
        require_true(record.config_id == 37,
                     "records are in ascending config-ID order");

        const auto fields =
            audit::decode_fields(record.config_id, model.sites() * 2);
        const auto direct = evaluator.evaluate(fields, 2, true);
        const double direct_log_d =
            -static_cast<double>(fields.size()) * std::log(2.0) +
            direct.log_common_factor + std::log(std::abs(direct.final_overlap));
        require_near(record.log_abs_d, direct_log_d, 1e-12,
                     "stored physical path contribution");
        require_true(record.alive == direct.alive,
                     "stored constrained-path survival");
        require_true(record.linear_bottleneck >= 0.0,
                     "stored detrended bottleneck is nonnegative");

        std::remove(options.output_path.c_str());
    });
}
