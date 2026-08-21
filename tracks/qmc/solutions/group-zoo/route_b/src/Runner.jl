struct RunnerResult
    status::Symbol
    raw_bins::Vector{RawBin}
    checkpoint_path::String
    completion_checksum::Union{Nothing,String}
    elapsed_seconds::Float64
    proposed::Dict{ProposalFamily,Int}
    accepted::Dict{ProposalFamily,Int}
    illegal::Dict{ProposalFamily,Int}
end

function task_worm_parameters(task::TaskSpec)
    lattice = build_lattice(task.lattice, task.L)
    coordination = length(lattice.incident[1])
    all(length(incident) == coordination for incident in lattice.incident) ||
        throw(ArgumentError("worm calibration requires a regular lattice"))
    scale = min(
        task.beta,
        1 / max(abs(task.h), eps(Float64)),
        1 / (coordination * task.J),
    )
    return WormParameters(
        0.25,
        0.25,
        0.25,
        task.tau_multipliers[1] * scale,
        task.tau_multipliers[2] * scale,
        task.tau_multipliers[3] * scale,
    )
end

function _runner_kernel(task::TaskSpec, state::WorldlineState, rng::CounterRNG)
    parameters = task_worm_parameters(task)
    return WormKernel(state, rng, task.J, task.h, parameters)
end

function _completion_checksum(task::TaskSpec, raw_bins::Vector{RawBin})
    records = [_raw_bin_record(bin) for bin in raw_bins]
    bytes2hex(SHA.sha256(codeunits(task_hash(task) * JSON.json(records))))
end

function summarize_observable_bins(raw_bins::AbstractVector{RawBin})
    length(raw_bins) >= 2 || throw(ArgumentError("at least two raw bins are required"))
    all(_valid_raw_bin, raw_bins) || throw(ArgumentError("invalid raw bin"))
    series = Dict(
        "R_down" => [bin.R_down for bin in raw_bins],
        "energy" => [bin.energy for bin in raw_bins],
        "mx" => [bin.mx_original for bin in raw_bins],
        "bond" => [bin.bond for bin in raw_bins],
        "worm_return" => [bin.g_visits / bin.z_visits for bin in raw_bins],
    )
    result = Dict{String,Float64}()
    for (name, values) in series
        stats = binned_stats(values; binsize=1)
        result[name] = name == "worm_return" ?
            sum(bin.g_visits for bin in raw_bins) / sum(bin.z_visits for bin in raw_bins) :
            stats.mean
        result[name * "_stderr"] = stats.stderr
        result[name * "_tau_int"] = stats.tau_int
        result[name * "_ess"] = stats.ess
    end
    return result
end

function _record_value(record, name::Symbol)
    return record isa AbstractDict ? record[String(name)] : getproperty(record, name)
end

function _raw_bin_from_record(record)
    names = (
        :R_down, :I_wrap_1, :I_wrap_2, :I_wrap_any,
        :signed_winding_u, :signed_winding_v, :loop_count, :kink_count,
        :hopping_kinks, :pairing_kinks, :mz_rotated, :mx_original,
        :bond, :energy, :rotated_m2, :rotated_m4,
    )
    values = Float64[_record_value(record, name) for name in names]
    return RawBin(
        values...,
        Int(_record_value(record, :z_visits)),
        Int(_record_value(record, :g_visits)),
    )
end

function summarize_result_payloads(payloads::AbstractVector)
    isempty(payloads) && throw(ArgumentError("result payloads must not be empty"))
    raw_bins = RawBin[]
    for payload in payloads
        get(payload, "status", nothing) == "complete" ||
            throw(ArgumentError("all result payloads must be complete"))
        append!(raw_bins, _raw_bin_from_record.(payload["raw_bins"]))
    end
    return summarize_observable_bins(raw_bins)
end

function make_result_payload(
    task::TaskSpec,
    result::RunnerResult;
    git_commit::AbstractString,
    manifest_sha256::AbstractString,
)
    commit = String(git_commit)
    manifest = String(manifest_sha256)
    occursin(r"^[0-9a-f]{40}$", commit) ||
        throw(ArgumentError("result provenance requires a 40-hex Git commit"))
    occursin(r"^[0-9a-f]{64}$", manifest) ||
        throw(ArgumentError("result provenance requires a 64-hex manifest SHA-256"))
    return (
        status=String(result.status),
        task_hash=task_hash(task),
        git_commit=commit,
        manifest_sha256=manifest,
        raw_bins=[_raw_bin_record(bin) for bin in result.raw_bins],
        summary=length(result.raw_bins) >= 2 ? summarize_observable_bins(result.raw_bins) : nothing,
        checkpoint=result.checkpoint_path,
        completion_checksum=result.completion_checksum,
        elapsed_seconds=result.elapsed_seconds,
        proposed=Dict(string(family) => count for (family, count) in result.proposed),
        accepted=Dict(string(family) => count for (family, count) in result.accepted),
        illegal=Dict(string(family) => count for (family, count) in result.illegal),
    )
