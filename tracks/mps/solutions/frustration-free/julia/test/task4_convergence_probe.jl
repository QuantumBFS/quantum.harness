#!/usr/bin/env julia

module Task4ConvergenceProbe

using JSON3
using LinearAlgebra

const PRODUCTION_ROOT = normpath(joinpath(@__DIR__, ".."))
include(joinpath(PRODUCTION_ROOT, "finite_bath_mps_runner.jl"))
include(joinpath(@__DIR__, "validated_chain_fixture.jl"))

const N_BATH = 3
const INTERACTION = 0.0
const BETA = 0.04
const EPSILON_D = -0.31
const CHEMICAL_POTENTIAL = 0.07
const TAU = [0.0, BETA / 4, BETA / 2, 3 * BETA / 4, BETA]
const SCIENTIFIC_THRESHOLD = 1.0e-6
const PROBE_SCHEMA_VERSION = 1

function _choice(env, key, default, choices)
    value = get(env, key, default)
    value in choices ||
        throw(ArgumentError("$key must be one of $(join(choices, ", "))"))
    return Symbol(value)
end

function _positive_float(env, key, default)
    value = tryparse(Float64, get(env, key, default))
    value !== nothing && isfinite(value) && value > 0 ||
        throw(ArgumentError("$key must be a finite positive number"))
    return value
end

function _nonnegative_float(env, key, default)
    value = tryparse(Float64, get(env, key, default))
    value !== nothing && isfinite(value) && value >= 0 ||
        throw(ArgumentError("$key must be a finite nonnegative number"))
    return value
end

function _positive_integer(env, key, default)
    value = tryparse(Int, get(env, key, default))
    value !== nothing && value > 0 ||
        throw(ArgumentError("$key must be a positive integer"))
    return value
end

function _nonnegative_integer(env, key, default)
    value = tryparse(Int, get(env, key, default))
    value !== nothing && value >= 0 ||
        throw(ArgumentError("$key must be a nonnegative integer"))
    return value
end

function parse_probe_config(env = ENV)
    representation = _choice(env, "REP", "chain", ("direct", "chain"))
    mode = _choice(env, "MODE", "qn", ("non_qn", "qn"))
    insertion =
        _choice(env, "INSERTION", "creation", ("creation", "annihilation"))
    representation === :direct && mode === :qn &&
        throw(ArgumentError("MODE=qn requires REP=chain"))
    return (;
        representation,
        mode,
        insertion,
        dt = _positive_float(env, "DT", "0.01"),
        cutoff = _nonnegative_float(env, "CUTOFF", "0"),
        maxdim = _positive_integer(env, "MAXDIM", "256"),
        kdim = _nonnegative_integer(env, "KDIM", "64"),
    )
end

function canonical_json(value)
    if value === nothing
        return "null"
    elseif value isa AbstractFloat
        isfinite(value) ||
            throw(ArgumentError("canonical JSON cannot contain nonfinite floats"))
        return String(JSON3.write(Float64(value)))
    elseif value isa Bool || value isa Integer || value isa AbstractString
        return String(JSON3.write(value))
    elseif value isa Symbol
        return String(JSON3.write(String(value)))
    elseif value isa NamedTuple
        return canonical_json(Dict(String(key) => item for (key, item) in pairs(value)))
    elseif value isa AbstractVector || value isa Tuple
        return "[" * join(canonical_json.(collect(value)), ",") * "]"
    elseif value isa AbstractDict
        keys_sorted = sort!(String.(collect(keys(value))))
        entries = [
            canonical_json(key) * ":" * canonical_json(value[key])
            for key in keys_sorted
        ]
        return "{" * join(entries, ",") * "}"
    end
    throw(ArgumentError("unsupported canonical JSON value $(typeof(value))"))
end

