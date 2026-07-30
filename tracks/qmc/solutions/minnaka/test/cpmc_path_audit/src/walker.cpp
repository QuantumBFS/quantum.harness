#include "walker.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace audit {

Walker::Walker(Matrix up, Matrix down)
    : up_(std::move(up)), down_(std::move(down)) {
    if (up_.rows() != down_.rows()) {
        throw std::invalid_argument("walker spin sectors have different sites");
    }
}

Walker Walker::from_trial(const TrialState& trial) {
    return Walker(trial.up_orbitals(), trial.down_orbitals());
}

void Walker::apply_half_kinetic(const HubbardModel& model) {
    up_ = multiply(model.kinetic_half(), up_);
    down_ = multiply(model.kinetic_half(), down_);
}

void Walker::apply_site_field(const HubbardModel& model, std::size_t site,
                              int field) {
    if (site >= up_.rows()) {
        throw std::out_of_range("walker site index out of range");
    }
    const double up_factor = model.hs_multiplier(true, field);
    const double down_factor = model.hs_multiplier(false, field);
    for (std::size_t orbital = 0; orbital < up_.cols(); ++orbital) {
        up_(site, orbital) *= up_factor;
    }
    for (std::size_t orbital = 0; orbital < down_.cols(); ++orbital) {
        down_(site, orbital) *= down_factor;
    }
}

void Walker::stabilize() {
    auto up_qr = thin_qr(up_);
    auto down_qr = thin_qr(down_);
    const auto absorb_diagonal = [](const Matrix& r, int permutation_sign,
                                    double& log_scale, int& sign) {
        sign *= permutation_sign;
        for (std::size_t index = 0; index < r.rows(); ++index) {
            const double diagonal = r(index, index);
            if (diagonal == 0.0) {
                sign = 0;
                log_scale =
                    -std::numeric_limits<double>::infinity();
                return;
            }
            if (diagonal < 0.0) {
                sign = -sign;
            }
            log_scale += std::log(std::abs(diagonal));
        }
    };
    absorb_diagonal(
        up_qr.r, up_qr.permutation_sign,
        up_log_abs_scale_, up_scale_sign_
    );
    absorb_diagonal(
        down_qr.r, down_qr.permutation_sign,
        down_log_abs_scale_, down_scale_sign_
    );
    up_ = std::move(up_qr.q);
    down_ = std::move(down_qr.q);
}

double Walker::overlap(const TrialState& trial) const {
    if (scale_sign() == 0) {
        return 0.0;
    }
    return static_cast<double>(scale_sign()) * std::exp(log_abs_scale()) *
           trial.overlap(up_, down_);
}

SignedLog Walker::overlap_signed_log(const TrialState& trial) const {
    const auto up = signed_log_determinant(multiply(
        transpose(trial.up_orbitals()), up_
    ));
    const auto down = signed_log_determinant(multiply(
        transpose(trial.down_orbitals()), down_
    ));
    auto result = signed_log_product(up, down);
    if (result.sign == 0 || scale_sign() == 0) {
        return {0, -std::numeric_limits<double>::infinity()};
    }
    result.sign *= scale_sign();
    result.log_abs += log_abs_scale();
    return result;
}

double Walker::overlap_ratio(
    const TrialState& trial, const Walker& before
) const {
    return signed_log_ratio(
        overlap_signed_log(trial),
        before.overlap_signed_log(trial)
    );
}

}  // namespace audit
