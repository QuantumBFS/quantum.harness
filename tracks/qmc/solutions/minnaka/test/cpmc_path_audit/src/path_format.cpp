#include "path_format.hpp"

#include <array>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <type_traits>

namespace audit {

namespace {

constexpr std::array<char, 8> magic{'C', 'P', 'A', 'U', 'D', 'I', 'T', '\0'};
constexpr std::uint32_t current_format_version = 2;
constexpr std::uint32_t header_bytes = 128;
constexpr std::uint32_t record_bytes = 64;
constexpr std::uint32_t endian_marker = 0x01020304U;

template <class Stream, class T>
void write_scalar(Stream& stream, const T& value) {
    static_assert(std::is_trivially_copyable_v<T>);
    stream.write(reinterpret_cast<const char*>(&value),
                 static_cast<std::streamsize>(sizeof(T)));
    if (!stream) {
        throw std::runtime_error("failed to write path file");
    }
}

template <class Stream, class T>
T read_scalar(Stream& stream) {
    static_assert(std::is_trivially_copyable_v<T>);
    T value{};
    stream.read(reinterpret_cast<char*>(&value),
                static_cast<std::streamsize>(sizeof(T)));
    if (!stream) {
        throw std::runtime_error("truncated path file");
    }
    return value;
}

void write_zeros(std::ostream& stream, std::size_t count) {
    const std::array<char, 32> zeros{};
    while (count > 0) {
        const std::size_t chunk = std::min(count, zeros.size());
        stream.write(zeros.data(), static_cast<std::streamsize>(chunk));
        if (!stream) {
            throw std::runtime_error("failed to write path file padding");
        }
        count -= chunk;
    }
}

void require_equal(bool condition, const char* field) {
    if (!condition) {
        throw std::invalid_argument(std::string("path metadata mismatch: ") +
                                    field);
    }
}

void write_header_fields(std::ostream& stream,
                         const PathFileHeader& header) {
    stream.write(magic.data(), static_cast<std::streamsize>(magic.size()));
    write_scalar(stream, current_format_version);
    write_scalar(stream, header_bytes);
    write_scalar(stream, record_bytes);
    write_scalar(stream, endian_marker);
    write_scalar(stream, header.lx);
    write_scalar(stream, header.ly);
    write_scalar(stream, header.n_up);
    write_scalar(stream, header.n_down);
    write_scalar(stream, header.slices);
    write_scalar(stream, static_cast<std::uint32_t>(header.trial));
    write_scalar(stream, static_cast<std::uint32_t>(header.proposal));
    write_scalar(stream, static_cast<std::uint32_t>(header.site_order));
    write_scalar(stream, header.hopping);
    write_scalar(stream, header.interaction);
    write_scalar(stream, header.dt);
    write_scalar(stream, header.expected_records);
    write_scalar(stream, header.actual_records);
    write_zeros(stream, header_bytes - 96U);
}

PathFileHeader read_header_fields(std::istream& stream) {
    std::array<char, magic.size()> actual_magic{};
    stream.read(actual_magic.data(),
                static_cast<std::streamsize>(actual_magic.size()));
    if (!stream || actual_magic != magic) {
        throw std::runtime_error("invalid path file magic");
    }
    const auto version = read_scalar<std::istream, std::uint32_t>(stream);
    const auto actual_header_bytes =
        read_scalar<std::istream, std::uint32_t>(stream);
    const auto actual_record_bytes =
        read_scalar<std::istream, std::uint32_t>(stream);
    const auto actual_endian =
        read_scalar<std::istream, std::uint32_t>(stream);
    if ((version != 1U && version != current_format_version) ||
        actual_header_bytes != header_bytes ||
        actual_record_bytes != record_bytes || actual_endian != endian_marker) {
        throw std::runtime_error("unsupported path file format");
    }

    PathFileHeader header;
    header.format_version = version;
    header.lx = read_scalar<std::istream, std::uint32_t>(stream);
    header.ly = read_scalar<std::istream, std::uint32_t>(stream);
    header.n_up = read_scalar<std::istream, std::uint32_t>(stream);
    header.n_down = read_scalar<std::istream, std::uint32_t>(stream);
    header.slices = read_scalar<std::istream, std::uint32_t>(stream);
    header.trial = static_cast<TrialCode>(
        read_scalar<std::istream, std::uint32_t>(stream));
    header.proposal = static_cast<ProposalCode>(
        read_scalar<std::istream, std::uint32_t>(stream));
    header.site_order = static_cast<SiteOrderCode>(
        read_scalar<std::istream, std::uint32_t>(stream));
    header.hopping = read_scalar<std::istream, double>(stream);
    header.interaction = read_scalar<std::istream, double>(stream);
    header.dt = read_scalar<std::istream, double>(stream);
    header.expected_records =
        read_scalar<std::istream, std::uint64_t>(stream);
    header.actual_records =
        read_scalar<std::istream, std::uint64_t>(stream);
    stream.seekg(static_cast<std::streamoff>(header_bytes), std::ios::beg);
    if (!stream) {
        throw std::runtime_error("truncated path file header");
    }
    return header;
}

}  // namespace

std::uint64_t encode_fields(const std::vector<int>& fields) {
    if (fields.size() > 64) {
        throw std::invalid_argument("config ID supports at most 64 fields");
    }
    std::uint64_t result = 0;
    for (std::size_t index = 0; index < fields.size(); ++index) {
        if (fields.at(index) == +1) {
            result |= std::uint64_t{1}
                      << (fields.size() - 1U - index);
        } else if (fields.at(index) != -1) {
            throw std::invalid_argument("field value must be -1 or +1");
        }
    }
    return result;
}

std::vector<int> decode_fields(std::uint64_t config_id,
                               std::size_t field_count) {
    if (field_count > 64) {
        throw std::invalid_argument("config ID supports at most 64 fields");
    }
    std::vector<int> fields(field_count, -1);
    for (std::size_t index = 0; index < field_count; ++index) {
        const std::size_t bit = field_count - 1U - index;
        if (((config_id >> bit) & std::uint64_t{1}) != 0U) {
            fields.at(index) = +1;
        }
    }
    return fields;
}

void validate_compatible(const PathFileHeader& expected,
                         const PathFileHeader& actual) {
    require_equal(expected.lx == actual.lx, "lx");
    require_equal(expected.ly == actual.ly, "ly");
    require_equal(expected.n_up == actual.n_up, "n_up");
    require_equal(expected.n_down == actual.n_down, "n_down");
    require_equal(expected.slices == actual.slices, "slices");
    require_equal(expected.trial == actual.trial, "trial");
    require_equal(expected.proposal == actual.proposal, "proposal");
    require_equal(expected.site_order == actual.site_order, "site_order");
    require_equal(expected.hopping == actual.hopping, "hopping");
    require_equal(expected.interaction == actual.interaction, "interaction");
    require_equal(expected.dt == actual.dt, "dt");
}

PathRecordWriter::PathRecordWriter(const std::string& path,
                                   PathFileHeader header)
    : stream_(path, std::ios::in | std::ios::out | std::ios::binary |
                       std::ios::trunc),
      header_(header) {
    if (!stream_) {
        throw std::runtime_error("cannot open path output: " + path);
    }
    header_.actual_records = 0;
    write_header();
}

PathRecordWriter::~PathRecordWriter() {
    if (!closed_) {
        try {
            close();
        } catch (...) {
        }
    }
}

void PathRecordWriter::write_header() {
    stream_.seekp(0, std::ios::beg);
    write_header_fields(stream_, header_);
    stream_.seekp(0, std::ios::end);
}

void PathRecordWriter::write(const PathRecord& record) {
    if (closed_) {
        throw std::runtime_error("cannot write a closed path file");
    }
    write_scalar(stream_, record.config_id);
    write_scalar(stream_, record.log_abs_d);
    write_scalar(stream_, record.log_q);
    write_scalar(stream_, record.log_abs_weight);
    write_scalar(stream_, record.min_log_abs_weight);
    write_scalar(stream_, record.min_abs_overlap);
    write_scalar(stream_, record.argmin_weight_step);
    write_scalar(stream_, record.first_rejected_step);
    write_scalar(stream_, record.sign_d);
    write_scalar(stream_, static_cast<std::uint8_t>(record.alive ? 1U : 0U));
    write_scalar(stream_, static_cast<float>(record.linear_bottleneck));
    write_scalar(stream_, record.argmin_linear_slice);
    write_scalar(stream_, std::uint8_t{0});
    ++header_.actual_records;
}

void PathRecordWriter::flush() {
    write_header();
    stream_.flush();
    if (!stream_) {
        throw std::runtime_error("failed to flush path output");
    }
}

void PathRecordWriter::close() {
    if (closed_) {
        return;
    }
    write_header();
    stream_.flush();
    if (!stream_) {
        throw std::runtime_error("failed to finalize path output");
    }
    stream_.close();
    closed_ = true;
}

PathRecordReader::PathRecordReader(const std::string& path)
    : stream_(path, std::ios::binary) {
    if (!stream_) {
        throw std::runtime_error("cannot open path input: " + path);
    }
    header_ = read_header_fields(stream_);
}

bool PathRecordReader::read(PathRecord& record) {
    if (records_read_ >= header_.actual_records) {
        return false;
    }
    record.config_id = read_scalar<std::ifstream, std::uint64_t>(stream_);
    record.log_abs_d = read_scalar<std::ifstream, double>(stream_);
    record.log_q = read_scalar<std::ifstream, double>(stream_);
    record.log_abs_weight = read_scalar<std::ifstream, double>(stream_);
    record.min_log_abs_weight = read_scalar<std::ifstream, double>(stream_);
    record.min_abs_overlap = read_scalar<std::ifstream, double>(stream_);
    record.argmin_weight_step =
        read_scalar<std::ifstream, std::uint32_t>(stream_);
    record.first_rejected_step =
        read_scalar<std::ifstream, std::uint32_t>(stream_);
    record.sign_d = read_scalar<std::ifstream, std::int8_t>(stream_);
    record.alive =
        read_scalar<std::ifstream, std::uint8_t>(stream_) != 0U;
    record.linear_bottleneck =
        read_scalar<std::ifstream, float>(stream_);
    record.argmin_linear_slice =
        read_scalar<std::ifstream, std::uint8_t>(stream_);
    (void)read_scalar<std::ifstream, std::uint8_t>(stream_);
    if (!stream_) {
        throw std::runtime_error("truncated path record");
    }
    ++records_read_;
    return true;
}

}  // namespace audit
