using Dates
using JSON
using SHA
using Sockets
using Statistics

include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
using .Challenge148

const _RUNNER_ROOT = normpath(joinpath(@__DIR__, ".."))
const _RESULT_SCHEMA_VERSION = 2
const _RAW_BIN_SCHEMA_VERSION = 2
const _RAW_BIN_FIELDS = (
    :energy_per_site,
    :m_time2,
    :m_time4,
    :m_equal2,
    :m_equal4,
    :cuts_mean,
)
const _CUT_HISTOGRAM_FIELD = :cut_histogram
const _CUT_HISTOGRAM_FIELDS = ("cut_counts", "counts", "sum_m2", "sum_m4")
const _RESULT_FIELDS = (
    "schema_version",
    "status",
    "task",
    "task_hash",
    "algorithm",
    "observable_schema_version",
    "physics",
    "provenance",
    "completed_bins",
    "raw_bins",
    "estimates",
    "completion_checksum",
)
const _TASK_RESULT_FIELDS = (
    "schema_version",
    "lattice",
    "L",
    "J",
    "h",
    "c",
    "replica",
    "seed",
    "thermalization_sweeps",
    "measurement_sweeps",
    "base_bin_size",
    "checkpoint_interval_bins",
    "output_path",
    "canonical_task",
)
const _PHYSICS_FIELDS = ("h_input", "h_simulated", "beta")
const _PROVENANCE_FIELDS = (
    "git_commit",
    "manifest_sha256",
    "julia_version",
    "hostname",
    "slurm_job_id",
    "slurm_array_task_id",
    "started_at",
    "completed_at",
    "wall_seconds",
)
const _ESTIMATE_FIELDS = (
    "energy_per_site",
    "m_time2",
    "m_time4",
    "m_equal2",
    "m_equal4",
    "cuts_mean",
    "binder_time",
    "binder_equal",
)
const _ESTIMATE_VALUE_FIELDS = ("mean", "stderr", "bins")

"""Parse exactly the supported one-chain runner command-line grammar."""
function parse_runner_args(arguments::Vector{String})
    length(arguments) in (2, 4) ||
        throw(ArgumentError("usage: run_cluster.jl --task PATH [--stop-after-bins N]"))
    arguments[1] == "--task" ||
        throw(ArgumentError("the first argument must be --task"))
    !isempty(arguments[2]) || throw(ArgumentError("--task requires a nonempty path"))
    if length(arguments) == 2
        return (task_path = arguments[2], stop_after_bins = nothing)
    end
    arguments[3] == "--stop-after-bins" ||
        throw(ArgumentError("only --stop-after-bins may follow --task PATH"))
    all(isdigit, arguments[4]) && !isempty(arguments[4]) ||
        throw(ArgumentError("--stop-after-bins requires a nonnegative decimal integer"))
    stop_after_bins = try
        parse(Int, arguments[4])
    catch error
        error isa OverflowError || rethrow()
        throw(ArgumentError("--stop-after-bins is outside the supported integer range"))
    end
    return (task_path = arguments[2], stop_after_bins)
end

function _git_commit()
    if haskey(ENV, "CHALLENGE148_RELEASE_COMMIT")
        commit = ENV["CHALLENGE148_RELEASE_COMMIT"]
        occursin(r"^[0-9a-f]{40}$", commit) ||
            throw(ArgumentError("CHALLENGE148_RELEASE_COMMIT must be 40 lowercase hex characters"))
        return String(commit)
    end
    try
        commit = readchomp(`git -C $_RUNNER_ROOT rev-parse HEAD`)
        occursin(r"^[0-9a-f]{40}$", commit) || error("git returned a malformed commit")
        return String(commit)
    catch error
        throw(ArgumentError("could not determine the Git commit for $_RUNNER_ROOT: $(sprint(showerror, error))"))
    end
end

function _manifest_hash()
    manifest_path = joinpath(_RUNNER_ROOT, "Manifest.toml")
    isfile(manifest_path) || throw(ArgumentError("Manifest.toml is required for runner provenance"))
    return bytes2hex(sha256(read(manifest_path)))
