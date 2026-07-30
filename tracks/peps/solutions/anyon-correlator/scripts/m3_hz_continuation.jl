# Dense tied-tensor AD continuation along h_x = 0 for M3.

using LinearAlgebra, Printf, Random
using TensorKit, PEPSKit, MPSKit, Zygote, JLD2

isdefined(@__MODULE__, :run_tied_mode) ||
    include(joinpath(@__DIR__, "ad_tied_gd.jl"))

struct M3Config
    chi::Int
    ctm_tol::Float64
    ctm_maxiter::Int
    grad_tol::Float64
    max_steps::Int
    plaquette_tolerance::Float64
    armijo_initial_alpha::Float64

    function M3Config(;
            chi::Int = 4,
            ctm_tol::Float64 = 1e-6,
            ctm_maxiter::Int = 80,
            grad_tol::Float64 = 1e-5,
            max_steps::Int = 4,
            plaquette_tolerance::Float64 = 0.05,
            armijo_initial_alpha::Float64 = 0.05)
        chi in (4, 6) || throw(ArgumentError("M3 chi must be 4 or 6"))
        0 < armijo_initial_alpha <= 0.05 || throw(ArgumentError(
            "M3 initial Armijo step must lie in (0, 0.05]"))
        max_steps > 0 || throw(ArgumentError("M3 max_steps must be positive"))
        return new(
            chi, ctm_tol, ctm_maxiter, grad_tol, max_steps,
            plaquette_tolerance, armijo_initial_alpha)
    end
end

function validate_m3_config(config)
    config.chi in (4, 6) || throw(ArgumentError("M3 chi must be 4 or 6"))
    0 < config.armijo_initial_alpha <= 0.05 || throw(ArgumentError(
        "M3 initial Armijo step must lie in (0, 0.05]"))
    config.max_steps > 0 || throw(ArgumentError("M3 max_steps must be positive"))
    return config
end

const M3_SMOKE_GRID = [0.0, 0.10, 0.33, 0.50]
const M3_POINT_GRID = [0.0, 0.10]
const M3_CHAIN_GRID = [0.0, 0.02, 0.05, 0.08, 0.10]
const M3_FULL_GRID = [
    0.0, 0.10, 0.20, 0.28, 0.30, 0.32, 0.33, 0.34, 0.36, 0.40, 0.50]

valid_m3_grid(grid) =
    !isempty(grid) && first(grid) == 0.0 && all(isfinite, grid) && all(diff(grid) .> 0)

finite_m3_row(row) = all(isfinite, (
    row.energy_cell,
    row.energy_per_spin,
    row.mz,
    row.mean_star,
    row.mean_plaquette,
    row.max_star_error,
    row.max_plaquette_error,
    row.max_abs_star,
    row.max_abs_plaquette,
    row.ctm_residual,
))

plaquette_sector_ok(row; tolerance) = row.max_plaquette_error <= tolerance

function summarize_m3_observables(energy, mz, stars, plaquettes, ctm_residual)
    return (
        energy_cell = Float64(energy),
        energy_per_spin = Float64(energy / 8),
        mz = Float64(mz),
        mean_star = Float64(sum(stars) / length(stars)),
        mean_plaquette = Float64(sum(plaquettes) / length(plaquettes)),
        max_star_error = Float64(maximum(abs.(stars .- 1))),
        max_plaquette_error = Float64(maximum(abs.(plaquettes .- 1))),
        max_abs_star = Float64(maximum(abs, stars)),
        max_abs_plaquette = Float64(maximum(abs, plaquettes)),
        ctm_residual = Float64(ctm_residual),
    )
end

