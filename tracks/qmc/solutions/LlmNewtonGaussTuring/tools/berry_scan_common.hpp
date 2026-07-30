#pragma once

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace cm::scan {

inline std::vector<double> uniform_axis(double minimum, double maximum,
                                        double step, const char* label) {
    if (!std::isfinite(minimum) || !std::isfinite(maximum)
        || !std::isfinite(step) || !(step > 0.0) || !(maximum > minimum))
        throw std::invalid_argument(
            std::string(label) + ": require finite increasing bounds and a finite positive step");

    const double span = maximum - minimum;
    if (!std::isfinite(span))
        throw std::invalid_argument(std::string(label) + ": range is not finite");
    const double quotient = span / step;
    const double nearest = std::round(quotient);
    const double endpoint_scale = std::max({
        1.0, std::abs(quotient), std::abs(minimum / step),
        std::abs(maximum / step),
    });
    const double rounding_tolerance = std::min(
        0.25, 64.0 * std::numeric_limits<double>::epsilon() * endpoint_scale);
    const bool endpoint_reached = std::abs(quotient - nearest) <= rounding_tolerance;
    const double interval_count = endpoint_reached ? nearest : std::floor(quotient);
    if (!(interval_count >= 1.0))
        throw std::invalid_argument(std::string(label) + ": range must span at least one step");
    if (interval_count > static_cast<double>(std::numeric_limits<int>::max() - 1))
        throw std::length_error(std::string(label) + ": grid has too many points");

    const auto intervals = static_cast<std::size_t>(interval_count);
    std::vector<double> axis(intervals + 1);
    for (std::size_t index = 0; index <= intervals; ++index)
        axis[index] = minimum + static_cast<double>(index) * step;
    if (endpoint_reached) axis.back() = maximum;
    return axis;
}

} // namespace cm::scan
