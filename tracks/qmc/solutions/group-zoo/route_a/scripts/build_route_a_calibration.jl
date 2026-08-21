using JSON
using SHA

include(joinpath(@__DIR__, "make_route_a_manifest.jl"))

const _BINARY_MEMORY_SCALE = Dict(
    'K' => Int128(1024),
    'M' => Int128(1024)^2,
    'G' => Int128(1024)^3,
    'T' => Int128(1024)^4,
)

function _bounded_int(value::Int128, label::String)
    0 <= value <= typemax(Int) || throw(ArgumentError("$label is outside the supported Int range"))
    return Int(value)
end

"""Parse one Slurm memory token into binary bytes, excluding any per-CPU multiplier."""
function parse_slurm_memory(value::AbstractString)
    token = String(value)
    matched = match(r"^([1-9][0-9]*)([KMGT])([cn]?)$", token)
    matched === nothing && throw(ArgumentError("unsupported Slurm memory token: $token"))
    amount = try
        parse(Int128, matched.captures[1])
    catch error
        error isa ArgumentError || rethrow()
        throw(ArgumentError("Slurm memory amount is outside the supported range"))
    end
    scale = _BINARY_MEMORY_SCALE[only(matched.captures[2])]
    return _bounded_int(amount * scale, "Slurm memory")
end

function _duration_component(value::AbstractString, label::String)
    !isempty(value) && all(isdigit, value) ||
        throw(ArgumentError("$label is not a nonnegative decimal integer"))
    parsed = try
        parse(Int128, value)
    catch error
        error isa ArgumentError || rethrow()
        throw(ArgumentError("$label is outside the supported range"))
    end
    return parsed
end

"""Parse Slurm raw seconds or an optional-days HH:MM:SS token into exact seconds."""
function parse_slurm_seconds(value::AbstractString)
    token = String(value)
    isempty(token) && throw(ArgumentError("Slurm duration is empty"))
    if occursin(r"^[0-9]+$", token)
        return _bounded_int(_duration_component(token, "Slurm seconds"), "Slurm duration")
    end
    matched = match(r"^(?:([0-9]+)-)?([0-9]{1,2}):([0-9]{2}):([0-9]{2})$", token)
    matched === nothing && throw(ArgumentError("unsupported Slurm duration token: $token"))
    days = matched.captures[1] === nothing ? Int128(0) :
        _duration_component(matched.captures[1], "Slurm days")
    hours = _duration_component(matched.captures[2], "Slurm hours")
    minutes = _duration_component(matched.captures[3], "Slurm minutes")
    seconds = _duration_component(matched.captures[4], "Slurm seconds")
    hours < 24 || throw(ArgumentError("Slurm duration hours must be below 24"))
    minutes < 60 || throw(ArgumentError("Slurm duration minutes must be below 60"))
    seconds < 60 || throw(ArgumentError("Slurm duration seconds must be below 60"))
    total = days * 86_400 + hours * 3_600 + minutes * 60 + seconds
    return _bounded_int(total, "Slurm duration")
end

const _CAPTURE_FIELDS = Set((
    "schema_version", "kind", "campaign_sha256", "bundle_script_sha256",
    "sacct_sha256", "wrapper_inventory_sha256", "result_provenance_sha256",
    "allocation_count", "result_count",
))
const _SACCT_HEADER = (
    "JobIDRaw", "JobID", "JobName", "State", "ElapsedRaw", "TimelimitRaw",
    "ReqMem", "AllocCPUS", "MaxRSS", "ExitCode", "SubmitLine",
)
const _WRAPPER_HEADER = (
    "allocation_key", "raw_job_id", "array_task_id", "wrapper_file",
    "wrapper_sha256", "start_index", "end_index",
)
const _RESULT_PROVENANCE_HEADER = ("result_file", "result_sha256", "slurm_job_id")

_sha256_token(value) = value isa AbstractString && occursin(r"^[0-9a-f]{64}$", value)

struct AllocationEvidence
    allocation_key::String
    raw_job_id::String
    array_task_id::Int
    state::String
    exit_code::String
    alloc_cpus::Int
    requested_memory_bytes::Int
    requested_walltime_seconds::Int
    elapsed_seconds::Int
    max_rss_upper_bytes::Int
    wrapper_file::String
    wrapper_sha256::String
    start_index::Int
    end_index::Int
    bundle_size::Int
    nominal_bundle_size::Int
    task_indices::Tuple{Vararg{Int}}
    canonical_accounting_rows::Tuple{String,String}
end

struct AccountingEvidence
    campaign_sha256::String
    bundle_script_sha256::String
    sacct_sha256::String
    wrapper_inventory_sha256::String
    result_provenance_sha256::String
    result_count::Int
    allocations::Tuple{Vararg{AllocationEvidence}}
    result_provenance::Tuple
end

struct ResultProvenanceEvidence
    result_file::String
    result_sha256::String
    raw_job_id::String
end

function _strict_int(value, label::String; positive::Bool=false, nonnegative::Bool=false)
    value isa Integer && !(value isa Bool) || throw(ArgumentError("$label must be an integer"))
    result = try
        Int(value)
    catch error
        error isa InexactError || rethrow()
        throw(ArgumentError("$label is outside the supported range"))
    end
    positive && result <= 0 && throw(ArgumentError("$label must be positive"))
    nonnegative && result < 0 && throw(ArgumentError("$label must be nonnegative"))
    return result
end

function _decimal_int(value::AbstractString, label::String; positive::Bool=false)
    occursin(r"^(0|[1-9][0-9]*)$", value) ||
        throw(ArgumentError("$label must be a canonical decimal integer"))
    result = try
        parse(Int, value)
    catch error
        error isa ArgumentError || rethrow()
        throw(ArgumentError("$label is outside the supported range"))
    end
    positive && result <= 0 && throw(ArgumentError("$label must be positive"))
    return result
