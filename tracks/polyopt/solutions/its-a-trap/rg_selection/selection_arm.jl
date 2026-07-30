#!/usr/bin/env julia
# selection_arm.jl <KEY> — ONE fresh-selection eval on the replacement chassis
# (Amendment 4C §3). Chassis (4A.1): N=10, d=4, rdm=false, pso=0, lso=false,
# r(N) via builder. KEY = "BASELINE" (Core+RG, S=∅) or "B_a" / "B_a+B_b".
# One solve per process (local memory law 4C §5). Appends one CSV row.
using Printf
include(joinpath(@__DIR__, "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "src", "functional_rg.jl"))

const KEY = ARGS[1]
const N = 10; const NRG = 6
As = load_D4()
rg = rg_spec(N, NRG, As)
S = KEY == "BASELINE" ? String[] : Vector{String}(sort(split(KEY, "+")))
GC.gc()
t0 = time()
r = build_rg_selection_model(N; S = S, rg = rg, vspace = :auto,
                             rdm = false, pso = 0, lso = false)
w = time() - t0
open(joinpath(@__DIR__, "results", "fresh_selection.csv"), "a") do io
    println(io, "$KEY,$(r.E),$(r.resid.pfeas),$(r.resid.dfeas),$(r.resid.mu)," *
        "$(r.sig.scalarized),$(r.sig.nrows),$(get(r.counters,"gamma2_dim",0))," *
        "$(get(r.counters,"seam_newwords",-1)),$(round(w,digits=1))," *
        "$(round(Sys.maxrss()/2^30,digits=2))")
end
@printf("SEL-ARM %s E=%.12f wall=%.0fs rss=%.1fG\n", KEY, r.E, w, Sys.maxrss()/2^30)
