using JSON
using LinearAlgebra
using SHA
using Statistics
using TOML

include(joinpath(@__DIR__, "aggregate_route_a.jl"))

const _RECON_ROOT = normpath(joinpath(@__DIR__, ".."))
const _RECON_CONFIG_FIELDS = (
    "schema_version", "J", "sizes", "anchors", "yt_anchor", "replicas",
    "primary_c", "thermal_check_c", "thermal_check_sizes", "triangle_h_old",
    "honeycomb_h_old", "min_ess_per_replica", "min_ess_per_point",
    "max_predicted_sigma_stat_R", "walltime_fraction_limit", "memory_fraction_limit",
    "thermalization_sweeps", "candidate_measurement_sweeps", "base_bin_size",
    "checkpoint_interval_bins", "requested_walltime_seconds", "requested_memory_bytes",
    "requested_disk_bytes", "disk_fraction_limit", "smoke_thermalization_sweeps",
    "smoke_measurement_sweeps", "smoke_base_bin_size", "smoke_checkpoint_interval_bins",
    "benchmark_thermalization_sweeps", "benchmark_measurement_sweeps",
    "benchmark_base_bin_size", "benchmark_checkpoint_interval_bins",
    "benchmark_replicas", "burnin_prefix_sweeps", "burnin_compatibility_z",
    "benchmark_requested_walltime_seconds",
    "benchmark_requested_memory_bytes", "benchmark_requested_disk_bytes",
    "elapsed_relative_tolerance", "confidence_policy", "confidence_level",
)

struct ReconConfig
    schema_version::Int
    J::Float64
    sizes::Tuple{Vararg{Int}}
    anchors::Tuple{Vararg{Float64}}
    yt_anchor::Float64
    replicas::Int
    primary_c::Float64
    thermal_check_c::Tuple{Vararg{Float64}}
    thermal_check_sizes::Tuple{Vararg{Int}}
    h_old::NamedTuple{(:triangle, :honeycomb),Tuple{Float64,Float64}}
    min_ess_per_replica::Int
    min_ess_per_point::Int
    max_predicted_sigma_stat_R::Float64
    walltime_fraction_limit::Float64
    memory_fraction_limit::Float64
    thermalization_sweeps::Int
    candidate_measurement_sweeps::Int
    base_bin_size::Int
    checkpoint_interval_bins::Int
    requested_walltime_seconds::Float64
    requested_memory_bytes::Float64
    requested_disk_bytes::Float64
    disk_fraction_limit::Float64
    smoke_thermalization_sweeps::Int
    smoke_measurement_sweeps::Int
    smoke_base_bin_size::Int
    smoke_checkpoint_interval_bins::Int
    benchmark_thermalization_sweeps::Int
    benchmark_measurement_sweeps::Int
    benchmark_base_bin_size::Int
    benchmark_checkpoint_interval_bins::Int
    benchmark_replicas::Int
    burnin_prefix_sweeps::Tuple{Vararg{Int}}
    burnin_compatibility_z::Float64
    benchmark_requested_walltime_seconds::Float64
    benchmark_requested_memory_bytes::Float64
    benchmark_requested_disk_bytes::Float64
    elapsed_relative_tolerance::Float64
    confidence_policy::String
    confidence_level::Float64
end

struct CampaignManifest
    schema_version::Int
    kind::String
    campaign_id::String
    git_commit::String
    julia_manifest_sha256::String
    julia_version::String
    algorithm::String
    observable_schema_version::Int
    tasks::Tuple{Vararg{ClusterTask}}
end

const _CALIBRATION_FIELDS = (
    "schema_version", "kind", "builder_version", "sampling_unit", "campaign_id",
    "campaign_checksum", "campaign_manifest_sha256", "task_paths_sha256",
    "release_git_commit", "release_julia_manifest_sha256", "release_julia_version",
    "algorithm", "observable_schema_version", "bundle_script_sha256",
    "accounting_snapshot_filename", "accounting_snapshot_sha256",
    "wrapper_inventory_filename", "wrapper_inventory_sha256",
    "result_provenance_filename", "result_provenance_sha256", "resource_summary",
    "allocations", "records",
)
const _CALIBRATION_RECORD_FIELDS = (
    "calibration_key", "manifest_index", "allocation_key", "raw_slurm_job_id",
    "slurm_task_index", "task_id", "task_hash", "seed", "result_sha256",
    "completion_checksum",
    "release_git_commit", "release_julia_manifest_sha256", "release_julia_version", "algorithm",
    "observable_schema_version", "lattice", "L", "J", "h", "c", "anchor_x", "replica",
    "thermalization_sweeps", "measurement_sweeps", "base_bin_size",
    "energy_mean", "energy_stderr", "energy_first_half_mean", "energy_first_half_stderr",
    "energy_second_half_mean", "energy_second_half_stderr", "binder_mean", "binder_stderr",
    "binder_first_half_mean", "binder_first_half_stderr", "binder_second_half_mean",
    "binder_second_half_stderr", "binder_slope", "binder_slope_stderr", "tau_int_base_bins",
    "tau_int_stderr_base_bins", "binder_variance_per_base_bin",
    "binder_variance_stderr_per_base_bin", "cut_count_mean", "elapsed_seconds",
    "elapsed_per_sweep_seconds", "max_rss_upper_bytes",
    "nominal_requested_memory_per_chain_bytes", "result_bytes",
)
const _CALIBRATION_ALLOCATION_FIELDS = (
    "allocation_key", "raw_job_id", "array_task_id", "state", "exit_code", "alloc_cpus",
    "requested_memory_bytes", "requested_walltime_seconds", "elapsed_seconds",
    "max_rss_upper_bytes", "nominal_bundle_size", "bundle_size", "task_indices",
    "task_ids", "task_hashes", "wrapper_file", "wrapper_sha256",
    "completed_start_index", "completed_end_index", "canonical_accounting_rows",
)
const _CALIBRATION_RESOURCE_SUMMARY_FIELDS = (
    "memory_fit_sample_count", "chain_count", "max_rss_semantics",
)

"""One strict schema-4 chain-grain `calibration.json` record.

Task 12 writes one record for every task in `make_benchmark_manifest`.  Identity
and software fields bind the measurement to its Slurm job, immutable task, Git
release commit, release `Manifest.toml`, runtime, algorithm, and observable
schema. Every exact task stores full-chain and split-half energy/Binder means and
errors plus chain-local timing/disk evidence and an allocation memory link. The
generator derives thermalization from the
four independently seeded central-prefix levels; calibration never asserts a
required burn-in. The longest-prefix central tasks additionally store autocorrelation
and Binder variance diagnostics, while the 500-sweep three-anchor schedule stores
the Binder slope/error. Requested resources are retained once per allocation.

The c=1 records comprise all anchors at L=16,24,32 plus central L=48, exactly
matching the original Task 12 contract.  Freezing additionally requires all
anchors at L=16,24,32,48 for c=1.5 and c=2.0.  The latter are deliberately direct
calibrations: this generator never assumes that c=1 cost or autocorrelation is
valid for a longer imaginary-time extent.
"""
struct CalibrationAllocation
    allocation_key::String
    raw_job_id::String
    array_task_id::Int
    state::String
    exit_code::String
    alloc_cpus::Int
    requested_memory_bytes::Float64
    requested_walltime_seconds::Float64
    elapsed_seconds::Float64
    max_rss_upper_bytes::Float64
    nominal_bundle_size::Int
    bundle_size::Int
    task_indices::Tuple{Vararg{Int}}
    task_ids::Tuple{Vararg{String}}
    task_hashes::Tuple{Vararg{String}}
    wrapper_file::String
    wrapper_sha256::String
    completed_start_index::Int
    completed_end_index::Int
    canonical_accounting_rows::Tuple{Vararg{String}}
end

struct CalibrationRecord
    calibration_key::String
    manifest_index::Int
    allocation_key::String
    raw_slurm_job_id::String
    slurm_task_index::Int
    task_id::String
    task_hash::String
    seed::String
    result_sha256::String
    completion_checksum::String
    release_git_commit::String
    release_julia_manifest_sha256::String
    release_julia_version::String
    algorithm::String
    observable_schema_version::Int
    lattice::Symbol
    L::Int
    J::Float64
    h::Float64
    c::Float64
    anchor_x::Float64
    replica::Int
    thermalization_sweeps::Int
    measurement_sweeps::Int
    base_bin_size::Int
    energy_mean::Float64
    energy_stderr::Float64
    energy_first_half_mean::Float64
    energy_first_half_stderr::Float64
    energy_second_half_mean::Float64
    energy_second_half_stderr::Float64
    binder_mean::Float64
    binder_stderr::Float64
    binder_first_half_mean::Float64
    binder_first_half_stderr::Float64
    binder_second_half_mean::Float64
    binder_second_half_stderr::Float64
    binder_slope::Union{Nothing,Float64}
    binder_slope_stderr::Union{Nothing,Float64}
    tau_int_base_bins::Union{Nothing,Float64}
    tau_int_stderr_base_bins::Union{Nothing,Float64}
    binder_variance_per_base_bin::Union{Nothing,Float64}
    binder_variance_stderr_per_base_bin::Union{Nothing,Float64}
    cut_count_mean::Float64
    elapsed_seconds::Float64
    elapsed_per_sweep_seconds::Float64
    max_rss_upper_bytes::Float64
    nominal_requested_memory_per_chain_bytes::Float64
    result_bytes::Float64
end

struct CalibrationData
    schema_version::Int
    kind::String
    sampling_unit::String
    release_git_commit::String
    release_julia_manifest_sha256::String
    release_julia_version::String
    algorithm::String
    observable_schema_version::Int
    content_sha256::String
    campaign_id::String
    campaign_checksum::String
    campaign_manifest_sha256::String
    task_paths_sha256::String
    bundle_script_sha256::String
    accounting_snapshot_filename::String
    accounting_snapshot_sha256::String
    wrapper_inventory_filename::String
    wrapper_inventory_sha256::String
    result_provenance_filename::String
    result_provenance_sha256::String
    memory_fit_sample_count::Int
    allocations::Tuple{Vararg{CalibrationAllocation}}
    records::Tuple{Vararg{CalibrationRecord}}
end

struct FreezeRefusal <: Exception
    report::NamedTuple
end

Base.showerror(io::IO, error::FreezeRefusal) =
    print(io, "Route A frozen manifest refused: ", join(error.report.gates, ", "))

function _freeze_refusal(gates, details=String[])
    normalized = sort!(unique!(String.(collect(gates))))
    report = (
        schema_version=2,
        kind="route_a_freeze_refusal",
        approved=false,
        gates=Tuple(normalized),
        details=Tuple(sort!(String.(collect(details)))),
        recovery_path=nothing,
    )
    return FreezeRefusal(report)
end

_config_int(value, name) = value isa Integer && !(value isa Bool) ? Int(value) :
    throw(ArgumentError("$name must be an integer"))

function _config_float(value, name)
    value isa Real && !(value isa Bool) || throw(ArgumentError("$name must be numeric"))
    result = Float64(value)
    isfinite(result) || throw(ArgumentError("$name must be finite"))
    return result
end

