# M3 finite-field series-validation driver (ratified 2026-07-30 protocol).
#
# Purpose: test whether the dense tied-tensor PEPS variational solver reproduces
# the small-field ground-state energy of
#   H = -sum_s A_s - sum_p B_p - h_z sum_i Z_i   (h_x = 0, J = 1)
# against the h_x = 0 perturbative series (arXiv:0807.0487 Eq. 8 ground-state
# energy, converted from the paper's J = 1/2 by e_ours(h) = 2 e_paper(h/2)):
#   e_series(h_z) = -1 - h_z^2/4 - 15 h_z^4/64 - 147 h_z^6/256 - 18003 h_z^8/8192
# per edge spin.
#
# Ratified protocol:
#  1. Pilot grid [0.00, 0.05, 0.10]; anchor = accepted M2 step-86 tied D=2 tensor.
#  2. Tensor-only continuation: field h_i initializes from the h_{i-1} tensor.
#  3. No optimizer state, line-search history, cached energies/gradients or
#     observables cross field points (normalized Armijo descent is stateless).
#  4. The warm CTMRG environment is one initialization, never the only contraction.
#  5. Frozen-tensor audit per point: warm + fresh deterministic + two fresh random
#     environments, all at the same chi/tolerance; one fresh chi_check contraction.
#  6. Record per-initialization residual, iterations, energy, <A_s>, <B_p>, m_z.
#  7. Acceptance: stationary optimizer (gradnorm <= grad_tol; budget exhaustion is
#     NOT convergence), every contraction converged, inter-initialization E/N
#     spread <= energy_init_tol and observable spread <= observable_init_tol, and
#     chi-increase |dE/N| <= chi_stability_tol.
#  8. Disagreement marks the point contraction-ambiguous: no averaging, no spread
#     as error bar, flagged (never silent) continuation in this pilot.
#
# Amendments (ratified 2026-07-30):
#  A1. Fresh-verified steps with alpha0 = 0.005 after the first pilot showed the
#      warm branch drifting to the trivial fixed point at alpha0 = 0.05.
#  A2. Fresh-det trial objective: the warm-carried trial environment proved
#      fragile (non-convergence at alpha >= 0.005), so every Armijo trial is a
#      from-scratch deterministic (seed 424242) contraction and the per-step
#      veto is an independent fresh random-seed (seed 1) contraction. The final
#      multi-initialization audit of the frozen tensor is unchanged.

using LinearAlgebra, Printf, Random
using TensorKit, PEPSKit, MPSKit, Zygote, JLD2

isdefined(@__MODULE__, :run_tied_mode) ||
    include(joinpath(@__DIR__, "ad_tied_gd.jl"))

# ---------- configuration ----------

struct SeriesConfig
    chi::Int
    chi_check::Int
    ctm_tol::Float64
    ctm_maxiter::Int
    grad_tol::Float64
    max_steps::Int
    armijo_initial_alpha::Float64
    armijo_trials::Int
    energy_init_tol::Float64
    observable_init_tol::Float64
    chi_stability_tol::Float64
    fresh_warm_tol::Float64

    function SeriesConfig(;
            chi::Int = 8, chi_check::Int = 16,
            ctm_tol::Float64 = 1e-8, ctm_maxiter::Int = 500,
            grad_tol::Float64 = 1e-6, max_steps::Int = 50,
            armijo_initial_alpha::Float64 = 0.05, armijo_trials::Int = 12,
            energy_init_tol::Float64 = 1e-6, observable_init_tol::Float64 = 1e-5,
            chi_stability_tol::Float64 = 1e-6, fresh_warm_tol::Float64 = 1e-6)
        chi >= 4 || throw(ArgumentError("series chi must be >= 4"))
        chi_check > chi || throw(ArgumentError("series chi_check must exceed chi"))
        ctm_tol > 0 || throw(ArgumentError("series ctm_tol must be positive"))
        ctm_maxiter > 0 || throw(ArgumentError("series ctm_maxiter must be positive"))
        grad_tol > 0 || throw(ArgumentError("series grad_tol must be positive"))
        max_steps > 0 || throw(ArgumentError("series max_steps must be positive"))
        0 < armijo_initial_alpha <= 0.05 || throw(ArgumentError(
            "series initial Armijo step must lie in (0, 0.05]"))
        armijo_trials > 0 || throw(ArgumentError("series armijo_trials must be positive"))
        energy_init_tol > 0 || throw(ArgumentError("series energy_init_tol must be positive"))
        observable_init_tol > 0 || throw(ArgumentError(
            "series observable_init_tol must be positive"))
        chi_stability_tol > 0 || throw(ArgumentError(
            "series chi_stability_tol must be positive"))
        fresh_warm_tol > 0 || throw(ArgumentError(
            "series fresh_warm_tol must be positive"))
        return new(
            chi, chi_check, ctm_tol, ctm_maxiter, grad_tol, max_steps,
            armijo_initial_alpha, armijo_trials,
            energy_init_tol, observable_init_tol, chi_stability_tol,
            fresh_warm_tol)
    end
