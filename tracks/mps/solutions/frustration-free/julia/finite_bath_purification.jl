module FiniteBathPurification

using ITensors
using ITensorMPS
using KrylovKit: exponentiate
import ITensorMPS: measure!

export FiniteBathParameters,
    MAX_EVOLUTION_STEPS,
    MAX_IMAGINARY_TIME_STEPS,
    MAX_LOCAL_EXPONENT_MAGNITUDE,
    PurificationResult,
    evolve_purification,
    identity_purification,
    impurity_observables,
    interleaved_sites,
    physical_hamiltonian_mpo

const ELECTRON_DIMENSION = 4

"""
Maximum number of inverse-temperature increments accepted by
`evolve_purification`. Larger requests are rejected before allocating history
or starting TDVP because they are not practical interactive convergence runs.
"""
const MAX_EVOLUTION_STEPS = 100_000
const MAX_IMAGINARY_TIME_STEPS = MAX_EVOLUTION_STEPS

"""
Maximum accepted upper bound on the magnitude of each local imaginary-time
exponent. Evolution increments are subdivided so that
`beta_increment * hamiltonian_norm_bound / 2` does not exceed this value.
"""
const MAX_LOCAL_EXPONENT_MAGNITUDE = 32.0

mutable struct TDVPStepMetricsObserver <: AbstractObserver
    max_truncation_error::Float64
    observer_visible_krylov_updates::Int
end

TDVPStepMetricsObserver() = TDVPStepMetricsObserver(0.0, 0)

function measure!(
    observer::TDVPStepMetricsObserver;
    spec = nothing,
    info = nothing,
    kwargs...,
)
    if spec !== nothing
        observer.max_truncation_error =
            max(observer.max_truncation_error, Float64(spec.truncerr))
    end
    info !== nothing && hasproperty(info, :info) &&
        (observer.observer_visible_krylov_updates += 1)
    return nothing
end

mutable struct KrylovStepMetrics
    all_converged::Bool
    max_error_estimate::Float64
    num_operations::Int
    num_iterations::Int
    local_updates::Int
end

KrylovStepMetrics() = KrylovStepMetrics(true, 0.0, 0, 0, 0)

function _accumulate_krylov!(metrics::KrylovStepMetrics, info)
    metrics.all_converged &=
        hasproperty(info, :converged) && info.converged == 1
    if hasproperty(info, :normres)
        metrics.max_error_estimate =
            max(metrics.max_error_estimate, Float64(info.normres))
    end
    hasproperty(info, :numops) &&
        (metrics.num_operations += Int(info.numops))
    hasproperty(info, :numiter) &&
        (metrics.num_iterations += Int(info.numiter))
    metrics.local_updates += 1
    return metrics
end

function _tracked_exponentiate_updater(
    operator,
    initial_state;
    internal_kwargs,
    metrics::KrylovStepMetrics,
    kwargs...,
)
    state, info = exponentiate(
        operator, internal_kwargs.time_step, initial_state; kwargs...
    )
    _accumulate_krylov!(metrics, info)
    return state, (; info)
end

struct FiniteBathParameters
    epsilon::Vector{Float64}
    V::Vector{Float64}
    U::Float64
    epsilon_d::Float64
    mu::Float64
end

struct PurificationResult{SiteVector, Diagnostics}
    sites::SiteVector
    psi::MPS
    hamiltonian::MPO
    diagnostics::Diagnostics
end

function _finite_real(value, name::AbstractString)
    value isa Real && !(value isa Bool) ||
        throw(ArgumentError("$name must be a real number"))
    converted = Float64(value)
    isfinite(converted) || throw(ArgumentError("$name must be finite"))
    return converted
end

function _finite_vector(values, name::AbstractString; nonnegative::Bool = false)
    values isa AbstractVector ||
        throw(ArgumentError("$name must be a vector of real numbers"))
    converted = Float64[]
    sizehint!(converted, length(values))
    for value in values
        entry = _finite_real(value, "$name values")
        nonnegative && entry < 0 &&
            throw(ArgumentError("$name values must be nonnegative"))
        push!(converted, entry)
    end
    return converted