end

function _regular_bytes(path::AbstractString, label::String)
    islink(path) && throw(ArgumentError("$label must not be a symlink"))
    isfile(path) || throw(ArgumentError("$label must be a regular file"))
    return read(path)
end

function _psv_rows(bytes::Vector{UInt8}, expected_header, label::String)
    lines = split(String(copy(bytes)), '\n'; keepempty=true)
    !isempty(lines) && isempty(lines[end]) || throw(ArgumentError("$label must end with one newline"))
    pop!(lines)
    !isempty(lines) || throw(ArgumentError("$label is empty"))
    Tuple(split(lines[1], '|'; keepempty=true)) == expected_header ||
        throw(ArgumentError("$label has an unexpected header"))
    rows = Vector{Vector{String}}()
    for (index, line) in enumerate(lines[2:end])
        isempty(line) && throw(ArgumentError("$label has an empty data row"))
        fields = String.(split(line, '|'; keepempty=true))
        length(fields) == length(expected_header) ||
            throw(ArgumentError("$label row $index has the wrong field count"))
        push!(rows, fields)
    end
    return rows
end

function _requested_memory_bytes(token::String, cpus::Int)
    bytes = parse_slurm_memory(token)
    if endswith(token, "c")
        product = Int128(bytes) * cpus
        return _bounded_int(product, "per-CPU requested memory")
    end
    return bytes
end

function _capture_metadata(bytes::Vector{UInt8})
    raw = try
        JSON.parse(String(copy(bytes)); dicttype=Dict)
    catch error
        throw(ArgumentError("capture metadata is invalid JSON: $(sprint(showerror, error))"))
    end
    raw isa AbstractDict && Set(string.(keys(raw))) == _CAPTURE_FIELDS ||
        throw(ArgumentError("capture metadata has missing or unknown fields"))
    _strict_int(raw["schema_version"], "capture schema_version") == 1 ||
        throw(ArgumentError("unsupported capture schema"))
    raw["kind"] == "route_a_accounting_capture" ||
        throw(ArgumentError("unsupported capture kind"))
    for field in ("campaign_sha256", "bundle_script_sha256", "sacct_sha256",
        "wrapper_inventory_sha256", "result_provenance_sha256")
        _sha256_token(raw[field]) || throw(ArgumentError("capture $field is invalid"))
    end
    return raw
end

function _allocation_from_rows(job_row, batch_row, wrapper_row, wrapper_bytes)
    raw_job_id, display, job_name, state, elapsed, limit, reqmem, cpus_token,
        maxrss, exit_code, submit_line = job_row
    raw_job_id == wrapper_row[2] || throw(ArgumentError("wrapper raw job ID mismatch"))
    display == wrapper_row[1] || throw(ArgumentError("wrapper allocation key mismatch"))
    matched = match(r"^([0-9]+)_([0-9]+)$", display)
    matched === nothing && throw(ArgumentError("allocation display ID is malformed"))
    array_task_id = _decimal_int(matched.captures[2], "array task ID")
    array_task_id == _decimal_int(wrapper_row[3], "wrapper array task ID") ||
        throw(ArgumentError("wrapper array task ID mismatch"))
    occursin(r"^[0-9]+$", raw_job_id) || throw(ArgumentError("raw job ID is malformed"))
    job_name == "route_a_bundle.sbatch" || throw(ArgumentError("unexpected allocation job name"))
    state == "COMPLETED" && exit_code == "0:0" ||
        throw(ArgumentError("allocation is not COMPLETED 0:0"))
    isempty(maxrss) || throw(ArgumentError("allocation row must not claim step MaxRSS"))
    cpus = _decimal_int(cpus_token, "AllocCPUS"; positive=true)
    elapsed_seconds = parse_slurm_seconds(elapsed)
    elapsed_seconds > 0 || throw(ArgumentError("allocation elapsed time must be positive"))
    requested_walltime_seconds = parse_slurm_seconds(limit)
    requested_walltime_seconds > 0 || throw(ArgumentError("allocation time limit must be positive"))
    requested_memory_bytes = _requested_memory_bytes(reqmem, cpus)
    isempty(submit_line) && throw(ArgumentError("allocation SubmitLine is absent"))
    bundle_matches = collect(eachmatch(
        r"(?:^|[,[:space:]])BUNDLE_SIZE=([1-9][0-9]*)(?=,|[[:space:]]|$)",
        submit_line,
    ))
    length(bundle_matches) == 1 ||
        throw(ArgumentError("allocation SubmitLine lacks one exact BUNDLE_SIZE"))
    nominal_bundle_size = _decimal_int(
        only(bundle_matches).captures[1], "submitted BUNDLE_SIZE"; positive=true)

    batch_raw, batch_display, batch_name, batch_state, batch_elapsed, batch_limit,
        batch_reqmem, batch_cpus, batch_maxrss, batch_exit, batch_submit = batch_row
    batch_raw == raw_job_id * ".batch" && batch_display == display * ".batch" &&
        batch_name == "batch" || throw(ArgumentError("batch row identity mismatch"))
    batch_state == "COMPLETED" && batch_exit == "0:0" ||
        throw(ArgumentError("batch step is not COMPLETED 0:0"))
    parse_slurm_seconds(batch_elapsed) == elapsed_seconds ||
        throw(ArgumentError("batch and allocation elapsed times disagree"))
    isempty(batch_limit) && isempty(batch_reqmem) && isempty(batch_submit) ||
        throw(ArgumentError("batch row contains allocation-only fields"))
    _decimal_int(batch_cpus, "batch AllocCPUS"; positive=true) == cpus ||
        throw(ArgumentError("batch and allocation CPUs disagree"))
    max_rss_upper_bytes = parse_slurm_memory(batch_maxrss)

    wrapper_file, wrapper_sha = wrapper_row[4], wrapper_row[5]
    basename(wrapper_file) == wrapper_file && !occursin('|', wrapper_file) ||
        throw(ArgumentError("wrapper filename is unsafe"))
    _sha256_token(wrapper_sha) && bytes2hex(sha256(wrapper_bytes)) == wrapper_sha ||
        throw(ArgumentError("wrapper hash mismatch"))
    start_index = _decimal_int(wrapper_row[6], "wrapper start index")
    end_index = _decimal_int(wrapper_row[7], "wrapper end index")
    start_index <= end_index || throw(ArgumentError("wrapper range is reversed"))
    completion = "route_a_bundle: completed task indices $start_index-$end_index"
    nonempty = filter(!isempty, split(String(copy(wrapper_bytes)), '\n'))
    count(==(completion), nonempty) == 1 && !isempty(nonempty) && nonempty[end] == completion ||
        throw(ArgumentError("wrapper completion line does not match inventory"))
    indices = Tuple(start_index:end_index)
    start_index == array_task_id * nominal_bundle_size ||
        throw(ArgumentError("wrapper range disagrees with submitted bundle mapping"))
    length(indices) <= nominal_bundle_size ||
        throw(ArgumentError("wrapper range exceeds submitted BUNDLE_SIZE"))
    return AllocationEvidence(
        display, raw_job_id, array_task_id, state, exit_code, cpus,
        requested_memory_bytes, requested_walltime_seconds, elapsed_seconds,
        max_rss_upper_bytes, wrapper_file, wrapper_sha, start_index, end_index,
        length(indices), nominal_bundle_size, indices,
        (join(job_row, '|'), join(batch_row, '|')),
    )
