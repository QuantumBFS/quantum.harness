using Serialization

struct CheckpointData{T}
    task_hash::String
    state::WorldlineState
    rng_state::UInt64
    bin_index::Int
    raw_bins::Vector{T}
    warmup_steps::Int
    bin_samples::Vector{Float64}
end

function _serialized_bytes(value)
    io = IOBuffer()
    serialize(io, value)
    return take!(io)
end

_checkpoint_checksum(payload_bytes::Vector{UInt8}) = bytes2hex(SHA.sha256(payload_bytes))

function write_checkpoint(
    path::AbstractString,
    task::TaskSpec,
    state::WorldlineState,
    rng::CounterRNG,
    bin_index::Integer,
    raw_bins::AbstractVector,
    ; warmup_steps::Integer=0,
    bin_samples::AbstractVector{<:Real}=Float64[],
)
    validate_state(state) || throw(ArgumentError("cannot checkpoint an invalid state"))
    bin_index >= 0 || throw(ArgumentError("bin_index must be nonnegative"))
    bins = collect(raw_bins)
    if all(bin -> bin isa Real, bins)
        all(isfinite, bins) || throw(ArgumentError("raw bins must be finite"))
    elseif all(bin -> bin isa RawBin, bins)
        all(_valid_raw_bin, bins) || throw(ArgumentError("raw observable bins must be valid"))
    else
        throw(ArgumentError("unsupported raw bin type"))
    end
    warmup_steps >= 0 || throw(ArgumentError("warmup_steps must be nonnegative"))
    samples = Float64.(bin_samples)
    all(isfinite, samples) || throw(ArgumentError("bin samples must be finite"))
    payload = CheckpointData(
        task_hash(task), deepcopy(state), rng.state, Int(bin_index), bins,
        Int(warmup_steps), samples,
    )
    payload_bytes = _serialized_bytes(payload)
    envelope = (
        magic="ROUTE_B_WORM_CHECKPOINT_V1",
        checksum=_checkpoint_checksum(payload_bytes),
        payload_bytes=payload_bytes,
    )
    bytes = _serialized_bytes(envelope)
    directory = dirname(path)
    isdir(directory) || mkpath(directory)
    temporary = path * ".tmp-" * string(getpid())
    open(temporary, "w") do io
        write(io, bytes)
        flush(io)
    end
    mv(temporary, path; force=true)
    return path
end

function read_checkpoint(path::AbstractString, task::TaskSpec)
    isfile(path) || throw(ArgumentError("checkpoint file does not exist"))
    envelope = try
        deserialize(path)
    catch error
        throw(ArgumentError("checkpoint cannot be deserialized: $(sprint(showerror, error))"))
    end
    envelope.magic == "ROUTE_B_WORM_CHECKPOINT_V1" ||
        throw(ArgumentError("unsupported checkpoint format"))
    payload_bytes = envelope.payload_bytes
    envelope.checksum == _checkpoint_checksum(payload_bytes) ||
        throw(ArgumentError("checkpoint checksum mismatch"))
    payload = try
        deserialize(IOBuffer(payload_bytes))
    catch error
        throw(ArgumentError("checkpoint payload cannot be deserialized: $(sprint(showerror, error))"))
    end
    payload.task_hash == task_hash(task) ||
        throw(ArgumentError("checkpoint belongs to another task"))
    validate_state(payload.state) || throw(ArgumentError("checkpoint state is invalid"))
    return payload
end