end

# h_z = 0.10 is deferred per user directive (2026-07-30): the h_z = 0.05 point
# must pass the audit first.
const SERIES_PILOT_GRID = [0.0, 0.05]

"Ground-state energy per edge spin along h_x = 0 through order h_z^8 (J = 1)."
function series_energy_per_spin(hz)
    h2 = abs2(hz)
    return -1.0 - h2 / 4 - 15 * h2^2 / 64 - 147 * h2^3 / 256 - 18003 * h2^4 / 8192
end

series_energy_floor_cell(hz) = -8 - 8 * abs(hz) - 1e-5

# ---------- observables ----------

"sum over cell sites of -(Z_E + Z_N); expectation = -8 * m_z."
function series_field_operator()
    lattice = fill(TIED_UP, 2, 2)
    operator = empty_localoperator(lattice)
    unit = field_op(0.0, 1.0, TIED_UP)
    for r in 1:2, c in 1:2
        PEPSKit.add_term!(operator, [CartesianIndex(r, c)], unit)
    end
    return operator
end

const SERIES_FIELD_OP = series_field_operator()

function evaluate_series_observables(psi, env, hamiltonian, hz)
    energy = real(expectation_value(psi, hamiltonian, env))
    h0_energy, stars, plaquettes = evaluate_tied_h0(psi, env)
    field_energy = real(expectation_value(psi, SERIES_FIELD_OP, env))
    mz = -field_energy / 8
    expected = h0_energy + hz * field_energy
    isapprox(energy, expected; atol = 1e-8, rtol = 1e-8) || error(
        @sprintf(
            "finite-field energy mismatch at h_z=%.4f: H=%.12f, H0+h_z*field=%.12f",
            hz, energy, expected))
    all(isfinite, (energy, mz, stars..., plaquettes...)) ||
        error("series observables are non-finite")
    return (; energy, stars, plaquettes, mz)
end

# ---------- optimizer (stateless normalized Armijo descent) ----------

function series_energy_gradient(psi, env, hamiltonian, config)
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
    isfinite(value) || error("series AD energy is non-finite")
    isfinite(peps_frobnorm(gradient)) || error("series AD gradient is non-finite")
    return value, gradient
end

# Trial objective (ratified 2026-07-30, second amendment): every Armijo trial is
# evaluated with a from-scratch deterministic CTMRG contraction (fixed seed).
# The warm-carried environment was diagnosed to be the fragile element: it
# failed to converge for tensor perturbations with alpha >= 0.005, and in the
# first pilot it drifted onto the trivial factorizing fixed point (energy
# -8-8*h_z, stabilizers > 1) while claiming physical descent. The fresh
# deterministic branch converges robustly and does not follow that artifact.
"Fresh deterministic trial contraction (the line-search objective)."
function series_evaluate_trial(trial, hamiltonian, config)
    trial_env, trial_info = converge_tied_environment(
        trial, config.chi; tol = config.ctm_tol,
        maxiter = config.ctm_maxiter, seed = TIED_CTM_SEED)
    trial_energy = real(cost_function(trial, trial_env, hamiltonian))
    return (; env = trial_env, info = trial_info, energy = trial_energy)
end

"Independent fresh random-seed trial contraction (acceptance veto, never the objective)."
function series_verify_trial(trial, hamiltonian, config)
    env, info = converge_tied_environment(
        trial, config.chi; tol = config.ctm_tol,
        maxiter = config.ctm_maxiter, seed = 1)
    energy = real(cost_function(trial, env, hamiltonian))
    return (; energy, residual = info.convergence_error)
