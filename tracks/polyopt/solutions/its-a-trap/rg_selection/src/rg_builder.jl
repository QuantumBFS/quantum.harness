# rg_builder.jl — build_rg_selection_model: the ONLY path at N∈{10,12,14,200}.
# Arms (four-arm contract): S=∅+rg=nothing → Base; S≠∅ → +[SEL]; rg≠nothing
# → +[RG]. vspace ∈ {:stock (no extension), :pool (full V_pool), :auto
# (V(S) products only)}. All-off + :stock reduces EXACTLY to the adapter.
using JuMP, Mosek, MosekTools, LinearAlgebra, SparseArrays, Printf, SHA
include(joinpath(@__DIR__, "..", "..", "cg_hybrid", "gsb_cg.jl"))
include(joinpath(@__DIR__, "local_cone_adapter.jl"))
include(joinpath(@__DIR__, "moment_bundles.jl"))

const SUPP = [[1, 4]]; const COE = [3 / 4]

function build_rg_selection_model(N::Int; S::Vector{String} = String[],
        rg = nothing, vspace::Symbol = :auto, rdm = 8, pso = 0, lso = true,
        keeplog::Union{Nothing,String} = nothing)
    extra = r_of(N) - 1
    counters = Dict{String,Int}()
    ext = nothing
    if !(vspace == :stock && isempty(S) && rg === nothing)
        newwords = Vector{Vector{UInt16}}()
        gramblocks = NamedTuple[]
        if vspace == :pool
            append!(newwords, vpool_words(N))
            counters["vpool_words"] = length(newwords)
        end
        if !isempty(S)
            gb = gamma2_block(S, N)
            append!(newwords, gb.prods)
            push!(gramblocks, (dim = gb.dim, entries = gb.entries))
            counters["gamma2_dim"] = gb.dim
            counters["gamma2_entries"] = length(gb.entries)
            counters["O_rows"] = length(gb.rows)
        end
        ycoef = Vector{Vector{Tuple{Vector{UInt16},Float64}}}()
        zblocks = NamedTuple[]
        if rg !== nothing               # (G2+) rg = (ycoef, zblocks, words)
            append!(newwords, rg.words)
            append!(ycoef, rg.ycoef)
            append!(zblocks, rg.zblocks)
            counters["rg_rows"] = length(rg.ycoef)
        end
        unique!(newwords)
        counters["newwords"] = length(newwords)
        ext = RGExt(newwords,
            [(dim = g.dim, entries = g.entries) for g in gramblocks],
            ycoef,
            [(dim = z.dim, entries = z.entries) for z in zblocks],
            Tuple{Int,Float64}[], counters)
    end
    logpath, logio = mktemp()
    E = redirect_stdout(logio) do
        r = GSB_cg(SUPP, COE, N, 4; extra = extra, rdm = rdm, pso = pso,
                   lso = lso, QUIET = false, tower = ext)[1]
        flush(logio); r
    end
    close(logio)
    log = read(logpath, String)
    keeplog === nothing || cp(logpath, keeplog; force = true)
    rm(logpath; force = true)
    m = match(r"SDP size: n = (\d+), m = (\d+)", log)
    mos = match(r"Matrix variables\s+: (\d+) \(scalarized: (\d+)\)", log)
    con = match(r"Constraints\s+: (\d+)", log)
    lastit = nothing
    for l in eachmatch(r"^\s*\d+\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+[\d.eE+-]+\s+\S+\s+[\d.eE+-]+\s+[\d.eE+-]+\s+([\d.eE+-]+)\s"m, log)
        lastit = l
    end
    sig = (nblk = m === nothing ? -1 : parse(Int, m.captures[1]),
           mwords = m === nothing ? -1 : parse(Int, m.captures[2]),
           matvars = mos === nothing ? -1 : parse(Int, mos.captures[1]),
           scalarized = mos === nothing ? -1 : parse(Int, mos.captures[2]),
           nrows = con === nothing ? -1 : parse(Int, con.captures[1]))
    resid = lastit === nothing ? (pfeas = NaN, dfeas = NaN, mu = NaN) :
            (pfeas = parse(Float64, lastit.captures[1]),
             dfeas = parse(Float64, lastit.captures[2]),
             mu = parse(Float64, lastit.captures[3]))
    return (E = E, sig = sig, resid = resid, counters = counters, ext = ext)
end
