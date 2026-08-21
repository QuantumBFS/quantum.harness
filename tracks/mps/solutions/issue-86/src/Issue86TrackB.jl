module Issue86TrackB

using Dates
using DelimitedFiles
using JSON
using KrylovKit
using LinearAlgebra
using MPSKit
using Printf
using Random
using SHA
using SparseArrays
using SpecialFunctions
using Statistics
using TensorKit
using TensorKit: ℂ

export SOEApproximation
export build_run_spec
export collect_cell_results
export conservative_error_budget
export coupling_error
export crossing_bracket
export dmrg_point
export ed_hamiltonian
export ed_lowest
export execute_cell
export exact_mpo
export fit_periodic_soe
export fit_power_law_soe
export fit_crossing_sequence
export fit_dynamic_exponent
export nn_coupling_matrix
export normalized_energy_variance
export pauli_x
export pauli_z
export periodic_coupling
export periodic_coupling_matrix
export pending_cell_indices
export read_config_jobs
export resource_class
export run_jobs
export soe_mpo
export soe_periodic_coupling
export structure_factor

const X_MATRIX = ComplexF64[0 1; 1 0]
const Z_MATRIX = ComplexF64[1 0; 0 -1]

pauli_x() = TensorMap(X_MATRIX, ℂ^2 ← ℂ^2)
pauli_z() = TensorMap(Z_MATRIX, ℂ^2 ← ℂ^2)

"""
Positive sum-of-exponentials approximation

    d^(-alpha) ≈ sum(amplitudes[p] * lambdas[p]^(d - 1), p=1:poles)

obtained from a sinc/trapezoid quadrature of the Laplace representation.
"""
struct SOEApproximation
    alpha::Float64
    poles::Int
    dmax::Int
    xmin::Float64
    xmax::Float64
    amplitudes::Vector{Float64}
    lambdas::Vector{Float64}
    max_relative_error::Float64
    rms_relative_error::Float64
end

function _quadrature_soe(alpha::Float64, poles::Int, xmin::Float64, xmax::Float64)
    xs = collect(range(xmin, xmax; length = poles))
    h = (xmax - xmin) / (poles - 1)
    weights = fill(h, poles)
    weights[1] *= 0.5
    weights[end] *= 0.5
    lambdas = exp.(-exp.(xs))
    amplitudes = weights .* exp.(alpha .* xs) .* lambdas ./ gamma(alpha)
    return amplitudes, lambdas
end

function _soe_errors(alpha, amplitudes, lambdas, dmax)
    rel = map(1:dmax) do d
        target = d^(-alpha)
        approximate = sum(amplitudes .* lambdas .^ (d - 1))
        return (approximate - target) / target
    end
    return maximum(abs, rel), sqrt(mean(abs2, rel))
end

"""
    fit_power_law_soe(alpha, poles; dmax=512)

Choose the quadrature window by a deterministic grid search that minimizes the
maximum relative coupling error on every integer distance `1:dmax`.
"""
function fit_power_law_soe(alpha::Real, poles::Integer; dmax::Integer = 512)
    alpha > 1 || throw(ArgumentError("alpha must be larger than one"))
    poles >= 4 || throw(ArgumentError("at least four poles are required"))
    dmax >= 2 || throw(ArgumentError("dmax must be at least two"))

    best = nothing
    for xmin in -14.0:0.2:-2.0, xmax in -1.0:0.2:4.0
        xmax > xmin || continue
        amplitudes, lambdas = _quadrature_soe(Float64(alpha), Int(poles), xmin, xmax)
        maximum_error, rms_error = _soe_errors(alpha, amplitudes, lambdas, dmax)
        if isnothing(best) || maximum_error < best.max_relative_error
            best = SOEApproximation(
                Float64(alpha), Int(poles), Int(dmax), xmin, xmax,
                amplitudes, lambdas, maximum_error, rms_error
            )
        end
    end
    return best::SOEApproximation
end

"""
Hurwitz-zeta periodic-image interaction from Shiratani--Todo:

    J_L(r) = L^(-alpha) [zeta(alpha, r/L) + zeta(alpha, 1-r/L)].
"""
function periodic_coupling(L::Integer, sigma::Real, r::Integer)
    1 <= r < L || throw(ArgumentError("r must satisfy 1 <= r < L"))
    alpha = 1 + Float64(sigma)
    x = Float64(r) / L
    return L^(-alpha) * (zeta(alpha, x) + zeta(alpha, 1 - x))
end

function soe_periodic_coupling(approx::SOEApproximation, L::Integer, r::Integer)
    1 <= r < L || throw(ArgumentError("r must satisfy 1 <= r < L"))
    return sum(zip(approx.amplitudes, approx.lambdas)) do (amplitude, lambda)
        denominator = 1 - lambda^L
        return amplitude * (lambda^(r - 1) + lambda^(L - r - 1)) / denominator
    end
