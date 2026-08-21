using JSON
using SHA

include(joinpath(@__DIR__, "run_cluster.jl"))

const _AGGREGATE_ROOT = normpath(joinpath(@__DIR__, ".."))
const _CAMPAIGN_MANIFEST_SCHEMA_VERSION = 1
const _CAMPAIGN_MANIFEST_KIND = "route_a_campaign_manifest"
const _CAMPAIGN_MANIFEST_FIELDS = (
    "schema_version",
    "kind",
    "campaign_id",
    "campaign_checksum",
    "git_commit",
    "julia_manifest_sha256",
    "julia_version",
    "algorithm",
    "observable_schema_version",
    "tasks",
)
const _COMBINED_BINS_SCHEMA_VERSION = 1
const _AUDIT_SCHEMA_VERSION = 1
const _RELEASE_REQUIRED_FILES = (
    "Project.toml", "Manifest.toml", "src/Challenge148.jl",
    "scripts/run_cluster.jl", "scripts/aggregate_route_a.jl", "test/runtests.jl",
)
const _FROZEN_RESOURCE_FIELDS = (
    "schema_version", "kind", "approved", "estimate_checksum",
    "calibration_path", "calibration_content_sha256", "config_path",
    "config_content_sha256", "campaign_id", "campaign_checksum",
    "release_git_commit", "release_julia_manifest_sha256", "release_julia_version",
    "task_count", "predicted_cpu_seconds", "max_task_wall_seconds",
    "max_task_memory_bytes", "predicted_disk_bytes", "requested_walltime_seconds",
    "requested_memory_bytes", "requested_disk_bytes", "walltime_fraction_limit",
    "memory_fraction_limit", "disk_fraction_limit", "task_resources", "deployment_instruction",
)
const _TASK_RESOURCE_FIELDS = (
    "task_id", "task_hash", "predicted_wall_seconds", "predicted_memory_bytes",
    "predicted_disk_bytes",
)

_sha256_token(value::AbstractString) = occursin(r"^[0-9a-f]{64}$", value)
_commit_token(value::AbstractString) = occursin(r"^[0-9a-f]{40}$", value)

function _git_read(root::AbstractString, arguments::AbstractString...)
    try
        return read(pipeline(`git -C $root $(arguments)`; stderr=devnull), String)
    catch
        return nothing
    end
end

function _release_prefix(root::AbstractString)
    top = _git_read(root, "rev-parse", "--show-toplevel")
    top === nothing && return nothing
    relative = relpath(abspath(root), abspath(strip(top)))
    relative == "." && return ""
    startswith(relative, "..") && return nothing
    return replace(relative, '\\' => '/')
end

_release_path(prefix::AbstractString, relative::AbstractString) =
    isempty(prefix) ? String(relative) : prefix * "/" * relative

"""Fail-closed verification of a runnable historical release snapshot."""
function _verify_release_snapshot(commit::AbstractString, manifest_hash::AbstractString;
    root::AbstractString=_AGGREGATE_ROOT)
    _commit_token(commit) && _sha256_token(manifest_hash) || return false
    inside = _git_read(root, "rev-parse", "--is-inside-work-tree")
    inside !== nothing && strip(inside) == "true" || return false
    _git_read(root, "cat-file", "-e", String(commit) * "^{commit}") !== nothing || return false
    prefix = _release_prefix(root)
    prefix === nothing && return false
    for candidate in unique((prefix, ""))
        all(relative -> _git_read(
                root, "cat-file", "-e",
                String(commit) * ":" * _release_path(candidate, relative),
            ) !== nothing,
            _RELEASE_REQUIRED_FILES,
        ) || continue
        manifest = _git_read(
            root, "show", String(commit) * ":" * _release_path(candidate, "Manifest.toml"))
        manifest === nothing && continue
        bytes2hex(sha256(codeunits(manifest))) == manifest_hash && return true
    end
    return false
end

_resource_field(record::NamedTuple, name::String) = getproperty(record, Symbol(name))
_resource_field(record::AbstractDict, name::String) = record[name]

function _resource_checksum_token(value)
    value isa Bool && return value ? "b1" : "b0"
    value isa Integer && return "i" * string(value)
    value isa Real && !(value isa Bool) && return "f" *
        string(reinterpret(UInt64, Float64(value)); base=16, pad=16)
    value isa AbstractString && return "s" * bytes2hex(codeunits(value))
    throw(ArgumentError("unsupported resource checksum value"))
end

