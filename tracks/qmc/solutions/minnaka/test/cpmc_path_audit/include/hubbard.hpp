#pragma once

#include "dense_matrix.hpp"

#include <cstddef>
#include <vector>

namespace audit {

class HubbardModel {
public:
    static HubbardModel square_periodic(std::size_t lx, std::size_t ly,
                                        double hopping, double interaction,
                                        double dt, std::size_t n_up,
                                        std::size_t n_down);

    std::size_t lx() const noexcept { return lx_; }
    std::size_t ly() const noexcept { return ly_; }
    std::size_t sites() const noexcept { return lx_ * ly_; }
    std::size_t n_up() const noexcept { return n_up_; }
    std::size_t n_down() const noexcept { return n_down_; }
    double hopping() const noexcept { return hopping_; }
    double u() const noexcept { return interaction_; }
    double dt() const noexcept { return dt_; }
    double gamma() const noexcept { return gamma_; }

    const Matrix& kinetic() const noexcept { return kinetic_; }
    const Matrix& kinetic_half() const noexcept { return kinetic_half_; }

    double hs_multiplier(bool spin_up, int field) const;
    double local_hs_weight(int n_up, int n_down, int field) const;
    double slice_constant() const;

    std::vector<std::size_t> row_major_order() const;
    std::vector<std::size_t> reverse_order() const;
    std::vector<std::size_t> sublattice_order() const;
    int sublattice(std::size_t site) const;

private:
    HubbardModel(std::size_t lx, std::size_t ly, double hopping,
                 double interaction, double dt, std::size_t n_up,
                 std::size_t n_down);

    std::size_t lx_;
    std::size_t ly_;
    double hopping_;
    double interaction_;
    double dt_;
    std::size_t n_up_;
    std::size_t n_down_;
    double gamma_;
    Matrix kinetic_;
    Matrix kinetic_half_;
};

}  // namespace audit