end

"""Read and verify one immutable accounting-capture directory."""
function read_accounting_evidence(path::AbstractString)
    islink(path) && throw(ArgumentError("accounting evidence directory must not be a symlink"))
    isdir(path) || throw(ArgumentError("accounting evidence directory is absent"))
    files = Dict(
        name => _regular_bytes(joinpath(path, name), name)
        for name in ("capture.json", "sacct.psv", "wrapper_inventory.psv", "result_provenance.psv")
    )
    capture = _capture_metadata(files["capture.json"])
    for (field, name) in (
        ("sacct_sha256", "sacct.psv"),
        ("wrapper_inventory_sha256", "wrapper_inventory.psv"),
        ("result_provenance_sha256", "result_provenance.psv"),
    )
        bytes2hex(sha256(files[name])) == capture[field] ||
            throw(ArgumentError("$name does not match capture metadata"))
    end
    sacct_rows = _psv_rows(files["sacct.psv"], _SACCT_HEADER, "sacct.psv")
    wrapper_rows = _psv_rows(files["wrapper_inventory.psv"], _WRAPPER_HEADER,
        "wrapper_inventory.psv")
    result_rows = _psv_rows(files["result_provenance.psv"], _RESULT_PROVENANCE_HEADER,
        "result_provenance.psv")
    allocation_count = _strict_int(capture["allocation_count"], "allocation_count"; positive=true)
    result_count = _strict_int(capture["result_count"], "result_count"; positive=true)
    length(wrapper_rows) == allocation_count ||
        throw(ArgumentError("wrapper inventory allocation count mismatch"))
    length(result_rows) == result_count ||
        throw(ArgumentError("result provenance count mismatch"))

    wrapper_keys = getindex.(wrapper_rows, 1)
    raw_ids = getindex.(wrapper_rows, 2)
    length(unique(wrapper_keys)) == length(wrapper_keys) ||
        throw(ArgumentError("duplicate wrapper allocation key"))
    length(unique(raw_ids)) == length(raw_ids) ||
        throw(ArgumentError("duplicate wrapper raw job ID"))
    allocations = AllocationEvidence[]
    for wrapper_row in wrapper_rows
        raw = wrapper_row[2]
        jobs = filter(row -> row[1] == raw, sacct_rows)
        batches = filter(row -> row[1] == raw * ".batch", sacct_rows)
        length(jobs) == 1 && length(batches) == 1 ||
            throw(ArgumentError("allocation $raw lacks one exact job and batch row"))
        wrapper_path = joinpath(path, "wrappers", wrapper_row[4])
        wrapper_bytes = _regular_bytes(wrapper_path, "wrapper stdout")
        push!(allocations, _allocation_from_rows(only(jobs), only(batches), wrapper_row, wrapper_bytes))
    end
    used_rows = Set(vcat(
        [allocation.canonical_accounting_rows[1] for allocation in allocations],
        [allocation.canonical_accounting_rows[2] for allocation in allocations],
    ))
    Set(join(row, '|') for row in sacct_rows) == used_rows ||
        throw(ArgumentError("sacct.psv contains unassigned or duplicate rows"))

    result_names = getindex.(result_rows, 1)
    length(unique(result_names)) == length(result_names) ||
        throw(ArgumentError("duplicate result provenance filename"))
    allocation_ids = Set(getfield.(allocations, :raw_job_id))
    counts = Dict(id => 0 for id in allocation_ids)
    result_provenance = ResultProvenanceEvidence[]
    for row in result_rows
        basename(row[1]) == row[1] && !occursin('|', row[1]) ||
            throw(ArgumentError("unsafe result provenance filename"))
        _sha256_token(row[2]) || throw(ArgumentError("invalid result provenance hash"))
        row[3] in allocation_ids || throw(ArgumentError("result references an unknown allocation"))
        counts[row[3]] += 1
        push!(result_provenance, ResultProvenanceEvidence(row[1], row[2], row[3]))
    end
    for allocation in allocations
        counts[allocation.raw_job_id] == allocation.bundle_size ||
            throw(ArgumentError("result count disagrees with wrapper range for $(allocation.allocation_key)"))
    end
    sort!(allocations; by=allocation -> allocation.allocation_key)
    for (name, bytes) in files
        read(joinpath(path, name)) == bytes || throw(ArgumentError("$name changed while it was read"))
    end
    for allocation in allocations
        wrapper_path = joinpath(path, "wrappers", allocation.wrapper_file)
        bytes2hex(sha256(_regular_bytes(wrapper_path, "wrapper stdout"))) ==
            allocation.wrapper_sha256 ||
            throw(ArgumentError("wrapper stdout changed while it was read"))
    end
    return AccountingEvidence(
        String(capture["campaign_sha256"]), String(capture["bundle_script_sha256"]),
        String(capture["sacct_sha256"]), String(capture["wrapper_inventory_sha256"]),
        String(capture["result_provenance_sha256"]), result_count, Tuple(allocations),
        Tuple(sort!(result_provenance; by=record -> record.result_file)),
    )
