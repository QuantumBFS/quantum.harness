# Dense tied-tensor AD optimizer for the zero-field toric-code M2 gates.
# Numerical modes are intentionally bounded; see mode_config below.

using LinearAlgebra, Printf, Random
using TensorKit, PEPSKit, MPSKit, Zygote, JLD2

isdefined(@__MODULE__, :toric_code_hamiltonian) ||
    include(joinpath(@__DIR__, "tc_peps.jl"))
isdefined(@__MODULE__, :tied_peps) ||
    include(joinpath(@__DIR__, "ad_tied_core.jl"))

const TIED_UP = UPSPACE
const TIED_UV = uspace(2)
const TIED_H0, _ = toric_code_hamiltonian(0.0, 0.0; P = TIED_UP)
const TIED_CTM_SEED = 424242
const TIED_START = Ref(time())

struct CTMRGConvergenceError <: Exception
    message::String
end

Base.showerror(io::IO, error_value::CTMRGConvergenceError) =
    print(io, error_value.message)

Base.@kwdef struct ModeConfig
    name::String
    chi::Int
    ctm_tol::Float64
    ctm_maxiter::Int
    grad_tol::Float64
    max_steps::Int
    require_accepts::Int
    final_chi::Int
end

function mode_config(mode)
    mode == "exact-smoke" && return ModeConfig(
        name = mode, chi = 4, ctm_tol = 1e-10, ctm_maxiter = 300,
        grad_tol = 1e-8, max_steps = 2, require_accepts = 0, final_chi = 4)
    mode == "random-smoke" && return ModeConfig(
        name = mode, chi = 4, ctm_tol = 1e-6, ctm_maxiter = 50,
        grad_tol = 1e-5, max_steps = 20, require_accepts = 20, final_chi = 4)
    mode == "run" && return ModeConfig(
        name = mode, chi = 12, ctm_tol = 1e-8, ctm_maxiter = 150,
        grad_tol = 1e-7, max_steps = 20, require_accepts = 0, final_chi = 20)
    throw(ArgumentError("unknown mode: $mode"))
end

function continuation_config(max_steps; chi = 4)
    max_steps > 0 || throw(ArgumentError("continuation steps must be positive"))
    chi > 0 || throw(ArgumentError("continuation chi must be positive"))
    return ModeConfig(
        name = "random-continue", chi = chi, ctm_tol = 1e-6, ctm_maxiter = 50,
        grad_tol = 1e-5, max_steps = max_steps,
        require_accepts = max_steps, final_chi = chi)
end

global_step(step_offset, local_step) = step_offset + local_step

function requested_modes(mode)
    mode == "smoke" && return ("exact-smoke", "random-smoke")
    mode_config(mode)
    return (mode,)
end

record_stabilizers_each_step(config) =
    config.name == "random-smoke" || config.name == "random-continue"

tied_log(message) = begin
    println(@sprintf("[%8.1f s] %s", time() - TIED_START[], message))
    flush(stdout)
end

function random_tied_peps(seed)
    Random.seed!(seed)
    data6 = randn(ComplexF64, 2, 2, 2, 2, 2, 2)
    data = reshape(reshape(data6, 4, 2, 2, 2, 2), 4, 16)
    tensor = normalize!(
        TensorMap(data, TIED_UP, TIED_UV ⊗ TIED_UV ⊗ TIED_UV' ⊗ TIED_UV'), Inf)
    return tied_peps(tensor)
end

exact_tied_peps() = tied_peps(exact_peps_tensor(TIED_UP, TIED_UV))

ctm_iterations(info) = length(info.contraction_metrics)

