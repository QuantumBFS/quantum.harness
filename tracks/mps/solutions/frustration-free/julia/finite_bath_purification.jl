module FiniteBathPurification

using ITensors
using ITensorMPS
using HDF5: h5open
using KrylovKit: exponentiate
using SHA: sha256
import ITensorMPS: measure!

export FiniteBathParameters,
    EvolutionInterrupted,
    EvolutionResumeState,
    MAX_EVOLUTION_STEPS,
    MAX_IMAGINARY_TIME_STEPS,
    MAX_LOCAL_EXPONENT_MAGNITUDE,
    PurificationSpec,
    PurificationResult,
    evolve_purification,
    identity_purification,
    impurity_observables,
    interleaved_sites,
    non_qn_purification,
    physical_hamiltonian_mpo,
    probe_qn_purification_capability,
    qn_dual_purification,
    validate_purification_fluxes

const ELECTRON_DIMENSION = 4
const QN_GAUGE = "electron_nf_sz_ancilla_particle_hole"
const QN_GAUGE_VERSION = 1
const QN_PURIFICATION_BINDING_DOMAIN =
    "finite_bath_qn_purification_identity"
const QN_PURIFICATION_BINDING_VERSION = 1

_locked_qn_electron_space() = Pair{QN,Int}[
    QN(("Nf", 0, -1), ("Sz", 0)) => 1,
    QN(("Nf", 1, -1), ("Sz", 1)) => 1,
    QN(("Nf", 1, -1), ("Sz", -1)) => 1,
    QN(("Nf", 2, -1), ("Sz", 0)) => 1,
]

struct ChainMappingValidationSeal end
const _CHAIN_MAPPING_VALIDATION_SEAL = ChainMappingValidationSeal()

function _lowercase_sha256(value, name::AbstractString)
    value isa AbstractString && occursin(r"^[0-9a-f]{64}$", value) ||
        throw(ArgumentError("$name must be 64 lowercase hexadecimal digits"))
    return String(value)
end

struct ValidatedChainMappingCapability
    source_bath_sha256::String
    mapping_sha256::String
    epsilon::Tuple{Vararg{Float64}}
    chain_onsite::Tuple{Vararg{Float64}}
    chain_hopping::Tuple{Vararg{Float64}}
    lambda::Float64

    function ValidatedChainMappingCapability(
        seal::ChainMappingValidationSeal;
        source_bath_sha256,
        mapping_sha256,
        epsilon,
        chain_onsite,
        chain_hopping,
        lambda,
    )
        seal === _CHAIN_MAPPING_VALIDATION_SEAL ||
            throw(ArgumentError("invalid chain mapping validation seal"))
        source =
            _lowercase_sha256(source_bath_sha256, "source bath SHA256")
        mapping = _lowercase_sha256(mapping_sha256, "mapping SHA256")
        star_energies = _finite_vector(epsilon, "epsilon")
        isempty(star_energies) &&
            throw(ArgumentError("chain epsilon must contain at least one orbital"))
        onsite = _finite_vector(chain_onsite, "chain_onsite")
        hopping = _finite_vector(
            chain_hopping, "chain_hopping"; nonnegative = true
        )
        hybridization = _finite_real(lambda, "lambda")
        hybridization >= 0 ||
            throw(ArgumentError("lambda must be nonnegative"))
        length(onsite) == length(star_energies) ||
            throw(ArgumentError("chain onsite length mismatch"))
        length(hopping) == max(0, length(star_energies) - 1) ||
            throw(ArgumentError("chain hopping length mismatch"))
        new(
            source,
            mapping,
            Tuple(star_energies),
            Tuple(onsite),
            Tuple(hopping),
            hybridization,
        )
    end
end

struct PurificationConstructionSeal end
const _PURIFICATION_CONSTRUCTION_SEAL = PurificationConstructionSeal()

