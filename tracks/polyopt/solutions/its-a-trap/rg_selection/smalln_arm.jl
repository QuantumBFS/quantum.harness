#!/usr/bin/env julia
# smalln_arm.jl <N> <arm> — ONE small-N comparison arm on the 4A.1 chassis
# (lso=false for ALL arms incl. Full). One solve per process (4C §5).
# arms: full (rdm=10) | core (rdm=false) | corerg | coresel | adaptive
using Printf
include(joinpath(@__DIR__, "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "src", "functional_rg.jl"))

const N = parse(Int, ARGS[1]); const ARM = ARGS[2]; const NRG = 6
raw = read(joinpath(@__DIR__, "A200_CONFIG.json"), String)
bid = match(r"\"bundle_ids\"\s*:\s*(\[[^\]]*\])", raw)
S = Vector{String}(sort([String(m.captures[1]) for m in eachmatch(r"\"(B_[a-z_]+)\"", bid.captures[1])]))
As = load_D4()
rg = rg_spec(N, NRG, As)
kw = ARM == "full"     ? (vspace = :stock, rdm = 10,    pso = 0, lso = false) :
     ARM == "core"     ? (vspace = :stock, rdm = false, pso = 0, lso = false) :
     ARM == "corerg"   ? (vspace = :auto,  rdm = false, pso = 0, lso = false, rg = rg) :
     ARM == "coresel"  ? (vspace = :auto,  rdm = false, pso = 0, lso = false, S = S) :
     ARM == "adaptive" ? (vspace = :auto,  rdm = false, pso = 0, lso = false, S = S, rg = rg) :
     error("unknown arm $ARM")
GC.gc()
t0 = time()
r = build_rg_selection_model(N; kw...)
w = time() - t0
open(joinpath(@__DIR__, "results", "smalln_arms_raw.csv"), "a") do io
    println(io, "$N,$ARM,$(r.E),$(r.resid.pfeas),$(r.resid.dfeas),$(r.resid.mu)," *
        "$(round(w,digits=1)),$(round(Sys.maxrss()/2^30,digits=2))," *
        "$(r.sig.scalarized),$(r.sig.nrows),$(get(r.counters,"seam_newwords",-1))")
end
@printf("SMALLN N=%d %s E=%.12f wall=%.0fs rss=%.1fG\n", N, ARM, r.E, w, Sys.maxrss()/2^30)
