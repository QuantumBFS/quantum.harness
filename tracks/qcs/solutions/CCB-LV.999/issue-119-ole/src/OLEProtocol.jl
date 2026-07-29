module OLEProtocol

using SHA

export OLEQASMProtocol,
    QASMGate,
    basis_bits,
    gate_counts,
    observable_parity,
    parse_qasm,
    qasm_sha256,
    tnqs_layers,
    validate_qasm_identity,
    with_zeroed_perturbation

struct QASMGate
    name::String
    qubits::Vector{Int}
    angle::Union{Nothing, Float64}
end

struct OLEQASMProtocol
    register_size::Int
    layers::Vector{Vector{QASMGate}}
    physical_labels::Vector{Int}
    physical_to_internal::Dict{Int, Int}
    barrier_count::Int
end

const _NUMBER_PATTERN = raw"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"

function _parse_angle(expression::AbstractString)
    compact = replace(strip(expression), r"\s+" => "")
    if occursin(Regex("^[-+]?" * _NUMBER_PATTERN * "\$"), compact)
        value = tryparse(Float64, compact)
        value === nothing && throw(ArgumentError("invalid numeric angle: $expression"))
        isfinite(value) || throw(ArgumentError("non-finite angle: $expression"))
        return value
    end

    matched = match(
        Regex(
            "^([+-]?)(?:(" * _NUMBER_PATTERN * ")\\*)?pi(?:/(" *
            _NUMBER_PATTERN * "))?\$",
        ),
        compact,
    )
    matched === nothing && throw(ArgumentError("unsupported angle expression: $expression"))

    sign = matched.captures[1] == "-" ? -1.0 : 1.0
    numerator = isnothing(matched.captures[2]) ? 1.0 : parse(Float64, matched.captures[2])
    denominator = isnothing(matched.captures[3]) ? 1.0 : parse(Float64, matched.captures[3])
    iszero(denominator) && throw(ArgumentError("zero denominator in angle: $expression"))
    return sign * numerator * π / denominator
end

function _check_qubits(qubits::Vector{Int}, register_size::Int, line_number::Int)
    for qubit in qubits
        0 <= qubit < register_size ||
            throw(ArgumentError("q[$qubit] is outside qreg at line $line_number"))
    end
    return nothing
end

"""
    parse_qasm(text)

Parse the strict OpenQASM 2 subset used by the official OLE input. Barriers
become layer boundaries. Only `rx`, `rz`, `cz`, `s`, `sdg`, `sx`, and `sxdg`
are accepted, so an upstream protocol change fails loudly.
"""
function parse_qasm(text::AbstractString)
    register_size = nothing
    layers = Vector{Vector{QASMGate}}()
    current_layer = QASMGate[]
    barrier_count = 0
    saw_header = false
    saw_include = false

    for (line_number, original_line) in enumerate(eachline(IOBuffer(text)))
        line = strip(first(split(original_line, "//"; limit = 2)))
        isempty(line) && continue

        if line == "OPENQASM 2.0;"
            saw_header && throw(ArgumentError("duplicate OPENQASM header at line $line_number"))
            saw_header = true
            continue
        elseif line == "include \"qelib1.inc\";"
            saw_include && throw(ArgumentError("duplicate qelib include at line $line_number"))
            saw_include = true
            continue
        end

        qreg_match = match(r"^qreg\s+q\[(\d+)\];$", line)
        if qreg_match !== nothing
            register_size === nothing ||
                throw(ArgumentError("duplicate qreg declaration at line $line_number"))
            register_size = parse(Int, only(qreg_match.captures))
            register_size > 0 || throw(ArgumentError("qreg must be nonempty"))
            continue
        end

        register_size === nothing &&
            throw(ArgumentError("gate before qreg declaration at line $line_number"))

        if startswith(line, "barrier ")
            occursin(r"^barrier\s+q\[\d+\](?:,q\[\d+\])*\s*;$", line) ||
                throw(ArgumentError("malformed barrier at line $line_number"))
            !isempty(current_layer) && push!(layers, current_layer)
            current_layer = QASMGate[]
            barrier_count += 1
            continue
        end

        parameterized = match(r"^(rx|rz)\(([^()]*)\)\s+q\[(\d+)\];$", line)
        if parameterized !== nothing
            name, angle_expression, qubit_text = parameterized.captures
            qubits = [parse(Int, qubit_text)]
            _check_qubits(qubits, register_size, line_number)
            push!(current_layer, QASMGate(name, qubits, _parse_angle(angle_expression)))
            continue
        end

        fixed = match(r"^(s|sdg|sx|sxdg)\s+q\[(\d+)\];$", line)
        if fixed !== nothing
            name, qubit_text = fixed.captures
            qubits = [parse(Int, qubit_text)]
            _check_qubits(qubits, register_size, line_number)
            push!(current_layer, QASMGate(name, qubits, nothing))
            continue
        end

        controlled_z = match(r"^cz\s+q\[(\d+)\],q\[(\d+)\];$", line)
        if controlled_z !== nothing
            qubits = parse.(Int, controlled_z.captures)
            qubits[1] == qubits[2] &&
                throw(ArgumentError("cz repeats q[$(qubits[1])] at line $line_number"))
            _check_qubits(qubits, register_size, line_number)
            push!(current_layer, QASMGate("cz", qubits, nothing))
            continue
        end

        throw(ArgumentError("unsupported OpenQASM statement at line $line_number: $line"))
    end

    saw_header || throw(ArgumentError("missing OPENQASM 2.0 header"))
    saw_include || throw(ArgumentError("missing qelib1.inc include"))
    register_size === nothing && throw(ArgumentError("missing qreg declaration"))
    !isempty(current_layer) && push!(layers, current_layer)
    isempty(layers) && throw(ArgumentError("QASM contains no gates"))

    physical_labels = sort!(unique!(reduce(vcat, [gate.qubits for layer in layers for gate in layer])))
    mapping = Dict(label => index for (index, label) in enumerate(physical_labels))
    return OLEQASMProtocol(register_size, layers, physical_labels, mapping, barrier_count)
