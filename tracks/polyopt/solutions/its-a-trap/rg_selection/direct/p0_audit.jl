#!/usr/bin/env julia
# p0_audit.jl — PATCH §2 audit on TODAY'S artifacts (zero new machinery):
# enumerate every tower link word of the four-hour C6 arm and every pool
# word against closure(G_retained) = the truncated-chassis stock tsupp at
# N=14, via the seam's own bfind. Also emit the Gram-induced partition
# sizes (W_full vs W_R) for BASIS_PARTITION.json.
using Printf, SHA
include(joinpath(@__DIR__, "..", "src", "rg_builder.jl"))
include(joinpath(@__DIR__, "..", "src", "functional_rg.jl"))

struct AbortDump <: Exception end
struct TsuppDump
    inner::RGExt
    out::Base.RefValue{Vector{Vector{UInt16}}}
end
function tower_dual_extend!(model, cons, tsupp, L, d::TsuppDump)
    d.out[] = copy(tsupp)          # stock tsupp BEFORE any extension
    throw(AbortDump())
end
empty_ext() = RGExt(Vector{Vector{UInt16}}(), NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Vector{UInt16},Int,Int,Float64}}}}[],
    Vector{Vector{Tuple{Vector{UInt16},Float64}}}(),
    NamedTuple{(:dim, :entries),Tuple{Int,Vector{Tuple{Int,Int,Int,Float64}}}}[],
    Tuple{Int,Float64}[], Dict{String,Int}())

function stock_tsupp(N::Int, extra::Int)
    ref = Ref(Vector{Vector{UInt16}}())
    d = TsuppDump(empty_ext(), ref)
    try
        redirect_stdout(devnull) do
            GSB_cg(SUPP, COE, N, 4; extra = extra, rdm = false, pso = 0,
                   lso = false, QUIET = false, tower = d)
        end
    catch e
        e isa AbortDump || rethrow()
    end
    return ref[]
end

As = load_D4()
out = String[]
push!(out, "check,word,in_retained_closure,note")

# --- tower link words (n=6, N=14) vs closure(G_ret) = B@14 stock tsupp ---
ts = stock_tsupp(14, r_of(14) - 1)      # retained chassis r=2
sort!(ts)
rg = rg_spec(14, 6, As)
nout = 0
for w in rg.words
    inside = bfind(ts, w) !== nothing
    global nout += inside ? 0 : 1
    push!(out, "tower_link_word,\"$(Int.(w))\",$(inside),n=6 ycoef word")
end
println("tower link words: $(length(rg.words)) total, $(nout) OUTSIDE retained closure")

# --- pool bundle closure words vs retained closure (context for P5) ---
for b in POOL, w in bundle_closure(b, 14)
    inside = bfind(ts, w) !== nothing
    push!(out, "bundle_closure,\"$(Int.(w))\",$(inside),$b (deleted-region anchor expected: false)")
end

# --- Gram-induced partition at N=8 ONLY (FINAL CUT): frozen allowlist ---
part = String[]
push!(part, "{")
let N = 8
    tR = stock_tsupp(N, r_of(N) - 1)     # retained: reach-generated candidates
    tF = stock_tsupp(N, N ÷ 2 - 1)       # full fine comparator basis
    sort!(tR); sort!(tF)
    WD = [w for w in tF if bfind(tR, w) === nothing]
    @printf("N=%d |W_full|=%d |W_R|=%d |W_D|=%d\n", N, length(tF), length(tR), length(WD))
    enc(ws) = "[" * join(("\"" * join(Int.(w), "-") * "\"" for w in ws), ",") * "]"
    allow_sha = bytes2hex(sha256(join((join(Int.(w), "-") for w in tR), ";")))
    push!(part, "  \"8\": {\"W_full\": $(length(tF)), \"W_R\": $(length(tR)), \"W_D\": $(length(WD)),")
    push!(part, "  \"allowlist_sha256\": \"$allow_sha\",")
    push!(part, "  \"W_R_words\": " * enc(tR) * ",")
    push!(part, "  \"W_D_words\": " * enc(WD) * "}")
end
push!(part, "}")
open(io -> foreach(l -> println(io, l), part), joinpath(@__DIR__, "BASIS_PARTITION.json"), "w")
open(io -> foreach(l -> println(io, l), out), joinpath(@__DIR__, "TOWER_WORD_AUDIT.csv"), "w")
println("P0 AUDIT DONE — tower words outside retained closure: ", nout,
        nout == 0 ? " (containment PROVEN by enumeration)" : " (ADDITIVE TOWER RESTORED DELETED CONTENT — reportable finding)")
