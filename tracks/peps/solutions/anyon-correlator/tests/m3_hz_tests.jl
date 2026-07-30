using Test, LinearAlgebra
using TensorKit, PEPSKit

include(joinpath(@__DIR__, "..", "scripts", "m3_hz_continuation.jl"))

@testset "M3 finite-field contracts" begin
    @test M3_SMOKE_GRID == [0.0, 0.10, 0.33, 0.50]
    @test M3_POINT_GRID == [0.0, 0.10]
    @test M3_CHAIN_GRID == [0.0, 0.02, 0.05, 0.08, 0.10]
    @test M3_FULL_GRID == [
        0.0, 0.10, 0.20, 0.28, 0.30, 0.32, 0.33, 0.34, 0.36, 0.40, 0.50]
    @test valid_m3_grid(M3_FULL_GRID)
    @test !valid_m3_grid(Float64[])
    @test !valid_m3_grid([0.0, 0.2, 0.1])
    @test !valid_m3_grid([0.1, 0.2])

    config = M3Config()
    @test (config.chi, config.max_steps) == (4, 4)
    @test config.ctm_tol == 1e-6
    @test config.ctm_maxiter == 80
    @test config.plaquette_tolerance == 0.05
    @test config.armijo_initial_alpha == 0.05
    @test validate_m3_config(config) === config
    @test_throws ArgumentError M3Config(chi = 8)
    @test_throws ArgumentError M3Config(armijo_initial_alpha = 0.1)
    @test_throws ArgumentError validate_m3_config(M3Config(chi = 8))
    @test_throws ArgumentError validate_m3_config(
        M3Config(armijo_initial_alpha = 0.1))

    healthy = (
        energy_cell = -8.2,
        energy_per_spin = -1.025,
        mz = 0.2,
        mean_star = 0.95,
        mean_plaquette = 0.999,
        max_star_error = 0.05,
        max_plaquette_error = 0.001,
        max_abs_star = 0.95,
        max_abs_plaquette = 1.0,
        ctm_residual = 1e-6)
    @test finite_m3_row(healthy)
    @test !finite_m3_row(merge(healthy, (mz = NaN,)))
    @test plaquette_sector_ok(healthy; tolerance = 0.05)
    @test !plaquette_sector_ok(
        merge(healthy, (max_plaquette_error = 0.2,)); tolerance = 0.05)

    rows = [
        (hz = 0.0, mz = 0.00),
        (hz = 0.2, mz = 0.05),
        (hz = 0.3, mz = 0.15),
        (hz = 0.34, mz = 0.35),
        (hz = 0.5, mz = 0.50),
    ]
    @test transition_interval(rows) == (0.30, 0.34)
    @test_throws ArgumentError transition_interval(rows[1:1])

    field_matrix = reshape(convert(Array, field_op(0.0, 0.25, TIED_UP)), 4, 4)
    @test field_matrix ≈ -0.25 .* (ZE_mat() + ZN_mat())
    hamiltonian, table = toric_code_hamiltonian(0.0, 0.25; P = TIED_UP)
    @test length(hamiltonian.terms) == 12
    @test count(term -> term.kind == :field, table) == 4
end

@testset "M3 observable summary preserves physical normalization" begin
    row = summarize_m3_observables(
        -8.2, 0.2, [0.90, 0.95, 0.90, 0.95], [1.0, 0.999, 1.0, 1.0], 1e-6)
    @test row.energy_cell == -8.2
    @test row.energy_per_spin == -1.025
    @test row.mz == 0.2
    @test row.mean_star == 0.925
    @test row.mean_plaquette == 0.99975
    @test row.max_star_error ≈ 0.1
    @test row.max_plaquette_error ≈ 0.001
    @test row.max_abs_star == 0.95
    @test row.max_abs_plaquette == 1.0
    @test row.ctm_residual == 1e-6
    @test finite_m3_row(row)
end