"""Canonical checksum of every resource-estimate payload field and task detail."""
function _resource_estimate_checksum(record)
    tokens = String[]
    for name in _FROZEN_RESOURCE_FIELDS
        name in ("estimate_checksum", "task_resources") && continue
        push!(tokens, name * "=" * _resource_checksum_token(_resource_field(record, name)))
    end
    details = collect(_resource_field(record, "task_resources"))
    sort!(details; by=detail -> String(_resource_field(detail, "task_id")))
    for detail in details, name in _TASK_RESOURCE_FIELDS
        push!(tokens, "task." * name * "=" *
            _resource_checksum_token(_resource_field(detail, name)))
    end
    return bytes2hex(sha256(codeunits(join(tokens, "|"))))
end

function _campaign_task_record(task::ClusterTask)
    return (
        schema_version=task.schema_version,
        lattice=String(task.lattice),
        L=task.L,
        J=task.J,
        h=task.h,
        c=task.c,
        replica=task.replica,
        seed="u64:" * string(task.seed, base=16, pad=16),
        thermalization_sweeps=task.thermalization_sweeps,
        measurement_sweeps=task.measurement_sweeps,
        base_bin_size=task.base_bin_size,
        checkpoint_interval_bins=task.checkpoint_interval_bins,
        output_path=task.output_path,
    )
end

function _campaign_checksum(
    campaign_id::String,
    git_commit::String,
    julia_manifest_sha256::String,
    julia_version::String,
    algorithm::String,
    observable_schema_version::Int,
    tasks::Vector{ClusterTask},
)
    tokens = String[
        "campaign_manifest_schema=$(_CAMPAIGN_MANIFEST_SCHEMA_VERSION)",
        "kind=$(_CAMPAIGN_MANIFEST_KIND)",
        "campaign_id=$(bytes2hex(codeunits(campaign_id)))",
        "git_commit=$git_commit",
        "julia_manifest_sha256=$julia_manifest_sha256",
        "julia_version=$(bytes2hex(codeunits(julia_version)))",
        "algorithm=$(bytes2hex(codeunits(algorithm)))",
        "observable_schema_version=$observable_schema_version",
    ]
    append!(tokens, "task=" * canonical_task_string(task) for task in tasks)
    return bytes2hex(sha256(codeunits(join(tokens, "|"))))
end

"""Write the frozen, versioned Route A campaign input consumed by the aggregator.

`campaign_checksum` identifies this campaign manifest and deliberately differs
from `julia_manifest_sha256`, which identifies the Julia `Manifest.toml` used
to run each chain.  Task objects are ordered and complete immutable tasks.
"""
function write_campaign_manifest(
    path::AbstractString,
    campaign_id::AbstractString,
    git_commit::AbstractString,
    julia_manifest_sha256::AbstractString,
    tasks::Vector{ClusterTask};
    julia_version::AbstractString=string(VERSION),
    algorithm::AbstractString="continuous_time_cluster",
    observable_schema_version::Int=_RAW_BIN_SCHEMA_VERSION,
)
    id = String(campaign_id)
    commit = String(git_commit)
    manifest_hash = String(julia_manifest_sha256)
    runtime = String(julia_version)
    algorithm_name = String(algorithm)
    !isempty(id) || throw(ArgumentError("campaign_id must be nonempty"))
    _commit_token(commit) || throw(ArgumentError("campaign git_commit must be a lowercase SHA-1"))
    _sha256_token(manifest_hash) ||
        throw(ArgumentError("campaign julia_manifest_sha256 must be a lowercase SHA-256"))
    runtime == string(VERSION) || throw(ArgumentError("campaign julia_version must match this Julia runtime"))
    algorithm_name == "continuous_time_cluster" || throw(ArgumentError("unsupported campaign algorithm"))
    observable_schema_version == _RAW_BIN_SCHEMA_VERSION ||
        throw(ArgumentError("unsupported campaign observable schema version"))
    isempty(tasks) && throw(ArgumentError("campaign must contain at least one task"))
    foreach(validate_task, tasks)
    record = (
        schema_version=_CAMPAIGN_MANIFEST_SCHEMA_VERSION,
        kind=_CAMPAIGN_MANIFEST_KIND,
        campaign_id=id,
        campaign_checksum=_campaign_checksum(
            id, commit, manifest_hash, runtime, algorithm_name, observable_schema_version, tasks),
        git_commit=commit,
        julia_manifest_sha256=manifest_hash,
        julia_version=runtime,
        algorithm=algorithm_name,
        observable_schema_version=observable_schema_version,
        tasks=[_campaign_task_record(task) for task in tasks],
    )
    return atomic_write_json(path, record)
