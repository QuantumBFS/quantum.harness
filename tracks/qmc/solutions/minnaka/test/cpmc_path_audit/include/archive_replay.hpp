#pragma once

#include "archive_reader.hpp"
#include "path_evaluator.hpp"
#include "physical_path.hpp"

#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iosfwd>
#include <string>
#include <vector>

namespace audit {

struct PrefixReplayRecord {
    std::uint64_t sample_id = 0;
    std::uint32_t slice = 0;
    bool alive_after_slice = false;
    double log_q = 0.0;
    double log_w_ratio = 0.0;
    double log_w_phys = 0.0;
    double log_normalized_overlap = 0.0;
    double sigma_min = 0.0;
    double min_q_in_slice = 0.0;
};

struct ArchiveReplayResult {
    ArchiveRecordView source;
    PhysicalPathResult physical;
    PathSummary path;
    double log_w_stock = 0.0;
    double log_w_phys = 0.0;
    double s_ref = 0.0;
    double identity_log_residual = 0.0;
    std::size_t min_selected_q_slice = 0;
    std::size_t min_selected_q_site = 0;
    std::size_t min_halfk_slice = 0;
    StepKind min_halfk_kind = StepKind::PreHalfK;
    double min_normalized_overlap = 1.0;
    double min_sigma = 1.0;
    double max_principal_angle = 0.0;
    std::vector<PrefixReplayRecord> prefixes;
};

class PrefixFileWriter {
public:
    PrefixFileWriter(const std::string& path, std::uint64_t record_count);
    void write(const PrefixReplayRecord& record);
    void finish();
    ~PrefixFileWriter();

private:
    std::ofstream output_;
    std::uint64_t expected_ = 0;
    std::uint64_t written_ = 0;
    bool finished_ = false;
};

ArchiveReplayResult replay_archive_record(
    const ArchiveHeader& header,
    const ArchiveRecordView& record,
    const HubbardModel& model,
    const TrialState& initial,
    const TrialState& guide,
    const std::vector<std::size_t>& cpp_site_by_alf_site,
    std::size_t center_slice,
    std::size_t stabilization_interval,
    double reference_energy
);

void write_prefix_file(
    const std::string& path,
    const std::vector<PrefixReplayRecord>& records
);

std::vector<PrefixReplayRecord> read_prefix_file(
    const std::string& path
);

void write_replay_summary_header(std::ostream& output);
void write_replay_summary_row(
    std::ostream& output,
    const ArchiveHeader& header,
    const ArchiveReplayResult& result
);

}  // namespace audit