function _positive_int(value, name; allow_zero::Bool=false)
    result = _config_int(value, name)
    (allow_zero ? result >= 0 : result > 0) || throw(ArgumentError("$name is out of range"))
    return result
end

function _positive_float(value, name)
    result = _config_float(value, name)
    result > 0 || throw(ArgumentError("$name must be positive"))
    return result
end

function _exact_scientific_config(config::ReconConfig)
    config.schema_version == 1 || throw(ArgumentError("unsupported reconnaissance config schema"))
    config.J == 1.0 || throw(ArgumentError("Route A requires J=1.0"))
    config.sizes == (8, 12, 16, 24, 32, 48, 64) || throw(ArgumentError("sizes are not approved"))
    config.anchors == (-0.6, 0.0, 0.6) || throw(ArgumentError("anchors are not approved"))
    config.yt_anchor == 1.5868 || throw(ArgumentError("anchor exponent is not approved"))
    config.replicas == 8 || throw(ArgumentError("Route A requires eight replicas"))
    config.primary_c == 1.0 || throw(ArgumentError("primary aspect ratio is not approved"))
    config.thermal_check_c == (1.5, 2.0) || throw(ArgumentError("thermal aspect ratios are not approved"))
    config.thermal_check_sizes == (24, 48) || throw(ArgumentError("thermal sizes are not approved"))
    config.h_old == (triangle=4.76811, honeycomb=2.13250) || throw(ArgumentError("old fields are not approved"))
    config.min_ess_per_replica == 100 || throw(ArgumentError("per-replica ESS gate is not approved"))
    config.min_ess_per_point == 1000 || throw(ArgumentError("point ESS gate is not approved"))
    config.max_predicted_sigma_stat_R == 2.0e-5 || throw(ArgumentError("ratio precision gate is not approved"))
    config.walltime_fraction_limit == 0.70 || throw(ArgumentError("walltime gate is not approved"))
    config.memory_fraction_limit == 0.70 || throw(ArgumentError("memory gate is not approved"))
    exact_controls = (
        config.thermalization_sweeps == 5000,
        config.candidate_measurement_sweeps == 10000,
        config.base_bin_size == 100,
        config.checkpoint_interval_bins == 10,
        config.requested_walltime_seconds == 86400.0,
        config.requested_memory_bytes == 17179869184.0,
        config.requested_disk_bytes == 25000000000.0,
        config.disk_fraction_limit == 0.70,
        config.smoke_thermalization_sweeps == 10,
        config.smoke_measurement_sweeps == 20,
        config.smoke_base_bin_size == 5,
        config.smoke_checkpoint_interval_bins == 1,
        config.benchmark_thermalization_sweeps == 500,
        config.benchmark_measurement_sweeps == 2000,
        config.benchmark_base_bin_size == 100,
        config.benchmark_checkpoint_interval_bins == 5,
        config.benchmark_replicas == 2,
        config.burnin_prefix_sweeps == (500, 2000, 5000, 10000),
        config.burnin_compatibility_z == 3.5,
        config.benchmark_requested_walltime_seconds == 14400.0,
        config.benchmark_requested_memory_bytes == 17179869184.0,
        config.benchmark_requested_disk_bytes == 25000000000.0,
        config.elapsed_relative_tolerance == 1.0e-6,
        config.confidence_policy == "student_t_two_sided_95",
        config.confidence_level == 0.95,
    )
    all(exact_controls) || throw(ArgumentError("execution, resource, and uncertainty controls are not approved"))
    return config
end

"""Read and strictly validate the exact approved Route A configuration."""
function load_recon_config(path::AbstractString=joinpath(_RECON_ROOT, "config", "route_a_recon.toml"))
    islink(path) && throw(ArgumentError("reconnaissance config must not be a symlink"))
    isfile(path) || throw(ArgumentError("reconnaissance config must be a regular file"))
    raw = TOML.parsefile(path)
    Set(keys(raw)) == Set(_RECON_CONFIG_FIELDS) ||
        throw(ArgumentError("reconnaissance config has missing or unknown fields"))
    integers(name) = _positive_int(raw[name], name)
    floats(name) = _positive_float(raw[name], name)
    config = ReconConfig(
        _config_int(raw["schema_version"], "schema_version"),
        _config_float(raw["J"], "J"),
        Tuple(_positive_int(value, "sizes") for value in raw["sizes"]),
        Tuple(_config_float(value, "anchors") for value in raw["anchors"]),
        floats("yt_anchor"), integers("replicas"), floats("primary_c"),
        Tuple(_positive_float(value, "thermal_check_c") for value in raw["thermal_check_c"]),
        Tuple(_positive_int(value, "thermal_check_sizes") for value in raw["thermal_check_sizes"]),
        (triangle=floats("triangle_h_old"), honeycomb=floats("honeycomb_h_old")),
        integers("min_ess_per_replica"), integers("min_ess_per_point"),
        floats("max_predicted_sigma_stat_R"), floats("walltime_fraction_limit"),
        floats("memory_fraction_limit"), integers("thermalization_sweeps"),
        integers("candidate_measurement_sweeps"), integers("base_bin_size"),
        integers("checkpoint_interval_bins"), floats("requested_walltime_seconds"),
        floats("requested_memory_bytes"), floats("requested_disk_bytes"),
        floats("disk_fraction_limit"), integers("smoke_thermalization_sweeps"),
        integers("smoke_measurement_sweeps"), integers("smoke_base_bin_size"),
        integers("smoke_checkpoint_interval_bins"), integers("benchmark_thermalization_sweeps"),
        integers("benchmark_measurement_sweeps"), integers("benchmark_base_bin_size"),
        integers("benchmark_checkpoint_interval_bins"), integers("benchmark_replicas"),
        Tuple(_positive_int(value, "burnin_prefix_sweeps") for value in raw["burnin_prefix_sweeps"]),
        floats("burnin_compatibility_z"),
        floats("benchmark_requested_walltime_seconds"),
        floats("benchmark_requested_memory_bytes"), floats("benchmark_requested_disk_bytes"),
        floats("elapsed_relative_tolerance"),
        _calibration_string(raw["confidence_policy"], "confidence_policy"),
        floats("confidence_level"),
    )
    for (measurement, bin, label) in (
        (config.candidate_measurement_sweeps, config.base_bin_size, "candidate"),
        (config.smoke_measurement_sweeps, config.smoke_base_bin_size, "smoke"),
        (config.benchmark_measurement_sweeps, config.benchmark_base_bin_size, "benchmark"),
    )
        measurement % bin == 0 || throw(ArgumentError("$label measurement sweeps must be a base-bin multiple"))
    end
    all(limit -> 0 < limit <= 1, (config.walltime_fraction_limit, config.memory_fraction_limit, config.disk_fraction_limit)) ||
        throw(ArgumentError("resource fraction limits must lie in (0,1]"))
    return _exact_scientific_config(config)
end

function _provenance_manifest(campaign_id::String, tasks::Vector{ClusterTask})
    return CampaignManifest(
        _CAMPAIGN_MANIFEST_SCHEMA_VERSION,
        _CAMPAIGN_MANIFEST_KIND,
        campaign_id,
        _git_commit(),
        _manifest_hash(),
        string(VERSION),
        "continuous_time_cluster",
        _RAW_BIN_SCHEMA_VERSION,
        Tuple(tasks),
    )
end

_field(config::ReconConfig, lattice::Symbol, L::Int, anchor::Float64) =
    config.h_old[lattice] + anchor * L^-config.yt_anchor

function _task(
    config::ReconConfig, lattice::Symbol, L::Int, anchor::Float64, c::Float64,
    replica::Int, thermalization::Int, measurement::Int, bin::Int, checkpoint::Int,
)
    h = _field(config, lattice, L, anchor)
    seed = task_seed(:route_a, lattice, L, h, c, replica)
    placeholder = ClusterTask(
        config.schema_version, lattice, L, config.J, h, c, replica, seed,
        thermalization, measurement, bin, checkpoint, "placeholder.json")
    output = task_id(placeholder) * ".json"
    return validate_task(ClusterTask(
        config.schema_version, lattice, L, config.J, h, c, replica, seed,
        thermalization, measurement, bin, checkpoint, output))
end

function _candidate_tasks(config::ReconConfig; measurement_sweeps::Int=config.candidate_measurement_sweeps)
    tasks = ClusterTask[]
    for lattice in (:triangle, :honeycomb), L in config.sizes, anchor in config.anchors,
        replica in 1:config.replicas
        push!(tasks, _task(config, lattice, L, anchor, config.primary_c, replica,
            config.thermalization_sweeps, measurement_sweeps, config.base_bin_size,
            config.checkpoint_interval_bins))
    end
    for lattice in (:triangle, :honeycomb), L in config.thermal_check_sizes,
        c in config.thermal_check_c, anchor in config.anchors, replica in 1:config.replicas
        push!(tasks, _task(config, lattice, L, anchor, c, replica,
            config.thermalization_sweeps, measurement_sweeps, config.base_bin_size,
            config.checkpoint_interval_bins))
    end
    sort!(tasks; by=task_id)
    return tasks
end

"""Build the deterministic, unfrozen 528-chain science candidate without production data."""
make_candidate_manifest(config::ReconConfig=load_recon_config()) =
    _provenance_manifest("route-a-candidate-v1", _candidate_tasks(config))

"""Build the deterministic four-chain local/remote smoke schedule."""
function make_smoke_manifest(config::ReconConfig=load_recon_config())
    tasks = ClusterTask[]
    for (lattice, L) in ((:triangle, 3), (:honeycomb, 2)), replica in 1:2
        push!(tasks, _task(config, lattice, L, 0.0, config.primary_c, replica,
            config.smoke_thermalization_sweeps, config.smoke_measurement_sweeps,
            config.smoke_base_bin_size, config.smoke_checkpoint_interval_bins))
    end
    sort!(tasks; by=task_id)
    return _provenance_manifest("route-a-smoke-v1", tasks)
end

"""Build Task 12's c=1 schedule plus mandatory c=1.5/2 calibration groups.

The extra thermal-aspect groups are intentional: autocorrelation and cost at
`c=1` are not a scientifically defensible calibration for the longer imaginary-
time extents.  A frozen manifest therefore requires direct calibration of them.
"""
function make_benchmark_manifest(config::ReconConfig=load_recon_config())
    tasks = ClusterTask[]
    for lattice in (:triangle, :honeycomb), L in (16, 24, 32), anchor in config.anchors,
        replica in 1:config.benchmark_replicas
        push!(tasks, _task(config, lattice, L, anchor, config.primary_c, replica,
            config.benchmark_thermalization_sweeps, config.benchmark_measurement_sweeps,
            config.benchmark_base_bin_size, config.benchmark_checkpoint_interval_bins))
    end
    for lattice in (:triangle, :honeycomb), replica in 1:config.benchmark_replicas
        push!(tasks, _task(config, lattice, 48, 0.0, config.primary_c, replica,
            config.benchmark_thermalization_sweeps, config.benchmark_measurement_sweeps,
            config.benchmark_base_bin_size, config.benchmark_checkpoint_interval_bins))
    end
    for lattice in (:triangle, :honeycomb), L in (16, 24, 32, 48),
        c in config.thermal_check_c, anchor in config.anchors, replica in 1:config.benchmark_replicas
        push!(tasks, _task(config, lattice, L, anchor, c, replica,
            config.benchmark_thermalization_sweeps, config.benchmark_measurement_sweeps,
            config.benchmark_base_bin_size, config.benchmark_checkpoint_interval_bins))
    end
    # Thermalization is audited from four independently seeded retained-prefix
    # jobs at every production c=1 size and at every modeled longer-c size.
    # Replica IDs are disjoint across prefix levels, so no seed is reused.
    for lattice in (:triangle, :honeycomb), c in (config.primary_c, config.thermal_check_c...),
        L in (c == config.primary_c ? config.sizes : (16, 24, 32, 48)),
        (level_index, thermalization) in enumerate(config.burnin_prefix_sweeps),
        local_replica in 1:config.benchmark_replicas
        replica = (level_index - 1) * config.benchmark_replicas + local_replica
        task = _task(config, lattice, L, 0.0, c, replica,
            thermalization, config.benchmark_measurement_sweeps,
            config.benchmark_base_bin_size, config.benchmark_checkpoint_interval_bins)
        any(existing -> task_id(existing) == task_id(task), tasks) || push!(tasks, task)
    end
    sort!(tasks; by=task_id)
    return _provenance_manifest("route-a-benchmark-v1", tasks)