end

function _manifest_int(value, label::String)
    value isa Integer && !(value isa Bool) || throw(ArgumentError("$label must be an integer"))
    try
        return Int(value)
    catch error
        error isa InexactError || rethrow()
        throw(ArgumentError("$label must fit in Int"))
    end
end

function _manifest_float(value, label::String)
    value isa Real && !(value isa Bool) || throw(ArgumentError("$label must be numeric"))
    return Float64(value)
end

function _campaign_task(value, index::Int)
    value isa AbstractDict || throw(ArgumentError("campaign task $index must be an object"))
    Set(string.(keys(value))) == Set(Challenge148._TASK_JSON_FIELDS) ||
        throw(ArgumentError("campaign task $index has missing or unknown fields"))
    lattice = value["lattice"]
    output_path = value["output_path"]
    lattice isa AbstractString || throw(ArgumentError("campaign task $index lattice must be a string"))
    output_path isa AbstractString || throw(ArgumentError("campaign task $index output_path must be a string"))
    seed = value["seed"]
    seed isa AbstractString && startswith(seed, "u64:") && ncodeunits(seed) == 20 &&
        all(isxdigit, seed[5:end]) ||
        throw(ArgumentError("campaign task $index seed must be an exact u64 token"))
    return validate_task(ClusterTask(
        _manifest_int(value["schema_version"], "campaign task $index schema_version"),
        Symbol(lattice),
        _manifest_int(value["L"], "campaign task $index L"),
        _manifest_float(value["J"], "campaign task $index J"),
        _manifest_float(value["h"], "campaign task $index h"),
        _manifest_float(value["c"], "campaign task $index c"),
        _manifest_int(value["replica"], "campaign task $index replica"),
        parse(UInt64, seed[5:end]; base=16),
        _manifest_int(value["thermalization_sweeps"], "campaign task $index thermalization_sweeps"),
        _manifest_int(value["measurement_sweeps"], "campaign task $index measurement_sweeps"),
        _manifest_int(value["base_bin_size"], "campaign task $index base_bin_size"),
        _manifest_int(value["checkpoint_interval_bins"], "campaign task $index checkpoint_interval_bins"),
        String(output_path),
    ))
end

function _result_basename(task::ClusterTask)
    basename(task.output_path) == task.output_path && endswith(task.output_path, ".json") &&
        !endswith(task.output_path, ".partial") ||
        throw(ArgumentError("campaign task output_path must be a JSON basename: $(task.output_path)"))
    return task.output_path
end

function _read_campaign_manifest(path::AbstractString)
    islink(path) && throw(ArgumentError("campaign manifest must not be a symlink: $path"))
    isfile(path) || throw(ArgumentError("campaign manifest must be a regular file: $path"))
    manifest = try
        JSON.parsefile(path; dicttype=Dict)
    catch error
        throw(ArgumentError("could not parse campaign manifest $path: $(sprint(showerror, error))"))
    end
    manifest isa AbstractDict || throw(ArgumentError("campaign manifest must be a JSON object"))
    Set(string.(keys(manifest))) == Set(_CAMPAIGN_MANIFEST_FIELDS) ||
        throw(ArgumentError("campaign manifest has missing or unknown fields"))
    _manifest_int(manifest["schema_version"], "campaign manifest schema_version") == _CAMPAIGN_MANIFEST_SCHEMA_VERSION ||
        throw(ArgumentError("unsupported campaign manifest schema version"))
    manifest["kind"] == _CAMPAIGN_MANIFEST_KIND || throw(ArgumentError("unsupported campaign manifest kind"))
    campaign_id = manifest["campaign_id"]
    campaign_id isa AbstractString && !isempty(campaign_id) || throw(ArgumentError("campaign_id must be nonempty"))
    git_commit = manifest["git_commit"]
    git_commit isa AbstractString && _commit_token(git_commit) || throw(ArgumentError("campaign git_commit is invalid"))
    manifest_hash = manifest["julia_manifest_sha256"]
    manifest_hash isa AbstractString && _sha256_token(manifest_hash) ||
        throw(ArgumentError("campaign julia_manifest_sha256 is invalid"))
    runtime = manifest["julia_version"]
    runtime == string(VERSION) || throw(ArgumentError("campaign Julia runtime does not match this runtime"))
    algorithm = manifest["algorithm"]
    algorithm == "continuous_time_cluster" || throw(ArgumentError("campaign algorithm is incompatible"))
    observable_schema_version = _manifest_int(
        manifest["observable_schema_version"], "campaign observable_schema_version")
    observable_schema_version == _RAW_BIN_SCHEMA_VERSION ||
        throw(ArgumentError("campaign observable schema is incompatible"))
    task_values = manifest["tasks"]
    task_values isa AbstractVector && !isempty(task_values) || throw(ArgumentError("campaign tasks must be a nonempty array"))
    tasks = [_campaign_task(value, index) for (index, value) in enumerate(task_values)]
    expected_checksum = _campaign_checksum(
        String(campaign_id), String(git_commit), String(manifest_hash), String(runtime), String(algorithm),
        observable_schema_version, tasks)
    checksum = manifest["campaign_checksum"]
    checksum isa AbstractString && checksum == expected_checksum ||
        throw(ArgumentError("campaign checksum does not match immutable campaign input"))
    hashes = task_hash.(tasks)
    ids = task_id.(tasks)
    seeds = getfield.(tasks, :seed)
    outputs = _result_basename.(tasks)
    length(unique(hashes)) == length(hashes) || throw(ArgumentError("campaign has duplicate task hashes"))
    length(unique(ids)) == length(ids) || throw(ArgumentError("campaign has duplicate task IDs"))
    length(unique(seeds)) == length(seeds) || throw(ArgumentError("campaign has duplicate task seeds"))
    length(unique(outputs)) == length(outputs) || throw(ArgumentError("campaign has duplicate output basenames"))
    return (
        campaign_id=String(campaign_id),
        campaign_checksum=String(checksum),
        git_commit=String(git_commit),
        julia_manifest_sha256=String(manifest_hash),
        julia_version=String(runtime),
        algorithm=String(algorithm),
        observable_schema_version=observable_schema_version,
        tasks=tasks,
        outputs=outputs,
    )