end

# Acceptance requires the Armijo criteria on the deterministic branch AND an
# independent fresh random-seed verification: it must converge, stay inside the
# physical window, decrease against the last accepted deterministic-branch
# energy, and agree with the deterministic branch to fresh_warm_tol per spin.
# Two independent contractions per accepted step close the artifact-descent
# channel diagnosed in the first pilot.
function series_armijo_step(
        psi, current_env, energy, fresh_ref, gradient, hz, hamiltonian, config;
        evaluate_trial = series_evaluate_trial, verify_trial = series_verify_trial)
    is_tied(psi) || error("series optimizer received an untied state")
    direction, gradnorm = tied_descent_direction(gradient; grad_tol = config.grad_tol)
    isfinite(gradnorm) || error("series projected gradient norm is non-finite")
    direction === nothing && return (
        status = :stationary, psi, env = current_env, energy,
        fresh_energy = fresh_ref, alpha = 0.0, gradnorm, info = nothing)

    alpha = config.armijo_initial_alpha
    for _ in 1:config.armijo_trials
        tensor = psi.A[1, 1] + alpha * direction.A[1, 1]
        normalize!(tensor, Inf)
        trial = tied_peps(tensor)
        evaluation = try
            evaluate_trial(trial, hamiltonian, config)
        catch error_value
            if error_value isa CTMRGConvergenceError
                tied_log(@sprintf(
                    "series h_z=%.4f alpha=%.4f objective rejected: %s",
                    hz, alpha, error_value.message))
                alpha /= 2
                continue
            end
            rethrow()
        end
        trial_energy = evaluation.energy
        objective_ok = isfinite(trial_energy) &&
                       trial_energy >= series_energy_floor_cell(hz) &&
                       trial_energy <= -8 + 1e-3 &&
                       trial_energy < energy &&
                       trial_energy <= energy - 1e-4 * alpha * gradnorm
        if objective_ok
            verification = try
                verify_trial(trial, hamiltonian, config)
            catch error_value
                if error_value isa CTMRGConvergenceError
                    tied_log(@sprintf(
                        "series h_z=%.4f alpha=%.4f veto rejected: %s",
                        hz, alpha, error_value.message))
                    alpha /= 2
                    continue
                end
                rethrow()
            end
            verified = isfinite(verification.energy) &&
                       verification.energy >= series_energy_floor_cell(hz) &&
                       verification.energy <= -8 + 1e-3 &&
                       verification.energy < fresh_ref &&
                       abs(verification.energy - trial_energy) / 8 <=
                       config.fresh_warm_tol
            if verified
                return (
                    status = :accepted, psi = trial, env = evaluation.env,
                    energy = trial_energy, fresh_energy = verification.energy,
                    alpha, gradnorm, info = evaluation.info)
            end
            tied_log(@sprintf(
                "series h_z=%.4f alpha=%.4f vetoed: det=%+.10f rand=%+.10f ref=%+.10f",
                hz, alpha, trial_energy, verification.energy, fresh_ref))
        end
        alpha /= 2
    end
    return (
        status = :armijo_failed, psi, env = current_env, energy,
        fresh_energy = fresh_ref, alpha = 0.0, gradnorm, info = nothing)
end

# ---------- frozen-tensor environment audit ----------

function audit_series_initialization(
        psi, hamiltonian, hz, config, label, seed, initial_env, chi)
    env, info = converge_tied_environment(
        psi, chi; tol = config.ctm_tol, maxiter = config.ctm_maxiter,
        seed = seed, initial_env = initial_env)
    observables = evaluate_series_observables(psi, env, hamiltonian, hz)
    return (;
        label, seed, chi, status = :converged,
        residual = Float64(info.convergence_error), iters = ctm_iterations(info),
        observables...)
end

failed_audit_row(label, seed, chi) = (;
    label, seed, chi, status = :failed, residual = NaN, iters = -1,
    energy = NaN, stars = fill(NaN, 4), plaquettes = fill(NaN, 4), mz = NaN)

