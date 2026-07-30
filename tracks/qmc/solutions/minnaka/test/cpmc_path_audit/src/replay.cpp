#include "replay.hpp"

#include "path_format.hpp"

#include <fstream>
#include <iomanip>
#include <stdexcept>

namespace audit {

namespace {

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

void write_trace(const std::string& path, const PathSummary& summary) {
    if (path.empty()) {
        return;
    }
    std::ofstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot open trace output: " + path);
    }
    stream << "step,kind,slice,site,field,alive_before,alive_after,"
              "overlap_before,overlap_after,overlap_ratio,q_plus,q_minus,"
              "q_selected,weight_factor,cumulative_log_q,"
              "cumulative_log_weight\n";
    stream << std::setprecision(17);
    for (std::size_t step = 0; step < summary.trace.size(); ++step) {
        const auto& trace = summary.trace.at(step);
        stream << step << ',' << step_name(trace.kind) << ',' << trace.slice
               << ',';
        if (trace.site == std::numeric_limits<std::size_t>::max()) {
            stream << -1;
        } else {
            stream << trace.site;
        }
        stream << ',' << trace.selected_field << ','
               << static_cast<int>(trace.alive_before) << ','
               << static_cast<int>(trace.alive_after) << ','
               << trace.overlap_before << ',' << trace.overlap_after << ','
               << trace.overlap_ratio << ',' << trace.q_plus << ','
               << trace.q_minus << ',' << trace.q_selected << ','
               << trace.weight_factor << ',' << trace.cumulative_log_q
               << ',' << trace.cumulative_log_weight << '\n';
    }
    stream.flush();
    if (!stream) {
        throw std::runtime_error("failed to write trace output: " + path);
    }
}

}  // namespace

PathSummary replay_fields(const PathEvaluator& evaluator,
                          const std::vector<int>& fields,
                          std::size_t slices, bool clip,
                          const std::string& trace_csv) {
    const auto summary = evaluator.evaluate(fields, slices, clip);
    write_trace(trace_csv, summary);
    return summary;
}

PathSummary replay_config(const PathEvaluator& evaluator,
                          std::uint64_t config_id, std::size_t slices,
                          bool clip, const std::string& trace_csv) {
    const std::size_t field_count = slices * evaluator.model().sites();
    return replay_fields(evaluator, decode_fields(config_id, field_count),
                         slices, clip, trace_csv);
}

std::vector<int> read_text_fields(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot open field input: " + path);
    }
    std::vector<int> fields;
    int field = 0;
    while (stream >> field) {
        if (field != -1 && field != +1) {
            throw std::runtime_error(
                "text field input contains a value other than -1 or +1");
        }
        fields.push_back(field);
    }
    if (!stream.eof()) {
        throw std::runtime_error("failed to parse text field input");
    }
    return fields;
}

}  // namespace audit