end

function _safe_directory(path::AbstractString, label::String)
    islink(path) && throw(ArgumentError("$label must not be a symlink: $path"))
    isdir(path) || throw(ArgumentError("$label must be an existing directory: $path"))
    return realpath(path)
end

function _safe_manifest_path(path::AbstractString)
    islink(path) && throw(ArgumentError("campaign manifest must not be a symlink: $path"))
    isfile(path) || throw(ArgumentError("campaign manifest must be a regular file: $path"))
    return realpath(path)
end

function _is_within(path::String, parent::String)
    relative = relpath(path, parent)
    return relative == "." || first(splitpath(relative)) != ".."
end

function _file_identity(path::String)
    metadata = stat(path)
    return (metadata.device, metadata.inode)
end

function _input_file_identities(manifest_path::String, results_dir::String)
    identities = Set{Tuple{UInt64,UInt64}}()
    push!(identities, _file_identity(manifest_path))
    for name in readdir(results_dir)
        path = joinpath(results_dir, name)
        !islink(path) && isfile(path) && push!(identities, _file_identity(path))
    end
    return identities
end

function _output_destination(path::String, label::String, input_identities)
    islink(path) && throw(ArgumentError("$label must be absent or a regular file: $path"))
    if ispath(path)
        isfile(path) || throw(ArgumentError("$label must be absent or a regular file: $path"))
        _file_identity(path) in input_identities &&
            throw(ArgumentError("$label aliases an immutable campaign input: $path"))
        return realpath(path)
    end
    return normpath(path)
end

function _guard_output_aliases(manifest_path::AbstractString, results_path::AbstractString, output_path::AbstractString)
    manifest = _safe_manifest_path(manifest_path)
    results = _safe_directory(results_path, "results directory")
    output = _safe_directory(output_path, "output directory")
    _is_within(output, results) &&
        throw(ArgumentError("output directory must be disjoint from the results directory"))
    input_identities = _input_file_identities(manifest, results)
    audit = _output_destination(joinpath(output, "audit.json"), "audit output", input_identities)
    combined = _output_destination(
        joinpath(output, "combined_bins.json"), "combined output", input_identities)
    return (manifest_path=manifest, results_dir=results, output_dir=output, audit_path=audit, combined_path=combined)
end

function _invalidate_combined!(path::String)
    islink(path) && throw(ArgumentError("combined output must be absent or a regular file: $path"))
    if ispath(path)
        isfile(path) || throw(ArgumentError("combined output must be absent or a regular file: $path"))
        rm(path; force=false)
    end
    return nothing
end

