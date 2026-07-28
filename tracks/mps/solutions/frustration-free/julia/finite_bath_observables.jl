module FiniteBathObservables

using ITensors
using ITensorMPS

using ..FiniteBathPurification:
    FiniteBathParameters,
    PurificationResult,
    _evolve_normalized_state,
    _evolution_settings,
    _finite_real,
    _hamiltonian_norm_bound,
    _nonnegative_integer,
    evolve_purification,
    identity_purification,
    impurity_observables,
    physical_hamiltonian_mpo

export FiniteBathContext,
    build_finite_bath_context,
    copy_identity_purification,
    finite_bath_observables,
    impurity_green_function

const GREEN_FUNCTION_CONVENTION =
    "G_sigma(tau) = -Tr[exp(-(beta-tau)K) d_sigma exp(-tau K) d_sigma^dag] / Z"

struct FiniteBathContext{P,S,I,H}
    parameters::P
    sites::S
    identity::I
    hamiltonian::H
    hamiltonian_norm_bound::Float64
    spin_qn_enabled::Bool
    reuse_policy::String
end

function build_finite_bath_context(parameters::FiniteBathParameters)
    sites, identity = identity_purification(parameters)
    hamiltonian = physical_hamiltonian_mpo(sites, parameters)
    return FiniteBathContext(
        parameters,
        sites,
        identity,
        hamiltonian,
        _hamiltonian_norm_bound(parameters),
        false,
        "identity template and immutable MPO may be deep-copied across branches",
    )
end

copy_identity_purification(context::FiniteBathContext) =
    deepcopy(context.identity)

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
    psi::MPS, physical_site::Index, spin::Symbol, insertion::Symbol
)
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
        return branch, -Inf, :zero
    end
    branch[1] /= amplitude
    return branch, log(amplitude), :finite
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
    # At tau=beta, use the cyclically equivalent annihilation branch
    # ||d exp(-beta*K/2)|I>||^2. It avoids starting odd-sector TDVP from
    # the exactly rank-deficient beta=0 identity MPS.
    insertion = tau == beta ? :annihilation : :creation
    before_duration = insertion === :creation ? beta - tau : tau
    after_duration = insertion === :creation ? tau : beta - tau

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
    branch, operator_log_norm, branch_status =
        _apply_impurity_operator(branch, sites[1], spin, insertion)
    if branch_status === :zero
        return -0.0, (;
            tau,
            spin,
            insertion,
            branch_status,
            branch_log_norms = (;
                before_operator = before.log_unnormalized_norm,
                operator = operator_log_norm,
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
        operator_log_norm +
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
        branch_status,
        branch_log_norms = (;
            before_operator = before.log_unnormalized_norm,
            operator = operator_log_norm,
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
    beta, tau, time_step, cutoff, maxdim, krylov_expansion_dim
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
    return inverse_temperature, tau_values, step, truncation, Int(maxdim), expansion
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
    insertion = tau == beta ? :annihilation : :creation
    magnitude = -value
    return (;
        tau,
        spin,
        insertion,
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
    time_step = 0.05,
    cutoff = 1.0e-12,
    maxdim = 256,
    krylov_expansion_dim = 0,
    progress = false,
)
    spin_label = _spin_label(spin)
    beta, tau, time_step, cutoff, maxdim, krylov_expansion_dim =
        _validated_request(
            beta, tau, time_step, cutoff, maxdim, krylov_expansion_dim
        )
    context = build_finite_bath_context(parameters)
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
function finite_bath_observables(
    parameters::FiniteBathParameters;
    beta,
    tau,
    time_step = 0.05,
    cutoff = 1.0e-12,
    maxdim = 256,
    krylov_expansion_dim = 0,
    progress = false,
)
    beta, tau, time_step, cutoff, maxdim, krylov_expansion_dim =
        _validated_request(
            beta, tau, time_step, cutoff, maxdim, krylov_expansion_dim
        )
    context = build_finite_bath_context(parameters)
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
            time_step,
            cutoff,
            maxdim,
            requested_tau = copy(tau),
        ),
        disclaimer = "local TDVP/Krylov/truncation summaries; no global timestep error is claimed",
    )
    provenance = (;
        module_name = "FiniteBathObservables",
        module_version = "1.0.0",
        julia_version = string(VERSION),
        itensors_version = string(Base.pkgversion(ITensors)),
        itensormps_version = string(Base.pkgversion(ITensorMPS)),
        green_function = GREEN_FUNCTION_CONVENTION,
        branch_identity = "creation norm identity, with its cyclic annihilation form at tau=beta",
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

end