struct PurificationSpec
    mode::Symbol
    qn_gauge::Union{Nothing,String}
    qn_gauge_version::Union{Nothing,Int}
    base_sector_nf::Union{Nothing,Int}
    base_sector_sz::Union{Nothing,Int}
    parameter_binding_domain::Union{Nothing,String}
    parameter_binding_version::Union{Nothing,Int}
    parameter_binding_sha256::Union{Nothing,String}

    function PurificationSpec(
        seal::PurificationConstructionSeal;
        mode,
        qn_gauge,
        qn_gauge_version,
        base_sector_nf,
        base_sector_sz,
        parameter_binding_domain,
        parameter_binding_version,
        parameter_binding_sha256,
    )
        seal === _PURIFICATION_CONSTRUCTION_SEAL ||
            throw(ArgumentError("invalid purification construction seal"))
        new(
            mode,
            qn_gauge,
            qn_gauge_version,
            base_sector_nf,
            base_sector_sz,
            parameter_binding_domain,
            parameter_binding_version,
            parameter_binding_sha256,
        )
    end
end

non_qn_purification() =
    PurificationSpec(
        _PURIFICATION_CONSTRUCTION_SEAL;
        mode = :non_qn,
        qn_gauge = nothing,
        qn_gauge_version = nothing,
        base_sector_nf = nothing,
        base_sector_sz = nothing,
        parameter_binding_domain = nothing,
        parameter_binding_version = nothing,
        parameter_binding_sha256 = nothing,
    )

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
    bath_representation::Symbol
    chain_onsite::Vector{Float64}
    chain_hopping::Vector{Float64}
    lambda::Float64
    source_bath_sha256::Union{Nothing,String}
    mapping_sha256::Union{Nothing,String}

    function FiniteBathParameters(
        seal::ChainMappingValidationSeal;
        epsilon,
        V,
        U,
        epsilon_d,
        mu,
        bath_representation,
        chain_onsite,
        chain_hopping,
        lambda,
        source_bath_sha256,
        mapping_sha256,
    )
        seal === _CHAIN_MAPPING_VALIDATION_SEAL ||
            throw(ArgumentError("invalid finite-bath construction seal"))
        new(
            copy(epsilon),
            copy(V),
            U,
            epsilon_d,
            mu,
            bath_representation,
            copy(chain_onsite),
            copy(chain_hopping),
            lambda,
            source_bath_sha256,
            mapping_sha256,
        )
    end
end

_binding_float(value) = string(
    reinterpret(UInt64, Float64(value)); base = 16, pad = 16
)

function _binding_float_vector(values)
    return string(
        length(values),
        ":",
        join((_binding_float(value) for value in values), ","),
    )
end

function _binding_string(value)
    value === nothing && return "nothing"
    text = String(value)
    return "$(ncodeunits(text)):$text"
end

_binding_integer(value::Integer) = string(
    reinterpret(UInt64, Int64(value)); base = 16, pad = 16
)

const _PURIFICATION_IDENTITY_KEYS = (
    :mode,
    :qn_gauge,
    :qn_gauge_version,
    :binding_domain,
    :binding_version,
    :base_sector_nf,
    :base_sector_sz,
)

function _purification_identity_binding_sha256(
    parameters::FiniteBathParameters, identity::NamedTuple
)
    keys(identity) == _PURIFICATION_IDENTITY_KEYS ||
        throw(ArgumentError("invalid purification binding identity"))
    canonical = join(
        (
            "binding_domain=" * _binding_string(identity.binding_domain),
            "binding_version=" * _binding_integer(identity.binding_version),
            "mode=" * _binding_string(identity.mode),
            "qn_gauge=" * _binding_string(identity.qn_gauge),
            "qn_gauge_version=" *
                _binding_integer(identity.qn_gauge_version),
            "base_target_sector_nf=" *
                _binding_integer(identity.base_sector_nf),
            "base_target_sector_sz=" *
                _binding_integer(identity.base_sector_sz),
            "epsilon=" * _binding_float_vector(parameters.epsilon),
            "V=" * _binding_float_vector(parameters.V),
            "U=" * _binding_float(parameters.U),
            "epsilon_d=" * _binding_float(parameters.epsilon_d),
            "mu=" * _binding_float(parameters.mu),
            "bath_representation=" *
                _binding_string(parameters.bath_representation),
            "chain_onsite=" *
                _binding_float_vector(parameters.chain_onsite),
            "chain_hopping=" *
                _binding_float_vector(parameters.chain_hopping),
            "lambda=" * _binding_float(parameters.lambda),
            "source_bath_sha256=" *
                _binding_string(parameters.source_bath_sha256),
            "mapping_sha256=" *
                _binding_string(parameters.mapping_sha256),
        ),
        "\n",
    )
    return bytes2hex(sha256(codeunits(canonical)))
