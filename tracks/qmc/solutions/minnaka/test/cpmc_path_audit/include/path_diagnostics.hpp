#pragma once

#include "walker.hpp"

#include <cstddef>
#include <limits>

namespace audit {

struct SpinSubspaceDiagnostic {
    double sigma_min = std::numeric_limits<double>::quiet_NaN();
    double sigma_max = std::numeric_limits<double>::quiet_NaN();
    double principal_angle_min =
        std::numeric_limits<double>::quiet_NaN();
    double principal_angle_max =
        std::numeric_limits<double>::quiet_NaN();
    double condition_g = std::numeric_limits<double>::quiet_NaN();
    double log_abs_det_s = std::numeric_limits<double>::quiet_NaN();
    double log_abs_orbital_scale =
        std::numeric_limits<double>::quiet_NaN();
};

struct SubspaceDiagnostic {
    SpinSubspaceDiagnostic up;
    SpinSubspaceDiagnostic down;
    double log_abs_normalized_overlap =
        std::numeric_limits<double>::quiet_NaN();
    double log_abs_orbital_scale =
        std::numeric_limits<double>::quiet_NaN();
};

struct SiteRatioDiagnostic {
    double g_up = std::numeric_limits<double>::quiet_NaN();
    double g_down = std::numeric_limits<double>::quiet_NaN();
    double predicted_plus_ratio =
        std::numeric_limits<double>::quiet_NaN();
    double predicted_minus_ratio =
        std::numeric_limits<double>::quiet_NaN();
    double direct_plus_ratio = std::numeric_limits<double>::quiet_NaN();
    double direct_minus_ratio =
        std::numeric_limits<double>::quiet_NaN();
    double max_abs_residual =
        std::numeric_limits<double>::quiet_NaN();
    int predicted_low_overlap_field = 0;
};

SubspaceDiagnostic diagnose_subspace(const TrialState& trial,
                                     const Walker& walker);

SiteRatioDiagnostic diagnose_site_ratios(
    const HubbardModel& model, const TrialState& trial,
    const Walker& walker, std::size_t site);

}  // namespace audit
