using Test, LinearAlgebra
using TensorKit, PEPSKit

include(joinpath(@__DIR__, "..", "scripts", "ad_tied_core.jl"))

@testset "M2 tied dense-AD core" begin
    P, V = ℂ^4, ℂ^2
    A = TensorMap(randn(ComplexF64, 4, 16), P, V ⊗ V ⊗ V' ⊗ V')

    psi = tied_peps(A)
    @test is_tied(psi)
    @test all(psi.A[r, c] ≈ A for r in 1:2, c in 1:2)

    bad = [copy(A) for _ in 1:2, _ in 1:2]
    bad[2, 1] = 2A
    @test !is_tied(InfinitePEPS(bad))

    g = InfinitePEPS([Float64(2(r - 1) + c) * A for r in 1:2, c in 1:2])
    gp = project_tied_gradient(g)
    @test is_tied(gp)
    @test gp.A[1, 1] ≈ 2.5A

    d, ng = tied_descent_direction(g; grad_tol = 0.0)
    @test d !== nothing
    @test ng ≈ peps_frobnorm(gp)
    @test peps_frobnorm(d) ≈ 1.0
    @test is_tied(d)

    z = InfinitePEPS([zero(A) for _ in 1:2, _ in 1:2])
    d0, ng0 = tied_descent_direction(z; grad_tol = 1e-12)
    @test d0 === nothing
    @test ng0 == 0
end

include(joinpath(@__DIR__, "..", "scripts", "ad_tied_gd.jl"))

@testset "M2 tied dense-AD mode ceilings" begin
    exact = mode_config("exact-smoke")
    smoke = mode_config("random-smoke")
    run = mode_config("run")

    @test (exact.chi, exact.max_steps) == (4, 2)
    @test (smoke.chi, smoke.max_steps) == (4, 20)
    @test (run.chi, run.max_steps) == (12, 20)
    @test exact.require_accepts == 0
    @test smoke.require_accepts == 20
    @test run.final_chi == 20
    @test_throws ArgumentError mode_config("m3")
    @test requested_modes("smoke") == ("exact-smoke", "random-smoke")
    @test record_stabilizers_each_step(smoke)

    continuation = continuation_config(32; chi = 8)
    @test (continuation.chi, continuation.max_steps) == (8, 32)
    @test continuation.require_accepts == 32
    @test record_stabilizers_each_step(continuation)
    @test global_step(20, 80) == 100

    @test physical_observables(-7.9768, fill(0.9997, 4), fill(0.9945, 4))
    @test !physical_observables(-8.0025, fill(0.9999, 4), fill(0.9999, 4))
    @test !physical_observables(-7.9999, fill(1.00005, 4), fill(0.9999, 4))
    @test meets_h0_target(-8.00000000156, fill(1 + 3e-10, 4), fill(1 + 9e-11, 4))
    @test !meets_h0_target(-7.99982465, fill(0.99998, 4), fill(0.99997, 4))
    @test continuation_passed(
        -8.00000000156, fill(1 + 3e-10, 4), fill(1 + 9e-11, 4))
    @test !continuation_passed(-7.9, fill(0.99, 4), fill(0.99, 4))

    seen_environments = Symbol[]
    evaluate = function (_, environment)
        push!(seen_environments, environment)
        energy = environment == :warm ? -7.999 : -8.001
        return energy, fill(1.0, 4), fill(1.0, 4)
    end
    evaluations = continuation_evaluations(
        (psi = :state, env = :warm), smoke;
        fresh_environment = (_, _) -> (:fresh, :fresh_info), evaluate)
    @test evaluations.primary.energy == -7.999
    @test evaluations.fresh.energy == -8.001
    @test seen_environments == [:warm, :fresh]

    P, V = ℂ^4, ℂ^2
    tensor = TensorMap(randn(ComplexF64, 4, 16), P, V ⊗ V ⊗ V' ⊗ V')
    line_psi = tied_peps(tensor)
    line_gradient = tied_peps(tensor)
    trial_calls = Ref(0)
    warm_env = Ref(:accepted_environment)
    seen_environments = Any[]
    evaluate_trial = function (_, environment, _)
        trial_calls[] += 1
        push!(seen_environments, environment)
        trial_calls[] == 1 && throw(CTMRGConvergenceError("test non-convergence"))
        return (env = nothing, info = nothing, energy = -1.0)
    end
    line_result = tied_armijo_step(
        line_psi, warm_env, 0.0, line_gradient, smoke; evaluate_trial)
    @test line_result.status == :accepted
    @test line_result.alpha == 0.15
    @test trial_calls[] == 2
    @test all(environment === warm_env for environment in seen_environments)
end
