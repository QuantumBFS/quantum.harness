#pragma once

#include <cstdint>
#include <fstream>
#include <string>
#include <vector>

namespace audit {

struct ArchiveHeader {
    std::uint32_t version = 0;
    std::uint32_t record_bytes = 0;
    std::uint32_t lx = 0;
    std::uint32_t ly = 0;
    std::uint32_t n_up = 0;
    std::uint32_t n_down = 0;
    std::uint32_t ltrot = 0;
    std::uint32_t nsites = 0;
    std::uint32_t nfield = 0;
    std::uint32_t payload_bytes = 0;
    double hopping = 0.0;
    double interaction = 0.0;
    double dt = 0.0;
    double beta = 0.0;
    double theta = 0.0;
    std::uint8_t ensemble_code = 0;
    std::string selected_projection_sha256;
    std::string trial_manifest_sha256;
};

struct ArchiveRecordView {
    std::uint64_t sample_id = 0;
    std::uint32_t chain_id = 0;
    std::uint32_t bin_id = 0;
    std::uint64_t sweep_id = 0;
    std::int8_t frozen_sign = 0;
    bool endpoint_present = false;
    std::uint16_t flags = 0;
    double central_ekin = 0.0;
    double central_epot = 0.0;
    double central_etot = 0.0;
    double central_npart = 0.0;
    std::int8_t endpoint_sign = 0;
    double endpoint_logabs_d = 0.0;
    double endpoint_ekin = 0.0;
    double endpoint_epot = 0.0;
    double endpoint_etot = 0.0;
    std::vector<int> fields;
};

class ArchiveReader {
public:
    explicit ArchiveReader(const std::string& path);
    const ArchiveHeader& header() const noexcept { return header_; }
    bool read(ArchiveRecordView& record);
    bool truncated_tail() const noexcept { return truncated_tail_; }

private:
    ArchiveHeader header_;
    std::ifstream stream_;
    bool truncated_tail_ = false;
};

}  // namespace audit