end

"""Map every zero-based manifest index to exactly one completed allocation."""
function build_allocation_table(evidence::AccountingEvidence; expected_task_count::Integer)
    count = Int(expected_task_count)
    count > 0 || throw(ArgumentError("expected task count must be positive"))
    table = Dict{Int,AllocationEvidence}()
    for allocation in evidence.allocations, index in allocation.task_indices
        0 <= index < count || throw(ArgumentError("allocation task index is outside the campaign"))
        haskey(table, index) && throw(ArgumentError("task index $index belongs to multiple allocations"))
        table[index] = allocation
    end
    Set(keys(table)) == Set(0:(count - 1)) ||
        throw(ArgumentError("allocation table does not cover every task exactly once"))
    evidence.result_count == count || throw(ArgumentError("capture result count disagrees with campaign"))
    return table
end

function _safe_input_directory(path::AbstractString, label::String)
    islink(path) && throw(ArgumentError("$label must not be a symlink"))
    isdir(path) || throw(ArgumentError("$label must be an existing directory"))
    return realpath(path)
end

function _task_path_entries(bytes::Vector{UInt8}, expected_count::Int)
    source = String(copy(bytes))
    endswith(source, '\n') || throw(ArgumentError("task_paths.txt must end with one newline"))
    entries = split(chomp(source), '\n')
    length(entries) == expected_count || throw(ArgumentError("task_paths.txt count mismatch"))
    length(unique(entries)) == length(entries) || throw(ArgumentError("task_paths.txt has duplicate entries"))
    for entry in entries
        !isempty(entry) && basename(entry) == entry && endswith(entry, ".json") &&
            !occursin('|', entry) && !occursin('\r', entry) ||
            throw(ArgumentError("task_paths.txt contains an unsafe entry"))
    end
    return String.(entries)
end

"""Audit campaign, ordered task inputs, immutable results, and allocation evidence together."""
function audit_benchmark_inputs(
    campaign_path::AbstractString,
    task_paths_path::AbstractString,
    results_path::AbstractString,
    evidence_path::AbstractString;
    expected_campaign_id::AbstractString="benchmark-5c3e1a4868c36f8e",
    expected_task_count::Integer=328,
    expected_release_commit::AbstractString="69e02b31a5078afa531e2ff96d80cc35bd6a2124",
)
    count = Int(expected_task_count)
    count > 0 || throw(ArgumentError("expected benchmark task count must be positive"))
    campaign_bytes = _regular_bytes(campaign_path, "benchmark campaign")
    task_paths_bytes = _regular_bytes(task_paths_path, "task_paths.txt")
    campaign_sha = bytes2hex(sha256(campaign_bytes))
    task_paths_sha = bytes2hex(sha256(task_paths_bytes))
    campaign = _read_campaign_manifest(campaign_path)
    campaign.campaign_id == expected_campaign_id ||
        throw(ArgumentError("benchmark campaign ID mismatch"))
    length(campaign.tasks) == count || throw(ArgumentError("benchmark campaign task count mismatch"))
    campaign.git_commit == expected_release_commit ||
        throw(ArgumentError("benchmark release commit mismatch"))
    _verify_release_snapshot(campaign.git_commit, campaign.julia_manifest_sha256;
        root=_RECON_ROOT) || throw(ArgumentError("benchmark release snapshot is not runnable"))

    task_directory = _safe_input_directory(dirname(abspath(task_paths_path)), "task directory")
    entries = _task_path_entries(task_paths_bytes, count)
    task_input_bytes = Vector{Vector{UInt8}}(undef, count)
    input_tasks = ClusterTask[]
    for (index, entry) in enumerate(entries)
        path = joinpath(task_directory, entry)
        task_input_bytes[index] = _regular_bytes(path, "task input")
        task = read_task(path)
        canonical_task_string(task) == canonical_task_string(campaign.tasks[index]) ||
            throw(ArgumentError("task input $entry disagrees with campaign index $(index - 1)"))
        push!(input_tasks, task)
    end

    results_directory = _safe_input_directory(results_path, "results directory")
    _result_occupants(results_directory, campaign.outputs)
    evidence = read_accounting_evidence(evidence_path)
    evidence.campaign_sha256 == campaign_sha ||
        throw(ArgumentError("accounting evidence is bound to another campaign"))
    allocation_by_index = build_allocation_table(evidence; expected_task_count=count)
    result_evidence = Dict(record.result_file => record for record in evidence.result_provenance)
    Set(keys(result_evidence)) == Set(campaign.outputs) ||
        throw(ArgumentError("result provenance inventory does not match campaign outputs"))

    results = Any[]
    result_bytes = Vector{Vector{UInt8}}(undef, count)
    for (index, task) in enumerate(campaign.tasks)
        result_path = joinpath(results_directory, task.output_path)
        bytes = _regular_bytes(result_path, "benchmark result")
        result_bytes[index] = bytes
        recorded = result_evidence[task.output_path]
        bytes2hex(sha256(bytes)) == recorded.result_sha256 ||
            throw(ArgumentError("result provenance hash mismatch for $(task.output_path)"))
        allocation = allocation_by_index[index - 1]
        recorded.raw_job_id == allocation.raw_job_id ||
            throw(ArgumentError("result provenance allocation mismatch for $(task.output_path)"))
        result = verify_completed_result(
            result_path, task;
            git_commit=campaign.git_commit,
            manifest_hash=campaign.julia_manifest_sha256,
        )
        provenance = result["provenance"]
        provenance["slurm_job_id"] == allocation.raw_job_id ||
            throw(ArgumentError("result Slurm job ID does not match its allocation"))
        provenance["slurm_array_task_id"] == string(index - 1) ||
            throw(ArgumentError("result task index does not match task_paths.txt order"))
        read(result_path) == bytes || throw(ArgumentError("benchmark result changed while it was read"))
        push!(results, result)
    end

    read(campaign_path) == campaign_bytes ||
        throw(ArgumentError("benchmark campaign changed while it was read"))
    read(task_paths_path) == task_paths_bytes ||
        throw(ArgumentError("task_paths.txt changed while it was read"))
    for (index, entry) in enumerate(entries)
        read(joinpath(task_directory, entry)) == task_input_bytes[index] ||
            throw(ArgumentError("task input changed while it was read"))
    end
    return (
        campaign=campaign,
        campaign_sha256=campaign_sha,
        task_paths_sha256=task_paths_sha,
        tasks=Tuple(input_tasks),
        results=Tuple(results),
        result_bytes=Tuple(result_bytes),
        allocations=evidence.allocations,
        allocation_by_index=allocation_by_index,
        accounting=evidence,
    )