function assess_m3_audit(
        results;
        energy_tolerance_per_spin = 1e-3,
        observable_tolerance = 1e-3,
        physical_tolerance = 1e-6,
        plaquette_tolerance = 0.05)
    count = length(results)
    count >= 2 || return (
        usable = false, reason = :insufficient_seeds, converged_seeds = count,
        energy_spread_per_spin = Inf, observable_spread = Inf)

    finite = all(result -> all(isfinite, (
        result.energy, result.mz, result.ctm_residual,
        result.stars..., result.plaquettes...)), results)
    finite || return (
        usable = false, reason = :nonfinite, converged_seeds = count,
        energy_spread_per_spin = Inf, observable_spread = Inf)

    energies = [result.energy for result in results]
    energy_spread = (maximum(energies) - minimum(energies)) / 8
    star_spread = maximum(
        maximum(result.stars[index] for result in results) -
        minimum(result.stars[index] for result in results)
        for index in eachindex(results[1].stars))
    plaquette_spread = maximum(
        maximum(result.plaquettes[index] for result in results) -
        minimum(result.plaquettes[index] for result in results)
        for index in eachindex(results[1].plaquettes))
    mz_values = [result.mz for result in results]
    observable_spread = max(
        star_spread, plaquette_spread, maximum(mz_values) - minimum(mz_values))

    physical = all(result ->
        maximum(abs, result.stars) <= 1 + physical_tolerance &&
        maximum(abs, result.plaquettes) <= 1 + physical_tolerance, results)
    physical || return (
        usable = false, reason = :operator_bound, converged_seeds = count,
        energy_spread_per_spin = energy_spread, observable_spread)

    plaquette_sector = all(result ->
        maximum(abs.(result.plaquettes .- 1)) <= plaquette_tolerance, results)
    plaquette_sector || return (
        usable = false, reason = :plaquette_sector, converged_seeds = count,
        energy_spread_per_spin = energy_spread, observable_spread)

    energy_spread <= energy_tolerance_per_spin || return (
        usable = false, reason = :energy_disagreement, converged_seeds = count,
        energy_spread_per_spin = energy_spread, observable_spread)
    observable_spread <= observable_tolerance || return (
        usable = false, reason = :observable_disagreement, converged_seeds = count,
        energy_spread_per_spin = energy_spread, observable_spread)
    return (
        usable = true, reason = :accepted, converged_seeds = count,
        energy_spread_per_spin = energy_spread, observable_spread)
end

function transition_interval(rows)
    length(rows) >= 2 || throw(ArgumentError("at least two rows are required"))
    slopes = [
        abs((rows[index + 1].mz - rows[index].mz) /
            (rows[index + 1].hz - rows[index].hz))
        for index in 1:(length(rows) - 1)
    ]
    index = argmax(slopes)
    return (rows[index].hz, rows[index + 1].hz)
end

function run_continuation_sequence(initial_state, initial_env, grid, run_point)
    valid_m3_grid(grid) || throw(ArgumentError(
        "field grid must start at zero and increase strictly"))
    state, env = initial_state, initial_env
    source_hz = nothing
    rows = NamedTuple[]
    for hz in grid
        result = run_point(state, env, hz, source_hz)
        state, env = result.state, result.env
        push!(rows, result.row)
        source_hz = hz
    end
    return (; state, env, rows)
end

function smoke_passed(rows; plaquette_tolerance)
    return stage_passed(rows, M3_SMOKE_GRID; plaquette_tolerance)
end

function stage_passed(rows, expected_grid; plaquette_tolerance)
    length(rows) == length(expected_grid) || return false
    [row.hz for row in rows] == expected_grid || return false
    rows[1].source_hz === nothing || return false
    all(rows[index].source_hz == rows[index - 1].hz for index in 2:length(rows)) ||
        return false
    all(optimizer_point_safe, rows) || return false
    return all(row -> continuation_point_safe(row; plaquette_tolerance), rows)
end

function optimizer_point_safe(row)
    row.status == "m2_anchor" && return row.hz == 0
    row.status == "budget" && return row.accepted_steps > 0
    row.status == "stationary" && return row.final_gradnorm <= 1e-5
    return false
end

function prepare_m3_outdir(outdir)
    if isdir(outdir)
        isempty(readdir(outdir)) || error("M3 output directory is not empty: $outdir")
    else
        mkpath(outdir)
    end
    return outdir
end

stage_marker_path(outdir) = joinpath(outdir, "STAGE_PASSED")
stage_grid_text(grid) = join([@sprintf("%.17g", value) for value in grid], ";")

function mark_stage_passed(outdir; checkpoint, chi, stage, grid)
    open(stage_marker_path(outdir), "w") do io
        println(io, "checkpoint=$checkpoint")
        println(io, "chi=$chi")
        println(io, "stage=$stage")
        println(io, "grid=$(stage_grid_text(grid))")
        flush(io)
    end
    return stage_marker_path(outdir)
end

function require_stage_marker(outdir; checkpoint, chi, stage, grid)
    path = stage_marker_path(outdir)
    isfile(path) || error(
        "required prior M3 stage has not passed: $outdir")
    fields = Dict{String, String}()
    for line in readlines(path)
        key, value = split(line, "="; limit = 2)
        fields[key] = value
    end
    expected = Dict(
        "checkpoint" => String(checkpoint),
        "chi" => string(chi),
        "stage" => String(stage),
        "grid" => stage_grid_text(grid),
    )
    fields == expected || error(
        "M3 stage marker provenance mismatch in $outdir")
    return true
end

