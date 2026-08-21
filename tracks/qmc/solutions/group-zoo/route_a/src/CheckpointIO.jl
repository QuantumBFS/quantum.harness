const _CHECKPOINT_SCHEMA_VERSION = 3
const _CHECKPOINT_MAGIC = UInt8[0x43, 0x31, 0x34, 0x38, 0x43, 0x48, 0x4b, 0x00]
const _MAX_RUNTIME_ID_BYTES = 128

_runtime_identity() = string(VERSION)

"""A versioned, exact snapshot of a Route A Markov chain and its completed bins."""
struct CheckpointEnvelope
    schema_version::Int
    task_hash::String
    git_commit::String
    manifest_hash::String
    runtime_version::String
    completed_bins::Int
    state::CWAState
    bins::Vector{BinRecord}
end

function _require_regular_or_absent(path::AbstractString, label::AbstractString)
    islink(path) && throw(ArgumentError("$label must be absent or a regular file: $path"))
    if ispath(path)
        isfile(path) || throw(ArgumentError("$label must be absent or a regular file: $path"))
    end
    return nothing
end

function _partial_path(path::AbstractString)
    directory = dirname(abspath(path))
    isdir(directory) || throw(ArgumentError("checkpoint directory does not exist: $directory"))
    temporary, io = mktemp(directory; cleanup=false)
    close(io)
    partial = temporary * ".partial"
    try
        mv(temporary, partial; force=false)
    catch
        isfile(temporary) && !islink(temporary) && rm(temporary; force=true)
        rethrow()
    end
    return partial
end

function _remove_temporary(path::AbstractString)
    isfile(path) && !islink(path) && rm(path; force=true)
    return nothing
end

function _read_checkpoint_header(io::IO, path::AbstractString)
    read(io, length(_CHECKPOINT_MAGIC)) == _CHECKPOINT_MAGIC ||
        throw(ArgumentError("checkpoint $path has an unsupported file header"))
    runtime_length = Int(read(io, UInt16))
    0 < runtime_length <= _MAX_RUNTIME_ID_BYTES ||
        throw(ArgumentError("checkpoint $path has an invalid runtime identifier"))
    runtime_version = String(read(io, runtime_length))
    runtime_version == _runtime_identity() ||
        throw(ArgumentError("checkpoint Julia runtime $runtime_version does not match $(_runtime_identity())"))
    return runtime_version
end

function _read_serialized_checkpoint(path::AbstractString)::CheckpointEnvelope
    header_runtime, envelope = try
        open(path, "r") do io
            _read_checkpoint_header(io, path), deserialize(io)
        end
    catch error
        error isa ArgumentError && rethrow()
        throw(ArgumentError("could not deserialize checkpoint $path: $(sprint(showerror, error))"))
    end
    envelope isa CheckpointEnvelope ||
        throw(ArgumentError("checkpoint $path does not contain a CheckpointEnvelope"))
    envelope.schema_version == _CHECKPOINT_SCHEMA_VERSION ||
        throw(ArgumentError("unsupported checkpoint schema version: $(envelope.schema_version)"))
    envelope.runtime_version == header_runtime ||
        throw(ArgumentError("checkpoint runtime metadata does not match its file header"))
    envelope.completed_bins == length(envelope.bins) ||
        throw(ArgumentError("checkpoint completed-bin count does not match serialized bins"))
    return envelope
end

function _validate_state_for_task(state::CWAState, task::ClusterTask)
    expected_geometry = lattice_geometry(task.lattice, task.L)
    geometry = state.geometry
    geometry.lattice == expected_geometry.lattice &&
        geometry.L == expected_geometry.L &&
        geometry.nsites == expected_geometry.nsites &&
        geometry.bonds == expected_geometry.bonds &&
        geometry.coordination == expected_geometry.coordination ||
        throw(ArgumentError("checkpoint state geometry does not match its task"))
    length(state.worldlines) == geometry.nsites ||
        throw(ArgumentError("checkpoint worldline count does not match its geometry"))
    state.J == task.J || throw(ArgumentError("checkpoint coupling does not match its task"))
    state.h_input == task.h || throw(ArgumentError("checkpoint input field does not match its task"))
    state.h_simulated == abs(task.h) ||
        throw(ArgumentError("checkpoint simulated field does not match its task"))
    state.beta == beta_for_aspect(task.h, task.L; c=task.c) ||
        throw(ArgumentError("checkpoint beta does not match its task"))
    return nothing
