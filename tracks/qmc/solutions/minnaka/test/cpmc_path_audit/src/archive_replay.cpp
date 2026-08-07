#include "archive_replay.hpp"

#include "path_diagnostics.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <stdexcept>

namespace audit {
namespace {

constexpr std::size_t kPrefixHeaderBytes = 64;
constexpr std::size_t kPrefixRecordBytes = 72;
constexpr double kNegativeInfinity =
    -std::numeric_limits<double>::infinity();

void validate_site_map(
    const std::vector<std::size_t>& map, std::size_t sites
) {
    if (map.size() != sites) {
        throw std::invalid_argument("ALF/C++ site map has wrong length");
    }
    std::vector<bool> seen(sites, false);
    for (const auto site : map) {
        if (site >= sites || seen.at(site)) {
            throw std::invalid_argument(
                "ALF/C++ site map is not a bijection"
            );
        }
        seen.at(site) = true;
    }
}

void append_u32(
    std::vector<unsigned char>& raw, std::uint32_t value
) {
    for (unsigned shift = 0; shift < 32; shift += 8) {
        raw.push_back(static_cast<unsigned char>(value >> shift));
    }
}

void append_u64(
    std::vector<unsigned char>& raw, std::uint64_t value
) {
    for (unsigned shift = 0; shift < 64; shift += 8) {
        raw.push_back(static_cast<unsigned char>(value >> shift));
    }
}

void append_f64(std::vector<unsigned char>& raw, double value) {
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value), "unexpected double size");
    std::memcpy(&bits, &value, sizeof(bits));
    append_u64(raw, bits);
}

std::uint32_t read_u32(
    const std::vector<unsigned char>& raw, std::size_t offset
) {
    if (offset + 4 > raw.size()) {
        throw std::runtime_error("truncated prefix integer");
    }
    std::uint32_t value = 0;
    for (unsigned index = 0; index < 4; ++index) {
        value |= static_cast<std::uint32_t>(raw[offset + index])
                 << (8U * index);
    }
    return value;
}

std::uint64_t read_u64(
    const std::vector<unsigned char>& raw, std::size_t offset
) {
    if (offset + 8 > raw.size()) {
        throw std::runtime_error("truncated prefix integer");
    }
    std::uint64_t value = 0;
    for (unsigned index = 0; index < 8; ++index) {
        value |= static_cast<std::uint64_t>(raw[offset + index])
                 << (8U * index);
    }
    return value;
}