function continuation_point_safe(row; plaquette_tolerance)
    return finite_m3_row(row) &&
           isfinite(row.warm_energy_cell) &&
           isfinite(row.fresh_warm_energy_spread) &&
           row.audit_usable &&
           row.audit_converged_seeds >= 2 &&
           row.audit_energy_spread_per_spin <= 1e-3 &&
           row.audit_observable_spread <= 1e-3 &&
           row.energy_cell >= m3_energy_floor(row.hz) &&
           row.energy_cell <= -8 + 1e-3 &&
           row.fresh_warm_energy_spread / 8 <= 1e-3 &&
           row.max_abs_star <= 1 + 1e-6 &&
           row.max_abs_plaquette <= 1 + 1e-6 &&
           plaquette_sector_ok(row; tolerance = plaquette_tolerance)
end

function full_evidence_usable(rows; plaquette_tolerance)
    length(rows) >= 2 || return false
    all(row -> continuation_point_safe(row; plaquette_tolerance), rows) || return false
    all(optimizer_point_safe, rows) || return false
    return all(row -> row.max_abs_star <= 1 + 1e-6 &&
                      row.max_abs_plaquette <= 1 + 1e-6, rows)
end

m3_csv_header() =
    "hz,source_hz,energy_cell,energy_per_spin,warm_energy_cell," *
    "fresh_warm_energy_spread,mz,mean_star,mean_plaquette," *
    "max_star_error,max_plaquette_error,max_abs_star,max_abs_plaquette," *
    "audit_usable,audit_converged_seeds,audit_energy_spread_per_spin," *
    "audit_observable_spread," *
    "accepted_steps,attempts,status,final_gradnorm,chi," *
    "ctm_iters,ctm_residual,elapsed_s,checkpoint"

function initialize_m3_csv(path)
    open(path, "w") do io
        println(io, m3_csv_header())
        flush(io)
    end
end

function append_m3_row(path, row)
    source_text = isnothing(row.source_hz) ? "" : @sprintf("%.6f", row.source_hz)
    open(path, "a") do io
        @printf(
            io,
            "%.6f,%s,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%s,%d,%.16e,%.16e,%d,%d,%s,%.16e,%d,%d,%.16e,%.3f,%s\n",
            row.hz, source_text, row.energy_cell, row.energy_per_spin,
            row.warm_energy_cell, row.fresh_warm_energy_spread, row.mz,
            row.mean_star, row.mean_plaquette, row.max_star_error,
            row.max_plaquette_error, row.max_abs_star, row.max_abs_plaquette,
            string(row.audit_usable), row.audit_converged_seeds,
            row.audit_energy_spread_per_spin, row.audit_observable_spread,
            row.accepted_steps, row.attempts,
            String(row.status), row.final_gradnorm, row.chi,
            row.ctm_iters, row.ctm_residual,
            row.elapsed_s, row.checkpoint)
        flush(io)
    end
end

function load_m2_checkpoint(path; expected_step = 86)
    isfile(path) || error("M2 checkpoint does not exist: $path")
    data = load(path)
    haskey(data, "tensors") || error("M2 checkpoint has no tensors: $path")
    haskey(data, "step") || error("M2 checkpoint has no step: $path")
    Int(data["step"]) == expected_step || error(
        "M2 checkpoint step $(data["step"]) does not match expected step $expected_step")
    psi = InfinitePEPS(data["tensors"])
    is_tied(psi) || error("M2 checkpoint tensor is not tied")
    tensor = psi.A[1, 1]
    dim(codomain(tensor)) == 4 || error("M2 checkpoint physical dimension is not 4")
    dim(domain(tensor)) == 16 || error("M2 checkpoint virtual bond dimension is not D=2")
    return psi
end

function write_mz_svg(path, rows)
    isempty(rows) && throw(ArgumentError("cannot plot an empty M3 path"))
    xs = Float64[row.hz for row in rows]
    ys = Float64[row.mz for row in rows]
    width, height = 800.0, 500.0
    left, right, top, bottom = 85.0, 30.0, 55.0, 70.0
    xmin, xmax = minimum(xs), maximum(xs)
    ymin, ymax = min(0.0, minimum(ys)), max(0.05, maximum(ys))
    ypadding = max(0.05 * (ymax - ymin), 0.01)
    ymin, ymax = ymin - ypadding, ymax + ypadding
    sx(x) = left + (x - xmin) / max(xmax - xmin, eps()) * (width - left - right)
    sy(y) = top + (ymax - y) / (ymax - ymin) * (height - top - bottom)
    polyline = join(
        [@sprintf("%.2f,%.2f", sx(x), sy(y)) for (x, y) in zip(xs, ys)], " ")

    open(path, "w") do io
        println(io, "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"800\" height=\"500\" viewBox=\"0 0 800 500\">")
        println(io, "<rect width=\"800\" height=\"500\" fill=\"white\"/>")
        println(io, "<text x=\"400\" y=\"30\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"20\">M3 field polarization m_z(h_z)</text>")
        @printf(io, "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#222\"/>\n", left, height - bottom, width - right, height - bottom)
        @printf(io, "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#222\"/>\n", left, top, left, height - bottom)
        println(io, "<polyline points=\"$polyline\" fill=\"none\" stroke=\"#8f2d2d\" stroke-width=\"2.5\"/>")
        for (x, y) in zip(xs, ys)
            @printf(io, "<circle cx=\"%.2f\" cy=\"%.2f\" r=\"4\" fill=\"#8f2d2d\"/>\n", sx(x), sy(y))
        end
        println(io, "<text x=\"400\" y=\"480\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"15\">h_z</text>")
        println(io, "<text x=\"20\" y=\"250\" text-anchor=\"middle\" transform=\"rotate(-90 20 250)\" font-family=\"sans-serif\" font-size=\"15\">m_z per edge spin</text>")
        println(io, "</svg>")
        flush(io)
    end