end

_checkpoint_path(task::ClusterTask) = task.output_path * ".checkpoint"

function _task_result_record(task::ClusterTask)
    return (
        schema_version = task.schema_version,
        lattice = String(task.lattice),
        L = task.L,
        J = task.J,
        h = task.h,
        c = task.c,
        replica = task.replica,
        seed = "u64:" * string(task.seed, base=16, pad=16),
        thermalization_sweeps = task.thermalization_sweeps,
        measurement_sweeps = task.measurement_sweeps,
        base_bin_size = task.base_bin_size,
        checkpoint_interval_bins = task.checkpoint_interval_bins,
        output_path = task.output_path,
        canonical_task = canonical_task_string(task),
    )
end

function _raw_bin_columns(bins::Vector{BinRecord})
    scalar_columns = NamedTuple{_RAW_BIN_FIELDS}(
        Tuple(getfield.(bins, field) for field in _RAW_BIN_FIELDS),
    )
    return merge(scalar_columns, (_CUT_HISTOGRAM_FIELD => [_histogram_record(bin.cut_histogram) for bin in bins],))
end

function _histogram_record(histogram::CutHistogramBin)
    return (
        cut_counts = collect(histogram.cut_counts),
        counts = collect(histogram.counts),
        sum_m2 = collect(histogram.sum_m2),
        sum_m4 = collect(histogram.sum_m4),
    )
end

function _estimate(values::AbstractVector{<:Real})
    n = length(values)
    n > 0 || throw(ArgumentError("cannot estimate an empty bin series"))
    return (mean = mean(values), stderr = n == 1 ? nothing : std(values) / sqrt(n), bins = n)
end

function _binder_estimate(m2::AbstractVector{<:Real}, m4::AbstractVector{<:Real})
    length(m2) == length(m4) || throw(ArgumentError("Binder inputs must have equal lengths"))
    n = length(m2)
    n > 0 || throw(ArgumentError("cannot estimate Binder ratio from no bins"))
    value = mean(m2)^2 / mean(m4)
    isfinite(value) || throw(ArgumentError("Binder ratio is not finite"))
    if n == 1
        return (mean = value, stderr = nothing, bins = n)
    end
    estimate = binder_from_bins(m2, m4)
    return (mean = estimate.mean, stderr = estimate.stderr, bins = estimate.bins)
end

function _result_estimates(bins::Vector{BinRecord})
    columns = _raw_bin_columns(bins)
    return (
        energy_per_site = _estimate(columns.energy_per_site),
        m_time2 = _estimate(columns.m_time2),
        m_time4 = _estimate(columns.m_time4),
        m_equal2 = _estimate(columns.m_equal2),
        m_equal4 = _estimate(columns.m_equal4),
        cuts_mean = _estimate(columns.cuts_mean),
        binder_time = _binder_estimate(columns.m_time2, columns.m_time4),
        binder_equal = _binder_estimate(columns.m_equal2, columns.m_equal4),
    )
end

function _completion_checksum(
    task::ClusterTask,
    git_commit::AbstractString,
    manifest_hash::AbstractString,
    bins::Vector{BinRecord},
)
    tokens = String[
        "result_schema=$(_RESULT_SCHEMA_VERSION)",
        "task_hash=$(task_hash(task))",
        "git_commit=$(git_commit)",
        "manifest_sha256=$(manifest_hash)",
        "completed_bins=$(length(bins))",
    ]
    for bin in bins, field in _RAW_BIN_FIELDS
        value = getfield(bin, field)
        push!(tokens, string(field) * "=f64:" * string(reinterpret(UInt64, value), base=16, pad=16))
    end
    for bin in bins
        histogram = bin.cut_histogram
        for index in eachindex(histogram.cut_counts)
            push!(tokens, "cut_count=i:" * string(histogram.cut_counts[index]))
            push!(tokens, "count=i:" * string(histogram.counts[index]))
            push!(tokens, "sum_m2=f64:" * string(reinterpret(UInt64, histogram.sum_m2[index]), base=16, pad=16))
            push!(tokens, "sum_m4=f64:" * string(reinterpret(UInt64, histogram.sum_m4[index]), base=16, pad=16))
        end
    end
    return bytes2hex(sha256(codeunits(join(tokens, "|"))))