function converge_tied_environment(
        psi, chi; tol, maxiter, seed = TIED_CTM_SEED, initial_env = nothing)
    if isnothing(initial_env)
        Random.seed!(seed)
        env0 = CTMRGEnv(randn, ComplexF64, psi, uenv(chi))
    else
        env0 = initial_env
    end
    alg = SimultaneousCTMRG(; tol, maxiter, verbosity = 0)
    env, info = leading_boundary(env0, psi, alg)
    isfinite(info.convergence_error) || throw(
        CTMRGConvergenceError("CTMRG residual is non-finite"))
    info.converged || throw(CTMRGConvergenceError(
        "CTMRG did not converge at chi=$chi after $(ctm_iterations(info)) iterations " *
        "(residual=$(info.convergence_error))"))
    return env, info
end

function evaluate_tied_h0(psi, env)
    energy = real(expectation_value(psi, TIED_H0, env))
    lattice = fill(TIED_UP, 2, 2)
    sop, pop = star_op(1.0, TIED_UP), plaq_op(1.0, TIED_UP)
    stars, plaquettes = Float64[], Float64[]
    for r in 1:2, c in 1:2
        hs = empty_localoperator(lattice)
        PEPSKit.add_term!(
            hs,
            [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)],
            sop)
        push!(stars, -real(expectation_value(psi, hs, env)))

        hp = empty_localoperator(lattice)
        PEPSKit.add_term!(
            hp,
            [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)],
            pop)
        push!(plaquettes, -real(expectation_value(psi, hp, env)))
    end
    all(isfinite, (energy, stars..., plaquettes...)) ||
        error("energy or stabilizer is non-finite")
    return energy, stars, plaquettes
end

physical_observables(energy, stars, plaquettes; tol = 1e-6) =
    energy >= -8 - tol &&
    all(value -> abs(value) <= 1 + tol, (stars..., plaquettes...))

meets_h0_target(energy, stars, plaquettes; tol = 1e-6) =
    abs(energy / 8 + 1) <= tol &&
    all(value -> abs(value - 1) <= tol, (stars..., plaquettes...))

continuation_passed(energy, stars, plaquettes) =
    physical_observables(energy, stars, plaquettes) &&
    meets_h0_target(energy, stars, plaquettes)

function tied_energy_gradient(psi, env, config)
    boundary_alg = SimultaneousCTMRG(
        ; tol = config.ctm_tol, maxiter = config.ctm_maxiter, verbosity = 0)
    gradient_alg = PEPSKit.GradientAlgorithm(
        ; alg = :FixedPointGradient, tol = config.grad_tol, maxiter = 10)
    energy, gradients = withgradient(psi) do state
        env_ad, _ = PEPSKit.hook_pullback(
            leading_boundary, env, state, boundary_alg; alg_rrule = gradient_alg)
        cost_function(state, env_ad, TIED_H0)
    end
    gradient = only(gradients)
    value = real(energy)
    isfinite(value) || error("AD energy is non-finite")
    isfinite(peps_frobnorm(gradient)) || error("AD gradient is non-finite")
    return value, gradient
end

function evaluate_armijo_trial(trial, current_env, config)
    env, info = converge_tied_environment(
        trial, config.chi; tol = config.ctm_tol, maxiter = config.ctm_maxiter,
        initial_env = current_env)
    energy = real(cost_function(trial, env, TIED_H0))
    return (; env, info, energy)
end