end

function FiniteBathParameters(
    epsilon,
    V;
    U = 0.8,
    epsilon_d = -Float64(U) / 2,
    mu = 0.0,
)
    energies = _finite_vector(epsilon, "epsilon")
    couplings = _finite_vector(V, "V"; nonnegative = true)
    length(energies) == length(couplings) ||
        throw(ArgumentError("epsilon and V must have the same length"))
    interaction = _finite_real(U, "U")
    interaction >= 0 || throw(ArgumentError("U must be nonnegative"))
    impurity_energy = _finite_real(epsilon_d, "epsilon_d")
    chemical_potential = _finite_real(mu, "mu")
    return FiniteBathParameters(
        energies, couplings, interaction, impurity_energy, chemical_potential
    )
end

"""Return interleaved Electron sites `[d_phys,d_anc,c1_phys,c1_anc,...]`."""
function interleaved_sites(parameters::FiniteBathParameters)
    n_orbitals = length(parameters.epsilon) + 1
    return siteinds(
        "Electron", 2 * n_orbitals; conserve_qns = false
    )
end

function _identity_pair_tensors(
    sites::AbstractVector{<:Index},
    orbital::Int,
    pair_link::Index,
    left_link,
    right_link,
)
    physical_site = sites[2 * orbital - 1]
    ancilla_site = sites[2 * orbital]
    physical = ITensor(physical_site, pair_link)
    ancilla = ITensor(pair_link, ancilla_site)
    for state_index in 1:ELECTRON_DIMENSION
        physical[physical_site => state_index, pair_link => state_index] = 1.0
        ancilla[pair_link => state_index, ancilla_site => state_index] = 0.5
    end
    left_link === nothing || (physical *= onehot(left_link => 1))
    right_link === nothing || (ancilla *= onehot(right_link => 1))
    return physical, ancilla
end

"""
Construct a product of normalized local identity pairs, one per physical
orbital and its adjacent ancilla.
"""
function identity_purification(parameters::FiniteBathParameters)
    sites = interleaved_sites(parameters)
    n_orbitals = length(parameters.epsilon) + 1
    pair_links = [
        Index(ELECTRON_DIMENSION, "Link,pair=$orbital")
        for orbital in 1:n_orbitals
    ]
    interpair_links = [
        Index(1, "Link,between=$orbital")
        for orbital in 1:(n_orbitals - 1)
    ]
    tensors = Vector{ITensor}(undef, length(sites))
    for orbital in 1:n_orbitals
        left_link = orbital == 1 ? nothing : interpair_links[orbital - 1]
        right_link =
            orbital == n_orbitals ? nothing : interpair_links[orbital]
        physical, ancilla = _identity_pair_tensors(
            sites,
            orbital,
            pair_links[orbital],
            left_link,
            right_link,
        )
        tensors[2 * orbital - 1] = physical
        tensors[2 * orbital] = ancilla
    end
    psi = MPS(tensors)
    normalize!(psi)
    return sites, psi
end

function _validate_sites(sites, parameters::FiniteBathParameters)
    sites isa AbstractVector ||
        throw(ArgumentError("sites must be a vector of Electron site indices"))
    expected_length = 2 * (length(parameters.epsilon) + 1)
    length(sites) == expected_length ||
        throw(
            ArgumentError(
                "sites must contain $expected_length interleaved physical/ancilla indices"
            ),
        )
    all(site -> dim(site) == ELECTRON_DIMENSION, sites) ||
        throw(ArgumentError("all Electron site indices must have dimension 4"))
    allunique(sites) ||
        throw(ArgumentError("site indices must be unique"))
    all(site -> hastags(site, "Electron") && hastags(site, "Site"), sites) ||
        throw(ArgumentError("all sites must carry Electron and Site tags"))
    site_tags = string.(tags.(sites))
    allunique(site_tags) ||
        throw(ArgumentError("Electron site tag sets must be unique"))
    return nothing