end

m3_energy_floor(hz) = -8 - 8abs(hz) - 1e-5

function candidate_contraction_safe(warm_energy, fresh_energy, hz)
    return isfinite(warm_energy) &&
           isfinite(fresh_energy) &&
           fresh_energy >= m3_energy_floor(hz) &&
           fresh_energy <= -8 + 1e-3 &&
           abs(fresh_energy - warm_energy) <= 0.05
end

function m3_armijo_step(
        psi, current_env, energy, gradient, hz, hamiltonian, config;
        evaluate_trial)
    is_tied(psi) || error("M3 optimizer received an untied state")
    direction, gradnorm = tied_descent_direction(gradient; grad_tol = config.grad_tol)
    isfinite(gradnorm) || error("M3 projected gradient norm is non-finite")
    direction === nothing && return (
        status = :stationary, psi, env = current_env, energy,
        alpha = 0.0, gradnorm, info = nothing)

    alpha = config.armijo_initial_alpha
    for _ in 1:12
        tensor = psi.A[1, 1] + alpha * direction.A[1, 1]
        normalize!(tensor, Inf)
        trial = tied_peps(tensor)
        evaluation = try
            evaluate_trial(trial, current_env, hamiltonian, config)
        catch error_value
            if error_value isa CTMRGConvergenceError
                tied_log(@sprintf(
                    "M3 h_z=%.4f alpha=%.4f rejected: %s",
                    hz, alpha, error_value.message))
                alpha /= 2
                continue
            end
            rethrow()
        end
        trial_energy = evaluation.energy
        if isfinite(trial_energy) &&
           trial_energy >= m3_energy_floor(hz) &&
           trial_energy <= -8 + 1e-3 &&
           trial_energy < energy &&
           trial_energy <= energy - 1e-4 * alpha * gradnorm
            return (
                status = :accepted, psi = trial, env = evaluation.env,
                energy = trial_energy, warm_energy = trial_energy,
                alpha, gradnorm, info = evaluation.info)
        end
        alpha /= 2
    end
    return (
        status = :armijo_failed, psi, env = current_env, energy,
        alpha = 0.0, gradnorm, info = nothing)
end

function m3_energy_gradient(psi, env, hamiltonian, config)
    boundary_alg = SimultaneousCTMRG(
        ; tol = config.ctm_tol, maxiter = config.ctm_maxiter, verbosity = 0)
    gradient_alg = PEPSKit.GradientAlgorithm(
        ; alg = :FixedPointGradient, tol = config.grad_tol, maxiter = 10)
    energy, gradients = withgradient(psi) do state
        env_ad, _ = PEPSKit.hook_pullback(
            leading_boundary, env, state, boundary_alg; alg_rrule = gradient_alg)
        cost_function(state, env_ad, hamiltonian)
    end
    gradient = only(gradients)
    value = real(energy)
    isfinite(value) || error("M3 AD energy is non-finite")
    isfinite(peps_frobnorm(gradient)) || error("M3 AD gradient is non-finite")
    return value, gradient
end

function m3_evaluate_trial(trial, current_env, hamiltonian, config)
    env, info = converge_tied_environment(
        trial, config.chi; tol = config.ctm_tol, maxiter = config.ctm_maxiter,
        initial_env = current_env)
    energy = real(cost_function(trial, env, hamiltonian))
    return (; env, info, energy)
end

function converge_m3_fresh_environment(
        psi, config;
        seeds = (TIED_CTM_SEED, 1, 2),
        converge = converge_tied_environment)
    isempty(seeds) && throw(ArgumentError("at least one fresh CTMRG seed is required"))
    last_error = nothing
    for seed in seeds
        try
            env, info = converge(
                psi, config.chi; tol = config.ctm_tol,
                maxiter = config.ctm_maxiter, seed)
            return env, info, seed
        catch error_value
            error_value isa CTMRGConvergenceError || rethrow()
            last_error = error_value
            tied_log("fresh CTMRG seed=$seed rejected: $(error_value.message)")
        end
    end
    throw(last_error)