function tied_armijo_step(
        psi, current_env, energy, gradient, config;
        evaluate_trial = evaluate_armijo_trial)
    is_tied(psi) || error("optimizer received an untied state")
    direction, gradnorm = tied_descent_direction(gradient; grad_tol = config.grad_tol)
    isfinite(gradnorm) || error("projected gradient norm is non-finite")
    direction === nothing && return (
        status = :stationary, psi, env = nothing, energy,
        alpha = 0.0, gradnorm, info = nothing)

    alpha = 0.3
    for _ in 1:12
        tensor = psi.A[1, 1] + alpha * direction.A[1, 1]
        normalize!(tensor, Inf)
        trial = tied_peps(tensor)
        is_tied(trial) || error("Armijo trial broke tensor tying")
        evaluation = try
            evaluate_trial(trial, current_env, config)
        catch error_value
            if error_value isa CTMRGConvergenceError
                tied_log(@sprintf(
                    "Armijo alpha=%.4f rejected: %s", alpha, error_value.message))
                alpha /= 2
                continue
            end
            rethrow()
        end
        env, info, trial_energy = evaluation.env, evaluation.info, evaluation.energy
        isfinite(trial_energy) || error("Armijo trial energy is non-finite")
        if trial_energy >= -8 - 1e-6 &&
           trial_energy < energy &&
           trial_energy <= energy - 1e-4 * alpha * gradnorm
            return (
                status = :accepted, psi = trial, env, energy = trial_energy,
                alpha, gradnorm, info)
        end
        alpha /= 2
    end
    return (
        status = :armijo_failed, psi, env = nothing, energy,
        alpha = 0.0, gradnorm, info = nothing)
end

function progress_path(config, outdir)
    filename = config.name == "run" ? "energy_convergence.csv" :
               "$(config.name)_energy.csv"
    return joinpath(outdir, filename)
end

function initialize_progress(path)
    open(path, "w") do io
        println(io, "phase,mode,step,chi,E_cell,E_per_spin,gradnorm,alpha,ctm_iters,ctm_residual,elapsed_s")
    end
end

function make_record(phase, mode, step, chi, energy, gradnorm, alpha, info)
    return (
        phase = String(phase), mode = String(mode), step = Int(step), chi = Int(chi),
        energy_cell = Float64(energy), energy_per_spin = Float64(energy / 8),
        gradnorm = Float64(gradnorm), alpha = Float64(alpha),
        ctm_iters = ctm_iterations(info),
        ctm_residual = Float64(info.convergence_error),
        elapsed_s = Float64(time() - TIED_START[]))
end

function append_record!(history, path, record)
    push!(history, record)
    open(path, "a") do io
        @printf(
            io, "%s,%s,%d,%d,%.16e,%.16e,%.16e,%.16e,%d,%.16e,%.3f\n",
            record.phase, record.mode, record.step, record.chi,
            record.energy_cell, record.energy_per_spin, record.gradnorm,
            record.alpha, record.ctm_iters, record.ctm_residual, record.elapsed_s)
        flush(io)
    end
end

function initialize_stabilizer_trace(path)
    open(path, "w") do io
        println(io, "step,chi,kind,row,column,value,error_from_one")
    end
end

function append_stabilizer_trace(path, step, chi, stars, plaquettes)
    open(path, "a") do io
        for (kind, values) in (("star", stars), ("plaquette", plaquettes))
            index = 1
            for r in 1:2, c in 1:2
                value = values[index]
                @printf(
                    io, "%d,%d,%s,%d,%d,%.16e,%.16e\n",
                    step, chi, kind, r, c, value, abs(value - 1))
                index += 1
            end
        end
        flush(io)
    end
end

