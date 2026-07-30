# DIAGNOSTIC EXTRACT — read-only build probes (2026-07-30, CST)

## 1. COUNTER TABLE

Nine build-only rows; every row aborted inside the seam hook AFTER extension,
before any MOSEK call. Batches: rows R1/R3/R4 and R2/R5–R9 both ran under
`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`, `timeout 180`
per row, one process per row. No row was KILLED.

psd_scalars = scalarized entries over all PSD constraints in the JuMP model at
seam-hook exit (stock + extension); largest_block = largest PSD dim;
n_rows = length(tsupp); nnz = Σ linear terms over cons; peak_RSS =
Sys.maxrss() of the row's own julia process; build_s wraps the GSB_cg call.

| row | N | chassis | rg | S | vspace | status | psd_scalars | largest_block | n_rows | nnz | seam_newwords | build_s | peak_RSS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 10 | rdm=8,lso=true | off | none | stock | OK | 23900 | 70 | 641 | 224899 | 0 | 24.2 | 1.32G |
| R2 | 10 | rdm=8,lso=true | on | pilot | auto | OK | 73491 | 128 | 641 | 225521 | 0 | 57.6 | 1.41G |
| R3 | 10 | rdm=false,lso=false | off | none | stock | OK | 19376 | 66 | 472 | 88595 | 0 | 15.4 | 1.33G |
| R4 | 10 | rdm=false,lso=false | off | none | auto | OK | 19376 | 66 | 472 | 88595 | 0 | 22.8 | 1.33G |
| R5 | 10 | rdm=false,lso=false | off | pilot | auto | OK | 19431 | 66 | 472 | 88625 | 0 | 17.0 | 1.27G |
| R6 | 10 | rdm=false,lso=false | on | none | auto | OK | 68912 | 128 | 472 | 89187 | 0 | 16.0 | 1.37G |
| R7 | 10 | rdm=false,lso=false | on | pilot | auto | OK | 68967 | 128 | 472 | 89217 | 0 | 15.0 | 1.35G |
| R8 | 8 | rdm=false,lso=false | on | pilot | auto | OK | 64676 | 128 | 145 | 53579 | 0 | 14.9 | 1.32G |
| R9 | 12 | rdm=false,lso=false | on | pilot | auto | OK | 73258 | 128 | 726 | 134041 | 0 | 14.8 | 1.37G |

gamma2_dim = 10 on every S=pilot row; rg_rows = 768 on every rg=on row
(identical across R7/R8/R9, i.e. across N = 8/10/12). "SDP size" log line at
abort: n = 66 on every row; m equals the n_rows column.

## 2. DEFINITIONS

BASELINE arm of the 10:21 observation — selection_arm.jl:12-18 with
KEY = "BASELINE" ⇒ S = String[]:

```julia
const KEY = ARGS[1]
const N = 10; const NRG = 6
As = load_D4()
rg = rg_spec(N, NRG, As)
S = KEY == "BASELINE" ? String[] : Vector{String}(sort(split(KEY, "+")))
GC.gc()
t0 = time()
r = build_rg_selection_model(N; S = S, rg = rg, vspace = :auto,
                             rdm = false, pso = 0, lso = false)
```

kwargs: N=10, S=[], rg=rg_spec(10,6,As), vspace=:auto, rdm=false, pso=0,
lso=false. RG active: YES. Selected bundles active: NO (S empty ⇒ no Γ₂
block). The kill happened mid-solve.

The 16.9 G figure = whole-julia-process RSS from `ps` (kB column). It is not
a systemd-scope statistic and not an in-process counter. Measurement line
(10:21):

```
$ ps -o pid,etime,rss,args -p 23859
  23859       04:58 16957636 /home/outerlink/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu/bin/julia selection_arm.jl BASELINE
```

## 3. CODE — verbatim

### 3a. build_rg_selection_model signature + vspace branch — src/rg_builder.jl:12-47

```julia
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
```

(vspace=:auto adds no words of its own — only gb.prods and rg.words enter;
:pool additionally prepends vpool_words(N); :stock with S/rg still builds ext.)

### 3b. Seam new-word admission + non-redundancy — src/local_cone_adapter.jl:29-42

```julia
    n0 = length(tsupp)
    prefix = copy(tsupp)                       # sorted stock prefix for bfind
    nwidx = Dict{Vector{UInt16},Int}()
    for w in ext.newwords
        haskey(nwidx, w) && continue               # dedup vs EACH OTHER
        bfind(prefix, w) === nothing || continue   # already a stock class
        push!(tsupp, w); push!(cons, AffExpr(0.0))
        nwidx[w] = length(tsupp)
    end
    lookup(w) = get(nwidx, w) do
        loc = bfind(prefix, w)
        loc === nothing && error("RGExt word $(w) resolves in neither stock tsupp nor newwords (hard error)")
        loc
    end
```

