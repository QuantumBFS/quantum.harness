#include "archive_reader.hpp"

#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace audit {
namespace {

constexpr std::size_t kHeaderBytes = 256;
constexpr std::size_t kRecordPrefixBytes = 108;

std::uint32_t u32(const std::vector<unsigned char>& raw, std::size_t offset) {
    if (offset + 4 > raw.size()) {
        throw std::runtime_error("truncated archive integer");
    }
    return static_cast<std::uint32_t>(raw[offset]) |
           (static_cast<std::uint32_t>(raw[offset + 1]) << 8U) |
           (static_cast<std::uint32_t>(raw[offset + 2]) << 16U) |
           (static_cast<std::uint32_t>(raw[offset + 3]) << 24U);
}

std::uint16_t u16(const std::vector<unsigned char>& raw, std::size_t offset) {
    if (offset + 2 > raw.size()) {
        throw std::runtime_error("truncated archive integer");
    }
    return static_cast<std::uint16_t>(raw[offset]) |
           static_cast<std::uint16_t>(
               static_cast<std::uint16_t>(raw[offset + 1]) << 8U
           );
}

std::uint64_t u64(const std::vector<unsigned char>& raw, std::size_t offset) {
    if (offset + 8 > raw.size()) {
        throw std::runtime_error("truncated archive integer");
    }
    std::uint64_t value = 0;
    for (std::size_t index = 0; index < 8; ++index) {
        value |= static_cast<std::uint64_t>(raw[offset + index])
                 << (8U * index);
    }
    return value;
}

double f64(const std::vector<unsigned char>& raw, std::size_t offset) {
    const auto bits = u64(raw, offset);
    double value = 0.0;
    static_assert(sizeof(value) == sizeof(bits), "unexpected double size");
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
    std::ifstream& stream, std::size_t count
) {
    std::vector<unsigned char> raw(count);
    stream.read(
        reinterpret_cast<char*>(raw.data()),
        static_cast<std::streamsize>(raw.size())
    );
    raw.resize(static_cast<std::size_t>(stream.gcount()));
    return raw;
}

}  // namespace

ArchiveReader::ArchiveReader(const std::string& path) : stream_(path, std::ios::binary) {
    if (!stream_) {
        throw std::runtime_error("cannot open path archive: " + path);
    }
    const auto raw = read_exact(stream_, kHeaderBytes);
    if (raw.size() != kHeaderBytes ||
        std::string(raw.begin(), raw.begin() + 8) != "QHPATH01") {
        throw std::runtime_error("invalid path archive header");
    }
    header_.version = u32(raw, 8);
    if (header_.version != 1 || u32(raw, 12) != 0x01020304U ||
        u32(raw, 16) != kHeaderBytes) {
        throw std::runtime_error("unsupported path archive format");
    }
    header_.record_bytes = u32(raw, 20);
    header_.lx = u32(raw, 24);
    header_.ly = u32(raw, 28);
    header_.n_up = u32(raw, 32);
    header_.n_down = u32(raw, 36);
    header_.ltrot = u32(raw, 40);
    header_.nsites = u32(raw, 44);
    header_.nfield = u32(raw, 48);
    header_.payload_bytes = u32(raw, 52);
    header_.hopping = f64(raw, 56);
    header_.interaction = f64(raw, 64);
    header_.dt = f64(raw, 72);
    header_.beta = f64(raw, 80);
    header_.theta = f64(raw, 88);
    header_.ensemble_code = raw[96];
    if (raw[97] != 1 || raw[98] != 1 || raw[99] != 0) {
        throw std::runtime_error("unsupported path field ordering");
    }
    header_.selected_projection_sha256 =
        std::string(raw.begin() + 100, raw.begin() + 164);
    header_.trial_manifest_sha256 =
        std::string(raw.begin() + 164, raw.begin() + 228);
    const std::uint32_t expected_payload = (header_.nfield + 7U) / 8U;
    const std::uint32_t expected_record =
        ((112U + expected_payload + 63U) / 64U) * 64U;
    if (header_.nsites != header_.lx * header_.ly ||
        header_.nfield != header_.ltrot * header_.nsites ||
        header_.payload_bytes != expected_payload ||
        header_.record_bytes != expected_record) {
        throw std::runtime_error("inconsistent path archive dimensions");
    }
    for (std::size_t offset = 228; offset < raw.size(); ++offset) {
        if (raw[offset] != 0) {
            throw std::runtime_error("nonzero path archive header padding");
        }
    }
}

bool ArchiveReader::read(ArchiveRecordView& record) {
    const auto raw = read_exact(stream_, header_.record_bytes);
    if (raw.empty()) {
        return false;
    }
    if (raw.size() != header_.record_bytes) {
        truncated_tail_ = true;
        return false;
    }
    const std::size_t payload_end =
        kRecordPrefixBytes + header_.payload_bytes;
    if (u32(raw, payload_end) != crc32(raw.data(), payload_end)) {
        throw std::runtime_error("path archive record CRC mismatch");
    }
    for (std::size_t offset = payload_end + 4; offset < raw.size(); ++offset) {
        if (raw[offset] != 0) {
            throw std::runtime_error("nonzero path archive record padding");
        }
    }
    if (u32(raw, 24) != header_.ltrot ||
        u32(raw, 28) != header_.nfield) {
        throw std::runtime_error("path archive record/header mismatch");
    }
    record.sample_id = u64(raw, 0);
    record.chain_id = u32(raw, 8);
    record.bin_id = u32(raw, 12);
    record.sweep_id = u64(raw, 16);
    record.frozen_sign = static_cast<std::int8_t>(raw[32]);
    if (raw[33] > 1) {
        throw std::runtime_error("invalid archive endpoint flag");
    }
    record.endpoint_present = raw[33] == 1;
    record.flags = u16(raw, 34);
    record.central_ekin = f64(raw, 36);
    record.central_epot = f64(raw, 44);
    record.central_etot = f64(raw, 52);
    record.central_npart = f64(raw, 60);
    record.endpoint_sign = static_cast<std::int8_t>(raw[68]);
    record.endpoint_logabs_d = f64(raw, 76);
    record.endpoint_ekin = f64(raw, 84);
    record.endpoint_epot = f64(raw, 92);
    record.endpoint_etot = f64(raw, 100);
    if (!record.endpoint_present &&
        !(std::isnan(record.endpoint_logabs_d) &&
          std::isnan(record.endpoint_ekin) &&
          std::isnan(record.endpoint_epot) &&
          std::isnan(record.endpoint_etot))) {
        throw std::runtime_error(
            "absent archive endpoint does not use canonical NaNs"
        );
    }
    record.fields.clear();
    record.fields.reserve(header_.nfield);
    for (std::uint32_t index = 0; index < header_.nfield; ++index) {
        const bool plus =
            (raw[kRecordPrefixBytes + index / 8U] &
             (1U << (index % 8U))) != 0;
        record.fields.push_back(plus ? 1 : -1);
    }
    return true;
}

}  // namespace audit
