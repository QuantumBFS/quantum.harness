#!/usr/bin/env julia

include(joinpath(@__DIR__, "build_shastry_full_state_spin_isotypic_mof.jl"))

problem = GapProblem(
    square_patch_geometry(1),
    shastry_sutherland_model(4 // 5),
    2 // 1,
    2;
    basis_mode=:structured,
    basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
)
stationarity = StationaritySpec(:full_inner_state, 1)

println("[structural-primal-truth] assemble materialized L=1 truth")
flush(stdout)
materialized_measurement = @timed assemble_primal_gap(
    problem;
    stationarity_spec=stationarity,
)
materialized = materialized_measurement.value

println("[structural-primal-truth] assemble structural L=1 candidate")
flush(stdout)
structural_measurement = @timed assemble_primal_gap(
    problem;
    stationarity_spec=stationarity,
    materialize_coefficients=false,
)
structural = structural_measurement.value

materialized.moments == structural.moments ||
    error("structural primal moment inventory differs from materialized truth")
materialized.moments_sha256 == structural.moments_sha256 ||
    error("structural primal moment fingerprint differs from materialized truth")
materialized.stationarity_equalities == structural.stationarity_equalities ||
    error("structural primal stationarity equalities differ")
(
    materialized.positive_basis.sha256 ==
        structural.positive_basis.sha256 &&
    materialized.positive_basis.entries ==
        structural.positive_basis.entries
) ||
    error("structural primal positive basis differs")
(
    materialized.gap_basis.sha256 == structural.gap_basis.sha256 &&
    materialized.gap_basis.entries == structural.gap_basis.entries
) ||
    error("structural primal gap basis differs")

println(
    "structural_primal_truth=true",
    " moments=", length(structural.moments),
    " moments_sha256=", structural.moments_sha256,
    " materialized_wall_seconds=", materialized_measurement.time,
    " structural_wall_seconds=", structural_measurement.time,
)
flush(stdout)