function optimize_tied(initial, config, outdir; step_offset = 0)
    path = progress_path(config, outdir)
    initialize_progress(path)
    history = NamedTuple[]
    psi = initial
    env, info = converge_tied_environment(
        psi, config.chi; tol = config.ctm_tol, maxiter = config.ctm_maxiter)
    trace_path = joinpath(outdir, "$(config.name)_stabilizer_trace.csv")
    if record_stabilizers_each_step(config)
        initialize_stabilizer_trace(trace_path)
        initial_energy, stars, plaquettes = evaluate_tied_h0(psi, env)
        physical_observables(initial_energy, stars, plaquettes) || error(
            "initial state violates toric-code energy or stabilizer bounds")
        append_stabilizer_trace(
            trace_path, global_step(step_offset, 0), config.chi, stars, plaquettes)
    else
        initial_energy = real(cost_function(psi, env, TIED_H0))
    end
    append_record!(
        history, path,
        make_record("optimization", config.name, global_step(step_offset, 0), config.chi,
                    initial_energy, 0.0, 0.0, info))
    tied_log(@sprintf(
        "%s init: E_cell=%+.10f, CTMRG iters=%d, residual=%.2e",
        config.name, initial_energy, ctm_iterations(info), info.convergence_error))

    accepted = 0
    attempts = 0
    status = :budget
    while accepted < config.max_steps
        attempts += 1
        energy, gradient = tied_energy_gradient(psi, env, config)
        result = tied_armijo_step(psi, env, energy, gradient, config)
        if result.status == :stationary
            status = :stationary
            tied_log(@sprintf(
                "%s attempt %d: stationary, projected gradnorm=%.3e",
                config.name, attempts, result.gradnorm))
            break
        elseif result.status == :armijo_failed
            status = :armijo_failed
            tied_log(@sprintf(
                "%s attempt %d: Armijo failed, projected gradnorm=%.3e",
                config.name, attempts, result.gradnorm))
            break
        end

        step = global_step(step_offset, accepted + 1)
        if record_stabilizers_each_step(config)
            _, stars, plaquettes = evaluate_tied_h0(result.psi, result.env)
            if !physical_observables(result.energy, stars, plaquettes)
                status = :physical_bound_failed
                tied_log(@sprintf(
                    "%s candidate step %d rejected: E_cell=%+.10f, max|A|=%.8f, max|B|=%.8f",
                    config.name, step, result.energy,
                    maximum(abs, stars), maximum(abs, plaquettes)))
                break
            end
        end

        psi, env = result.psi, result.env
        accepted += 1
        record = make_record(
            "optimization", config.name, step, config.chi,
            result.energy, result.gradnorm, result.alpha, result.info)
        append_record!(history, path, record)
        tied_log(@sprintf(
            "%s step %d: E_cell=%+.10f, gradnorm=%.3e, alpha=%.4f, CTMRG iters=%d, residual=%.2e",
            config.name, step, result.energy, result.gradnorm, result.alpha,
            record.ctm_iters, record.ctm_residual))
        jldsave(
            joinpath(outdir, @sprintf("%s_step%03d.jld2", config.name, step));
            tensors = psi.A, mode = config.name, step,
            energy = result.energy, gradnorm = result.gradnorm,
            alpha = result.alpha, chi = config.chi)
        if record_stabilizers_each_step(config)
            append_stabilizer_trace(
                trace_path, step, config.chi, stars, plaquettes)
            tied_log(@sprintf(
                "%s step %d stabilizers: mean(A)=%.6f, mean(B)=%.6f",
                config.name, step, sum(stars) / 4, sum(plaquettes) / 4))
        end
    end
    return (; psi, env, history, accepted, attempts, status, path, step_offset)
end

function write_stabilizers(path, evaluations)
    open(path, "w") do io
        println(io, "phase,chi,kind,row,column,value,error_from_one")
        for evaluation in evaluations
            for (kind, values) in (("star", evaluation.stars),
                                   ("plaquette", evaluation.plaquettes))
                index = 1
                for r in 1:2, c in 1:2
                    value = values[index]
                    @printf(
                        io, "%s,%d,%s,%d,%d,%.16e,%.16e\n",
                        evaluation.phase, evaluation.chi, kind, r, c,
                        value, abs(value - 1))
                    index += 1
                end
            end
        end
        flush(io)
    end
end