end

function periodic_coupling_matrix(L::Integer, sigma::Real)
    matrix = zeros(Float64, L, L)
    for i in 1:(L - 1), j in (i + 1):L
        matrix[i, j] = matrix[j, i] = periodic_coupling(L, sigma, j - i)
    end
    return matrix
end

function nn_coupling_matrix(L::Integer)
    L >= 3 || throw(ArgumentError("the periodic NN anchor uses L >= 3"))
    matrix = zeros(Float64, L, L)
    for i in 1:L
        j = mod1(i + 1, L)
        matrix[i, j] = matrix[j, i] = 1.0
    end
    return matrix
end

function _periodic_fit_candidate(L, sigma, poles, xmin, xmax, relative_tolerance)
    xs = collect(range(xmin, xmax; length = poles))
    lambdas = exp.(-exp.(xs))
    distances = collect(1:fld(L, 2))
    exact = [periodic_coupling(L, sigma, distance) for distance in distances]
    basis = [
        (lambda^(distance - 1) + lambda^(L - distance - 1)) / (1 - lambda^L)
        for distance in distances, lambda in lambdas
    ]
    relative_basis = basis ./ exact
    amplitudes = pinv(relative_basis; rtol = relative_tolerance) * ones(length(exact))
    relative_errors = basis * amplitudes ./ exact .- 1
    return SOEApproximation(
        1 + Float64(sigma), Int(poles), Int(L - 1), Float64(xmin), Float64(xmax),
        amplitudes, lambdas, maximum(abs, relative_errors),
        sqrt(mean(abs2, relative_errors)),
    )
end

function _padded_candidate(previous::SOEApproximation, poles::Integer)
    added = poles - previous.poles
    added > 0 || throw(ArgumentError("padded pole count must increase"))
    extra_xs = collect(range(-12.0, 6.0; length = added + 2))[2:(added + 1)]
    lambdas = vcat(previous.lambdas, exp.(-exp.(extra_xs)))
    amplitudes = vcat(previous.amplitudes, zeros(added))
    order = sortperm(lambdas; rev = true)
    return SOEApproximation(
        previous.alpha, Int(poles), previous.dmax,
        minimum(vcat(previous.xmin, extra_xs)),
        maximum(vcat(previous.xmax, extra_xs)),
        amplitudes[order], lambdas[order],
        previous.max_relative_error, previous.rms_relative_error,
    )
end

"""
    fit_periodic_soe(L, sigma, poles)

Fit the finite-size Hurwitz-zeta coupling directly in the periodic exponential
basis used by `soe_mpo`. The least-squares system is scaled by the exact
coupling, so its residual is a relative rather than absolute error. Larger
four-pole steps retain the preceding fit as a zero-padded candidate, ensuring
that the audited error cannot increase in the 8/12/16 pole sweep.
"""
function fit_periodic_soe(L::Integer, sigma::Real, poles::Integer)
    L >= 3 || throw(ArgumentError("L must be at least three"))
    sigma > 0 || throw(ArgumentError("sigma must be positive"))
    poles >= 4 || throw(ArgumentError("at least four poles are required"))

    best = nothing
    for xmin in -8.0:0.25:-1.0, xmax in -0.5:0.25:5.0
        for relative_tolerance in (1.0e-16, 1.0e-14, 1.0e-12, 1.0e-10, 1.0e-8)
            candidate = _periodic_fit_candidate(
                L, sigma, poles, xmin, xmax, relative_tolerance
            )
            if isnothing(best) || candidate.max_relative_error < best.max_relative_error
                best = candidate
            end
        end
    end

    if poles in (12, 16)
        padded = _padded_candidate(fit_periodic_soe(L, sigma, poles - 4), poles)
        padded.max_relative_error < best.max_relative_error && (best = padded)
    end
    return best::SOEApproximation
end

function coupling_error(L::Integer, sigma::Real, approx::SOEApproximation)
    exact = [periodic_coupling(L, sigma, r) for r in 1:(L - 1)]
    fitted = [soe_periodic_coupling(approx, L, r) for r in 1:(L - 1)]
    relative = abs.((fitted .- exact) ./ exact)
    return Dict(
        "max_relative" => maximum(relative),
        "rms_relative" => sqrt(mean(abs2, relative)),
        "max_absolute" => maximum(abs.(fitted .- exact)),
    )
end