end

"""
Build the grand-canonical Anderson Hamiltonian on odd (physical) sites.

Fermionic `Cdag*`/`C*` operators let `OpSum` insert Jordan-Wigner parity
strings across every intervening site, including interleaved ancillas.
"""
function physical_hamiltonian_mpo(
    sites::AbstractVector{<:Index}, parameters::FiniteBathParameters
)
    _validate_sites(sites, parameters)
    terms = OpSum()
    impurity = 1
    terms += parameters.epsilon_d - parameters.mu, "Ntot", impurity
    terms += parameters.U, "Nupdn", impurity
    for bath in eachindex(parameters.epsilon)
        bath_site = 2 * bath + 1
        terms +=
            parameters.epsilon[bath] - parameters.mu, "Ntot", bath_site
        for spin in ("up", "dn")
            terms +=
                parameters.V[bath],
                "Cdag$spin",
                impurity,
                "C$spin",
                bath_site
            terms +=
                parameters.V[bath],
                "Cdag$spin",
                bath_site,
                "C$spin",
                impurity
        end
    end
    return MPO(terms, sites)
end

"""Measure physical impurity total and double occupancy."""
function impurity_observables(psi::MPS)
    occupancy = real(expect(psi, "Ntot")[1])
    double_occupancy = real(expect(psi, "Nupdn")[1])
    return (; occupancy, double_occupancy)
end

function _evolution_settings(beta, time_step, cutoff, maxdim)
    inverse_temperature = _finite_real(beta, "beta")
    inverse_temperature >= 0 ||
        throw(ArgumentError("beta must be nonnegative"))
    step = _finite_real(time_step, "time_step")
    step > 0 || throw(ArgumentError("time_step must be positive"))
    truncation = _finite_real(cutoff, "cutoff")
    truncation >= 0 || throw(ArgumentError("cutoff must be nonnegative"))
    maxdim isa Integer && !(maxdim isa Bool) ||
        throw(ArgumentError("maxdim must be a positive integer"))
    maxdim > 0 || throw(ArgumentError("maxdim must be a positive integer"))
    return inverse_temperature, step, truncation, Int(maxdim)
end

function _nonnegative_integer(value, name)
    value isa Integer && !(value isa Bool) && value >= 0 ||
        throw(ArgumentError("$name must be a nonnegative integer"))
    return Int(value)
end

function _step_count(
    beta::Float64, time_step::Float64; label::AbstractString = "requested"
)
    iszero(beta) && return 0
    ratio = beta / time_step
    isfinite(ratio) ||
        throw(
            ArgumentError(
                "$label beta/time_step must be finite and representable as a step count"
            ),
        )
    ratio <= MAX_EVOLUTION_STEPS ||
        throw(
            ArgumentError(
                "$label step count exceeds MAX_EVOLUTION_STEPS=$(MAX_EVOLUTION_STEPS)"
            ),
        )
    nearest = round(Int, ratio)
    if isapprox(ratio, nearest; atol = 8 * eps(Float64), rtol = 8 * eps(Float64))
        return max(1, nearest)
    end
    steps = ceil(Int, ratio)
    steps <= MAX_EVOLUTION_STEPS ||
        throw(
            ArgumentError(
                "$label step count exceeds MAX_EVOLUTION_STEPS=$(MAX_EVOLUTION_STEPS)"
            ),
        )
    return steps
end

"""
Conservative triangle-inequality upper bound on the finite-bath Hamiltonian
operator norm. Each hopping monomial is bounded separately.
"""
function _hamiltonian_norm_bound(parameters::FiniteBathParameters)
    bound =
        2 * abs(parameters.epsilon_d - parameters.mu) + parameters.U
    for bath in eachindex(parameters.epsilon)
        bound +=
            2 * abs(parameters.epsilon[bath] - parameters.mu) +
            4 * parameters.V[bath]
        isfinite(bound) ||
            throw(ArgumentError("Hamiltonian norm bound must be finite"))
    end
    return bound
