#include "path_diagnostics.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace audit {

namespace {

constexpr double negative_infinity =
    -std::numeric_limits<double>::infinity();

double log_abs_determinant(const Matrix& matrix) {
    const double value = determinant(matrix);
    return value == 0.0 ? negative_infinity : std::log(std::abs(value));
}

std::pair<double, double> singular_extrema(const Matrix& matrix) {
    const Matrix gram = multiply(transpose(matrix), matrix);
    const auto [eigenvalues, eigenvectors] = symmetric_eigh(gram);
    (void)eigenvectors;
    if (eigenvalues.empty()) {
        throw std::invalid_argument("singular spectrum is empty");
    }
    const double minimum =
        std::sqrt(std::max(eigenvalues.front(), 0.0));
    const double maximum =
        std::sqrt(std::max(eigenvalues.back(), 0.0));
    return {minimum, maximum};
}

SpinSubspaceDiagnostic diagnose_spin(const Matrix& trial,
                                     const Matrix& phi,
                                     double absorbed_log_scale) {
    const ThinQr qr = thin_qr(phi);
    const Matrix s = multiply(transpose(trial), qr.q);
    const auto [raw_sigma_min, raw_sigma_max] =
        singular_extrema(s);
    const double sigma_min = std::clamp(raw_sigma_min, 0.0, 1.0);
    const double sigma_max = std::clamp(raw_sigma_max, 0.0, 1.0);
    const Matrix g = multiply(transpose(trial), phi);
    const auto [g_min, g_max] = singular_extrema(g);

    SpinSubspaceDiagnostic result;
    result.sigma_min = sigma_min;
    result.sigma_max = sigma_max;
    result.principal_angle_min = std::acos(sigma_max);
    result.principal_angle_max = std::acos(sigma_min);
    result.condition_g =
        g_min == 0.0
            ? std::numeric_limits<double>::infinity()
            : g_max / g_min;
    result.log_abs_det_s = log_abs_determinant(s);
    result.log_abs_orbital_scale =
        absorbed_log_scale + log_abs_determinant(qr.r);
    return result;
}

double mixed_local_density(const Matrix& trial, const Matrix& phi,
                           std::size_t site) {
    const Matrix g = multiply(transpose(trial), phi);
    const Matrix mixed = multiply(
        multiply(phi, inverse(g)), transpose(trial));
    return mixed(site, site);
}

double predicted_spin_ratio(const HubbardModel& model,
                            bool spin_up, int field,
                            double local_density) {
    const double multiplier =
        model.hs_multiplier(spin_up, field);
    return 1.0 + (multiplier - 1.0) * local_density;
}

}  // namespace

SubspaceDiagnostic diagnose_subspace(const TrialState& trial,
                                     const Walker& walker) {
    SubspaceDiagnostic result;
    result.up = diagnose_spin(trial.up_orbitals(), walker.up(),
                              walker.up_log_abs_scale());
    result.down = diagnose_spin(
        trial.down_orbitals(), walker.down(),
        walker.down_log_abs_scale());
    result.log_abs_normalized_overlap =
        result.up.log_abs_det_s + result.down.log_abs_det_s;
    result.log_abs_orbital_scale =
        result.up.log_abs_orbital_scale +
        result.down.log_abs_orbital_scale;
    return result;
}

SiteRatioDiagnostic diagnose_site_ratios(
    const HubbardModel& model, const TrialState& trial,
    const Walker& walker, std::size_t site) {
    if (site >= model.sites()) {
        throw std::out_of_range("diagnostic site is outside lattice");
    }
    SiteRatioDiagnostic result;
    if (walker.overlap_signed_log(trial).sign == 0) {
        throw std::runtime_error(
            "cannot diagnose site ratios at zero trial overlap");
    }

    Walker plus = walker;
    Walker minus = walker;
    plus.apply_site_field(model, site, +1);
    minus.apply_site_field(model, site, -1);
    result.direct_plus_ratio = plus.overlap_ratio(trial, walker);
    result.direct_minus_ratio = minus.overlap_ratio(trial, walker);

    try {
        result.g_up = mixed_local_density(
            trial.up_orbitals(), walker.up(), site);
        result.g_down = mixed_local_density(
            trial.down_orbitals(), walker.down(), site);
        result.predicted_plus_ratio =
            predicted_spin_ratio(model, true, +1, result.g_up) *
            predicted_spin_ratio(model, false, +1, result.g_down);
        result.predicted_minus_ratio =
            predicted_spin_ratio(model, true, -1, result.g_up) *
            predicted_spin_ratio(model, false, -1, result.g_down);
        result.max_abs_residual = std::max(
            std::abs(result.predicted_plus_ratio -
                     result.direct_plus_ratio),
            std::abs(result.predicted_minus_ratio -
                     result.direct_minus_ratio));
        result.predicted_low_overlap_field =
            result.predicted_plus_ratio < result.predicted_minus_ratio
                ? +1
                : -1;
    } catch (const std::runtime_error&) {
        result.max_abs_residual =
            std::numeric_limits<double>::infinity();
        result.predicted_low_overlap_field =
            result.direct_plus_ratio < result.direct_minus_ratio ? +1 : -1;
    }
    return result;
}

}  // namespace audit
