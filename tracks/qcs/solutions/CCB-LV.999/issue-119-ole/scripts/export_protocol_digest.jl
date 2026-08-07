#!/usr/bin/env julia

include(joinpath(@__DIR__, "..", "src", "OLEProtocol.jl"))

using .OLEProtocol
using Printf
using SHA

function canonical_gate_records(protocol::OLEQASMProtocol)
    records = String[]
    gate_index = 0
    for (layer_position, layer) in enumerate(protocol.layers)
        layer_index = layer_position - 1
        for gate in layer
            angle_bits = isnothing(gate.angle) ? "-" :
                @sprintf("%016x", reinterpret(UInt64, Float64(gate.angle)))
            push!(
                records,
                "$(layer_index)|$(gate_index)|$(gate.name)|$(join(gate.qubits, ","))|$(angle_bits)",
            )
            gate_index += 1
        end
    end
    return records
end

function canonical_gate_digest(protocol::OLEQASMProtocol)
    payload = join(canonical_gate_records(protocol), "\n") * "\n"
    return bytes2hex(SHA.sha256(codeunits(payload)))
end

function _json_string(value::AbstractString)
    return "\"" * replace(value, "\\" => "\\\\", "\"" => "\\\"") * "\""
end

function _json_integer_array(values)
    return "[" * join(string.(values), ",") * "]"
end

function _json_output(protocol::OLEQASMProtocol)
    return "{" *
           "\"digest\":" * _json_string(canonical_gate_digest(protocol)) * "," *
           "\"gates\":" * string(sum(length, protocol.layers)) * "," *
           "\"layers\":" * string(length(protocol.layers)) * "," *
           "\"active_sites\":" * _json_integer_array(protocol.physical_labels) *
           "}"
end

length(ARGS) == 1 || error("usage: export_protocol_digest.jl INPUT.qasm")
protocol = parse_qasm(read(only(ARGS), String))
println(_json_output(protocol))