@testset "M3 finite-field Armijo is bounded and field-aware" begin
    P, V = ℂ^4, ℂ^2
    tensor = normalize!(
        TensorMap(randn(ComplexF64, 4, 16), P, V ⊗ V ⊗ V' ⊗ V'), Inf)
    psi = tied_peps(tensor)
    gradient = tied_peps(tensor)
    config = M3Config()

    trial_calls = Ref(0)
    evaluate_trial = function (_, _, _, _)
        trial_calls[] += 1
        trial_calls[] == 1 && throw(CTMRGConvergenceError("test non-convergence"))
        return (env = :accepted_env, info = nothing, energy = -8.3)
    end
    accepted = m3_armijo_step(
        psi, :warm_env, -8.2, gradient, 0.1, nothing, config; evaluate_trial)
    @test accepted.status == :accepted
    @test accepted.alpha == 0.025
    @test accepted.energy == -8.3
    @test accepted.env == :accepted_env
    @test trial_calls[] == 2

    floor_calls = Ref(0)
    below_floor = function (_, _, _, _)
        floor_calls[] += 1
        return (env = :bad_env, info = nothing, energy = -100.0)
    end
    rejected = m3_armijo_step(
        psi, :warm_env, -8.2, gradient, 0.1, nothing, config;
        evaluate_trial = below_floor)
    @test rejected.status == :armijo_failed
    @test floor_calls[] == 12

    warm_objective = function (_, _, _, _)
        return (
            env = :continued_warm_env, info = nothing,
            energy = -8.25, fresh_energy = -7.5)
    end
    consistent = m3_armijo_step(
        psi, :warm_env, -8.2, gradient, 0.1, nothing, config;
        evaluate_trial = warm_objective)
    @test consistent.status == :accepted
    @test consistent.alpha == 0.05
    @test consistent.energy == -8.25
    @test consistent.env == :continued_warm_env
end

@testset "M3 fresh CTMRG retries a failed deterministic branch" begin
    attempted_seeds = Int[]
    converge = function (state, chi; tol, maxiter, seed)
        push!(attempted_seeds, seed)
        seed == 424242 && throw(CTMRGConvergenceError("bad branch"))
        return :fresh_env, :fresh_info
    end
    env, info, seed = converge_m3_fresh_environment(
        :state, M3Config(); seeds = (424242, 1, 2), converge)
    @test (env, info, seed) == (:fresh_env, :fresh_info, 1)
    @test attempted_seeds == [424242, 1]

    always_fails = (state, chi; tol, maxiter, seed) ->
        throw(CTMRGConvergenceError("seed $seed failed"))
    @test_throws CTMRGConvergenceError converge_m3_fresh_environment(
        :state, M3Config(); seeds = (3, 4), converge = always_fails)

    @test candidate_contraction_safe(-8.20, -8.18, 0.1)
    @test !candidate_contraction_safe(-8.20, -8.00, 0.1)
    @test !candidate_contraction_safe(-8.20, -7.90, 0.1)
    @test !candidate_contraction_safe(-8.20, -9.00, 0.1)

    warm_calls = Ref(0)
    initialize_warm = function (state, chi; tol, maxiter, seed)
        warm_calls[] += 1
        @test seed == TIED_CTM_SEED
        return :warm_env, :warm_info
    end
    @test initialize_m3_warm_environment(
        :state, nothing, M3Config(); converge = initialize_warm) ==
          (:warm_env, :warm_info)
    @test initialize_m3_warm_environment(
        :state, :existing_env, M3Config(); converge = initialize_warm) ==
          (:existing_env, nothing)
    @test warm_calls[] == 1
end