end

function _qn_purification_identity(parameters::FiniteBathParameters)
    n_orbitals = length(parameters.epsilon) + 1
    return (;
        mode = :qn_dual,
        qn_gauge = QN_GAUGE,
        qn_gauge_version = QN_GAUGE_VERSION,
        binding_domain = QN_PURIFICATION_BINDING_DOMAIN,
        binding_version = QN_PURIFICATION_BINDING_VERSION,
        base_sector_nf = 2 * n_orbitals,
        base_sector_sz = 0,
    )
end

function _purification_identity(purification::PurificationSpec)
    return (;
        mode = purification.mode,
        qn_gauge = purification.qn_gauge,
        qn_gauge_version = purification.qn_gauge_version,
        binding_domain = purification.parameter_binding_domain,
        binding_version = purification.parameter_binding_version,
        base_sector_nf = purification.base_sector_nf,
        base_sector_sz = purification.base_sector_sz,
    )
end

struct PurificationResult{SiteVector, Diagnostics}
    sites::SiteVector
    psi::MPS
    hamiltonian::MPO
    diagnostics::Diagnostics
end

struct EvolutionResumeState
    completed_steps::Int
    beta_endpoint::Float64
    log_unnormalized_norm::Float64
    maximum_link_dimensions_by_bond::Vector{Int}
    step_history::Vector{NamedTuple}
    expansion_applied::Bool
end

function EvolutionResumeState(;
    completed_steps,
    beta_endpoint,
    log_unnormalized_norm,
    maximum_link_dimensions_by_bond,
    step_history,
    expansion_applied = false,
)
    completed_steps =
        _nonnegative_integer(completed_steps, "completed_steps")
    beta_endpoint = _finite_real(beta_endpoint, "beta_endpoint")
    beta_endpoint >= 0 ||
        throw(ArgumentError("beta_endpoint must be nonnegative"))
    log_unnormalized_norm =
        _finite_real(log_unnormalized_norm, "log_unnormalized_norm")
    maximum_link_dimensions_by_bond isa AbstractVector ||
        throw(
            ArgumentError(
                "maximum_link_dimensions_by_bond must be a vector of nonnegative integers"
            ),
        )
    bond_dimensions = [
        _nonnegative_integer(value, "maximum_link_dimensions_by_bond values")
        for value in maximum_link_dimensions_by_bond
    ]
    step_history isa AbstractVector &&
        all(entry -> entry isa NamedTuple, step_history) ||
        throw(ArgumentError("step_history must be a vector of named tuples"))
    length(step_history) == completed_steps ||
        throw(
            ArgumentError(
                "step_history length must equal completed_steps"
            ),
        )
    expansion_applied isa Bool ||
        throw(ArgumentError("expansion_applied must be a boolean"))
    return EvolutionResumeState(
        completed_steps,
        beta_endpoint,
        log_unnormalized_norm,
        bond_dimensions,
        NamedTuple[step_history...],
        expansion_applied,
    )
end

struct EvolutionInterrupted <: Exception
    psi::MPS
    state::EvolutionResumeState
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
        _CHAIN_MAPPING_VALIDATION_SEAL;
        epsilon = energies,
        V = couplings,
        U = interaction,
        epsilon_d = impurity_energy,
        mu = chemical_potential,
        bath_representation = :direct_star,
        chain_onsite = energies,
        chain_hopping = zeros(max(0, length(energies) - 1)),
        lambda = sqrt(sum(abs2, couplings)),
        source_bath_sha256 = nothing,
        mapping_sha256 = nothing,
    )
