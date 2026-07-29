module FiniteBathObservables

using ITensors
using ITensorMPS

const PARENT_MODULE = parentmodule(@__MODULE__)
isdefined(PARENT_MODULE, :FiniteBathCheckpoint) ||
    Base.include(
        PARENT_MODULE, joinpath(@__DIR__, "finite_bath_checkpoint.jl")
    )

using ..FiniteBathPurification:
    FiniteBathParameters,
    PurificationSpec,
    PurificationResult,
    _evolve_normalized_state,
    _evolution_settings,
    _finite_real,
    _hamiltonian_norm_bound,
    _nonnegative_integer,
    evolve_purification,
    identity_purification,
    impurity_observables,
    non_qn_purification,
    physical_hamiltonian_mpo,
    validate_purification_fluxes
using ..FiniteBathCheckpoint: ObservableCursor, ObservableResumeState

export FiniteBathContext,
    AppliedOperatorBranch,
    ObservableCursor,
    ObservableInterrupted,
    OperatorSector,
    build_finite_bath_context,
    copy_identity_purification,
    finite_bath_observables,
    impurity_green_function,
    operator_sector

const GREEN_FUNCTION_CONVENTION =
    "G_sigma(tau) = -Tr[exp(-(beta-tau)K) d_sigma exp(-tau K) d_sigma^dag] / Z"
const MODULE_VERSION = "1.1.0"
const SPIN_TRANSFORM_CONVENTION =
    "the same real Q is used for up and down"

struct ObservableInterrupted <: Exception
    psi::Union{Nothing,MPS}
    state::ObservableResumeState
end

const _NEVER_STOP = () -> false

struct FiniteBathContext{P,S,I,H}
    parameters::P
    purification::PurificationSpec
    sites::S
    identity::I
    hamiltonian::H
    hamiltonian_norm_bound::Float64
    spin_qn_enabled::Bool
    bath_representation::Symbol
    chain_mapping_sha256::Union{Nothing,String}
    spin_transform::String
    reuse_policy::String
end

struct OperatorSector
    insertion::Symbol
    spin::Symbol
    nf::Int
    sz::Int

    function OperatorSector(insertion, spin, nf, sz)
        insertion in (:creation, :annihilation) ||
            throw(ArgumentError("operator sector insertion is invalid"))
        spin in (:up, :dn) ||
            throw(ArgumentError("operator sector spin is invalid"))
        nf isa Integer && !(nf isa Bool) && nf >= 0 ||
            throw(ArgumentError("operator sector Nf is invalid"))
        expected_sz =
            (insertion, spin) in
            ((:creation, :up), (:annihilation, :dn)) ? 1 : -1
        sz == expected_sz ||
            throw(ArgumentError("operator sector Sz is invalid"))
        return new(insertion, spin, Int(nf), expected_sz)
    end
end

struct AppliedOperatorBranch
    psi::Union{Nothing,MPS}
    expected_sector::Union{Nothing,OperatorSector}
    log_norm::Float64
    status::Symbol
end

function operator_sector(
    purification::PurificationSpec, insertion, spin
)
    purification.mode === :qn_dual ||
        throw(ArgumentError("operator sectors require QN purification"))
    insertion in (:creation, :annihilation) ||
        throw(ArgumentError("insertion must be :creation or :annihilation"))
    spin in (:up, :dn) ||
        throw(ArgumentError("spin must be :up or :dn"))
    delta_nf = insertion === :creation ? 1 : -1
    delta_sz =
        (insertion, spin) in ((:creation, :up), (:annihilation, :dn)) ?
        1 : -1
    return OperatorSector(
        insertion,
        spin,
        purification.base_sector_nf + delta_nf,
        delta_sz,
    )
end

function build_finite_bath_context(
    parameters::FiniteBathParameters;
    purification::PurificationSpec = non_qn_purification(),
)
    sites, identity = identity_purification(parameters; purification)
    hamiltonian =
        physical_hamiltonian_mpo(sites, parameters; purification)
    purification.mode === :qn_dual &&
        validate_purification_fluxes(
            sites, identity, hamiltonian, purification
        )
    return FiniteBathContext(
        parameters,
        purification,
        sites,
        identity,
        hamiltonian,
        _hamiltonian_norm_bound(parameters),
        purification.mode === :qn_dual,
        parameters.bath_representation,
        parameters.mapping_sha256,
        SPIN_TRANSFORM_CONVENTION,
        "identity template and immutable MPO may be deep-copied across branches",
    )
end

copy_identity_purification(context::FiniteBathContext) =
    deepcopy(context.identity)

function _context_on_sites(
    parameters::FiniteBathParameters,
    sites::AbstractVector{<:Index};
    purification::PurificationSpec = non_qn_purification(),
)
    template_sites, identity =
        identity_purification(parameters; purification)
    for index in eachindex(identity)
        identity[index] = replaceind(
            identity[index], template_sites[index], sites[index]
        )
    end
    return FiniteBathContext(
        parameters,
        purification,
        collect(sites),
        identity,
        physical_hamiltonian_mpo(sites, parameters; purification),
        _hamiltonian_norm_bound(parameters),
        purification.mode === :qn_dual,
        parameters.bath_representation,
        parameters.mapping_sha256,
        SPIN_TRANSFORM_CONVENTION,
        "identity template and immutable MPO may be deep-copied across branches",
    )
end

function _evolve_context(
    context::FiniteBathContext;
    beta,
    time_step,
    cutoff,
    maxdim,
    krylov_expansion_dim,
    progress,
    progress_label,
)
    beta, time_step, cutoff, maxdim =
        _evolution_settings(beta, time_step, cutoff, maxdim)
    psi, evolution = _evolve_normalized_state(
        copy_identity_purification(context),
        context.hamiltonian;
        beta,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
        hamiltonian_norm_bound = context.hamiltonian_norm_bound,
        progress,
        progress_label,
    )
    diagnostics = (; parameters = context.parameters, evolution...)
    return PurificationResult(
        context.sites, psi, context.hamiltonian, diagnostics
    )
end