end

function _result_record(
    task::ClusterTask,
    git_commit::String,
    manifest_hash::String,
    bins::Vector{BinRecord},
    started_at::String,
    started_seconds::Float64,
)
    completed_at = string(Dates.now(Dates.UTC)) * "Z"
    return (
        schema_version = _RESULT_SCHEMA_VERSION,
        status = "complete",
        task = _task_result_record(task),
        task_hash = task_hash(task),
        algorithm = "continuous_time_cluster",
        observable_schema_version = _RAW_BIN_SCHEMA_VERSION,
        physics = (
            h_input = task.h,
            h_simulated = abs(task.h),
            beta = beta_for_aspect(task.h, task.L; c=task.c),
        ),
        provenance = (
            git_commit = git_commit,
            manifest_sha256 = manifest_hash,
            julia_version = string(VERSION),
            hostname = gethostname(),
            slurm_job_id = get(ENV, "SLURM_JOB_ID", nothing),
            slurm_array_task_id = get(ENV, "SLURM_ARRAY_TASK_ID", nothing),
            started_at = started_at,
            completed_at = completed_at,
            wall_seconds = time() - started_seconds,
        ),
        completed_bins = length(bins),
        raw_bins = _raw_bin_columns(bins),
        estimates = _result_estimates(bins),
        completion_checksum = _completion_checksum(task, git_commit, manifest_hash, bins),
    )
end

function _required_value(object::AbstractDict, key::String)
    haskey(object, key) || throw(ArgumentError("completed result is missing $key"))
    return object[key]
end

function _require_exact_keys(object, expected::Tuple, label::String)
    object isa AbstractDict || throw(ArgumentError("$label must be an object"))
    Set(string.(keys(object))) == Set(expected) ||
        throw(ArgumentError("$label has missing or unknown fields"))
    return object
end

function _require_exact_string(value, expected::AbstractString, label::String)
    value isa AbstractString && value == expected ||
        throw(ArgumentError("$label does not match"))
    return nothing
end

function _require_exact_int(value, expected::Int, label::String)
    value isa Integer && !(value isa Bool) && value == expected ||
        throw(ArgumentError("$label does not match"))
    return nothing
end

function _finite_float(value, label::String)
    value isa Real && !(value isa Bool) || throw(ArgumentError("$label must be numeric"))
    converted = Float64(value)
    isfinite(converted) || throw(ArgumentError("$label must be finite"))
    return converted
end

function _require_exact_float(value, expected::Float64, label::String)
    observed = _finite_float(value, label)
    isapprox(observed, expected; rtol=64eps(Float64), atol=64eps(Float64)) ||
        throw(ArgumentError("$label does not match"))
    return nothing
end

function _histogram_from_record(value, label::String, samples_per_bin::Int)
    _require_exact_keys(value, _CUT_HISTOGRAM_FIELDS, label)
    columns = Vector{Vector{Any}}()
    for field in _CUT_HISTOGRAM_FIELDS
        values = _required_value(value, field)
        values isa AbstractVector || throw(ArgumentError("$label.$field must be an array"))
        push!(columns, collect(values))
    end
    length(columns[1]) == length(columns[2]) == length(columns[3]) == length(columns[4]) ||
        throw(ArgumentError("$label fields must have equal lengths"))
    cut_counts = Int[]
    counts = Int[]
    for (field, destination, values) in (("cut_counts", cut_counts, columns[1]), ("counts", counts, columns[2]))
        for entry in values
            entry isa Integer && !(entry isa Bool) ||
                throw(ArgumentError("$label.$field must contain integers"))
            push!(destination, Int(entry))
        end
    end
    histogram = CutHistogramBin(
        cut_counts,
        counts,
        [_finite_float(entry, "$label.sum_m2") for entry in columns[3]],
        [_finite_float(entry, "$label.sum_m4") for entry in columns[4]],
    )
    sum(histogram.counts) == samples_per_bin ||
        throw(ArgumentError("$label sample count does not match the task bin size"))
    return histogram
