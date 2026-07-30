#!/usr/bin/env julia
# replace_arm.jl <N> <A|B|C6|C10|C14|D|E> <build|solve>  — or —  degate
# FOUR-HOUR REPLACEMENT LOCK (plan v4 + FINAL EXECUTION PATCH).
# Chassis (all arms): d=4, rdm=false, pso=0, lso=false.
#   A  FINE_RICH_REACH_COMPARATOR   extra=N÷2-1, stock
#   B  TRUNCATED_CORE               extra=r_of(N)-1, stock
#   Cn TRUNCATED_PLUS_TOWER         B basis + tower depth n
#   D  C6 + FULL_DECLARED_POOL_NO_SELECTION (all four bundles)
#   E  C6 + TRANSFERRED_FIXED_BUNDLE {B_bond_edge, B_half}
# build mode: fresh process, aborts INSIDE the seam hook pre-optimize!.
# degate mode (patch §1): N=14 full-pool ED substitution + one targeted
#   mutation red-test (B_pair_edge Γ diagonal negation). Blocks D/E only.
using Printf, SHA, Dates
include(joinpath(@__DIR__, "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "src", "functional_rg.jl"))
include(joinpath(@__DIR__, "src", "vcheck.jl"))

const RESULTS = joinpath(@__DIR__, "results")
const CH = (rdm = false, pso = 0, lso = false)

struct AbortBuild <: Exception end
struct BuildProbe
    inner::RGExt
    stats::Dict{String,Any}
end
function tower_dual_extend!(model, cons, tsupp, L, d::BuildProbe)
    tower_dual_extend!(model, cons, tsupp, L, d.inner)
    st = d.stats
    st["tsupp_rows"] = length(tsupp)
    st["cons_nnz"] = sum(length(JuMP.linear_terms(c)) for c in cons)
    psd = 0; big = 0; nb = 0
    for (F, S_) in JuMP.list_of_constraint_types(model)
        (S_ <: MOI.PositiveSemidefiniteConeTriangle || S_ <: MOI.PositiveSemidefiniteConeSquare) || continue
        for con in JuMP.all_constraints(model, F, S_)
            lv = length(JuMP.constraint_object(con).func)
            n = S_ <: MOI.PositiveSemidefiniteConeTriangle ?
                Int((sqrt(8 * lv + 1) - 1) / 2) : Int(sqrt(lv))
            psd += lv; big = max(big, n); nb += 1
        end
    end
    st["psd_scalars"] = psd; st["largest_block"] = big; st["psd_blocks"] = nb
    throw(AbortBuild())
end

if ARGS[1] == "degate"
    # (i) ED substitution: full pool + n=6 tower at N=14 (blocks/links vs ED)
    As = load_D4()
    o1, m1 = vcheck_physical(14, sort(collect(POOL)), As, 6)
    foreach(println, m1)
    # (ii) targeted mutation red-test: B_pair_edge Γ diagonal negation must
    # go red on the truncated chassis (E > E_Bethe(14)/site + tol or fail)
    gb = gamma2_block(["B_pair_edge"], 14)
    bad = [(w, i, j, (i == j ? -1.0 : 1.0) * c) for (w, i, j, c) in gb.entries]
    ext = RGExt(unique([e[1] for e in bad]), [(dim = gb.dim, entries = bad)],
                Vector{Vector{Tuple{Vector{UInt16},Float64}}}(),
                NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Int,Int,Int,Float64}}}}[],
                Tuple{Int,Float64}[], Dict{String,Int}())
    E0_14 = -0.44739639525335979   # bethe/ED N=14 per-site (source-of-record)
    red = false; note = ""
    try
        logpath, logio = mktemp()
        E = redirect_stdout(logio) do
            r = GSB_cg(SUPP, COE, 14, 4; extra = r_of(14) - 1, rdm = false,
                       pso = 0, lso = false, QUIET = false, tower = ext)[1]
            flush(logio); r
        end
        close(logio); rm(logpath; force = true)
        global red = !isfinite(E) || E > E0_14 + 5e-7   # top-level try = soft scope
        global note = @sprintf("mutated-E=%s vs E14/site=%.12f", string(E), E0_14)
    catch e
        global red = true; global note = "hard failure (caught): " * string(typeof(e))
    end
    println("DEGATE mutation: ", note, " -> ", red ? "RED as required" : "NOT CAUGHT")
    ok = o1 && red
    open(joinpath(RESULTS, "replacement_degate.txt"), "w") do io
        println(io, "degate ", ok ? "PASS" : "FAIL", " $(now())")
        foreach(l -> println(io, l), m1)
        println(io, "mutation: ", note, " -> ", red ? "RED" : "NOT-CAUGHT")
    end
    println(ok ? "DEGATE PASS" : "DEGATE FAIL")
    exit(ok ? 0 : 1)
end

const N = parse(Int, ARGS[1]); const ARM = ARGS[2]; const MODE = ARGS[3]
n_tower(a) = a == "C6" || a == "D" || a == "E" ? 6 :
             a == "C10" ? 10 : a == "C14" ? 14 : 0
S_of(a) = a == "D" ? Vector{String}(sort(collect(POOL))) :
          a == "E" ? ["B_bond_edge", "B_half"] : String[]