function _validated_tau(tau, beta::Float64)
    tau isa AbstractVector ||
        throw(ArgumentError("tau must be a vector of real numbers"))
    isempty(tau) &&
        throw(ArgumentError("tau must contain at least one point"))
    values = Float64[]
    sizehint!(values, length(tau))
    for value in tau
        point = _finite_real(value, "tau values")
        0.0 <= point <= beta ||
            throw(ArgumentError("tau values must lie in [0, beta]"))
        push!(values, point)
    end
    return values
end

function _spin_label(spin)
    spin in (:up, "up") && return :up
    spin in (:dn, :down, "dn", "down") && return :dn
    throw(ArgumentError("spin must be :up or :dn"))
end

_creation_name(::Val{:up}) = "Cdagup"
_creation_name(::Val{:dn}) = "Cdagdn"
_annihilation_name(::Val{:up}) = "Cup"
_annihilation_name(::Val{:dn}) = "Cdn"

function _apply_impurity_operator(
    psi::MPS,
    physical_site::Index,
    spin::Symbol,
    insertion::Symbol,
    expected_sector::Union{Nothing,OperatorSector},
)
    if hasqns(physical_site)
        expected_sector !== nothing ||
            throw(ArgumentError(
                "QN operator branch requires an expected sector"
            ))
        expected_sector.insertion === insertion &&
            expected_sector.spin === spin ||
            throw(ArgumentError(
                "operator and expected sector coordinates disagree"
            ))
    else
        expected_sector === nothing ||
            throw(ArgumentError(
                "non-QN operator branch cannot claim a sector"
            ))
    end
    branch = deepcopy(psi)
    orthogonalize!(branch, 1)
    operator_name =
        insertion === :creation ?
        _creation_name(Val(spin)) :
        _annihilation_name(Val(spin))
    branch[1] =
        noprime(op(operator_name, physical_site) * branch[1])
    amplitude = norm(branch)
    isfinite(amplitude) ||
        error("impurity creation produced a non-finite branch amplitude")
    if iszero(amplitude)
        return AppliedOperatorBranch(
            nothing, expected_sector, -Inf, :zero
        )
    end
    if expected_sector !== nothing
        expected_flux = QN(
            ("Nf", expected_sector.nf, -1),
            ("Sz", expected_sector.sz),
        )
        flux(branch) == expected_flux ||
            error("impurity operator branch sector mismatch")
    end
    branch[1] /= amplitude
    return AppliedOperatorBranch(
        branch, expected_sector, log(amplitude), :finite
    )
end

function _bounded_summary(histories...)
    entries = Iterators.flatten(histories)
    max_link_dimension = 1
    max_truncation_error = 0.0
    krylov_all_converged = true
    krylov_max_error_estimate = 0.0
    krylov_num_operations = 0
    krylov_num_iterations = 0
    krylov_local_updates = 0
    steps = 0
    for entry in entries
        steps += 1
        max_link_dimension =
            max(max_link_dimension, entry.max_link_dimension)
        max_truncation_error =
            max(max_truncation_error, entry.max_truncation_error)
        krylov_all_converged &= entry.krylov_all_converged
        krylov_max_error_estimate = max(
            krylov_max_error_estimate,
            entry.krylov_max_error_estimate,
        )
        krylov_num_operations += entry.krylov_num_operations
        krylov_num_iterations += entry.krylov_num_iterations
        krylov_local_updates += entry.krylov_local_updates
    end
    return (;
        steps,
        max_link_dimension,
        truncation = (; max_error = max_truncation_error),
        krylov = (;
            all_converged = krylov_all_converged,
            max_error_estimate = krylov_max_error_estimate,
            num_operations = krylov_num_operations,
            num_iterations = krylov_num_iterations,
            local_updates = krylov_local_updates,
        ),
    )
end

function _green_branch(
    context::FiniteBathContext,
    thermal::PurificationResult,
    tau::Float64,
    spin::Symbol;
    insertion::Symbol,
    time_step::Float64,
    cutoff::Float64,
    maxdim::Int,
    krylov_expansion_dim::Int,
    progress::Bool = false,
)
    beta = thermal.diagnostics.beta
    sites = context.sites
    branch = copy_identity_purification(context)
    hamiltonian = context.hamiltonian
    bound = context.hamiltonian_norm_bound
    before_duration = insertion === :creation ? beta - tau : tau
    after_duration = insertion === :creation ? tau : beta - tau
    expected_sector =
        context.spin_qn_enabled ?
        operator_sector(context.purification, insertion, spin) : nothing

    branch, before = _evolve_normalized_state(
        branch,
        hamiltonian;
        beta = before_duration,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
        hamiltonian_norm_bound = bound,
        progress,
        progress_label = "Green-$(spin)-tau=$(tau)-before",
    )
    applied = _apply_impurity_operator(
        branch, sites[1], spin, insertion, expected_sector
    )
    if applied.status === :zero
        return -0.0, (;
            tau,
            spin,
            insertion,
            branch_status = applied.status,
            operator_sector = applied.expected_sector,
            branch_log_norms = (;
                before_operator = before.log_unnormalized_norm,
                operator = applied.log_norm,
                after_operator = -Inf,
                total = -Inf,
            ),
            overlap_magnitude = 0.0,
            max_link_dimension = before.max_link_dimension,
            maximum_link_dimensions_by_bond =
                before.maximum_link_dimensions_by_bond,
            truncation = (; max_error = maximum(
                (
                    entry.max_truncation_error
                    for entry in before.step_history
                );
                init = 0.0,
            )),
            krylov = _bounded_summary(before.step_history).krylov,
            settings = (;
                time_step,
                cutoff,
                maxdim,
                krylov_expansion_dim,
                hamiltonian_norm_bound = bound,
                before_steps = before.steps,
                after_steps = 0,
                before_effective_time_step = before.effective_time_step,
                after_effective_time_step = time_step,
            ),
        )
    end

    branch = applied.psi
    branch, after = _evolve_normalized_state(
        branch,
        hamiltonian;
        beta = after_duration,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
        hamiltonian_norm_bound = bound,
        progress,
        progress_label = "Green-$(spin)-tau=$(tau)-after",
    )
    branch_log_norm =
        before.log_unnormalized_norm +
        applied.log_norm +
        after.log_unnormalized_norm
    log_overlap = 2 * (
        branch_log_norm - thermal.diagnostics.log_unnormalized_norm
    )
    minimum_log_amplitude = log(nextfloat(0.0))
    if log_overlap < minimum_log_amplitude
        overlap_magnitude = 0.0
        branch_status = :underflow
    else
        overlap_magnitude = exp(log_overlap)
        branch_status = :finite
    end
    summary = _bounded_summary(
        before.step_history, after.step_history
    )
    maximum_link_dimensions_by_bond = max.(
        before.maximum_link_dimensions_by_bond,
        after.maximum_link_dimensions_by_bond,
    )
    diagnostics = (;
        tau,
        spin,
        insertion,
        operator_sector = applied.expected_sector,
        branch_status,
        branch_log_norms = (;
            before_operator = before.log_unnormalized_norm,
            operator = applied.log_norm,
            after_operator = after.log_unnormalized_norm,
            total = branch_log_norm,
        ),
        log_overlap,
        overlap_magnitude,
        max_link_dimension = maximum(
            maximum_link_dimensions_by_bond; init = 1
        ),
        maximum_link_dimensions_by_bond,
        truncation = summary.truncation,
        krylov = summary.krylov,
        settings = (;
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
            hamiltonian_norm_bound = bound,
            before_steps = before.steps,
            after_steps = after.steps,
            before_effective_time_step = before.effective_time_step,
            after_effective_time_step = after.effective_time_step,
        ),
    )
    return -overlap_magnitude, diagnostics
