#!/usr/bin/env julia

using SHA

function capture_verifier(verifier::String, circuit::String, dataset::String)
    command = `$(Base.julia_cmd()) --startup-file=no $verifier $circuit $dataset`
    output = read(command, String)
    exact_match = match(r"exact-match acc:\s+([0-9.]+)", output)
    bit_match = match(r"bit accuracy:\s+([0-9.]+)", output)
    exact_match === nothing && error("official verifier omitted exact-match accuracy")
    bit_match === nothing && error("official verifier omitted bit accuracy")
    exact = parse(Float64, only(exact_match.captures))
    bit = parse(Float64, only(bit_match.captures))
    exact == 1.0 || error("exact-match accuracy is $exact for $dataset")
    bit == 1.0 || error("bit accuracy is $bit for $dataset")
end

function expected_commitment(path::String)
    fields = split(read(path, String))
    length(fields) == 2 || error("malformed commitment $path")
    fields[2] == "test_outputs.csv" || error("unexpected commitment filename")
    digest = fields[1]
    occursin(r"^[0-9a-f]{64}$", digest) || error("malformed SHA-256 in $path")
    digest
end

function verify_case(root::String, name::String)
    solution = joinpath(root, "challenge-71-occam", "solutions", "rewrite-it-in-rust")
    official = joinpath(root, "vendor", "occam-circuit")
    circuit = joinpath(solution, "circuits", "$name.txt")
    training = joinpath(official, "datasets", name, "train.csv")
    prediction = joinpath(solution, "predictions", name, "test_outputs.csv")
    commitment = joinpath(official, "datasets", name, "commitment.sha256")
    verifier = joinpath(official, "verify.jl")

    actual = bytes2hex(sha256(read(prediction)))
    expected = expected_commitment(commitment)
    actual == expected ||
        error("$name prediction hash mismatch: expected $expected, got $actual")
    capture_verifier(verifier, circuit, training)
    capture_verifier(verifier, circuit, prediction)
    println("$name: Julia training and prediction verification passed ($actual)")
end

function main()
    root = normpath(joinpath(@__DIR__, ".."))
    for suffix in ("A", "B", "C", "D")
        verify_case(root, "mystery-$suffix")
    end
end

main()