end

function _finite_series(result, field::String)
    raw = result["raw_bins"]
    raw isa AbstractDict && haskey(raw, field) ||
        throw(ArgumentError("raw-bin field $field is absent"))
    values = raw[field]
    values isa AbstractVector && length(values) >= 2 ||
        throw(ArgumentError("raw-bin field $field is too short"))
    normalized = Float64[]
    for value in values
        value isa Real && !(value isa Bool) ||
            throw(ArgumentError("raw-bin field $field is not numeric"))
        converted = Float64(value)
        isfinite(converted) || throw(ArgumentError("raw-bin field $field is nonfinite"))
        push!(normalized, converted)
    end
    return normalized
end

function _mean_summary(values::Vector{Float64})
    length(values) >= 2 || throw(ArgumentError("mean summary needs at least two bins"))
    value = mean(values)
    error = std(values) / sqrt(length(values))
    isfinite(value) && isfinite(error) && error >= 0 ||
        throw(ArgumentError("mean summary is invalid"))
    return (mean=value, stderr=error)
end

function _binder_summary(m2::Vector{Float64}, m4::Vector{Float64})
    length(m2) == length(m4) && length(m2) >= 2 ||
        throw(ArgumentError("Binder summary needs matching bin series"))
    estimate = binder_from_bins(m2, m4)
    isfinite(estimate.mean) && isfinite(estimate.stderr) && estimate.stderr >= 0 ||
        throw(ArgumentError("Binder summary is invalid"))
    return (mean=estimate.mean, stderr=estimate.stderr)
end

function _split_summaries(values::Vector{Float64}, summary::Function)
    iseven(length(values)) && length(values) >= 4 ||
        throw(ArgumentError("split summary requires an even number of at least four bins"))
    midpoint = length(values) ÷ 2
    return summary(values[1:midpoint]), summary(values[(midpoint + 1):end])
end

function _split_binder_summaries(m2::Vector{Float64}, m4::Vector{Float64})
    length(m2) == length(m4) && iseven(length(m2)) && length(m2) >= 4 ||
        throw(ArgumentError("split Binder summary requires matching even bin series"))
    midpoint = length(m2) ÷ 2
    return _binder_summary(m2[1:midpoint], m4[1:midpoint]),
        _binder_summary(m2[(midpoint + 1):end], m4[(midpoint + 1):end])
end

function _binder_influence(m2::Vector{Float64}, m4::Vector{Float64})
    length(m2) == length(m4) && length(m2) >= 3 ||
        throw(ArgumentError("Binder influence needs at least three matching bins"))
    mean_m2 = mean(m2)
    mean_m4 = mean(m4)
    isfinite(mean_m2) && isfinite(mean_m4) && !iszero(mean_m4) ||
        throw(ArgumentError("Binder influence has degenerate moments"))
    gradient_m2 = 2mean_m2 / mean_m4
    gradient_m4 = -(mean_m2^2) / mean_m4^2
    influence = gradient_m2 .* (m2 .- mean_m2) .+ gradient_m4 .* (m4 .- mean_m4)
    all(isfinite, influence) && var(influence) > 0 ||
        throw(ArgumentError("Binder influence variance is degenerate"))
    return influence
end