end

function _calibration_string(value, name::String)
    value isa AbstractString && !isempty(value) || throw(_freeze_refusal(("provenance",), ["$name is invalid"]))
    return String(value)
end

function _calibration_number(value, name::String; positive::Bool=false, nonnegative::Bool=false)
    value isa Real && !(value isa Bool) || throw(_freeze_refusal(("missing_resource",), ["$name is not numeric"]))
    result = Float64(value)
    isfinite(result) || throw(_freeze_refusal(("nonfinite_fit",), ["$name is nonfinite"]))
    positive && result <= 0 && throw(_freeze_refusal(("missing_resource",), ["$name must be positive"]))
    nonnegative && result < 0 && throw(_freeze_refusal(("missing_resource",), ["$name must be nonnegative"]))
    return result
end

function _optional_calibration_number(value, name::String; positive::Bool=false, nonnegative::Bool=false)
    value === nothing && return nothing
    return _calibration_number(value, name; positive, nonnegative)
end

function _optional_calibration_bool(value, name::String)
    value === nothing && return nothing
    value isa Bool || throw(_freeze_refusal(("thermalization",), ["$name must be boolean or null"]))
    return value
end

function _calibration_record(value, index::Int)
    value isa AbstractDict || throw(_freeze_refusal(("provenance",), ["record $index is not an object"]))
    Set(string.(keys(value))) == Set(_CALIBRATION_RECORD_FIELDS) ||
        throw(_freeze_refusal(("provenance",), ["record $index has missing or unknown fields"]))
    lattice_name = _calibration_string(value["lattice"], "record $index lattice")
    lattice = Symbol(lattice_name)
    lattice in (:triangle, :honeycomb) ||
        throw(_freeze_refusal(("provenance",), ["record $index lattice is unsupported"]))
    integer(name; allow_zero=false) = try
        _positive_int(value[name], "record $index $name"; allow_zero)
    catch error
        throw(_freeze_refusal(("provenance",), [sprint(showerror, error)]))
    end
    number(name; positive=false, nonnegative=false) =
        _calibration_number(value[name], "record $index $name"; positive, nonnegative)
    optional(name; positive=false, nonnegative=false) =
        _optional_calibration_number(value[name], "record $index $name"; positive, nonnegative)
    return CalibrationRecord(
        _calibration_string(value["calibration_key"], "record $index calibration_key"),
        integer("manifest_index"; allow_zero=true),
        _calibration_string(value["allocation_key"], "record $index allocation_key"),
        _calibration_string(value["raw_slurm_job_id"], "record $index raw_slurm_job_id"),
        integer("slurm_task_index"; allow_zero=true),
        _calibration_string(value["task_id"], "record $index task_id"),
        _calibration_string(value["task_hash"], "record $index task_hash"),
        _calibration_string(value["seed"], "record $index seed"),
        _calibration_string(value["result_sha256"], "record $index result_sha256"),
        _calibration_string(value["completion_checksum"], "record $index completion_checksum"),
        _calibration_string(value["release_git_commit"], "record $index release_git_commit"),
        _calibration_string(value["release_julia_manifest_sha256"], "record $index release_julia_manifest_sha256"),
        _calibration_string(value["release_julia_version"], "record $index release_julia_version"),
        _calibration_string(value["algorithm"], "record $index algorithm"),
        integer("observable_schema_version"), lattice, integer("L"), number("J"), number("h"),
        number("c"; positive=true), number("anchor_x"), integer("replica"),
        integer("thermalization_sweeps"), integer("measurement_sweeps"), integer("base_bin_size"),
        number("energy_mean"), number("energy_stderr"; nonnegative=true),
        number("energy_first_half_mean"), number("energy_first_half_stderr"; nonnegative=true),
        number("energy_second_half_mean"), number("energy_second_half_stderr"; nonnegative=true),
        number("binder_mean"), number("binder_stderr"; nonnegative=true),
        number("binder_first_half_mean"), number("binder_first_half_stderr"; nonnegative=true),
        number("binder_second_half_mean"), number("binder_second_half_stderr"; nonnegative=true),
        optional("binder_slope"),
        optional("binder_slope_stderr"; nonnegative=true), optional("tau_int_base_bins"; positive=true),
        optional("tau_int_stderr_base_bins"; nonnegative=true),
        optional("binder_variance_per_base_bin"; positive=true),
        optional("binder_variance_stderr_per_base_bin"; nonnegative=true),
        number("cut_count_mean"; nonnegative=true), number("elapsed_seconds"; positive=true),
        number("elapsed_per_sweep_seconds"; positive=true),
        number("max_rss_upper_bytes"; positive=true),
        number("nominal_requested_memory_per_chain_bytes"; positive=true),
        number("result_bytes"; positive=true),
    )
end

function _calibration_allocation(value, index::Int)
    value isa AbstractDict || throw(_freeze_refusal(("provenance",), ["allocation $index is not an object"]))
    Set(string.(keys(value))) == Set(_CALIBRATION_ALLOCATION_FIELDS) ||
        throw(_freeze_refusal(("provenance",), ["allocation $index has missing or unknown fields"]))
    integer(name; allow_zero=false) = try
        _positive_int(value[name], "allocation $index $name"; allow_zero)
    catch error
        throw(_freeze_refusal(("provenance",), [sprint(showerror, error)]))
    end
    numbers(name; positive=false) =
        _calibration_number(value[name], "allocation $index $name"; positive)
    function integer_tuple(name; allow_zero=false)
        raw = value[name]
        raw isa AbstractVector || throw(_freeze_refusal(("provenance",), ["allocation $index $name must be an array"]))
        return Tuple(begin
            try
                _positive_int(item, "allocation $index $name"; allow_zero)
            catch error
                throw(_freeze_refusal(("provenance",), [sprint(showerror, error)]))
            end
        end for item in raw)
    end
    function string_tuple(name)
        raw = value[name]
        raw isa AbstractVector || throw(_freeze_refusal(("provenance",), ["allocation $index $name must be an array"]))
        return Tuple(_calibration_string(item, "allocation $index $name") for item in raw)
    end
    return CalibrationAllocation(
        _calibration_string(value["allocation_key"], "allocation $index allocation_key"),
        _calibration_string(value["raw_job_id"], "allocation $index raw_job_id"),
        integer("array_task_id"; allow_zero=true),
        _calibration_string(value["state"], "allocation $index state"),
        _calibration_string(value["exit_code"], "allocation $index exit_code"),
        integer("alloc_cpus"), numbers("requested_memory_bytes"; positive=true),
        numbers("requested_walltime_seconds"; positive=true),
        numbers("elapsed_seconds"; positive=true), numbers("max_rss_upper_bytes"; positive=true),
        integer("nominal_bundle_size"), integer("bundle_size"),
        integer_tuple("task_indices"; allow_zero=true), string_tuple("task_ids"),
        string_tuple("task_hashes"),
        _calibration_string(value["wrapper_file"], "allocation $index wrapper_file"),
        _calibration_string(value["wrapper_sha256"], "allocation $index wrapper_sha256"),
        integer("completed_start_index"; allow_zero=true),
        integer("completed_end_index"; allow_zero=true),
        string_tuple("canonical_accounting_rows"),
    )
end

function _calibration_task_key(record::CalibrationRecord)
    return (record.lattice, record.L, record.h, record.c, record.replica)
end

function _release_commit_exists(commit::String)
    return _commit_token(commit) &&
        _git_read(_RECON_ROOT, "cat-file", "-e", commit * "^{commit}") !== nothing
end

function _release_manifest_hash(commit::String)
    manifest = _git_read(_RECON_ROOT, "show", commit * ":Manifest.toml")
    return manifest === nothing ? nothing : bytes2hex(sha256(codeunits(manifest)))
end

const _STUDENT_T_975 = (
    12.7062047364, 4.30265272975, 3.18244630528, 2.7764451052,
    2.57058183564, 2.44691185114, 2.36462425101, 2.3060041352,
    2.26215716285, 2.22813885196, 2.20098516008, 2.17881282966,
    2.16036865646, 2.14478668792, 2.13144954556, 2.11990529922,
    2.10981557783, 2.10092204024, 2.09302405441, 2.08596344727,
    2.07961384473, 2.0738730679, 2.06865761042, 2.06389856163,
    2.05953855275, 2.05552943864, 2.05183051648, 2.0484071418,
    2.04522964213, 2.0422724563,
)

function _student_t_critical(dof::Int)
    dof > 0 || throw(_freeze_refusal(("ill_conditioned_fit",), ["fit has no residual degrees of freedom"]))
    return dof <= length(_STUDENT_T_975) ? _STUDENT_T_975[dof] : 1.95996398454
end

function _compatibility_z(first::Float64, first_error::Float64,
    second::Float64, second_error::Float64)
    denominator = hypot(first_error, second_error)
    denominator > 0 && return abs(first - second) / denominator
    return first == second ? 0.0 : Inf
end

function _pooled_observable(records, getter, error_getter)
    values = Float64.(getter.(records))
    errors = Float64.(error_getter.(records))
    empirical = length(values) > 1 ? std(values) / sqrt(length(values)) : 0.0
    declared = sqrt(sum(abs2, errors)) / length(errors)
    return (mean(values), hypot(empirical, declared))
end

function _split_halves_pass(record::CalibrationRecord, config::ReconConfig)
    energy_z = _compatibility_z(record.energy_first_half_mean,
        record.energy_first_half_stderr, record.energy_second_half_mean,
        record.energy_second_half_stderr)
    binder_z = _compatibility_z(record.binder_first_half_mean,
        record.binder_first_half_stderr, record.binder_second_half_mean,
        record.binder_second_half_stderr)
    return energy_z <= config.burnin_compatibility_z &&
        binder_z <= config.burnin_compatibility_z
end

