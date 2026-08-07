#!/usr/bin/env julia

module Task5QNResourceBenchmark

using JSON3
using SHA

const PRODUCTION_ROOT = normpath(joinpath(@__DIR__, ".."))
const SOLUTION_ROOT = normpath(joinpath(PRODUCTION_ROOT, ".."))
include(joinpath(PRODUCTION_ROOT, "finite_bath_mps_runner.jl"))
include(joinpath(@__DIR__, "validated_chain_fixture.jl"))

const BENCHMARK_SCHEMA_VERSION = 1
const SCIENTIFIC_THRESHOLD = 1.0e-6
const TRUNCATION_LIMIT = 1.0e-8
const KRYLOV_LIMIT = 1.0e-8
const SOURCE_FILES = (
    "finite_bath_purification.jl",
    "finite_bath_observables.jl",
    "finite_bath_checkpoint.jl",
    "finite_bath_mps_runner.jl",
)

function _choice(env, key, default, choices)
    value = get(env, key, default)
    value in choices ||
        throw(ArgumentError("$key must be one of $(join(choices, ", "))"))
    return Symbol(value)
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

function _sha1(env, key)
    value = get(env, key, "")
    occursin(r"^[0-9a-f]{40}$", value) ||
        throw(ArgumentError("$key must be a lowercase 40-character Git SHA"))
    return value
end