end

function initialize_m3_warm_environment(
        psi, env, config;
        converge = converge_tied_environment)
    !isnothing(env) && return env, nothing
    return converge(
        psi, config.chi; tol = config.ctm_tol,
        maxiter = config.ctm_maxiter, seed = TIED_CTM_SEED)
end

function m3_field_sum_operator()
    lattice = fill(TIED_UP, 2, 2)
    operator = empty_localoperator(lattice)
    unit_field = field_op(0.0, 1.0, TIED_UP)
    for row in 1:2, column in 1:2
        PEPSKit.add_term!(operator, [CartesianIndex(row, column)], unit_field)
    end
    return operator
end

function evaluate_m3_observables(psi, env, hamiltonian, hz, info)
    energy = real(expectation_value(psi, hamiltonian, env))
    h0_energy, stars, plaquettes = evaluate_tied_h0(psi, env)
    field_energy = real(expectation_value(psi, m3_field_sum_operator(), env))
    mz = -field_energy / 8
    expected_energy = h0_energy + hz * field_energy
    isapprox(energy, expected_energy; atol = 1e-8, rtol = 1e-8) || error(
        @sprintf(
            "finite-field energy mismatch at h_z=%.4f: H=%.12f, H0+h_z*field=%.12f",
            hz, energy, expected_energy))
    abs(mz) <= 1 + 1e-5 || error(
        @sprintf("unphysical m_z=%+.8f at h_z=%.4f", mz, hz))
    summary = summarize_m3_observables(
        energy, mz, stars, plaquettes, info.convergence_error)
    finite_m3_row(summary) || error("M3 final observables are non-finite")
    return summary, stars, plaquettes
end

function evaluate_m3_seed(psi, hamiltonian, hz, config, seed)
    env, info = converge_tied_environment(
        psi, config.chi; tol = config.ctm_tol,
        maxiter = config.ctm_maxiter, seed)
    summary, stars, plaquettes = evaluate_m3_observables(
        psi, env, hamiltonian, hz, info)
    return (
        seed, env, info,
        energy = summary.energy_cell,
        stars,
        plaquettes,
        mz = summary.mz,
        ctm_residual = summary.ctm_residual,
        summary,
    )
end

function audit_m3_point(
        psi, hamiltonian, hz, config;
        seeds = (TIED_CTM_SEED, 1, 2),
        evaluate_seed = evaluate_m3_seed)
    results = NamedTuple[]
    failed_seeds = Int[]
    for seed in seeds
        try
            push!(results, evaluate_seed(psi, hamiltonian, hz, config, seed))
        catch error_value
            error_value isa CTMRGConvergenceError || rethrow()
            push!(failed_seeds, seed)
            tied_log("M3 audit h_z=$hz seed=$seed rejected: $(error_value.message)")
        end
    end
    verdict = assess_m3_audit(
        results; plaquette_tolerance = config.plaquette_tolerance)
    representative = isempty(results) ? nothing : first(results)
    return (; verdict, results, failed_seeds, representative)
end

function write_m3_audit_csv(path, audit)
    successful = Dict(result.seed => result for result in audit.results)
    seeds = sort(vcat(collect(keys(successful)), audit.failed_seeds))
    open(path, "w") do io
        println(
            io,
            "seed,status,energy,mz,star_1,star_2,star_3,star_4," *
            "plaquette_1,plaquette_2,plaquette_3,plaquette_4," *
            "max_abs_star,max_abs_plaquette,ctm_residual")
        for seed in seeds
            if haskey(successful, seed)
                result = successful[seed]
                @printf(
                    io,
                    "%d,converged,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e\n",
                    seed, result.energy, result.mz, result.stars...,
                    result.plaquettes..., maximum(abs, result.stars),
                    maximum(abs, result.plaquettes), result.ctm_residual)
            else
                @printf(io, "%d,failed,,,,,,,,,,,,,\n", seed)
            end
        end
        flush(io)
    end
end

function m3_point_tag(hz)
    return "hz_" * replace(@sprintf("%.3f", hz), "." => "p")
end

