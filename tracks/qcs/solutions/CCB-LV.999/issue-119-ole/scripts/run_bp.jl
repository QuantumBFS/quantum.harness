using Dates
using LinearAlgebra
using SHA
using TOML

include(joinpath(@__DIR__, "..", "src", "OLEProtocol.jl"))
include(joinpath(@__DIR__, "..", "src", "BPTNRunner.jl"))
include(joinpath(@__DIR__, "..", "src", "RunRecords.jl"))
using .OLEProtocol
using .BPTNRunner
using .RunRecords

const ROOT = normpath(joinpath(@__DIR__, ".."))

function cli_arguments(args)
    values = Dict{String, String}()
    flags = Set{String}()
    index = 1
    while index <= length(args)
        argument = args[index]
        startswith(argument, "--") ||
            throw(ArgumentError("unexpected positional argument: $argument"))
        if argument == "--execute"
            push!(flags, argument)
            index += 1
        else
            index < length(args) ||
                throw(ArgumentError("$argument requires a value"))
            values[argument] = args[index + 1]
            index += 2
        end
    end
    return values, flags
end

function require_equal(name, actual, expected)
    actual == expected ||
        throw(ArgumentError("$name changed: expected $expected, got $actual"))
    return nothing
end

function git_commit()
    try
        return readchomp(`git -C $ROOT rev-parse HEAD`)
    catch
        return "unknown"
    end
end