function parse_benchmark_config(env = ENV)
    n_bath = _positive_integer(env, "N_BATH", "12")
    return (;
        mode = _choice(env, "MODE", "qn", ("non_qn", "qn")),
        n_bath,
        beta = _positive_float(env, "BETA", "0.2"),
        dt = _positive_float(env, "DT", "0.05"),
        cutoff = _nonnegative_float(env, "CUTOFF", "1e-12"),
        maxdim = _positive_integer(env, "MAXDIM", "256"),
        kdim = _nonnegative_integer(env, "KDIM", "0"),
        expected_git_commit = _sha1(env, "EXPECTED_GIT_COMMIT"),
        bath_path = get(env, "BATH_ARTIFACT_PATH", ""),
        mapping_path = get(env, "MAPPING_ARTIFACT_PATH", ""),
        expected_bath_file_sha256 = get(env, "EXPECTED_BATH_FILE_SHA256", ""),
        expected_mapping_file_sha256 =
            get(env, "EXPECTED_MAPPING_FILE_SHA256", ""),
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
        entries = [
            canonical_json(key) * ":" * canonical_json(value[key])
            for key in sort!(String.(collect(keys(value))))
        ]
        return "{" * join(entries, ",") * "}"
    end
    throw(ArgumentError("unsupported canonical JSON value $(typeof(value))"))
end

_file_sha256(path) = bytes2hex(sha256(read(path)))

function _read_artifacts(config)
    if isempty(config.bath_path) && isempty(config.mapping_path)
        config.n_bath <= 6 ||
            throw(ArgumentError("N_b>6 requires explicit bath and mapping paths"))
        return validated_chain_fixture_artifacts(config.n_bath)
    end
    isempty(config.bath_path) != isempty(config.mapping_path) &&
        throw(ArgumentError("bath and mapping paths must be supplied together"))
    isfile(config.bath_path) || throw(ArgumentError("bath path is not a file"))
    isfile(config.mapping_path) || throw(ArgumentError("mapping path is not a file"))
    bath_json = read(config.bath_path, String)
    mapping_json = read(config.mapping_path, String)
    _file_sha256(config.bath_path) == config.expected_bath_file_sha256 ||
        throw(ArgumentError("bath file SHA256 mismatch"))
    _file_sha256(config.mapping_path) == config.expected_mapping_file_sha256 ||
        throw(ArgumentError("mapping file SHA256 mismatch"))
    return (;
        bath_json,
        mapping_json,
        bath_artifact = strict_json_read(bath_json, "benchmark bath artifact"),
        mapping_artifact =
            strict_json_read(mapping_json, "benchmark mapping artifact"),
    )
end

function _summary(histories)
    truncation = 0.0
    krylov_error = 0.0
    krylov_converged = true
    completed_steps = 0
    for history in values(histories), entry in history
        completed_steps += 1
        truncation = max(truncation, entry.max_truncation_error)
        krylov_error = max(krylov_error, entry.krylov_max_error_estimate)
        krylov_converged &= entry.krylov_all_converged
    end
    return (; completed_steps, truncation, krylov_error, krylov_converged)
end

function _source_hashes()
    hashes = Dict(
        name => _file_sha256(joinpath(PRODUCTION_ROOT, name))
        for name in SOURCE_FILES
    )
    hashes[basename(@__FILE__)] = _file_sha256(@__FILE__)
    hashes["task5_qn_resource_benchmark.sbatch"] =
        _file_sha256(joinpath(@__DIR__, "task5_qn_resource_benchmark.sbatch"))
    hashes["bath.py"] = _file_sha256(joinpath(SOLUTION_ROOT, "bath.py"))
    hashes["chain_mapping.py"] =
        _file_sha256(joinpath(SOLUTION_ROOT, "chain_mapping.py"))
    hashes["Project.toml"] = _file_sha256(joinpath(PRODUCTION_ROOT, "Project.toml"))
    hashes["Manifest.toml"] = _file_sha256(joinpath(PRODUCTION_ROOT, "Manifest.toml"))
    return hashes
end

function run_benchmark(config = parse_benchmark_config())
    artifacts = _read_artifacts(config)
    bath_payload = artifacts.bath_artifact["payload"]
    Int(bath_payload["parameters"]["n_bath"]) == config.n_bath ||
        throw(ArgumentError("configured N_b does not match bath artifact"))
    validated = validate_chain_mapping_artifact(
        artifacts.mapping_artifact,
        artifacts.mapping_json,
        artifacts.bath_artifact,
    )
    purification_module = getfield(@__MODULE__, :FiniteBathPurification)
    observables_module = getfield(@__MODULE__, :FiniteBathObservables)
    parameters = purification_module.FiniteBathParameters(
        validated; U = 0.8, epsilon_d = -0.4, mu = 0.0
    )
    purification =
        config.mode === :qn ?
        purification_module.qn_dual_purification(parameters, validated) :
        purification_module.non_qn_purification()
    tau = [0.0, config.beta / 4, config.beta / 2, 3config.beta / 4, config.beta]
    histories = Dict{String,Any}()
    checkpoint_manager = (_, state) -> begin
        evolution = state.evolution_state
        evolution === nothing && return
        cursor = state.cursor
        key = join(
            (
                String(cursor.phase),
                string(cursor.tau_index),
                String(cursor.spin),
                String(cursor.segment),
            ),
            ":",
        )
        histories[key] = copy(evolution.step_history)
    end
    rss_before = Sys.maxrss()
    started = time_ns()
    result = observables_module.finite_bath_observables(
        parameters;
        beta = config.beta,
        tau,
        purification,
        green_insertion = :creation,
        time_step = config.dt,
        cutoff = config.cutoff,
        maxdim = config.maxdim,
        krylov_expansion_dim = config.kdim,
        progress = false,
        checkpoint_manager,
    )
    wall_seconds = (time_ns() - started) / 1.0e9
    peak_rss_bytes = max(rss_before, Sys.maxrss())
    summary = _summary(histories)
    max_link = maximum(result.diagnostics.maximum_link_dimensions_by_bond; init = 1)
    maxdim_saturated = max_link >= config.maxdim
    return (;
        schema_version = BENCHMARK_SCHEMA_VERSION,
        artifact_type = "qn_chain_resource_sample",
        fixed_problem = (;
            n_bath = config.n_bath,
            U = 0.8,
            epsilon_d = -0.4,
            mu = 0.0,
            beta = config.beta,
            tau,
            bath_representation = "chain",
            green_insertion = "creation",
            bath_sha256 = artifacts.bath_artifact["sha256"],
            mapping_sha256 = artifacts.mapping_artifact["sha256"],
        ),
        settings = (;
            purification_mode = config.mode === :qn ? "qn_dual" : "non_qn",
            qn_gauge =
                config.mode === :qn ?
                "electron_nf_sz_ancilla_particle_hole" : nothing,
            qn_gauge_version = config.mode === :qn ? 1 : nothing,
            base_sector =
                config.mode === :qn ?
                (Nf = 2 * (config.n_bath + 1), Sz = 0) : nothing,
            time_step = config.dt,
            cutoff = config.cutoff,
            maxdim = config.maxdim,
            krylov_expansion_dim = config.kdim,
        ),
        matched_work = (;
            completed_steps = summary.completed_steps,
            tau_points = length(tau),
            spin_branches = 2,
        ),
        resources = (; wall_seconds, peak_rss_bytes),
        diagnostics = (;
            mpo_link_dimensions = copy(result.diagnostics.mpo_link_dimensions),
            maximum_link_dimensions_by_bond =
                copy(result.diagnostics.maximum_link_dimensions_by_bond),
            truncation_max_error = summary.truncation,
            krylov_max_error_estimate = summary.krylov_error,
            krylov_all_converged = summary.krylov_converged,
            maxdim_saturated,
        ),
        observables = (;
            n_d = result.n_d,
            double_occupancy = result.double_occupancy,
            G_up = copy(result.G_up),
            G_down = copy(result.G_dn),
        ),
        provenance = (;
            git_commit = config.expected_git_commit,
            source_hashes = _source_hashes(),
            julia_version = string(VERSION),
            itensors_version = result.provenance.itensors_version,
            itensormps_version = result.provenance.itensormps_version,
            solver_module_version = result.provenance.module_version,
            slurm_job_id = get(ENV, "SLURM_JOB_ID", nothing),
            slurm_cpus_per_task =
                tryparse(Int, get(ENV, "SLURM_CPUS_PER_TASK", "1")),
        ),
    )
end

function _observable_delta(left, right)
    values = [
        abs(left.n_d - right.n_d),
        abs(left.double_occupancy - right.double_occupancy),
        abs.(left.G_up .- right.G_up)...,
        abs.(left.G_down .- right.G_down)...,
    ]
    return maximum(values)
end

function validate_paired_benchmark(non_qn, qn)
    non_qn.artifact_type == qn.artifact_type == "qn_chain_resource_sample" ||
        throw(ArgumentError("sample artifact type mismatch"))
    non_qn.settings.purification_mode == "non_qn" ||
        throw(ArgumentError("baseline sample must be non-QN chain"))
    qn.settings.purification_mode == "qn_dual" ||
        throw(ArgumentError("candidate sample must be QN dual chain"))
    non_qn.fixed_problem == qn.fixed_problem ||
        throw(ArgumentError("paired benchmark problem mismatch"))
    non_qn.matched_work == qn.matched_work ||
        throw(ArgumentError("paired benchmark work mismatch"))
    non_qn.provenance.git_commit == qn.provenance.git_commit ||
        throw(ArgumentError("paired benchmark commit mismatch"))
    non_qn.provenance.source_hashes == qn.provenance.source_hashes ||
        throw(ArgumentError("paired benchmark source mismatch"))
    delta = _observable_delta(non_qn.observables, qn.observables)
    diagnostic_passed = all(
        sample ->
            sample.diagnostics.krylov_all_converged &&
            !sample.diagnostics.maxdim_saturated &&
            sample.diagnostics.truncation_max_error <= TRUNCATION_LIMIT &&
            sample.diagnostics.krylov_max_error_estimate <= KRYLOV_LIMIT,
        (non_qn, qn),
    )
    return (;
        schema_version = BENCHMARK_SCHEMA_VERSION,
        artifact_type = "qn_chain_resource_pair",
        status = "n_bath_12_qualification_only",
        scientific_threshold = SCIENTIFIC_THRESHOLD,
        observable_max_absolute_delta = delta,
        diagnostic_validation_passed = diagnostic_passed,
        scientific_validation_passed =
            diagnostic_passed && delta <= SCIENTIFIC_THRESHOLD,
        wall_seconds_qn_over_non_qn =
            qn.resources.wall_seconds / non_qn.resources.wall_seconds,
        peak_rss_qn_over_non_qn =
            qn.resources.peak_rss_bytes / non_qn.resources.peak_rss_bytes,
        maximum_mpo_link_qn_over_non_qn =
            maximum(qn.diagnostics.mpo_link_dimensions) /
            maximum(non_qn.diagnostics.mpo_link_dimensions),
        maximum_mps_link_qn_over_non_qn =
            maximum(qn.diagnostics.maximum_link_dimensions_by_bond) /
            maximum(non_qn.diagnostics.maximum_link_dimensions_by_bond),
        production_beta32_eligible = false,
        n_bath_48_eligible = false,
    )
end

function main()
    println(canonical_json(run_benchmark()))
    return 0
end

end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    exit(Task5QNResourceBenchmark.main())
end
