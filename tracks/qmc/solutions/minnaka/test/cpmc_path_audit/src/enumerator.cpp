#include "enumerator.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace audit {

namespace {

PathFileHeader make_header(const PathEvaluator& evaluator,
                           const EnumerationOptions& options,
                           std::uint64_t records) {
    const auto& model = evaluator.model();
    PathFileHeader header;
    header.lx = static_cast<std::uint32_t>(model.lx());
    header.ly = static_cast<std::uint32_t>(model.ly());
    header.n_up = static_cast<std::uint32_t>(model.n_up());
    header.n_down = static_cast<std::uint32_t>(model.n_down());
    header.slices = static_cast<std::uint32_t>(options.slices);
    header.trial = options.trial_code;
    header.proposal = options.proposal_code;
    header.site_order = options.site_order_code;
    header.hopping = model.hopping();
    header.interaction = model.u();
    header.dt = model.dt();
    header.expected_records = records;
    return header;
}

PathRecord make_record(std::uint64_t config_id, std::size_t field_count,
                       const PathSummary& summary,
                       const LinearBottleneck& bottleneck) {
    PathRecord record;
    record.config_id = config_id;
    const double final_overlap = summary.final_overlap;
    if (final_overlap != 0.0) {
        record.sign_d = final_overlap > 0.0 ? +1 : -1;
        record.log_abs_d =
            -static_cast<double>(field_count) * std::log(2.0) +
            summary.log_common_factor + std::log(std::abs(final_overlap));
    }
    record.log_q = summary.log_q_prop;
    record.log_abs_weight = summary.log_w_ratio;
    record.min_log_abs_weight = summary.min_log_weight;
    record.min_abs_overlap = summary.min_abs_overlap;
    record.argmin_weight_step =
        static_cast<std::uint32_t>(summary.argmin_weight_step);
    record.first_rejected_step =
        summary.first_rejected_step ==
                std::numeric_limits<std::size_t>::max()
            ? no_rejection_step
            : static_cast<std::uint32_t>(summary.first_rejected_step);
    record.alive = summary.alive;
    record.linear_bottleneck = bottleneck.depth;
    record.argmin_linear_slice =
        static_cast<std::uint8_t>(bottleneck.slice);
    return record;
}

LinearBottleneck linear_bottleneck(const double* values,
                                   std::size_t count) {
    LinearBottleneck result;
    if (count < 2 || !std::isfinite(values[count - 1U])) {
        return result;
    }
    const double final = values[count - 1U];
    const double intervals = static_cast<double>(count - 1U);
    double minimum_residual = 0.0;
    for (std::size_t slice = 1; slice + 1U < count; ++slice) {
        if (!std::isfinite(values[slice])) {
            continue;
        }
        const double residual =
            values[slice] -
            static_cast<double>(slice) / intervals * final;
        if (residual < minimum_residual) {
            minimum_residual = residual;
            result.slice = slice;
        }
    }
    result.depth = -minimum_residual;
    return result;
}

}  // namespace

LinearBottleneck linear_bottleneck(
    const std::vector<double>& slice_log_weights) {
    return linear_bottleneck(slice_log_weights.data(),
                             slice_log_weights.size());
}

EnumerationResult enumerate_paths(const PathEvaluator& evaluator,
                                  const EnumerationOptions& options) {
    if (options.slices == 0) {
        throw std::invalid_argument("enumeration needs at least one slice");
    }
    if (options.output_path.empty()) {
        throw std::invalid_argument("enumeration output path is empty");
    }
    const std::size_t field_count =
        options.slices * evaluator.model().sites();
    if (field_count >= 63) {
        throw std::invalid_argument(
            "exhaustive enumeration supports fewer than 63 fields");
    }
    const std::uint64_t total = std::uint64_t{1} << field_count;
    PathRecordWriter writer(options.output_path,
                            make_header(evaluator, options, total));
    EnumerationResult result;
    const auto begin = std::chrono::steady_clock::now();
    const std::uint64_t progress_interval =
        options.progress_updates == 0
            ? total + 1
            : std::max<std::uint64_t>(
                  1, total /
                         static_cast<std::uint64_t>(options.progress_updates));

    std::array<double, 64> slice_log_weights{};
    const auto visit =
        [&](auto&& self, const EvaluationState& state, std::size_t slice,
            std::uint64_t config_id) -> void {
        if (slice < options.slices) {
            const auto children = evaluator.advance_all_slice_fields(
                state, slice, true, false);
            for (std::size_t mask = 0; mask < children.size(); ++mask) {
                slice_log_weights.at(slice + 1U) =
                    children.at(mask).summary.log_w_ratio;
                self(self, children.at(mask), slice + 1U,
                     (config_id << evaluator.model().sites()) |
                         static_cast<std::uint64_t>(mask));
            }
            return;
        }

        const auto summary = evaluator.finish(state);
        const auto bottleneck = linear_bottleneck(
            slice_log_weights.data(), options.slices + 1U);
        const auto record =
            make_record(config_id, field_count, summary, bottleneck);
        writer.write(record);

        if (record.sign_d != 0) {
            const double absolute_d = std::exp(record.log_abs_d);
            result.absolute_sum_d += absolute_d;
            result.signed_sum_d +=
                static_cast<double>(record.sign_d) * absolute_d;
            if (record.sign_d < 0) {
                ++result.negative_records;
            }
            if (record.alive) {
                result.alive_absolute_sum_d += absolute_d;
            }
        }
        if (record.alive) {
            ++result.alive_records;
            const double lhs =
                record.log_q + record.log_abs_weight +
                summary.log_common_factor +
                std::log(std::abs(summary.initial_overlap));
            result.max_alive_identity_residual =
                std::max(result.max_alive_identity_residual,
                         std::abs(lhs - record.log_abs_d));
        }
        ++result.records;

        if ((result.records % progress_interval) == 0 ||
            result.records == total) {
            const auto now = std::chrono::steady_clock::now();
            const double elapsed =
                std::chrono::duration<double>(now - begin).count();
            std::cout << "progress " << result.records << '/' << total
                      << " paths, "
                      << static_cast<double>(result.records) /
                             std::max(elapsed, 1.0e-12)
                      << " paths/s\n"
                      << std::flush;
            writer.flush();
        }
    };
    const auto initial = evaluator.initial_state();
    slice_log_weights.at(0) = initial.summary.log_w_ratio;
    visit(visit, initial, 0, 0);
    writer.close();
    const auto end = std::chrono::steady_clock::now();
    result.elapsed_seconds =
        std::chrono::duration<double>(end - begin).count();
    result.paths_per_second =
        static_cast<double>(result.records) /
        std::max(result.elapsed_seconds, 1.0e-12);
    return result;
}

}  // namespace audit
