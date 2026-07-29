using Dates
using Downloads
using TOML

include(joinpath(@__DIR__, "..", "src", "OLEProtocol.jl"))
using .OLEProtocol

const ROOT = normpath(joinpath(@__DIR__, ".."))

function require_equal(name, actual, expected)
    actual == expected ||
        throw(ArgumentError("$name changed: expected $expected, got $actual"))
    return nothing
end

function main()
    config_path = isempty(ARGS) ?
                  joinpath(ROOT, "configs", "baseline-49x648.toml") :
                  abspath(first(ARGS))
    config = TOML.parsefile(config_path)
    problem = config["problem"]
    destination = joinpath(ROOT, problem["qasm_path"])
    mkpath(dirname(destination))

    temporary_path = Downloads.download(problem["qasm_url"])
    text = read(temporary_path, String)
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
    require_equal("barrier count", protocol.barrier_count, problem["barriers"])
    require_equal("CZ count", counts["cz"], problem["cz_gates"])
    with_zeroed_perturbation(
        protocol;
        perturbation_angle = problem["perturbation"]["qasm_angle"],
        expected_count = problem["perturbation"]["gate_count"],
    )

    mv(temporary_path, destination; force = true)
    manifest_path = replace(destination, r"\.qasm$" => ".manifest.toml")
    manifest = Dict(
        "source" => Dict(
            "url" => problem["qasm_url"],
            "tracker_issue" => problem["tracker_issue"],
            "downloaded_at_utc" => string(now(UTC)),
        ),
        "identity" => Dict(
            "sha256" => qasm_sha256(text),
            "bytes" => ncodeunits(text),
        ),
        "circuit" => Dict(
            "qreg_size" => protocol.register_size,
            "active_qubits" => protocol.physical_labels,
            "physical_to_internal" => Dict(
                string(label) => internal
                for (label, internal) in protocol.physical_to_internal
            ),
            "layers" => length(protocol.layers),
            "barriers" => protocol.barrier_count,
            "gate_counts" => counts,
        ),
    )
    open(manifest_path, "w") do io
        TOML.print(io, manifest; sorted = true)
    end

    println("validated_qasm=$destination")
    println("manifest=$manifest_path")
    println("sha256=$(qasm_sha256(text)) active_qubits=$(length(protocol.physical_labels)) cz=$(counts["cz"])")
    flush(stdout)
    return nothing
end

main()