function save_m3_checkpoint(
        path, psi, hz, source_hz, config, status, accepted_steps, attempts,
        summary, stars, plaquettes)
    jldsave(
        path;
        tensors = psi.A,
        hx = 0.0,
        hz,
        source_hz,
        D = 2,
        chi = config.chi,
        ctm_tol = config.ctm_tol,
        ctm_maxiter = config.ctm_maxiter,
        grad_tol = config.grad_tol,
        max_steps = config.max_steps,
        optimizer_status = String(status),
        accepted_steps,
        attempts,
        final_gradnorm = summary.final_gradnorm,
        energy_cell = summary.energy_cell,
        energy_per_spin = summary.energy_per_spin,
        warm_energy_cell = summary.warm_energy_cell,
        fresh_warm_energy_spread = summary.fresh_warm_energy_spread,
        mz = summary.mz,
        max_abs_star = summary.max_abs_star,
        max_abs_plaquette = summary.max_abs_plaquette,
        audit_usable = summary.audit_usable,
        audit_converged_seeds = summary.audit_converged_seeds,
        audit_energy_spread_per_spin = summary.audit_energy_spread_per_spin,
        audit_observable_spread = summary.audit_observable_spread,
        stars,
        plaquettes,
        ctm_residual = summary.ctm_residual)
end

function run_m3_point(psi, warm_env, hz, source_hz, config, outdir)
    hamiltonian, _ = toric_code_hamiltonian(0.0, hz; P = TIED_UP)
    accepted_steps = 0
    attempts = 0
    status = hz == 0 ? :m2_anchor : :budget
    final_gradnorm = 0.0
    env = warm_env

    env, initial_info = initialize_m3_warm_environment(psi, env, config)
    if !isnothing(initial_info)
        tied_log(@sprintf(
            "M3 h_z=%.4f initial warm CTMRG: iterations=%d residual=%.2e",
            hz, ctm_iterations(initial_info), initial_info.convergence_error))
    end

    if hz > 0
        while accepted_steps < config.max_steps
            attempts += 1
            current_energy, gradient = m3_energy_gradient(psi, env, hamiltonian, config)
            result = m3_armijo_step(
                psi, env, current_energy, gradient, hz, hamiltonian, config;
                evaluate_trial = m3_evaluate_trial)
            final_gradnorm = result.gradnorm
            if result.status != :accepted
                status = result.status
                tied_log(@sprintf(
                    "M3 h_z=%.4f attempt=%d status=%s gradnorm=%.3e",
                    hz, attempts, result.status, result.gradnorm))
                break
            end
            psi, env = result.psi, result.env
            accepted_steps += 1
            tied_log(@sprintf(
                "M3 h_z=%.4f step=%d warm=%+.10f gradnorm=%.3e alpha=%.4f residual=%.2e",
                hz, accepted_steps, result.energy,
                result.gradnorm, result.alpha, result.info.convergence_error))
            step_path = joinpath(
                outdir, @sprintf("%s_step%02d.jld2", m3_point_tag(hz), accepted_steps))
            jldsave(
                step_path;
                tensors = psi.A, hx = 0.0, hz, source_hz, D = 2,
                chi = config.chi, accepted_steps, attempts,
                energy = result.energy, warm_energy = result.warm_energy,
                gradnorm = result.gradnorm,
                alpha = result.alpha, ctm_residual = result.info.convergence_error)
        end
    end

    warm_energy = real(cost_function(psi, env, hamiltonian))
    audit = audit_m3_point(psi, hamiltonian, hz, config)
    write_m3_audit_csv(
        joinpath(outdir, "$(m3_point_tag(hz))_audit.csv"), audit)
    isnothing(audit.representative) && error(
        @sprintf("M3 audit found no converged fresh environment at h_z=%.4f", hz))
    representative = audit.representative
    fresh_summary = representative.summary
    stars, plaquettes = representative.stars, representative.plaquettes
    fresh_info, fresh_seed = representative.info, representative.seed
    summary = merge(fresh_summary, (
        warm_energy_cell = Float64(warm_energy),
        fresh_warm_energy_spread = Float64(abs(fresh_summary.energy_cell - warm_energy)),
        audit_usable = audit.verdict.usable,
        audit_converged_seeds = audit.verdict.converged_seeds,
        audit_energy_spread_per_spin = audit.verdict.energy_spread_per_spin,
        audit_observable_spread = audit.verdict.observable_spread,
        final_gradnorm = Float64(final_gradnorm),
    ))
    checkpoint = joinpath(outdir, "$(m3_point_tag(hz))_final.jld2")
    save_m3_checkpoint(
        checkpoint, psi, hz, source_hz, config, status, accepted_steps, attempts,
        summary, stars, plaquettes)
    row = merge(summary, (
        hz = Float64(hz),
        source_hz = isnothing(source_hz) ? nothing : Float64(source_hz),
        accepted_steps,
        attempts,
        status = String(status),
        final_gradnorm = summary.final_gradnorm,
        chi = config.chi,
        ctm_iters = ctm_iterations(fresh_info),
        elapsed_s = Float64(time() - TIED_START[]),
        checkpoint,
    ))
    tied_log(@sprintf(
        "M3 h_z=%.4f final: E/N=%+.8f m_z=%.8f mean(A)=%.8f mean(B)=%.8f max|B-1|=%.2e fresh-warm=%.2e audit=%s seeds=%d seed=%d status=%s",
        hz, row.energy_per_spin, row.mz, row.mean_star, row.mean_plaquette,
        row.max_plaquette_error, row.fresh_warm_energy_spread,
        audit.verdict.reason, audit.verdict.converged_seeds, fresh_seed, row.status))
    return (; state = psi, env, row)