function assess_series_consistency(rows; energy_tol, observable_tol)
    length(rows) >= 4 || return (
        usable = false, reason = :insufficient_inits, converged = length(rows),
        energy_spread_per_spin = Inf, observable_spread = Inf)
    energies = [row.energy for row in rows]
    energy_spread = (maximum(energies) - minimum(energies)) / 8
    star_spread = maximum(
        maximum(row.stars[i] for row in rows) - minimum(row.stars[i] for row in rows)
        for i in 1:4)
    plaquette_spread = maximum(
        maximum(row.plaquettes[i] for row in rows) -
        minimum(row.plaquettes[i] for row in rows)
        for i in 1:4)
    mz_values = [row.mz for row in rows]
    observable_spread = max(
        star_spread, plaquette_spread, maximum(mz_values) - minimum(mz_values))
    energy_spread <= energy_tol || return (
        usable = false, reason = :energy_disagreement, converged = length(rows),
        energy_spread_per_spin = energy_spread, observable_spread)
    observable_spread <= observable_tol || return (
        usable = false, reason = :observable_disagreement, converged = length(rows),
        energy_spread_per_spin = energy_spread, observable_spread)
    return (
        usable = true, reason = :consistent, converged = length(rows),
        energy_spread_per_spin = energy_spread, observable_spread)
end

function assess_series_chi(reference, check; energy_tol, observable_tol)
    energy_delta = abs(check.energy - reference.energy) / 8
    observable_delta = max(
        maximum(abs.(check.stars .- reference.stars)),
        maximum(abs.(check.plaquettes .- reference.plaquettes)),
        abs(check.mz - reference.mz))
    return (
        stable = energy_delta <= energy_tol && observable_delta <= observable_tol,
        energy_delta_per_spin = energy_delta, observable_delta)
end

series_point_accepted(hz, optimizer_status, consistency, chi_stability) =
    (hz == 0 ? optimizer_status == :m2_anchor : optimizer_status == :stationary) &&
    consistency.usable && chi_stability.stable

function run_series_audit(psi, hamiltonian, hz, warm_env, config)
    specs = [
        (label = "warm", seed = TIED_CTM_SEED, initial_env = warm_env),
        (label = "fresh_det", seed = TIED_CTM_SEED, initial_env = nothing),
        (label = "fresh_rand_1", seed = 1, initial_env = nothing),
        (label = "fresh_rand_2", seed = 2, initial_env = nothing),
    ]
    rows = NamedTuple[]
    for spec in specs
        row = try
            audit_series_initialization(
                psi, hamiltonian, hz, config,
                spec.label, spec.seed, spec.initial_env, config.chi)
        catch error_value
            error_value isa CTMRGConvergenceError || rethrow()
            tied_log(
                "series audit h_z=$hz $(spec.label) rejected: $(error_value.message)")
            failed_audit_row(spec.label, spec.seed, config.chi)
        end
        push!(rows, row)
    end
    check = try
        audit_series_initialization(
            psi, hamiltonian, hz, config,
            "chi$(config.chi_check)_det", TIED_CTM_SEED, nothing, config.chi_check)
    catch error_value
        error_value isa CTMRGConvergenceError || rethrow()
        tied_log(
            "series audit h_z=$hz chi=$(config.chi_check) rejected: " *
            error_value.message)
        failed_audit_row("chi$(config.chi_check)_det", TIED_CTM_SEED, config.chi_check)
    end

    converged = filter(row -> row.status == :converged, rows)
    consistency = assess_series_consistency(
        converged; energy_tol = config.energy_init_tol,
        observable_tol = config.observable_init_tol)
    references = filter(row -> row.label == "fresh_det", converged)
    chi_stability =
        if check.status == :converged && !isempty(references)
            assess_series_chi(
                first(references), check; energy_tol = config.chi_stability_tol,
                observable_tol = config.observable_init_tol)
        else
            (stable = false, energy_delta_per_spin = Inf, observable_delta = Inf)
        end
    representative = isempty(references) ? nothing : first(references)
    return (; rows, check, consistency, chi_stability, representative)
end

# ---------- output ----------

series_point_tag(hz) = "hz_" * replace(@sprintf("%.3f", hz), "." => "p")

series_audit_header() =
    "label,seed,chi,status,residual,iters,energy_cell,energy_per_spin," *
    "star_1,star_2,star_3,star_4," *
    "plaquette_1,plaquette_2,plaquette_3,plaquette_4,mz"