function _result_occupants(results_dir::String, expected_outputs::Vector{String})
    observed = String[]
    for name in readdir(results_dir)
        path = joinpath(results_dir, name)
        islink(path) && throw(ArgumentError("results directory contains a symlink: $name"))
        isfile(path) || throw(ArgumentError("results directory contains a nonregular occupant: $name"))
        endswith(name, ".partial") && throw(ArgumentError("results directory contains stale partial: $name"))
        push!(observed, name)
    end
    sort!(observed)
    sort(expected_outputs) == observed ||
        throw(ArgumentError("results directory does not contain exactly the expected result JSON files"))
    return nothing
end

function _audit_record(campaign, passed::Bool, accepted::Vector{String}, errors::Vector{String})
    return (
        schema_version=_AUDIT_SCHEMA_VERSION,
        kind="route_a_campaign_audit",
        campaign_id=campaign === nothing ? nothing : campaign.campaign_id,
        campaign_checksum=campaign === nothing ? nothing : campaign.campaign_checksum,
        julia_manifest_sha256=campaign === nothing ? nothing : campaign.julia_manifest_sha256,
        passed=passed,
        expected_task_count=campaign === nothing ? 0 : length(campaign.tasks),
        accepted_task_ids=accepted,
        errors=errors,
    )
end

function _combined_record(campaign, results::Vector)
    return (
        schema_version=_COMBINED_BINS_SCHEMA_VERSION,
        kind="route_a_combined_bins",
        campaign_id=campaign.campaign_id,
        campaign_checksum=campaign.campaign_checksum,
        julia_manifest_sha256=campaign.julia_manifest_sha256,
        git_commit=campaign.git_commit,
        julia_version=campaign.julia_version,
        algorithm=campaign.algorithm,
        observable_schema_version=campaign.observable_schema_version,
        chains=[
            (
                task_id=task_id(task),
                task_hash=task_hash(task),
                task=result["task"],
                provenance=result["provenance"],
                completed_bins=result["completed_bins"],
                raw_bins=result["raw_bins"],
            ) for (task, result) in zip(campaign.tasks, results)
        ],
    )
end

"""Validate a campaign and its result directory without modifying either input."""
function audit_campaign(manifest_path::AbstractString, results_path::AbstractString)
    campaign = nothing
    accepted = String[]
    errors = String[]
    results = Any[]
    try
        campaign = _read_campaign_manifest(manifest_path)
        _verify_release_snapshot(campaign.git_commit, campaign.julia_manifest_sha256;
            root=_AGGREGATE_ROOT) || throw(ArgumentError("provenance"))
        results_dir = _safe_directory(results_path, "results directory")
        _result_occupants(results_dir, campaign.outputs)
        for task in campaign.tasks
            result_path = joinpath(results_dir, task.output_path)
            result = verify_completed_result(
                result_path, task;
                git_commit=campaign.git_commit,
                manifest_hash=campaign.julia_manifest_sha256,
            )
            push!(results, result)
            push!(accepted, task_id(task))
        end
    catch error
        error isa InterruptException && rethrow()
        push!(errors, sprint(showerror, error))
    end
    passed = isempty(errors)
    audit = _audit_record(campaign, passed, accepted, errors)
    return (passed=passed, audit=audit, campaign=campaign, results=results)
end

"""Audit every expected Route A result before atomically emitting a combined bins file."""
function aggregate_campaign(manifest_path::AbstractString, results_path::AbstractString, output_path::AbstractString)
    guarded = _guard_output_aliases(manifest_path, results_path, output_path)
    audited = audit_campaign(guarded.manifest_path, guarded.results_dir)
    audit = audited.audit
    audited.passed || _invalidate_combined!(guarded.combined_path)
    atomic_write_json(guarded.audit_path, audit)
    if audited.passed
        atomic_write_json(guarded.combined_path, _combined_record(audited.campaign, audited.results))
    end
    return (passed=audited.passed, audit=audit)
end

function _frozen_resource_path(manifest_path::String)
    stem, extension = splitext(manifest_path)
    extension == ".json" || throw(ArgumentError("frozen campaign manifest must end in .json"))
    if endswith(stem, "_recon_manifest")
        return stem[1:end-length("_recon_manifest")] * "_resource_estimate.json"
    elseif endswith(stem, "_manifest")
        return stem[1:end-length("_manifest")] * "_resource_estimate.json"
    end
    return stem * "-resource-estimate.json"
end

function _frozen_evidence_paths(manifest_path::String)
    stem, extension = splitext(manifest_path)
    extension == ".json" || throw(ArgumentError("frozen campaign manifest must end in .json"))
    prefix = endswith(stem, "_recon_manifest") ? stem[1:end-length("_recon_manifest")] :
        endswith(stem, "_manifest") ? stem[1:end-length("_manifest")] : stem
    return (
        calibration_path=prefix * "_calibration.json",
        config_path=prefix * "_recon_config.toml",
    )