function exact_mpo(couplings::AbstractMatrix, gamma::Real)
    L = size(couplings, 1)
    size(couplings, 2) == L || throw(DimensionMismatch("coupling matrix must be square"))
    X = pauli_x()
    ZZ = pauli_z() ⊗ pauli_z()
    terms = Any[i => -Float64(gamma) * X for i in 1:L]
    for i in 1:(L - 1), j in (i + 1):L
        iszero(couplings[i, j]) || push!(terms, (i, j) => -couplings[i, j] * ZZ)
    end
    return FiniteMPOHamiltonian(fill(ℂ^2, L), terms)
end

"""
Construct the periodic-image long-range MPO with `2P + 2` virtual levels.

The forward channels generate lambda^(j-i-1). The image channels factor
lambda^(L-(j-i)-1) into site-dependent start/end coefficients, avoiding an
unstable propagation by lambda^(-1).
"""
function soe_mpo(L::Integer, sigma::Real, gamma::Real, approx::SOEApproximation)
    isapprox(approx.alpha, 1 + sigma; atol = 100eps(Float64)) ||
        throw(ArgumentError("SOE alpha does not match sigma"))
    levels = 2 * approx.poles + 2
    finish = levels
    X = FiniteMPO(pauli_x())[1]
    Z = FiniteMPO(pauli_z())[1]
    matrices = Vector{Matrix{Any}}(undef, L)

    for site in 1:L
        W = Matrix{Any}(undef, levels, levels)
        fill!(W, missing)
        W[1, 1] = ComplexF64(1)
        W[finish, finish] = ComplexF64(1)
        W[1, finish] = -Float64(gamma) * X

        for pole in 1:approx.poles
            amplitude = approx.amplitudes[pole]
            lambda = approx.lambdas[pole]
            denominator = 1 - lambda^L

            forward = 1 + pole
            W[1, forward] = -(amplitude / denominator) * Z
            W[forward, forward] = ComplexF64(lambda)
            W[forward, finish] = Z

            image = 1 + approx.poles + pole
            W[1, image] = -(amplitude * lambda^(site - 1) / denominator) * Z
            W[image, image] = ComplexF64(1)
            W[image, finish] = lambda^(L - site) * Z
        end

        matrices[site] = site == 1 ? W[1:1, :] : (site == L ? W[:, finish:finish] : W)
    end
    return FiniteMPOHamiltonian(matrices)
end

function ed_hamiltonian(couplings::AbstractMatrix, gamma::Real)
    L = size(couplings, 1)
    size(couplings, 2) == L || throw(DimensionMismatch("coupling matrix must be square"))
    L <= 16 || throw(ArgumentError("ED is restricted to L <= 16"))
    dimension = 1 << L
    rows = Vector{Int}(undef, dimension * (L + 1))
    columns = similar(rows)
    values = Vector{Float64}(undef, length(rows))
    cursor = 0

    for state in 0:(dimension - 1)
        diagonal = 0.0
        for i in 1:(L - 1), j in (i + 1):L
            zi = iszero(state & (1 << (i - 1))) ? 1.0 : -1.0
            zj = iszero(state & (1 << (j - 1))) ? 1.0 : -1.0
            diagonal -= couplings[i, j] * zi * zj
        end
        cursor += 1
        rows[cursor] = state + 1
        columns[cursor] = state + 1
        values[cursor] = diagonal

        for site in 1:L
            cursor += 1
            rows[cursor] = state + 1
            columns[cursor] = xor(state, 1 << (site - 1)) + 1
            values[cursor] = -Float64(gamma)
        end
    end
    return sparse(rows, columns, values, dimension, dimension)
end

function ed_lowest(H::SparseMatrixCSC; number::Integer = 2, tolerance::Real = 1.0e-12)
    dimension = size(H, 1)
    if dimension <= 4096
        solution = eigen(Hermitian(Matrix(H)))
        return solution.values[1:number], [solution.vectors[:, i] for i in 1:number], nothing
    end
    initial = normalize!(ones(Float64, dimension))
    values, vectors, info = eigsolve(
        H, initial, number, :SR;
        tol = tolerance, krylovdim = max(30, 4number + 10), maxiter = 500
    )
    order = sortperm(real.(values))
    return real.(values[order]), vectors[order], info
end

function structure_factor(state::AbstractVector, L::Integer, momentum::Real)
    length(state) == 1 << L || throw(DimensionMismatch("state dimension does not match L"))
    result = 0.0
    for basis in 0:((1 << L) - 1)
        mode = 0.0 + 0.0im
        for site in 1:L
            z = iszero(basis & (1 << (site - 1))) ? 1.0 : -1.0
            mode += z * cis(momentum * (site - 1))
        end
        result += abs2(state[basis + 1]) * abs2(mode)
    end
    return real(result) / L
end