end

function run_m3_path(checkpoint, grid, config, outdir)
    validate_m3_config(config)
    valid_m3_grid(grid) || throw(ArgumentError(
        "M3 field grid must start at zero and increase strictly"))
    prepare_m3_outdir(outdir)
    csv_path = joinpath(outdir, "m3_hz_points.csv")
    initialize_m3_csv(csv_path)
    initial = load_m2_checkpoint(checkpoint)
    TIED_START[] = time()
    tied_log(
        "M3 path start: D=2 chi=$(config.chi) max_steps=$(config.max_steps) " *
        "ctm_tol=$(config.ctm_tol) points=$(length(grid))")

    run_point = function (state, environment, hz, source_hz)
        result = run_m3_point(
            state, environment, hz, source_hz, config, outdir)
        append_m3_row(csv_path, result.row)
        optimizer_point_safe(result.row) || error(
            @sprintf(
                "unsafe optimizer status at h_z=%.4f: status=%s accepted=%d gradnorm=%.3e",
                hz, result.row.status, result.row.accepted_steps,
                result.row.final_gradnorm))
        continuation_point_safe(
            result.row; plaquette_tolerance = config.plaquette_tolerance) || error(
            @sprintf(
                "unsafe continuation at h_z=%.4f: E_cell=%+.8f spread=%.3e max|B-1|=%.3e",
                hz, result.row.energy_cell, result.row.fresh_warm_energy_spread,
                result.row.max_plaquette_error))
        return result
    end
    result = run_continuation_sequence(initial, nothing, grid, run_point)
    write_mz_svg(joinpath(outdir, "m3_mz_vs_hz.svg"), result.rows)
    return merge(result, (; csv_path))
end

function parse_m3_args(args)
    isempty(args) && throw(ArgumentError(
        "usage: m3_hz_continuation.jl point CHECKPOINT OUTDIR [CHI]"))
    mode = args[1]
    if mode == "all" || mode == "resume"
        length(args) in (6, 7) || throw(ArgumentError(
            "usage: m3_hz_continuation.jl $mode CHECKPOINT POINT_OUTDIR CHAIN_OUTDIR SMOKE_OUTDIR FULL_OUTDIR [CHI]"))
        chi = length(args) == 7 ? parse(Int, args[7]) : 4
        chi in (4, 6) || throw(ArgumentError("M3 chi must be 4 or 6"))
        return (
            mode, checkpoint = args[2], point_outdir = args[3],
            chain_outdir = args[4], smoke_outdir = args[5],
            full_outdir = args[6], chi)
    elseif mode == "point"
        length(args) in (3, 4) || throw(ArgumentError(
            "usage: m3_hz_continuation.jl $mode CHECKPOINT OUTDIR"))
        chi = length(args) == 4 ? parse(Int, args[4]) : 4
        chi in (4, 6) || throw(ArgumentError("M3 chi must be 4 or 6"))
        return (mode, checkpoint = args[2], outdir = args[3], chi)
    elseif mode == "chain" || mode == "smoke"
        length(args) in (4, 5) || throw(ArgumentError(
            "usage: m3_hz_continuation.jl $mode CHECKPOINT PRIOR_OUTDIR OUTDIR [CHI]"))
        chi = length(args) == 5 ? parse(Int, args[5]) : 4
        chi in (4, 6) || throw(ArgumentError("M3 chi must be 4 or 6"))
        return (
            mode, checkpoint = args[2], prior_outdir = args[3],
            outdir = args[4], chi)
    end
    throw(ArgumentError("unknown M3 mode: $mode"))
end