@testset "M3 multi-seed audit requires physical branch agreement" begin
    seed_result(seed, energy; stars = fill(0.95, 4), plaquettes = fill(0.999, 4),
                mz = 0.1) = (; seed, energy, stars, plaquettes, mz, ctm_residual = 1e-7)

    agreeing = [seed_result(1, -8.200), seed_result(2, -8.204)]
    accepted = assess_m3_audit(agreeing)
    @test accepted.usable
    @test accepted.converged_seeds == 2
    @test accepted.energy_spread_per_spin ≈ 0.0005
    @test accepted.observable_spread == 0.0

    energy_split = assess_m3_audit([
        seed_result(1, -8.20), seed_result(2, -8.22)])
    @test !energy_split.usable
    @test energy_split.reason == :energy_disagreement

    observable_split = assess_m3_audit([
        seed_result(1, -8.20),
        seed_result(2, -8.20; stars = [0.95, 0.95, 0.95, 0.96])])
    @test !observable_split.usable
    @test observable_split.reason == :observable_disagreement

    unphysical = assess_m3_audit([
        seed_result(1, -8.20; stars = [1.01, 0.93, 0.93, 0.93]),
        seed_result(2, -8.20; stars = [1.01, 0.93, 0.93, 0.93])])
    @test !unphysical.usable
    @test unphysical.reason == :operator_bound

    @test assess_m3_audit([seed_result(1, -8.20)]).reason == :insufficient_seeds

    attempted = Int[]
    evaluate_seed = function (_, _, _, _, seed)
        push!(attempted, seed)
        seed == 3 && throw(CTMRGConvergenceError("seed 3 failed"))
        result = seed_result(seed, -8.20 - 0.001seed)
        return merge(result, (env = Symbol("env_$seed"), info = :info))
    end
    audit = audit_m3_point(
        :state, :hamiltonian, 0.1, M3Config();
        seeds = (1, 2, 3), evaluate_seed)
    @test audit.verdict.usable
    @test attempted == [1, 2, 3]
    @test audit.representative.seed == 1
    @test audit.failed_seeds == [3]
    mktempdir() do directory
        path = joinpath(directory, "audit.csv")
        write_m3_audit_csv(path, audit)
        lines = readlines(path)
        @test lines[1] ==
              "seed,status,energy,mz,star_1,star_2,star_3,star_4," *
              "plaquette_1,plaquette_2,plaquette_3,plaquette_4," *
              "max_abs_star,max_abs_plaquette,ctm_residual"
        @test startswith(lines[2], "1,converged,")
        @test startswith(lines[4], "3,failed,")
    end
end

@testset "M3 continuation passes accepted state forward" begin
    seen = NamedTuple[]
    run_point = function (state, environment, hz, source_hz)
        push!(seen, (; state, environment, hz, source_hz))
        return (
            state = Symbol("state_$(hz)"),
            env = Symbol("env_$(hz)"),
            row = (hz = hz, source_hz = source_hz),
        )
    end

    result = run_continuation_sequence(
        :m2_state, :m2_environment, [0.0, 0.1, 0.2], run_point)

    @test [entry.source_hz for entry in seen] == [nothing, 0.0, 0.1]
    @test seen[1].state == :m2_state
    @test seen[2].state == Symbol("state_0.0")
    @test seen[2].environment == Symbol("env_0.0")
    @test result.state == Symbol("state_0.2")
    @test result.env == Symbol("env_0.2")
    @test length(result.rows) == 3
end