end

function gate_counts(protocol::OLEQASMProtocol)
    counts = Dict{String, Int}()
    for gate in Iterators.flatten(protocol.layers)
        counts[gate.name] = get(counts, gate.name, 0) + 1
    end
    return counts
end

function _tnqs_gate(gate::QASMGate)
    gate.name == "rx" && return ("Rx", gate.qubits, something(gate.angle))
    gate.name == "rz" && return ("Rz", gate.qubits, something(gate.angle))
    gate.name == "cz" && return ("CZ", gate.qubits)
    gate.name == "s" && return ("Rz", gate.qubits, π / 2)
    gate.name == "sdg" && return ("Rz", gate.qubits, -π / 2)
    gate.name == "sx" && return ("Rx", gate.qubits, π / 2)
    gate.name == "sxdg" && return ("Rx", gate.qubits, -π / 2)
    throw(ArgumentError("no TNQS translation for gate $(gate.name)"))
end

tnqs_layers(protocol::OLEQASMProtocol) =
    [[_tnqs_gate(gate) for gate in layer] for layer in protocol.layers]

function with_zeroed_perturbation(
    protocol::OLEQASMProtocol;
    perturbation_angle::Real,
    expected_count::Integer,
)
    replacement_count = 0
    new_layers = [
        [
            if gate.name == "rz" &&
                    !isnothing(gate.angle) &&
                    isapprox(gate.angle, perturbation_angle; atol = 8eps(Float64), rtol = 0)
                replacement_count += 1
                QASMGate(gate.name, copy(gate.qubits), 0.0)
            else
                QASMGate(gate.name, copy(gate.qubits), gate.angle)
            end
            for gate in layer
        ]
        for layer in protocol.layers
    ]
    replacement_count == expected_count || throw(
        ArgumentError(
            "expected $expected_count perturbation gates at angle $perturbation_angle, " *
            "found $replacement_count",
        ),
    )
    return OLEQASMProtocol(
        protocol.register_size,
        new_layers,
        copy(protocol.physical_labels),
        copy(protocol.physical_to_internal),
        protocol.barrier_count,
    )
end

qasm_sha256(text::AbstractString) = bytes2hex(sha256(codeunits(text)))

function validate_qasm_identity(
    text::AbstractString;
    expected_sha256::AbstractString,
    expected_bytes::Integer,
)
    actual_bytes = ncodeunits(text)
    actual_bytes == expected_bytes || throw(
        ArgumentError("QASM byte count changed: expected $expected_bytes, got $actual_bytes"),
    )
    actual_sha256 = qasm_sha256(text)
    lowercase(actual_sha256) == lowercase(expected_sha256) || throw(
        ArgumentError(
            "QASM SHA-256 changed: expected $expected_sha256, got $actual_sha256",
        ),
    )
    return nothing
end

function basis_bits(namespace::AbstractString, seed::Integer, physical_labels)
    seed >= 0 || throw(ArgumentError("seed id must be nonnegative"))
    return [
        Int(first(sha256(codeunits("$namespace:$seed:$label"))) & 0x01)
        for label in physical_labels
    ]
end

function observable_parity(bits_by_label::AbstractDict, observable_labels)
    parity = 1
    for label in observable_labels
        haskey(bits_by_label, label) ||
            throw(ArgumentError("observable label $label is absent from the basis state"))
        bit = bits_by_label[label]
        bit in (0, 1) || throw(ArgumentError("basis bit for label $label must be 0 or 1"))
        parity *= iszero(bit) ? 1 : -1
    end
    return parity
end

end