end

function _validated_request(
    beta,
    tau,
    green_insertion,
    time_step,
    cutoff,
    maxdim,
    krylov_expansion_dim,
)
    inverse_temperature = _finite_real(beta, "beta")
    inverse_temperature >= 0 ||
        throw(ArgumentError("beta must be nonnegative"))
    tau_values = _validated_tau(tau, inverse_temperature)
    step = _finite_real(time_step, "time_step")
    step > 0 || throw(ArgumentError("time_step must be positive"))
    truncation = _finite_real(cutoff, "cutoff")
    truncation >= 0 ||
        throw(ArgumentError("cutoff must be nonnegative"))
    maxdim isa Integer && !(maxdim isa Bool) && maxdim > 0 ||
        throw(ArgumentError("maxdim must be a positive integer"))
    expansion = _nonnegative_integer(
        krylov_expansion_dim, "krylov_expansion_dim"
    )
    green_insertion in (:creation, :annihilation) ||
        throw(ArgumentError(
            "green_insertion must be :creation or :annihilation"
        ))
    return (
        inverse_temperature,
        tau_values,
        green_insertion,
        step,
        truncation,
        Int(maxdim),
        expansion,
    )
end

function _endpoint_green_diagnostics(
    thermal::PurificationResult,
    tau::Float64,
    beta::Float64,
    spin::Symbol,
    value::Float64;
    time_step::Float64,
    cutoff::Float64,
    maxdim::Int,
    krylov_expansion_dim::Int,
)
    magnitude = -value
    return (;
        tau,
        spin,
        insertion = :none,
        operator_sector = nothing,
        branch_status = :endpoint_identity,
        branch_log_norms = (;
            before_operator = 0.0,
            operator = 0.0,
            after_operator = 0.0,
            total = 0.0,
        ),
        log_overlap = log(magnitude),
        overlap_magnitude = magnitude,
        max_link_dimension = thermal.diagnostics.max_link_dimension,
        maximum_link_dimensions_by_bond =
            thermal.diagnostics.maximum_link_dimensions_by_bond,
        truncation = (; max_error = 0.0),
        krylov = (;
            all_converged = true,
            max_error_estimate = 0.0,
            num_operations = 0,
            num_iterations = 0,
            local_updates = 0,
        ),
        settings = (;
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
            hamiltonian_norm_bound =
                thermal.diagnostics.hamiltonian_norm_bound,
            before_steps = 0,
            after_steps = 0,
            before_effective_time_step = time_step,
            after_effective_time_step = time_step,
        ),
    )
end

"""
Return one spin-resolved impurity Green function on the caller's tau order.
The branch identity is evaluated entirely with nonpositive imaginary-time
TDVP exponents.
"""
function impurity_green_function(
    parameters::FiniteBathParameters;
    beta,
    tau,
    spin,
    purification::PurificationSpec = non_qn_purification(),
    green_insertion = :creation,
    time_step = 0.05,
    cutoff = 1.0e-12,
    maxdim = 256,
    krylov_expansion_dim = 0,
    progress = false,
)
    spin_label = _spin_label(spin)
    beta, tau, green_insertion, time_step, cutoff, maxdim, krylov_expansion_dim =
        _validated_request(
            beta,
            tau,
            green_insertion,
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
        )
    context = build_finite_bath_context(parameters; purification)
    thermal = _evolve_context(
        context;
        beta,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
        progress,
        progress_label = "thermal-$(spin_label)",
    )
    values = Float64[]
    diagnostics = NamedTuple[]
    for point in tau
        value, point_diagnostics = _green_branch(
            context,
            thermal,
            point,
            spin_label;
            insertion = green_insertion,
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
            progress,
        )
        push!(values, value)
        push!(diagnostics, point_diagnostics)
    end
    return (; tau, spin = spin_label, values, diagnostics, thermal_state = thermal)
end