@testset "M3 smoke gate requires safe sequential AD continuation" begin
    base = (
        energy_cell = -8.2,
        energy_per_spin = -1.025,
        warm_energy_cell = -8.21,
        fresh_warm_energy_spread = 0.004,
        mz = 0.2,
        mean_star = 0.95,
        mean_plaquette = 0.999,
        max_star_error = 0.05,
        max_plaquette_error = 0.001,
        max_abs_star = 0.95,
        max_abs_plaquette = 1.0,
        ctm_residual = 1e-6,
        audit_usable = true,
        audit_converged_seeds = 3,
        audit_energy_spread_per_spin = 0.0005,
        audit_observable_spread = 0.0005,
        attempts = 1,
        status = "budget",
        final_gradnorm = 1e-3,
        chi = 4,
        ctm_iters = 3,
        elapsed_s = 1.0,
        checkpoint = "point.jld2",
    )
    rows = [
        merge(base, (
            hz = 0.0, source_hz = nothing, accepted_steps = 0, mz = 0.0,
            energy_cell = -8.0, energy_per_spin = -1.0,
            warm_energy_cell = -8.0, fresh_warm_energy_spread = 0.0,
            status = "m2_anchor", final_gradnorm = 0.0)),
        merge(base, (hz = 0.1, source_hz = 0.0, accepted_steps = 1, mz = 0.1)),
        merge(base, (hz = 0.33, source_hz = 0.1, accepted_steps = 1, mz = 0.3)),
        merge(base, (hz = 0.5, source_hz = 0.33, accepted_steps = 1, mz = 0.6)),
    ]
    @test continuation_point_safe(rows[2]; plaquette_tolerance = 0.05)
    @test !continuation_point_safe(
        merge(rows[2], (energy_cell = -7.9,)); plaquette_tolerance = 0.05)
    @test !continuation_point_safe(
        merge(rows[2], (fresh_warm_energy_spread = 0.2,));
        plaquette_tolerance = 0.05)
    @test !continuation_point_safe(
        merge(rows[2], (audit_usable = false,)); plaquette_tolerance = 0.05)
    @test !continuation_point_safe(
        merge(rows[2], (max_abs_plaquette = 1.01,)); plaquette_tolerance = 0.05)
    @test smoke_passed(rows; plaquette_tolerance = 0.05)
    @test stage_passed(
        rows[1:2], M3_POINT_GRID; plaquette_tolerance = 0.05)
    @test !stage_passed(
        [rows[1], merge(rows[2], (status = "armijo_failed",))], M3_POINT_GRID;
        plaquette_tolerance = 0.05)
    stationary = merge(rows[2], (
        accepted_steps = 0, status = "stationary", final_gradnorm = 1e-6))
    @test stage_passed(
        [rows[1], stationary], M3_POINT_GRID; plaquette_tolerance = 0.05)
    @test !stage_passed(
        [rows[1], merge(stationary, (final_gradnorm = 1e-4,))], M3_POINT_GRID;
        plaquette_tolerance = 0.05)
    @test optimizer_point_safe(rows[2])
    @test !optimizer_point_safe(merge(rows[2], (status = "armijo_failed",)))
    @test !smoke_passed(
        [merge(row, (accepted_steps = 0,)) for row in rows];
        plaquette_tolerance = 0.05)
    @test !smoke_passed(
        [rows[1:2]..., merge(rows[3], (accepted_steps = 0,)), rows[4]];
        plaquette_tolerance = 0.05)
    @test !smoke_passed(
        [rows[1], merge(rows[2], (source_hz = 0.5,)), rows[3], rows[4]];
        plaquette_tolerance = 0.05)
    @test !smoke_passed(
        [rows[1:3]..., merge(rows[4], (max_plaquette_error = 0.2,))];
        plaquette_tolerance = 0.05)
    @test full_evidence_usable(rows; plaquette_tolerance = 0.05)
    @test !full_evidence_usable(
        [rows[1:2]..., merge(rows[3], (status = "armijo_failed",)), rows[4]];
        plaquette_tolerance = 0.05)
    @test !full_evidence_usable(
        [rows[1:2]..., merge(rows[3], (accepted_steps = 0,)), rows[4]];
        plaquette_tolerance = 0.05)
    @test !full_evidence_usable(
        [rows[1:2]..., merge(rows[3], (
            mean_star = 0.9, max_abs_star = 1.1,)), rows[4]];
        plaquette_tolerance = 0.05)

    @test m3_csv_header() ==
          "hz,source_hz,energy_cell,energy_per_spin,warm_energy_cell," *
          "fresh_warm_energy_spread,mz,mean_star,mean_plaquette," *
          "max_star_error,max_plaquette_error,max_abs_star,max_abs_plaquette," *
          "audit_usable,audit_converged_seeds,audit_energy_spread_per_spin," *
          "audit_observable_spread,accepted_steps,attempts,status,final_gradnorm,chi," *
          "ctm_iters,ctm_residual,elapsed_s,checkpoint"

    mktempdir() do directory
        path = joinpath(directory, "mz.svg")
        write_mz_svg(path, rows)
        svg = read(path, String)
        @test occursin("m_z", svg)
        @test occursin("h_z", svg)
        @test !occursin("energy", lowercase(svg))
        @test !occursin("plaquette", lowercase(svg))
    end

    mktempdir() do directory
        csv_path = joinpath(directory, "points.csv")
        initialize_m3_csv(csv_path)
        append_m3_row(csv_path, rows[1])
        lines = readlines(csv_path)
        @test lines[1] == m3_csv_header()
        @test startswith(lines[2], "0.000000,,")
        @test endswith(lines[2], ",point.jld2")
    end
end