end

function _result_bins(result::AbstractDict, completed_bins::Int, samples_per_bin::Int)
    raw = _required_value(result, "raw_bins")
    _require_exact_keys(
        raw,
        (Tuple(String(field) for field in _RAW_BIN_FIELDS)..., String(_CUT_HISTOGRAM_FIELD)),
        "completed result raw_bins",
    )
    columns = Vector{Vector{Float64}}()
    for field in _RAW_BIN_FIELDS
        name = String(field)
        values = _required_value(raw, name)
        values isa AbstractVector || throw(ArgumentError("raw bin column $name must be an array"))
        length(values) == completed_bins ||
            throw(ArgumentError("raw bin column $name has the wrong length"))
        push!(columns, [_finite_float(value, "raw bin $name") for value in values])
    end
    histograms = _required_value(raw, String(_CUT_HISTOGRAM_FIELD))
    histograms isa AbstractVector ||
        throw(ArgumentError("raw bin cut_histogram must be an array"))
    length(histograms) == completed_bins ||
        throw(ArgumentError("raw bin cut_histogram has the wrong length"))
    return [
        BinRecord(
            (column[index] for column in columns)...,
            _histogram_from_record(
                histograms[index], "raw bin cut_histogram[$index]", samples_per_bin),
        ) for index in 1:completed_bins
    ]
end

function _verify_task_record(task_record, task::ClusterTask)
    _require_exact_keys(task_record, _TASK_RESULT_FIELDS, "completed result task")
    expected = _task_result_record(task)
    for field in _TASK_RESULT_FIELDS
        actual = _required_value(task_record, field)
        expected_value = getproperty(expected, Symbol(field))
        label = "completed result task.$field"
        if expected_value isa Float64
            _require_exact_float(actual, expected_value, label)
        elseif expected_value isa Int
            _require_exact_int(actual, expected_value, label)
        else
            _require_exact_string(actual, expected_value, label)
        end
    end
    return nothing
end

function _verify_physics(physics, task::ClusterTask)
    _require_exact_keys(physics, _PHYSICS_FIELDS, "completed result physics")
    _require_exact_float(_required_value(physics, "h_input"), task.h, "completed result physics.h_input")
    _require_exact_float(_required_value(physics, "h_simulated"), abs(task.h), "completed result physics.h_simulated")
    _require_exact_float(
        _required_value(physics, "beta"),
        beta_for_aspect(task.h, task.L; c=task.c),
        "completed result physics.beta",
    )
    return nothing
end

function _verify_provenance(provenance, git_commit::AbstractString, manifest_hash::AbstractString)
    _require_exact_keys(provenance, _PROVENANCE_FIELDS, "completed result provenance")
    _require_exact_string(_required_value(provenance, "git_commit"), git_commit, "completed result Git commit")
    _require_exact_string(_required_value(provenance, "manifest_sha256"), manifest_hash, "completed result Manifest hash")
    _require_exact_string(_required_value(provenance, "julia_version"), string(VERSION), "completed result Julia version")
    for field in ("hostname", "started_at", "completed_at")
        value = _required_value(provenance, field)
        value isa AbstractString && !isempty(value) ||
            throw(ArgumentError("completed result provenance.$field must be a nonempty string"))
    end
    for field in ("slurm_job_id", "slurm_array_task_id")
        value = _required_value(provenance, field)
        (value === nothing || value isa AbstractString) ||
            throw(ArgumentError("completed result provenance.$field must be a string or null"))
    end
    _finite_float(_required_value(provenance, "wall_seconds"), "completed result wall_seconds") >= 0 ||
        throw(ArgumentError("completed result wall_seconds must be nonnegative"))
    return nothing