end

function _evolution_plan(
    beta::Float64,
    requested_time_step::Float64,
    hamiltonian_norm_bound::Float64,
)
    requested_steps = _step_count(
        beta, requested_time_step; label = "requested"
    )
    maximum_safe_beta_increment =
        iszero(hamiltonian_norm_bound) ?
        Inf :
        2 * MAX_LOCAL_EXPONENT_MAGNITUDE / hamiltonian_norm_bound
    effective_time_step =
        min(requested_time_step, maximum_safe_beta_increment)
    steps = _step_count(
        beta, effective_time_step; label = "safe subdivision"
    )
    return (;
        requested_steps,
        steps,
        effective_time_step,
        maximum_safe_beta_increment,
    )
end

"""
Evolve an already-normalized MPS by `exp(-beta*K/2)`, renormalizing after
each increment and retaining the removed logarithmic norm. This is the shared
TDVP engine for the thermal purification and Green-function branches.
"""
function _evolve_normalized_state(
    psi::MPS,
    hamiltonian::MPO;
    beta,
    time_step,
    cutoff,
    maxdim,
    krylov_expansion_dim,
    hamiltonian_norm_bound,
    progress = false,
    progress_label = "evolution",
)
    beta, time_step, cutoff, maxdim =
        _evolution_settings(beta, time_step, cutoff, maxdim)
    bound = _finite_real(hamiltonian_norm_bound, "hamiltonian_norm_bound")
    bound >= 0 ||
        throw(ArgumentError("hamiltonian_norm_bound must be nonnegative"))
    isapprox(norm(psi), 1.0; atol = 64 * eps(Float64), rtol = 0.0) ||
        throw(ArgumentError("input state must be normalized"))

    plan = _evolution_plan(beta, time_step, bound)
    initial_link_dimensions = linkdims(psi)
    initial_max_link_dimension = maximum(initial_link_dimensions; init = 1)
    expansion_krylov_dimension = _nonnegative_integer(
        krylov_expansion_dim, "krylov_expansion_dim"
    )
    if expansion_krylov_dimension > 0
        psi = expand(
            psi,
            hamiltonian;
            alg = "global_krylov",
            krylovdim = expansion_krylov_dimension,
            cutoff = max(cutoff, eps(Float64)),
            apply_kwargs = (; maxdim),
        )
        normalize!(psi)
    end
    expanded_max_link_dimension = maximum(linkdims(psi); init = 1)
    maximum_link_dimensions_by_bond =
        max.(linkdims(psi), initial_link_dimensions)
    log_unnormalized_norm = 0.0
    step_history = NamedTuple[]
    progress_interval = max(1, cld(max(plan.steps, 1), 20))
    for step_index in 1:plan.steps
        beta_increment =
            step_index == plan.steps ?
            beta - plan.effective_time_step * (plan.steps - 1) :
            plan.effective_time_step
        truncation_metrics = TDVPStepMetricsObserver()
        krylov_metrics = KrylovStepMetrics()
        function tracked_updater(
            operator, initial_state; internal_kwargs, kwargs...
        )
            return _tracked_exponentiate_updater(
                operator,
                initial_state;
                internal_kwargs,
                metrics = krylov_metrics,
                kwargs...,
            )
        end
        psi = tdvp(
            hamiltonian,
            -beta_increment / 2,
            psi;
            nsteps = 1,
            nsite = 2,
            cutoff,
            maxdim,
            normalize = false,
            outputlevel = 0,
            updater = tracked_updater,
            (observer!) = truncation_metrics,
        )
        normalization_logs = Float64[]
        normalize!(psi; lognorm! = normalization_logs)
        length(normalization_logs) == 1 ||
            error("ITensorMPS normalization did not report exactly one log norm")
        log_norm_increment = only(normalization_logs)
        isfinite(log_norm_increment) ||
            error("imaginary-time evolution produced a non-finite log norm")
        krylov_metrics.local_updates > 0 ||
            error("TDVP did not expose Krylov updater diagnostics")
        log_unnormalized_norm += log_norm_increment
        maximum_link_dimensions_by_bond =
            max.(maximum_link_dimensions_by_bond, linkdims(psi))
        beta_endpoint =
            step_index == plan.steps ?
            beta : step_index * plan.effective_time_step
        push!(
            step_history,
            (;
                beta_endpoint,
                beta_increment,
                log_norm_increment,
                cumulative_log_norm = log_unnormalized_norm,
                max_link_dimension = maximum(linkdims(psi); init = 1),
                max_truncation_error =
                    truncation_metrics.max_truncation_error,
                krylov_all_converged = krylov_metrics.all_converged,
                krylov_max_error_estimate =
                    krylov_metrics.max_error_estimate,
                krylov_num_operations = krylov_metrics.num_operations,
                krylov_num_iterations = krylov_metrics.num_iterations,
                krylov_local_updates = krylov_metrics.local_updates,
                observer_visible_krylov_updates =
                    truncation_metrics.observer_visible_krylov_updates,
            ),
        )
        if progress &&
           (step_index % progress_interval == 0 || step_index == plan.steps)
            latest = last(step_history)
            println(
                "progress phase=tdvp evolution=$(progress_label) " *
                "step=$(step_index) total_steps=$(plan.steps) " *
                "beta_endpoint=$(latest.beta_endpoint) " *
                "max_link_dimension=$(latest.max_link_dimension) " *
                "truncation_max_error=$(latest.max_truncation_error) " *
                "krylov_all_converged=$(latest.krylov_all_converged) " *
                "krylov_max_error_estimate=$(latest.krylov_max_error_estimate)",
            )
            flush(stdout)
        end
    end
    normalize!(psi)
    return psi, (;
        beta,
        steps = plan.steps,
        norm = norm(psi),
        max_link_dimension = maximum(linkdims(psi); init = 1),
        maximum_link_dimensions_by_bond,
        initial_max_link_dimension,
        expanded_max_link_dimension,
        expansion_krylov_dimension,
        time_step,
        requested_time_step = time_step,
        effective_time_step = plan.effective_time_step,
        requested_steps = plan.requested_steps,
        hamiltonian_norm_bound = bound,
        maximum_safe_beta_increment = plan.maximum_safe_beta_increment,
        max_allowed_local_exponent_magnitude =
            MAX_LOCAL_EXPONENT_MAGNITUDE,
        cutoff,
        maxdim,
        log_unnormalized_norm,
        step_history,
        metric_availability = (
            truncation_error = "ITensor two-site SVD spec.truncerr",
            krylov_error = "KrylovKit exponentiate info.normres estimate",
        ),
    )
end

"""
Evolve the physical half of the purification by `exp(-beta*K/2)` with
two-site TDVP. `time_step` is an inverse-temperature increment.
"""
function evolve_purification(
    parameters::FiniteBathParameters;
    beta,
    time_step = 0.05,
    cutoff = 1.0e-12,
    maxdim = 256,
    krylov_expansion_dim = 0,
    progress = false,
    progress_label = "thermal",
)
    beta, time_step, cutoff, maxdim =
        _evolution_settings(beta, time_step, cutoff, maxdim)
    hamiltonian_norm_bound = _hamiltonian_norm_bound(parameters)
    sites, psi = identity_purification(parameters)
    hamiltonian = physical_hamiltonian_mpo(sites, parameters)
    psi, evolution = _evolve_normalized_state(
        psi,
        hamiltonian;
        beta,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
        hamiltonian_norm_bound,
        progress,
        progress_label,
    )
    diagnostics = (;
        parameters,
        evolution...,
    )
    return PurificationResult(sites, psi, hamiltonian, diagnostics)
end

end
