#!/usr/bin/env julia

using Test

include(joinpath(
    @__DIR__,
    "..",
    "scripts",
    "build_shastry_full_state_spin_isotypic_mof.jl",
))

model = JuMP.Model(MosekTools.Optimizer)
JuMP.set_silent(model)
y = JuMP.@variable(model, [1:2], base_name="synthetic_moment")
normalization = JuMP.@constraint(
    model,
    y[1] == 1.0,
    base_name="normalization",
)
psd = JuMP.@constraint(
    model,
    Symmetric([y[1] y[2]; y[2] y[1]]) in JuMP.PSDCone(),
    base_name="synthetic_real_psd",
)
JuMP.@objective(model, Max, y[2])
JuMP.optimize!(model)

wrapped = ShastryFullStateSpinIsotypicJuMPPrimalModel(
    model,
    collect(y),
    normalization,
    JuMP.ConstraintRef[],
    [psd],
    "synthetic-audit-v1",
)
diagnostics = spin_isotypic_solution_diagnostics(wrapped, 1e-7)

@testset "direct spin-isotypic solve audit" begin
    @test JuMP.termination_status(model) == JuMP.MOI.OPTIMAL
    @test diagnostics["available"]
    @test diagnostics["passed"]
    @test diagnostics["normalization"]["normalized_residual"] <= 1e-7
    @test diagnostics["worst_normalized_psd_violation"] <= 1e-7
    @test haskey(diagnostics["psd_blocks"], "synthetic_real_psd")
    @test classify_spin_isotypic_result(
        JuMP.termination_status(model),
        JuMP.primal_status(model),
        JuMP.dual_status(model),
        diagnostics,
    ) == "feasible_residual_checked_float"
    @test classify_spin_isotypic_result(
        JuMP.MOI.INFEASIBLE,
        JuMP.MOI.NO_SOLUTION,
        JuMP.MOI.INFEASIBILITY_CERTIFICATE,
        Dict{String,Any}(),
    ) == "infeasibility_candidate_requires_independent_ray_replay"
    @test classify_spin_isotypic_result(
        JuMP.MOI.TIME_LIMIT,
        JuMP.MOI.NO_SOLUTION,
        JuMP.MOI.NO_SOLUTION,
        Dict{String,Any}(),
    ) == "unknown"
end