function _delete_one_stderr(estimator::Function, length_data::Int)
    length_data >= 4 || throw(ArgumentError("delete-one uncertainty needs at least four bins"))
    estimates = Float64[]
    for omitted in 1:length_data
        value = Float64(estimator(omitted))
        isfinite(value) || throw(ArgumentError("delete-one estimate is nonfinite"))
        push!(estimates, value)
    end
    error = sqrt((length_data - 1) / length_data * sum(abs2, estimates .- mean(estimates)))
    isfinite(error) && error >= 0 || throw(ArgumentError("delete-one uncertainty is invalid"))
    return error
end

function _without_index(values::Vector{Float64}, omitted::Int)
    return vcat(values[1:(omitted - 1)], values[(omitted + 1):end])
end

function _binder_reference_diagnostics(m2::Vector{Float64}, m4::Vector{Float64})
    influence = _binder_influence(m2, m4)
    tau = tau_int_initial_positive(influence)
    variance = var(influence)
    tau_error = _delete_one_stderr(length(m2)) do omitted
        reduced_m2 = _without_index(m2, omitted)
        reduced_m4 = _without_index(m4, omitted)
        tau_int_initial_positive(_binder_influence(reduced_m2, reduced_m4))
    end
    variance_error = _delete_one_stderr(length(m2)) do omitted
        var(_binder_influence(_without_index(m2, omitted), _without_index(m4, omitted)))
    end
    isfinite(tau) && tau >= 0.5 && isfinite(variance) && variance > 0 ||
        throw(ArgumentError("Binder reference diagnostics are invalid"))
    return (tau=tau, tau_stderr=tau_error, variance=variance,
        variance_stderr=variance_error)
end

"""Derive one immutable chain-grain record from an already audited result."""
function derive_chain_record(audited, index::Integer; anchor_x::Real,
    reference_diagnostics::Bool=false)
    1 <= index <= length(audited.tasks) || throw(BoundsError(audited.tasks, index))
    task = audited.tasks[index]
    result = audited.results[index]
    allocation = audited.allocation_by_index[index - 1]
    energy = _finite_series(result, "energy_per_site")
    m2 = _finite_series(result, "m_time2")
    m4 = _finite_series(result, "m_time4")
    cuts = _finite_series(result, "cuts_mean")
    energy_summary = _mean_summary(energy)
    energy_first, energy_second = _split_summaries(energy, _mean_summary)
    binder_summary = _binder_summary(m2, m4)
    binder_first, binder_second = _split_binder_summaries(m2, m4)
    reference = reference_diagnostics ? _binder_reference_diagnostics(m2, m4) : nothing
    provenance = result["provenance"]
    elapsed = Float64(provenance["wall_seconds"])
    total_sweeps = task.thermalization_sweeps + task.measurement_sweeps
    elapsed > 0 && total_sweeps > 0 || throw(ArgumentError("chain timing is invalid"))
    anchor = Float64(anchor_x)
    isfinite(anchor) || throw(ArgumentError("anchor_x must be finite"))
    allocation.requested_memory_bytes % allocation.bundle_size == 0 ||
        throw(ArgumentError("allocation memory is not divisible by its chain count"))
    return (
        calibration_key="cal-" * lpad(string(index), 4, '0'),
        manifest_index=index - 1,
        allocation_key=allocation.allocation_key,
        raw_slurm_job_id=allocation.raw_job_id,
        slurm_task_index=index - 1,
        task_id=task_id(task),
        task_hash=task_hash(task),
        seed="u64:" * string(task.seed; base=16, pad=16),
        result_sha256=bytes2hex(sha256(audited.result_bytes[index])),
        completion_checksum=String(result["completion_checksum"]),
        release_git_commit=String(provenance["git_commit"]),
        release_julia_manifest_sha256=String(provenance["manifest_sha256"]),
        release_julia_version=String(provenance["julia_version"]),
        algorithm=String(result["algorithm"]),
        observable_schema_version=Int(result["observable_schema_version"]),
        lattice=task.lattice,
        L=task.L,
        J=task.J,
        h=task.h,
        c=task.c,
        anchor_x=anchor,
        replica=task.replica,
        thermalization_sweeps=task.thermalization_sweeps,
        measurement_sweeps=task.measurement_sweeps,
        base_bin_size=task.base_bin_size,
        energy_mean=energy_summary.mean,
        energy_stderr=energy_summary.stderr,
        energy_first_half_mean=energy_first.mean,
        energy_first_half_stderr=energy_first.stderr,
        energy_second_half_mean=energy_second.mean,
        energy_second_half_stderr=energy_second.stderr,
        binder_mean=binder_summary.mean,
        binder_stderr=binder_summary.stderr,
        binder_first_half_mean=binder_first.mean,
        binder_first_half_stderr=binder_first.stderr,
        binder_second_half_mean=binder_second.mean,
        binder_second_half_stderr=binder_second.stderr,
        binder_slope=nothing,
        binder_slope_stderr=nothing,
        tau_int_base_bins=reference === nothing ? nothing : reference.tau,
        tau_int_stderr_base_bins=reference === nothing ? nothing : reference.tau_stderr,
        binder_variance_per_base_bin=reference === nothing ? nothing : reference.variance,
        binder_variance_stderr_per_base_bin=reference === nothing ? nothing : reference.variance_stderr,
        cut_count_mean=mean(cuts),
        elapsed_seconds=elapsed,
        elapsed_per_sweep_seconds=elapsed / total_sweeps,
        max_rss_upper_bytes=allocation.max_rss_upper_bytes,
        nominal_requested_memory_per_chain_bytes=
            div(allocation.requested_memory_bytes, allocation.bundle_size),
        result_bytes=length(audited.result_bytes[index]),
    )
end