function write_series_audit_csv(path, rows, check)
    open(path, "w") do io
        println(io, series_audit_header())
        for row in vcat(rows, [check])
            if row.status == :converged
                @printf(
                    io,
                    "%s,%d,%d,converged,%.16e,%d,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e,%.16e\n",
                    row.label, row.seed, row.chi, row.residual, row.iters,
                    row.energy, row.energy / 8,
                    row.stars..., row.plaquettes..., row.mz)
            else
                @printf(io, "%s,%d,%d,failed,,,,,,,,,,,,,\n",
                    row.label, row.seed, row.chi)
            end
        end
        flush(io)
    end
end

series_points_header() =
    "hz,source_hz,parent_accepted,optimizer_status,accepted_steps,attempts," *
    "final_gradnorm,series_e_per_spin,repr_e_per_spin,delta_e_per_spin," *
    "audit_converged,energy_spread_per_spin,observable_spread," *
    "chi_check,chi_delta_e_per_spin,chi_delta_obs,consistency,chi_stable," *
    "point_accepted,checkpoint"

function initialize_series_csv(path)
    open(path, "w") do io
        println(io, series_points_header())
        flush(io)
    end
end

function append_series_row(path, row)
    open(path, "a") do io
        @printf(
            io,
            "%.6f,%.6f,%s,%s,%d,%d,%.16e,%.16e,%.16e,%.16e,%d,%.16e,%.16e,%d,%.16e,%.16e,%s,%s,%s,%s\n",
            row.hz, row.source_hz, string(row.parent_accepted),
            String(row.optimizer_status), row.accepted_steps, row.attempts,
            row.final_gradnorm, row.series_e_per_spin, row.repr_e_per_spin,
            row.delta_e_per_spin, row.audit_converged,
            row.energy_spread_per_spin, row.observable_spread,
            row.chi_check, row.chi_delta_e_per_spin, row.chi_delta_obs,
            String(row.consistency), string(row.chi_stable),
            string(row.point_accepted), row.checkpoint)
        flush(io)
    end
end

function prepare_series_outdir(outdir)
    if isdir(outdir)
        isempty(readdir(outdir)) || error("series output directory is not empty: $outdir")
    else
        mkpath(outdir)
    end
    return outdir
end

function load_series_anchor(path; expected_step = 86)
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

function write_series_svg(path, rows)
    isempty(rows) && throw(ArgumentError("cannot plot an empty series path"))
    curve_xs = range(0.0, 0.12; length = 121)
    curve_ys = series_energy_per_spin.(curve_xs)
    width, height = 800.0, 500.0
    left, right, top, bottom = 95.0, 30.0, 55.0, 70.0
    xmin, xmax = 0.0, 0.12
    ys = vcat(curve_ys, [row.repr_e_per_spin for row in rows if isfinite(row.repr_e_per_spin)])
    ymin, ymax = minimum(ys), maximum(ys)
    ypadding = max(0.05 * (ymax - ymin), 1e-4)
    ymin, ymax = ymin - ypadding, ymax + ypadding
    sx(x) = left + (x - xmin) / (xmax - xmin) * (width - left - right)
    sy(y) = top + (ymax - y) / (ymax - ymin) * (height - top - bottom)
    polyline = join(
        [@sprintf("%.2f,%.2f", sx(x), sy(y)) for (x, y) in zip(curve_xs, curve_ys)], " ")

    open(path, "w") do io
        println(io, "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"800\" height=\"500\" viewBox=\"0 0 800 500\">")
        println(io, "<rect width=\"800\" height=\"500\" fill=\"white\"/>")
        println(io, "<text x=\"400\" y=\"30\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"20\">M3 series pilot: E/N vs h_z series</text>")
        @printf(io, "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#222\"/>\n", left, height - bottom, width - right, height - bottom)
        @printf(io, "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#222\"/>\n", left, top, left, height - bottom)
        println(io, "<polyline points=\"$polyline\" fill=\"none\" stroke=\"#555\" stroke-width=\"2\" stroke-dasharray=\"6 4\"/>")
        println(io, "<text x=\"765\" y=\"$(sy(curve_ys[end]) - 8)\" text-anchor=\"end\" font-family=\"sans-serif\" font-size=\"12\" fill=\"#555\">h_z^8 series</text>")
        for row in rows
            isfinite(row.repr_e_per_spin) || continue
            color = row.point_accepted ? "#215a86" : "#8f2d2d"
            @printf(io, "<circle cx=\"%.2f\" cy=\"%.2f\" r=\"5\" fill=\"%s\"/>\n",
                sx(row.hz), sy(row.repr_e_per_spin), color)
        end
        println(io, "<text x=\"400\" y=\"480\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"15\">h_z</text>")
        println(io, "<text x=\"22\" y=\"250\" text-anchor=\"middle\" transform=\"rotate(-90 22 250)\" font-family=\"sans-serif\" font-size=\"15\">E/N per edge spin</text>")
        println(io, "</svg>")
        flush(io)
    end
