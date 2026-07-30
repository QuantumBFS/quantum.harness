#!/usr/bin/env julia
# release_gates.jl <stage> — A200 release gates on the replacement chassis
# (d=4, rdm=false, pso=0, lso=false). ONE heavy solve per process (OOM law):
#   r123       : R1 canary + R2 ED-feasibility + R3 mutation red
#   r4bauto    : R4b auto arm solve -> results/r4b_auto.txt
#   r4bpool    : R4b pool arm solve -> results/r4b_pool.txt
#   r4bverdict : R4b comparison (no solve) + Γ ED eigmin
# Bundle set S comes from A200_CONFIG.json (4C §2). Each stage appends
# durable rows to results/a200_release_gates.csv immediately.
using Printf, SHA
include(joinpath(@__DIR__, "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "src", "functional_rg.jl"))
include(joinpath(@__DIR__, "src", "vcheck.jl"))
include(joinpath(@__DIR__, "src", "semhash.jl"))

const STAGE = ARGS[1]
const CH = (rdm = false, pso = 0, lso = false)   # 4A.1 chassis
const NRG = 6
const CSVP = joinpath(@__DIR__, "results", "a200_release_gates.csv")
isfile(CSVP) || open(io -> println(io, "gate,verdict,detail"), CSVP, "w")
ok = true
gate!(n, c, m) = (global ok &= c; println(@sprintf("%-10s %s  %s", n, c ? "PASS" : "FAIL", m));
                  open(io -> println(io, "$n,$(c ? "PASS" : "FAIL")," * "\"" * m * "\""), CSVP, "a"); flush(stdout))

raw = read(joinpath(@__DIR__, "A200_CONFIG.json"), String)
bid = match(r"\"bundle_ids\"\s*:\s*(\[[^\]]*\])", raw)
Sids = Vector{String}(sort([String(m.captures[1]) for m in eachmatch(r"\"(B_[a-z_]+)\"", bid.captures[1])]))
As = load_D4()

armfile(tag) = joinpath(@__DIR__, "results", "r4b_$(tag).txt")
function dump_arm(tag, r)
    open(armfile(tag), "w") do io
        println(io, r.E); println(io, r.resid.pfeas); println(io, r.resid.dfeas)
        println(io, r.resid.mu); println(io, r.sig.scalarized); println(io, r.sig.nrows)
        println(io, get(r.counters, "seam_newwords", -1))
        println(io, ext_semhash(r.ext; include_words = false))
        println(io, ext_semhash(r.ext; include_words = true))
    end
end
load_arm(tag) = readlines(armfile(tag))

if STAGE == "r123"
    E0, ψ = heis_ground(10)
    core = build_rg_selection_model(10; vspace = :stock, CH...)
    r1ok = isfinite(core.E) && core.resid.pfeas <= 1e-6 && core.resid.dfeas <= 1e-6 &&
           core.E <= E0 / 10 + 5e-7
    gate!("R1", r1ok, @sprintf("Core(rdm=false,lso=false) N=10 E=%.12f <= E0/N=%.12f pfeas=%.1e dfeas=%.1e",
          core.E, E0 / 10, core.resid.pfeas, core.resid.dfeas))
    o2, m2 = vcheck_physical(10, Sids, As, NRG)
    foreach(l -> println("  ", l), m2)
    gate!("R2", o2, "V1 ED substitution: Gamma + omega blocks + link rows @ N=10 (chassis-independent)")
    rg = rg_spec(10, NRG, As)
    bad_ycoef = deepcopy(rg.ycoef)
    bad_ycoef[1] = [(w, -c) for (w, c) in bad_ycoef[1]]
    bad = (words = rg.words, ycoef = bad_ycoef, zblocks = rg.zblocks)
    caught = false; note = ""
    try
        rb = build_rg_selection_model(10; rg = bad, vspace = :auto, CH...)
        viol = rb.E > E0 / 10 + 5e-7 || rb.E < core.E - 5e-7 || !isfinite(rb.E)
        global caught = viol
        global note = @sprintf("mutated-E=%.10f (core %.10f, E0/N %.10f)", rb.E, core.E, E0 / 10)
    catch e
        global caught = true; global note = "hard failure (caught): " * string(typeof(e))
    end
    gate!("R3", caught, "link-sign mutation on rdm=false chassis -> " * note)
    # persist core arm numbers for the verdict stage
    open(joinpath(@__DIR__, "results", "r1_core.txt"), "w") do io
        println(io, core.E); println(io, E0 / 10)
    end
elseif STAGE == "r4bauto"
    rg = rg_spec(10, NRG, As)
    dump_arm("auto", build_rg_selection_model(10; S = Sids, rg = rg, vspace = :auto, CH...))
    println("r4b auto arm dumped")
elseif STAGE == "r4bpool"
    rg = rg_spec(10, NRG, As)
    dump_arm("pool", build_rg_selection_model(10; S = Sids, rg = rg, vspace = :pool, CH...))
    println("r4b pool arm dumped")
elseif STAGE == "r4bverdict"
    A = load_arm("auto"); P = load_arm("pool")
    EA, EP = parse(Float64, A[1]), parse(Float64, P[1])
    ec = parse(Float64, A[4]) + parse(Float64, P[4]) +
         0.75 * (parse(Float64, A[2]) + parse(Float64, A[3]) + parse(Float64, P[2]) + parse(Float64, P[3]))
    cntok = parse(Int, A[7]) <= parse(Int, P[7]) && parse(Int, A[5]) <= parse(Int, P[5])
    hEq = A[8] == P[8]
    E0, ψ = heis_ground(10)
    gb = gamma2_block(Sids, 10)
    yv = Dict{Vector{UInt16},Float64}(); G = zeros(gb.dim, gb.dim)
    for (w, i, j, c) in gb.entries
        G[i, j] += c * get!(() -> word_expect(ψ, 10, w), yv, w)
    end
    lmin = minimum(LinearAlgebra.eigvals(LinearAlgebra.Symmetric((G + G') / 2)))
    r4bok = abs(EA - EP) <= ec && hEq && cntok && lmin >= -1e-10
    gate!("R4b", r4bok, @sprintf("auto=%.12f pool=%.12f |dE|=%.1e<=eps_cmp=%.1e blockhash_eq=%s counts(auto<=pool)=%s(nw %s<=%s, scal %s<=%s) eigmin=%+.1e",
          EA, EP, abs(EA - EP), ec, hEq, cntok, A[7], P[7], A[5], P[5], lmin))
    open(io -> println(io, A[9]), joinpath(@__DIR__, "results", "r4b_auto_fullhash.txt"), "w")
else
    error("unknown stage $STAGE")
end
println(ok ? "STAGE $STAGE GREEN" : "STAGE $STAGE FAILED")
exit(ok ? 0 : 1)