"""Derive independent three-anchor slopes and attach them only to central records."""
function derive_three_anchor_slopes(records; slope_required::Function)
    normalized = collect(records)
    all(record -> record.binder_slope === nothing && record.binder_slope_stderr === nothing,
        normalized) || throw(ArgumentError("input records already claim Binder slopes"))
    groups = Dict{Tuple,Vector{Int}}()
    for (index, record) in enumerate(normalized)
        key = (record.lattice, record.L, record.c, record.replica,
            record.thermalization_sweeps)
        push!(get!(groups, key, Int[]), index)
    end
    updated = Any[record for record in normalized]
    for indices in values(groups)
        central_indices = filter(index -> normalized[index].anchor_x == 0.0, indices)
        isempty(central_indices) && continue
        length(central_indices) == 1 || throw(ArgumentError("slope group has duplicate central anchors"))
        central_index = only(central_indices)
        slope_required(normalized[central_index]) || continue
        length(indices) == 3 || throw(ArgumentError("required slope group does not contain three anchors"))
        group = normalized[indices]
        Set(getfield.(group, :anchor_x)) == Set((-0.6, 0.0, 0.6)) ||
            throw(ArgumentError("required slope group has incorrect anchors"))
        h = Float64.(getfield.(group, :h))
        binder = Float64.(getfield.(group, :binder_mean))
        errors = Float64.(getfield.(group, :binder_stderr))
        all(isfinite, h) && all(isfinite, binder) && all(value -> isfinite(value) && value >= 0, errors) ||
            throw(ArgumentError("required slope group contains invalid values"))
        centered_h = h .- mean(h)
        denominator = sum(abs2, centered_h)
        denominator > 0 || throw(ArgumentError("required slope group has degenerate fields"))
        weights = centered_h ./ denominator
        slope = sum(weights .* binder)
        slope_stderr = sqrt(sum(abs2, weights .* errors))
        isfinite(slope) && isfinite(slope_stderr) && slope_stderr >= 0 ||
            throw(ArgumentError("derived Binder slope is invalid"))
        updated[central_index] = merge(normalized[central_index],
            (binder_slope=slope, binder_slope_stderr=slope_stderr))
    end
    sort!(updated; by=record -> record.manifest_index)
    return updated
end

function _production_anchor(task::ClusterTask, config::ReconConfig)
    matches = [anchor for anchor in config.anchors if
        task.h == config.h_old[task.lattice] + anchor * task.L^-config.yt_anchor]
    length(matches) == 1 || throw(ArgumentError("task does not have one exact approved anchor"))
    return only(matches)
end

function _allocation_json(allocation::AllocationEvidence, tasks)
    assigned = [tasks[index + 1] for index in allocation.task_indices]
    return (
        allocation_key=allocation.allocation_key,
        raw_job_id=allocation.raw_job_id,
        array_task_id=allocation.array_task_id,
        state=allocation.state,
        exit_code=allocation.exit_code,
        alloc_cpus=allocation.alloc_cpus,
        requested_memory_bytes=allocation.requested_memory_bytes,
        requested_walltime_seconds=allocation.requested_walltime_seconds,
        elapsed_seconds=allocation.elapsed_seconds,
        max_rss_upper_bytes=allocation.max_rss_upper_bytes,
        nominal_bundle_size=allocation.nominal_bundle_size,
        bundle_size=allocation.bundle_size,
        task_indices=collect(allocation.task_indices),
        task_ids=task_id.(assigned),
        task_hashes=task_hash.(assigned),
        wrapper_file=allocation.wrapper_file,
        wrapper_sha256=allocation.wrapper_sha256,
        completed_start_index=allocation.start_index,
        completed_end_index=allocation.end_index,
        canonical_accounting_rows=collect(allocation.canonical_accounting_rows),
    )
end

_chain_json(record) = merge(record, (lattice=String(record.lattice),))

function _audit_fingerprint(audited)
    return (
        campaign_sha256=audited.campaign_sha256,
        task_paths_sha256=audited.task_paths_sha256,
        result_sha256=Tuple(bytes2hex(sha256(bytes)) for bytes in audited.result_bytes),
        sacct_sha256=audited.accounting.sacct_sha256,
        wrapper_inventory_sha256=audited.accounting.wrapper_inventory_sha256,
        result_provenance_sha256=audited.accounting.result_provenance_sha256,
    )
end

function _calibration_report(payload)
    allocations = payload.allocations
    records = payload.records
    memory = getfield.(allocations, :max_rss_upper_bytes)
    requested = getfield.(allocations, :requested_memory_bytes)
    wall = getfield.(allocations, :requested_walltime_seconds)
    lines = [
        "# Route A Benchmark Calibration",
        "",
        "- Schema: 4",
        "- Campaign: $(payload.campaign_id)",
        "- Release: $(payload.release_git_commit)",
        "- Chains: $(length(records))",
        "- Completed allocations: $(length(allocations))",
        "- Allocation-grain memory samples: $(payload.resource_summary.memory_fit_sample_count)",
        "- Requested allocation memory range (bytes): $(minimum(requested))–$(maximum(requested))",
        "- Observed .batch MaxRSS range (bytes): $(minimum(memory))–$(maximum(memory))",
        "- Requested allocation walltime range (seconds): $(minimum(wall))–$(maximum(wall))",
        "- Conservative chain memory label: max_rss_upper_bytes",
        "",
        "Each shared allocation contributes exactly one correlated memory observation.",
        "Chain-local wall time and result bytes remain direct per-chain observations.",
        "",
    ]
    return join(lines, '\n')
end