"""
Measure impurity occupancy, double occupancy, and both spin Green functions.
No number-sector projection is used; `tau` order and duplicates are preserved.
"""
function _finite_bath_observables_uninterrupted(
    parameters::FiniteBathParameters;
    beta,
    tau,
    purification::PurificationSpec = non_qn_purification(),
    green_insertion = :creation,
    time_step = 0.05,
    cutoff = 1.0e-12,
    maxdim = 256,
    krylov_expansion_dim = 0,
    progress = false,
)
    beta, tau, green_insertion, time_step, cutoff, maxdim, krylov_expansion_dim =
        _validated_request(
            beta,
            tau,
            green_insertion,
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
        )
    context = build_finite_bath_context(parameters; purification)
    thermal = _evolve_context(
        context;
        beta,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
        progress,
        progress_label = "thermal",
    )
    occupation = impurity_observables(thermal.psi)
    n_up = real(expect(thermal.psi, "Nup")[1])
    n_dn = real(expect(thermal.psi, "Ndn")[1])
    G_up = Float64[]
    G_dn = Float64[]
    diagnostics_up = NamedTuple[]
    diagnostics_dn = NamedTuple[]
    for point in tau
        if point == 0.0 || point == beta
            for (spin, n_spin, values, diagnostics) in (
                (:up, n_up, G_up, diagnostics_up),
                (:dn, n_dn, G_dn, diagnostics_dn),
            )
                value = point == 0.0 ? -(1 - n_spin) : -n_spin
                push!(values, value)
                push!(
                    diagnostics,
                    _endpoint_green_diagnostics(
                        thermal,
                        point,
                        beta,
                        spin,
                        value;
                        time_step,
                        cutoff,
                        maxdim,
                        krylov_expansion_dim,
                    ),
                )
            end
            continue
        end
        for (spin, values, diagnostics) in (
            (:up, G_up, diagnostics_up),
            (:dn, G_dn, diagnostics_dn),
        )
            value, point_diagnostics = _green_branch(
                context,
                thermal,
                point,
                spin;
                insertion = green_insertion,
                time_step,
                cutoff,
                maxdim,
                krylov_expansion_dim,
                progress,
            )
            push!(values, value)
            push!(diagnostics, point_diagnostics)
        end
    end

    n_orbitals = length(parameters.epsilon) + 1
    log_partition =
        n_orbitals * log(4.0) +
        2 * thermal.diagnostics.log_unnormalized_norm
    maximum_link_dimensions_by_bond = copy(
        thermal.diagnostics.maximum_link_dimensions_by_bond
    )
    for entry in Iterators.flatten((diagnostics_up, diagnostics_dn))
        maximum_link_dimensions_by_bond = max.(
            maximum_link_dimensions_by_bond,
            entry.maximum_link_dimensions_by_bond,
        )
    end
    diagnostics = (;
        bath_representation = context.bath_representation,
        chain_mapping_sha256 = context.chain_mapping_sha256,
        spin_qn_enabled = context.spin_qn_enabled,
        spin_transform = context.spin_transform,
        log_partition,
        mpo_link_dimensions = linkdims(context.hamiltonian),
        thermal_log_norm = thermal.diagnostics.log_unnormalized_norm,
        thermal_max_link_dimension =
            thermal.diagnostics.max_link_dimension,
        maximum_link_dimensions_by_bond,
        green_up = diagnostics_up,
        green_dn = diagnostics_dn,
        settings = (;
            beta,
            green_insertion,
            time_step,
            cutoff,
            maxdim,
            requested_tau = copy(tau),
        ),
        disclaimer = "local TDVP/Krylov/truncation summaries; no global timestep error is claimed",
    )
    provenance = (;
        module_name = "FiniteBathObservables",
        module_version = MODULE_VERSION,
        bath_representation = context.bath_representation,
        chain_mapping_sha256 = context.chain_mapping_sha256,
        purification_mode = context.purification.mode,
        spin_transform = context.spin_transform,
        julia_version = string(VERSION),
        itensors_version = string(Base.pkgversion(ITensors)),
        itensormps_version = string(Base.pkgversion(ITensorMPS)),
        green_function = GREEN_FUNCTION_CONVENTION,
        branch_identity = "$(green_insertion) norm identity on interior tau",
        thermal_space = "full grand-canonical Fock space; no fixed-number projection",
        site_layout = "interleaved physical and ancilla Electron sites",
        impurity_physical_site = 1,
        normalization = "log norms accumulated after every nonpositive-imaginary-time TDVP increment",
    )
    return (;
        n_d = occupation.occupancy,
        double_occupancy = occupation.double_occupancy,
        G_up,
        G_dn,
        tau,
        thermal_state = thermal,
        diagnostics,
        provenance,
    )
end

function _resume_parts(resume)
    resume isa ObservableInterrupted &&
        return (
            resume.psi === nothing ? nothing : copy(resume.psi),
            resume.state,
        )
    if resume isa NamedTuple
        haskey(resume, :psi) && haskey(resume, :resume_state) ||
            throw(ArgumentError("resume must contain psi and resume_state"))
        resume.resume_state isa ObservableResumeState ||
            throw(ArgumentError("resume_state must be an ObservableResumeState"))
        return (
            resume.psi === nothing ? nothing : copy(resume.psi),
            resume.resume_state,
        )
    end
    throw(ArgumentError("resume must be an ObservableInterrupted or loaded checkpoint"))
end