New words are deduplicated BOTH against each other (`haskey(nwidx, w)` at
local_cone_adapter.jl:33, plus upstream `unique!(newwords)` at
rg_builder.jl:40) AND against the core closure (`bfind(prefix, w)` at
local_cone_adapter.jl:34). Additional upstream dedup:
moment_bundles.jl:30 `w in prods || push!(prods, w)`;
functional_rg.jl:29 `words = unique(first.(vcat(tw.ycoef...)))`.

### 3c. Every site where a translation orbit becomes words/entries

src/local_cone_adapter.jl:95-107 (bundle_ops — one site-1-anchored
representative per operator; comment 93-94: "translation orbit NOT
materialized"):

```julia
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
```

src/local_cone_adapter.jl:114-122 (bundle_closure — canon() per op, dedup):

```julia
function bundle_closure(name::String, N::Int)
    out = Vector{Vector{UInt16}}()
    for op in bundle_ops(name, N)
        w, c = canon(op, N)
        (abs(c) < 1e-14 || isempty(w)) && continue
        w in out || push!(out, w)
    end
    return out
end
```

src/moment_bundles.jl:7-17 (O_rows — loop over separations 1..r(N), not
sites; canonical representative per class):

```julia
function O_rows(S::Vector{String}, N::Int)
    rows = Vector{Vector{UInt16}}()
    for s in 1:r_of(N), a in 1:1        # S3 quotient: one component rep
        w, c = canon(UInt16[a, 3 * s + a], N)
        abs(c) > 1e-14 && !(w in rows) && push!(rows, w)
    end
    for b in S, w in bundle_closure(b, N)
        w in rows || push!(rows, w)
    end
    return rows
end
```

src/moment_bundles.jl:22-41 (gamma2_block — i,j over row representatives;
≤4 real-embedding entries per (i,j); prods deduped):

```julia
function gamma2_block(S::Vector{String}, N::Int)
    O = O_rows(S, N)
    t = length(O)
    entries = Tuple{Vector{UInt16},Int,Int,Float64}[]
    prods = Vector{Vector{UInt16}}()
    for i in 1:t, j in 1:t
        w, c = canon(vcat(O[i], O[j]), N)
        abs(c) < 1e-14 && continue
        w in prods || push!(prods, w)
        re, im_ = real(c), imag(c)
        if abs(re) > 1e-14
            push!(entries, (w, i, j, re))            # R block (1,1)
            push!(entries, (w, t + i, t + j, re))    # R block (2,2)
        end
        if abs(im_) > 1e-14
            push!(entries, (w, i, t + j, -im_))      # -I block (1,2)
            push!(entries, (w, t + i, j, im_))       # +I block (2,1)
        end
    end
    return (dim = 2t, entries = entries, rows = O, prods = prods)
end
```

cg_hybrid/tower_gen.jl:66-79 (rho3_groups — loop over the 4³ window Pauli
words, window-anchored; reduce! canonicalizes; accumulate per class):

```julia
function rho3_groups(L::Int)
    groups = Dict{Vector{UInt16},Matrix{ComplexF64}}()
    for b1 in 0:3, b2 in 0:3, b3 in 0:3
        b = (b1, b2, b3)
        codes = UInt16[3 * (t - 1) + b[t] for t in 1:3 if b[t] > 0]
        w, c = reduce!(copy(codes); L = L, lattice = "chain", realify = true)
        c == 0 && continue
        @assert abs(imag(c)) < 1e-14 "unexpected complex reduce! coef for distinct-site word"
        Wm = kron((t == 0 ? σI : PMATS[t] for t in b)...)
        G = get!(() -> zeros(ComplexF64, 8, 8), groups, w)
        G .+= (real(c) / 8) .* Wm
    end
    return groups
end
```

cg_hybrid/tower_gen.jl:123-138 (push_rows! — rows indexed by Hermitian dual
basis elements, not by site):

```julia
        for f in hermbasis(t)
            yr = Tuple{Vector{UInt16},Float64}[]
            if yimg !== nothing
                for (w, T) in yimg
                    c = hcoord(f, T)
                    abs(c) > 1e-12 && push!(yr, (w, c))
                end
            end
            sr = Tuple{Int,Int,Float64}[]
            for (blk, sgn, imgs) in ωimg, (k, T) in enumerate(imgs)
                c = sgn * hcoord(f, T)
                abs(c) > 1e-12 && push!(sr, (blk, k, c))
            end
            (isempty(yr) && isempty(sr)) && continue
            push!(ycoef, yr); push!(sent, sr)
        end
```

cg_hybrid/tower_gen.jl:144-166 (link loops — over parities p∈{1,2} and tower
levels M∈4..n−1, not sites):

```julia
    for p in 1:2
        W2p = chainmap2(As, 2, p + 1)
        Xp  = kron(σI, W2p)
        X2p = kron(W2p, σI)
        push_rows!(2mm, ρ -> ptr_mid(Xp * ρ * Xp', 2mm, mm, 1),
            [(blk(4, p), Ω -> ptr_last(ptr_mid(Ω, 2mm, mm, 2), 2mm), -1.0)])
        ...
    for M in 4:(n - 1), p in 1:2
        pr = mod1(p + M - 1, 2)
        TRp = kron(Matrix{ComplexF64}(I, 2mm, 2mm), bmat(As[pr]))
        ...
```

No loop over site indices 1..N pushing into word/entry containers exists in
the build path; N enters only through `reduce!(...; L = N)`.

### 3d. kron / zeros( / Matrix{ / Array{ inside per-word or per-orbit loops

```
cg_hybrid/tower_gen.jl:74   Wm = kron(...)            in: for b1 in 0:3, b2 in 0:3, b3 in 0:3
cg_hybrid/tower_gen.jl:75   zeros(ComplexF64, 8, 8)   in: same loop (via get! default)
cg_hybrid/tower_gen.jl:95   zeros(ComplexF64, mm*mm, 2^k)  in: chainmap2 body (per call; the μs loop follows)
cg_hybrid/tower_gen.jl:146  Xp  = kron(σI, W2p)       in: for p in 1:2
cg_hybrid/tower_gen.jl:147  X2p = kron(W2p, σI)       in: for p in 1:2
cg_hybrid/tower_gen.jl:157  TRp = kron(Matrix{ComplexF64}(I, 2mm, 2mm), bmat(As[pr]))  in: for M in 4:(n-1), p in 1:2
cg_hybrid/tower_gen.jl:162  TLp = kron(bmat_left(As[pl]), Matrix{ComplexF64}(I, mm*2, mm*2))  in: same loop
src/local_cone_adapter.jl:59  Z = [AffExpr(0.0) for _ in 1:blk.dim, _ in 1:blk.dim]  in: for blk in tw.zblocks
src/functional_rg.jl:42     built = zeros(ComplexF64, mm*mm, 2^(k+1))  in: for q in 1:2, k in 2:kmax  (compat_residual: G2 gate only, not model build)
```

### 3e. Counter emission

src/local_cone_adapter.jl:69-70:

```julia
    ext.counters["seam_newwords"] = length(nwidx)
    ext.counters["seam_tsupp_total"] = length(tsupp)
```

src/rg_builder.jl:23,29,30,31,39,42 — `vpool_words`, `gamma2_dim`,
`gamma2_entries`, `O_rows`, `rg_rows`, `newwords` = lengths of the containers
shown in 3a.

src/rg_builder.jl:59-61 (solver-side sizes parsed from the captured log —
MOSEK-emitted lines absent in build-only rows; the table's psd_scalars/nnz
are JuMP-model counts taken at the seam hook by the probe):

```julia
    m = match(r"SDP size: n = (\d+), m = (\d+)", log)
    mos = match(r"Matrix variables\s+: (\d+) \(scalarized: (\d+)\)", log)
    con = match(r"Constraints\s+: (\d+)", log)
```

## 4. FACTS

- Worktree ~/code/qh-method: branch `method-lane`, HEAD 91af879 (after the
  execution-record commit; the diagnostic probes ran read-only at bef4dc6).
- Main checkout ~/code/quantum.harness: branch
  `challenge/polyopt-coarse-grained-npa`, HEAD a80fc54; `git status --short`:
  `M tracks/polyopt/solutions/its-a-trap/hpc/refs/bethe_ref.json`.
- method-lane `git status --short` after the record commit: clean except
  `?? .external` (untracked by design, chmod-protected QMBCertify pin).
- r123 verdicts (results/a200_release_gates.csv): R1 PASS, R2 PASS, R3 PASS;
  R4b PASS (10:46, before the kill order). R4c not completed (killed 10:50).

## 5. ALLOC

diag_alloc pass (R7 configuration, Profile.Allocs, sample_rate = 1e-3, one
warm pass then one profiled pass; first repo frame per allocation; sampled
bytes, multiply by ~10³ for the rate):

```
gsb_cg.jl:152                  0.3 MB sampled
local_cone_adapter.jl:59       0.0 MB sampled
local_cone_adapter.jl:61       0.0 MB sampled
local_cone_adapter.jl:62       0.0 MB sampled
local_cone_adapter.jl:54       0.0 MB sampled
```

Whole-build peak RSS in the same configuration: 1.35 G (table row R7).