"""Build one deterministic schema-4 calibration directory from immutable evidence."""
function build_calibration(
    campaign_path::AbstractString,
    task_paths_path::AbstractString,
    results_path::AbstractString,
    evidence_path::AbstractString,
    bundle_script_path::AbstractString,
    output_path::AbstractString;
    expected_campaign_id::AbstractString="benchmark-5c3e1a4868c36f8e",
    expected_task_count::Integer=328,
    expected_release_commit::AbstractString="69e02b31a5078afa531e2ff96d80cc35bd6a2124",
    config::ReconConfig=load_recon_config(),
    anchor_resolver::Union{Nothing,Function}=nothing,
    reference_selector::Union{Nothing,Function}=nothing,
    slope_required::Union{Nothing,Function}=nothing,
)
    output = abspath(output_path)
    ispath(output) || islink(output) ?
        throw(ArgumentError("calibration output directory already exists")) : nothing
    parent = dirname(output)
    isdir(parent) && !islink(parent) ||
        throw(ArgumentError("calibration output parent must be an existing non-symlink directory"))
    bundle_bytes = _regular_bytes(bundle_script_path, "bundle script")
    bundle_sha = bytes2hex(sha256(bundle_bytes))
    audited = audit_benchmark_inputs(
        campaign_path, task_paths_path, results_path, evidence_path;
        expected_campaign_id, expected_task_count, expected_release_commit)
    audited.accounting.bundle_script_sha256 == bundle_sha ||
        throw(ArgumentError("bundle script does not match captured evidence"))

    resolve_anchor = anchor_resolver === nothing ?
        task -> _production_anchor(task, config) : anchor_resolver
    select_reference = reference_selector === nothing ?
        task -> resolve_anchor(task) == 0.0 &&
            task.thermalization_sweeps == last(config.burnin_prefix_sweeps) :
        reference_selector
    require_slope = slope_required === nothing ?
        record -> record.anchor_x == 0.0 &&
            record.thermalization_sweeps == first(config.burnin_prefix_sweeps) &&
            record.replica <= config.benchmark_replicas &&
            !(record.c == config.primary_c && record.L == 48) : slope_required
    records = [derive_chain_record(
        audited, index;
        anchor_x=resolve_anchor(audited.tasks[index]),
        reference_diagnostics=Bool(select_reference(audited.tasks[index])),
    ) for index in eachindex(audited.tasks)]
    records = derive_three_anchor_slopes(records; slope_required=require_slope)
    allocations = [_allocation_json(allocation, audited.tasks) for allocation in audited.allocations]
    sort!(allocations; by=allocation -> allocation.allocation_key)
    json_records = _chain_json.(records)
    payload = (
        schema_version=4,
        kind="route_a_calibration",
        builder_version="route-a-calibration-builder-v1",
        sampling_unit="base_bin",
        campaign_id=audited.campaign.campaign_id,
        campaign_checksum=audited.campaign.campaign_checksum,
        campaign_manifest_sha256=audited.campaign_sha256,
        task_paths_sha256=audited.task_paths_sha256,
        release_git_commit=audited.campaign.git_commit,
        release_julia_manifest_sha256=audited.campaign.julia_manifest_sha256,
        release_julia_version=audited.campaign.julia_version,
        algorithm=audited.campaign.algorithm,
        observable_schema_version=audited.campaign.observable_schema_version,
        bundle_script_sha256=bundle_sha,
        accounting_snapshot_filename="sacct.psv",
        accounting_snapshot_sha256=audited.accounting.sacct_sha256,
        wrapper_inventory_filename="wrapper_inventory.psv",
        wrapper_inventory_sha256=audited.accounting.wrapper_inventory_sha256,
        result_provenance_filename="result_provenance.psv",
        result_provenance_sha256=audited.accounting.result_provenance_sha256,
        resource_summary=(
            memory_fit_sample_count=length(allocations),
            chain_count=length(json_records),
            max_rss_semantics="allocation_batch_upper_bound_per_chain",
        ),
        allocations=allocations,
        records=json_records,
    )

    second_audit = audit_benchmark_inputs(
        campaign_path, task_paths_path, results_path, evidence_path;
        expected_campaign_id, expected_task_count, expected_release_commit)
    _audit_fingerprint(second_audit) == _audit_fingerprint(audited) ||
        throw(ArgumentError("benchmark evidence changed during calibration build"))
    read(bundle_script_path) == bundle_bytes ||
        throw(ArgumentError("bundle script changed during calibration build"))

    stage = mktempdir(parent; prefix=".route-a-calibration-stage-")
    promoted = false
    try
        atomic_write_json(joinpath(stage, "calibration.json"), payload)
        write(joinpath(stage, "CALIBRATION.md"), _calibration_report(payload))
        mv(stage, output)
        promoted = true
        return output
    finally
        !promoted && isdir(stage) && rm(stage; recursive=true)
    end
end

function parse_calibration_args(arguments::Vector{String})
    names = ("--campaign", "--task-paths", "--results", "--accounting",
        "--bundle-script", "--output")
    length(arguments) == 2length(names) || throw(ArgumentError(
        "usage: build_route_a_calibration.jl --campaign PATH --task-paths PATH --results DIR --accounting DIR --bundle-script PATH --output DIR"))
    for (index, name) in enumerate(names)
        arguments[2index - 1] == name && !isempty(arguments[2index]) ||
            throw(ArgumentError("calibration arguments must appear in the documented order"))
    end
    return (
        campaign_path=arguments[2],
        task_paths_path=arguments[4],
        results_path=arguments[6],
        evidence_path=arguments[8],
        bundle_script_path=arguments[10],
        output_path=arguments[12],
    )
end

function _calibration_main()
    arguments = parse_calibration_args(copy(ARGS))
    build_calibration(
        arguments.campaign_path, arguments.task_paths_path, arguments.results_path,
        arguments.evidence_path, arguments.bundle_script_path, arguments.output_path)
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    try
        _calibration_main()
    catch error
        Base.display_error(stderr, catch_backtrace())
        exit(1)
    end
end