end

# ---------- per-point driver ----------

function run_series_point(psi, warm_env, hz, source_hz, config, outdir; parent_accepted)
    hamiltonian, _ = toric_code_hamiltonian(0.0, hz; P = TIED_UP)
    env = warm_env
    accepted_steps = 0
    attempts = 0
    final_gradnorm = 0.0
    status = hz == 0 ? :m2_anchor : :budget

    if hz == 0
        env, anchor_info = converge_tied_environment(
            psi, config.chi; tol = config.ctm_tol, maxiter = config.ctm_maxiter,
            seed = TIED_CTM_SEED)
        tied_log(@sprintf(
            "series h_z=0 anchor CTMRG: iterations=%d residual=%.2e",
            ctm_iterations(anchor_info), anchor_info.convergence_error))
        _, gradient = series_energy_gradient(psi, env, hamiltonian, config)
        final_gradnorm = peps_frobnorm(project_tied_gradient(gradient))
        tied_log(@sprintf("series h_z=0 anchor gradnorm=%.3e", final_gradnorm))
    else
        fresh_ref = series_evaluate_trial(psi, hamiltonian, config).energy
        tied_log(@sprintf(
            "series h_z=%.4f initial deterministic-branch reference: %+.10f",
            hz, fresh_ref))
        while accepted_steps < config.max_steps
            attempts += 1
            current_energy, gradient = series_energy_gradient(psi, env, hamiltonian, config)
            result = series_armijo_step(
                psi, env, current_energy, fresh_ref, gradient, hz, hamiltonian, config)
            final_gradnorm = result.gradnorm
            if result.status != :accepted
                status = result.status
                tied_log(@sprintf(
                    "series h_z=%.4f attempt=%d status=%s gradnorm=%.3e",
                    hz, attempts, result.status, result.gradnorm))
                break
            end
            psi, env = result.psi, result.env
            fresh_ref = result.energy
            accepted_steps += 1
            tied_log(@sprintf(
                "series h_z=%.4f step=%d det=%+.10f veto=%+.10f gradnorm=%.3e alpha=%.4f residual=%.2e",
                hz, accepted_steps, result.energy, result.fresh_energy,
                result.gradnorm, result.alpha, result.info.convergence_error))
            jldsave(
                joinpath(outdir, @sprintf(
                    "%s_step%02d.jld2", series_point_tag(hz), accepted_steps));
                tensors = psi.A, hx = 0.0, hz, source_hz, D = 2,
                chi = config.chi, accepted_steps, attempts,
                energy = result.energy, fresh_energy = result.fresh_energy,
                gradnorm = result.gradnorm,
                alpha = result.alpha, ctm_residual = result.info.convergence_error)
        end
    end

    audit = run_series_audit(psi, hamiltonian, hz, env, config)
    write_series_audit_csv(
        joinpath(outdir, "$(series_point_tag(hz))_audit.csv"), audit.rows, audit.check)
    accepted = series_point_accepted(
        hz, status, audit.consistency, audit.chi_stability)
    representative = audit.representative
    repr_e = isnothing(representative) ? NaN : representative.energy / 8
    series_e = series_energy_per_spin(hz)
    checkpoint = joinpath(outdir, "$(series_point_tag(hz))_final.jld2")
    jldsave(
        checkpoint;
        tensors = psi.A, hx = 0.0, hz, source_hz, D = 2,
        chi = config.chi, chi_check = config.chi_check,
        ctm_tol = config.ctm_tol, ctm_maxiter = config.ctm_maxiter,
        grad_tol = config.grad_tol, max_steps = config.max_steps,
        optimizer_status = String(status), accepted_steps, attempts, final_gradnorm,
        series_e_per_spin = series_e, repr_e_per_spin = repr_e,
        delta_e_per_spin = repr_e - series_e,
        consistency = String(audit.consistency.reason),
        audit_converged = audit.consistency.converged,
        energy_spread_per_spin = audit.consistency.energy_spread_per_spin,
        observable_spread = audit.consistency.observable_spread,
        chi_stable = audit.chi_stability.stable,
        chi_delta_e_per_spin = audit.chi_stability.energy_delta_per_spin,
        chi_delta_obs = audit.chi_stability.observable_delta,
        point_accepted = accepted)
    row = (
        hz = Float64(hz), source_hz = Float64(source_hz), parent_accepted,
        optimizer_status = status, accepted_steps, attempts, final_gradnorm,
        series_e_per_spin = series_e, repr_e_per_spin = repr_e,
        delta_e_per_spin = repr_e - series_e,
        audit_converged = audit.consistency.converged,
        energy_spread_per_spin = audit.consistency.energy_spread_per_spin,
        observable_spread = audit.consistency.observable_spread,
        chi_check = config.chi_check,
        chi_delta_e_per_spin = audit.chi_stability.energy_delta_per_spin,
        chi_delta_obs = audit.chi_stability.observable_delta,
        consistency = audit.consistency.reason,
        chi_stable = audit.chi_stability.stable,
        point_accepted = accepted, checkpoint)
    tied_log(@sprintf(
        "series h_z=%.4f final: E/N=%+.10f series=%+.10f delta=%+.3e spread=%.2e chi_delta=%.2e audit=%s chi_stable=%s status=%s accepted=%s",
        hz, repr_e, series_e, repr_e - series_e,
        row.energy_spread_per_spin, row.chi_delta_e_per_spin,
        audit.consistency.reason, audit.chi_stability.stable, status, accepted))
    return (; state = psi, env, accepted, row)
