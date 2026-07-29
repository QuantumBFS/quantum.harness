#!/usr/bin/env julia
# Occam's Circuit challenge — dataset generator.
# Stdlib only (SHA). Deterministic: same args → identical files, independent of Julia version.
#
# Usage:
#   julia generate.jl <function> <nbits> <ntrain> <ntest> <seed> <outdir>
#   julia generate.jl mul 6 1200 1500 303 datasets/mystery-C
#
# Encoding (documented in the challenge spec):
#   input  = 2n characters, x bits then y bits, LSB first (char i of a block = bit i-1)
#   output = m characters, LSB first
#   train.csv:        input,output
#   test_inputs.csv:  input
#   secret/test_outputs.csv, secret/ground_truth.txt  — organizer-only, never commit

using SHA

# ---- deterministic RNG (splitmix64) ----
mutable struct SM64; s::UInt64; end
function nextu64!(r::SM64)
    r.s += 0x9e3779b97f4a7c15
    z = r.s
    z = (z ⊻ (z >> 30)) * 0xbf58476d1ce4e5b9
    z = (z ⊻ (z >> 27)) * 0x94d049bb133111eb
    return z ⊻ (z >> 31)
end

# Fisher-Yates shuffle of 0:total-1 using splitmix64 (rejection sampling, no modulo bias)
function detshuffle(total::Int, seed::UInt64)
    r = SM64(seed)
    a = collect(0:total-1)
    for i in total:-1:2
        lim = typemax(UInt64) - typemax(UInt64) % UInt64(i)
        v = nextu64!(r)
        while v >= lim
            v = nextu64!(r)
        end
        j = Int(v % UInt64(i)) + 1
        a[i], a[j] = a[j], a[i]
    end
    return a
end

# ---- function registry: name => (f(x,y), output width m given n) ----
outwidth(name, n) = Dict(
    "add"     => n + 1,
    "mul"     => 2n,
    "sos"     => 2n + 1,   # x^2 + y^2
    "absdiff" => n,
)[name]

evalf(name, x, y) = Dict(
    "add"     => (x, y) -> x + y,
    "mul"     => (x, y) -> x * y,
    "sos"     => (x, y) -> x^2 + y^2,
    "absdiff" => (x, y) -> abs(x - y),
)[name](x, y)

bitstr(v::Int, k::Int) = join(((v >> i) & 1 for i in 0:k-1))

function main()
    length(ARGS) == 6 || error("usage: julia generate.jl <function> <nbits> <ntrain> <ntest> <seed> <outdir>")
    name = ARGS[1]
    n, ntrain, ntest, seed = parse.(Int, ARGS[2:5])
    outdir = ARGS[6]
    m = outwidth(name, n)
    total = 4^n
    ntrain + ntest <= total || error("ntrain + ntest = $(ntrain+ntest) exceeds input space $total")

    perm = detshuffle(total, UInt64(seed))
    mkpath(joinpath(outdir, "secret"))

    encode(idx) = begin
        x, y = idx & (2^n - 1), idx >> n
        (bitstr(x, n) * bitstr(y, n), bitstr(evalf(name, x, y), m))
    end

    open(joinpath(outdir, "train.csv"), "w") do io
        println(io, "input,output")
        for idx in perm[1:ntrain]
            i, o = encode(idx)
            println(io, i, ",", o)
        end
    end

    testio = IOBuffer()
    open(joinpath(outdir, "test_inputs.csv"), "w") do io
        println(io, "input")
        println(testio, "input,output")
        for idx in perm[ntrain+1:ntrain+ntest]
            i, o = encode(idx)
            println(io, i)
            println(testio, i, ",", o)
        end
    end
    testbytes = take!(testio)
    write(joinpath(outdir, "secret", "test_outputs.csv"), testbytes)
    commitment = bytes2hex(sha256(testbytes))

    open(joinpath(outdir, "secret", "ground_truth.txt"), "w") do io
        println(io, "function: $name   nbits: $n   m: $m   seed: $seed")
        println(io, "ntrain: $ntrain   ntest: $ntest   input space: $total")
    end
    open(joinpath(outdir, "commitment.sha256"), "w") do io
        println(io, commitment, "  test_outputs.csv")
    end

    println("[$outdir] f=$name n=$n m=$m  train=$ntrain test=$ntest of $total ",
            "($(round(100ntrain/total, digits=1))% observed)")
    println("  sha256(test_outputs.csv) = $commitment")
end

main()
