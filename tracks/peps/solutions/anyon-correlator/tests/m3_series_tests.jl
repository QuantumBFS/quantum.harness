using Test, LinearAlgebra
using TensorKit, PEPSKit

include(joinpath(@__DIR__, "..", "scripts", "m3_series_validation.jl"))

@testset "series expansion matches the converted J=1 reference" begin
    @test SERIES_PILOT_GRID == [0.0, 0.05]
    @test series_energy_per_spin(0.0) == -1.0
    @test series_energy_per_spin(-0.1) == series_energy_per_spin(0.1)
    # h_z^2 leading term: (e(h) + 1) / h^2 -> 1/4 as h -> 0
    @test (series_energy_per_spin(1e-3) + 1) / 1e-6 ≈ -0.25 rtol = 1e-4
    # reference values (arXiv:0807.0487 Eq. 8 converted: e_ours = 2 e_paper(h/2))
    @test series_energy_per_spin(0.10) ≈ -1.0025240337 rtol = 1e-9
    h2 = 0.05^2
    expected_005 =
        -1 - h2 / 4 - 15 * h2^2 / 64 - 147 * h2^3 / 256 - 18003 * h2^4 / 8192
    @test series_energy_per_spin(0.05) ≈ expected_005 rtol = 1e-12
    @test series_energy_floor_cell(0.1) ≈ -8.8 - 1e-5
end

@testset "series config is bounded and validated" begin
    config = SeriesConfig()
    @test (config.chi, config.chi_check) == (8, 16)
    @test config.ctm_tol == 1e-8
    @test config.ctm_maxiter == 500
    @test config.grad_tol == 1e-6
    @test config.max_steps == 50
    @test config.armijo_initial_alpha == 0.05
    @test config.fresh_warm_tol == 1e-6
    @test_throws ArgumentError SeriesConfig(chi = 2)
    @test_throws ArgumentError SeriesConfig(chi_check = 8)
    @test_throws ArgumentError SeriesConfig(ctm_tol = 0.0)
    @test_throws ArgumentError SeriesConfig(max_steps = 0)
    @test_throws ArgumentError SeriesConfig(armijo_initial_alpha = 0.1)
    @test_throws ArgumentError SeriesConfig(energy_init_tol = 0.0)
    @test_throws ArgumentError SeriesConfig(fresh_warm_tol = 0.0)
end

series_row(label, energy; stars = fill(0.95, 4), plaquettes = fill(0.999, 4),
           mz = 0.1, seed = 424242, chi = 8, residual = 1e-9, iters = 5) =
    (; label, seed, chi, status = :converged, residual, iters,
       energy, stars, plaquettes, mz)