end

function FiniteBathParameters(
    validated::ValidatedChainMappingCapability;
    U = 0.8,
    epsilon_d = -Float64(U) / 2,
    mu = 0.0,
)
    interaction = _finite_real(U, "U")
    interaction >= 0 || throw(ArgumentError("U must be nonnegative"))
    impurity_energy = _finite_real(epsilon_d, "epsilon_d")
    chemical_potential = _finite_real(mu, "mu")
    energies = collect(validated.epsilon)
    couplings = [validated.lambda; zeros(length(energies) - 1)]
    return FiniteBathParameters(
        _CHAIN_MAPPING_VALIDATION_SEAL;
        epsilon = energies,
        V = couplings,
        U = interaction,
        epsilon_d = impurity_energy,
        mu = chemical_potential,
        bath_representation = :chain,
        chain_onsite = collect(validated.chain_onsite),
        chain_hopping = collect(validated.chain_hopping),
        lambda = validated.lambda,
        source_bath_sha256 = validated.source_bath_sha256,
        mapping_sha256 = validated.mapping_sha256,
    )
end

function qn_dual_purification(
    parameters::FiniteBathParameters,
    validated::ValidatedChainMappingCapability,
)
    parameters.bath_representation === :chain ||
        throw(ArgumentError("QN dual purification requires chain parameters"))
    parameters.source_bath_sha256 == validated.source_bath_sha256 &&
        parameters.mapping_sha256 == validated.mapping_sha256 &&
        Tuple(parameters.epsilon) == validated.epsilon &&
        Tuple(parameters.V) ==
            (validated.lambda, zeros(length(validated.epsilon) - 1)...) &&
        Tuple(parameters.chain_onsite) == validated.chain_onsite &&
        Tuple(parameters.chain_hopping) == validated.chain_hopping &&
        parameters.lambda == validated.lambda ||
        throw(
            ArgumentError(
                "QN dual purification capability does not match chain parameters"
            ),
        )
    identity = _qn_purification_identity(parameters)
    return PurificationSpec(
        _PURIFICATION_CONSTRUCTION_SEAL;
        mode = identity.mode,
        qn_gauge = identity.qn_gauge,
        qn_gauge_version = identity.qn_gauge_version,
        base_sector_nf = identity.base_sector_nf,
        base_sector_sz = identity.base_sector_sz,
        parameter_binding_domain = identity.binding_domain,
        parameter_binding_version = identity.binding_version,
        parameter_binding_sha256 =
            _purification_identity_binding_sha256(parameters, identity),
    )
end

function _validate_purification_spec(
    parameters::FiniteBathParameters, purification::PurificationSpec
)
    if purification == non_qn_purification()
        return purification
    end
    expected_identity = _qn_purification_identity(parameters)
    identity = _purification_identity(purification)
    identity == expected_identity &&
        purification.parameter_binding_sha256 ==
            _purification_identity_binding_sha256(parameters, identity) &&
        parameters.bath_representation === :chain &&
        parameters.source_bath_sha256 !== nothing &&
        parameters.mapping_sha256 !== nothing ||
        throw(ArgumentError("invalid purification specification"))
    return purification
end