double read_f64(
    const std::vector<unsigned char>& raw, std::size_t offset
) {
    const std::uint64_t bits = read_u64(raw, offset);
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

std::uint32_t crc32(const unsigned char* data, std::size_t size) {
    std::uint32_t crc = 0xffffffffU;
    for (std::size_t index = 0; index < size; ++index) {
        crc ^= data[index];
        for (int bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask =
                0U - static_cast<std::uint32_t>(crc & 1U);
            crc = (crc >> 1U) ^ (0xedb88320U & mask);
        }
    }
    return ~crc;
}

std::vector<unsigned char> read_exact(
    std::istream& input, std::size_t count
) {
    std::vector<unsigned char> raw(count);
    input.read(
        reinterpret_cast<char*>(raw.data()),
        static_cast<std::streamsize>(count)
    );
    raw.resize(static_cast<std::size_t>(input.gcount()));
    return raw;
}

const char* rejection_name(RejectionKind kind) {
    switch (kind) {
        case RejectionKind::None:
            return "none";
        case RejectionKind::PreHalfK:
            return "pre_half_k";
        case RejectionKind::Site:
            return "site";
        case RejectionKind::PostHalfK:
            return "post_half_k";
    }
    throw std::logic_error("unknown rejection kind");
}

const char* step_name(StepKind kind) {
    switch (kind) {
        case StepKind::PreHalfK:
            return "pre_half_k";
        case StepKind::Site:
            return "site";
        case StepKind::PostHalfK:
            return "post_half_k";
        case StepKind::JointSlice:
            return "joint_slice";
    }
    throw std::logic_error("unknown step kind");
}

std::vector<std::uint8_t> map_and_pack_fields(
    const ArchiveHeader& header,
    const ArchiveRecordView& record,
    const std::vector<std::size_t>& cpp_site_by_alf_site,
    std::vector<int>& mapped
) {
    if (record.fields.size() != header.nfield) {
        throw std::invalid_argument("archive replay field count mismatch");
    }
    mapped.assign(header.nfield, -1);
    std::vector<std::uint8_t> packed(
        (static_cast<std::size_t>(header.nfield) + 7U) / 8U, 0
    );
    for (std::size_t slice = 0; slice < header.ltrot; ++slice) {
        for (std::size_t alf = 0; alf < header.nsites; ++alf) {
            const std::size_t source = slice * header.nsites + alf;
            const std::size_t target =
                slice * header.nsites + cpp_site_by_alf_site.at(alf);
            const int field = record.fields.at(source);
            if (field != -1 && field != +1) {
                throw std::invalid_argument(
                    "archive replay field is not binary"
                );
            }
            mapped.at(target) = field;
            if (field == +1) {
                packed.at(target / 8U) |=
                    static_cast<std::uint8_t>(1U << (target % 8U));
            }
        }
    }
    return packed;
}

double safe_exp(double value) {
    if (value == kNegativeInfinity) {
        return 0.0;
    }
    if (value >= std::log(std::numeric_limits<double>::max())) {
        return std::numeric_limits<double>::max();
    }
    return std::exp(value);
}

}  // namespace

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
) {
    if (header.lx != model.lx() || header.ly != model.ly() ||
        header.n_up != model.n_up() || header.n_down != model.n_down() ||
        header.nsites != model.sites() ||
        header.nfield != header.ltrot * header.nsites ||
        std::abs(header.hopping - model.hopping()) > 1.0e-14 ||
        std::abs(header.interaction - model.u()) > 1.0e-14 ||
        std::abs(header.dt - model.dt()) > 1.0e-14) {
        throw std::invalid_argument("archive/model contract mismatch");
    }
    if (center_slice > header.ltrot || stabilization_interval == 0) {
        throw std::invalid_argument(
            "invalid replay center/stabilization interval"
        );
    }
    validate_site_map(cpp_site_by_alf_site, model.sites());

    std::vector<int> mapped_fields;
    const auto packed = map_and_pack_fields(
        header, record, cpp_site_by_alf_site, mapped_fields
    );
    ArchiveReplayResult result;
    result.source = record;
    result.physical = evaluate_physical_path(
        model, initial, guide,
        {packed.data(), mapped_fields.size()},
        header.ltrot, center_slice, stabilization_interval
    );

    PathEvaluator evaluator(
        model, initial, guide, cpp_site_by_alf_site,
        ProposalKind::SiteBySite, stabilization_interval
    );
    EvaluationState state = evaluator.initial_state();
    double min_log_normalized = 0.0;
    for (std::size_t slice = 0; slice < header.ltrot; ++slice) {
        const auto first = mapped_fields.begin() +
            static_cast<std::ptrdiff_t>(slice * model.sites());
        const std::vector<int> slice_fields(
            first, first + static_cast<std::ptrdiff_t>(model.sites())
        );
        state = evaluator.advance_slice(
            state, slice_fields, slice, true, true
        );

        double min_q_in_slice = 1.0;
        for (const auto& trace : state.summary.trace) {
            if (trace.kind == StepKind::Site && trace.alive_before &&
                trace.q_selected < min_q_in_slice) {
                min_q_in_slice = trace.q_selected;
                if (trace.q_selected <= state.summary.min_selected_q) {
                    result.min_selected_q_slice = trace.slice;
                    result.min_selected_q_site = trace.site;
                }
            }
            if ((trace.kind == StepKind::PreHalfK ||
                 trace.kind == StepKind::PostHalfK) &&
                trace.alive_before && trace.overlap_ratio > 0.0 &&
                trace.overlap_ratio <= state.summary.min_halfk_ratio) {
                result.min_halfk_slice = trace.slice;
                result.min_halfk_kind = trace.kind;
            }
        }
        state.summary.trace.clear();

        double log_normalized = kNegativeInfinity;
        double sigma_min = 0.0;
        double principal_angle = std::acos(0.0);
        try {
            const auto diagnostic =
                diagnose_subspace(guide, state.walker);
            log_normalized = diagnostic.log_abs_normalized_overlap;
            sigma_min = std::min(
                diagnostic.up.sigma_min, diagnostic.down.sigma_min
            );
            principal_angle = std::max(
                diagnostic.up.principal_angle_max,
                diagnostic.down.principal_angle_max
            );
        } catch (const std::runtime_error&) {
            // An exactly singular overlap is itself the limiting diagnostic.
        }
        min_log_normalized =
            std::min(min_log_normalized, log_normalized);
        result.min_sigma = std::min(result.min_sigma, sigma_min);
        result.max_principal_angle =
            std::max(result.max_principal_angle, principal_angle);
        result.prefixes.push_back(
            {record.sample_id, static_cast<std::uint32_t>(slice),
             state.summary.alive, state.summary.log_q_prop,
             state.summary.log_w_ratio,
             state.summary.log_w_ratio +
                 state.summary.log_common_factor,
             log_normalized, sigma_min, min_q_in_slice}
        );
    }
    result.path = evaluator.finish(state);
    result.path.trace.clear();
    if (!std::isfinite(result.path.min_selected_q)) {
        result.path.min_selected_q =
            result.path.first_rejection_kind == RejectionKind::Site
                ? 0.0
                : 1.0;
        result.min_selected_q_slice =
            result.path.first_rejection_slice ==
                    std::numeric_limits<std::size_t>::max()
                ? 0
                : result.path.first_rejection_slice;
        result.min_selected_q_site =
            result.path.first_rejection_site ==
                    std::numeric_limits<std::size_t>::max()
                ? 0
                : result.path.first_rejection_site;
    }
    if (!std::isfinite(result.path.min_halfk_ratio)) {
        const bool rejected_at_half_k =
            result.path.first_rejection_kind == RejectionKind::PreHalfK ||
            result.path.first_rejection_kind == RejectionKind::PostHalfK;
        result.path.min_halfk_ratio = rejected_at_half_k ? 0.0 : 1.0;
        if (rejected_at_half_k) {
            result.min_halfk_slice = result.path.first_rejection_slice;
            result.min_halfk_kind =
                result.path.first_rejection_kind ==
                        RejectionKind::PreHalfK
                    ? StepKind::PreHalfK
                    : StepKind::PostHalfK;
        }
    }
    result.min_normalized_overlap = safe_exp(min_log_normalized);
    result.log_w_phys =
        result.path.log_w_ratio + result.path.log_common_factor;
    result.s_ref = reference_energy * model.dt() *
                   static_cast<double>(header.ltrot);
    result.log_w_stock = result.log_w_phys + result.s_ref;

    if (result.path.alive) {
        const auto initial_overlap =
            Walker::from_trial(initial).overlap_signed_log(guide);
        if (initial_overlap.sign == 0 ||
            result.physical.d_ti.sign != initial_overlap.sign) {
            result.identity_log_residual =
                std::numeric_limits<double>::infinity();
        } else {
            const double reconstructed =
                initial_overlap.log_abs + result.path.log_q_prop +
                result.log_w_phys;
            result.identity_log_residual = std::abs(
                result.physical.d_ti.log_abs - reconstructed
            );
        }
    } else {
        result.identity_log_residual =
            std::numeric_limits<double>::quiet_NaN();
    }
    return result;
}

