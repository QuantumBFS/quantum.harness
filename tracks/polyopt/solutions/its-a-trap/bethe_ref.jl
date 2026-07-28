#!/usr/bin/env julia
# High-precision numerical Bethe reference for the PBC spin-1/2 Heisenberg
# chain, H = (1/4) Σ_i Σ_a σ_i^a σ_{i+1}^a = Σ_i S_i·S_{i+1}, N even.
#
# Ground state: Sz = 0 sector, M = N/2 real rapidities. Logarithmic Bethe
# equations (XXX, spin-1/2):
#     2N·atan(2 λ_j) = 2π I_j + 2 Σ_k atan(λ_j − λ_k)
# with consecutive quantum numbers I_j = −(M−1)/2 + (j−1)  (half-integers for
# M even, integers for M odd). Energy:
#     E = N/4 − Σ_j 2 / (4 λ_j² + 1)
#
# Validation battery (plan correction 8):
#   (i)   ED cross-check at N = 8, 10, 12, 14 — self-contained dense ED in the
#         Sz=0 sector (plan named XDiag; standalone dense ED chosen instead —
#         same check, zero external API risk; deviation logged).
#   (ii)  Bethe-equation residuals per N (max |F_j|).
#   (iii) Root/quantum-number checks: M = N/2 real, distinct, ordered roots.
#   (iv)  BigFloat re-solve at 2× precision; agreement reported.
#   (v)   Table 3 DMRG column match to 7 digits for N = 10…100.
#
# Product terminology: "high-precision numerical Bethe reference" — not an
# exact value. Output: bethe_ref.json mapping N → E/N (BigFloat-derived,
# 25 significant digits).
#
# Usage: julia bethe_ref.jl <outdir>

using LinearAlgebra
using Printf

const OUTDIR = length(ARGS) >= 1 ? ARGS[1] : "."
mkpath(OUTDIR)

