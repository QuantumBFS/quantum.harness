#!/usr/bin/env julia

using Test

include(joinpath(
    @__DIR__,
    "..",
    "scripts",
    "build_shastry_full_state_spin_isotypic_mof.jl",
))
include(joinpath(
    @__DIR__,
    "..",
    "scripts",
    "replay_mosek_infeasibility_artifact.jl",
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
synthetic_assembly = ShastryFullStateSpinIsotypicReducedPrimalAssembly(
    "synthetic-audit-v1",
    nothing,
    nothing,
    ShastrySpinIsotypicPSDBlock[],
    ShastrySpinIsotypicPSDBlock[],
    ExactLinearPolynomial[],
    [
        moment_key(),
        moment_key([PauliWord([(1, UInt8(1))])]),
    ],
    "synthetic-coefficients",
    "synthetic-audit-v1",
)

infeasible_model = JuMP.Model(MosekTools.Optimizer)
JuMP.set_silent(infeasible_model)
z = JuMP.@variable(infeasible_model, base_name="infeasible_moment")
JuMP.@constraint(infeasible_model, z == 1.0)
JuMP.@constraint(infeasible_model, z <= 0.0)
JuMP.optimize!(infeasible_model)

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
    @test JuMP.termination_status(infeasible_model) == JuMP.MOI.INFEASIBLE
    @test classify_spin_isotypic_result(
        JuMP.termination_status(infeasible_model),
        JuMP.primal_status(infeasible_model),
        JuMP.dual_status(infeasible_model),
        Dict{String,Any}(),
    ) == "infeasibility_candidate_requires_independent_ray_replay"
    mktempdir() do directory
        path = joinpath(directory, "primal-values.tsv")
        artifact = write_spin_isotypic_primal_values(
            path,
            wrapped,
            synthetic_assembly,
        )
        @test artifact["variable_count"] == 2
        @test artifact["sha256"] == file_sha256(path)
        lines = readlines(path)
        @test lines[3] == "index\tmoment_canonical\tfloat64_bits"
        @test endswith(lines[4], bitstring(JuMP.value(y[1])))
        @test endswith(lines[5], bitstring(JuMP.value(y[2])))
        mosek_solution = write_mosek_solution_artifact(
            joinpath(directory, "synthetic.bsol.gz"),
            model,
        )
        @test mosek_solution["available"]
        @test mosek_solution["bytes"] > 0
        @test mosek_solution["sha256"] ==
              file_sha256(joinpath(directory, "synthetic.bsol.gz"))
        mosek_task = write_mosek_task_artifact(
            joinpath(directory, "synthetic.task.gz"),
            model,
        )
        @test mosek_task["bytes"] > 0
        @test mosek_task["sha256"] ==
              file_sha256(joinpath(directory, "synthetic.task.gz"))
        infeasible_solution = write_mosek_solution_artifact(
            joinpath(directory, "infeasible.bsol.gz"),
            infeasible_model,
        )
        @test infeasible_solution["available"]
        @test infeasible_solution["bytes"] > 0
        infeasible_task = write_mosek_task_artifact(
            joinpath(directory, "infeasible.task.gz"),
            infeasible_model,
        )
        replay = mosek_ray_replay_report(
            joinpath(directory, "infeasible.task.gz"),
            joinpath(directory, "infeasible.bsol.gz");
            expected_task_sha256=infeasible_task["sha256"],
            expected_solution_sha256=infeasible_solution["sha256"],
        )
        println("synthetic infeasibility replay audit: ", replay["audit"])
        flush(stdout)
        @test replay["audit"]["status_passed"]
        @test replay["audit"]["finite"]
        @test replay["audit"]["residual_passed"]
        @test replay["audit"]["separation_passed"]
        @test replay["audit"]["passed"]
        @test replay["classification"] ==
              "mosek_native_infeasibility_ray_replayed_float"
    end
end
