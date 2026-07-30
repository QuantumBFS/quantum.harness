#!/usr/bin/env julia

mutable struct JsonParser
    data::Vector{UInt8}
    position::Int
end

function skip_whitespace!(parser::JsonParser)
    while parser.position <= length(parser.data) &&
          parser.data[parser.position] in UInt8[0x20, 0x09, 0x0a, 0x0d]
        parser.position += 1
    end
end

function take_byte!(parser::JsonParser)
    parser.position <= length(parser.data) || error("unexpected end of JSON")
    byte = parser.data[parser.position]
    parser.position += 1
    byte
end

function expect_byte!(parser::JsonParser, expected::UInt8)
    actual = take_byte!(parser)
    actual == expected ||
        error("expected JSON byte $(Char(expected)), got $(Char(actual))")
end

function parse_json_string!(parser::JsonParser)
    expect_byte!(parser, UInt8('"'))
    output = IOBuffer()
    while true
        byte = take_byte!(parser)
        byte == UInt8('"') && return String(take!(output))
        if byte == UInt8('\\')
            escaped = take_byte!(parser)
            if escaped in UInt8['"', '\\', '/']
                write(output, escaped)
            elseif escaped == UInt8('b')
                write(output, UInt8(0x08))
            elseif escaped == UInt8('f')
                write(output, UInt8(0x0c))
            elseif escaped == UInt8('n')
                write(output, UInt8('\n'))
            elseif escaped == UInt8('r')
                write(output, UInt8('\r'))
            elseif escaped == UInt8('t')
                write(output, UInt8('\t'))
            elseif escaped == UInt8('u')
                digits = String(UInt8[take_byte!(parser) for _ in 1:4])
                codepoint = parse(UInt32, digits; base=16)
                write(output, string(Char(codepoint)))
            else
                error("unsupported JSON escape")
            end
        else
            byte >= 0x20 || error("control byte in JSON string")
            write(output, byte)
        end
    end
end

function parse_json_number!(parser::JsonParser)
    start = parser.position
    parser.data[parser.position] == UInt8('-') && (parser.position += 1)
    while parser.position <= length(parser.data) &&
          isdigit(Char(parser.data[parser.position]))
        parser.position += 1
    end
    parser.position > start || error("invalid JSON number")
    text = String(parser.data[start:parser.position-1])
    occursin(r"^-?(0|[1-9][0-9]*)$", text) ||
        error("manifest accepts integer JSON numbers only")
    parse(Int, text)
end

function parse_json_array!(parser::JsonParser)
    expect_byte!(parser, UInt8('['))
    values = Any[]
    skip_whitespace!(parser)
    if parser.position <= length(parser.data) &&
       parser.data[parser.position] == UInt8(']')
        parser.position += 1
        return values
    end
    while true
        push!(values, parse_json_value!(parser))
        skip_whitespace!(parser)
        separator = take_byte!(parser)
        separator == UInt8(']') && return values
        separator == UInt8(',') || error("expected comma or array end")
        skip_whitespace!(parser)
    end
end

function parse_json_object!(parser::JsonParser)
    expect_byte!(parser, UInt8('{'))
    object = Dict{String,Any}()
    skip_whitespace!(parser)
    if parser.position <= length(parser.data) &&
       parser.data[parser.position] == UInt8('}')
        parser.position += 1
        return object
    end
    while true
        key = parse_json_string!(parser)
        haskey(object, key) && error("duplicate JSON key $key")
        skip_whitespace!(parser)
        expect_byte!(parser, UInt8(':'))
        skip_whitespace!(parser)
        object[key] = parse_json_value!(parser)
        skip_whitespace!(parser)
        separator = take_byte!(parser)
        separator == UInt8('}') && return object
        separator == UInt8(',') || error("expected comma or object end")
        skip_whitespace!(parser)
    end
end

function parse_literal!(parser::JsonParser, literal::String, value)
    for byte in codeunits(literal)
        expect_byte!(parser, byte)
    end
    value
end

function parse_json_value!(parser::JsonParser)
    skip_whitespace!(parser)
    parser.position <= length(parser.data) || error("unexpected end of JSON")
    byte = parser.data[parser.position]
    byte == UInt8('{') && return parse_json_object!(parser)
    byte == UInt8('[') && return parse_json_array!(parser)
    byte == UInt8('"') && return parse_json_string!(parser)
    byte == UInt8('t') && return parse_literal!(parser, "true", true)
    byte == UInt8('f') && return parse_literal!(parser, "false", false)
    byte == UInt8('n') && return parse_literal!(parser, "null", nothing)
    (byte == UInt8('-') || isdigit(Char(byte))) && return parse_json_number!(parser)
    error("unexpected JSON byte $(Char(byte))")
