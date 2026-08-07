using JLD2

const CORRELATION_CHECKPOINT_SCHEMA_VERSION = 1

"""A resumable, unnormalized phase sum for one correlation calculation."""
struct CorrelationCheckpoint
    schema_version::Int
    config_hash::String
    completed_phases::Int
    phase_count::Int
    lag_count::Int
    partial_sum::Vector{ComplexF64}
end

function CorrelationCheckpoint(config_hash::AbstractString,
                               completed_phases::Integer,
                               phase_count::Integer,
                               partial_sum::AbstractVector)
    isempty(config_hash) &&
        throw(ArgumentError("correlation checkpoint config hash cannot be empty"))
    phase_count > 0 ||
        throw(ArgumentError("correlation checkpoint phase count must be positive"))
    0 <= completed_phases <= phase_count ||
        throw(ArgumentError("completed phases are outside the checkpoint range"))
    isempty(partial_sum) &&
        throw(ArgumentError("correlation checkpoint partial sum cannot be empty"))
    eltype(partial_sum) <: Complex ||
        throw(ArgumentError("correlation checkpoint must retain complex values"))
    all(isfinite, partial_sum) ||
        throw(ArgumentError("correlation checkpoint contains non-finite values"))
    values = ComplexF64.(partial_sum)
    return CorrelationCheckpoint(
        CORRELATION_CHECKPOINT_SCHEMA_VERSION, String(config_hash),
        Int(completed_phases), Int(phase_count), length(values), values)
end

"""Atomically persist a correlation checkpoint in the destination directory."""
function save_correlation_checkpoint(path::AbstractString,
                                     checkpoint::CorrelationCheckpoint)
    directory = dirname(path)
    mkpath(directory)
    temporary_path, temporary_io = mktemp(directory; cleanup=false)
    close(temporary_io)
    try
        JLD2.jldsave(
            temporary_path;
            schema_version=checkpoint.schema_version,
            config_hash=checkpoint.config_hash,
            completed_phases=checkpoint.completed_phases,
            phase_count=checkpoint.phase_count,
            lag_count=checkpoint.lag_count,
            partial_sum=checkpoint.partial_sum)
        mv(temporary_path, path; force=true)
    catch
        ispath(temporary_path) && rm(temporary_path; force=true)
        rethrow()
    end
    return path
end

"""Load and validate a correlation checkpoint without accepting older schemas."""
function load_correlation_checkpoint(path::AbstractString)
    isfile(path) ||
        throw(ArgumentError("correlation checkpoint does not exist: " * path))
    payload = JLD2.load(path)
    required = ("schema_version", "config_hash", "completed_phases",
                "phase_count", "lag_count", "partial_sum")
    all(key -> haskey(payload, key), required) ||
        throw(ArgumentError("correlation checkpoint is incomplete: " * path))
    payload["schema_version"] == CORRELATION_CHECKPOINT_SCHEMA_VERSION ||
        throw(ArgumentError("correlation checkpoint schema is incompatible"))
    checkpoint = CorrelationCheckpoint(
        payload["config_hash"], payload["completed_phases"],
        payload["phase_count"], payload["partial_sum"])
    checkpoint.lag_count == payload["lag_count"] ||
        throw(ArgumentError("correlation checkpoint lag count is inconsistent"))
    return checkpoint
end

function _fig5_manifest_is_complete(path::AbstractString,
                                    config_hash::AbstractString)
    isfile(path) || return false
    contents = read(path, String)
    status_match = match(r"\"status\"\s*:\s*\"([^\"]+)\"", contents)
    hash_match = match(r"\"config_hash\"\s*:\s*\"([^\"]+)\"", contents)
    return !isnothing(status_match) && status_match.captures[1] == "ok" &&
           !isnothing(hash_match) && hash_match.captures[1] == config_hash
end

"""Return failed, incompatible, and missing Fig. 5 points in grid order."""
function pending_fig5_points(output_dir::AbstractString,
                             drive::Symbol,
                             frequencies::AbstractVector,
                             config_hash::AbstractString)
    drive in (:longitudinal, :transversal) ||
        throw(ArgumentError("Fig. 5 drive must be longitudinal or transversal"))
    isempty(config_hash) &&
        throw(ArgumentError("Fig. 5 config hash cannot be empty"))
    pending = Float64[]
    for frequency in frequencies
        frequency isa Real && isfinite(frequency) && frequency > 0 ||
            throw(ArgumentError(
                "Fig. 5 frequencies must be finite and positive"))
        manifest = joinpath(
            output_dir, String(drive), string(Float64(frequency)),
            "manifest.json")
        _fig5_manifest_is_complete(manifest, config_hash) ||
            push!(pending, Float64(frequency))
    end
    return pending