extra_of(a) = a == "A" ? N ÷ 2 - 1 : r_of(N) - 1
label_of(a) = a == "A" ? "FINE_RICH_REACH_COMPARATOR" :
              a == "B" ? "TRUNCATED_CORE" :
              a == "D" ? "C6+FULL_DECLARED_POOL_NO_SELECTION" :
              a == "E" ? "C6+TRANSFERRED_FIXED_BUNDLE" :
              "TRUNCATED_PLUS_TOWER_n$(n_tower(a))"

nt = n_tower(ARM); S = S_of(ARM); xtra = extra_of(ARM)
As = nt > 0 ? load_D4() : nothing
rg = nt > 0 ? rg_spec(N, nt, As) : nothing
vs = (nt > 0 || !isempty(S)) ? :auto : :stock

# fully resolved configuration, printed and hashed BEFORE solving (Phase 1)
cfg = "arm=$ARM label=$(label_of(ARM)) N=$N d=4 rdm=false pso=0 lso=false " *
      "extra=$xtra r=$(xtra + 1) vspace=$vs tower_n=$nt " *
      "rg_map=$(nt > 0 ? d4_hash() : "off") S=$(isempty(S) ? "off" : join(S, "+")) " *
      "supp=[[1,4]] coe=[0.75] quotient=be63c27 tol=1e-8"
csha = bytes2hex(sha256(cfg))[1:16]
println("RESOLVED-CONFIG ", cfg)
println("CONFIG-SHA16 ", csha)
open(io -> println(io, "{\"N\": $N, \"arm\": \"$ARM\", \"mode\": \"$MODE\", \"sha16\": \"$csha\", \"config\": \"$cfg\"}"),
     joinpath(RESULTS, "replacement_configs.jsonl"), "a")

if MODE == "build"
    newwords = Vector{Vector{UInt16}}(); gramblocks = NamedTuple[]
    counters = Dict{String,Int}()
    if !isempty(S)
        gb = gamma2_block(S, N)
        append!(newwords, gb.prods)
        push!(gramblocks, (dim = gb.dim, entries = gb.entries))
        counters["gamma2_dim"] = gb.dim
    end
    ycoef = Vector{Vector{Tuple{Vector{UInt16},Float64}}}(); zblocks = NamedTuple[]
    if rg !== nothing
        append!(newwords, rg.words); append!(ycoef, rg.ycoef); append!(zblocks, rg.zblocks)
        counters["rg_rows"] = length(rg.ycoef)
    end
    unique!(newwords)
    inner = RGExt(newwords, [(dim = g.dim, entries = g.entries) for g in gramblocks],
                  ycoef, [(dim = z.dim, entries = z.entries) for z in zblocks],
                  Tuple{Int,Float64}[], counters)
    probe = BuildProbe(inner, Dict{String,Any}())
    t0 = time(); aborted = false
    try
        redirect_stdout(devnull) do
            GSB_cg(SUPP, COE, N, 4; extra = xtra, rdm = false, pso = 0,
                   lso = false, QUIET = false, tower = probe)
        end
    catch e
        e isa AbortBuild || rethrow(); global aborted = true
    end
    w = time() - t0
    st = probe.stats
    open(joinpath(RESULTS, "replacement_build.csv"), "a") do io
        println(io, "$N,$ARM,$(get(st,"psd_scalars",-1)),$(get(st,"psd_blocks",-1))," *
            "$(get(st,"largest_block",-1)),$(get(st,"tsupp_rows",-1)),$(get(st,"cons_nnz",-1))," *
            "$(get(counters,"rg_rows",0)),$(round(w,digits=1)),$(round(Sys.maxrss()/2^30,digits=2))," *
            "$(aborted ? "BUILD_OK" : "NO_ABORT"),$csha")
    end
    @printf("BUILD %s@N=%d psd=%s big=%s rows=%s nnz=%s wall=%.1fs rss=%.2fG\n",
            ARM, N, get(st, "psd_scalars", "?"), get(st, "largest_block", "?"),
            get(st, "tsupp_rows", "?"), get(st, "cons_nnz", "?"), w, Sys.maxrss() / 2^30)
elseif MODE == "solve"
    GC.gc()
    t0 = time()
    r = build_rg_selection_model(N; S = S, rg = rg, vspace = vs, extra = xtra, CH...)
    w = time() - t0
    stat = isfinite(r.E) && r.resid.pfeas <= 1e-6 && r.resid.dfeas <= 1e-6 ? "OPTIMAL" : "NONOPT"
    open(joinpath(RESULTS, "replacement_solve.csv"), "a") do io
        println(io, "$N,$ARM,$(r.E),$(r.resid.pfeas),$(r.resid.dfeas),$(r.resid.mu)," *
            "$(r.sig.scalarized),$(r.sig.nrows),$(get(r.counters,"seam_newwords",-1))," *
            "$(get(r.counters,"gamma2_dim",0)),$(get(r.counters,"rg_rows",0))," *
            "$(round(w,digits=1)),$(round(Sys.maxrss()/2^30,digits=2)),$stat,$csha")
    end
    @printf("SOLVE %s@N=%d E=%.12f %s wall=%.0fs rss=%.1fG\n", ARM, N, r.E, stat, w, Sys.maxrss() / 2^30)
else
    error("unknown mode $MODE")
end