@testset "series Armijo requires fresh-verified acceptance" begin
    P, V = ℂ^4, ℂ^2
    tensor = normalize!(
        TensorMap(randn(ComplexF64, 4, 16), P, V ⊗ V ⊗ V' ⊗ V'), Inf)
    psi = tied_peps(tensor)
    gradient = tied_peps(tensor)
    config = SeriesConfig()

    det_accept(det_energy) = (_, _, _) ->
        (env = :det_env, info = nothing, energy = det_energy)
    veto_accept(veto_energy) = (_, _, _) ->
        (energy = veto_energy, residual = 1e-9)

    # both branches healthy: accepted at full alpha, veto energy recorded
    result = series_armijo_step(
        psi, :carried_env, -8.2, -8.2, gradient, 0.05, nothing, config;
        evaluate_trial = det_accept(-8.2005), verify_trial = veto_accept(-8.200505))
    @test result.status == :accepted
    @test result.alpha == 0.05
    @test result.fresh_energy == -8.200505
    @test result.env == :det_env

    # veto contraction fails to converge: halve alpha, accept the retry
    veto_calls = Ref(0)
    veto_flaky = function (_, _, _)
        veto_calls[] += 1
        veto_calls[] == 1 && throw(CTMRGConvergenceError("veto branch failed"))
        return (energy = -8.200505, residual = 1e-9)
    end
    result = series_armijo_step(
        psi, :carried_env, -8.2, -8.2, gradient, 0.05, nothing, config;
        evaluate_trial = det_accept(-8.2005), verify_trial = veto_flaky)
    @test result.status == :accepted
    @test result.alpha == 0.025
    @test veto_calls[] == 2

    # objective branch fails to converge: halve alpha, accept the retry
    det_calls = Ref(0)
    det_flaky = function (_, _, _)
        det_calls[] += 1
        det_calls[] == 1 && throw(CTMRGConvergenceError("objective branch failed"))
        return (env = :det_env, info = nothing, energy = -8.2005)
    end
    result = series_armijo_step(
        psi, :carried_env, -8.2, -8.2, gradient, 0.05, nothing, config;
        evaluate_trial = det_flaky, verify_trial = veto_accept(-8.200505))
    @test result.status == :accepted
    @test result.alpha == 0.025
    @test det_calls[] == 2

    # veto energy rises against the reference: veto every trial
    result = series_armijo_step(
        psi, :carried_env, -8.2, -8.2, gradient, 0.05, nothing, config;
        evaluate_trial = det_accept(-8.2005), verify_trial = veto_accept(-8.199))
    @test result.status == :armijo_failed

    # det/veto disagreement beyond fresh_warm_tol per spin: veto every trial
    result = series_armijo_step(
        psi, :carried_env, -8.2, -8.2, gradient, 0.05, nothing, config;
        evaluate_trial = det_accept(-8.2005), verify_trial = veto_accept(-8.210))
    @test result.status == :armijo_failed

    # objective branch itself unphysical: rejected before any veto call
    veto_never = function (_, _, _)
        error("veto verifier must not run when the objective branch is rejected")
    end
    result = series_armijo_step(
        psi, :carried_env, -8.2, -8.2, gradient, 0.05, nothing, config;
        evaluate_trial = det_accept(-100.0), verify_trial = veto_never)
    @test result.status == :armijo_failed
end

@testset "series audit consistency requires branch agreement" begin
    config = SeriesConfig()
    rows = [
        series_row("warm", -8.200),
        series_row("fresh_det", -8.200000001),
        series_row("fresh_rand_1", -8.200000002; seed = 1),
        series_row("fresh_rand_2", -8.199999999; seed = 2),
    ]
    accepted = assess_series_consistency(
        rows; energy_tol = config.energy_init_tol,
        observable_tol = config.observable_init_tol)
    @test accepted.usable
    @test accepted.reason == :consistent
    @test accepted.converged == 4
    @test accepted.energy_spread_per_spin ≈ 3e-9 / 8 rtol = 1e-6

    split_energy = assess_series_consistency(
        [rows[1], rows[2], rows[3],
         series_row("fresh_rand_2", -8.201; seed = 2)];
        energy_tol = config.energy_init_tol,
        observable_tol = config.observable_init_tol)
    @test !split_energy.usable
    @test split_energy.reason == :energy_disagreement

    split_observable = assess_series_consistency(
        [rows[1], rows[2], rows[3],
         series_row("fresh_rand_2", -8.2; seed = 2, stars = [0.95, 0.95, 0.95, 0.96])];
        energy_tol = config.energy_init_tol,
        observable_tol = config.observable_init_tol)
    @test !split_observable.usable
    @test split_observable.reason == :observable_disagreement

    short = assess_series_consistency(
        rows[1:3]; energy_tol = config.energy_init_tol,
        observable_tol = config.observable_init_tol)
    @test !short.usable
    @test short.reason == :insufficient_inits
end

@testset "series chi stability compares against the fresh deterministic branch" begin
    config = SeriesConfig()
    reference = series_row("fresh_det", -8.200)
    close_check = series_row("chi16_det", -8.200000004; chi = 16)
    stable = assess_series_chi(
        reference, close_check; energy_tol = config.chi_stability_tol,
        observable_tol = config.observable_init_tol)
    @test stable.stable
    @test stable.energy_delta_per_spin ≈ 5e-10 rtol = 1e-6

    drifted = series_row("chi16_det", -8.2001; chi = 16)
    unstable = assess_series_chi(
        reference, drifted; energy_tol = config.chi_stability_tol,
        observable_tol = config.observable_init_tol)
    @test !unstable.stable
    @test unstable.energy_delta_per_spin ≈ 1.25e-5 rtol = 1e-6
