#include "physical_path.hpp"
#include "test_common.hpp"
#include "walker.hpp"

#include <cmath>
#include <cstdint>
#include <vector>

namespace {

std::vector<std::uint8_t> pack(const std::vector<int>& fields) {
    std::vector<std::uint8_t> packed((fields.size() + 7) / 8, 0);
    for (std::size_t index = 0; index < fields.size(); ++index) {
        if (fields.at(index) == 1) {
            packed.at(index / 8) |=
                static_cast<std::uint8_t>(1U << (index % 8));
        }
    }
    return packed;
}

}  // namespace

int main() {
    return run_test_main([] {
        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 8.0, 0.1, 2, 2);
        const auto initial = audit::TrialState::rhf_x(model);
        const auto guide = audit::TrialState::solve_uhf(model, 8.0);
        const std::vector<int> fields = {
            1, -1, -1, 1,
            -1, 1, 1, -1,
        };
        const auto packed = pack(fields);
        const audit::FieldView view{packed.data(), fields.size()};
        const auto stable = audit::evaluate_physical_path(
            model, initial, guide, view, 2, 1, 1
        );
        const auto direct = audit::evaluate_physical_path(
            model, initial, guide, view, 2, 1, 0
        );
        require_true(stable.d_ii.sign == direct.d_ii.sign,
                     "II sign is stabilization invariant");
        require_true(stable.d_ti.sign == direct.d_ti.sign,
                     "TI sign is stabilization invariant");
        require_near(stable.d_ii.log_abs, direct.d_ii.log_abs, 1e-10,
                     "II log weight is stabilization invariant");
        require_near(stable.d_ti.log_abs, direct.d_ti.log_abs, 1e-10,
                     "TI log weight is stabilization invariant");
        require_true(stable.alf_d_ii.sign == direct.alf_d_ii.sign,
                     "ALF-ordered II sign is stabilization invariant");
        require_true(stable.alf_d_ti.sign == direct.alf_d_ti.sign,
                     "ALF-ordered TI sign is stabilization invariant");
        require_near(
            stable.alf_d_ii.log_abs, direct.alf_d_ii.log_abs, 1e-10,
            "ALF-ordered II log weight is stabilization invariant"
        );
        require_near(
            stable.alf_d_ti.log_abs, direct.alf_d_ti.log_abs, 1e-10,
            "ALF-ordered TI log weight is stabilization invariant"
        );
        require_near(
            stable.central_ii.total,
            stable.central_ii.kinetic + stable.central_ii.interaction,
            1e-12,
            "central II E=K+V"
        );
        require_near(
            stable.central_ti.total,
            stable.central_ti.kinetic + stable.central_ti.interaction,
            1e-12,
            "central TI E=K+V"
        );
        require_near(stable.central_ii.particle_number, 4.0, 1e-10,
                     "central II particle number");
        require_near(stable.central_ti.particle_number, 4.0, 1e-10,
                     "central TI particle number");

        audit::Walker endpoint = audit::Walker::from_trial(initial);
        for (std::size_t slice = 0; slice < 2; ++slice) {
            endpoint.apply_half_kinetic(model);
            for (std::size_t site = 0; site < model.sites(); ++site) {
                endpoint.apply_site_field(
                    model, site, fields.at(slice * model.sites() + site)
                );
            }
            endpoint.apply_half_kinetic(model);
        }
        const double log_common =
            -static_cast<double>(fields.size()) * std::log(2.0)
            + 2.0 * std::log(model.slice_constant());
        const auto endpoint_ii = endpoint.overlap_signed_log(initial);
        const auto endpoint_ti = endpoint.overlap_signed_log(guide);
        require_true(stable.endpoint_overlap_ii.sign == endpoint_ii.sign,
                     "direct II endpoint sign");
        require_near(stable.endpoint_overlap_ii.log_abs,
                     endpoint_ii.log_abs, 1e-10,
                     "direct II endpoint overlap");
        require_near(stable.d_ii.log_abs,
                     endpoint_ii.log_abs + log_common, 1e-10,
                     "II includes HS measure and constant");
        require_near(stable.d_ti.log_abs,
                     endpoint_ti.log_abs + log_common, 1e-10,
                     "TI includes HS measure and constant");

        audit::Walker alf_endpoint = audit::Walker::from_trial(initial);
        for (std::size_t slice = 0; slice < 2; ++slice) {
            alf_endpoint.apply_half_kinetic(model);
            alf_endpoint.apply_half_kinetic(model);
            for (std::size_t site = 0; site < model.sites(); ++site) {
                alf_endpoint.apply_site_field(
                    model, site, fields.at(slice * model.sites() + site)
                );
            }
        }
        const auto alf_endpoint_ii =
            alf_endpoint.overlap_signed_log(initial);
        const auto alf_endpoint_ti =
            alf_endpoint.overlap_signed_log(guide);
        require_true(stable.alf_d_ii.sign == alf_endpoint_ii.sign,
                     "ALF-ordered II endpoint sign");
        require_true(stable.alf_d_ti.sign == alf_endpoint_ti.sign,
                     "ALF-ordered TI endpoint sign");
        require_near(
            stable.alf_d_ii.log_abs,
            alf_endpoint_ii.log_abs + log_common, 1e-10,
            "ALF-ordered II endpoint weight"
        );
        require_near(
            stable.alf_d_ti.log_abs,
            alf_endpoint_ti.log_abs + log_common, 1e-10,
            "ALF-ordered TI endpoint weight"
        );
        require_true(
            std::abs(stable.d_ti.log_abs - stable.alf_d_ti.log_abs)
                > 1.0e-6,
            "UHF boundary exposes the ALF/CP Trotter-cut factor"
        );
    });
}