end

function _validate_checkpoint_bins(bins::Vector{BinRecord}, task::ClusterTask)
    for (index, bin) in enumerate(bins)
        all(isfinite, (
            bin.energy_per_site,
            bin.m_time2,
            bin.m_time4,
            bin.m_equal2,
            bin.m_equal4,
            bin.cuts_mean,
        )) || throw(ArgumentError("checkpoint bin $index contains nonfinite observables"))
        histogram = bin.cut_histogram
        canonical = CutHistogramBin(
            collect(histogram.cut_counts),
            collect(histogram.counts),
            collect(histogram.sum_m2),
            collect(histogram.sum_m4),
        )
        canonical == histogram ||
            throw(ArgumentError("checkpoint bin $index has a noncanonical cut histogram"))
        sum(histogram.counts) == task.base_bin_size ||
            throw(ArgumentError("checkpoint bin $index cut histogram has the wrong sample count"))
    end
    return nothing
end

function _validate_checkpoint(
    envelope::CheckpointEnvelope,
    task::ClusterTask;
    git_commit::AbstractString,
    manifest_hash::AbstractString,
)
    validate_task(task)
    envelope.task_hash == task_hash(task) ||
        throw(ArgumentError("checkpoint task hash does not match the requested task"))
    envelope.git_commit == git_commit ||
        throw(ArgumentError("checkpoint git commit does not match the running code"))
    envelope.manifest_hash == manifest_hash ||
        throw(ArgumentError("checkpoint manifest hash does not match the running environment"))
    envelope.runtime_version == _runtime_identity() ||
        throw(ArgumentError("checkpoint Julia runtime does not match the running runtime"))
    _validate_state_for_task(envelope.state, task)
    max_bins = task.measurement_sweeps ÷ task.base_bin_size
    0 <= envelope.completed_bins <= max_bins ||
        throw(ArgumentError("checkpoint completed-bin count is outside the task measurement range"))
    _validate_checkpoint_bins(envelope.bins, task)
    return envelope
end

function _write_serialized_checkpoint(path::AbstractString, envelope::CheckpointEnvelope)
    open(path, "w") do io
        runtime_bytes = codeunits(envelope.runtime_version)
        0 < length(runtime_bytes) <= typemax(UInt16) ||
            throw(ArgumentError("checkpoint runtime identifier has invalid length"))
        write(io, _CHECKPOINT_MAGIC)
        write(io, UInt16(length(runtime_bytes)))
        write(io, runtime_bytes)
        serialize(io, envelope)
        flush(io)
    end
    return _read_serialized_checkpoint(path)
end

function _validated_current_or_nothing(
    path::AbstractString,
    task::ClusterTask;
    git_commit::AbstractString,
    manifest_hash::AbstractString,
)
    !isfile(path) && return nothing
    try
        return _validate_checkpoint(
            _read_serialized_checkpoint(path), task; git_commit, manifest_hash)
    catch error
        error isa ArgumentError || rethrow()
        return nothing
    end
end

function _retain_current(path::AbstractString, backup::AbstractString)
    try
        hardlink(path, backup)
    catch error
        error isa Base.IOError || rethrow()
        cp(path, backup; force=false, follow_symlinks=false)
    end
    return nothing
end

function _install_retained_previous!(recovery::AbstractString, previous::AbstractString)
    isfile(recovery) && !islink(recovery) ||
        throw(ArgumentError("checkpoint recovery must be a regular file: $recovery"))
    _require_regular_or_absent(previous, "checkpoint previous destination")
    mv(recovery, previous; force=true)
    return nothing
end

function _recover_pending_previous!(
    previous::AbstractString,
    recovery::AbstractString,
    task::ClusterTask;
    git_commit::AbstractString,
    manifest_hash::AbstractString,
)
    !isfile(recovery) && return nothing
    _validate_checkpoint(
        _read_serialized_checkpoint(recovery), task; git_commit, manifest_hash)
    if isfile(previous)
        _validate_checkpoint(
            _read_serialized_checkpoint(previous), task; git_commit, manifest_hash)
    end
    _install_retained_previous!(recovery, previous)
    return nothing
end

