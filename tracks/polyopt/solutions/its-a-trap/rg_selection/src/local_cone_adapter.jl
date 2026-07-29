# local_cone_adapter.jl — the single builder's dual-side plumbing.
# Dispatch trick: gsb_cg.jl's seam calls tower_dual_extend!(model, cons,
# tsupp, L, tower) with an UNTYPED tower — defining a method on ::RGExt
# extends the fork without touching cg_hybrid (G1 verifies equality fresh).
#
# RGExt implements THEOREM_CONTRACT_RG_SELECTION §4 exactly:
#   newwords   : coefficient-space extension (appended to tsupp/cons at the
#                seam; new words carry no objective ⇒ neutrality when no
#                block touches them — gate G1b)
#   gramblocks : Γ_{2,S}(Q₂y) ⪰ 0 duals — entries (w, i, j, c):
#                cons[w] += c·G[i,j] over the REAL EMBEDDING [[R,-I],[I,R]]
#   ycoef      : link-row adjoints (A_yᵀμ), existing convention
#   zblocks    : Γ₃ duals Z = mat(−Sᵀμ), existing convention
#   brows      : inhomogeneous terms (emitted explicitly, expected empty)
#   counters   : code-generated build accounting (gate G1c: materialized
#                objects scale with canonical representatives, never ×N)
struct RGExt
    newwords::Vector{Vector{UInt16}}
    gramblocks::Vector{@NamedTuple{dim::Int, entries::Vector{Tuple{Vector{UInt16},Int,Int,Float64}}}}
    ycoef::Vector{Vector{Tuple{Vector{UInt16},Float64}}}
    zblocks::Vector{@NamedTuple{dim::Int, entries::Vector{Tuple{Int,Int,Int,Float64}}}}
    brows::Vector{Tuple{Int,Float64}}
    counters::Dict{String,Int}
    capture::Base.RefValue{Any}   # vcheck: stash the JuMP model at the seam
end
RGExt(nw, gb, yc, zb, br, ct) = RGExt(nw, gb, yc, zb, br, ct, Ref{Any}(nothing))

function tower_dual_extend!(model, cons, tsupp, L, ext::RGExt)
    n0 = length(tsupp)
    prefix = copy(tsupp)                       # sorted stock prefix for bfind
    nwidx = Dict{Vector{UInt16},Int}()
    for w in ext.newwords
        haskey(nwidx, w) && continue
        bfind(prefix, w) === nothing || continue   # already a stock class
        push!(tsupp, w); push!(cons, AffExpr(0.0))
        nwidx[w] = length(tsupp)
    end
    lookup(w) = get(nwidx, w) do
        loc = bfind(prefix, w)
        loc === nothing && error("RGExt word $(w) resolves in neither stock tsupp nor newwords (hard error)")
        loc
    end
    # Γ_{2,S} dual Gram blocks (real embedding; full-matrix entries)
    for blk in ext.gramblocks
        G = @variable(model, [1:blk.dim, 1:blk.dim] in PSDCone())
        for (w, i, j, c) in blk.entries
            add_to_expression!(cons[lookup(w)], c, G[i, j])
        end
    end
    # link rows + Γ₃ duals: delegate to the validated cg_hybrid consumer
    if !isempty(ext.ycoef) || !isempty(ext.zblocks) || !isempty(ext.brows)
        tw = (nrows = length(ext.ycoef), ycoef = ext.ycoef,
              zblocks = ext.zblocks, brows = ext.brows)
        μ = @variable(model, [1:tw.nrows])
        for (r, pairs) in enumerate(tw.ycoef), (w, c) in pairs
            add_to_expression!(cons[lookup(w)], c, μ[r])
        end
        for blk in tw.zblocks
            Z = [AffExpr(0.0) for _ in 1:blk.dim, _ in 1:blk.dim]
            for (i, j, r, c) in blk.entries
                add_to_expression!(Z[i, j], c, μ[r])
                i != j && add_to_expression!(Z[j, i], c, μ[r])
            end
            @constraint(model, LinearAlgebra.Symmetric(Z) in PSDCone())
        end
        isempty(tw.brows) || @objective(model, Max,
            objective_function(model) + sum(b * μ[r] for (r, b) in tw.brows))
    end
    ext.counters["seam_newwords"] = length(nwidx)
    ext.counters["seam_tsupp_total"] = length(tsupp)
    if haskey(ENV, "RG_PROBE_MAXTIME")   # build-probe only: cap solver time
        JuMP.set_optimizer_attribute(model, "MSK_DPAR_OPTIMIZER_MAX_TIME",
                                     parse(Float64, ENV["RG_PROBE_MAXTIME"]))
    end
    ext.capture[] = model
    return nothing