"""Derive the first stable observed prefix for every modeled central group."""
function _derived_burnin_by_group(records, config::ReconConfig)
    result = Dict{Tuple{Symbol,Float64,Int},Float64}()
    modeled = Tuple{Symbol,Float64,Int}[]
    for lattice in (:triangle, :honeycomb), c in (config.primary_c, config.thermal_check_c...),
        L in (c == config.primary_c ? config.sizes : (16, 24, 32, 48))
        push!(modeled, (lattice, c, L))
    end
    for (lattice, c, L) in modeled
        group = filter(record -> record.lattice == lattice && record.c == c &&
            record.L == L && record.anchor_x == 0.0, records)
        length(group) == length(config.burnin_prefix_sweeps) * config.benchmark_replicas ||
            throw(_freeze_refusal(("thermalization",), ["missing burn-in prefix tasks for $lattice L=$L c=$c"]))
        levels = sort!(unique(getfield.(group, :thermalization_sweeps)))
        Tuple(levels) == config.burnin_prefix_sweeps ||
            throw(_freeze_refusal(("thermalization",), ["burn-in levels are not exact for $lattice L=$L c=$c"]))
        for (level_index, level) in enumerate(levels)
            level_records = filter(record -> record.thermalization_sweeps == level, group)
            expected_replicas = Set(((level_index - 1) * config.benchmark_replicas + 1):
                (level_index * config.benchmark_replicas))
            length(level_records) == config.benchmark_replicas &&
                Set(getfield.(level_records, :replica)) == expected_replicas ||
                throw(_freeze_refusal(("thermalization",), ["burn-in replicas are not exact for $lattice L=$L c=$c prefix=$level"]))
        end
        reference = filter(record -> record.thermalization_sweeps == levels[end], group)
        reference_energy = _pooled_observable(reference,
            record -> record.energy_mean, record -> record.energy_stderr)
        reference_binder = _pooled_observable(reference,
            record -> record.binder_mean, record -> record.binder_stderr)
        passes = Bool[]
        for level in levels
            level_records = filter(record -> record.thermalization_sweeps == level, group)
            energy = _pooled_observable(level_records,
                record -> record.energy_mean, record -> record.energy_stderr)
            binder = _pooled_observable(level_records,
                record -> record.binder_mean, record -> record.binder_stderr)
            push!(passes,
                _compatibility_z(energy..., reference_energy...) <= config.burnin_compatibility_z &&
                _compatibility_z(binder..., reference_binder...) <= config.burnin_compatibility_z &&
                all(record -> _split_halves_pass(record, config), level_records))
        end
        any(i -> passes[i] && any(!, passes[(i + 1):end]), 1:(length(passes) - 1)) &&
            throw(_freeze_refusal(("thermalization",), ["later burn-in prefix is inconsistent for $lattice L=$L c=$c"]))
        accepted = findfirst(i -> i < length(levels) && all(passes[i:end]), eachindex(levels))
        accepted === nothing && throw(_freeze_refusal(("thermalization",),
            ["longest burn-in prefix lacks a stable earlier prefix for $lattice L=$L c=$c"]))
        result[(lattice, c, L)] = Float64(levels[accepted])
    end
    return result
end

function _validate_calibration_contract(calibration::CalibrationData, config::ReconConfig)
    gates = String[]
    details = String[]
    expected_manifest = make_benchmark_manifest(config)
    expected_tasks = collect(expected_manifest.tasks)
    expected = Dict(
        (task.lattice, task.L, task.h, task.c, task.replica) => task
        for task in expected_tasks)
    records = collect(calibration.records)
    calibration_keys = getfield.(records, :calibration_key)
    length(unique(calibration_keys)) == length(calibration_keys) || push!(gates, "duplicate_calibration_key")
    length(records) == length(expected_tasks) || push!(gates, "calibration_task_count")
    task_ids = getfield.(records, :task_id)
    task_hashes = getfield.(records, :task_hash)
    length(unique(task_ids)) == length(task_ids) || push!(gates, "duplicate_calibration_task")
    length(unique(task_hashes)) == length(task_hashes) || push!(gates, "duplicate_calibration_task")
    expected_provenance = (
        calibration.release_git_commit, calibration.release_julia_manifest_sha256,
        calibration.release_julia_version,
        calibration.algorithm, calibration.observable_schema_version)
    calibration.sampling_unit == "base_bin" || push!(gates, "sampling_unit")
    calibration.campaign_id == "benchmark-5c3e1a4868c36f8e" || push!(gates, "provenance")
    calibration.campaign_checksum == _campaign_checksum(
        calibration.campaign_id, calibration.release_git_commit,
        calibration.release_julia_manifest_sha256, calibration.release_julia_version,
        calibration.algorithm, calibration.observable_schema_version, expected_tasks) ||
        push!(gates, "provenance")
    _verify_release_snapshot(calibration.release_git_commit,
        calibration.release_julia_manifest_sha256; root=_RECON_ROOT) || push!(gates, "provenance")
    calibration.release_julia_version == string(VERSION) &&
        calibration.algorithm == "continuous_time_cluster" &&
        calibration.observable_schema_version == _RAW_BIN_SCHEMA_VERSION || begin
        push!(gates, "provenance")
        push!(details, "calibration release runtime, algorithm, or schema is incompatible")
    end
    observed = Set{Tuple{Symbol,Int,Float64,Float64,Int}}()
    expected_order = sort(expected_tasks; by=task_id)
    expected_index = Dict(task_id(task) => index - 1 for (index, task) in enumerate(expected_order))
    allocations = collect(calibration.allocations)
    allocation_keys = getfield.(allocations, :allocation_key)
    length(unique(allocation_keys)) == length(allocation_keys) || push!(gates, "slurm_id")
    calibration.memory_fit_sample_count == length(allocations) || push!(gates, "requested_resource")
    allocation_by_key = Dict(allocation.allocation_key => allocation for allocation in allocations)
    assigned_indices = Int[]
    slurm_pairs = Set{Tuple{String,Int}}()
    for allocation in allocations
        occursin(r"^[0-9]+$", allocation.raw_job_id) || push!(gates, "slurm_id")
        allocation.allocation_key == "$(allocation.raw_job_id)_$(allocation.array_task_id)" ||
            push!(gates, "slurm_id")
        pair = (allocation.raw_job_id, allocation.array_task_id)
        pair in slurm_pairs && push!(gates, "slurm_id")
        push!(slurm_pairs, pair)
        allocation.state == "COMPLETED" && allocation.exit_code == "0:0" ||
            push!(gates, "slurm_id")
        allocation.bundle_size == length(allocation.task_indices) == length(allocation.task_ids) ==
            length(allocation.task_hashes) || push!(gates, "array_index")
        allocation.bundle_size <= allocation.nominal_bundle_size &&
            allocation.alloc_cpus >= allocation.bundle_size || push!(gates, "requested_resource")
        allocation.completed_start_index <= allocation.completed_end_index &&
            allocation.task_indices == Tuple(allocation.completed_start_index:allocation.completed_end_index) ||
            push!(gates, "array_index")
        allocation.wrapper_file == basename(allocation.wrapper_file) &&
            _sha256_token(allocation.wrapper_sha256) || push!(gates, "provenance")
        length(allocation.canonical_accounting_rows) == 2 || push!(gates, "provenance")
        allocation.requested_memory_bytes / allocation.bundle_size > 0 ||
            push!(gates, "requested_resource")
        for (position, task_index) in enumerate(allocation.task_indices)
            if 0 <= task_index < length(expected_order)
                task = expected_order[task_index + 1]
                allocation.task_ids[position] == task_id(task) &&
                    allocation.task_hashes[position] == task_hash(task) || push!(gates, "provenance")
            else
                push!(gates, "array_index")
            end
            push!(assigned_indices, task_index)
        end
    end
    sort(assigned_indices) == collect(0:(length(expected_order) - 1)) || push!(gates, "array_index")
    for (record_index, record) in enumerate(records)
        provenance = (
            record.release_git_commit, record.release_julia_manifest_sha256,
            record.release_julia_version,
            record.algorithm, record.observable_schema_version)
        provenance == expected_provenance || begin
            push!(gates, "provenance")
            push!(details, "record $(record.calibration_key) provenance mismatch")
        end
        key = _calibration_task_key(record)
        task = get(expected, key, nothing)
        if task === nothing
            push!(gates, "provenance")
            push!(details, "record $(record.calibration_key) is not an approved benchmark task")
        else
            record.task_id == task_id(task) && record.task_hash == task_hash(task) || begin
                push!(gates, "provenance")
                push!(details, "record $(record.calibration_key) task identity mismatch")
            end
            record.thermalization_sweeps == task.thermalization_sweeps &&
                record.measurement_sweeps == task.measurement_sweeps &&
                record.base_bin_size == task.base_bin_size && record.J == task.J &&
                record.seed == "u64:" * string(task.seed; base=16, pad=16) || begin
                push!(gates, "provenance")
                push!(details, "record $(record.calibration_key) sweep provenance mismatch")
            end
        end
        index_for_task = get(expected_index, record.task_id, -1)
        record.manifest_index == index_for_task && record.slurm_task_index == index_for_task ||
            push!(gates, "array_index")
        allocation = get(allocation_by_key, record.allocation_key, nothing)
        if allocation === nothing
            push!(gates, "slurm_id")
        else
            record.raw_slurm_job_id == allocation.raw_job_id || push!(gates, "slurm_id")
            record.manifest_index in allocation.task_indices || push!(gates, "array_index")
            record.max_rss_upper_bytes == allocation.max_rss_upper_bytes ||
                push!(gates, "requested_resource")
            record.nominal_requested_memory_per_chain_bytes ==
                allocation.requested_memory_bytes / allocation.bundle_size ||
                push!(gates, "requested_resource")
        end
        _sha256_token(record.task_hash) && _sha256_token(record.result_sha256) &&
            _sha256_token(record.completion_checksum) || push!(gates, "provenance")
        expected_elapsed = record.elapsed_per_sweep_seconds *
            (record.thermalization_sweeps + record.measurement_sweeps)
        abs(record.elapsed_seconds - expected_elapsed) <=
            config.elapsed_relative_tolerance * max(expected_elapsed, eps(Float64)) || push!(gates, "timing")
        push!(observed, key)
        central = record.anchor_x == 0.0
        exact_anchor = record.h == config.h_old[record.lattice] + record.anchor_x * record.L^-config.yt_anchor &&
            record.anchor_x in config.anchors
        exact_anchor || begin
            push!(gates, "provenance")
            push!(details, "record $(record.calibration_key) field anchor mismatch")
        end
        if central
            slope_required = record.thermalization_sweeps == first(config.burnin_prefix_sweeps) &&
                record.replica <= config.benchmark_replicas &&
                !(record.c == config.primary_c && record.L == 48)
            reference = record.thermalization_sweeps == last(config.burnin_prefix_sweeps)
            slope_required && record.binder_slope === nothing && push!(gates, "missing_slope")
            slope_required && record.binder_slope_stderr === nothing && push!(gates, "missing_slope")
            !slope_required && (record.binder_slope !== nothing || record.binder_slope_stderr !== nothing) &&
                push!(gates, "provenance")
            reference && record.tau_int_base_bins === nothing && push!(gates, "missing_tau")
            reference && record.tau_int_stderr_base_bins === nothing && push!(gates, "missing_tau")
            reference && record.binder_variance_per_base_bin === nothing && push!(gates, "missing_tau")
            reference && record.binder_variance_stderr_per_base_bin === nothing && push!(gates, "uncertainty")
            !reference && (record.tau_int_base_bins !== nothing ||
                record.tau_int_stderr_base_bins !== nothing ||
                record.binder_variance_per_base_bin !== nothing ||
                record.binder_variance_stderr_per_base_bin !== nothing) && push!(gates, "provenance")
        elseif record.binder_slope !== nothing || record.binder_slope_stderr !== nothing ||
            record.tau_int_base_bins !== nothing || record.tau_int_stderr_base_bins !== nothing ||
            record.binder_variance_per_base_bin !== nothing ||
            record.binder_variance_stderr_per_base_bin !== nothing
            push!(gates, "provenance")
            push!(details, "noncentral record $(record.calibration_key) must not claim central diagnostics")
        end
    end
    missing = setdiff(Set(Base.keys(expected)), observed)
    for (lattice, L, h, c, replica) in missing
        h == config.h_old[lattice] && push!(gates, "thermalization")
        matching_group = filter(record -> record.lattice == lattice && record.L == L && record.c == c, records)
        if isempty(matching_group)
            push!(gates, "missing_calibration_group")
        else
            push!(gates, "insufficient_three_anchors")
        end
    end
    # Every slope group must contain all three anchors and both benchmark replicas.
    for lattice in (:triangle, :honeycomb), c in (config.primary_c, config.thermal_check_c...),
        L in (c == config.primary_c ? (16, 24, 32) : (16, 24, 32, 48))
        group = filter(record -> record.lattice == lattice && record.L == L && record.c == c &&
            record.thermalization_sweeps == first(config.burnin_prefix_sweeps) &&
            record.replica <= config.benchmark_replicas, records)
        Set(getfield.(group, :anchor_x)) == Set(config.anchors) || push!(gates, "insufficient_three_anchors")
        all(count(record -> record.replica == replica, group) == 3 for replica in 1:config.benchmark_replicas) ||
            push!(gates, "insufficient_three_anchors")
        for replica in 1:config.benchmark_replicas
            replica_group = sort!(filter(record -> record.replica == replica, group); by=record -> record.h)
            length(replica_group) == 3 || continue
            h = getfield.(replica_group, :h)
            binder = getfield.(replica_group, :binder_mean)
            centered_h = h .- mean(h)
            derived_slope = dot(centered_h, binder .- mean(binder)) / dot(centered_h, centered_h)
            central = only(filter(record -> record.anchor_x == 0.0, replica_group))
            if central.binder_slope !== nothing && central.binder_slope_stderr !== nothing
                tolerance = _student_t_critical(1) * max(central.binder_slope_stderr, eps(Float64))
                abs(derived_slope - central.binder_slope) <= tolerance || begin
                    push!(gates, "provenance")
                    push!(details, "stored Binder slope disagrees with three anchors for $lattice L=$L c=$c replica=$replica")
                end
            end
        end
    end
    isempty(gates) || throw(_freeze_refusal(gates, details))
    _derived_burnin_by_group(records, config)
    return calibration
