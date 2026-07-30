#pragma once

#include "hubbard.hpp"
#include "signed_log.hpp"
#include "trial.hpp"

#include <cstddef>

namespace audit {

class Walker {
public:
    Walker(Matrix up, Matrix down);
    static Walker from_trial(const TrialState& trial);

    const Matrix& up() const noexcept { return up_; }
    const Matrix& down() const noexcept { return down_; }

    void apply_half_kinetic(const HubbardModel& model);
    void apply_site_field(const HubbardModel& model, std::size_t site,
                          int field);
    void stabilize();
    double overlap(const TrialState& trial) const;
    SignedLog overlap_signed_log(const TrialState& trial) const;
    double overlap_ratio(const TrialState& trial,
                         const Walker& before) const;
    double log_abs_scale() const noexcept {
        return up_log_abs_scale_ + down_log_abs_scale_;
    }
    double up_log_abs_scale() const noexcept {
        return up_log_abs_scale_;
    }
    double down_log_abs_scale() const noexcept {
        return down_log_abs_scale_;
    }
    int scale_sign() const noexcept {
        return up_scale_sign_ * down_scale_sign_;
    }

private:
    Matrix up_;
    Matrix down_;
    double up_log_abs_scale_ = 0.0;
    double down_log_abs_scale_ = 0.0;
    int up_scale_sign_ = 1;
    int down_scale_sign_ = 1;
};

}  // namespace audit