"""Return interleaved Electron sites `[d_phys,d_anc,c1_phys,c1_anc,...]`."""
function interleaved_sites(
    parameters::FiniteBathParameters;
    purification::PurificationSpec = non_qn_purification(),
)
    _validate_purification_spec(parameters, purification)
    n_orbitals = length(parameters.epsilon) + 1
    if purification.mode === :non_qn
        return siteinds(
            "Electron", 2 * n_orbitals; conserve_qns = false
        )
    end
    return siteinds(
        "Electron",
        2 * n_orbitals;
        conserve_qns = true,
        conserve_nf = true,
        conserve_sz = true,
        conserve_nfparity = false,
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

function _qn_identity_pair_tensors(
    sites::AbstractVector{<:Index},
    orbital::Int,
    pair_link::Index,
    left_link,
    right_link,
)
    physical_site = sites[2 * orbital - 1]
    ancilla_site = sites[2 * orbital]
    physical = ITensor(physical_site, pair_link)
    ancilla = ITensor(dag(pair_link), ancilla_site)
    complementary_state = (4, 3, 2, 1)
    for physical_state in 1:ELECTRON_DIMENSION
        ancilla_state = complementary_state[physical_state]
        physical[
            physical_site => physical_state,
            pair_link => physical_state,
        ] = 1.0
        ancilla[
            dag(pair_link) => physical_state,
            ancilla_site => ancilla_state,
        ] = 0.5
    end
    left_link === nothing ||
        (physical *= onehot(dag(left_link) => 1))
    right_link === nothing ||
        (ancilla *= onehot(right_link => 1))
    return physical, ancilla
end

"""
Construct a product of normalized local identity pairs, one per physical
orbital and its adjacent ancilla.
"""
function identity_purification(
    parameters::FiniteBathParameters;
    purification::PurificationSpec = non_qn_purification(),
)
    _validate_purification_spec(parameters, purification)
    sites = interleaved_sites(parameters; purification)
    n_orbitals = length(parameters.epsilon) + 1
    if purification.mode === :non_qn
        pair_links = [
            Index(ELECTRON_DIMENSION, "Link,pair=$orbital")
            for orbital in 1:n_orbitals
        ]
        interpair_links = [
            Index(1, "Link,between=$orbital")
            for orbital in 1:(n_orbitals - 1)
        ]
    else
        pair_space = [
            QN(("Nf", 2, -1), ("Sz", 0)) => 1,
            QN(("Nf", 1, -1), ("Sz", -1)) => 1,
            QN(("Nf", 1, -1), ("Sz", 1)) => 1,
            QN(("Nf", 0, -1), ("Sz", 0)) => 1,
        ]
        pair_links = [
            Index(pair_space; tags = "Link,pair=$orbital")
            for orbital in 1:n_orbitals
        ]
        interpair_links = [
            Index(QN() => 1; tags = "Link,between=$orbital")
            for orbital in 1:(n_orbitals - 1)
        ]
    end
    tensors = Vector{ITensor}(undef, length(sites))
    for orbital in 1:n_orbitals
        left_link = orbital == 1 ? nothing : interpair_links[orbital - 1]
        right_link =
            orbital == n_orbitals ? nothing : interpair_links[orbital]
        physical, ancilla =
            purification.mode === :non_qn ?
            _identity_pair_tensors(
                sites,
                orbital,
                pair_links[orbital],
                left_link,
                right_link,
            ) :
            _qn_identity_pair_tensors(
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
    if purification.mode === :qn_dual
        expected_flux = QN(
            ("Nf", purification.base_sector_nf, -1),
            ("Sz", purification.base_sector_sz),
        )
        flux(psi) == expected_flux ||
            error("QN dual purification has unexpected global flux")
    end
    return sites, psi
end

function _validate_sites(
    sites,
    parameters::FiniteBathParameters,
    purification::PurificationSpec,
)
    _validate_purification_spec(parameters, purification)
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
    qn_enabled = purification.mode === :qn_dual
    all(site -> hasqns(site) == qn_enabled, sites) ||
        throw(
            ArgumentError(
                "site QN structure does not match purification specification"
            ),
        )
    if qn_enabled
        expected_space = _locked_qn_electron_space()
        all(site -> space(site) == expected_space, sites) ||
            throw(
                ArgumentError(
                    "QN Electron sites must have exactly the locked Nf/Sz labels"
                ),
            )
    end
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
    sites::AbstractVector{<:Index},
    parameters::FiniteBathParameters;
    purification::PurificationSpec = non_qn_purification(),
)
    _validate_sites(sites, parameters, purification)
    terms = OpSum()
    impurity = 1
    terms += parameters.epsilon_d - parameters.mu, "Ntot", impurity
    terms += parameters.U, "Nupdn", impurity
    for bath in eachindex(parameters.epsilon)
        bath_site = 2 * bath + 1
        onsite =
            parameters.bath_representation === :chain ?
            parameters.chain_onsite[bath] : parameters.epsilon[bath]
        terms += onsite - parameters.mu, "Ntot", bath_site
    end
    if parameters.bath_representation === :direct_star
        for bath in eachindex(parameters.V), spin in ("up", "dn")
            bath_site = 2 * bath + 1
            terms += parameters.V[bath], "Cdag$spin", impurity, "C$spin", bath_site
            terms += parameters.V[bath], "Cdag$spin", bath_site, "C$spin", impurity
        end
    elseif parameters.bath_representation === :chain
        first_chain_site = 3
        for spin in ("up", "dn")
            terms +=
                parameters.lambda,
                "Cdag$spin",
                impurity,
                "C$spin",
                first_chain_site
            terms +=
                parameters.lambda,
                "Cdag$spin",
                first_chain_site,
                "C$spin",
                impurity
        end
        for link in eachindex(parameters.chain_hopping)
            left_site = 2 * link + 1
            right_site = left_site + 2
            for spin in ("up", "dn")
                terms +=
                    parameters.chain_hopping[link],
                    "Cdag$spin",
                    left_site,
                    "C$spin",
                    right_site
                terms +=
                    parameters.chain_hopping[link],
                    "Cdag$spin",
                    right_site,
                    "C$spin",
                    left_site
            end
        end
    else
        error("unsupported bath representation")
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
    onsite =
        parameters.bath_representation === :chain ?
        parameters.chain_onsite : parameters.epsilon
    hopping =
        parameters.bath_representation === :chain ?
        [parameters.lambda; parameters.chain_hopping] : parameters.V
    for energy in onsite
        bound +=
            2 * abs(energy - parameters.mu)
        isfinite(bound) ||
            throw(ArgumentError("Hamiltonian norm bound must be finite"))
    end
    bound += 4 * sum(hopping)
    isfinite(bound) ||
        throw(ArgumentError("Hamiltonian norm bound must be finite"))
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
    resume_state = nothing,
    step_callback = nothing,
    stop_requested = () -> false,
)
    beta, time_step, cutoff, maxdim =
        _evolution_settings(beta, time_step, cutoff, maxdim)
    bound = _finite_real(hamiltonian_norm_bound, "hamiltonian_norm_bound")
    bound >= 0 ||
        throw(ArgumentError("hamiltonian_norm_bound must be nonnegative"))
    isapprox(norm(psi), 1.0; atol = 64 * eps(Float64), rtol = 0.0) ||
        throw(ArgumentError("input state must be normalized"))

    plan = _evolution_plan(beta, time_step, bound)
    if resume_state !== nothing
        resume_state isa EvolutionResumeState ||
            throw(ArgumentError("resume_state must be an EvolutionResumeState"))
        resume_state.completed_steps <= plan.steps ||
            throw(
                ArgumentError(
                    "resume_state completed_steps exceeds the planned step count"
                ),
            )
        expected_beta_endpoint =
            resume_state.completed_steps == plan.steps ?
            beta : resume_state.completed_steps * plan.effective_time_step
        isapprox(
            resume_state.beta_endpoint,
            expected_beta_endpoint;
            atol = 8 * eps(Float64) * max(1.0, abs(expected_beta_endpoint)),
            rtol = 8 * eps(Float64),
        ) ||
            throw(
                ArgumentError(
                    "resume_state beta_endpoint is inconsistent with the effective step"
                ),
            )
    end
    initial_link_dimensions = linkdims(psi)
    initial_max_link_dimension = maximum(initial_link_dimensions; init = 1)
    expansion_krylov_dimension = _nonnegative_integer(
        krylov_expansion_dim, "krylov_expansion_dim"
    )
    expansion_applied =
        resume_state !== nothing && resume_state.expansion_applied
    if !expansion_applied && expansion_krylov_dimension > 0
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
    expansion_applied = true
    expanded_max_link_dimension = maximum(linkdims(psi); init = 1)
    if resume_state === nothing
        maximum_link_dimensions_by_bond =
            max.(linkdims(psi), initial_link_dimensions)
        log_unnormalized_norm = 0.0
        step_history = NamedTuple[]
        first_step = 1
    else
        length(resume_state.maximum_link_dimensions_by_bond) ==
            length(linkdims(psi)) ||
            throw(
                ArgumentError(
                    "resume_state bond-dimension history does not match the input state"
                ),
            )
        maximum_link_dimensions_by_bond =
            copy(resume_state.maximum_link_dimensions_by_bond)
        log_unnormalized_norm = resume_state.log_unnormalized_norm
        step_history = copy(resume_state.step_history)
        first_step = resume_state.completed_steps + 1
    end
    progress_interval = max(1, cld(max(plan.steps, 1), 20))
    for step_index in first_step:plan.steps
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
        state = EvolutionResumeState(
            completed_steps = step_index,
            beta_endpoint = beta_endpoint,
            log_unnormalized_norm = log_unnormalized_norm,
            maximum_link_dimensions_by_bond =
                copy(maximum_link_dimensions_by_bond),
            step_history = copy(step_history),
            expansion_applied = expansion_applied,
        )
        step_callback === nothing || step_callback(psi, state)
        stop_requested() && throw(EvolutionInterrupted(copy(psi), state))
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