function write_energy_svg(path, history)
    points = [record for record in history if record.phase == "optimization"]
    isempty(points) && return
    xs = Float64[record.step for record in points]
    ys = Float64[record.energy_per_spin for record in points]
    width, height = 800.0, 500.0
    left, right, top, bottom = 85.0, 30.0, 55.0, 70.0
    xmin, xmax = 0.0, max(maximum(xs), 1.0)
    raw_min, raw_max = min(minimum(ys), -1.0), max(maximum(ys), -1.0)
    padding = max(0.05 * (raw_max - raw_min), 0.02)
    ymin, ymax = raw_min - padding, raw_max + padding
    sx(x) = left + (x - xmin) / (xmax - xmin) * (width - left - right)
    sy(y) = top + (ymax - y) / (ymax - ymin) * (height - top - bottom)
    polyline = join([@sprintf("%.2f,%.2f", sx(x), sy(y)) for (x, y) in zip(xs, ys)], " ")

    open(path, "w") do io
        println(io, "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"800\" height=\"500\" viewBox=\"0 0 800 500\">")
        println(io, "<rect width=\"800\" height=\"500\" fill=\"white\"/>")
        println(io, "<text x=\"400\" y=\"30\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"20\">Toric code h=0: dense tied-tensor AD</text>")
        @printf(io, "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#222\"/>\n", left, height - bottom, width - right, height - bottom)
        @printf(io, "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#222\"/>\n", left, top, left, height - bottom)
        @printf(io, "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#b13a32\" stroke-dasharray=\"7 5\"/>\n", left, sy(-1.0), width - right, sy(-1.0))
        println(io, "<text x=\"765\" y=\"$(sy(-1.0) - 7)\" text-anchor=\"end\" font-family=\"sans-serif\" font-size=\"12\" fill=\"#b13a32\">exact E0/N = -1</text>")
        println(io, "<polyline points=\"$polyline\" fill=\"none\" stroke=\"#215a86\" stroke-width=\"2.5\"/>")
        for (x, y) in zip(xs, ys)
            @printf(io, "<circle cx=\"%.2f\" cy=\"%.2f\" r=\"3.5\" fill=\"#215a86\"/>\n", sx(x), sy(y))
        end
        println(io, "<text x=\"400\" y=\"480\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"15\">accepted step</text>")
        println(io, "<text x=\"20\" y=\"250\" text-anchor=\"middle\" transform=\"rotate(-90 20 250)\" font-family=\"sans-serif\" font-size=\"15\">E_cell/8</text>")
        @printf(io, "<text x=\"%.2f\" y=\"%.2f\" text-anchor=\"end\" font-family=\"sans-serif\" font-size=\"12\">%.5f</text>\n", left - 8, sy(ymax), ymax)
        @printf(io, "<text x=\"%.2f\" y=\"%.2f\" text-anchor=\"end\" font-family=\"sans-serif\" font-size=\"12\">%.5f</text>\n", left - 8, sy(ymin), ymin)
        println(io, "</svg>")
    end
end

max_stabilizer_error(stars, plaquettes) =
    max(maximum(abs.(stars .- 1)), maximum(abs.(plaquettes .- 1)))

function run_exact_or_smoke(config, seed, outdir)
    initial = config.name == "exact-smoke" ? exact_tied_peps() : random_tied_peps(seed)
    result = optimize_tied(initial, config, outdir)
    env, info = converge_tied_environment(
        result.psi, config.chi; tol = config.ctm_tol, maxiter = config.ctm_maxiter)
    energy, stars, plaquettes = evaluate_tied_h0(result.psi, env)
    write_stabilizers(
        joinpath(outdir, "$(config.name)_stabilizers.csv"),
        [(phase = "final", chi = config.chi, stars, plaquettes)])
    tied_log(@sprintf(
        "%s final: E_cell=%+.12f, max stabilizer error=%.3e, status=%s",
        config.name, energy, max_stabilizer_error(stars, plaquettes), result.status))
    tied_log(@sprintf(
        "%s final CTMRG: iters=%d, residual=%.2e",
        config.name, ctm_iterations(info), info.convergence_error))

    healthy = result.status != :armijo_failed
    if config.name == "exact-smoke"
        return healthy && abs(energy + 8) <= 1e-8 &&
               max_stabilizer_error(stars, plaquettes) <= 1e-8 &&
               energy >= -8 - 1e-8
    end

    energies = [record.energy_cell for record in result.history
                if record.phase == "optimization"]
    descending = length(energies) == config.require_accepts + 1 &&
                 all(diff(energies) .< 0)
    return healthy && result.accepted == config.require_accepts && descending