function independent_noninteracting_oracle(epsilon, coupling)
    one_particle =
        diagm([EPSILON_D - CHEMICAL_POTENTIAL; epsilon .- CHEMICAL_POTENTIAL])
    one_particle[1, 2:end] = coupling
    one_particle[2:end, 1] = coupling
    eig = eigen(Hermitian(one_particle))
    occupations = 1.0 ./ (1.0 .+ exp.(BETA .* eig.values))
    density = eig.vectors * Diagonal(occupations) * eig.vectors'
    n_spin = real(density[1, 1])
    green = [
        -real(
            (
                eig.vectors *
                Diagonal(exp.(-point .* eig.values) .* (1 .- occupations)) *
                eig.vectors'
            )[1, 1],
        ) for point in TAU
    ]
    return (;
        logZ = 2 * sum(
            max(0.0, -BETA * value) +
            log1p(exp(-abs(BETA * value))) for value in eig.values
        ),
        n_up = n_spin,
        n_dn = n_spin,
        n_d = 2 * n_spin,
        double_occupancy = n_spin^2,
        G_up = green,
        G_dn = copy(green),
        one_particle_eigenvalues = collect(eig.values),
    )
end

step_record(entry) = (;
    beta_endpoint = entry.beta_endpoint,
    beta_increment = entry.beta_increment,
    log_norm_increment = entry.log_norm_increment,
    cumulative_log_norm = entry.cumulative_log_norm,
    max_link_dimension = entry.max_link_dimension,
    max_truncation_error = entry.max_truncation_error,
    krylov_all_converged = entry.krylov_all_converged,
    krylov_max_error_estimate = entry.krylov_max_error_estimate,
    krylov_num_operations = entry.krylov_num_operations,
    krylov_num_iterations = entry.krylov_num_iterations,
    krylov_local_updates = entry.krylov_local_updates,
    observer_visible_krylov_updates = entry.observer_visible_krylov_updates,
)

function evolution_record(evolution)
    return (;
        completed_steps = evolution.completed_steps,
        beta_endpoint = evolution.beta_endpoint,
        log_unnormalized_norm = evolution.log_unnormalized_norm,
        maximum_link_dimensions_by_bond =
            copy(evolution.maximum_link_dimensions_by_bond),
        max_link_dimension =
            maximum(evolution.maximum_link_dimensions_by_bond; init = 1),
        step_history = step_record.(evolution.step_history),
    )
end

function _branch_key(cursor)
    return (
        cursor.tau_index,
        cursor.spin === :up ? 1 : 2,
        cursor.segment === :before ? 1 : 2,
    )
end

function _error_payload(solver, oracle)
    fields = (;
        logZ = solver.logZ - oracle.logZ,
        n_up = solver.n_up - oracle.n_up,
        n_dn = solver.n_dn - oracle.n_dn,
        n_d = solver.n_d - oracle.n_d,
        double_occupancy =
            solver.double_occupancy - oracle.double_occupancy,
        G_up = solver.G_up .- oracle.G_up,
        G_dn = solver.G_dn .- oracle.G_dn,
    )
    absolute = (;
        logZ = abs(fields.logZ),
        n_up = abs(fields.n_up),
        n_dn = abs(fields.n_dn),
        n_d = abs(fields.n_d),
        double_occupancy = abs(fields.double_occupancy),
        G_up = abs.(fields.G_up),
        G_dn = abs.(fields.G_dn),
    )
    maximum_absolute = maximum(
        [
            absolute.logZ,
            absolute.n_up,
            absolute.n_dn,
            absolute.n_d,
            absolute.double_occupancy,
            absolute.G_up...,
            absolute.G_dn...,
        ],
    )
    return (;
        signed = fields,
        absolute,
        maximum_absolute,
        scientific_threshold = SCIENTIFIC_THRESHOLD,
        within_scientific_threshold =
            maximum_absolute <= SCIENTIFIC_THRESHOLD,
    )
end