function validate_purification_fluxes(
    sites,
    psi::MPS,
    hamiltonian::MPO,
    purification::PurificationSpec,
)
    purification.mode === :qn_dual &&
        purification.qn_gauge == QN_GAUGE &&
        purification.qn_gauge_version == QN_GAUGE_VERSION &&
        purification.parameter_binding_domain ==
            QN_PURIFICATION_BINDING_DOMAIN &&
        purification.parameter_binding_version ==
            QN_PURIFICATION_BINDING_VERSION &&
        purification.parameter_binding_sha256 !== nothing &&
        occursin(
            r"^[0-9a-f]{64}$", purification.parameter_binding_sha256
        ) &&
        purification.base_sector_nf isa Int &&
        purification.base_sector_nf >= 4 &&
        iseven(purification.base_sector_nf) &&
        purification.base_sector_sz == 0 ||
        throw(ArgumentError("invalid validated QN purification specification"))
    expected_length = purification.base_sector_nf
    length(sites) == expected_length ||
        throw(ArgumentError("QN site count does not match the base sector"))
    expected_space = _locked_qn_electron_space()
    all(site -> space(site) == expected_space, sites) ||
        throw(
            ArgumentError(
                "QN Electron site labels do not match the locked gauge"
            ),
        )
    base_flux = QN(
        ("Nf", purification.base_sector_nf, -1),
        ("Sz", purification.base_sector_sz),
    )
    flux(psi) == base_flux ||
        throw(
            ArgumentError(
                "purification MPS flux does not match the base sector"
            ),
        )
    zero_flux = QN(("Nf", 0, -1), ("Sz", 0))
    flux(hamiltonian) == zero_flux ||
        throw(ArgumentError("physical Hamiltonian MPO must have zero QN flux"))
    return nothing