end

function _verify_estimate(observed, expected, label::String)
    _require_exact_keys(observed, _ESTIMATE_VALUE_FIELDS, label)
    _require_exact_float(_required_value(observed, "mean"), expected.mean, "$label.mean")
    stderr = _required_value(observed, "stderr")
    if expected.stderr === nothing
        stderr === nothing || throw(ArgumentError("$label.stderr does not match"))
    else
        _require_exact_float(stderr, expected.stderr, "$label.stderr")
    end
    _require_exact_int(_required_value(observed, "bins"), expected.bins, "$label.bins")
    return nothing
end

function _verify_estimates(estimates, bins::Vector{BinRecord})
    _require_exact_keys(estimates, _ESTIMATE_FIELDS, "completed result estimates")
    expected = _result_estimates(bins)
    for field in _ESTIMATE_FIELDS
        _verify_estimate(
            _required_value(estimates, field),
            getproperty(expected, Symbol(field)),
            "completed result estimates.$field",
        )
    end
    return nothing
end

"""Validate a completed output against this exact immutable task and provenance."""
function verify_completed_result(
    path::AbstractString,
    task::ClusterTask;
    git_commit::AbstractString,
    manifest_hash::AbstractString,
)
    islink(path) && throw(ArgumentError("completed result must not be a symlink: $path"))
    isfile(path) ||
        throw(ArgumentError("completed result must be a regular file: $path"))
    result = try
        JSON.parsefile(path)
    catch error
        throw(ArgumentError("could not parse completed result $path: $(sprint(showerror, error))"))
    end
    _require_exact_keys(result, _RESULT_FIELDS, "completed result")
    _require_exact_int(_required_value(result, "schema_version"), _RESULT_SCHEMA_VERSION, "completed result schema version")
    _require_exact_string(_required_value(result, "status"), "complete", "completed result status")
    _require_exact_string(_required_value(result, "task_hash"), task_hash(task), "completed result task hash")
    _require_exact_string(_required_value(result, "algorithm"), "continuous_time_cluster", "completed result algorithm")
    _require_exact_int(
        _required_value(result, "observable_schema_version"),
        _RAW_BIN_SCHEMA_VERSION,
        "completed result observable schema version",
    )
    task_record = _required_value(result, "task")
    _verify_task_record(task_record, task)
    _verify_physics(_required_value(result, "physics"), task)
    provenance = _required_value(result, "provenance")
    _verify_provenance(provenance, git_commit, manifest_hash)
    completed_bins_value = _required_value(result, "completed_bins")
    completed_bins_value isa Integer && !(completed_bins_value isa Bool) ||
        throw(ArgumentError("completed result completed_bins must be an integer"))
    completed_bins = Int(completed_bins_value)
    expected_bins = div(task.measurement_sweeps, task.base_bin_size)
    completed_bins == expected_bins ||
        throw(ArgumentError("completed result has incomplete or excessive bins"))
    bins = _result_bins(result, completed_bins, task.base_bin_size)
    _verify_estimates(_required_value(result, "estimates"), bins)
    _require_exact_string(
        _required_value(result, "completion_checksum"),
        _completion_checksum(task, git_commit, manifest_hash, bins),
        "completed result checksum",
    )
    return result
end

function _load_matching_checkpoint(
    path::String,
    task::ClusterTask,
    git_commit::String,
    manifest_hash::String,
)
    islink(path) && throw(ArgumentError("checkpoint must not be a symlink: $path"))
    isfile(path) || return nothing
    try
        return load_checkpoint(path, task; git_commit, manifest_hash)
    catch error
        error isa ArgumentError || rethrow()
        return nothing
    end
end