end

function verify_result_payload(task::TaskSpec, payload::AbstractDict)
    get(payload, "status", nothing) == "complete" ||
        throw(ArgumentError("result payload is not complete"))
    get(payload, "task_hash", nothing) == task_hash(task) ||
        throw(ArgumentError("result task hash mismatch"))
    commit = get(payload, "git_commit", nothing)
    manifest = get(payload, "manifest_sha256", nothing)
    (commit === nothing) == (manifest === nothing) ||
        throw(ArgumentError("result provenance is incomplete"))
    if commit !== nothing
        commit isa AbstractString && occursin(r"^[0-9a-f]{40}$", commit) ||
            throw(ArgumentError("result Git commit provenance is invalid"))
        manifest isa AbstractString && occursin(r"^[0-9a-f]{64}$", manifest) ||
            throw(ArgumentError("result manifest provenance is invalid"))
    end
    records = get(payload, "raw_bins", nothing)
    records isa AbstractVector || throw(ArgumentError("result raw_bins are missing"))
    length(records) == task.retained_bins ||
        throw(ArgumentError("result raw bin count mismatch"))
    raw_bins = try
        _raw_bin_from_record.(records)
    catch error
        throw(ArgumentError("invalid result raw bin: $(sprint(showerror, error))"))
    end
    all(_valid_raw_bin, raw_bins) || throw(ArgumentError("result contains invalid raw bins"))
    checksum = get(payload, "completion_checksum", nothing)
    checksum isa AbstractString && length(checksum) == 64 ||
        throw(ArgumentError("result completion checksum is missing"))
    checksum == _completion_checksum(task, raw_bins) ||
        throw(ArgumentError("result completion checksum mismatch"))
    summary = get(payload, "summary", nothing)
    summary isa AbstractDict || throw(ArgumentError("result summary is missing"))
    expected_summary = summarize_observable_bins(raw_bins)
    for (name, expected) in expected_summary
        haskey(summary, name) || throw(ArgumentError("result summary is missing $name"))
        isapprox(Float64(summary[name]), expected; rtol=64eps(Float64), atol=64eps(Float64)) ||
            throw(ArgumentError("result summary mismatch for $name"))
    end
    return true
end

function run_task(
    task::TaskSpec;
    checkpoint_path::AbstractString,
    resume::Bool=false,
    stop_after_bins::Union{Nothing,Integer}=nothing,
)
    stop_after_bins === nothing || (0 < stop_after_bins <= task.retained_bins) ||
        throw(ArgumentError("stop_after_bins is outside the task"))
    if resume
        checkpoint = read_checkpoint(checkpoint_path, task)
        state = checkpoint.state
        rng = CounterRNG(checkpoint.rng_state)
        all(bin -> bin isa RawBin, checkpoint.raw_bins) ||
            throw(ArgumentError("checkpoint does not contain Route B observable bins"))
        raw_bins = RawBin[checkpoint.raw_bins...]
        warmup_steps = checkpoint.warmup_steps
    else
        lattice = build_lattice(task.lattice, task.L)
        state = WorldlineState(
            lattice,
            task.beta;
            initial_spins=fill(Int8(1), lattice.nsites),
        )
        rng = CounterRNG(task.seed)
        raw_bins = RawBin[]
        warmup_steps = 0
    end
    kernel = _runner_kernel(task, state, rng)
    started_ns = time_ns()
    target = stop_after_bins === nothing ? task.retained_bins : Int(stop_after_bins)
    accumulator = _BinAccumulator()
    while length(raw_bins) < target
        step!(kernel)
        if warmup_steps < task.warmup_bins * task.visits_per_bin
            warmup_steps += 1
            continue
        end
        _record_step!(accumulator, state; h=task.h)
        accumulator.z_visits < task.visits_per_bin && continue
        push!(raw_bins, _finish_bin(accumulator))
        accumulator = _BinAccumulator()
        if length(raw_bins) % task.checkpoint_every == 0
            write_checkpoint(
                checkpoint_path,
                task,
                state,
                rng,
                length(raw_bins),
                raw_bins;
                warmup_steps=warmup_steps,
            )
        end
    end
    write_checkpoint(
        checkpoint_path,
        task,
        state,
        rng,
        length(raw_bins),
        raw_bins;
        warmup_steps=warmup_steps,
    )
    complete = length(raw_bins) == task.retained_bins
    checksum = complete ? _completion_checksum(task, raw_bins) : nothing
    elapsed_seconds = (time_ns() - started_ns) / 1e9
    return RunnerResult(
        complete ? :complete : :partial,
        raw_bins,
        String(checkpoint_path),
        checksum,
        elapsed_seconds,
        copy(kernel.proposed),
        copy(kernel.accepted),
        copy(kernel.illegal),
    )
end