function _validate_resume_sectors(
    context::FiniteBathContext,
    state::ObservableResumeState,
    active::Union{Nothing,MPS},
)
    cursor = state.cursor
    qn_enabled = context.purification.mode === :qn_dual
    base_flux =
        qn_enabled ?
        QN(
            ("Nf", context.purification.base_sector_nf, -1),
            ("Sz", context.purification.base_sector_sz),
        ) : nothing
    expected_sector =
        qn_enabled && cursor.phase === :green ?
        operator_sector(
            context.purification, cursor.insertion, cursor.spin
        ) : nothing

    if state.thermal_psi !== nothing
        siteinds(state.thermal_psi) == context.sites ||
            throw(ArgumentError(
                "resume thermal-state sites do not match current context"
            ))
        if qn_enabled
            flux(state.thermal_psi) == base_flux ||
                throw(ArgumentError(
                    "resume thermal state has the wrong base sector"
                ))
        else
            all(!hasqns(site) for site in siteinds(state.thermal_psi)) ||
                throw(ArgumentError(
                    "non-QN resume thermal state contains QNs"
                ))
        end
    end

    if active !== nothing
        siteinds(active) == context.sites ||
            throw(ArgumentError(
                "resume active-state sites do not match current context"
            ))
    end

    if cursor.phase === :green &&
       cursor.segment in (:after, :terminal)
        state.data.expected_sector == expected_sector ||
            throw(ArgumentError(
                "resume operator-sector metadata mismatch"
            ))
        if cursor.segment === :terminal
            active === nothing ||
                throw(ArgumentError(
                    "zero terminal resume cannot carry active MPS"
                ))
            state.data.branch_status === :zero ||
                throw(ArgumentError(
                    "terminal resume must be a zero branch"
                ))
        else
            active !== nothing ||
                throw(ArgumentError(
                    "shifted resume requires active MPS"
                ))
            state.data.branch_status === :finite ||
                throw(ArgumentError(
                    "shifted resume must be a finite branch"
                ))
            if qn_enabled
                expected_flux = QN(
                    ("Nf", expected_sector.nf, -1),
                    ("Sz", expected_sector.sz),
                )
                flux(active) == expected_flux ||
                    throw(ArgumentError(
                        "resume active state has the wrong operator sector"
                    ))
            else
                all(!hasqns(site) for site in siteinds(active)) ||
                    throw(ArgumentError(
                        "non-QN resume active state contains QNs"
                    ))
            end
        end
    else
        state.data.expected_sector === nothing ||
            throw(ArgumentError(
                "base-state resume cannot claim an operator sector"
            ))
        active !== nothing ||
            throw(ArgumentError("base-state resume requires active MPS")
        )
        if qn_enabled
            flux(active) == base_flux ||
                throw(ArgumentError(
                    "resume active state has the wrong base sector"
                ))
        else
            all(!hasqns(site) for site in siteinds(active)) ||
                throw(ArgumentError(
                    "non-QN resume active state contains QNs"
                ))
        end
    end
    return nothing
end

function _publish_observable_checkpoint(
    checkpoint_manager,
    stop_requested,
    context::FiniteBathContext,
    psi::Union{Nothing,MPS},
    state::ObservableResumeState,
)
    _validate_resume_sectors(context, state, psi)
    if checkpoint_manager !== nothing
        if applicable(checkpoint_manager, psi, state)
            checkpoint_manager(psi, state)
        elseif applicable(checkpoint_manager, state)
            checkpoint_manager(state)
        else
            throw(ArgumentError("checkpoint_manager must accept (psi, state) or state"))
        end
    end
    stop_requested isa Function ||
        throw(ArgumentError("stop_requested must be callable"))
    stop_requested() &&
        throw(ObservableInterrupted(psi === nothing ? nothing : copy(psi), state))
    return nothing
end

function _thermal_setup_maxima(
    psi,
    hamiltonian;
    krylov_expansion_dim,
    cutoff,
    maxdim,
)
    initial = maximum(linkdims(psi); init = 1)
    iszero(krylov_expansion_dim) && return initial, initial
    expanded = expand(
        deepcopy(psi),
        hamiltonian;
        alg = "global_krylov",
        krylovdim = krylov_expansion_dim,
        cutoff = max(cutoff, eps(Float64)),
        apply_kwargs = (; maxdim),
    )
    normalize!(expanded)
    return initial, maximum(linkdims(expanded); init = 1)
end

function _empty_observable_data(tau, settings, thermal_setup_maxima)
    count = length(tau)
    return (;
        tau = copy(tau),
        settings,
        thermal_initial_max_link_dimension = thermal_setup_maxima[1],
        thermal_expanded_max_link_dimension = thermal_setup_maxima[2],
        thermal_diagnostics = nothing,
        n_d = nothing,
        double_occupancy = nothing,
        n_up = nothing,
        n_dn = nothing,
        G_up = Union{Nothing,Float64}[nothing for _ in 1:count],
        G_dn = Union{Nothing,Float64}[nothing for _ in 1:count],
        diagnostics_up = Any[nothing for _ in 1:count],
        diagnostics_dn = Any[nothing for _ in 1:count],
        before = nothing,
        operator_log_norm = nothing,
        expected_sector = nothing,
        branch_status = nothing,
    )
end

function _observable_state(cursor, evolution_state, thermal_psi, data)
    return ObservableResumeState(
        cursor,
        evolution_state,
        thermal_psi === nothing ? nothing : copy(thermal_psi),
        data,
    )
end

function _next_green_cursor(index, spin, insertion, count)
    if spin === :up
        return ObservableCursor(
            :green, index, :dn, insertion, :before
        )
    elseif index < count
        return ObservableCursor(
            :green, index + 1, :up, insertion, :before
        )
    end
    return ObservableCursor(:complete, 0, :none, :none, :none)
end

