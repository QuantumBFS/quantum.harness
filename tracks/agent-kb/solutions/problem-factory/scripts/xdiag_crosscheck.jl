# Cross-check the sawtooth localized-magnon anchors with the harness's XDiag
# stack, against pf/ed.py (scipy). Same physics, independent code — agreement
# upgrades the anchors to "Harness anchor" provenance.
#
# Run: julia --project=julia-env tracks/agent-kb/solutions/problem-factory/scripts/xdiag_crosscheck.jl
#
# Anchors (issue #112): flat band eps=-4*J1 at J2=2*J1; total GS degeneracy at
# h_sat=4*J1 equals Lucas(6)=18 (N=12); Monti-Suto point J2=J1 is 2-fold.

using XDiag
using LinearAlgebra
using Printf

const N = 12
const NC = div(N, 2)

# Sawtooth bonds, Julia sites count from 1. Base A_i = site 2i-1, apex B_i = 2i.
# J1: (A_i, A_{i+1}); J2: (A_i, B_i) and (B_i, A_{i+1}).
function sawtooth_ops(j1, j2, h)
    ops = OpSum()
    for i in 1:NC
        a, b, anext = 2i - 1, 2i, mod1(2i + 1, N)
        ops += "J1" * Op("SdotS", [a, anext])
        ops += "J2" * Op("SdotS", [a, b])
        ops += "J2" * Op("SdotS", [b, anext])
    end
    for i in 1:N
        ops += "h" * Op("Sz", [i])
    end
    ops["J1"] = j1
    ops["J2"] = j2
    ops["h"] = -h
    return ops
end

eigvals_sector(ops, nup) = begin
    block = Spinhalf(N, nup)
    eigen(Symmetric(matrix(ops, block))).values
end

function main()
    fails = 0

    # 1. Flat band at J2=2*J1: lowest NC one-magnon levels at E_pol - 4
    ops = sawtooth_ops(1.0, 2.0, 0.0)
    e_pol = (1.0 + 2 * 2.0) * NC / 4
    w = eigvals_sector(ops, N - 1)
    band = w[1:NC] .- e_pol
    ok = maximum(abs.(band .+ 4.0)) < 1e-8
    @printf("flat band: mean=%.10f spread=%.2e -> %s\n",
            sum(band) / NC, maximum(band) - minimum(band), ok ? "PASS" : "FAIL")
    fails += !ok

    # 2. Total GS degeneracy at h_sat = 4*J1 equals Lucas(6) = 18
    ops = sawtooth_ops(1.0, 2.0, 4.0)
    e0 = e_pol - 4.0 * N / 2   # polarized-state energy at h_sat = -16.5
    total = 0
    for k in 0:NC
        w = eigvals_sector(ops, N - k)
        total += count(x -> abs(x - e0) < 1e-8, w)
    end
    ok = total == 18
    @printf("h_sat degeneracy: %d (expect 18) -> %s\n", total, ok ? "PASS" : "FAIL")
    fails += !ok

    # 3. Monti-Suto point J2=J1: exactly 2-fold ground state, gapped above
    ops = sawtooth_ops(1.0, 1.0, 0.0)
    w = eigvals_sector(ops, NC)
    ok = (w[2] - w[1] < 1e-10) && (w[3] - w[1] > 1e-3)
    @printf("monti-suto: E2-E1=%.2e E3-E1=%.6f -> %s\n",
            w[2] - w[1], w[3] - w[1], ok ? "PASS" : "FAIL")
    fails += !ok

    println(fails == 0 ? "ALL XDIAG CROSS-CHECKS PASS" : "$fails CHECK(S) FAILED")
    exit(fails == 0 ? 0 : 1)
end

main()
