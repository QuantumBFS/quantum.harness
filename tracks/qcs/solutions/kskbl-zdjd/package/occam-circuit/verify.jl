#!/usr/bin/env julia
# Occam's Circuit challenge — circuit verifier & scorer. Stdlib only.
#
# Usage:
#   julia verify.jl <circuit.txt> <dataset.csv>
#     dataset.csv has header "input,output" (train.csv, or secret/test_outputs.csv for organizers)
#
# Circuit format (plain text, one statement per line, '#' comments):
#   INPUTS 12                      # number of input wires; inputs are x1..x12 (LSB-first, x block then y block)
#   w1 = AND x1 x7                 # fanin-2 gates: AND OR XOR NAND NOR XNOR
#   w2 = XOR ~w1 x2                # '~' negates an operand (inverters are FREE)
#   OUTPUTS w2 w5 ~w9              # m output wires, LSB first ('~' allowed, free)
#
# Score = (exact-match accuracy, bit accuracy, gate count). Fewer gates breaks ties.

function parseoperand(tok, ninputs)
    neg = startswith(tok, "~")
    neg && (tok = tok[2:end])
    if startswith(tok, "x")
        i = parse(Int, tok[2:end])
        1 <= i <= ninputs || error("input $tok out of range")
        return (:input, i, neg)
    elseif startswith(tok, "w")
        return (:wire, parse(Int, tok[2:end]), neg)
    end
    error("bad operand: $tok")
end

const OPS = Dict(
    "AND"  => (a, b) -> a & b,   "OR"   => (a, b) -> a | b,   "XOR"  => (a, b) -> a ⊻ b,
    "NAND" => (a, b) -> !(a & b), "NOR" => (a, b) -> !(a | b), "XNOR" => (a, b) -> !(a ⊻ b),
)

function main()
    length(ARGS) == 2 || error("usage: julia verify.jl <circuit.txt> <dataset.csv>")
    lines = [strip(replace(l, r"#.*" => "")) for l in readlines(ARGS[1])]
    filter!(!isempty, lines)

    ninputs = 0
    gates = Tuple{Int,Function,Tuple,Tuple}[]   # (wire id, op, operand a, operand b)
    outputs = Tuple[]
    defined = Set{Int}()
    for l in lines
        toks = split(l)
        if toks[1] == "INPUTS"
            ninputs = parse(Int, toks[2])
        elseif toks[1] == "OUTPUTS"
            outputs = [parseoperand(t, ninputs) for t in toks[2:end]]
        else
            length(toks) == 5 && toks[2] == "=" || error("bad gate line: $l")
            w = parse(Int, toks[1][2:end])
            w ∈ defined && error("wire w$w defined twice")
            op = get(OPS, toks[3], nothing)
            op === nothing && error("unknown op $(toks[3]) (allowed: $(join(keys(OPS), ' ')))")
            a, b = parseoperand(toks[4], ninputs), parseoperand(toks[5], ninputs)
            for o in (a, b)
                o[1] == :wire && o[2] ∉ defined && error("w$(o[2]) used before definition (line: $l)")
            end
            push!(gates, (w, op, a, b))
            push!(defined, w)
        end
    end
    ninputs > 0 || error("missing INPUTS line")
    !isempty(outputs) || error("missing OUTPUTS line")

    rows = readlines(ARGS[2])[2:end]
    nex, exact, bitok, bittot = 0, 0, 0, 0
    for row in rows
        isempty(strip(row)) && continue
        inp, out = split(strip(row), ",")
        length(inp) == ninputs || error("dataset input width $(length(inp)) ≠ INPUTS $ninputs")
        vals = Dict{Int,Bool}()
        getv(o) = begin
            v = o[1] == :input ? inp[o[2]] == '1' : vals[o[2]]
            o[3] ? !v : v
        end
        for (w, op, a, b) in gates
            vals[w] = op(getv(a), getv(b))
        end
        pred = [getv(o) for o in outputs]
        truth = [c == '1' for c in out]
        length(pred) == length(truth) || error("circuit has $(length(pred)) outputs, dataset has $(length(truth))")
        nex += 1
        exact += pred == truth
        bitok += count(pred .== truth)
        bittot += length(truth)
    end

    println("gates:            ", length(gates), "  (inverters free)")
    println("samples:          ", nex)
    println("exact-match acc:  ", round(exact / nex, digits=6))
    println("bit accuracy:     ", round(bitok / bittot, digits=6))
end

main()
