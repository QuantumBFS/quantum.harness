#!/usr/bin/env julia

"""Benchmark PSD verification on Gram matrices already stored in a result.

This is a performance/audit helper, not a replacement for `verify_certificate`:
it checks only the stored Gram blocks and does not reconstruct the affine
identity or Farkas margin.
"""

using JSON3
using QuantumGapHierarchy

length(ARGS) in (1,2) || error(
    "usage: benchmark_projected_psd.jl RESULT_JSON [GAMMA]",
)
requested_gamma = length(ARGS)==2 ? parse(Float64,ARGS[2]) : nothing
payload = JSON3.read(read(ARGS[1],String))

function parse_qq(value)
    numerator_text,denominator_text = split(String(value),"//";limit=2)
    parse(BigInt,numerator_text)//parse(BigInt,denominator_text)
end

q23(value) = Q23(
    parse_qq(value.a),parse_qq(value.b),parse_qq(value.c),parse_qq(value.d),
)

trials = [
    trial for trial in payload.trials
    if hasproperty(trial.record,:dual_data) &&
       hasproperty(trial.record.dual_data,:projected_certificate) &&
       (requested_gamma === nothing || isapprox(Float64(trial.gamma),requested_gamma;atol=1e-12))
]
length(trials)==1 || error("expected one stored projected certificate, found $(length(trials))")
trial = only(trials)
matrices = trial.record.dual_data.projected_certificate.psd_matrices
println("gamma=$(trial.gamma), blocks=$(length(matrices))")

all_psd = true
total_seconds = 0.0
for (index,encoded) in enumerate(matrices)
    rows,columns = Int.(encoded.shape)
    rows==columns || error("Gram block $index is not square")
    matrix = reshape(Q23[q23(value) for value in encoded.column_major_data],rows,columns)
    interval_seconds = @elapsed interval_ok =
        QuantumGapHierarchy._arb_strictly_positive_definite(matrix)
    negative_seconds = 0.0
    exact_seconds = 0.0
    method = "interval LDL"
    ok = interval_ok
    if !interval_ok
        negative_seconds = @elapsed negative =
            QuantumGapHierarchy._exact_negative_witness(matrix)
        if negative
            method = "exact negative witness"
            ok = false
        else
            method = "pivoted exact LDL/Schur"
            exact_seconds = @elapsed ok,_ = QuantumGapHierarchy._exact_psd(matrix)
        end
    end
    block_seconds = interval_seconds+negative_seconds+exact_seconds
    global total_seconds += block_seconds
    global all_psd &= ok
    println(
        "block $index: $(rows)x$(columns), method=$method, PSD=$ok, " *
        "interval=$(round(interval_seconds;digits=3))s, " *
        "witness=$(round(negative_seconds;digits=3))s, " *
        "exact=$(round(exact_seconds;digits=3))s",
    )
end
println("all PSD=$all_psd, total=$(round(total_seconds;digits=3))s")