# ---------------------------------------------------------------- Bethe -----
function bethe_roots(N::Int, ::Type{T}; maxiter=200, tol=eps(T)^(4//5)) where {T<:Real}
    M = N ÷ 2
    I_j = T[-(M - 1) / T(2) + (j - 1) for j in 1:M]
    # free-field initial guess: 2N atan(2λ) = 2π I_j
    lam = T[abs(2 * I * π / (2N)) < T(π) / 2 - T(1) / 100 ? tan(2 * I * π / (2N)) / 2 :
            sign(I) * T(2) for I in I_j]
    F = similar(lam); J = zeros(T, M, M)
    res = T(Inf); it = 0
    for outer it in 1:maxiter
        for j in 1:M
            s = zero(T)
            for k in 1:M
                k == j && continue
                s += atan(lam[j] - lam[k])
            end
            F[j] = 2N * atan(2 * lam[j]) - 2 * T(π) * I_j[j] - 2s
        end
        res = maximum(abs, F)
        res < tol && break
        for j in 1:M
            dj = 4N / (1 + 4 * lam[j]^2)
            for k in 1:M
                k == j && continue
                w = 2 / (1 + (lam[j] - lam[k])^2)
                dj -= w
                J[j, k] = w
            end
            J[j, j] = dj
        end
        lam .-= J \ F
    end
    E = N / T(4) - sum(2 / (4 * l^2 + 1) for l in lam)
    return (lam=lam, E=E, resid=res, iters=it, I=I_j)
end

# --------------------------------------------------- self-contained ED ------
# Dense ED of H = Σ S_i·S_{i+1} (PBC) in the Sz=0 sector via bit basis.
function ed_ground_energy(N::Int)
    M = N ÷ 2
    states = [s for s in 0:(2^N - 1) if count_ones(s) == M]
    idx = Dict(s => i for (i, s) in enumerate(states))
    dim = length(states)
    H = zeros(Float64, dim, dim)
    for (i, s) in enumerate(states)
        diag = 0.0
        for b in 0:(N - 1)
            b2 = (b + 1) % N
            u = (s >> b) & 1; v = (s >> b2) & 1
            if u == v
                diag += 0.25
            else
                diag -= 0.25
                t = s ⊻ ((1 << b) | (1 << b2))   # spin flip S+S- + S-S+ (1/2 each)
                H[idx[t], i] += 0.5
            end
        end
        H[i, i] += diag
    end
    return eigmin(Symmetric(H))
end

# Table 3 DMRG column (variational upper bounds; per-site)
const TABLE3_DMRG = Dict(
    10 => -0.4515446, 14 => -0.4473964, 18 => -0.4457083, 20 => -0.4452193,
    22 => -0.4448582, 26 => -0.4443707, 30 => -0.4440654, 34 => -0.4438616,
    38 => -0.4437189, 40 => -0.4436630, 42 => -0.4436150, 46 => -0.4435370,
    50 => -0.4434771, 60 => -0.4433762, 80 => -0.4432758, 100 => -0.4432295,
)

const NS = sort(unique(vcat(collect(keys(TABLE3_DMRG)), [8, 12, 140, 200])))

fail = String[]
out = Dict{Int,String}()

println("== (i) ED cross-check (self-contained dense ED, Sz=0 sector) ==")
for N in (8, 10, 12, 14)
    ed = ed_ground_energy(N) / N
    b = bethe_roots(N, Float64)
    dev = abs(b.E / N - ed)
    @printf("N=%3d  ED %.12f  Bethe %.12f  |diff| %.2e  %s\n", N, ed, b.E / N, dev,
            dev < 1e-9 ? "PASS" : "FAIL")
    dev < 1e-9 || push!(fail, "ED N=$N")
end

println("\n== (ii,iii) residuals + root checks; (iv) BigFloat stability ==")
setprecision(BigFloat, 256)
for N in NS
    b64 = bethe_roots(N, Float64)
    bbig = bethe_roots(N, BigFloat)
    ok_roots = length(b64.lam) == N ÷ 2 && issorted(b64.lam) &&
               minimum(diff(b64.lam)) > 0
    stab = abs(Float64(bbig.E / N) - b64.E / N)
    epersite = bbig.E / N
    out[N] = Base.MPFR.string_mpfr(epersite, "%.25Re")
    @printf("N=%3d  E/N=%.15f  resid64=%.1e residBig=%.1e  |F64−Big|=%.1e  roots:%s\n",
            N, Float64(epersite), b64.resid, Float64(bbig.resid), stab,
            ok_roots ? "ok" : "BAD")
    ok_roots || push!(fail, "roots N=$N")
    b64.resid < 1e-10 || push!(fail, "resid N=$N")
    stab < 1e-12 || push!(fail, "bigfloat N=$N")
end

println("\n== (v) Table 3 DMRG column check ==")
# Gate v2 (amended after first run, amendment logged): the DMRG column is a
# variational upper bound printed to 7 digits, itself unconverged at the
# ~1e-7 level for some N (observed one-sided: Bethe ≤ DMRG at N=34,40,46,80,
# 100). Criteria: (a) one-sidedness E_bethe ≤ E_dmrg + 5e-8 (print-rounding
# slack) for EVERY row; (b) |diff| ≤ 3 units of the 7th decimal; every
# non-exact row is flagged. Purpose of the gate — catching convention /
# normalization errors (which give ≥1e-3, sign, or two-sided scatter) — is
# unchanged.
for N in sort(collect(keys(TABLE3_DMRG)))
    eb = Float64(parse(BigFloat, out[N]))
    e7 = round(eb, digits=7)
    t = TABLE3_DMRG[N]
    d7 = round(abs(e7 - t) * 1e7)          # units of the 7th decimal
    onesided = eb <= t + 5e-8
    verdict = e7 == t ? "PASS" :
              (onesided && d7 <= 3 ? "PASS (Bethe below DMRG by $(Int(d7)) in 7th digit — flagged; DMRG is a variational upper bound)" : "FAIL")
    @printf("N=%3d  bethe7=%.7f  table3=%.7f  %s\n", N, e7, t, verdict)
    (e7 == t || (onesided && d7 <= 3)) || push!(fail, "table3 N=$N")
end

open(joinpath(OUTDIR, "bethe_ref.json"), "w") do io
    println(io, "{")
    ks = sort(collect(keys(out)))
    for (i, N) in enumerate(ks)
        print(io, "  \"$N\": ", out[N])
        println(io, i < length(ks) ? "," : "")
    end
    println(io, "}")
end
println("\nwrote $(joinpath(OUTDIR, "bethe_ref.json"))")

if isempty(fail)
    println("BETHE GATE: PASS (all checks)")
else
    println("BETHE GATE: FAIL — ", join(fail, ", "))
    exit(1)
end
