#include "path_format.hpp"

#include "test_common.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

template <class Callable>
void require_throws(Callable&& callable, const std::string& message) {
    bool threw = false;
    try {
        callable();
    } catch (const std::exception&) {
        threw = true;
    }
    require_true(threw, message);
}

}  // namespace

int main() {
    using audit::PathFileHeader;
    using audit::PathRecord;
    using audit::ProposalCode;
    using audit::SiteOrderCode;
    using audit::TrialCode;
    return run_test_main([&] {
        const std::vector<int> fields{-1, +1, +1, -1,
                                      +1, -1, -1, +1};
        const std::uint64_t config_id = audit::encode_fields(fields);
        require_true(config_id == 0x69U, "config ID bit convention");
        require_true(
            audit::decode_fields(config_id, fields.size()) == fields,
            "config ID round trip");
        require_throws(
            [] { (void)audit::encode_fields({-1, 0, +1}); },
            "invalid field must be rejected");

        PathFileHeader header;
        header.lx = 2;
        header.ly = 2;
        header.n_up = 2;
        header.n_down = 2;
        header.slices = 6;
        header.trial = TrialCode::Uhf;
        header.proposal = ProposalCode::SiteBySite;
        header.site_order = SiteOrderCode::RowMajor;
        header.hopping = 1.0;
        header.interaction = 8.0;
        header.dt = 0.1;
        header.expected_records = std::uint64_t{1} << 24U;

        PathRecord record;
        record.config_id = config_id;
        record.log_abs_d = -12.5;
        record.log_q = -10.25;
        record.log_abs_weight = -2.25;
        record.min_log_abs_weight = -7.0;
        record.min_abs_overlap = 1.0e-9;
        record.argmin_weight_step = 17;
        record.first_rejected_step = audit::no_rejection_step;
        record.linear_bottleneck = 3.25;
        record.argmin_linear_slice = 4;
        record.sign_d = +1;
        record.alive = true;

        const std::string path = "build/test_paths.bin";
        {
            audit::PathRecordWriter writer(path, header);
            writer.write(record);
            writer.close();
        }
        {
            audit::PathRecordReader reader(path);
            const auto& actual_header = reader.header();
            require_true(actual_header.lx == header.lx,
                         "header lx round trip");
            require_true(actual_header.slices == header.slices,
                         "header slices round trip");
            require_true(actual_header.trial == header.trial,
                         "header trial round trip");
            require_true(
                actual_header.expected_records == header.expected_records,
                "expected record count round trip");
            require_true(actual_header.actual_records == 1,
                         "actual record count finalized");

            PathRecord actual;
            require_true(reader.read(actual), "record must be readable");
            require_true(actual.config_id == record.config_id,
                         "record config ID round trip");
            require_near(actual.log_abs_d, record.log_abs_d, 0.0,
                         "record log D round trip");
            require_near(actual.min_abs_overlap, record.min_abs_overlap, 0.0,
                         "record overlap round trip");
            require_true(
                actual.first_rejected_step == record.first_rejected_step,
                "record rejection step round trip");
            require_true(actual.sign_d == record.sign_d,
                         "record sign round trip");
            require_true(actual.alive == record.alive,
                         "record alive round trip");
            require_near(actual.linear_bottleneck,
                         record.linear_bottleneck, 0.0,
                         "record detrended bottleneck round trip");
            require_true(
                actual.argmin_linear_slice ==
                    record.argmin_linear_slice,
                "record bottleneck slice round trip");
            require_true(!reader.read(actual),
                         "reader must stop at end of file");
        }

        PathFileHeader mismatch = header;
        mismatch.dt = 0.05;
        require_throws(
            [&] { audit::validate_compatible(header, mismatch); },
            "metadata mismatch must be rejected");

        std::remove(path.c_str());
    });
}