end

"""Read strict schema-4 allocation- and chain-grain benchmark evidence."""
function read_calibration(path::AbstractString, config::ReconConfig=load_recon_config())
    islink(path) && throw(_freeze_refusal(("provenance",), ["calibration must not be a symlink"]))
    isfile(path) || throw(_freeze_refusal(("missing_calibration_group",), ["calibration file is absent"]))
    calibration_bytes = read(path)
    calibration_content_sha256 = bytes2hex(sha256(calibration_bytes))
    raw = try
        JSON.parse(String(calibration_bytes); dicttype=Dict)
    catch error
        throw(_freeze_refusal(("provenance",), ["calibration JSON is invalid: $(sprint(showerror, error))"]))
    end
    raw isa AbstractDict && Set(string.(keys(raw))) == Set(_CALIBRATION_FIELDS) ||
        throw(_freeze_refusal(("provenance",), ["calibration has missing or unknown fields"]))
    records_raw = raw["records"]
    records_raw isa AbstractVector || throw(_freeze_refusal(("missing_calibration_group",), ["records must be an array"]))
    allocations_raw = raw["allocations"]
    allocations_raw isa AbstractVector || throw(_freeze_refusal(("missing_resource",), ["allocations must be an array"]))
    summary = raw["resource_summary"]
    summary isa AbstractDict && Set(string.(keys(summary))) == Set(_CALIBRATION_RESOURCE_SUMMARY_FIELDS) ||
        throw(_freeze_refusal(("provenance",), ["resource_summary has missing or unknown fields"]))
    integer = try
        _positive_int(raw["schema_version"], "calibration schema_version")
    catch error
        throw(_freeze_refusal(("provenance",), [sprint(showerror, error)]))
    end
    observable = try
        _positive_int(raw["observable_schema_version"], "calibration observable_schema_version")
    catch error
        throw(_freeze_refusal(("provenance",), [sprint(showerror, error)]))
    end
    summary_count = try
        _positive_int(summary["memory_fit_sample_count"], "resource_summary memory_fit_sample_count")
    catch error
        throw(_freeze_refusal(("provenance",), [sprint(showerror, error)]))
    end
    chain_count = try
        _positive_int(summary["chain_count"], "resource_summary chain_count")
    catch error
        throw(_freeze_refusal(("provenance",), [sprint(showerror, error)]))
    end
    summary["max_rss_semantics"] == "allocation_batch_upper_bound_per_chain" ||
        throw(_freeze_refusal(("provenance",), ["unsupported MaxRSS semantics"]))
    for name in ("campaign_checksum", "campaign_manifest_sha256", "task_paths_sha256",
        "release_julia_manifest_sha256", "bundle_script_sha256", "accounting_snapshot_sha256",
        "wrapper_inventory_sha256", "result_provenance_sha256")
        value = raw[name]
        value isa AbstractString && _sha256_token(value) ||
            throw(_freeze_refusal(("provenance",), ["calibration $name is not a SHA-256"]))
    end
    for (name, suffix) in (("accounting_snapshot_filename", ".psv"),
        ("wrapper_inventory_filename", ".psv"), ("result_provenance_filename", ".psv"))
        value = raw[name]
        value isa AbstractString && basename(value) == value && endswith(value, suffix) ||
            throw(_freeze_refusal(("provenance",), ["calibration $name is not a portable PSV basename"]))
    end
    raw["accounting_snapshot_filename"] == "sacct.psv" &&
        raw["wrapper_inventory_filename"] == "wrapper_inventory.psv" &&
        raw["result_provenance_filename"] == "result_provenance.psv" ||
        throw(_freeze_refusal(("provenance",), ["calibration evidence filenames are incompatible"]))
    calibration = CalibrationData(
        integer,
        _calibration_string(raw["kind"], "calibration kind"),
        _calibration_string(raw["sampling_unit"], "calibration sampling_unit"),
        _calibration_string(raw["release_git_commit"], "calibration release_git_commit"),
        _calibration_string(raw["release_julia_manifest_sha256"], "calibration release_julia_manifest_sha256"),
        _calibration_string(raw["release_julia_version"], "calibration release_julia_version"),
        _calibration_string(raw["algorithm"], "calibration algorithm"),
        observable,
        calibration_content_sha256,
        _calibration_string(raw["campaign_id"], "calibration campaign_id"),
        String(raw["campaign_checksum"]), String(raw["campaign_manifest_sha256"]),
        String(raw["task_paths_sha256"]), String(raw["bundle_script_sha256"]),
        String(raw["accounting_snapshot_filename"]), String(raw["accounting_snapshot_sha256"]),
        String(raw["wrapper_inventory_filename"]), String(raw["wrapper_inventory_sha256"]),
        String(raw["result_provenance_filename"]), String(raw["result_provenance_sha256"]),
        summary_count,
        Tuple(_calibration_allocation(value, index) for (index, value) in enumerate(allocations_raw)),
        Tuple(_calibration_record(value, index) for (index, value) in enumerate(records_raw)),
    )
    calibration.schema_version == 4 && calibration.kind == "route_a_calibration" &&
        raw["builder_version"] == "route-a-calibration-builder-v1" ||
        throw(_freeze_refusal(("provenance",), ["unsupported calibration schema or kind"]))
    chain_count == length(calibration.records) ||
        throw(_freeze_refusal(("provenance",), ["resource_summary chain_count mismatch"]))
    return _validate_calibration_contract(calibration, config)
end

struct _LogScalingFit
    intercept::Float64
    exponent::Float64
    residual_variance::Float64
    inverse_normal::Matrix{Float64}
    coefficient_measurement_covariance::Matrix{Float64}
    individual_scatter_log_variance::Float64
    new_observation_log_variance::Float64
    dof::Int
end

function _log_scaling_fit(L_values, y_values, y_stderr, label::String;
    individual_scatter_log_variance::Float64=0.0,
    new_observation_log_variance::Union{Nothing,Float64}=nothing)
    length(L_values) == length(y_values) == length(y_stderr) && length(L_values) >= 3 ||
        throw(_freeze_refusal(("ill_conditioned_fit",), ["$label needs at least three unique L values"]))
    length(unique(L_values)) == length(L_values) ||
        throw(_freeze_refusal(("ill_conditioned_fit",), ["$label repeated L values were not collapsed"]))
    all(value -> isfinite(value), y_values) ||
        throw(_freeze_refusal(("nonfinite_fit",), ["$label contains nonfinite values"]))
    all(>(0), y_values) ||
        throw(_freeze_refusal(("ill_conditioned_fit",), ["$label contains nonpositive values"]))
    all(value -> isfinite(value) && value >= 0, y_stderr) ||
        throw(_freeze_refusal(("uncertainty",), ["$label contains invalid standard errors"]))
    X = hcat(ones(length(L_values)), log.(Float64.(L_values)))
    normal = transpose(X) * X
    rank(X) == 2 && isfinite(cond(normal)) && cond(normal) < 1e12 ||
        throw(_freeze_refusal(("ill_conditioned_fit",), ["$label log-L design is ill-conditioned"]))
    response = log.(Float64.(y_values))
    relative_variances = (Float64.(y_stderr) ./ Float64.(y_values)).^2
    positive_variances = filter(>(0), relative_variances)
    if isempty(positive_variances)
        coefficients = X \ response
        coefficient_measurement_covariance = zeros(2, 2)
    else
        variance_floor = minimum(positive_variances) * 1e-12
        weights = 1.0 ./ max.(relative_variances, variance_floor)
        weighted_normal = transpose(X) * Diagonal(weights) * X
        rank(weighted_normal) == 2 && isfinite(cond(weighted_normal)) && cond(weighted_normal) < 1e14 ||
            throw(_freeze_refusal(("ill_conditioned_fit",), ["$label weighted design is ill-conditioned"]))
        coefficient_measurement_covariance = inv(weighted_normal)
        coefficients = weighted_normal \ (transpose(X) * Diagonal(weights) * response)
    end
    maximum(response) - minimum(response) <= 128eps(Float64) * max(1.0, maximum(abs, response)) &&
        (coefficients = [mean(response), 0.0])
    residuals = response - X * coefficients
    dof = length(response) - 2
    variance = sum(abs2, residuals) / dof
    variance <= 128eps(Float64) * max(1.0, sum(abs2, response)) && (variance = 0.0)
    observation_variance = new_observation_log_variance === nothing ?
        maximum(relative_variances) : new_observation_log_variance
    all(isfinite, coefficients) && isfinite(variance) && variance >= 0 ||
        throw(_freeze_refusal(("nonfinite_fit",), ["$label fit is nonfinite"]))
    all(isfinite, coefficient_measurement_covariance) &&
        isfinite(individual_scatter_log_variance) && individual_scatter_log_variance >= 0 &&
        isfinite(observation_variance) && observation_variance >= 0 ||
        throw(_freeze_refusal(("uncertainty",), ["$label uncertainty is nonfinite"]))
    return _LogScalingFit(coefficients[1], coefficients[2], variance, inv(normal),
        coefficient_measurement_covariance, individual_scatter_log_variance,
        observation_variance, dof)