void write_prefix_file(
    const std::string& path,
    const std::vector<PrefixReplayRecord>& records
) {
    PrefixFileWriter output(path, records.size());
    for (const auto& record : records) {
        output.write(record);
    }
    output.finish();
}

PrefixFileWriter::PrefixFileWriter(
    const std::string& path, std::uint64_t record_count
) : output_(path, std::ios::binary), expected_(record_count) {
    if (!output_) {
        throw std::runtime_error("cannot write prefix file: " + path);
    }
    std::vector<unsigned char> header;
    header.insert(header.end(), {'Q', 'H', 'P', 'F', 'X', '0', '1', '\0'});
    append_u32(header, 1);
    append_u32(header, 0x01020304U);
    append_u32(header, static_cast<std::uint32_t>(kPrefixHeaderBytes));
    append_u32(header, static_cast<std::uint32_t>(kPrefixRecordBytes));
    append_u64(header, record_count);
    header.resize(kPrefixHeaderBytes, 0);
    output_.write(
        reinterpret_cast<const char*>(header.data()),
        static_cast<std::streamsize>(header.size())
    );
    if (!output_) {
        throw std::runtime_error("failed while writing prefix header");
    }
}

void PrefixFileWriter::write(const PrefixReplayRecord& record) {
    if (finished_ || written_ >= expected_) {
        throw std::runtime_error("too many prefix records");
    }
    std::vector<unsigned char> raw;
    append_u64(raw, record.sample_id);
    append_u32(raw, record.slice);
    raw.push_back(record.alive_after_slice ? 1U : 0U);
    raw.insert(raw.end(), 3, 0);
    append_f64(raw, record.log_q);
    append_f64(raw, record.log_w_ratio);
    append_f64(raw, record.log_w_phys);
    append_f64(raw, record.log_normalized_overlap);
    append_f64(raw, record.sigma_min);
    append_f64(raw, record.min_q_in_slice);
    append_u32(raw, crc32(raw.data(), raw.size()));
    raw.resize(kPrefixRecordBytes, 0);
    output_.write(
        reinterpret_cast<const char*>(raw.data()),
        static_cast<std::streamsize>(raw.size())
    );
    ++written_;
    if (!output_) {
        throw std::runtime_error("failed while writing prefix file");
    }
}