function crossing_bracket(rows_L, rows_2L)
    left = Dict(Float64(row["Gamma"]) => Float64(row["correlation_ratio"]) for row in rows_L)
    right = Dict(
        Float64(row["Gamma"]) => Float64(row["correlation_ratio"]) for row in rows_2L
    )
    gammas = sort!(collect(intersect(keys(left), keys(right))))
    length(gammas) >= 2 || return nothing
    differences = [left[gamma] - right[gamma] for gamma in gammas]
    for index in 1:(length(gammas) - 1)
        x1, x2 = gammas[index], gammas[index + 1]
        y1, y2 = differences[index], differences[index + 1]
        y1 == 0 && return Dict(
            "Gamma_low" => x1,
            "Gamma_high" => x1,
            "Gamma_crossing" => x1,
            "interpolation_half_width" => 0.0,
        )
        y1 * y2 > 0 && continue
        crossing = x1 - y1 * (x2 - x1) / (y2 - y1)
        return Dict(
            "Gamma_low" => x1,
            "Gamma_high" => x2,
            "Gamma_crossing" => crossing,
            "interpolation_half_width" => (x2 - x1) / 2,
        )
    end
    return nothing
end

function _fit_crossing_power(values)
    lengths = Float64[entry["L"] for entry in values]
    crossings = Float64[entry["Gamma_crossing"] for entry in values]
    best = nothing
    for omega in 0.10:0.01:4.00
        design = hcat(ones(length(lengths)), lengths .^ (-omega))
        coefficients = design \ crossings
        predicted = design * coefficients
        rmse = sqrt(mean(abs2, crossings - predicted))
        candidate = Dict{String, Any}(
            "Gamma_c" => coefficients[1],
            "amplitude" => coefficients[2],
            "omega" => omega,
            "rmse" => rmse,
        )
        if isnothing(best) || rmse < best["rmse"]
            best = candidate
        end
    end
    return best::Dict{String, Any}
end

function fit_crossing_sequence(values)
    length(values) >= 4 ||
        throw(ArgumentError("at least four crossing pairs are required"))
    ordered = sort!(collect(values); by = entry -> Float64(entry["L"]))
    fit = _fit_crossing_power(ordered)
    fit["lengths"] = [entry["L"] for entry in ordered]
    fit["crossings"] = [entry["Gamma_crossing"] for entry in ordered]
    fit["without_smallest"] = _fit_crossing_power(ordered[2:end])
    return fit
end

function fit_dynamic_exponent(rows)
    selected = filter(row -> row["model"] == "nn" && !isnothing(row["gap"]), rows)
    isempty(selected) && return nothing
    by_length = Dict{Int, Dict{String, Any}}()
    for row in selected
        L = Int(row["L"])
        gamma_distance = abs(Float64(row["Gamma"]) - 1)
        previous_distance = haskey(by_length, L) ?
            abs(Float64(by_length[L]["Gamma"]) - 1) : Inf
        if !haskey(by_length, L) ||
                gamma_distance < previous_distance ||
                (gamma_distance == previous_distance &&
                 Int(row["chi"]) > Int(by_length[L]["chi"]))
            by_length[L] = row
        end
    end
    length(by_length) >= 3 || return nothing
    lengths = sort!(collect(keys(by_length)))
    gaps = [Float64(by_length[L]["gap"]) for L in lengths]
    all(>(0), gaps) || return nothing
    design = hcat(ones(length(lengths)), log.(Float64.(lengths)))
    coefficients = design \ log.(gaps)
    predicted = design * coefficients
    fit = Dict{String, Any}(
        "z" => -coefficients[2],
        "intercept" => coefficients[1],
        "lengths" => lengths,
        "chis" => [Int(by_length[L]["chi"]) for L in lengths],
        "gaps" => gaps,
        "log_rmse" => sqrt(mean(abs2, log.(gaps) - predicted)),
    )
    if length(lengths) >= 4
        reduced_design = design[2:end, :]
        reduced_coefficients = reduced_design \ log.(gaps[2:end])
        fit["without_smallest"] = Dict(
            "z" => -reduced_coefficients[2],
            "lengths" => lengths[2:end],
        )
    end
    return fit
end

function conservative_error_budget(
        estimate::Real;
        interpolation::Real,
        finite_size::Real,
        chi::Real,
        mpo::Real,
        reference::Real,
        reference_error::Real,
    )
    components = Dict(
        "interpolation" => abs(Float64(interpolation)),
        "finite_size" => abs(Float64(finite_size)),
        "chi" => abs(Float64(chi)),
        "mpo" => abs(Float64(mpo)),
    )
    total = sum(values(components))
    interval = [Float64(estimate) - total, Float64(estimate) + total]
    reference_interval = [
        Float64(reference) - abs(Float64(reference_error)),
        Float64(reference) + abs(Float64(reference_error)),
    ]
    overlaps = interval[1] <= reference_interval[2] &&
        reference_interval[1] <= interval[2]
    return Dict{String, Any}(
        "estimate" => Float64(estimate),
        "components" => components,
        "total_error" => total,
        "interval" => interval,
        "reference" => Float64(reference),
        "reference_error" => abs(Float64(reference_error)),
        "reference_interval" => reference_interval,
        "covers_reference_interval" => overlaps,
    )
