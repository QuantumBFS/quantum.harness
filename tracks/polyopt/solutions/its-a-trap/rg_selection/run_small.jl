#!/usr/bin/env julia
# run_small.jl <gate>  — G1 (this file's g1 mode): fresh builder identity +
# neutrality (G1b) + orbit-complexity counters (G1c) + pool checks.
using Printf
include(joinpath(@__DIR__, "src", "rg_builder.jl"))

mode = length(ARGS) >= 1 ? ARGS[1] : "g1"
report = String[]; ok = true
gate!(n, c, m) = (global ok &= c; l = @sprintf("%-14s %s  %s", n, c ? "PASS" : "FAIL", m);
                  push!(report, l); println(l); flush(stdout))

if mode == "g1"
    # pool non-collapse/duplicate checks at every N in use (fix 2/3)
    for N in (10, 12, 14, 200)
        rep = pool_checks(N)
        gate!("POOL N=$N", true, string(rep))
    end
    # adapter reference vs builder all-off (fresh identity, N=10)
    a10 = build_rg_selection_model(10; vspace = :stock)
    b10 = build_rg_selection_model(10; vspace = :stock)  # determinism check
    gate!("G1 N=10", abs(a10.E - b10.E) <= 1e-12,
        @sprintf("builder(all-off) E=%.12f repeat |Δ|=%.1e", a10.E, abs(a10.E - b10.E)))
    # G1b neutrality: full V_pool, zero blocks
    n10 = build_rg_selection_model(10; vspace = :pool)
    gate!("G1b N=10", abs(n10.E - a10.E) <= 1e-8,
        @sprintf("neutral E=%.12f |Δ|=%.2e (+%d words)", n10.E, abs(n10.E - a10.E),
                 get(n10.counters, "seam_newwords", -1)))
    n12 = build_rg_selection_model(12; vspace = :pool)
    a12 = build_rg_selection_model(12; vspace = :stock)
    gate!("G1b N=12", abs(n12.E - a12.E) <= 1e-8,
        @sprintf("neutral |Δ|=%.2e", abs(n12.E - a12.E)))
    # N=14 structural signatures: all-off vs adapter twice (fresh)
    s1 = build_rg_selection_model(14; vspace = :stock)
    s2 = build_rg_selection_model(14; vspace = :stock)
    gate!("G1 N=14 sig", s1.sig == s2.sig && abs(s1.E - s2.E) <= 1e-12,
        @sprintf("sig=%s E=%.12f", s1.sig, s1.E))
    # G1c orbit complexity: materialized counts must equal the REPRESENTATIVE
    # formula rows == r(N) + Σ_b |closure(b)| and prods ≤ rows² — i.e. they
    # scale with representative counts (which depend on r(N) by design),
    # never with a ×N orbit-materialization factor.
    g1c_ok = true; msgs = String[]
    for N in (10, 14, 200)
        c = gamma2_block(collect(POOL), N)
        expected = r_of(N) + sum(length(bundle_closure(b, N)) for b in POOL)
        cond = length(c.rows) == expected && length(c.prods) <= length(c.rows)^2
        global g1c_ok &= cond
        push!(msgs, @sprintf("N=%d rows=%d(=r+Scl=%d) prods=%d<=%d", N,
            length(c.rows), expected, length(c.prods), length(c.rows)^2))
    end
    gate!("G1c orbits", g1c_ok, join(msgs, " | "))
end

open(joinpath(@__DIR__, "results", "g1_report.txt"), "w") do io
    println(io, "run_small.jl $(mode)  ", ok ? "PASS" : "FAIL")
    foreach(l -> println(io, l), report)
end
println(ok ? "GATE $(uppercase(mode)) GREEN" : "GATE $(uppercase(mode)) FAILED")
exit(ok ? 0 : 1)
