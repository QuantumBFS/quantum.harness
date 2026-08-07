#include "archive_replay.hpp"

#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

void require_close(double actual, double expected, double tolerance,
                   const std::string& message) {
    if (std::abs(actual - expected) > tolerance) {
        throw std::runtime_error(message);
    }
}

}  // namespace

int main() {
    const auto model = audit::HubbardModel::square_periodic(
        2, 2, 1.0, 4.0, 0.05, 2, 2);
    const auto initial = audit::TrialState::rhf_x(model);
    const auto guide = audit::TrialState::solve_uhf(model, 4.0);

    audit::ArchiveHeader header;
    header.lx = 2;
    header.ly = 2;
    header.n_up = 2;
    header.n_down = 2;
    header.ltrot = 2;
    header.nsites = 4;
    header.nfield = 8;
    header.hopping = 1.0;
    header.interaction = 4.0;
    header.dt = 0.05;
    header.ensemble_code = 2;

    audit::ArchiveRecordView record;
    record.sample_id = 23;
    record.chain_id = 3;
    record.bin_id = 4;
    record.sweep_id = 17;
    record.fields = {+1, -1, -1, +1, -1, +1, +1, -1};
    const auto result = audit::replay_archive_record(
        header, record, model, initial, guide, {1, 0, 3, 2},
        1, 1, -2.0);

    require(result.prefixes.size() == 2, "one prefix per slice");
    require(result.prefixes.front().sample_id == 23,
            "prefix sample id");
    require(result.prefixes.front().slice == 0 &&
                result.prefixes.back().slice == 1,
            "prefix slice order");
    require_close(result.s_ref, -0.2, 1.0e-14, "reference action");
    require_close(
        result.log_w_stock - result.log_w_phys,
        result.s_ref, 1.0e-13, "stock/physical weight separation");
    if (result.path.alive) {
        require(result.identity_log_residual < 1.0e-10,
                "alive absolute weight identity");
    }

    const std::string prefix_path = "build/test_prefix.qhpfx";
    audit::write_prefix_file(prefix_path, result.prefixes);
    const auto roundtrip = audit::read_prefix_file(prefix_path);
    require(roundtrip.size() == result.prefixes.size(),
            "prefix round-trip record count");
    for (std::size_t index = 0; index < roundtrip.size(); ++index) {
        require(roundtrip.at(index).sample_id ==
                    result.prefixes.at(index).sample_id,
                "prefix round-trip sample id");
        require_close(
            roundtrip.at(index).log_q,
            result.prefixes.at(index).log_q, 0.0,
            "prefix round-trip logQ");
    }
    std::remove(prefix_path.c_str());

    header.ltrot = 820;
    header.nfield = header.ltrot * header.nsites;
    record.fields.resize(header.nfield);
    for (std::size_t index = 0; index < record.fields.size(); ++index) {
        record.fields.at(index) = index % 3 == 0 ? +1 : -1;
    }
    const auto long_result = audit::replay_archive_record(
        header, record, model, initial, guide, {1, 0, 3, 2},
        410, 5, -2.0);
    require(long_result.prefixes.size() == 820,
            "long path prefix count");
    require(std::isfinite(long_result.log_w_phys) ||
                !long_result.path.alive,
            "long path stable physical log weight");
    if (long_result.path.alive) {
        require(long_result.identity_log_residual < 1.0e-8,
                "long path stable absolute identity");
    }

    std::cout << "PASS\n";
    return 0;
}
