#include "replay.hpp"
#include "path_format.hpp"

#include "test_common.hpp"

#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto trial = audit::TrialState::rhf_x(model);
        const audit::PathEvaluator evaluator(
            model, trial, model.row_major_order(),
            audit::ProposalKind::SiteBySite);
        const std::vector<int> fields{+1, -1, -1, +1};
        const auto config_id = audit::encode_fields(fields);
        const std::string output = "build/test_trace.csv";

        const auto summary =
            audit::replay_config(evaluator, config_id, 1, true, output);
        require_true(summary.trace.size() == 6, "replay keeps all substeps");

        std::ifstream stream(output);
        require_true(static_cast<bool>(stream), "trace CSV is created");
        std::size_t lines = 0;
        std::string line;
        while (std::getline(stream, line)) {
            ++lines;
        }
        require_true(lines == 7, "trace CSV header plus six rows");
        std::remove(output.c_str());
    });
}
