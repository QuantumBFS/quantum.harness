#pragma once

#include "path_evaluator.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace audit {

PathSummary replay_fields(const PathEvaluator& evaluator,
                          const std::vector<int>& fields,
                          std::size_t slices, bool clip,
                          const std::string& trace_csv);
PathSummary replay_config(const PathEvaluator& evaluator,
                          std::uint64_t config_id, std::size_t slices,
                          bool clip, const std::string& trace_csv);
std::vector<int> read_text_fields(const std::string& path);

}  // namespace audit