end

function run_production(config, seed, outdir)
    result = optimize_tied(random_tied_peps(seed), config, outdir)
    env12, info12 = converge_tied_environment(
        result.psi, 12; tol = 1e-10, maxiter = 300)
    energy12, stars12, plaquettes12 = evaluate_tied_h0(result.psi, env12)
    env20, info20 = converge_tied_environment(
        result.psi, 20; tol = 1e-10, maxiter = 300)
    energy20, stars20, plaquettes20 = evaluate_tied_h0(result.psi, env20)

    append_record!(
        result.history, result.path,
        make_record("validation", config.name,
                    global_step(result.step_offset, result.accepted), 12,
                    energy12, 0.0, 0.0, info12))
    append_record!(
        result.history, result.path,
        make_record("validation", config.name,
                    global_step(result.step_offset, result.accepted), 20,
                    energy20, 0.0, 0.0, info20))
    write_stabilizers(
        joinpath(outdir, "stabilizers_h0.csv"),
        [(phase = "validation", chi = 12, stars = stars12, plaquettes = plaquettes12),
         (phase = "validation", chi = 20, stars = stars20, plaquettes = plaquettes20)])
    write_energy_svg(joinpath(outdir, "energy_convergence.svg"), result.history)

    energy_error = abs(energy12 + 8)
    stabilizer_error = max_stabilizer_error(stars12, plaquettes12)
    chi_energy_change = abs(energy20 - energy12)
    chi_stabilizer_change = max(
        maximum(abs.(stars20 .- stars12)),
        maximum(abs.(plaquettes20 .- plaquettes12)))
    passed = result.status != :armijo_failed &&
             energy_error <= 1e-6 && stabilizer_error <= 1e-6 &&
             energy12 >= -8 - 1e-6 &&
             chi_energy_change <= 1e-6 && chi_stabilizer_change <= 1e-6

    jldsave(
        joinpath(outdir, "groundstate_h0.jld2");
        tensors = result.psi.A,
        environment_chi12 = env12,
        environment_chi20 = env20,
        seed,
        D = 2,
        chi_optimization = 12,
        chi_validation = 20,
        energy_chi12 = energy12,
        energy_chi20 = energy20,
        stars_chi12 = stars12,
        plaquettes_chi12 = plaquettes12,
        stars_chi20 = stars20,
        plaquettes_chi20 = plaquettes20,
        optimizer_status = String(result.status),
        accepted_steps = result.accepted,
        passed)

    tied_log(@sprintf(
        "run final: E_cell(chi=12)=%+.12f, E/N=%+.12f, max stabilizer error=%.3e",
        energy12, energy12 / 8, stabilizer_error))
    tied_log(@sprintf(
        "chi 12->20: |delta E|=%.3e, max |delta stabilizer|=%.3e, status=%s",
        chi_energy_change, chi_stabilizer_change, result.status))
    return passed
end

function fresh_continuation_environment(psi, config)
    return converge_tied_environment(
        psi, config.chi; tol = config.ctm_tol, maxiter = config.ctm_maxiter)
end

function continuation_evaluations(
        result, config;
        fresh_environment = fresh_continuation_environment,
        evaluate = evaluate_tied_h0)
    primary_energy, primary_stars, primary_plaquettes =
        evaluate(result.psi, result.env)
    fresh_env, fresh_info = fresh_environment(result.psi, config)
    fresh_energy, fresh_stars, fresh_plaquettes = evaluate(result.psi, fresh_env)
    return (
        primary = (
            energy = primary_energy, stars = primary_stars,
            plaquettes = primary_plaquettes, env = result.env),
        fresh = (
            energy = fresh_energy, stars = fresh_stars,
            plaquettes = fresh_plaquettes, env = fresh_env, info = fresh_info))