end

function parse_json(path::String)
    parser = JsonParser(read(path), 1)
    value = parse_json_value!(parser)
    skip_whitespace!(parser)
    parser.position == length(parser.data) + 1 || error("trailing JSON content")
    value
end

function required(object::Dict{String,Any}, key::String, type)
    haskey(object, key) || error("missing manifest field $key")
    value = object[key]
    value isa type || error("manifest field $key has wrong type")
    value
end

function materialize_circuit(root::String, case::Dict{String,Any}, directory::String)
    circuit = required(case, "circuit", Dict{String,Any})
    kind = required(circuit, "kind", String)
    if kind == "official_file"
        return joinpath(root, "vendor", "occam-circuit",
                        required(circuit, "path", String))
    end
    bits = required(circuit, "bits", Int)
    bits > 0 || error("generated circuit bits must be positive")
    output = joinpath(directory, required(case, "name", String) * ".txt")
    command = kind == "generated_adder" ? "generate-adder" :
              kind == "generated_multiplier" ? "generate-multiplier" :
              error("unknown circuit kind $kind")
    run(`$(joinpath(root, "target", "release", "occam71_rust")) $command --bits $bits --output $output`)
    output
end

function csv_shape(path::String)
    lines = filter(!isempty, strip.(readlines(path)))
    !isempty(lines) && lines[1] == "input,output" || error("bad dataset header")
    rows = lines[2:end]
    !isempty(rows) || error("dataset has no samples")
    widths = split(rows[1], ",")
    length(widths) == 2 || error("bad dataset row")
    for row in rows
        fields = split(row, ",")
        length(fields) == 2 || error("bad dataset row")
        length(fields[1]) == length(widths[1]) || error("input width mismatch")
        length(fields[2]) == length(widths[2]) || error("output width mismatch")
    end
    length(rows), length(widths[2])
end

function capture_verifier(root::String, circuit::String, dataset::String)
    command = `julia $(joinpath(root, "vendor", "occam-circuit", "verify.jl")) $circuit $dataset`
    output = read(command, String)
    gates = parse(Int, only(match(r"gates:\s+([0-9]+)", output).captures))
    samples = parse(Int, only(match(r"samples:\s+([0-9]+)", output).captures))
    exact = parse(Float64, only(match(r"exact-match acc:\s+([0-9.]+)", output).captures))
    bit = parse(Float64, only(match(r"bit accuracy:\s+([0-9.]+)", output).captures))
    gates, samples, exact, bit
end

function main()
    root = normpath(joinpath(@__DIR__, ".."))
    manifest = parse_json(joinpath(root, "tests", "oracles", "occam-v1.json"))
    required(manifest, "schema_version", Int) == 1 ||
        error("unsupported oracle manifest schema")
    archive = required(manifest, "archive", Dict{String,Any})
    required(archive, "sha256", String) ==
        "c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b" ||
        error("unexpected archive checksum")
    cases = required(manifest, "cases", Vector)
    names = Set{String}()
    mktempdir() do directory
        for raw_case in cases
            raw_case isa Dict{String,Any} || error("case must be an object")
            case = raw_case::Dict{String,Any}
            name = required(case, "name", String)
            name in names && error("duplicate oracle case $name")
            push!(names, name)
            circuit = materialize_circuit(root, case, directory)
            dataset = joinpath(root, "vendor", "occam-circuit",
                               required(case, "dataset", String))
            csv_samples, output_width = csv_shape(dataset)
            gates, samples, exact, bit = capture_verifier(root, circuit, dataset)
            expected_samples = required(case, "samples", Int)
            total_bits = required(case, "total_bits", Int)
            csv_samples == expected_samples || error("$name sample count mismatch")
            total_bits == expected_samples * output_width ||
                error("$name total bit count mismatch")
            gates == required(case, "gates", Int) || error("$name gate mismatch")
            samples == expected_samples || error("$name verifier sample mismatch")
            expected_exact = required(case, "exact_matches", Int) / expected_samples
            expected_bit = required(case, "correct_bits", Int) / total_bits
            isapprox(exact, expected_exact; atol=5e-7) ||
                error("$name exact accuracy mismatch")
            isapprox(bit, expected_bit; atol=5e-7) ||
                error("$name bit accuracy mismatch")
            println("oracle $name: verified")
        end
    end
end

main()