function run_repair_remaining(request, config)
    require_stage_marker(
        request.point_outdir; checkpoint = request.checkpoint, chi = config.chi,
        stage = "point", grid = M3_POINT_GRID)
    chain = run_m3_path(
        request.checkpoint, M3_CHAIN_GRID, config, request.chain_outdir)
    chain_passed = stage_passed(
        chain.rows, M3_CHAIN_GRID;
        plaquette_tolerance = config.plaquette_tolerance)
    tied_log(chain_passed ? "M3 REPAIR CHAIN PASSED" : "M3 REPAIR CHAIN FAILED")
    chain_passed || return false
    mark_stage_passed(
        request.chain_outdir; checkpoint = request.checkpoint, chi = config.chi,
        stage = "chain", grid = M3_CHAIN_GRID)

    smoke = run_m3_path(
        request.checkpoint, M3_SMOKE_GRID, config, request.smoke_outdir)
    smoke_ok = smoke_passed(
        smoke.rows; plaquette_tolerance = config.plaquette_tolerance)
    tied_log(smoke_ok ? "M3 REPAIR SMOKE PASSED" : "M3 REPAIR SMOKE FAILED")
    smoke_ok || return false
    mark_stage_passed(
        request.smoke_outdir; checkpoint = request.checkpoint, chi = config.chi,
        stage = "smoke", grid = M3_SMOKE_GRID)

    full = run_m3_path(
        request.checkpoint, M3_FULL_GRID, config, request.full_outdir)
    usable = full_evidence_usable(
        full.rows; plaquette_tolerance = config.plaquette_tolerance)
    interval = transition_interval(full.rows)
    tied_log(@sprintf(
        "M3 REPAIR FULL COMPLETED: evidence=%s steepest m_z interval h_z=[%.4f, %.4f]",
        usable ? "usable" : "unresolved", interval[1], interval[2]))
    if usable
        mark_stage_passed(
            request.full_outdir; checkpoint = request.checkpoint, chi = config.chi,
            stage = "full", grid = M3_FULL_GRID)
        durable_plot = normpath(joinpath(
            @__DIR__, "..", "figures", "m3_mz_vs_hz.svg"))
        write_mz_svg(durable_plot, full.rows)
    end
    return usable
end

function m3_main(args = ARGS)
    request = parse_m3_args(args)
    mode = request.mode
    config = M3Config(chi = request.chi)
    if mode == "point"
        result = run_m3_path(
            request.checkpoint, M3_POINT_GRID, config, request.outdir)
        passed = stage_passed(
            result.rows, M3_POINT_GRID;
            plaquette_tolerance = config.plaquette_tolerance)
        tied_log(passed ? "M3 REPAIR POINT PASSED" : "M3 REPAIR POINT FAILED")
        passed && mark_stage_passed(
            request.outdir; checkpoint = request.checkpoint, chi = config.chi,
            stage = "point", grid = M3_POINT_GRID)
        return passed
    elseif mode == "chain"
        require_stage_marker(
            request.prior_outdir; checkpoint = request.checkpoint, chi = config.chi,
            stage = "point", grid = M3_POINT_GRID)
        result = run_m3_path(
            request.checkpoint, M3_CHAIN_GRID, config, request.outdir)
        passed = stage_passed(
            result.rows, M3_CHAIN_GRID;
            plaquette_tolerance = config.plaquette_tolerance)
        tied_log(passed ? "M3 REPAIR CHAIN PASSED" : "M3 REPAIR CHAIN FAILED")
        passed && mark_stage_passed(
            request.outdir; checkpoint = request.checkpoint, chi = config.chi,
            stage = "chain", grid = M3_CHAIN_GRID)
        return passed
    elseif mode == "smoke"
        require_stage_marker(
            request.prior_outdir; checkpoint = request.checkpoint, chi = config.chi,
            stage = "chain", grid = M3_CHAIN_GRID)
        result = run_m3_path(
            request.checkpoint, M3_SMOKE_GRID, config, request.outdir)
        passed = smoke_passed(
            result.rows; plaquette_tolerance = config.plaquette_tolerance)
        tied_log(passed ? "M3 REPAIR SMOKE PASSED" : "M3 REPAIR SMOKE FAILED")
        passed && mark_stage_passed(
            request.outdir; checkpoint = request.checkpoint, chi = config.chi,
            stage = "smoke", grid = M3_SMOKE_GRID)
        return passed
    elseif mode == "all"
        point = run_m3_path(
            request.checkpoint, M3_POINT_GRID, config, request.point_outdir)
        passed = stage_passed(
            point.rows, M3_POINT_GRID;
            plaquette_tolerance = config.plaquette_tolerance)
        tied_log(passed ? "M3 REPAIR POINT PASSED" : "M3 REPAIR POINT FAILED")
        passed || return false
        mark_stage_passed(
            request.point_outdir; checkpoint = request.checkpoint, chi = config.chi,
            stage = "point", grid = M3_POINT_GRID)
        return run_repair_remaining(request, config)
    elseif mode == "resume"
        return run_repair_remaining(request, config)
    end
    error("unreachable M3 mode: $mode")
end

if abspath(PROGRAM_FILE) == @__FILE__
    code = try
        m3_main() ? 0 : 1
    catch error_value
        showerror(stderr, error_value, catch_backtrace())
        println(stderr)
        flush(stderr)
        2
    end
    exit(code)
end
