#pragma once

#include <cstddef>
#include <cstdint>
#include <fstream>
#include <limits>
#include <string>
#include <vector>

namespace audit {

enum class TrialCode : std::uint32_t { RhfX = 1, RhfY = 2, Uhf = 3 };
enum class ProposalCode : std::uint32_t { SiteBySite = 1, JointSlice = 2 };
enum class SiteOrderCode : std::uint32_t {
    RowMajor = 1,
    Reverse = 2,
    Sublattice = 3,
    NotApplicable = 4
};

inline constexpr std::uint32_t no_rejection_step =
    std::numeric_limits<std::uint32_t>::max();

struct PathFileHeader {
    std::uint32_t format_version = 2;
    std::uint32_t lx = 0;
    std::uint32_t ly = 0;
    std::uint32_t n_up = 0;
    std::uint32_t n_down = 0;
    std::uint32_t slices = 0;
    TrialCode trial = TrialCode::RhfX;
    ProposalCode proposal = ProposalCode::SiteBySite;
    SiteOrderCode site_order = SiteOrderCode::RowMajor;
    double hopping = 0.0;
    double interaction = 0.0;
    double dt = 0.0;
    std::uint64_t expected_records = 0;
    std::uint64_t actual_records = 0;
};

struct PathRecord {
    std::uint64_t config_id = 0;
    double log_abs_d = -std::numeric_limits<double>::infinity();
    double log_q = -std::numeric_limits<double>::infinity();
    double log_abs_weight = -std::numeric_limits<double>::infinity();
    double min_log_abs_weight = 0.0;
    double min_abs_overlap = std::numeric_limits<double>::infinity();
    std::uint32_t argmin_weight_step = 0;
    std::uint32_t first_rejected_step = no_rejection_step;
    std::int8_t sign_d = 0;
    bool alive = false;
    double linear_bottleneck = 0.0;
    std::uint8_t argmin_linear_slice = 0;
};

std::uint64_t encode_fields(const std::vector<int>& fields);
std::vector<int> decode_fields(std::uint64_t config_id,
                               std::size_t field_count);
void validate_compatible(const PathFileHeader& expected,
                         const PathFileHeader& actual);

class PathRecordWriter {
public:
    PathRecordWriter(const std::string& path, PathFileHeader header);
    ~PathRecordWriter();

    PathRecordWriter(const PathRecordWriter&) = delete;
    PathRecordWriter& operator=(const PathRecordWriter&) = delete;

    void write(const PathRecord& record);
    void flush();
    void close();
    std::uint64_t count() const noexcept { return header_.actual_records; }

private:
    void write_header();

    std::fstream stream_;
    PathFileHeader header_;
    bool closed_ = false;
};

class PathRecordReader {
public:
    explicit PathRecordReader(const std::string& path);

    const PathFileHeader& header() const noexcept { return header_; }
    bool read(PathRecord& record);

private:
    std::ifstream stream_;
    PathFileHeader header_;
    std::uint64_t records_read_ = 0;
};

}  // namespace audit