end

function _portable_evidence_path(value, parent::String, suffix::String)
    value isa AbstractString && !isempty(value) && basename(value) == value &&
        endswith(value, suffix) || throw(ArgumentError("resource_estimate"))
    return joinpath(parent, String(value))
end

const _MANIFEST_GENERATOR_CACHE = Ref{Union{Nothing,Module}}(nothing)

_latest_binding(module_value::Module, name::Symbol) =
    Base.invokelatest(getfield, module_value, name)

function _manifest_generator()
    cached = _MANIFEST_GENERATOR_CACHE[]
    cached === nothing || return cached
    generator = Module(gensym(:RouteAManifestAudit), true, true)
    Core.eval(generator, :(include(path::AbstractString) = Base.include($generator, path)))
    Base.include(generator, joinpath(_AGGREGATE_ROOT, "scripts", "make_route_a_manifest.jl"))
    _MANIFEST_GENERATOR_CACHE[] = generator
    return generator
end

function _same_frozen_manifest(campaign, generated, generator::Module)
    campaign.campaign_id == generated.campaign_id &&
        campaign.git_commit == generated.git_commit &&
        campaign.julia_manifest_sha256 == generated.julia_manifest_sha256 &&
        campaign.julia_version == generated.julia_version &&
        campaign.algorithm == generated.algorithm &&
        campaign.observable_schema_version == generated.observable_schema_version || return false
    generated_tasks = collect(generated.tasks)
    length(campaign.tasks) == length(generated_tasks) || return false
    generated_canonical_task_string = _latest_binding(generator, :canonical_task_string)
    return all(canonical_task_string(task) ==
        Base.invokelatest(generated_canonical_task_string, generated_task)
        for (task, generated_task) in zip(campaign.tasks, generated_tasks))
end

function _same_resource_estimate(observed::AbstractDict, expected)
    Set(string.(keys(observed))) == Set(_FROZEN_RESOURCE_FIELDS) || return false
    for name in _FROZEN_RESOURCE_FIELDS
        name == "task_resources" && continue
        _resource_field(observed, name) == _resource_field(expected, name) || return false
    end
    observed_details = collect(observed["task_resources"])
    expected_details = collect(expected.task_resources)
    length(observed_details) == length(expected_details) || return false
    sort!(observed_details; by=detail -> String(_resource_field(detail, "task_id")))
    sort!(expected_details; by=detail -> String(_resource_field(detail, "task_id")))
    for (observed_detail, expected_detail) in zip(observed_details, expected_details)
        observed_detail isa AbstractDict &&
            Set(string.(keys(observed_detail))) == Set(_TASK_RESOURCE_FIELDS) || return false
        for name in _TASK_RESOURCE_FIELDS
            _resource_field(observed_detail, name) == _resource_field(expected_detail, name) || return false
        end
    end
    return true
end

function _recompute_resource_estimate(manifest_path::String, campaign, estimate::AbstractDict)
    parent = dirname(manifest_path)
    calibration_path = _portable_evidence_path(
        estimate["calibration_path"], parent, ".json")
    config_path = _portable_evidence_path(estimate["config_path"], parent, ".toml")
    for path in (calibration_path, config_path)
        islink(path) && throw(ArgumentError("resource_estimate"))
        isfile(path) || throw(ArgumentError("resource_estimate"))
    end
    calibration_bytes = read(calibration_path)
    config_bytes = read(config_path)
    bytes2hex(sha256(calibration_bytes)) == estimate["calibration_content_sha256"] &&
        bytes2hex(sha256(config_bytes)) == estimate["config_content_sha256"] ||
        throw(ArgumentError("resource_estimate"))

    generator = _manifest_generator()
    config = Base.invokelatest(_latest_binding(generator, :load_recon_config), config_path)
    calibration = Base.invokelatest(
        _latest_binding(generator, :read_calibration), calibration_path, config)
    generated = Base.invokelatest(
        _latest_binding(generator, :make_frozen_manifest), config, calibration)
    _same_frozen_manifest(campaign, generated, generator) ||
        throw(ArgumentError("resource_estimate"))
    expected = Base.invokelatest(
        _latest_binding(generator, :frozen_resource_estimate), config, calibration, generated;
        calibration_path=basename(calibration_path), config_path=basename(config_path),
        config_content_sha256=bytes2hex(sha256(config_bytes)))
    read(calibration_path) == calibration_bytes && read(config_path) == config_bytes ||
        throw(ArgumentError("resource_estimate"))
    return expected
