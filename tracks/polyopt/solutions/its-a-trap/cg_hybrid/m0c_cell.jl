#!/usr/bin/env julia
# m0c_cell.jl — ONE M0-C regression arm per process (fresh, isolated timing;
# the CONFIG A stock arm at N=14 doubles as the B10-C cost baseline).
# Usage: julia m0c_cell.jl <N> <cfg:rdm8|configA> <variant:stock|adapter> <out.jsonl>
using JuMP, Mosek, MosekTools, LinearAlgebra, SparseArrays, Printf, SHA
include(joinpath(@__DIR__, "gsb_cg.jl"))

N       = parse(Int, ARGS[1])
cfg     = ARGS[2]
variant = ARGS[3]
outf    = ARGS[4]

supp = [[1, 4]]; coe = [3 / 4]
knobs = cfg == "rdm8"    ? (extra = 4, rdm = 8,  pso = 0, lso = false) :
        cfg == "configA" ? (extra = 4, rdm = 10, pso = 3, lso = true)  :
        error("unknown cfg $cfg")

t0 = time()
E = if variant == "stock"
    QMBCertify.GSB(supp, coe, N, 4; extra = knobs.extra, rdm = knobs.rdm,
                   pso = knobs.pso, lso = knobs.lso, QUIET = true)[1]
elseif variant == "adapter"
    GSB_cg(supp, coe, N, 4; extra = knobs.extra, rdm = knobs.rdm,
           pso = knobs.pso, lso = knobs.lso, QUIET = true, tower = nothing)[1]
else
    error("unknown variant $variant")
end
wall = time() - t0
rss_gb = Sys.maxrss() / 2^30

# provenance (per final-plan §R6)
wt = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
git(args...) = strip(read(Cmd(`git -C $wt $(collect(args))`), String))
jstr(x::String) = "\"" * x * "\""
jstr(x) = string(x)
fields = [
    "N" => N, "cfg" => cfg, "variant" => variant, "E" => E,
    "wall_s" => round(wall, digits = 2), "maxrss_gb" => round(rss_gb, digits = 3),
    "git_commit" => git("rev-parse", "HEAD"),
    "git_diff_empty" => isempty(strip(read(`git -C $wt status --porcelain`, String))),
    "script_sha256" => bytes2hex(sha256(read(@__FILE__))),
    "manifest_sha256" => bytes2hex(sha256(read(joinpath(wt, "julia-env", "Manifest.toml")))),
    "qmbcertify_commit" => strip(read(`git -C $(joinpath(wt, ".external", "QMBCertify")) rev-parse HEAD`, String)),
    "gsb_fork_sha" => _FORK_SHA,
    "julia" => string(VERSION), "ts" => string(round(Int, time()))]
open(outf, "a") do io
    println(io, "{", join(("$(jstr(String(k))): $(jstr(v))" for (k, v) in fields), ", "), "}")
end
@printf("M0C %s %s N=%d  E=%.12f  wall=%.1fs rss=%.2fGB\n", cfg, variant, N, E, wall, rss_gb)