end

@testset "series point acceptance implements protocol item 7" begin
    consistent = (
        usable = true, reason = :consistent, converged = 4,
        energy_spread_per_spin = 1e-9, observable_spread = 1e-7)
    stable = (stable = true, energy_delta_per_spin = 1e-9, observable_delta = 1e-7)
    @test series_point_accepted(0.0, :m2_anchor, consistent, stable)
    @test series_point_accepted(0.05, :stationary, consistent, stable)
    # budget exhaustion is not convergence (protocol item 9)
    @test !series_point_accepted(0.05, :budget, consistent, stable)
    @test !series_point_accepted(0.05, :armijo_failed, consistent, stable)
    ambiguous = (usable = false, reason = :energy_disagreement, converged = 4,
                 energy_spread_per_spin = 1e-4, observable_spread = 1e-7)
    @test !series_point_accepted(0.05, :stationary, ambiguous, stable)
    drifting = (stable = false, energy_delta_per_spin = 1e-4, observable_delta = 1e-7)
    @test !series_point_accepted(0.05, :stationary, consistent, drifting)
end

@testset "series audit CSV records every initialization" begin
    rows = [
        series_row("warm", -8.2; iters = 1),
        series_row("fresh_det", -8.2),
        failed_audit_row("fresh_rand_1", 1, 8),
        series_row("fresh_rand_2", -8.2; seed = 2),
    ]
    check = series_row("chi16_det", -8.2; chi = 16)
    mktempdir() do directory
        path = joinpath(directory, "audit.csv")
        write_series_audit_csv(path, rows, check)
        lines = readlines(path)
        @test lines[1] == series_audit_header()
        @test length(lines) == 6
        @test length(split(lines[1], ",")) == 17
        @test length(split(lines[2], ",")) == 17
        @test length(split(lines[4], ",")) == 17
        @test startswith(lines[2], "warm,424242,8,converged,")
        @test startswith(lines[4], "fresh_rand_1,1,8,failed,")
        @test startswith(lines[6], "chi16_det,424242,16,converged,")
    end
end

@testset "series summary CSV round-trips the point schema" begin
    mktempdir() do directory
        path = joinpath(directory, "points.csv")
        initialize_series_csv(path)
        row = (
            hz = 0.05, source_hz = 0.0, parent_accepted = true,
            optimizer_status = :stationary, accepted_steps = 12, attempts = 12,
            final_gradnorm = 5e-7, series_e_per_spin = series_energy_per_spin(0.05),
            repr_e_per_spin = -1.0006, delta_e_per_spin = 1e-5,
            audit_converged = 4, energy_spread_per_spin = 1e-9,
            observable_spread = 1e-7, chi_check = 16,
            chi_delta_e_per_spin = 1e-9, chi_delta_obs = 1e-7,
            consistency = :consistent, chi_stable = true, point_accepted = true,
            checkpoint = "hz_0p050_final.jld2")
        append_series_row(path, row)
        lines = readlines(path)
        @test lines[1] == series_points_header()
        @test length(split(lines[1], ",")) == length(split(lines[2], ","))
        @test startswith(lines[2], "0.050000,0.000000,true,stationary,12,12,")
        @test endswith(lines[2], ",hz_0p050_final.jld2")
    end
end

@testset "series anchor loader validates the M2 checkpoint" begin
    P, V = ℂ^4, ℂ^2
    tensor = normalize!(
        TensorMap(randn(ComplexF64, 4, 16), P, V ⊗ V ⊗ V' ⊗ V'), Inf)
    psi = tied_peps(tensor)
    mktempdir() do directory
        checkpoint = joinpath(directory, "m2.jld2")
        jldsave(checkpoint; tensors = psi.A, step = 86)
        loaded = load_series_anchor(checkpoint)
        @test is_tied(loaded)
        @test loaded.A[1, 1] ≈ tensor
        @test_throws ErrorException load_series_anchor(checkpoint; expected_step = 85)
    end
end