function _resume_checkpoint(
    checkpoint_path::String,
    task::ClusterTask,
    git_commit::String,
    manifest_hash::String,
)
    saw_incompatible_checkpoint = false
    for path in (checkpoint_path, checkpoint_path * ".previous", checkpoint_path * ".previous.recovery")
        if islink(path)
            throw(ArgumentError("checkpoint must not be a symlink: $path"))
        elseif ispath(path)
            isfile(path) || throw(ArgumentError("checkpoint must be a regular file: $path"))
        else
            continue
        end
        checkpoint = _load_matching_checkpoint(path, task, git_commit, manifest_hash)
        checkpoint === nothing || return checkpoint
        saw_incompatible_checkpoint = true
    end
    saw_incompatible_checkpoint &&
        throw(ArgumentError("no existing checkpoint matches the requested task, code, and Manifest"))
    return nothing
end

function _remove_matching_checkpoints!(
    checkpoint_path::String,
    task::ClusterTask,
    git_commit::String,
    manifest_hash::String,
)
    for path in (checkpoint_path, checkpoint_path * ".previous", checkpoint_path * ".previous.recovery")
        islink(path) && throw(ArgumentError("checkpoint must not be a symlink: $path"))
        checkpoint = _load_matching_checkpoint(path, task, git_commit, manifest_hash)
        checkpoint === nothing && continue
        rm(path; force=false)
    end
    return nothing
end

"""Run one immutable cluster task, checkpointing complete bins and optionally stopping early."""
function run_cluster_task(task_path::String; stop_after_bins::Union{Nothing,Int}=nothing)
    task = read_task(task_path)
    stop_after_bins === nothing || stop_after_bins >= 0 ||
        throw(ArgumentError("stop_after_bins must be nonnegative"))
    git_commit = _git_commit()
    manifest_hash = _manifest_hash()
    checkpoint_path = _checkpoint_path(task)

    islink(task.output_path) &&
        throw(ArgumentError("completed result must not be a symlink: $(task.output_path)"))
    if ispath(task.output_path)
        verify_completed_result(task.output_path, task; git_commit, manifest_hash)
        _remove_matching_checkpoints!(checkpoint_path, task, git_commit, manifest_hash)
        return task.output_path
    end

    started_at = string(Dates.now(Dates.UTC)) * "Z"
    started_seconds = time()
    checkpoint = _resume_checkpoint(checkpoint_path, task, git_commit, manifest_hash)
    if checkpoint === nothing
        state = CWAState(
            lattice_geometry(task.lattice, task.L);
            J=task.J,
            h=task.h,
            beta=beta_for_aspect(task.h, task.L; c=task.c),
            seed=task.seed,
        )
        thermalize!(state, task.thermalization_sweeps)
        bins = BinRecord[]
    else
        state = checkpoint.state
        bins = checkpoint.bins
    end

    total_bins = div(task.measurement_sweeps, task.base_bin_size)
    target_bins = stop_after_bins === nothing ? total_bins : min(stop_after_bins, total_bins)
    while length(bins) < target_bins
        chunk_bins = min(task.checkpoint_interval_bins, target_bins - length(bins))
        append!(bins, run_bins!(state, chunk_bins, task.base_bin_size))
        save_checkpoint(checkpoint_path, task, state, bins; git_commit, manifest_hash)
    end

    if length(bins) < total_bins
        if !isfile(checkpoint_path)
            save_checkpoint(checkpoint_path, task, state, bins; git_commit, manifest_hash)
        end
        return nothing
    end

    result = _result_record(task, git_commit, manifest_hash, bins, started_at, started_seconds)
    write_completed_result(task.output_path, result)
    verify_completed_result(task.output_path, task; git_commit, manifest_hash)
    _remove_matching_checkpoints!(checkpoint_path, task, git_commit, manifest_hash)
    return task.output_path
end

function _main()
    parsed = parse_runner_args(copy(ARGS))
    run_cluster_task(parsed.task_path; stop_after_bins=parsed.stop_after_bins)
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    try
        _main()
    catch error
        Base.display_error(stderr, catch_backtrace())
        exit(1)
    end
end