end

function _mps_structure_factor(state::FiniteMPS, momentum::Real)
    L = length(state)
    correlations = Matrix{ComplexF64}(I, L, L)
    Z = MPSKit.add_util_leg(pauli_z())
    for i in 1:(L - 1)
        values = correlator(state, Z, Z, i, (i + 1):L)
        for (offset, value) in enumerate(values)
            j = i + offset
            correlations[i, j] = value
            correlations[j, i] = conj(value)
        end
    end
    phase_sum = 0.0 + 0.0im
    for i in 1:L, j in 1:L
        phase_sum += cis(momentum * (i - j)) * correlations[i, j]
    end
    return real(phase_sum) / L
end

function _correlation_ratio(state::FiniteMPS)
    L = length(state)
    s0 = _mps_structure_factor(state, 0.0)
    sq = _mps_structure_factor(state, 2pi / L)
    argument = max(s0 / sq - 1, 0.0)
    return sqrt(argument) / (2pi), s0, sq
end

_residual_scalar(value::Number) = abs(Float64(real(value)))
_residual_scalar(value) = maximum(abs, value)

function normalized_energy_variance(variance_value::Real, energy::Real)
    iszero(energy) && return iszero(variance_value) ? 0.0 : Inf
    return abs(Float64(variance_value)) / abs2(Float64(energy))
end

function _git_revision()
    try
        return readchomp(`git rev-parse HEAD`)
    catch
        return "unknown"
    end
end

function dmrg_point(;
        model::AbstractString, L::Integer, gamma::Real, chi::Integer,
        sigma = nothing, poles = nothing,
        tolerance = 1.0e-8, maxiter = 20, excited = false, seed = 86
    )
    Random.seed!(seed)
    started = time()
    approximation = nothing
    mpo_error = nothing

    if model == "nn"
        couplings = nn_coupling_matrix(L)
        H = exact_mpo(couplings, gamma)
    elseif model == "long_range"
        isnothing(sigma) && throw(ArgumentError("sigma is required for the long-range model"))
        isnothing(poles) && throw(ArgumentError("poles is required for the long-range model"))
        approximation = fit_periodic_soe(L, sigma, poles)
        mpo_error = coupling_error(L, sigma, approximation)
        H = soe_mpo(L, sigma, gamma, approximation)
        couplings = periodic_coupling_matrix(L, sigma)
    else
        throw(ArgumentError("model must be 'nn' or 'long_range'"))
    end
    mpo_bond_dimension = maximum(dim, left_virtualspace(H))

    initial_bond = min(8, chi)
    state0 = FiniteMPS(randn, ComplexF64, L, ℂ^2, ℂ^initial_bond)
    trajectory = Vector{Dict{String, Any}}()
    finalizer = function (iteration, state, operator, environments)
        push!(trajectory, Dict(
            "iteration" => iteration,
            "energy" => real(expectation_value(state, operator, environments)),
        ))
        current_energy = trajectory[end]["energy"]
        println("DMRG L=$L gamma=$gamma chi=$chi iter=$iteration E=$current_energy")
        flush(stdout)
        return state, environments
    end
    algorithm = DMRG2(;
        tol = tolerance, maxiter, verbosity = 1, trscheme = truncrank(chi),
        finalize = finalizer
    )
    state, environments, residual = find_groundstate(state0, H, algorithm)
    energy0 = real(expectation_value(state, H, environments))
    variance0 = real(variance(state, H, environments))
    ratio, s0, sq = _correlation_ratio(state)

    energy1 = nothing
    gap = nothing
    variance1 = nothing
    if excited
        excited_algorithm = DMRG2(;
            tol = tolerance, maxiter, verbosity = 1, trscheme = truncrank(chi)
        )
        energies, states = excitations(
            H, FiniteExcited(; gsalg = excited_algorithm, weight = 10.0), state; num = 1
        )
        energy1 = real(first(energies))
        gap = energy1 - energy0
        variance1 = real(variance(first(states), H))
    end

    ed_energy0 = nothing
    ed_energy1 = nothing
    ed_gap = nothing
    ed_ratio = nothing
    ed_energy_relative_error = nothing
    ratio_absolute_error = nothing
    if L <= 16
        ed_H = ed_hamiltonian(couplings, gamma)
        ed_values, ed_states, _ = ed_lowest(ed_H; number = 2)
        ed_energy0, ed_energy1 = ed_values
        ed_gap = ed_energy1 - ed_energy0
        ed_s0 = structure_factor(first(ed_states), L, 0.0)
        ed_sq = structure_factor(first(ed_states), L, 2pi / L)
        ed_ratio = sqrt(max(ed_s0 / ed_sq - 1, 0.0)) / (2pi)
        ed_energy_relative_error = abs((energy0 - ed_energy0) / ed_energy0)
        ratio_absolute_error = abs(ratio - ed_ratio)
    end

    runtime_seconds = time() - started
    git_commit = _git_revision()
    return Dict{String, Any}(
        "model" => model,
        "sigma" => sigma,
        "L" => L,
        "Gamma" => Float64(gamma),
        "chi" => chi,
        "poles" => poles,
        "mpo_error" => mpo_error,
        "MPO_error" => mpo_error,
        "MPO_bond_dimension" => mpo_bond_dimension,
        "soe_fit_error" => isnothing(approximation) ? nothing : Dict(
            "target" => "finite_periodic_hurwitz",
            "max_relative" => approximation.max_relative_error,
            "rms_relative" => approximation.rms_relative_error,
            "unique_distances" => fld(L, 2),
            "xmin" => approximation.xmin,
            "xmax" => approximation.xmax,
        ),
        "E0" => energy0,
        "E1" => energy1,
        "gap" => gap,
        "ground_variance" => variance0,
        "excited_variance" => variance1,
        "normalized_ground_variance" => normalized_energy_variance(variance0, energy0),
        "normalized_excited_variance" => isnothing(variance1) ? nothing :
            normalized_energy_variance(variance1, energy1),
        "discarded_weight" => nothing,
        "convergence_residual" => _residual_scalar(residual),
        "correlation_ratio" => ratio,
        "S0" => s0,
        "Sq" => sq,
        "ed_E0" => ed_energy0,
        "ed_E1" => ed_energy1,
        "ed_gap" => ed_gap,
        "ed_correlation_ratio" => ed_ratio,
        "ed_energy_relative_error" => ed_energy_relative_error,
        "correlation_ratio_absolute_error" => ratio_absolute_error,
        "trajectory" => trajectory,
        "runtime_seconds" => runtime_seconds,
        "runtime" => runtime_seconds,
        "code_commit" => git_commit,
        "git_commit" => git_commit,
        "timestamp_utc" => string(now(UTC)),
    )