end

"""Atomically write one self-contained Fig. 5 point manifest."""
function save_fig5_manifest(path::AbstractString, contents::AbstractString)
    directory = dirname(path)
    mkpath(directory)
    temporary_path, temporary_io = mktemp(directory; cleanup=false)
    try
        write(temporary_io, contents)
        flush(temporary_io)
        close(temporary_io)
        mv(temporary_path, path; force=true)
    catch
        isopen(temporary_io) && close(temporary_io)
        ispath(temporary_path) && rm(temporary_path; force=true)
        rethrow()
    end
    return path
end

"""Return the deterministic on-disk location of one provenance-specific IF cache."""
function uniform_if_cache_path(cache_dir::AbstractString, metadata::AbstractDict)
    return joinpath(cache_dir, "uniform-if-" * uniform_if_key(metadata) * ".jld2")
end

"""Write a complete adapter through a same-directory temporary JLD2 file and atomic rename."""
function atomic_save(path::AbstractString, adapter::UniformIFAdapter; before_rename::Union{Nothing,Function}=nothing)
    directory = dirname(path)
    mkpath(directory)
    temporary_path, temporary_io = mktemp(directory; cleanup=false)
    close(temporary_io)
    try
        JLD2.jldsave(temporary_path;
                     q=adapter.q,
                     v_left=adapter.v_left,
                     v_right=adapter.v_right,
                     metadata=adapter.metadata,
                     achieved_chi=size(adapter.q, 1),
                     convergence_metadata=adapter.convergence_metadata)
        isnothing(before_rename) || before_rename()
        mv(temporary_path, path; force=true)
    catch
        ispath(temporary_path) && rm(temporary_path; force=true)
        rethrow()
    end
    return path
end

function _load_uniform_if(path::AbstractString, expected_metadata::AbstractDict)
    isfile(path) || throw(ArgumentError("uniform-IF cache does not exist: " * path))
    payload = JLD2.load(path)
    required = ("q", "v_left", "v_right", "metadata", "achieved_chi", "convergence_metadata")
    all(key -> haskey(payload, key), required) ||
        throw(ArgumentError("uniform-IF cache is incomplete: " * path))
    payload["achieved_chi"] == size(payload["q"], 1) ||
        throw(ArgumentError("uniform-IF cache achieved χ disagrees with q: " * path))
    payload["convergence_metadata"] isa AbstractDict ||
        throw(ArgumentError("uniform-IF cache convergence metadata is invalid: " * path))
    adapter = UniformIFAdapter(payload["q"], payload["v_left"], payload["v_right"],
                               payload["metadata"];
                               convergence_metadata=payload["convergence_metadata"])
    _canonical_uniform_if_metadata(adapter.metadata) ==
        _canonical_uniform_if_metadata(_string_metadata(expected_metadata)) ||
        throw(ArgumentError("uniform-IF cache provenance mismatch: " * path))
    return adapter
end

"""
Load a provenance-matched uniform IF cache, or build and atomically persist one.

A mismatched file is rejected rather than silently rebuilt. Pass rebuild=true
only when an explicit replacement was requested.
"""
function load_or_build_uniform_if(cache_dir::AbstractString, metadata::AbstractDict,
                                  builder::Function; rebuild::Bool=false)
    expected_metadata = _string_metadata(metadata)
    _validate_uniform_if_metadata(expected_metadata)
    path = uniform_if_cache_path(cache_dir, expected_metadata)
    if !rebuild && isfile(path)
        return _load_uniform_if(path, expected_metadata)
    end

    adapter = builder()
    adapter isa UniformIFAdapter ||
        throw(ArgumentError("uniform-IF builder must return UniformIFAdapter"))
    _canonical_uniform_if_metadata(adapter.metadata) ==
        _canonical_uniform_if_metadata(expected_metadata) ||
        throw(ArgumentError("uniform-IF builder provenance does not match requested cache"))
    atomic_save(path, adapter)
    return adapter
end