end

function _locked_probe_mapping_capability()
    return ValidatedChainMappingCapability(
        _CHAIN_MAPPING_VALIDATION_SEAL;
        source_bath_sha256 = bytes2hex(sha256("locked-qn-probe-bath")),
        mapping_sha256 = bytes2hex(sha256("locked-qn-probe-mapping")),
        epsilon = [0.0],
        chain_onsite = [0.0],
        chain_hopping = Float64[],
        lambda = 0.1,
    )
end

function _probe_operator_sectors(sites, psi, purification)
    expected = (
        ("Cdagup", purification.base_sector_nf + 1, 1),
        ("Cdagdn", purification.base_sector_nf + 1, -1),
        ("Cup", purification.base_sector_nf - 1, -1),
        ("Cdn", purification.base_sector_nf - 1, 1),
    )
    for (operator_name, nf, sz) in expected
        branch = deepcopy(psi)
        orthogonalize!(branch, 1)
        branch[1] = noprime(op(operator_name, sites[1]) * branch[1])
        norm(branch) > 0 ||
            error("locked QN probe operator branch unexpectedly vanished")
        flux(branch) == QN(("Nf", nf, -1), ("Sz", sz)) ||
            error("locked QN probe operator sector mismatch")
    end
    return true
end

function _run_qn_purification_capability_probe()
    validated = _locked_probe_mapping_capability()
    parameters = FiniteBathParameters(
        validated; U = 0.8, epsilon_d = -0.4, mu = 0.0
    )
    purification = qn_dual_purification(parameters, validated)
    sites, psi =
        identity_purification(parameters; purification = purification)
    hamiltonian = physical_hamiltonian_mpo(
        sites, parameters; purification = purification
    )
    validate_purification_fluxes(sites, psi, hamiltonian, purification)

    operator_sectors_valid =
        _probe_operator_sectors(sites, psi, purification)
    evolved, _ = _evolve_normalized_state(
        copy(psi),
        hamiltonian;
        beta = 0.02,
        time_step = 0.02,
        cutoff = 1.0e-12,
        maxdim = 16,
        krylov_expansion_dim = 0,
        hamiltonian_norm_bound = _hamiltonian_norm_bound(parameters),
    )
    flux(evolved) == flux(psi) ||
        error("locked QN probe TDVP step changed the base sector")

    hdf5_roundtrip_valid = mktempdir() do directory
        path = joinpath(directory, "qn-probe.h5")
        h5open(path, "w") do file
            write(file, "psi", evolved)
        end
        restored = h5open(path, "r") do file
            read(file, "psi", MPS)
        end
        flux(restored) == flux(evolved) &&
            isapprox(norm(restored), norm(evolved); atol = 1.0e-12)
    end
    hdf5_roundtrip_valid ||
        error("locked QN probe HDF5 round trip changed the state")

    return (;
        site_labels_valid = true,
        identity_sector_valid = true,
        mpo_zero_flux_valid = true,
        operator_sectors_valid,
        tdvp_step_valid = true,
        hdf5_roundtrip_valid,
    )