void PrefixFileWriter::finish() {
    if (written_ != expected_) {
        throw std::runtime_error("prefix record count mismatch");
    }
    output_.flush();
    if (!output_) {
        throw std::runtime_error("failed while flushing prefix file");
    }
    finished_ = true;
}

PrefixFileWriter::~PrefixFileWriter() = default;

std::vector<PrefixReplayRecord> read_prefix_file(
    const std::string& path
) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("cannot read prefix file: " + path);
    }
    const auto header = read_exact(input, kPrefixHeaderBytes);
    const std::array<unsigned char, 8> magic{
        'Q', 'H', 'P', 'F', 'X', '0', '1', '\0'
    };
    if (header.size() != kPrefixHeaderBytes ||
        !std::equal(magic.begin(), magic.end(), header.begin()) ||
        read_u32(header, 8) != 1 ||
        read_u32(header, 12) != 0x01020304U ||
        read_u32(header, 16) != kPrefixHeaderBytes ||
        read_u32(header, 20) != kPrefixRecordBytes) {
        throw std::runtime_error("invalid prefix file header");
    }
    const auto count = read_u64(header, 24);
    for (std::size_t offset = 32; offset < header.size(); ++offset) {
        if (header.at(offset) != 0) {
            throw std::runtime_error("nonzero prefix header padding");
        }
    }
    std::vector<PrefixReplayRecord> result;
    result.reserve(static_cast<std::size_t>(count));
    for (std::uint64_t index = 0; index < count; ++index) {
        const auto raw = read_exact(input, kPrefixRecordBytes);
        if (raw.size() != kPrefixRecordBytes ||
            read_u32(raw, 64) != crc32(raw.data(), 64)) {
            throw std::runtime_error("invalid prefix record CRC/length");
        }
        for (std::size_t offset = 68; offset < raw.size(); ++offset) {
            if (raw.at(offset) != 0) {
                throw std::runtime_error("nonzero prefix record padding");
            }
        }
        if (raw.at(12) > 1 || raw.at(13) != 0 ||
            raw.at(14) != 0 || raw.at(15) != 0) {
            throw std::runtime_error("invalid prefix record flags");
        }
        result.push_back(
            {read_u64(raw, 0), read_u32(raw, 8), raw.at(12) == 1,
             read_f64(raw, 16), read_f64(raw, 24),
             read_f64(raw, 32), read_f64(raw, 40),
             read_f64(raw, 48), read_f64(raw, 56)}
        );
    }
    if (input.peek() != std::char_traits<char>::eof()) {
        throw std::runtime_error("prefix file has trailing records");
    }
    return result;
}