function _validate_observable_resume(state::ObservableResumeState)
    cursor = state.cursor
    data = state.data
    length(data.G_up) == length(data.tau) &&
        length(data.G_dn) == length(data.tau) &&
        length(data.diagnostics_up) == length(data.tau) &&
        length(data.diagnostics_dn) == length(data.tau) ||
        throw(ArgumentError("resume partial-result lengths are inconsistent"))
    completed = Bool[]
    for index in eachindex(data.tau)
        (data.G_up[index] === nothing) ==
            (data.diagnostics_up[index] === nothing) ||
            throw(ArgumentError("spin-up result and diagnostics disagree"))
        (data.G_dn[index] === nothing) ==
            (data.diagnostics_dn[index] === nothing) ||
            throw(ArgumentError("spin-down result and diagnostics disagree"))
        push!(
            completed,
            data.G_up[index] !== nothing &&
            data.diagnostics_up[index] !== nothing,
            data.G_dn[index] !== nothing &&
            data.diagnostics_dn[index] !== nothing,
        )
    end
    if cursor.phase === :thermal
        any(completed) &&
            throw(ArgumentError("thermal cursor contains Green-function results"))
        data.thermal_diagnostics === nothing ||
            throw(ArgumentError("thermal cursor contains completed thermal diagnostics"))
        data.thermal_initial_max_link_dimension > 0 &&
            data.thermal_expanded_max_link_dimension > 0 ||
            throw(ArgumentError("thermal setup diagnostics are invalid"))
        state.evolution_state !== nothing &&
            state.evolution_state.completed_steps > 0 ||
            throw(ArgumentError("thermal cursor requires active evolution state"))
    elseif cursor.phase === :green
        cursor.tau_index <= length(data.tau) ||
            throw(ArgumentError("observable cursor tau_index is out of bounds"))
        position =
            2 * (cursor.tau_index - 1) + (cursor.spin === :up ? 1 : 2)
        all(completed[1:(position - 1)]) &&
            !any(completed[position:end]) ||
            throw(ArgumentError("observable cursor disagrees with partial results"))
        endpoint =
            data.tau[cursor.tau_index] == 0.0 ||
            data.tau[cursor.tau_index] == data.thermal_diagnostics.beta
        if endpoint
            cursor.segment === :before ||
                throw(ArgumentError("endpoint cursor must be before"))
            state.evolution_state === nothing ||
                throw(ArgumentError("endpoint cursor cannot carry evolution state"))
            data.before === nothing && data.operator_log_norm === nothing ||
                throw(ArgumentError("endpoint cursor contains operator state"))
        elseif cursor.segment === :before
            data.before === nothing && data.operator_log_norm === nothing ||
                throw(ArgumentError("before cursor contains post-operator state"))
            state.evolution_state === nothing ||
                state.evolution_state.completed_steps > 0 ||
                throw(ArgumentError("before cursor evolution state has no completed step"))
        elseif cursor.segment === :after
            data.before !== nothing && data.operator_log_norm !== nothing ||
                throw(ArgumentError("after cursor lacks operator state"))
            state.evolution_state === nothing ||
                state.evolution_state.completed_steps > 0 ||
                throw(ArgumentError("after cursor evolution state has no completed step"))
        else
            data.branch_status === :zero &&
                data.expected_sector !== nothing ||
                throw(ArgumentError("terminal cursor lacks zero-branch state"))
            state.evolution_state === nothing ||
                throw(ArgumentError("terminal cursor cannot carry evolution state"))
        end
    else
        all(completed) ||
            throw(ArgumentError("complete cursor has incomplete results"))
        state.evolution_state === nothing ||
            throw(ArgumentError("complete cursor cannot carry evolution state"))
        data.before === nothing && data.operator_log_norm === nothing ||
            throw(ArgumentError("complete cursor contains branch state"))
    end
    return nothing
end

function _branch_diagnostics(
    thermal,
    tau,
    spin,
    insertion,
    before,
    operator_log_norm,
    expected_sector,
    after;
    time_step,
    cutoff,
    maxdim,
    krylov_expansion_dim,
    bound,
)
    branch_log_norm =
        before.log_unnormalized_norm +
        operator_log_norm +
        after.log_unnormalized_norm
    log_overlap =
        2 * (branch_log_norm - thermal.diagnostics.log_unnormalized_norm)
    minimum_log_amplitude = log(nextfloat(0.0))
    overlap_magnitude =
        log_overlap < minimum_log_amplitude ? 0.0 : exp(log_overlap)
    branch_status =
        log_overlap < minimum_log_amplitude ? :underflow : :finite
    summary = _bounded_summary(before.step_history, after.step_history)
    dimensions = max.(
        before.maximum_link_dimensions_by_bond,
        after.maximum_link_dimensions_by_bond,
    )
    diagnostics = (;
        tau,
        spin,
        insertion,
        operator_sector = expected_sector,
        branch_status,
        branch_log_norms = (;
            before_operator = before.log_unnormalized_norm,
            operator = operator_log_norm,
            after_operator = after.log_unnormalized_norm,
            total = branch_log_norm,
        ),
        log_overlap,
        overlap_magnitude,
        max_link_dimension = maximum(dimensions; init = 1),
        maximum_link_dimensions_by_bond = dimensions,
        truncation = summary.truncation,
        krylov = summary.krylov,
        settings = (;
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
            hamiltonian_norm_bound = bound,
            before_steps = before.steps,
            after_steps = after.steps,
            before_effective_time_step = before.effective_time_step,
            after_effective_time_step = after.effective_time_step,
        ),
    )
    return -overlap_magnitude, diagnostics
end

function _finish_observable_result(context, thermal, data, settings)
    G_up = Float64[data.G_up...]
    G_dn = Float64[data.G_dn...]
    diagnostics_up = NamedTuple[data.diagnostics_up...]
    diagnostics_dn = NamedTuple[data.diagnostics_dn...]
    n_orbitals = length(context.parameters.epsilon) + 1
    log_partition =
        n_orbitals * log(4.0) +
        2 * thermal.diagnostics.log_unnormalized_norm
    dimensions = copy(thermal.diagnostics.maximum_link_dimensions_by_bond)
    for entry in Iterators.flatten((diagnostics_up, diagnostics_dn))
        dimensions = max.(dimensions, entry.maximum_link_dimensions_by_bond)
    end
    diagnostics = (;
        bath_representation = context.bath_representation,
        chain_mapping_sha256 = context.chain_mapping_sha256,
        spin_qn_enabled = context.spin_qn_enabled,
        spin_transform = context.spin_transform,
        log_partition,
        mpo_link_dimensions = linkdims(context.hamiltonian),
        thermal_log_norm = thermal.diagnostics.log_unnormalized_norm,
        thermal_max_link_dimension = thermal.diagnostics.max_link_dimension,
        maximum_link_dimensions_by_bond = dimensions,
        green_up = diagnostics_up,
        green_dn = diagnostics_dn,
        settings = (;
            beta = settings.beta,
            green_insertion = settings.green_insertion,
            time_step = settings.time_step,
            cutoff = settings.cutoff,
            maxdim = settings.maxdim,
            requested_tau = copy(data.tau),
        ),
        disclaimer = "local TDVP/Krylov/truncation summaries; no global timestep error is claimed",
    )
    provenance = (;
        module_name = "FiniteBathObservables",
        module_version = MODULE_VERSION,
        bath_representation = context.bath_representation,
        chain_mapping_sha256 = context.chain_mapping_sha256,
        purification_mode = context.purification.mode,
        spin_transform = context.spin_transform,
        julia_version = string(VERSION),
        itensors_version = string(Base.pkgversion(ITensors)),
        itensormps_version = string(Base.pkgversion(ITensorMPS)),
        green_function = GREEN_FUNCTION_CONVENTION,
        branch_identity = "$(settings.green_insertion) norm identity on interior tau",
        thermal_space = "full grand-canonical Fock space; no fixed-number projection",
        site_layout = "interleaved physical and ancilla Electron sites",
        impurity_physical_site = 1,
        normalization = "log norms accumulated after every nonpositive-imaginary-time TDVP increment",
    )
    return (;
        n_d = data.n_d,
        double_occupancy = data.double_occupancy,
        G_up,
        G_dn,
        tau = data.tau,
        thermal_state = thermal,
        diagnostics,
        provenance,
    )