end

function _prediction_log_variance(fit::_LogScalingFit, L::Int, prediction::Symbol)
    prediction in (:mean, :individual) || throw(ArgumentError("prediction must be mean or individual"))
    x = [1.0, log(Float64(L))]
    coefficient_variance = dot(x, fit.coefficient_measurement_covariance * x) +
        fit.residual_variance * dot(x, fit.inverse_normal * x)
    prediction_variance = coefficient_variance
    if prediction === :individual
        prediction_variance += fit.residual_variance +
            fit.individual_scatter_log_variance + fit.new_observation_log_variance
    end
    isfinite(prediction_variance) && prediction_variance >= 0 ||
        throw(_freeze_refusal(("nonfinite_fit",), ["prediction variance is invalid"]))
    return prediction_variance
end

function _predict_log_bound(fit::_LogScalingFit, L::Int, direction::Int;
    prediction::Symbol=:individual)
    x = [1.0, log(Float64(L))]
    prediction_variance = _prediction_log_variance(fit, L, prediction)
    critical = _student_t_critical(fit.dof)
    value = exp(fit.intercept + fit.exponent * x[2] +
        direction * critical * sqrt(prediction_variance))
    isfinite(value) && value > 0 || throw(_freeze_refusal(
        fit.new_observation_log_variance > 0 ? ("uncertainty",) : ("nonfinite_fit",),
        ["prediction is invalid"]))
    return value
end

function _records(calibration::CalibrationData, lattice::Symbol, c::Float64)
    return filter(record -> record.lattice == lattice && record.c == c, collect(calibration.records))
end

function _collapsed_metric(records, getter, stderr_getter, label::String)
    sizes = Int[]
    means = Float64[]
    errors = Float64[]
    individual_scatter = Float64[]
    observation_variance = Float64[]
    for size in sort!(unique(getfield.(records, :L)))
        group = filter(record -> record.L == size, records)
        values = getter.(group)
        stderrs = stderr_getter.(group)
        any(isnothing, values) && throw(_freeze_refusal(("missing_tau",), ["$label is missing"]))
        any(isnothing, stderrs) && throw(_freeze_refusal(("uncertainty",), ["$label uncertainty is missing"]))
        normalized_values = Float64.(values)
        normalized_stderrs = Float64.(stderrs)
        mean_value = mean(normalized_values)
        empirical = length(normalized_values) > 1 ? std(normalized_values) / sqrt(length(normalized_values)) : 0.0
        declared = sqrt(sum(abs2, normalized_stderrs)) / length(normalized_stderrs)
        push!(sizes, size)
        push!(means, mean_value)
        push!(errors, hypot(empirical, declared))
        push!(individual_scatter, length(normalized_values) > 1 ? var(log.(normalized_values)) : 0.0)
        push!(observation_variance,
            maximum((normalized_stderrs ./ normalized_values).^2))
    end
    return sizes, means, errors, individual_scatter, observation_variance
end

function _metric_bound(calibration::CalibrationData, lattice::Symbol, L::Int, c::Float64,
    getter, stderr_getter, label::String, direction::Int; central::Bool=false)
    records = _records(calibration, lattice, c)
    central && (records = filter(record -> record.anchor_x == 0.0, records))
    records = filter(record -> getter(record) !== nothing, records)
    sizes, values, stderrs, scatter, observation =
        _collapsed_metric(records, getter, stderr_getter, label)
    fit = _log_scaling_fit(sizes, values, stderrs, label;
        individual_scatter_log_variance=maximum(scatter),
        new_observation_log_variance=maximum(observation))
    return _predict_log_bound(fit, L, direction; prediction=:individual)
end

"""Conservative upper prediction of integrated autocorrelation for one science group."""
predict_tau_upper(calibration::CalibrationData, lattice::Symbol, L::Int, c::Float64,
    config::ReconConfig=load_recon_config()) =
    _metric_bound(calibration, lattice, L, c,
        record -> record.tau_int_base_bins, record -> record.tau_int_stderr_base_bins,
        "tau(base bins) $(lattice) c=$c", 1; central=true)

function predict_burnin_upper(calibration::CalibrationData, lattice::Symbol, L::Int, c::Float64,
    config::ReconConfig=load_recon_config())
    derived = _derived_burnin_by_group(collect(calibration.records), config)
    points = sort!([(size, value) for ((point_lattice, point_c, size), value) in derived
        if point_lattice == lattice && point_c == c]; by=first)
    sizes = first.(points)
    values = last.(points)
    !isempty(sizes) && minimum(sizes) <= L <= maximum(sizes) ||
        throw(_freeze_refusal(("thermalization",),
            ["burn-in extrapolation is unsupported for $lattice L=$L c=$c"]))
    fit = _log_scaling_fit(sizes, values, zeros(length(values)),
        "derived burnin(sweeps) $(lattice) c=$c")
    prediction = _predict_log_bound(fit, L, 1)
    nearest_sweep = round(prediction)
    return abs(prediction - nearest_sweep) <= 1e-10 * max(1.0, prediction) ?
        nearest_sweep : prediction
end

function _slope_lower(calibration::CalibrationData, lattice::Symbol, L::Int, c::Float64, config::ReconConfig)
    records = filter(record -> record.anchor_x == 0.0 && record.binder_slope !== nothing,
        _records(calibration, lattice, c))
    sizes, values, stderrs, scatter, observation = _collapsed_metric(records,
        record -> abs(record.binder_slope), record -> record.binder_slope_stderr,
        "Binder slope $(lattice) c=$c")
    return _predict_log_bound(
        _log_scaling_fit(sizes, values, stderrs, "Binder slope $(lattice) c=$c";
            individual_scatter_log_variance=maximum(scatter),
            new_observation_log_variance=maximum(observation)), L, -1; prediction=:mean)
end

function _minimum_measurement_sweeps(tau_upper::Float64, config::ReconConfig)
    required_bins = max(
        2tau_upper * config.min_ess_per_replica,
        2tau_upper * config.min_ess_per_point / config.replicas,
    )
    isfinite(required_bins) && required_bins <= typemax(Int) / config.base_bin_size ||
        throw(_freeze_refusal(("uncertainty",), ["tau uncertainty requires unrepresentable sweep count"]))
    return max(config.base_bin_size, ceil(Int, required_bins) * config.base_bin_size)
end

function _frozen_tasks(config::ReconConfig, calibration::CalibrationData)
    measurements = Dict{Tuple{Symbol,Int,Float64},Int}()
    thermalizations = Dict{Tuple{Symbol,Int,Float64},Int}()
    for lattice in (:triangle, :honeycomb), L in config.sizes
        tau = predict_tau_upper(calibration, lattice, L, config.primary_c, config)
        measurements[(lattice, L, config.primary_c)] = _minimum_measurement_sweeps(tau, config)
        burnin = predict_burnin_upper(calibration, lattice, L, config.primary_c, config)
        isfinite(burnin) && burnin <= typemax(Int) ||
            throw(_freeze_refusal(("thermalization",), ["predicted burnin is unrepresentable"]))
        thermalizations[(lattice, L, config.primary_c)] = max(config.thermalization_sweeps, ceil(Int, burnin))
    end
    for lattice in (:triangle, :honeycomb), L in config.thermal_check_sizes, c in config.thermal_check_c
        tau = predict_tau_upper(calibration, lattice, L, c, config)
        measurements[(lattice, L, c)] = _minimum_measurement_sweeps(tau, config)
        burnin = predict_burnin_upper(calibration, lattice, L, c, config)
        isfinite(burnin) && burnin <= typemax(Int) ||
            throw(_freeze_refusal(("thermalization",), ["predicted burnin is unrepresentable"]))
        thermalizations[(lattice, L, c)] = max(config.thermalization_sweeps, ceil(Int, burnin))
    end
    tasks = ClusterTask[]
    for lattice in (:triangle, :honeycomb), L in config.sizes, anchor in config.anchors,
        replica in 1:config.replicas
        push!(tasks, _task(config, lattice, L, anchor, config.primary_c, replica,
            thermalizations[(lattice, L, config.primary_c)], measurements[(lattice, L, config.primary_c)],
            config.base_bin_size, config.checkpoint_interval_bins))
    end
    for lattice in (:triangle, :honeycomb), L in config.thermal_check_sizes,
        c in config.thermal_check_c, anchor in config.anchors, replica in 1:config.replicas
        push!(tasks, _task(config, lattice, L, anchor, c, replica,
            thermalizations[(lattice, L, c)], measurements[(lattice, L, c)],
            config.base_bin_size, config.checkpoint_interval_bins))
    end
    sort!(tasks; by=task_id)
    return tasks
end

function _allocation_memory_samples(calibration::CalibrationData, lattice::Symbol, c::Float64)
    records = _records(calibration, lattice, c)
    allocation_by_key = Dict(allocation.allocation_key => allocation
        for allocation in calibration.allocations)
    samples = NamedTuple[]
    for size in sort!(unique(getfield.(records, :L)))
        keys = sort!(collect(unique(
            record.allocation_key for record in records if record.L == size)))
        push!(samples, (
            L=size,
            allocation_keys=Tuple(keys),
            values=Tuple(allocation_by_key[key].max_rss_upper_bytes for key in keys),
        ))
    end
    return samples
end

function _resource_upper(calibration::CalibrationData, task::ClusterTask,
    config::ReconConfig, metric::Symbol)
    if metric === :time
        getter = record -> record.elapsed_per_sweep_seconds
        label = "elapsed per sweep"
    elseif metric === :memory
        samples = _allocation_memory_samples(calibration, task.lattice, task.c)
        sizes = Int[]
        means = Float64[]
        errors = Float64[]
        scatter = Float64[]
        for sample in samples
            size = sample.L
            values = collect(sample.values)
            isempty(values) && throw(_freeze_refusal(("missing_resource",),
                ["allocation MaxRSS is missing for $(task.lattice) L=$size c=$(task.c)"]))
            push!(sizes, size)
            push!(means, mean(values))
            push!(errors, length(values) > 1 ? std(values) / sqrt(length(values)) : 0.0)
            push!(scatter, length(values) > 1 ? var(log.(values)) : 0.0)
        end
        fit = _log_scaling_fit(sizes, means, errors,
            "allocation MaxRSS $(task.lattice) c=$(task.c)";
            individual_scatter_log_variance=maximum(scatter),
            new_observation_log_variance=maximum(scatter))
        return _predict_log_bound(fit, task.L, 1; prediction=:individual)
    elseif metric === :disk
        getter = record -> record.result_bytes / record.measurement_sweeps
        label = "result bytes per sweep"
    else
        throw(ArgumentError("unknown resource metric"))
    end
    return _metric_bound(calibration, task.lattice, task.L, task.c, getter,
        _ -> 0.0, "$label $(task.lattice) c=$(task.c)", 1)
