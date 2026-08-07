#include "archive_reader.hpp"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void put_u32(std::vector<unsigned char>& raw, std::size_t offset,
             std::uint32_t value) {
    for (std::size_t index = 0; index < 4; ++index) {
        raw[offset + index] =
            static_cast<unsigned char>((value >> (8U * index)) & 0xffU);
    }
}

void put_u64(std::vector<unsigned char>& raw, std::size_t offset,
             std::uint64_t value) {
    for (std::size_t index = 0; index < 8; ++index) {
        raw[offset + index] =
            static_cast<unsigned char>((value >> (8U * index)) & 0xffU);
    }
}

void put_f64(std::vector<unsigned char>& raw, std::size_t offset,
             double value) {
    std::uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    put_u64(raw, offset, bits);
}

std::uint32_t crc32(const unsigned char* data, std::size_t size) {
    std::uint32_t crc = 0xffffffffU;
    for (std::size_t index = 0; index < size; ++index) {
        crc ^= data[index];
        for (int bit = 0; bit < 8; ++bit) {
            const auto mask = 0U - static_cast<std::uint32_t>(crc & 1U);
            crc = (crc >> 1U) ^ (0xedb88320U & mask);
        }
    }
    return ~crc;
}

void expect(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

}  // namespace

int main() {
    try {
        constexpr std::size_t header_bytes = 256;
        constexpr std::size_t record_bytes = 128;
        std::vector<unsigned char> raw(header_bytes + record_bytes, 0);
        std::memcpy(raw.data(), "QHPATH01", 8);
        put_u32(raw, 8, 1);
        put_u32(raw, 12, 0x01020304U);
        put_u32(raw, 16, header_bytes);
        put_u32(raw, 20, record_bytes);
        put_u32(raw, 24, 2);
        put_u32(raw, 28, 1);
        put_u32(raw, 32, 1);
        put_u32(raw, 36, 1);
        put_u32(raw, 40, 2);
        put_u32(raw, 44, 2);
        put_u32(raw, 48, 4);
        put_u32(raw, 52, 1);
        put_f64(raw, 56, 1.0);
        put_f64(raw, 64, 4.0);
        put_f64(raw, 72, 0.05);
        put_f64(raw, 80, 0.1);
        put_f64(raw, 88, 0.0);
        raw[96] = 2;
        raw[97] = 1;
        raw[98] = 1;
        std::memset(raw.data() + 100, '1', 64);
        std::memset(raw.data() + 164, '2', 64);

        const std::size_t base = header_bytes;
        put_u64(raw, base, (2ULL << 60U) | (3ULL << 56U) | 9ULL);
        put_u32(raw, base + 8, 3);
        put_u32(raw, base + 12, 4);
        put_u64(raw, base + 16, 17);
        put_u32(raw, base + 24, 2);
        put_u32(raw, base + 28, 4);
        raw[base + 32] = 1;
        raw[base + 33] = 1;
        put_f64(raw, base + 36, -2.0);
        put_f64(raw, base + 44, 0.5);
        put_f64(raw, base + 52, -1.5);
        put_f64(raw, base + 60, 2.0);
        raw[base + 68] = 1;
        put_f64(raw, base + 76, -7.0);
        put_f64(raw, base + 84, -1.9);
        put_f64(raw, base + 92, 0.4);
        put_f64(raw, base + 100, -1.5);
        raw[base + 108] = 0x06;
        put_u32(raw, base + 109, crc32(raw.data() + base, 109));

        const std::string path = "build/test_archive_reader.bin";
        {
            std::ofstream output(path, std::ios::binary);
            output.write(
                reinterpret_cast<const char*>(raw.data()),
                static_cast<std::streamsize>(raw.size())
            );
        }
        audit::ArchiveReader reader(path);
        expect(reader.header().ltrot == 2, "wrong header Ltrot");
        expect(reader.header().ensemble_code == 2, "wrong ensemble");
        audit::ArchiveRecordView record;
        expect(reader.read(record), "missing golden record");
        expect(record.chain_id == 3 && record.sweep_id == 17,
               "wrong record identifiers");
        expect(record.endpoint_present && record.flags == 0,
               "wrong endpoint flags");
        expect(record.fields == std::vector<int>({-1, 1, 1, -1}),
               "wrong LSB field decoding");
        expect(std::abs(record.endpoint_logabs_d + 7.0) < 1.0e-15,
               "wrong endpoint log determinant");
        expect(!reader.read(record), "unexpected second record");
        expect(!reader.truncated_tail(), "false truncated tail");
        std::cout << "PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
