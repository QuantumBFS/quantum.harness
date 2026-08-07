#include "hubbard.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

namespace audit {

HubbardModel HubbardModel::square_periodic(
    std::size_t lx, std::size_t ly, double hopping, double interaction,
    double dt, std::size_t n_up, std::size_t n_down) {
    return HubbardModel(lx, ly, hopping, interaction, dt, n_up, n_down);
}

HubbardModel::HubbardModel(std::size_t lx, std::size_t ly, double hopping,
                           double interaction, double dt, std::size_t n_up,
                           std::size_t n_down)
    : lx_(lx),
      ly_(ly),
      hopping_(hopping),
      interaction_(interaction),
      dt_(dt),
      n_up_(n_up),
      n_down_(n_down),
      gamma_(0.0),
      kinetic_(lx * ly, lx * ly),
      kinetic_half_(lx * ly, lx * ly) {
    if (lx_ < 2 || ly_ < 2) {
        throw std::invalid_argument(
            "square periodic audit requires both axes at least two");
    }
    if (!(hopping_ > 0.0) || interaction_ < 0.0 || !(dt_ > 0.0)) {
        throw std::invalid_argument("invalid Hubbard coupling or time step");
    }
    if (n_up_ > sites() || n_down_ > sites()) {
        throw std::invalid_argument("particle count exceeds site count");
    }

    gamma_ = std::acosh(std::exp(dt_ * interaction_ / 2.0));
    const auto index = [this](std::size_t x, std::size_t y) {
        return y * lx_ + x;
    };
    for (std::size_t y = 0; y < ly_; ++y) {
        for (std::size_t x = 0; x < lx_; ++x) {
            const std::size_t site = index(x, y);
            const std::size_t xp = index((x + 1) % lx_, y);
            const std::size_t xm = index((x + lx_ - 1) % lx_, y);
            const std::size_t yp = index(x, (y + 1) % ly_);
            const std::size_t ym = index(x, (y + ly_ - 1) % ly_);
            kinetic_(site, xp) -= hopping_;
            kinetic_(site, xm) -= hopping_;
            kinetic_(site, yp) -= hopping_;
            kinetic_(site, ym) -= hopping_;
        }
    }
    kinetic_half_ = symmetric_exponential(kinetic_, -0.5 * dt_);
}

double HubbardModel::hs_multiplier(bool spin_up, int field) const {
    if (field != -1 && field != +1) {
        throw std::invalid_argument("Hirsch field must be -1 or +1");
    }
    return std::exp((spin_up ? 1.0 : -1.0) * gamma_ * field);
}

double HubbardModel::local_hs_weight(int n_up, int n_down,
                                     int field) const {
    if ((n_up != 0 && n_up != 1) || (n_down != 0 && n_down != 1)) {
        throw std::invalid_argument("local occupations must be zero or one");
    }
    return std::exp(gamma_ * field * (n_up - n_down) -
                    0.5 * dt_ * interaction_ * (n_up + n_down));
}

double HubbardModel::slice_constant() const {
    return std::exp(-0.5 * dt_ * interaction_ *
                    static_cast<double>(n_up_ + n_down_));
}

std::vector<std::size_t> HubbardModel::row_major_order() const {
    std::vector<std::size_t> result(sites());
    std::iota(result.begin(), result.end(), std::size_t{0});
    return result;
}

std::vector<std::size_t> HubbardModel::reverse_order() const {
    auto result = row_major_order();
    std::reverse(result.begin(), result.end());
    return result;
}

std::vector<std::size_t> HubbardModel::sublattice_order() const {
    std::vector<std::size_t> result;
    result.reserve(sites());
    for (int target : {+1, -1}) {
        for (std::size_t site = 0; site < sites(); ++site) {
            if (sublattice(site) == target) {
                result.push_back(site);
            }
        }
    }
    return result;
}

int HubbardModel::sublattice(std::size_t site) const {
    if (site >= sites()) {
        throw std::out_of_range("site index outside lattice");
    }
    const std::size_t x = site % lx_;
    const std::size_t y = site / lx_;
    return ((x + y) % 2 == 0) ? +1 : -1;
}

}  // namespace audit