end

function _assess_frozen(config::ReconConfig, calibration::CalibrationData, tasks::Vector{ClusterTask})
    gates = String[]
    details = String[]
    sigma_h = Dict{Tuple{Symbol,Int},Float64}()
    for lattice in (:triangle, :honeycomb), L in config.sizes
        c = config.primary_c
        group_task = only(filter(task -> task.lattice == lattice && task.L == L && task.c == c &&
            task.replica == 1 && task.h == config.h_old[lattice], tasks))
        tau = predict_tau_upper(calibration, lattice, L, c, config)
        variance = _metric_bound(calibration, lattice, L, c,
            record -> record.binder_variance_per_base_bin,
            record -> record.binder_variance_stderr_per_base_bin,
            "Binder variance per base bin $(lattice) c=$c", 1; central=true)
        slope = _slope_lower(calibration, lattice, L, c, config)
        n_bins = group_task.measurement_sweeps / group_task.base_bin_size
        sigma_h[(lattice, L)] = sqrt(variance * 2tau /
            (n_bins * config.replicas)) / slope
    end
    for L in config.sizes
        ht = config.h_old.triangle
        hh = config.h_old.honeycomb
        sigma_ratio = hypot(sigma_h[(:triangle, L)] / hh,
            ht * sigma_h[(:honeycomb, L)] / hh^2)
        if !isfinite(sigma_ratio) || sigma_ratio > config.max_predicted_sigma_stat_R
            push!(gates, "sigma_stat_R")
            push!(details, "L=$L predicted sigma_stat(R)=$sigma_ratio")
        end
    end
    predicted_disk = 0.0
    predicted_cpu_seconds = 0.0
    max_task_wall_seconds = 0.0
    max_task_memory_bytes = 0.0
    task_resources = NamedTuple[]
    for task in tasks
        tau = predict_tau_upper(calibration, task.lattice, task.L, task.c, config)
        n_bins = task.measurement_sweeps / task.base_bin_size
        n_bins / (2tau) >= config.min_ess_per_replica || push!(gates, "ess_per_replica")
        config.replicas * n_bins / (2tau) >= config.min_ess_per_point ||
            push!(gates, "ess_per_point")
        time = _resource_upper(calibration, task, config, :time) *
            (task.thermalization_sweeps + task.measurement_sweeps)
        memory = _resource_upper(calibration, task, config, :memory)
        disk = _resource_upper(calibration, task, config, :disk) * task.measurement_sweeps
        predicted_disk += disk
        predicted_cpu_seconds += time
        max_task_wall_seconds = max(max_task_wall_seconds, time)
        max_task_memory_bytes = max(max_task_memory_bytes, memory)
        push!(task_resources, (
            task_id=task_id(task), task_hash=task_hash(task),
            predicted_wall_seconds=time, predicted_memory_bytes=memory,
            predicted_disk_bytes=disk,
        ))
        time <= config.walltime_fraction_limit * config.requested_walltime_seconds || push!(gates, "walltime")
        memory <= config.memory_fraction_limit * config.requested_memory_bytes || push!(gates, "memory")
    end
    predicted_disk <= config.disk_fraction_limit * config.requested_disk_bytes || push!(gates, "disk")
    isempty(gates) || throw(_freeze_refusal(gates, details))
    return (
        predicted_cpu_seconds=predicted_cpu_seconds,
        max_task_wall_seconds=max_task_wall_seconds,
        max_task_memory_bytes=max_task_memory_bytes,
        predicted_disk_bytes=predicted_disk,
        task_resources=sort!(task_resources; by=detail -> detail.task_id),
    )
end

"""Build a calibration-approved immutable frozen campaign or throw `FreezeRefusal`.

The campaign provenance is the exact benchmark release recorded by Task 12,
not the generator's current checkout. Deployment must stage that release commit;
later tasks may copy the frozen manifest and task inputs as evidence, but must
not replace the embedded production provenance with their own commits.
"""
function make_frozen_manifest(config::ReconConfig, calibration::CalibrationData)
    _validate_calibration_contract(calibration, config)
    tasks = _frozen_tasks(config, calibration)
    _assess_frozen(config, calibration, tasks)
    return CampaignManifest(
        _CAMPAIGN_MANIFEST_SCHEMA_VERSION, _CAMPAIGN_MANIFEST_KIND, "route-a-frozen-v1",
        calibration.release_git_commit, calibration.release_julia_manifest_sha256,
        calibration.release_julia_version, calibration.algorithm,
        calibration.observable_schema_version, Tuple(tasks))
end

function frozen_resource_estimate(config::ReconConfig, calibration::CalibrationData,
    manifest::CampaignManifest; calibration_path::AbstractString,
    config_path::AbstractString, config_content_sha256::AbstractString)
    calibration_name = String(calibration_path)
    config_name = String(config_path)
    basename(calibration_name) == calibration_name && endswith(calibration_name, ".json") ||
        throw(ArgumentError("calibration evidence path must be a JSON basename"))
    basename(config_name) == config_name && endswith(config_name, ".toml") ||
        throw(ArgumentError("config evidence path must be a TOML basename"))
    config_hash = String(config_content_sha256)
    _sha256_token(config_hash) || throw(ArgumentError("config evidence hash must be a SHA-256"))
    tasks = collect(manifest.tasks)
    assessment = _assess_frozen(config, calibration, tasks)
    checksum = _campaign_checksum(
        manifest.campaign_id, manifest.git_commit, manifest.julia_manifest_sha256,
        manifest.julia_version, manifest.algorithm, manifest.observable_schema_version, tasks)
    payload = (
        schema_version=3,
        kind="route_a_frozen_resource_estimate",
        approved=true,
        calibration_path=calibration_name,
        calibration_content_sha256=calibration.content_sha256,
        config_path=config_name,
        config_content_sha256=config_hash,
        campaign_id=manifest.campaign_id,
        campaign_checksum=checksum,
        release_git_commit=manifest.git_commit,
        release_julia_manifest_sha256=manifest.julia_manifest_sha256,
        release_julia_version=manifest.julia_version,
        task_count=length(tasks),
        predicted_cpu_seconds=assessment.predicted_cpu_seconds,
        max_task_wall_seconds=assessment.max_task_wall_seconds,
        max_task_memory_bytes=assessment.max_task_memory_bytes,
        predicted_disk_bytes=assessment.predicted_disk_bytes,
        requested_walltime_seconds=config.requested_walltime_seconds,
        requested_memory_bytes=config.requested_memory_bytes,
        requested_disk_bytes=config.requested_disk_bytes,
        walltime_fraction_limit=config.walltime_fraction_limit,
        memory_fraction_limit=config.memory_fraction_limit,
        disk_fraction_limit=config.disk_fraction_limit,
        task_resources=assessment.task_resources,
        deployment_instruction="stage release_git_commit; copy frozen inputs separately without changing campaign provenance",
    )
    return merge(payload, (estimate_checksum=_resource_estimate_checksum(payload),))
end

function _validate_manifest(manifest::CampaignManifest)
    manifest.schema_version == _CAMPAIGN_MANIFEST_SCHEMA_VERSION ||
        throw(ArgumentError("campaign manifest schema is incompatible with Task 8"))
    manifest.kind == _CAMPAIGN_MANIFEST_KIND ||
        throw(ArgumentError("campaign manifest kind is incompatible with Task 8"))
    _verify_release_snapshot(manifest.git_commit, manifest.julia_manifest_sha256;
        root=_RECON_ROOT) || throw(ArgumentError("campaign release snapshot is unavailable or not runnable"))
    manifest.julia_version == string(VERSION) || throw(ArgumentError("campaign runtime is not current"))
    manifest.algorithm == "continuous_time_cluster" || throw(ArgumentError("unsupported campaign algorithm"))
    manifest.observable_schema_version == _RAW_BIN_SCHEMA_VERSION ||
        throw(ArgumentError("unsupported campaign observable schema"))
    tasks = collect(manifest.tasks)
    isempty(tasks) && throw(ArgumentError("campaign has no tasks"))
    foreach(validate_task, tasks)
    ids = task_id.(tasks)
    hashes = task_hash.(tasks)
    seeds = getfield.(tasks, :seed)
    outputs = getfield.(tasks, :output_path)
    length(unique(ids)) == length(ids) || throw(ArgumentError("campaign has duplicate task IDs"))
    length(unique(hashes)) == length(hashes) || throw(ArgumentError("campaign has duplicate task hashes"))
    length(unique(seeds)) == length(seeds) || throw(ArgumentError("campaign has duplicate task seeds"))
    length(unique(outputs)) == length(outputs) || throw(ArgumentError("campaign has duplicate result basenames"))
    all(output -> basename(output) == output && endswith(output, ".json"), outputs) ||
        throw(ArgumentError("campaign result paths must be JSON basenames"))
    issorted(ids) || throw(ArgumentError("campaign tasks must be sorted by task ID"))
    return tasks
end

function _regular_unaliased_or_absent(path::String, label::String)
    islink(path) && throw(ArgumentError("$label must not be a symlink: $path"))
    if ispath(path)
        isfile(path) || throw(ArgumentError("$label must be absent or a regular file: $path"))
        stat(path).nlink == 1 || throw(ArgumentError("$label must not be a hard-link alias: $path"))
    end
    return path
end

function _safe_existing_task_directory(path::String)
    islink(path) && throw(ArgumentError("task directory must not be a symlink: $path"))
    if ispath(path)
        isdir(path) || throw(ArgumentError("task directory must be absent or a directory: $path"))
        for name in readdir(path)
            occupant = joinpath(path, name)
            islink(occupant) && throw(ArgumentError("task directory contains a symlink: $name"))
            isfile(occupant) || throw(ArgumentError("task directory contains a nonregular occupant: $name"))
            stat(occupant).nlink == 1 || throw(ArgumentError("task directory contains a hard-link alias: $name"))
        end
    end
    return path
end

function _task_directory_for(path::String)
    stem, extension = splitext(basename(path))
    extension == ".json" || throw(ArgumentError("campaign output must have a .json extension"))
    !isempty(stem) || throw(ArgumentError("campaign output stem must be nonempty"))
    return joinpath(dirname(path), stem * "-tasks")
end

function _unique_stage_path(parent::String, prefix::String)
    for nonce in 0:10_000
        path = joinpath(parent, ".$prefix.$(getpid()).$nonce")
        !ispath(path) && !islink(path) && return path
    end
    throw(ArgumentError("could not allocate a staging path"))
end

function _write_task_stage(stage::String, final_dir::String, tasks::Vector{ClusterTask})
    mkdir(stage)
    lines = String[]
    for task in tasks
        name = task_id(task) * ".json"
        write_task(joinpath(stage, name), task)
        push!(lines, name)
    end
    open(joinpath(stage, "task_paths.txt"), "w") do io
        for line in lines
            write(io, line, '\n')
        end
        flush(io)
    end
    return stage