end

function run_random_continuation(checkpoint, start_step, max_steps, chi, outdir)
    data = load(checkpoint)
    haskey(data, "tensors") || error("checkpoint has no tensors: $checkpoint")
    haskey(data, "step") || error("checkpoint has no step: $checkpoint")
    Int(data["step"]) == start_step || error(
        "checkpoint step $(data["step"]) does not match requested step $start_step")
    psi = InfinitePEPS(data["tensors"])
    is_tied(psi) || error("continuation checkpoint is not tied")

    mkpath(outdir)
    config = continuation_config(max_steps; chi)
    TIED_START[] = time()
    tied_log(
        "continuing checkpoint step=$start_step for at most $max_steps steps " *
        "at D=2 chi=$(config.chi)")
    result = optimize_tied(psi, config, outdir; step_offset = start_step)
    evaluations = continuation_evaluations(result, config)
    primary, fresh = evaluations.primary, evaluations.fresh
    write_stabilizers(
        joinpath(outdir, "random-continue_stabilizers.csv"),
        [(phase = "accepted", chi = config.chi,
          stars = primary.stars, plaquettes = primary.plaquettes),
         (phase = "fresh-repeat", chi = config.chi,
          stars = fresh.stars, plaquettes = fresh.plaquettes)])

    passed = continuation_passed(
        primary.energy, primary.stars, primary.plaquettes)
    primary_residual = result.history[end].ctm_residual
    tied_log(@sprintf(
        "continuation accepted step %d: E_cell=%+.12f, mean(A)=%.6f, mean(B)=%.6f, residual=%.2e",
        global_step(start_step, result.accepted), primary.energy,
        sum(primary.stars) / 4, sum(primary.plaquettes) / 4, primary_residual))
    tied_log(@sprintf(
        "continuation fresh repeat: E_cell=%+.12f, mean(A)=%.6f, mean(B)=%.6f, residual=%.2e",
        fresh.energy, sum(fresh.stars) / 4, sum(fresh.plaquettes) / 4,
        fresh.info.convergence_error))
    tied_log(passed ? "VERDICT: random continuation PASSED" :
                      "VERDICT: random continuation FAILED")
    return passed
end

function run_tied_mode(mode, seed, outdir)
    mkpath(outdir)
    config = mode_config(mode)
    TIED_START[] = time()
    tied_log("mode=$mode seed=$seed D=2 chi=$(config.chi) max_steps=$(config.max_steps)")
    passed = mode == "run" ? run_production(config, seed, outdir) :
             run_exact_or_smoke(config, seed, outdir)
    tied_log(passed ? "VERDICT: $mode PASSED" : "VERDICT: $mode FAILED")
    return passed
end

function tied_ad_main(args = ARGS)
    if !isempty(args) && args[1] == "continue"
        length(args) == 6 || throw(ArgumentError(
            "usage: ad_tied_gd.jl continue CHECKPOINT START_STEP N_STEPS CHI OUTDIR"))
        return run_random_continuation(
            args[2], parse(Int, args[3]), parse(Int, args[4]),
            parse(Int, args[5]), args[6])
    end
    length(args) == 3 || throw(ArgumentError(
        "usage: ad_tied_gd.jl MODE SEED OUTDIR"))
    mode, seed_text, outdir = args
    seed = parse(Int, seed_text)
    passed = true
    for requested_mode in requested_modes(mode)
        passed = run_tied_mode(requested_mode, seed, outdir) && passed
    end
    return passed
end

if abspath(PROGRAM_FILE) == @__FILE__
    code = try
        tied_ad_main() ? 0 : 1
    catch error_value
        showerror(stderr, error_value, catch_backtrace())
        println(stderr)
        flush(stderr)
        2
    end
    exit(code)
end