end

function _expand_sweep(sweep)
    model = String(sweep["model"])
    lengths = Int.(sweep["lengths"])
    gammas = Float64.(sweep["gammas"])
    chis = Int.(get(sweep, "chis", [32]))
    sigmas = model == "long_range" ? Float64.(sweep["sigmas"]) : [nothing]
    pole_values = model == "long_range" ? Int.(sweep["poles"]) : [nothing]
    jobs = Dict{String, Any}[]
    for sigma in sigmas, L in lengths, gamma in gammas, chi in chis, poles in pole_values
        push!(jobs, Dict{String, Any}(
            "model" => model,
            "sigma" => sigma,
            "L" => L,
            "gamma" => gamma,
            "chi" => chi,
            "poles" => poles,
            "tolerance" => Float64(get(sweep, "tolerance", 1.0e-8)),
            "maxiter" => Int(get(sweep, "maxiter", 20)),
            "excited" => Bool(get(sweep, "excited", false)),
            "seed" => Int(get(sweep, "seed", 86)),
        ))
    end
    return jobs
end

function read_config_jobs(config::AbstractDict)
    jobs = Dict{String, Any}[]
    for sweep in get(config, "sweeps", [])
        append!(jobs, _expand_sweep(sweep))
    end
    return jobs
end

"""
Map a parameter point to the packed-node resource tier used on SCNet.

The ordering is intentional: chi=256 always uses class D, including L=128;
L=128 at lower chi uses class C; chi=128 at smaller L uses class B.
"""
function resource_class(job::AbstractDict)
    chi = Int(job["chi"])
    L = Int(job["L"])
    chi >= 256 && return "D"
    L >= 128 && return "C"
    chi >= 128 && return "B"
    return "A"
end

function _canonical_cell_value(value)
    isnothing(value) && return "n:null"
    value isa Bool && return value ? "b:true" : "b:false"
    value isa Integer && return "i:" * string(value)
    if value isa AbstractFloat
        normalized = iszero(value) ? zero(value) : value
        return "f:" * @sprintf("%.17g", Float64(normalized))
    end
    value isa AbstractString && return "s:" * JSON.json(value)
    if value isa AbstractVector
        return "a:[" * join(_canonical_cell_value.(value), ",") * "]"
    end
    if value isa AbstractDict
        keys_sorted = sort!(String.(collect(keys(value))))
        entries = (
            JSON.json(key) * ":" * _canonical_cell_value(value[key])
            for key in keys_sorted
        )
        return "d:{" * join(entries, ",") * "}"
    end
    error("unsupported run-spec parameter type $(typeof(value))")