end

"""Atomically install a Task 8 campaign manifest and its immutable task bundle."""
function write_manifest_bundle(path::AbstractString, manifest::CampaignManifest)
    tasks = _validate_manifest(manifest)
    output = abspath(path)
    parent = dirname(output)
    isdir(parent) && !islink(parent) || throw(ArgumentError("campaign parent must be a real directory"))
    task_dir = _task_directory_for(output)
    _regular_unaliased_or_absent(output, "campaign output")
    _safe_existing_task_directory(task_dir)
    manifest_stage = _unique_stage_path(parent, basename(output) * ".stage")
    task_stage = _unique_stage_path(parent, basename(task_dir) * ".stage")
    manifest_backup = _unique_stage_path(parent, basename(output) * ".backup")
    task_backup = _unique_stage_path(parent, basename(task_dir) * ".backup")
    installed_manifest = false
    installed_tasks = false
    backed_manifest = false
    backed_tasks = false
    try
        _write_task_stage(task_stage, task_dir, tasks)
        write_campaign_manifest(
            manifest_stage, manifest.campaign_id, manifest.git_commit,
            manifest.julia_manifest_sha256, tasks;
            julia_version=manifest.julia_version, algorithm=manifest.algorithm,
            observable_schema_version=manifest.observable_schema_version)
        if ispath(output)
            mv(output, manifest_backup)
            backed_manifest = true
        end
        if ispath(task_dir)
            mv(task_dir, task_backup)
            backed_tasks = true
        end
        mv(task_stage, task_dir)
        installed_tasks = true
        mv(manifest_stage, output)
        installed_manifest = true
        backed_manifest && rm(manifest_backup)
        backed_tasks && rm(task_backup; recursive=true)
        return String(path)
    catch
        installed_manifest && isfile(output) && rm(output)
        installed_tasks && isdir(task_dir) && rm(task_dir; recursive=true)
        backed_manifest && isfile(manifest_backup) && mv(manifest_backup, output)
        backed_tasks && isdir(task_backup) && mv(task_backup, task_dir)
        rethrow()
    finally
        isfile(manifest_stage) && rm(manifest_stage)
        isdir(task_stage) && rm(task_stage; recursive=true)
    end
end

function _refusal_path(output::String)
    stem, extension = splitext(output)
    extension == ".json" || throw(ArgumentError("campaign output must have a .json extension"))
    return stem * "-refusal.json"
end

function _resource_estimate_path(output::String)
    stem, extension = splitext(output)
    extension == ".json" || throw(ArgumentError("campaign output must have a .json extension"))
    if endswith(stem, "_recon_manifest")
        return stem[1:end-length("_recon_manifest")] * "_resource_estimate.json"
    elseif endswith(stem, "_manifest")
        return stem[1:end-length("_manifest")] * "_resource_estimate.json"
    end
    return stem * "-resource-estimate.json"
end

function _atomic_write_bytes(path::String, bytes::Vector{UInt8})
    _regular_unaliased_or_absent(path, "evidence snapshot")
    stage = _unique_stage_path(dirname(path), basename(path) * ".stage")
    promoted = false
    try
        open(stage, "w") do io
            write(io, bytes)
            flush(io)
        end
        mv(stage, path; force=true)
        promoted = true
        return path
    finally
        !promoted && isfile(stage) && rm(stage)
    end
end

function _canonical_output_with_parent(path::AbstractString)
    absolute = abspath(path)
    parent = dirname(absolute)
    mkpath(parent)
    islink(parent) && throw(ArgumentError("campaign output parent must not be a symlink"))
    return joinpath(realpath(parent), basename(absolute))
end

function _paths_alias(first_path::AbstractString, second_path::AbstractString)
    normpath(abspath(first_path)) == normpath(abspath(second_path)) && return true
    if isfile(first_path) && isfile(second_path)
        first_stat = stat(first_path)
        second_stat = stat(second_path)
        return (first_stat.device, first_stat.inode) == (second_stat.device, second_stat.inode)
    end
    return false
end

function _preflight_frozen_paths(config_path::AbstractString, calibration_path::AbstractString,
    output::String, refusal::String, estimate::String, evidence)
    for (input, label) in ((config_path, "config"), (calibration_path, "calibration"))
        islink(input) && throw(_freeze_refusal(("path_alias",), ["$label input must not be a symlink"]))
        for destination in (output, refusal, estimate, evidence.calibration_path,
            evidence.config_path, _task_directory_for(output))
            _paths_alias(input, destination) &&
                throw(_freeze_refusal(("path_alias",), ["$label input aliases a frozen output"]))
        end
    end
    return nothing
end

function _recovery_path(output::String)
    stem, _ = splitext(basename(output))
    return joinpath(dirname(output), "." * stem * "-recovery")
end

function _remove_safe_or_recover(path::String, recovery::String, label::String)
    (ispath(path) || islink(path)) || return nothing
    if islink(path) || isfile(path)
        rm(path)
        return nothing
    end
    if isdir(path)
        safe = try
            _safe_existing_task_directory(path)
            true
        catch
            false
        end
        if safe
            rm(path; recursive=true)
            return nothing
        end
    end
    (ispath(recovery) || islink(recovery)) &&
        throw(ArgumentError("$label is unsafe and deterministic recovery is already occupied"))
    mv(path, recovery)
    return recovery
end

function _invalidate_frozen_approval(output::String)
    task_dir = _task_directory_for(output)
    estimate = _resource_estimate_path(output)
    evidence = _frozen_evidence_paths(output)
    recovery = _recovery_path(output)
    retained = (ispath(recovery) || islink(recovery)) ? recovery : nothing
    # Invalidate the visible approval first. Verified-regular trees are safely
    # deleted; one unsafe tree is atomically renamed without traversal.
    if isfile(output) || islink(output)
        rm(output)
    elseif ispath(output)
        recovered = _remove_safe_or_recover(output, recovery, "frozen campaign output")
        recovered !== nothing && (retained = recovered)
    end
    if ispath(task_dir) || islink(task_dir)
        recovered = _remove_safe_or_recover(task_dir, recovery, "frozen task directory")
        recovered !== nothing && (retained = recovered)
    end
    if isfile(estimate) || islink(estimate)
        rm(estimate)
    elseif ispath(estimate)
        recovered = _remove_safe_or_recover(estimate, recovery, "frozen resource estimate")
        recovered !== nothing && (retained = recovered)
    end
    for (path, label) in ((evidence.calibration_path, "frozen calibration evidence"),
        (evidence.config_path, "frozen config evidence"))
        if isfile(path) || islink(path)
            rm(path)
        elseif ispath(path)
            recovered = _remove_safe_or_recover(path, recovery, label)
            recovered !== nothing && (retained = recovered)
        end
    end
    return retained
end

function _remove_refusal(path::String)
    if isfile(path) || islink(path)
        rm(path)
    elseif ispath(path)
        _safe_existing_task_directory(path)
        rm(path; recursive=true)
    end
    return nothing
end

"""Generate one mode; frozen refusal leaves only `<stem>-refusal.json`."""
function generate_manifest(config_path::AbstractString, calibration_path::AbstractString,
    mode::Union{Symbol,AbstractString}, output_path::AbstractString)
    selected = Symbol(mode)
    selected in (:smoke, :benchmark, :candidate, :frozen) ||
        throw(ArgumentError("mode must be smoke, benchmark, candidate, or frozen"))
    output = _canonical_output_with_parent(output_path)
    refusal = _refusal_path(output)
    estimate = _resource_estimate_path(output)
    evidence = _frozen_evidence_paths(output)
    if selected === :frozen
        alias_error = try
            _preflight_frozen_paths(config_path, calibration_path, output, refusal, estimate, evidence)
            nothing
        catch error
            error
        end
        if alias_error !== nothing
            alias_error isa FreezeRefusal || throw(alias_error)
            _remove_refusal(refusal)
            atomic_write_json(refusal, alias_error.report)
            return false
        end
        try
            config_bytes = read(config_path)
            config = load_recon_config(config_path)
            read(config_path) == config_bytes ||
                throw(_freeze_refusal(("provenance",), ["config changed while it was read"]))
            calibration = read_calibration(calibration_path, config)
            calibration_bytes = read(calibration_path)
            bytes2hex(sha256(calibration_bytes)) == calibration.content_sha256 ||
                throw(_freeze_refusal(("provenance",), ["calibration changed while it was read"]))
            manifest = make_frozen_manifest(config, calibration)
            resource_estimate = frozen_resource_estimate(config, calibration, manifest;
                calibration_path=basename(evidence.calibration_path),
                config_path=basename(evidence.config_path),
                config_content_sha256=bytes2hex(sha256(config_bytes)))
            _atomic_write_bytes(evidence.calibration_path, calibration_bytes)
            _atomic_write_bytes(evidence.config_path, config_bytes)
            atomic_write_json(estimate, resource_estimate)
            _remove_refusal(refusal)
            write_manifest_bundle(output, manifest)
            return true
        catch error
            error isa InterruptException && rethrow()
            refusal_error = error isa FreezeRefusal ? error :
                _freeze_refusal(("config",), [sprint(showerror, error)])
            recovery = _invalidate_frozen_approval(output)
            _remove_refusal(refusal)
            atomic_write_json(refusal, merge(refusal_error.report, (recovery_path=recovery,)))
            return false
        end
    end
    config = load_recon_config(config_path)
    manifest = selected === :smoke ? make_smoke_manifest(config) :
        selected === :benchmark ? make_benchmark_manifest(config) : make_candidate_manifest(config)
    write_manifest_bundle(output, manifest)
    return true
end

"""Parse exactly `--config --calibration --mode --output` in declared order."""
function parse_manifest_args(arguments::Vector{String})
    length(arguments) == 8 || throw(ArgumentError(
        "usage: make_route_a_manifest.jl --config PATH --calibration PATH|none --mode MODE --output PATH"))
    arguments[1] == "--config" && arguments[3] == "--calibration" &&
        arguments[5] == "--mode" && arguments[7] == "--output" ||
        throw(ArgumentError("manifest arguments must be --config, --calibration, --mode, --output in order"))
    all(!isempty, arguments[2:2:8]) || throw(ArgumentError("manifest arguments must be nonempty"))
    mode = Symbol(arguments[6])
    mode in (:smoke, :benchmark, :candidate, :frozen) ||
        throw(ArgumentError("mode must be smoke, benchmark, candidate, or frozen"))
    mode === :frozen && arguments[4] == "none" &&
        throw(ArgumentError("frozen mode requires calibration JSON"))
    return (
        config_path=arguments[2], calibration_path=arguments[4], mode=mode,
        output_path=arguments[8],
    )
end

function _manifest_main()
    arguments = parse_manifest_args(copy(ARGS))
    return generate_manifest(arguments.config_path, arguments.calibration_path,
        arguments.mode, arguments.output_path)
end

if abspath(PROGRAM_FILE) == @__FILE__
    try
        _manifest_main() || exit(1)
    catch error
        Base.display_error(stderr, catch_backtrace())
        exit(1)
    end
end
