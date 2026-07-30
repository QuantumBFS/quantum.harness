#!/usr/bin/env julia

include(joinpath(@__DIR__, "build_shastry_full_state_spin_isotypic_mof.jl"))

function main()
    println("[ss-spin-isotypic-small] assemble one-symbol truth anchor")
    flush(stdout)
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(0//1),
        1//1,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    primal = assemble_primal_gap(
        problem;
        stationarity_spec=StationaritySpec(:full_inner_state, 1),
    )
    v4 = assemble_full_state_v4_reduced_primal(
        primal;
        verify_truth=false,
    )
    real_reduced = assemble_full_state_real_reduced_primal(
        v4;
        verify_truth=false,
    )
    spatial = assemble_shastry_full_state_spatial_reduced_primal(
        real_reduced;
        verify_truth=false,
    )
    spin_spatial =
        assemble_shastry_full_state_spin_spatial_reduced_primal(
            spatial;
            verify_truth=false,
            verify_source_covariance=false,
        )
    truth = shastry_spin_isotypic_truth(spin_spatial)
    show(stdout, "text/plain", truth)
    println()
    flush(stdout)
    truth.exact || exit(1)
end

main()