end

# ------------------------------------------------------------------ pool ----
"r(N) per BASE_CONFIG"
r_of(N) = max(2, round(Int, 0.12 * N))

const PAULI_N = 3   # code = 3(i-1)+a

"canonical class + complex coefficient of a raw operator word (codes may
repeat sites; reduce! multiplies same-site letters). Returns (word, c)."
function canon(codes::Vector{UInt16}, N)
    w, c = reduce!(copy(codes); L = N, lattice = "chain", realify = false)
    return w, ComplexF64(c)
end

"""Bundle → its defining operator list as (name, ops) where each op is a
Vector{UInt16} of codes (translation orbit NOT materialized — the canonical
representative at site 1 stands for the orbit; gate G1c counts this)."""
function bundle_ops(name::String, N::Int)
    s_edge = r_of(N) + 1
    s_half = N ÷ 2
    pair(s) = [UInt16[3 * 0 + a, 3 * (s % N) + a] for a in 1:3]
    # bond product b_1 b_{1+s} = Σ_{a,b} σᵃ₁σᵃ₂ σᵇ_{1+s}σᵇ_{2+s} — the 9
    # cross terms; each is one 4-site operator word (site-1 anchored rep)
    bond(s) = [UInt16[a, 3 + a, 3 * s + b, 3 * (s + 1) + b] for a in 1:3, b in 1:3] |> vec
    name == "B_pair_edge" && return pair(s_edge)
    name == "B_half"      && return pair(s_half)
    name == "B_bond_edge" && return bond(s_edge)
    name == "B_bond_half" && return bond(s_half)
    error("unknown bundle $name")
end

const POOL = ["B_pair_edge", "B_half", "B_bond_edge", "B_bond_half"]

"""Closure of a bundle at N: canonical classes of its ops (translation,
mirror, S₃, quotient all baked into reduce!). Returns unique canonical
words with nonzero class (sign-symmetry zeros dropped)."""
function bundle_closure(name::String, N::Int)
    out = Vector{Vector{UInt16}}()
    for op in bundle_ops(name, N)
        w, c = canon(op, N)
        (abs(c) < 1e-14 || isempty(w)) && continue
        w in out || push!(out, w)
    end
    return out
end

"""Mandatory-collapse and duplicate check (fix 2/3): every closure word must
NOT be a canonical class of the mandatory basis families, and closures must
be pairwise disjoint. Returns a report Dict; asserts on failure."""
function pool_checks(N::Int)
    # mandatory 2-site classes: separations 1..r(N)
    mand2 = [canon(UInt16[a, 3 * s + a], N)[1] for a in 1:3, s in 1:r_of(N)] |> vec |> unique
    rep = Dict{String,Any}("N" => N, "r" => r_of(N))
    cls = Dict(b => bundle_closure(b, N) for b in POOL)
    for b in POOL
        clash = intersect(cls[b], mand2)
        @assert isempty(clash) "bundle $b collapses into mandatory 2-site at N=$N"
        rep[b] = length(cls[b])
    end
    for i in 1:length(POOL), j in (i+1):length(POOL)
        d = intersect(cls[POOL[i]], cls[POOL[j]])
        @assert isempty(d) "bundles $(POOL[i])/$(POOL[j]) duplicate at N=$N"
    end
    return rep
end