end

function _finite_bath_observables_resumable(
    parameters::FiniteBathParameters;
    beta,
    tau,
    purification,
    green_insertion,
    time_step,
    cutoff,
    maxdim,
    krylov_expansion_dim,
    progress,
    checkpoint_manager,
    resume,
    stop_requested,
)
    beta, tau, green_insertion, time_step, cutoff, maxdim, krylov_expansion_dim =
        _validated_request(
            beta,
            tau,
            green_insertion,
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
        )
    context = build_finite_bath_context(parameters; purification)
    settings = (;
        beta,
        green_insertion,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
    )
    if resume === nothing
        active = copy_identity_purification(context)
        cursor = ObservableCursor(:thermal, 0, :none, :none, :none)
        evolution_state = nothing
        thermal_psi = nothing
        thermal_setup_maxima = _thermal_setup_maxima(
            active,
            context.hamiltonian;
            krylov_expansion_dim,
            cutoff,
            maxdim,
        )
        data = _empty_observable_data(tau, settings, thermal_setup_maxima)
    else
        active, state = _resume_parts(resume)
        state.data.tau == tau ||
            throw(ArgumentError("resume tau points do not match the request"))
        state.data.settings == settings ||
            throw(ArgumentError("resume solver settings do not match the request"))
        _validate_observable_resume(state)
        cursor = state.cursor
        active === nothing && cursor.segment !== :terminal &&
            throw(ArgumentError(
                "only a zero terminal resume may omit active MPS"
            ))
        cursor.phase === :green &&
            cursor.insertion !== green_insertion &&
            throw(ArgumentError(
                "resume Green insertion does not match the request"
            ))
        evolution_state = state.evolution_state
        thermal_psi = state.thermal_psi
        data = state.data
        resume_sites =
            thermal_psi === nothing ? siteinds(active) : siteinds(thermal_psi)
        active !== nothing &&
            thermal_psi !== nothing &&
            siteinds(active) != resume_sites &&
            throw(ArgumentError("active and thermal checkpoint sites do not match"))
        context = _context_on_sites(
            parameters, resume_sites; purification
        )
        _validate_resume_sectors(context, state, active)
    end

    if cursor.phase === :thermal
        callback = function (psi, evolution)
            state = _observable_state(
                cursor, evolution, nothing, data
            )
            _publish_observable_checkpoint(
                checkpoint_manager, stop_requested, context, psi, state
            )
        end
        active, thermal_diagnostics = _evolve_normalized_state(
            active,
            context.hamiltonian;
            beta,
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
            hamiltonian_norm_bound = context.hamiltonian_norm_bound,
            progress,
            progress_label = "thermal",
            resume_state = evolution_state,
            step_callback = callback,
        )
        thermal_diagnostics = merge(
            thermal_diagnostics,
            (;
                initial_max_link_dimension =
                    data.thermal_initial_max_link_dimension,
                expanded_max_link_dimension =
                    data.thermal_expanded_max_link_dimension,
            ),
        )
        thermal_psi = copy(active)
        thermal = PurificationResult(
            context.sites,
            thermal_psi,
            context.hamiltonian,
            (; parameters = context.parameters, thermal_diagnostics...),
        )
        occupation = impurity_observables(thermal.psi)
        data = merge(
            data,
            (;
                thermal_diagnostics,
                n_d = occupation.occupancy,
                double_occupancy = occupation.double_occupancy,
                n_up = real(expect(thermal.psi, "Nup")[1]),
                n_dn = real(expect(thermal.psi, "Ndn")[1]),
            ),
        )
        cursor = ObservableCursor(
            :green, 1, :up, green_insertion, :before
        )
        evolution_state = nothing
        active = copy_identity_purification(context)
        state = _observable_state(cursor, nothing, thermal_psi, data)
        _publish_observable_checkpoint(
            checkpoint_manager, stop_requested, context, active, state
        )
    end

    thermal = PurificationResult(
        context.sites,
        thermal_psi,
        context.hamiltonian,
        (; parameters = context.parameters, data.thermal_diagnostics...),
    )
    while cursor.phase === :green
        index = cursor.tau_index
        spin = cursor.spin
        point = tau[index]
        values_key = spin === :up ? :G_up : :G_dn
        diagnostics_key =
            spin === :up ? :diagnostics_up : :diagnostics_dn
        if point == 0.0 || point == beta
            n_spin = spin === :up ? data.n_up : data.n_dn
            value = point == 0.0 ? -(1 - n_spin) : -n_spin
            diagnostics = _endpoint_green_diagnostics(
                thermal,
                point,
                beta,
                spin,
                value;
                time_step,
                cutoff,
                maxdim,
                krylov_expansion_dim,
            )
        else
            insertion = cursor.insertion
            before_duration = beta - point
            after_duration = point
            if insertion === :annihilation
                before_duration, after_duration =
                    point, beta - point
            end
            if cursor.segment === :before
                callback = function (psi, evolution)
                    state = _observable_state(
                        cursor, evolution, thermal_psi, data
                    )
                    _publish_observable_checkpoint(
                        checkpoint_manager,
                        stop_requested,
                        context,
                        psi,
                        state,
                    )
                end
                active, before = _evolve_normalized_state(
                    active,
                    context.hamiltonian;
                    beta = before_duration,
                    time_step,
                    cutoff,
                    maxdim,
                    krylov_expansion_dim,
                    hamiltonian_norm_bound =
                        context.hamiltonian_norm_bound,
                    progress,
                    progress_label = "Green-$(spin)-tau=$(point)-before",
                    resume_state = evolution_state,
                    step_callback = callback,
                )
                expected_sector =
                    context.spin_qn_enabled ?
                    operator_sector(
                        context.purification, insertion, spin
                    ) : nothing
                applied = _apply_impurity_operator(
                    active,
                    context.sites[1],
                    spin,
                    insertion,
                    expected_sector,
                )
                data = merge(
                    data,
                    (;
                        before,
                        operator_log_norm = applied.log_norm,
                        expected_sector = applied.expected_sector,
                        branch_status = applied.status,
                    ),
                )
                if applied.status === :zero
                    cursor = ObservableCursor(
                        :green,
                        index,
                        spin,
                        insertion,
                        :terminal,
                    )
                    state = _observable_state(
                        cursor, nothing, thermal_psi, data
                    )
                    _publish_observable_checkpoint(
                        checkpoint_manager,
                        stop_requested,
                        context,
                        nothing,
                        state,
                    )
                else
                    active = applied.psi
                    cursor = ObservableCursor(
                        :green, index, spin, insertion, :after
                    )
                end
                evolution_state = nothing
                if applied.status === :finite
                    state = _observable_state(
                        cursor, nothing, thermal_psi, data
                    )
                    _publish_observable_checkpoint(
                        checkpoint_manager,
                        stop_requested,
                        context,
                        active,
                        state,
                    )
                end
            end
            if cursor.segment === :terminal
                value = -0.0
                diagnostics = (;
                    tau = point,
                    spin,
                    insertion,
                    operator_sector = data.expected_sector,
                    branch_status = :zero,
                    branch_log_norms = (;
                        before_operator =
                            data.before.log_unnormalized_norm,
                        operator = -Inf,
                        after_operator = -Inf,
                        total = -Inf,
                    ),
                    overlap_magnitude = 0.0,
                    max_link_dimension = data.before.max_link_dimension,
                    maximum_link_dimensions_by_bond =
                        data.before.maximum_link_dimensions_by_bond,
                    truncation = (; max_error = 0.0),
                    krylov =
                        _bounded_summary(data.before.step_history).krylov,
                    settings = (;
                        time_step,
                        cutoff,
                        maxdim,
                        krylov_expansion_dim,
                        hamiltonian_norm_bound =
                            context.hamiltonian_norm_bound,
                        before_steps = data.before.steps,
                        after_steps = 0,
                        before_effective_time_step =
                            data.before.effective_time_step,
                        after_effective_time_step = time_step,
                    ),
                )
            else
                callback = function (psi, evolution)
                    state = _observable_state(
                        cursor, evolution, thermal_psi, data
                    )
                    _publish_observable_checkpoint(
                        checkpoint_manager,
                        stop_requested,
                        context,
                        psi,
                        state,
                    )
                end
                active, after = _evolve_normalized_state(
                    active,
                    context.hamiltonian;
                    beta = after_duration,
                    time_step,
                    cutoff,
                    maxdim,
                    krylov_expansion_dim,
                    hamiltonian_norm_bound =
                        context.hamiltonian_norm_bound,
                    progress,
                    progress_label =
                        "Green-$(spin)-tau=$(point)-after",
                    resume_state = evolution_state,
                    step_callback = callback,
                )
                value, diagnostics = _branch_diagnostics(
                    thermal,
                    point,
                    spin,
                    insertion,
                    data.before,
                    data.operator_log_norm,
                    data.expected_sector,
                    after;
                    time_step,
                    cutoff,
                    maxdim,
                    krylov_expansion_dim,
                    bound = context.hamiltonian_norm_bound,
                )
            end
        end
        values = copy(getproperty(data, values_key))
        point_diagnostics = copy(getproperty(data, diagnostics_key))
        values[index] = value
        point_diagnostics[index] = diagnostics
        data = merge(
            data,
            NamedTuple{(values_key, diagnostics_key)}(
                (values, point_diagnostics)
            ),
            (;
                before = nothing,
                operator_log_norm = nothing,
                expected_sector = nothing,
                branch_status = nothing,
            ),
        )
        cursor = _next_green_cursor(
            index, spin, green_insertion, length(tau)
        )
        evolution_state = nothing
        active =
            cursor.phase === :green ?
            copy_identity_purification(context) : copy(thermal_psi)
        state = _observable_state(cursor, nothing, thermal_psi, data)
        _publish_observable_checkpoint(
            checkpoint_manager, stop_requested, context, active, state
        )
    end
    return _finish_observable_result(context, thermal, data, settings)
end

function finite_bath_observables(
    parameters::FiniteBathParameters;
    beta,
    tau,
    purification::PurificationSpec = non_qn_purification(),
    green_insertion = :creation,
    time_step = 0.05,
    cutoff = 1.0e-12,
    maxdim = 256,
    krylov_expansion_dim = 0,
    progress = false,
    checkpoint_manager = nothing,
    resume = nothing,
    stop_requested = _NEVER_STOP,
)
    if checkpoint_manager === nothing && resume === nothing &&
       stop_requested === _NEVER_STOP
        return _finite_bath_observables_uninterrupted(
            parameters;
            beta,
            tau,
            purification,
            green_insertion,
            time_step,
            cutoff,
            maxdim,
            krylov_expansion_dim,
            progress,
        )
    end
    return _finite_bath_observables_resumable(
        parameters;
        beta,
        tau,
        purification,
        green_insertion,
        time_step,
        cutoff,
        maxdim,
        krylov_expansion_dim,
        progress,
        checkpoint_manager,
        resume,
        stop_requested,
    )
end

end