void write_replay_summary_header(std::ostream& output) {
    output
        << "sample_id,ensemble,chain,bin,sweep,"
           "sign_d_ii,logabs_d_ii,sign_d_ti,logabs_d_ti,"
           "sign_d_alf_ii,logabs_d_alf_ii,"
           "sign_d_alf_ti,logabs_d_alf_ti,"
           "boundary_cut_log_ratio_ii,boundary_cut_log_ratio_ti,"
           "alive,first_rejection_kind,first_rejection_slice,"
           "first_rejection_site,log_q_prop,log_w_ratio,log_w_stock,"
           "log_w_phys,s_ref,identity_log_residual,min_selected_q,"
           "min_selected_q_slice,min_selected_q_site,min_halfk_ratio,"
           "min_halfk_slice,min_halfk_kind,min_normalized_overlap,"
           "min_sigma,min_principal_angle,central_ii_ekin,"
           "central_ii_epot,central_ii_etot,central_ti_ekin,"
           "central_ti_epot,central_ti_etot,endpoint_i_etot,"
           "endpoint_t_etot,alf_frozen_etot,alf_endpoint_etot\n";
}

void write_replay_summary_row(
    std::ostream& output,
    const ArchiveHeader& header,
    const ArchiveReplayResult& result
) {
    const auto none = std::numeric_limits<std::size_t>::max();
    const auto& path = result.path;
    output << std::setprecision(17)
           << result.source.sample_id << ','
           << (header.ensemble_code == 1 ? "II" : "TI") << ','
           << result.source.chain_id << ',' << result.source.bin_id << ','
           << result.source.sweep_id << ',' << result.physical.d_ii.sign
           << ',' << result.physical.d_ii.log_abs << ','
           << result.physical.d_ti.sign << ','
           << result.physical.d_ti.log_abs << ','
           << result.physical.alf_d_ii.sign << ','
           << result.physical.alf_d_ii.log_abs << ','
           << result.physical.alf_d_ti.sign << ','
           << result.physical.alf_d_ti.log_abs << ','
           << result.physical.d_ii.log_abs
                  - result.physical.alf_d_ii.log_abs << ','
           << result.physical.d_ti.log_abs
                  - result.physical.alf_d_ti.log_abs << ','
           << (path.alive ? 1 : 0) << ','
           << rejection_name(path.first_rejection_kind) << ',';
    if (path.first_rejection_slice != none) {
        output << path.first_rejection_slice;
    }
    output << ',';
    if (path.first_rejection_site != none) {
        output << path.first_rejection_site;
    }
    output << ',' << path.log_q_prop << ',' << path.log_w_ratio << ','
           << result.log_w_stock << ',' << result.log_w_phys << ','
           << result.s_ref << ',' << result.identity_log_residual << ','
           << path.min_selected_q << ','
           << result.min_selected_q_slice << ','
           << result.min_selected_q_site << ','
           << path.min_halfk_ratio << ',' << result.min_halfk_slice << ','
           << step_name(result.min_halfk_kind) << ','
           << result.min_normalized_overlap << ',' << result.min_sigma
           << ',' << result.max_principal_angle << ','
           << result.physical.central_ii.kinetic << ','
           << result.physical.central_ii.interaction << ','
           << result.physical.central_ii.total << ','
           << result.physical.central_ti.kinetic << ','
           << result.physical.central_ti.interaction << ','
           << result.physical.central_ti.total << ','
           << result.physical.endpoint_i.total << ','
           << result.physical.endpoint_t.total << ','
           << result.source.central_etot << ','
           << result.source.endpoint_etot << '\n';
}

}  // namespace audit