end

function _audit_number(value, label::String; positive::Bool=false)
    value isa Real && !(value isa Bool) || throw(ArgumentError("$label must be numeric"))
    result = Float64(value)
    isfinite(result) && (!positive || result > 0) || throw(ArgumentError("$label is invalid"))
    return result
end

"""Audit only a frozen manifest and its sibling resource estimate before submission."""
function audit_frozen_manifest(manifest_path::AbstractString)
    errors = String[]
    try
        campaign = _read_campaign_manifest(manifest_path)
        length(campaign.tasks) == 528 || throw(ArgumentError("task_count"))
        foreach(Challenge148._validate_frozen_task, campaign.tasks)
        expected = Set{Tuple{Symbol,Int,Float64,Float64,Int}}()
        sizes = (8, 12, 16, 24, 32, 48, 64)
        thermal_sizes = (24, 48)
        h_old = Dict(:triangle => 4.76811, :honeycomb => 2.13250)
        for lattice in (:triangle, :honeycomb), L in sizes, x in (-0.6, 0.0, 0.6), replica in 1:8
            h = h_old[lattice] + x * L^-1.5868
            push!(expected, (lattice, L, h, 1.0, replica))
        end
        for lattice in (:triangle, :honeycomb), L in thermal_sizes, c in (1.5, 2.0),
            x in (-0.6, 0.0, 0.6), replica in 1:8
            h = h_old[lattice] + x * L^-1.5868
            push!(expected, (lattice, L, h, c, replica))
        end
        observed = Set((task.lattice, task.L, task.h, task.c, task.replica) for task in campaign.tasks)
        observed == expected || throw(ArgumentError("science_grid"))
        resource_path = _frozen_resource_path(abspath(manifest_path))
        islink(resource_path) && throw(ArgumentError("resource_estimate"))
        isfile(resource_path) || throw(ArgumentError("resource_estimate"))
        estimate = JSON.parsefile(resource_path; dicttype=Dict)
        estimate isa AbstractDict && Set(string.(keys(estimate))) == Set(_FROZEN_RESOURCE_FIELDS) ||
            throw(ArgumentError("resource_estimate"))
        _manifest_int(estimate["schema_version"], "resource schema") == 3 ||
            throw(ArgumentError("resource_estimate"))
        estimate["kind"] == "route_a_frozen_resource_estimate" && estimate["approved"] === true ||
            throw(ArgumentError("resource_estimate"))
        estimate["campaign_id"] == campaign.campaign_id &&
            estimate["campaign_checksum"] == campaign.campaign_checksum &&
            estimate["release_git_commit"] == campaign.git_commit &&
            estimate["release_julia_manifest_sha256"] == campaign.julia_manifest_sha256 &&
            estimate["release_julia_version"] == campaign.julia_version ||
            throw(ArgumentError("resource_estimate"))
        _manifest_int(estimate["task_count"], "resource task_count") == 528 ||
            throw(ArgumentError("task_count"))
        _sha256_token(estimate["calibration_content_sha256"]) ||
            throw(ArgumentError("resource_estimate"))
        _sha256_token(estimate["estimate_checksum"]) &&
            estimate["estimate_checksum"] == _resource_estimate_checksum(estimate) ||
            throw(ArgumentError("resource_estimate"))
        details = estimate["task_resources"]
        details isa AbstractVector && length(details) == 528 ||
            throw(ArgumentError("resource_estimate"))
        expected_tasks = Dict(task_id(task) => (hash=task_hash(task), task=task)
            for task in campaign.tasks)
        seen = Set{String}()
        detail_wall = Float64[]
        detail_memory = Float64[]
        detail_disk = Float64[]
        for detail in details
            detail isa AbstractDict && Set(string.(keys(detail))) == Set(_TASK_RESOURCE_FIELDS) ||
                throw(ArgumentError("resource_estimate"))
            id = detail["task_id"]
            hash = detail["task_hash"]
            id isa AbstractString && hash isa AbstractString && haskey(expected_tasks, id) &&
                expected_tasks[id].hash == hash && !(id in seen) ||
                throw(ArgumentError("resource_estimate"))
            push!(seen, String(id))
            push!(detail_wall, _audit_number(detail["predicted_wall_seconds"],
                "task wall"; positive=true))
            push!(detail_memory, _audit_number(detail["predicted_memory_bytes"],
                "task memory"; positive=true))
            push!(detail_disk, _audit_number(detail["predicted_disk_bytes"],
                "task disk"; positive=true))
        end
        seen == Set(keys(expected_tasks)) || throw(ArgumentError("resource_estimate"))
        cpu = _audit_number(estimate["predicted_cpu_seconds"], "predicted CPU"; positive=true)
        wall = _audit_number(estimate["max_task_wall_seconds"], "max wall"; positive=true)
        memory = _audit_number(estimate["max_task_memory_bytes"], "max memory"; positive=true)
        disk = _audit_number(estimate["predicted_disk_bytes"], "disk"; positive=true)
        isapprox(cpu, sum(detail_wall); rtol=1e-12, atol=0.0) &&
            isapprox(wall, maximum(detail_wall); rtol=1e-12, atol=0.0) &&
            isapprox(memory, maximum(detail_memory); rtol=1e-12, atol=0.0) &&
            isapprox(disk, sum(detail_disk); rtol=1e-12, atol=0.0) ||
            throw(ArgumentError("resource_estimate"))
        requested_wall = _audit_number(estimate["requested_walltime_seconds"], "requested wall"; positive=true)
        requested_memory = _audit_number(estimate["requested_memory_bytes"], "requested memory"; positive=true)
        requested_disk = _audit_number(estimate["requested_disk_bytes"], "requested disk"; positive=true)
        wall_limit = _audit_number(estimate["walltime_fraction_limit"], "wall limit"; positive=true)
        memory_limit = _audit_number(estimate["memory_fraction_limit"], "memory limit"; positive=true)
        disk_limit = _audit_number(estimate["disk_fraction_limit"], "disk limit"; positive=true)
        requested_wall == 86400.0 && requested_memory == 17179869184.0 &&
            requested_disk == 25000000000.0 && wall_limit == 0.70 &&
            memory_limit == 0.70 && disk_limit == 0.70 ||
            throw(ArgumentError("resource_estimate"))
        estimate["deployment_instruction"] ==
            "stage release_git_commit; copy frozen inputs separately without changing campaign provenance" ||
            throw(ArgumentError("resource_estimate"))
        expected_estimate = _recompute_resource_estimate(abspath(manifest_path), campaign, estimate)
        _same_resource_estimate(estimate, expected_estimate) ||
            throw(ArgumentError("resource_estimate"))
        all(value -> value <= wall_limit * requested_wall, detail_wall) || push!(errors, "walltime")
        all(value -> value <= memory_limit * requested_memory, detail_memory) || push!(errors, "memory")
        wall <= wall_limit * requested_wall || push!(errors, "walltime")
        memory <= memory_limit * requested_memory || push!(errors, "memory")
        disk <= disk_limit * requested_disk || push!(errors, "disk")
    catch error
        error isa InterruptException && rethrow()
        message = error isa ArgumentError ? error.msg : "manifest"
        gate = message in ("task_count", "science_grid", "resource_estimate", "provenance") ?
            message : "manifest"
        push!(errors, gate)
    end
    return (passed=isempty(errors), errors=sort!(unique!(errors)))