function run_probe(config = parse_probe_config())
    artifacts = validated_chain_fixture_artifacts(N_BATH)
    bath_payload = artifacts.bath_artifact["payload"]
    epsilon = Float64.(bath_payload["epsilon"])
    coupling = Float64.(bath_payload["V"])
    oracle = independent_noninteracting_oracle(epsilon, coupling)
    validated = validate_chain_mapping_artifact(
        artifacts.mapping_artifact,
        artifacts.mapping_json,
        artifacts.bath_artifact,
    )

    purification_module = getfield(@__MODULE__, :FiniteBathPurification)
    observables_module = getfield(@__MODULE__, :FiniteBathObservables)
    if config.representation === :direct
        parameters = purification_module.FiniteBathParameters(
            epsilon,
            coupling;
            U = INTERACTION,
            epsilon_d = EPSILON_D,
            mu = CHEMICAL_POTENTIAL,
        )
    else
        parameters = purification_module.FiniteBathParameters(
            validated;
            U = INTERACTION,
            epsilon_d = EPSILON_D,
            mu = CHEMICAL_POTENTIAL,
        )
    end
    purification =
        config.mode === :qn ?
        purification_module.qn_dual_purification(parameters, validated) :
        purification_module.non_qn_purification()

    thermal_history = Ref{Any}(nothing)
    branch_histories = Dict{Tuple{Int,Int,Int},Any}()
    checkpoint_manager = (_, state) -> begin
        evolution = state.evolution_state
        evolution === nothing && return
        record = evolution_record(evolution)
        if state.cursor.phase === :thermal
            thermal_history[] = record
        elseif state.cursor.phase === :green
            branch_histories[_branch_key(state.cursor)] = (;
                tau_index = state.cursor.tau_index,
                tau = TAU[state.cursor.tau_index],
                spin = state.cursor.spin,
                insertion = state.cursor.insertion,
                segment = state.cursor.segment,
                evolution = record,
            )
        end
    end

    # This is intentionally the only solver invocation in the probe.
    result = observables_module.finite_bath_observables(
        parameters;
        beta = BETA,
        tau = TAU,
        purification,
        green_insertion = config.insertion,
        time_step = config.dt,
        cutoff = config.cutoff,
        maxdim = config.maxdim,
        krylov_expansion_dim = config.kdim,
        progress = false,
        checkpoint_manager,
    )
    thermal_history[] === nothing &&
        error("solver did not publish a thermal step history")

    solver = (;
        logZ = result.diagnostics.log_partition,
        n_up = -result.G_up[end],
        n_dn = -result.G_dn[end],
        n_d = result.n_d,
        double_occupancy = result.double_occupancy,
        G_up = copy(result.G_up),
        G_dn = copy(result.G_dn),
        tau = copy(result.tau),
    )
    branches = [
        branch_histories[key] for key in sort!(collect(keys(branch_histories)))
    ]
    length(branches) == 12 ||
        error("solver did not publish all 12 interior branch histories")
    return (;
        schema_version = PROBE_SCHEMA_VERSION,
        probe = "qn_task4_root_cause_convergence",
        fixed_problem = (;
            n_bath = N_BATH,
            U = INTERACTION,
            beta = BETA,
            epsilon_d = EPSILON_D,
            mu = CHEMICAL_POTENTIAL,
            tau = copy(TAU),
        ),
        settings = config,
        representation = (;
            bath = result.provenance.bath_representation,
            purification = result.provenance.purification_mode,
            spin_qn_enabled = result.diagnostics.spin_qn_enabled,
            insertion = config.insertion,
            chain_mapping_sha256 = result.provenance.chain_mapping_sha256,
        ),
        oracle,
        solver,
        errors = _error_payload(solver, oracle),
        diagnostics = (;
            thermal = thermal_history[],
            branches,
            solver_thermal_max_link_dimension =
                result.diagnostics.thermal_max_link_dimension,
            solver_maximum_link_dimensions_by_bond =
                copy(result.diagnostics.maximum_link_dimensions_by_bond),
            mpo_link_dimensions =
                copy(result.diagnostics.mpo_link_dimensions),
        ),
        provenance = (;
            diagnostic_only = true,
            source_remote_job = "2817984",
            source_failure =
                "N_b=3 Task4 Green-function error exceeded 1e-6",
            fixture_bath_sha256 = artifacts.bath_artifact["sha256"],
            fixture_mapping_sha256 =
                artifacts.mapping_artifact["sha256"],
            julia_version = string(VERSION),
            json3_version = string(Base.pkgversion(JSON3)),
            itensors_version = result.provenance.itensors_version,
            itensormps_version = result.provenance.itensormps_version,
            solver_module_version = result.provenance.module_version,
            git_commit = get(ENV, "PROBE_GIT_COMMIT", "unknown"),
            slurm_job_id = get(ENV, "SLURM_JOB_ID", nothing),
        ),
    )
end

function main()
    payload = run_probe()
    println(canonical_json(payload))
    return 0
end

end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    exit(Task4ConvergenceProbe.main())
end