end

function _probe_qn_purification_capability(stage::Function)
    try
        checks = stage()
        return (;
            supported = true,
            qn_gauge = QN_GAUGE,
            qn_gauge_version = QN_GAUGE_VERSION,
            julia_version = string(VERSION),
            itensors_version = string(pkgversion(ITensors)),
            itensormps_version = string(pkgversion(ITensorMPS)),
            site_labels_valid = checks.site_labels_valid,
            identity_sector_valid = checks.identity_sector_valid,
            mpo_zero_flux_valid = checks.mpo_zero_flux_valid,
            operator_sectors_valid = checks.operator_sectors_valid,
            tdvp_step_valid = checks.tdvp_step_valid,
            hdf5_roundtrip_valid = checks.hdf5_roundtrip_valid,
            failure = nothing,
        )
    catch exception
        return (;
            supported = false,
            qn_gauge = QN_GAUGE,
            qn_gauge_version = QN_GAUGE_VERSION,
            julia_version = string(VERSION),
            itensors_version = string(pkgversion(ITensors)),
            itensormps_version = string(pkgversion(ITensorMPS)),
            site_labels_valid = false,
            identity_sector_valid = false,
            mpo_zero_flux_valid = false,
            operator_sectors_valid = false,
            tdvp_step_valid = false,
            hdf5_roundtrip_valid = false,
            failure = sprint(showerror, exception),
        )
    end
end

probe_qn_purification_capability() =
    _probe_qn_purification_capability(_run_qn_purification_capability_probe)

end