@testset "M3 loads the accepted tied M2 checkpoint" begin
    P, V = ℂ^4, ℂ^2
    tensor = normalize!(
        TensorMap(randn(ComplexF64, 4, 16), P, V ⊗ V ⊗ V' ⊗ V'), Inf)
    psi = tied_peps(tensor)
    mktempdir() do directory
        checkpoint = joinpath(directory, "m2.jld2")
        jldsave(checkpoint; tensors = psi.A, step = 86)
        loaded = load_m2_checkpoint(checkpoint; expected_step = 86)
        @test is_tied(loaded)
        @test loaded.A[1, 1] ≈ tensor
        @test_throws ErrorException load_m2_checkpoint(checkpoint; expected_step = 85)

        bad_tensor = normalize!(
            TensorMap(randn(ComplexF64, 4, 81), P, ℂ^3 ⊗ ℂ^3 ⊗ (ℂ^3)' ⊗ (ℂ^3)'), Inf)
        bad_checkpoint = joinpath(directory, "bad-d.jld2")
        jldsave(bad_checkpoint; tensors = tied_peps(bad_tensor).A, step = 86)
        @test_throws ErrorException load_m2_checkpoint(bad_checkpoint; expected_step = 86)
    end
end


@testset "M3 CLI parses bounded run modes" begin
    all_request = parse_m3_args([
        "all", "checkpoint", "point", "chain", "smoke", "full"])
    @test all_request == (
        mode = "all", checkpoint = "checkpoint",
        point_outdir = "point", chain_outdir = "chain",
        smoke_outdir = "smoke", full_outdir = "full", chi = 4)
    chi6_request = parse_m3_args([
        "all", "checkpoint", "point", "chain", "smoke", "full", "6"])
    @test chi6_request == (
        mode = "all", checkpoint = "checkpoint",
        point_outdir = "point", chain_outdir = "chain",
        smoke_outdir = "smoke", full_outdir = "full", chi = 6)
    point_request = parse_m3_args(["point", "checkpoint", "point", "6"])
    @test point_request == (
        mode = "point", checkpoint = "checkpoint", outdir = "point", chi = 6)
    chain_request = parse_m3_args([
        "chain", "checkpoint", "point", "chain", "6"])
    @test chain_request == (
        mode = "chain", checkpoint = "checkpoint",
        prior_outdir = "point", outdir = "chain", chi = 6)
    smoke_request = parse_m3_args([
        "smoke", "checkpoint", "chain", "smoke", "6"])
    @test smoke_request == (
        mode = "smoke", checkpoint = "checkpoint",
        prior_outdir = "chain", outdir = "smoke", chi = 6)
    resume_request = parse_m3_args([
        "resume", "checkpoint", "point", "chain", "smoke", "full", "6"])
    @test resume_request == (
        mode = "resume", checkpoint = "checkpoint",
        point_outdir = "point", chain_outdir = "chain",
        smoke_outdir = "smoke", full_outdir = "full", chi = 6)
    @test_throws ArgumentError parse_m3_args(["all", "checkpoint", "point"])
    @test_throws ArgumentError parse_m3_args(["smoke", "checkpoint", "smoke"])
    @test_throws ArgumentError parse_m3_args(["full", "checkpoint", "full"])
    @test_throws ArgumentError parse_m3_args(["unknown", "checkpoint", "out"])

    mktempdir() do directory
        outdir = joinpath(directory, "new-run")
        prepare_m3_outdir(outdir)
        @test isdir(outdir)
        mark_stage_passed(
            outdir; checkpoint = "checkpoint", chi = 6,
            stage = "point", grid = M3_POINT_GRID)
        @test require_stage_marker(
            outdir; checkpoint = "checkpoint", chi = 6,
            stage = "point", grid = M3_POINT_GRID)
        @test_throws ErrorException require_stage_marker(
            outdir; checkpoint = "other", chi = 6,
            stage = "point", grid = M3_POINT_GRID)
        @test_throws ErrorException require_stage_marker(
            outdir; checkpoint = "checkpoint", chi = 4,
            stage = "point", grid = M3_POINT_GRID)
        @test_throws ErrorException prepare_m3_outdir(outdir)
    end
end
