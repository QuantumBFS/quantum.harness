#!/usr/bin/env julia
# finalize_smalln.jl — build results/smalln_comparison.csv from raw arm rows
# (4A.7 + 4B.7): delta_adaptive_vs_full = (L_adaptive - L_full)/N SIGNED per
# amendment (positive = Adaptive tighter). NOTE: builder E is PER-SITE, so
# the per-site delta is (E_adaptive - E_full); the /N form in the law assumes
# total energies — both stated in the header. eta_adaptive only when
# Full-Core is resolved-positive, UNCAPPED. Cost ratios Adaptive/Full.
using Printf
raw = joinpath(@__DIR__, "results", "smalln_arms_raw.csv")
out = joinpath(@__DIR__, "results", "smalln_comparison.csv")
rows = Dict{Tuple{Int,String},Vector{String}}()
for l in readlines(raw)[2:end]
    f = split(l, ","); rows[(parse(Int, f[1]), String(f[2]))] = f
end
open(out, "w") do io
    println(io, "# E columns are PER-SITE bounds; delta_adaptive_vs_full = E_adaptive - E_full (per-site, signed, positive = Adaptive tighter)")
    println(io, "N,E_full,E_core,E_corerg,E_coresel,E_adaptive,delta_adaptive_vs_full,fullcore_gap,fullcore_resolved,eta_adaptive,wall_ratio_adaptive_over_full,rss_ratio_adaptive_over_full,scal_ratio_adaptive_over_full,rows_ratio_adaptive_over_full")
    for N in (10, 12, 14)
        all(haskey(rows, (N, a)) for a in ("full", "core", "corerg", "coresel", "adaptive")) || continue
        g(a, i) = parse(Float64, rows[(N, a)][i])
        Ef, Ec, Ea = g("full", 3), g("core", 3), g("adaptive", 3)
        ec(a, b) = g(a, 6) + g(b, 6) + 0.75 * (g(a, 4) + g(a, 5) + g(b, 4) + g(b, 5))
        dAF = Ea - Ef                      # signed, positive = adaptive tighter
        gap = Ef - Ec                      # Full-Core (positive expected)
        resolved = gap > ec("full", "core")
        eta = resolved ? (Ea - Ec) / gap : NaN
        @printf(io, "%d,%.14f,%.14f,%.14f,%.14f,%.14f,%+.3e,%+.3e,%s,%s,%.2f,%.2f,%.3f,%.3f\n",
            N, Ef, Ec, g("corerg", 3), g("coresel", 3), Ea, dAF, gap,
            resolved ? "resolved-positive" : "unresolved",
            resolved ? @sprintf("%.4f", eta) : "NA",
            g("adaptive", 7) / max(g("full", 7), 0.1), g("adaptive", 8) / max(g("full", 8), 0.01),
            g("adaptive", 9) / max(g("full", 9), 1.0), g("adaptive", 10) / max(g("full", 10), 1.0))
    end
end
println("smalln_comparison.csv written")
foreach(println, readlines(out))