end

function _cell_id(stage::AbstractString, params::AbstractDict)
    payload = "issue86-cell-v1|" * _canonical_cell_value(params)
    digest = first(bytes2hex(sha1(payload)), 32)
    return "$(stage)-$(digest)"
end

function build_run_spec(
        config::AbstractDict;
        run_id::AbstractString,
        stage::AbstractString,
    )
    jobs = read_config_jobs(config)
    cells = map(jobs) do job
        Dict{String, Any}(
            "cell_id" => _cell_id(stage, job),
            "stage" => String(stage),
            "resource_class" => resource_class(job),
            "params" => job,
        )
    end
    cell_ids = [cell["cell_id"] for cell in cells]
    length(unique(cell_ids)) == length(cell_ids) ||
        error("run spec contains duplicate parameter cells")
    return Dict{String, Any}(
        "metadata" => Dict{String, Any}(
            "schema_version" => 1,
            "run_id" => String(run_id),
            "stage" => String(stage),
            "jobs_total" => length(cells),
            "created_utc" => string(now(UTC)),
            "code_commit" => _git_revision(),
            "hamiltonian" => "-sum_{i<j} J_L(|i-j|) Z_i Z_j - Gamma sum_i X_i",
            "boundary" => "periodic image sum via Hurwitz zeta",
        ),
        "cells" => cells,
    )
end

function _successful_manifest(path::AbstractString, cell = nothing)
    isfile(path) || return nothing
    try
        manifest = JSON.parsefile(path)
        get(manifest, "status", nothing) == "success" || return nothing
        get(manifest, "result", nothing) isa AbstractDict || return nothing
        if !isnothing(cell)
            get(manifest, "cell_id", nothing) == cell["cell_id"] || return nothing
            get(manifest, "stage", nothing) == cell["stage"] || return nothing
            get(manifest, "resource_class", nothing) == cell["resource_class"] ||
                return nothing
            haskey(manifest, "params") || return nothing
            _canonical_cell_value(manifest["params"]) ==
                _canonical_cell_value(cell["params"]) || return nothing
        end
        return manifest
    catch
        return nothing
    end
end

function pending_cell_indices(
        spec::AbstractDict,
        output_directory::AbstractString;
        resource_class = nothing,
    )
    pending = Int[]
    for (index, cell) in enumerate(spec["cells"])
        isnothing(resource_class) ||
            cell["resource_class"] == resource_class ||
            continue
        manifest_path = joinpath(
            output_directory, "cells", cell["cell_id"], "manifest.json"
        )
        isnothing(_successful_manifest(manifest_path, cell)) && push!(pending, index)
    end
    return pending
end

function collect_cell_results(spec::AbstractDict, output_directory::AbstractString)
    rows = Dict{String, Any}[]
    for cell in spec["cells"]
        manifest_path = joinpath(
            output_directory, "cells", cell["cell_id"], "manifest.json"
        )
        manifest = _successful_manifest(manifest_path, cell)
        isnothing(manifest) && continue
        result = Dict{String, Any}(manifest["result"])
        result["cell_id"] = cell["cell_id"]
        result["stage"] = cell["stage"]
        result["resource_class"] = cell["resource_class"]
        push!(rows, result)
    end
    return rows
end

function _write_json(path, data)
    open(path, "w") do io
        JSON.print(io, data, 2)
        println(io)
    end
end

function _write_json_atomic(path::AbstractString, data)
    mkpath(dirname(path))
    temporary = path * ".tmp-" * string(getpid()) * "-" * string(rand(UInt))
    try
        _write_json(temporary, data)
        mv(temporary, path; force = true)
    finally
        isfile(temporary) && rm(temporary; force = true)
    end
    return path
end

function _runtime_metadata()
    max_rss = try
        Sys.maxrss()
    catch
        nothing
    end
    return Dict{String, Any}(
        "hostname" => get(ENV, "HOSTNAME", "unknown"),
        "julia_threads" => Threads.nthreads(),
        "blas_threads" => BLAS.get_num_threads(),
        "max_rss_raw" => max_rss,
        "slurm_job_id" => get(ENV, "SLURM_JOB_ID", nothing),
        "slurm_step_id" => get(ENV, "SLURM_STEP_ID", nothing),
        "slurm_cpus_per_task" => get(ENV, "SLURM_CPUS_PER_TASK", nothing),
    )
end