"""
Atomically save a checkpoint and retain its preceding valid version at
`path * ".previous"`. Existing names must be regular files. The old current
checkpoint is retained before the candidate replaces it atomically, and becomes
`.previous` only after the new current is read back successfully. A failed
previous installation leaves the retained old checkpoint at
`path * ".previous.recovery"` for the next save to install before rotating.
"""
function save_checkpoint(
    path::AbstractString,
    task::ClusterTask,
    state::CWAState,
    bins::Vector{BinRecord};
    git_commit::AbstractString,
    manifest_hash::AbstractString,
    checkpoint_observer::Function=(_ -> nothing),
)
    validate_task(task)
    destination = abspath(path)
    previous = destination * ".previous"
    recovery = previous * ".recovery"
    _require_regular_or_absent(destination, "checkpoint destination")
    _require_regular_or_absent(previous, "checkpoint previous destination")
    _require_regular_or_absent(recovery, "checkpoint recovery destination")
    envelope = CheckpointEnvelope(
        _CHECKPOINT_SCHEMA_VERSION,
        task_hash(task),
        String(git_commit),
        String(manifest_hash),
        _runtime_identity(),
        length(bins),
        state,
        bins,
    )
    _validate_checkpoint(envelope, task; git_commit, manifest_hash)

    _recover_pending_previous!(
        previous, recovery, task; git_commit, manifest_hash)

    current = _validated_current_or_nothing(destination, task; git_commit, manifest_hash)
    if isfile(previous)
        _validate_checkpoint(
            _read_serialized_checkpoint(previous), task; git_commit, manifest_hash)
    end

    partial = _partial_path(destination)
    promoted = false
    candidate_valid = false
    retained_current = false

    try
        _write_serialized_checkpoint(partial, envelope)
        _validate_checkpoint(
            _read_serialized_checkpoint(partial), task; git_commit, manifest_hash)

        if current !== nothing
            _retain_current(destination, recovery)
            retained_current = true
            checkpoint_observer(:old_retained)
        end

        _require_regular_or_absent(destination, "checkpoint destination")
        mv(partial, destination; force=true)
        promoted = true
        _validate_checkpoint(
            _read_serialized_checkpoint(destination), task; git_commit, manifest_hash)
        candidate_valid = true
        checkpoint_observer(:candidate_promoted)

        if retained_current
            _install_retained_previous!(recovery, previous)
            retained_current = false
        end
        checkpoint_observer(:previous_installed)
        return String(path)
    catch
        if promoted && retained_current
            if candidate_valid
                try
                    _install_retained_previous!(recovery, previous)
                catch
                    retained_current = false
                    rethrow()
                end
            else
                _require_regular_or_absent(destination, "checkpoint destination")
                mv(recovery, destination; force=true)
            end
            retained_current = false
        end
        rethrow()
    finally
        _remove_temporary(partial)
        retained_current && _remove_temporary(recovery)
    end
end

"""Load a checkpoint only when its task, code, environment, and Julia runtime match."""
function load_checkpoint(
    path::AbstractString,
    task::ClusterTask;
    git_commit::AbstractString,
    manifest_hash::AbstractString,
    runtime_version::AbstractString=_runtime_identity(),
)::CheckpointEnvelope
    String(runtime_version) == _runtime_identity() ||
        throw(ArgumentError("requested checkpoint runtime does not match the running runtime"))
    envelope = _read_serialized_checkpoint(path)
    return _validate_checkpoint(envelope, task; git_commit, manifest_hash)
end

"""Write JSON to a same-directory temporary file and atomically replace a regular-file `path` after parsing it."""
function atomic_write_json(path::AbstractString, value)
    destination = abspath(path)
    _require_regular_or_absent(destination, "JSON destination")
    partial = _partial_path(destination)
    promoted = false
    try
        try
            open(partial, "w") do io
                JSON.print(io, value)
                flush(io)
            end
            JSON.parsefile(partial)
        catch error
            throw(ArgumentError("refusing to replace $path with invalid JSON: $(sprint(showerror, error))"))
        end
        _require_regular_or_absent(destination, "JSON destination")
        mv(partial, destination; force=true)
        promoted = true
        return String(path)
    finally
        !promoted && _remove_temporary(partial)
    end
end

"""Atomically write a completed Route A result only after validating its JSON representation."""
write_completed_result(path::AbstractString, result) = atomic_write_json(path, result)