function main()
    values, flags = cli_arguments(ARGS)
    config_path = abspath(
        get(values, "--config", joinpath(ROOT, "configs", "baseline-49x648.toml")),
    )
    seed_id = parse(Int, get(values, "--seed", "1"))
    maxdim = parse(Int, get(values, "--chi", "64"))
    delta_mode = get(values, "--delta", "0.15")

    config = TOML.parsefile(config_path)
    problem = config["problem"]
    simulation = config["simulation"]
    seed_id in simulation["seed_ids"] ||
        throw(ArgumentError("seed $seed_id is outside the fixed seed bank"))
    maxdim in simulation["bond_dimensions"] ||
        throw(ArgumentError("chi=$maxdim is outside the configured scan"))

    qasm_path = joinpath(ROOT, problem["qasm_path"])
    isfile(qasm_path) ||
        throw(ArgumentError("missing QASM; run `julia --project=. scripts/fetch_inputs.jl`"))
    text = read(qasm_path, String)
    validate_qasm_identity(
        text;
        expected_sha256 = problem["qasm_sha256"],
        expected_bytes = problem["qasm_bytes"],
    )
    protocol = parse_qasm(text)
    counts = gate_counts(protocol)
    require_equal("qreg size", protocol.register_size, problem["qasm_register_size"])
    require_equal("active qubits", protocol.physical_labels, problem["active_qubits"])
    require_equal("layer count", length(protocol.layers), problem["layers"])
    require_equal("CZ count", counts["cz"], problem["cz_gates"])

    effective_delta = if delta_mode == "0.15"
        problem["delta"]
    elseif delta_mode == "0"
        protocol = with_zeroed_perturbation(
            protocol;
            perturbation_angle = problem["perturbation"]["qasm_angle"],
            expected_count = problem["perturbation"]["gate_count"],
        )
        0.0
    else
        throw(ArgumentError("--delta must be 0.15 or 0"))
    end

    fingerprint_material = join(
        [
            problem["qasm_sha256"],
            config["software"]["gate_convention"],
            "L=$(problem["L"])",
            "b=$(problem["b"])",
            "delta=$effective_delta",
            "observable=$(join(problem["observable_qubits"], ","))",
            "seed=$seed_id",
            "chi=$maxdim",
            "dtype=$(simulation["dtype"])",
            "cutoff=$(simulation["cutoff"])",
            "bp=$(simulation["bp_maxiter"]):$(simulation["bp_tolerance"])",
            "julia_threads=$(Threads.nthreads())",
            "blas_threads=$(BLAS.get_num_threads())",
        ],
        "|",
    )
    confirmation_token = first(bytes2hex(sha256(codeunits(fingerprint_material))), 16)

    println("problem=$(problem["name"])")
    println("qasm_sha256=$(problem["qasm_sha256"]) qreg=$(protocol.register_size) active=$(length(protocol.physical_labels)) layers=$(length(protocol.layers)) cz=$(counts["cz"])")
    println("convention=$(config["software"]["gate_convention"])")
    println("L=$(problem["L"]) b=$(problem["b"]) delta=$effective_delta observable=Z$(join(problem["observable_qubits"], " Z"))")
    println("seed=$seed_id namespace=$(simulation["seed_namespace"]) chi=$maxdim dtype=$(simulation["dtype"]) cutoff=$(simulation["cutoff"])")
    println("bp_maxiter=$(simulation["bp_maxiter"]) bp_tolerance=$(simulation["bp_tolerance"]) normalize=$(simulation["normalize_tensors"])")
    println("resource_cpu=$(Sys.CPU_NAME) julia_threads=$(Threads.nthreads()) blas_threads=$(BLAS.get_num_threads()) total_memory_bytes=$(Sys.total_memory())")
    println("confirmation_token=$confirmation_token")
    flush(stdout)

    if !("--execute" in flags)
        println("dry_run=true; no tensor-network computation was started")
        return nothing
    end
    get(values, "--confirm", "") == confirmation_token || throw(
        ArgumentError(
            "protocol not confirmed; rerun with --execute --confirm $confirmation_token",
        ),
    )

    dtype = simulation["dtype"] == "ComplexF64" ? ComplexF64 :
            simulation["dtype"] == "ComplexF32" ? ComplexF32 :
            throw(ArgumentError("unsupported dtype $(simulation["dtype"])"))
    delta_directory = effective_delta == 0 ? "delta-0" : "delta-0p15"
    output_directory = joinpath(
        ROOT,
        "runs",
        "baseline-49x648",
        delta_directory,
        "chi-$maxdim",
    )
    output_path = joinpath(output_directory, "seed-$(lpad(seed_id, 4, '0')).toml")
    partial_path = output_path * ".partial"
    checkpointed_layers = NamedTuple[]
    metadata = Dict(
        "status" => "running",
        "started_at_utc" => string(now(UTC)),
        "git_commit" => git_commit(),
        "qasm_sha256" => problem["qasm_sha256"],
        "tnqs_commit" => config["software"]["tnqs_commit"],
        "delta" => effective_delta,
        "chi" => maxdim,
        "confirmation_token" => confirmation_token,
        "cpu_name" => Sys.CPU_NAME,
        "julia_threads" => Threads.nthreads(),
        "blas_threads" => BLAS.get_num_threads(),
        "total_memory_bytes" => Sys.total_memory(),
    )
    checkpoint = record -> begin
        push!(checkpointed_layers, record)
        write_run_record(
            partial_path,
            (
                seed_id,
                completed_layers = length(checkpointed_layers),
                layers = checkpointed_layers,
            );
            run_metadata = metadata,
        )
    end

    result = run_seed(
        protocol;
        seed_namespace = simulation["seed_namespace"],
        seed_id,
        observable_labels = problem["observable_qubits"],
        maxdim,
        cutoff = simulation["cutoff"],
        dtype,
        bp_maxiter = simulation["bp_maxiter"],
        bp_tolerance = simulation["bp_tolerance"],
        normalize_tensors = simulation["normalize_tensors"],
        progress = true,
        layer_callback = checkpoint,
    )
    metadata["status"] = "complete"
    metadata["completed_at_utc"] = string(now(UTC))
    write_run_record(output_path, result; run_metadata = metadata)
    rm(partial_path; force = true)
    println("result=$output_path sample_value=$(result.sample_value) wall_s=$(result.wall_seconds) peak_rss_bytes=$(result.peak_rss_bytes)")
    flush(stdout)
    return nothing
end

main()