end

function run_series_pilot(checkpoint, config, outdir)
    prepare_series_outdir(outdir)
    csv_path = joinpath(outdir, "series_points.csv")
    initialize_series_csv(csv_path)
    psi = load_series_anchor(checkpoint)
    TIED_START[] = time()
    tied_log(
        "series pilot start: D=2 chi=$(config.chi) chi_check=$(config.chi_check) " *
        "ctm_tol=$(config.ctm_tol) max_steps=$(config.max_steps) " *
        "alpha0=$(config.armijo_initial_alpha) grid=$(SERIES_PILOT_GRID)")
    env = nothing
    source_hz = 0.0
    parent_accepted = true
    rows = NamedTuple[]
    for hz in SERIES_PILOT_GRID
        if !parent_accepted
            tied_log(
                "series WARNING: parent point not accepted; h_z=$hz continuation " *
                "is a flagged pilot diagnostic (protocol item 8)")
        end
        result = run_series_point(
            psi, env, hz, source_hz, config, outdir; parent_accepted)
        append_series_row(csv_path, result.row)
        psi, env = result.state, result.env
        parent_accepted = result.accepted
        source_hz = hz
        push!(rows, result.row)
    end
    write_series_svg(joinpath(outdir, "series_pilot.svg"), rows)
    return rows
end

function series_main(args = ARGS)
    length(args) >= 3 || throw(ArgumentError(
        "usage: m3_series_validation.jl pilot CHECKPOINT OUTDIR " *
        "[CHI CHI_CHECK MAX_STEPS ALPHA]"))
    args[1] == "pilot" || throw(ArgumentError("unknown series mode: $(args[1])"))
    chi = length(args) >= 4 ? parse(Int, args[4]) : 8
    chi_check = length(args) >= 5 ? parse(Int, args[5]) : 16
    max_steps = length(args) >= 6 ? parse(Int, args[6]) : 50
    alpha = length(args) >= 7 ? parse(Float64, args[7]) : 0.05
    config = SeriesConfig(;
        chi, chi_check, max_steps, armijo_initial_alpha = alpha)
    rows = run_series_pilot(args[2], config, args[3])
    accepted = all(row -> row.point_accepted, rows)
    tied_log(accepted ? "SERIES PILOT ACCEPTED" : "SERIES PILOT NOT ACCEPTED")
    return accepted
end

if abspath(PROGRAM_FILE) == @__FILE__
    code = try
        series_main() ? 0 : 1
    catch error_value
        showerror(stderr, error_value, catch_backtrace())
        println(stderr)
        flush(stderr)
        2
    end
    exit(code)
end