end

"""Parse exactly `--manifest PATH --results DIR --output DIR`."""
function parse_aggregate_args(arguments::Vector{String})
    if length(arguments) == 2 && arguments[1] == "--audit-manifest" && !isempty(arguments[2])
        return (audit_manifest_path=arguments[2],)
    end
    length(arguments) == 6 ||
        throw(ArgumentError("usage: aggregate_route_a.jl --manifest PATH --results DIR --output DIR"))
    arguments[1] == "--manifest" && arguments[3] == "--results" && arguments[5] == "--output" ||
        throw(ArgumentError("usage: aggregate_route_a.jl --manifest PATH --results DIR --output DIR"))
    all(!isempty, (arguments[2], arguments[4], arguments[6])) ||
        throw(ArgumentError("aggregate paths must be nonempty"))
    return (manifest_path=arguments[2], results_dir=arguments[4], output_dir=arguments[6])
end

function _main()
    arguments = parse_aggregate_args(copy(ARGS))
    if hasproperty(arguments, :audit_manifest_path)
        audit = audit_frozen_manifest(arguments.audit_manifest_path)
        audit.passed || throw(ArgumentError("frozen manifest audit failed: $(join(audit.errors, ","))"))
        return nothing
    end
    aggregate_campaign(arguments.manifest_path, arguments.results_dir, arguments.output_dir).passed ||
        throw(ArgumentError("campaign audit failed; see audit.json"))
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
