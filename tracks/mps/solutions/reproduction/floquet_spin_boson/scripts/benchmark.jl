#!/usr/bin/env julia

using LinearAlgebra
using Random

const ROOT = normpath(joinpath(@__DIR__, ".."))
include(joinpath(ROOT, "src", "FloquetSpinBoson.jl"))
using .FloquetSpinBoson

json_value(x::AbstractString) = "\"" * replace(x, "\\" => "\\\\", "\"" => "\\\"") * "\""
json_value(x::Symbol) = json_value(String(x))
json_value(x::Real) = string(x)
json_value(x::Bool) = string(x)
json_value(::Nothing) = "null"
function json_value(x::NamedTuple)
    return "{" * join((json_value(String(k)) * ":" * json_value(v)
                       for (k, v) in pairs(x)), ",") * "}"
end

function benchmark_matrix_free(; bond_dimension=32, period_steps=20, samples=20)
    rng = MersenneTwister(0xF105)
    χ = Int(bond_dimension)
    q = randn(rng, ComplexF64, χ, 4, χ, 4)
    channels = [Matrix{ComplexF64}(I, 4, 4) for _ in 1:period_steps]
    operator = FloquetOperator(q, channels, channels)
    workspace = StepWorkspace(operator)
    x = randn(rng, ComplexF64, 4χ)
    y = similar(x)
    apply_period!(y, x, operator, workspace)

    allocation_bytes = @allocated apply_period!(y, x, operator, workspace)
    elapsed = @elapsed for _ in 1:samples
        apply_period!(y, x, operator, workspace)
    end
    estimate = estimate_resources(
        bond_dimension=χ,
        period_steps=period_steps,
        correlation_lag_steps=256,
        frequency_points=1,
    )
    return (; representation="matrix-free",
            bond_dimension=χ,
            augmented_dimension=4χ,
            period_steps,
            samples,
            seconds_per_period=elapsed / samples,
            allocation_bytes_per_period=allocation_bytes,
            dense_floquet_bytes=estimate.dense_floquet_bytes,
            julia_version=string(VERSION),
            julia_threads=Threads.nthreads(),
            blas_threads=BLAS.get_num_threads())
end

function benchmark_cli(args=ARGS)
    length(args) in (1, 3) ||
        error("usage: benchmark.jl <output_dir> [bond_dimension period_steps]")
    output = abspath(args[1])
    χ = length(args) == 3 ? parse(Int, args[2]) : 32
    M = length(args) == 3 ? parse(Int, args[3]) : 20
    mkpath(output)
    report = benchmark_matrix_free(; bond_dimension=χ, period_steps=M)
    path = joinpath(output, "allocation_report.json")
    open(path, "w") do io
        print(io, json_value(report))
        println(io)
    end
    println("allocation report: $(path)")
    flush(stdout)
    return report
end

if abspath(PROGRAM_FILE) == @__FILE__
    benchmark_cli()
end