function execute_cell(
        spec::AbstractDict,
        index::Integer,
        output_directory::AbstractString;
        solver = dmrg_point,
    )
    1 <= index <= length(spec["cells"]) ||
        throw(BoundsError(spec["cells"], index))
    cell = spec["cells"][index]
    cell_directory = joinpath(output_directory, "cells", cell["cell_id"])
    manifest_path = joinpath(cell_directory, "manifest.json")
    existing = _successful_manifest(manifest_path, cell)
    isnothing(existing) || return Dict{String, Any}(existing["result"])

    params = cell["params"]
    started = now(UTC)
    runtime = _runtime_metadata()
    println("cell $(cell["cell_id"]) starting: $(params)")
    flush(stdout)

    try
        result = solver(;
            model = String(params["model"]),
            L = Int(params["L"]),
            gamma = Float64(params["gamma"]),
            chi = Int(params["chi"]),
            sigma = get(params, "sigma", nothing),
            poles = get(params, "poles", nothing),
            tolerance = Float64(get(params, "tolerance", 1.0e-8)),
            maxiter = Int(get(params, "maxiter", 20)),
            excited = Bool(get(params, "excited", false)),
            seed = Int(get(params, "seed", 86)),
        )
        manifest = Dict{String, Any}(
            "schema_version" => 1,
            "status" => "success",
            "cell_id" => cell["cell_id"],
            "stage" => cell["stage"],
            "resource_class" => cell["resource_class"],
            "params" => params,
            "runtime" => merge(runtime, Dict(
                "started_utc" => string(started),
                "completed_utc" => string(now(UTC)),
            )),
            "result" => result,
        )
        _write_json_atomic(manifest_path, manifest)
        println("cell $(cell["cell_id"]) completed")
        flush(stdout)
        return result
    catch error
        manifest = Dict{String, Any}(
            "schema_version" => 1,
            "status" => "failed",
            "cell_id" => cell["cell_id"],
            "stage" => cell["stage"],
            "resource_class" => cell["resource_class"],
            "params" => params,
            "runtime" => merge(runtime, Dict(
                "started_utc" => string(started),
                "completed_utc" => string(now(UTC)),
            )),
            "error" => sprint(showerror, error, catch_backtrace()),
        )
        _write_json_atomic(manifest_path, manifest)
        rethrow()
    end
end

function _csv_value(value)
    isnothing(value) && return ""
    value isa AbstractDict && return replace(JSON.json(value), '"' => "\"\"")
    return string(value)
end

function _write_csv(path, rows)
    columns = [
        "model", "sigma", "L", "Gamma", "chi", "poles", "MPO_bond_dimension",
        "MPO_error", "E0", "E1", "gap",
        "ground_variance", "excited_variance",
        "normalized_ground_variance", "normalized_excited_variance",
        "discarded_weight",
        "convergence_residual", "correlation_ratio", "ed_E0", "ed_E1", "ed_gap",
        "ed_correlation_ratio", "ed_energy_relative_error",
        "correlation_ratio_absolute_error", "runtime", "git_commit",
    ]
    open(path, "w") do io
        println(io, join(columns, ","))
        for row in rows
            values = map(columns) do column
                value = _csv_value(get(row, column, nothing))
                occursin(',', value) || occursin('"', value) ? "\"$value\"" : value
            end
            println(io, join(values, ","))
        end
    end
end

function run_jobs(config::AbstractDict, output_directory::AbstractString)
    mkpath(output_directory)
    rows = Dict{String, Any}[]
    jobs = read_config_jobs(config)
    raw_json = joinpath(output_directory, "raw.json")
    raw_csv = joinpath(output_directory, "raw.csv")
    metadata = Dict(
        "hamiltonian" => "-sum_{i<j} J_L(|i-j|) Z_i Z_j - Gamma sum_i X_i",
        "boundary" => "periodic image sum via Hurwitz zeta",
        "observable" => "xi/L = sqrt(S(0)/S(2pi/L)-1)/(2pi)",
        "jobs_total" => length(jobs),
        "started_utc" => string(now(UTC)),
        "code_commit" => _git_revision(),
    )

    for (index, job) in enumerate(jobs)
        println("job $index/$(length(jobs)): $job")
        flush(stdout)
        result = dmrg_point(;
            model = job["model"], L = job["L"], gamma = job["gamma"],
            chi = job["chi"], sigma = job["sigma"], poles = job["poles"],
            tolerance = job["tolerance"], maxiter = job["maxiter"],
            excited = job["excited"], seed = job["seed"],
        )
        push!(rows, result)
        _write_json(raw_json, Dict("metadata" => metadata, "rows" => rows))
        _write_csv(raw_csv, rows)
    end
    metadata["completed_utc"] = string(now(UTC))
    _write_json(raw_json, Dict("metadata" => metadata, "rows" => rows))
    return rows
end

end
