# Spec — `certify_Heisenberg_square_gap` for the square-lattice J1-J2 model

> Implementation specification for the square-lattice spin-1/2 J1-J2 Heisenberg
> gap-certification SDP, by faithful translation of
> `certify_Heisenberg_kagome_gap` in `wangjie212/SpectralGap`.
>
> **Status:** spec, not runnable yet. **v2 (post-QMBCertify read):** the basis
> enumeration that v1 left open is *closed* — `QMBCertify.jl` already implements
> the full square-lattice basis + D₄/translation symmetry + SU(2) sector
> machinery (`get_basis(lattice="square")`, `reduce4`, `add_SU2_equality!`,
> `slabel`). The remaining work is integration (§5) + the γ-shift gap assembly
> (§7), not new theory or hand-enumeration.
>
> **Confidence:** the encoding, H construction, flag/bisection semantics (§2),
> and SU(2) sector prescription (§4) are confirmed by reading SpectralGap
> `src/basicfunction.jl`/`src/sdp.jl`/`example/example.jl` and QMBCertify
> `src/basic_function.jl`. The integration plan (§5–§7) is the open part.

---

## 1. Encoding reference (from `basicfunction.jl`)

The whole codebase speaks one convention; the square function must match it
exactly.

- **Operators are Pauli matrices σ^α** (NOT S = σ/2). Spin-1/2 enters through
  the explicit 1/4 factor in H (since S⃗i·S⃗j = ¼ σ⃗i·σ⃗j).
- **Integer index** for (site i, component α): `3*(i-1) + α` with α ∈ {1,2,3}
  = {x,y,z}. So site i is {3i−2 = x, 3i−1 = y, 3i = z}. N sites → indices 1..3N.
- **Monomial** = `Vector{Int}` of these indices in application order.
- **`ncpoly`** = `mutable struct ncpoly; supp::Vector{Vector{Int}}; coe::Vector{Float64}; end` — a noncommutative polynomial (support monomials + real coefficients).
- **`reduce!(a, N; model, realify, identify_zeros, symmetry)`** canonicalises any
  monomial by: (1) bubble-sort sites into increasing order (different sites
  commute), (2) cancel adjacent equal indices (since (σ^α)² = I), (3) apply
  same-site Pauli algebra σ^ασ^β = δ^{αβ}I + iε^{αβγ}σ^γ accumulating a complex
  prefactor, then (4) optionally zero it via `isz` and/or reduce by the model
  symmetry (`reduce_mirror` for Ising Z₂, `reduce_perm` for kagome S₃).
- **`isz(a; model)`** returns true (→ monomial vanishes) when the component
  counts violate the sector rule. For `model="kagome"`: vanishes if **any** of
  count_x, count_y, count_z is odd — this is the **SU(2)-scalar (S=0) sector**
  selection, and it is the rule to reuse for the square Heisenberg ground state.

## 2. CONFIRMED flag / bisection semantics (resolves cross-check §A.3 fully)

From `example/example.jl` (Ising and kagome both use the same loop) combined
with the arXiv:2606.03836 abstract:

```julia
ub, lb = <initial>, <initial>
while ub - lb > 1e-2
    gamma = (ub + lb)/2
    flag  = certify_<model>_gap(..., gamma, d, ...)
    flag == 1 ? (lb = gamma) : (ub = gamma)   # OPTIMAL → γ feasible → raise lb
end
# certified upper bound ≈ ub
```

- **`flag == 1` (OPTIMAL):** the gap-SDP at candidate γ is **feasible** — there
  exists a thermodynamic-limit state consistent with the (L,d) relaxation whose
  gap is ≥ γ. Equivalently γ ≤ Γ_{L,d}.
- **`flag == 0`:** infeasible at γ → γ > Γ_{L,d}.
- **Γ_{L,d} := sup{γ : flag==1}** is the **certified UPPER bound on Δ_bulk**,
  Γ_{L,d} ↘ Δ from above as (L,d) ↑ (per the 2606.03836 abstract). The true gap
  satisfies Δ ≤ Γ_{L,d}; a proof of gappedness (lower bound) is **not** in scope
  of this method.

So: small γ easy/feasible, large γ hard/infeasible; bisection brackets Γ_{L,d}
as the infeasibility threshold; report `ub`.

## 3. Square-lattice J1-J2 geometry + Hamiltonian (copy-pasteable)

L×L periodic lattice, N = L² sites. Index `i = y*L + x + 1` (1-based), x,y ∈
{0,…,L−1}. Unit shifts: x̂ ≡ +1 (mod L), ŷ ≡ +L. g = J₂/J₁; set J₁ = 1, J₂ = g.

```julia
function square_geometry(L)
    N = L*L
    # site index for (x,y)
    site(x, y) = mod(y, L)*L + mod(x, L) + 1
    j1_bonds = Vector{Int}[]   # nearest-neighbour (horizontal + vertical)
    j2_bonds = Vector{Int}[]   # next-nearest-neighbour (both diagonals)
    plaquettes = Vector{Int}[] # 4-site squares
    triangles  = Vector{Int}[] # 3-site J1-J1-J2 right triangles (4 per plaquette)
    for y in 0:L-1, x in 0:L-1
        i = site(x, y)
        a, b, c, d = i, site(x+1, y), site(x+1, y+1), site(x, y+1)
        # J1 bonds: take right and up only (avoids double count under PBC)
        push!(j1_bonds, sort([a, b]))
        push!(j1_bonds, sort([a, d]))
        # J2 bonds: both diagonals of the plaquette, take "forward" only
        push!(j2_bonds, sort([a, c]))
        push!(j2_bonds, sort([b, d]))
        push!(plaquettes, sort([a, b, c, d]))
        # the four J1-J1-J2 triangles in this plaquette
        for tri in ([a,b,c], [a,c,d], [a,b,d], [b,c,d])
            push!(triangles, sort(tri))
        end
    end
    unique!(sort!(j1_bonds)); unique!(sort!(j2_bonds))
    unique!(sort!(triangles))
    return (N=N, j1=j1_bonds, j2=j2_bonds, plaq=plaquettes, tri=triangles)
end

# H = J1 Σ_{<ij>} S_i·S_j + J2 Σ_{<<ij>>} S_i·S_j   (antiferromagnetic, J1=1)
function heisenberg_J1J2_hamiltonian(L, g; J1=1.0)
    geo = square_geometry(L)
    supp = Vector{Int}[]
    coe  = Float64[]
    for (J, bonds) in ((J1, geo.j1), (J1*g, geo.j2))
        for (i, j) in bonds
            push!(supp, [3i-2; 3j-2]); push!(coe, J/4)  # σ^x_i σ^x_j
            push!(supp, [3i-1; 3j-1]); push!(coe, J/4)  # σ^y_i σ^y_j
            push!(supp, [3i  ; 3j  ]); push!(coe, J/4)  # σ^z_i σ^z_j
        end
    end
    return ncpoly(supp, coe)
end
```

⚠️ **Indexing caveat (decides whether you can reuse QMBCertify):** the
`site(x,y)` above is row-major. QMBCertify's symmetry reducer `reduce4` and
basis enumerator depend on the **spiral indexing `slabel(i,j;L)`** (with inverse
`location`). To reuse QMBCertify's `get_basis`/`reduce4`/`add_SU2_equality!`
unchanged (the recommended path, §5), replace `site(x,y)` with
`slabel(x, y; L)` everywhere (geometry + H). The sanity-check counts below are
indexing-independent and stay valid either way.

Sanity checks (do these before trusting the geometry): `length(j1) == 2N`,
`length(j2) == 2N`, `length(plaq) == N`, `length(tri) == 4N`. The triangle
count is 4N because each plaquette contributes 4 distinct J1-J1-J2 triangles and
each such triangle's 3 corners determine a unique unit plaquette (no
cross-plaquette duplication); the `unique!` is therefore a no-op but kept for
safety. (Each J2 diagonal is internal to exactly one plaquette, hence
`length(j2) == 2N` = 2 diagonals × N plaquettes.)

⚠️ **These counts hold for L ≥ 3 only.** L=2 is periodic-boundary-degenerate: on
a 2×2 torus each site is its own neighbour in multiple directions (every site
has only 2 distinct nearest neighbours and 1 distinct diagonal), so the dedup
collapses to `|j1|=4, |j2|=2, |plaq|=1, |tri|=4`. **Treat L=2 as pathologic and
start real runs at L=3.** Verified by direct enumeration: L=3 → (18, 18, 9, 36)
✓; L=4 → (32, 32, 16, 64) ✓.

**g = 0 note:** at g=0 the J2 terms drop out and the `triangles` list still
exists geometrically but the J2 bonds carry zero coefficient, so the triangle
strengthening identities (cross-check §1 B2) become vacuous — consistent with
the pure-J1 square lattice having no 3-site loops.

## 4. SU(2) sector selection — already implemented in QMBCertify

Both the kagome and square Heisenberg models have global SU(2) spin symmetry;
the ground state is a singlet (S=0) and the first bulk excitation is a triplet
(S=1). The gap SDP separates them by building the moment matrices in definite
SU(2) sectors. **QMBCertify already implements this for the square lattice** —
no derivation needed, only correct invocation.

**Two label conventions exist — do not mix them:**

| package | `label` value | SU(2) sector | basis function |
|---|---|---|---|
| SpectralGap (kagome) | 1 | S = 0 scalar | `get_kagome_basis(..., label=1)` |
| SpectralGap (kagome) | 2,3,4 | S = 1 x,y,z vector | `get_kagome_basis(..., label=2/3/4)` |
| **QMBCertify (square)** | **0** | **S = 0 scalar** | `get_basis(L, 0, d; lattice="square")` |
| **QMBCertify (square)** | **1,2,3** | **S = 1 x,y,z vector** | `get_basis(L, k, d; lattice="square")` |

For the square Heisenberg (reusing QMBCertify):
- **Ground-state matrix `pos`** ← `get_basis(L, 0, d; lattice="square")` (S=0 scalar).
- **Gap matrix `gpos`** ← `get_basis(L, 1, d−1; lattice="square")` (S=1, x-vector component — one label suffices because of the additional sign/momentum reduction; use labels 1+2+3 together only in the no-symmetry variant).

**SU(2) invariance is enforced by `QMBCertify.add_SU2_equality!(model, tsupp, cons; L, lattice="square")`** — this is the concrete Casimir projection (cross-check §A.2). It walks `tsupp`, and for each monomial of a given component pattern adds a free variable and equality constraints pinning it to its SU(2)-rotated partners (e.g. `⟨σ^xσ^xσ^xσ^x⟩ = ⟨σ^yσ^yσ^xσ^x⟩ = …`). Call it once after assembling `cons`, before `optimize!`. This replaces the hand-pruning `isz` rule used by the SpectralGap kagome path with a fully rigorous SU(2) projection — and it is already written.

## 5. The basis: reuse QMBCertify — do NOT hand-write

v1 of this spec proposed hand-enumerating `get_square_basis` by analogy to
`get_kagome_basis`. That is unnecessary: **QMBCertify's `get_basis` with
`lattice="square"` already enumerates the symmetry-reduced basis per SU(2)
sector, with translation + D₄ symmetry built in.** Reuse it directly.

The cost is a convention reconciliation between the two packages:

| aspect | SpectralGap | QMBCertify | resolution |
|---|---|---|---|
| monomial element type | `Vector{Int}` | `Vector{UInt16}` | convert at the package boundary |
| **site indexing** | row-major `y*L+x+1` | **spiral `slabel(i,j;L)`** | **adopt `slabel` everywhere** (H, geometry, basis) — `reduce4` depends on it |
| label: S=0 sector | 1 | 0 | map |
| label: S=1 sector | 2 | 1 (or 1,2,3) | map |
| basis return shape | tuple `(mono, Vector{Vector{Int}})` | `Vector{UInt16}` | wrap to tuple, second slot `Int[]` (see note) |
| `reduce!` signature | `reduce!(a, N; model=…)` | `reduce!(a; L, lattice=…)` | use QMBCertify's; it carries D₄+translation |
| symmetry reducer | `reduce_perm` (triangle S₃) | `reduce4(…; lattice="square")` (D₄+translation) | use `reduce4` |

**Recommended integration (decision for Jie Wang, who owns both packages):**
implement `certify_Heisenberg_square_gap` **inside QMBCertify** (native UInt16 /
`slabel` / `reduce4` convention), porting only the gap-SDP assembly — i.e. the
`pos`/`gpos` coupling, the γ-shift on `gpos`, the `Max λ` objective, and the
bisection driver — from SpectralGap `src/sdp.jl`. This is far cleaner than
porting QMBCertify's symmetry code into SpectralGap, because the symmetry code
is large and depends on the `slabel`/`location` indexing.

The "tuple second slot" detail: SpectralGap's `get_kagome_basis` returns
`(monomial, Vector{Vector{Int}})` where the second slot is non-empty only for
specific mirror-equivalence entries consumed by the `tsupp` assembly. If porting
into SpectralGap, inspect how `certify_Heisenberg_kagome_gap` reads
`basis[i][j][2]` before deciding the wrapper shape; if implementing inside
QMBCertify, ignore — QMBCertify's flat `Vector{UInt16}` is simpler.

## 6. Component-by-component map: kagome gap → square gap (v2)

| Component | Kagome (SpectralGap) | Square (reuse QMBCertify) |
|---|---|---|
| basis construction | `get_kagome_basis` (hand-listed) | **`QMBCertify.get_basis(L, label, d; lattice="square")`** |
| bulk basis | `get_kagome_bulkbasis` | `get_basis` with the inner/bulk site set (cf. QMBCertify energy SDP) |
| symmetry reducer | `reduce_perm` (S₃) | **`reduce4(…; lattice="square")`** (D₄ + translation) |
| SU(2) sector enforcement | implicit via `isz` + label | **`add_SU2_equality!(…; lattice="square")`** (rigorous Casimir projection) |
| site indexing | row-major (kagome-specific) | **`slabel` spiral** + `location` inverse |
| `bfind`, `PSDstate_entry`, `arrange`, `generate_mons*`, `filter_mons` | — | identical logic; adapt element type `Int↔UInt16` |
| PSD block strengthening `posepsd9!` | kagome 9-site Pauli block | reuse, or add `posepsd16!` for L≥4 (`strengthening.jl`) |
| **gap-SDP assembly** (`pos`, `gpos`, γ-shift on `gpos`, `Max λ`, `cons .== 0`) | — | **port from SpectralGap `src/sdp.jl`** — this is the actual new code |
| bisection driver | — | identical (§2) |

Net: **the only genuinely new code is the gap-SDP assembly** (the `pos`/`gpos`
coupling with the γ-shift and the `Max λ` objective). Everything else is reused.

## 7. Skeleton (`certify_Heisenberg_square_gap`) — QMBCertify-native

Implement inside QMBCertify (native `UInt16` / `slabel` / `reduce4`). The body
mirrors `certify_Heisenberg_kagome_gap`'s gap-SDP assembly, but draws basis,
symmetry, and SU(2) projection from QMBCertify itself.

```julia
# to live in QMBCertify/src/ (e.g. bound_gap.jl), reusing QMBCertify's own
# get_basis, reduce!, reduce4, add_SU2_equality!, slabel, bfind, PSDstate_entry.
using JuMP, MosekTools, MathOptInterface

function certify_Heisenberg_square_gap(L::Int, H, gamma, d::Int; QUIET=false)
    # ---- basis: QMBCertify square enumerator, per SU(2) sector ----
    basis  = [QMBCertify.get_basis(L, 0, d;   lattice="square"),   # S=0 scalar  -> pos
              QMBCertify.get_basis(L, 1, d-1; lattice="square")]   # S=1 vector  -> gpos
    lb  = length.(basis)
    # NOTE: SpectralGap uses two gbasis blocks at d-1 ("bulk" basis); QMBCertify's
    # energy SDP uses a single basis per sector. Decide whether the gap matrix
    # needs the bulk-restriction split (cf. get_kagome_bulkbasis) or whether the
    # full d-1 basis suffices — this is the one structural choice to confirm
    # against the kagome gap function's use of gbasis/gpos.

    # ---- tsupp collection + PSD variable assembly (pos, gpos) ----
    # PORT from SpectralGap certify_Heisenberg_kagome_gap: build the affine
    # constraint vector `cons` indexed by `tsupp`; `pos[1]` PSD over basis[1],
    # `pos[2]` PSD over basis[2]; couple `gpos` to `pos` through H-moments
    # (PSDstate_entry) with the γ-shift on the gap block
    #   add_to_expression!(cons[Locb], -c*gamma, gpos[...])
    #   add_to_expression!(cons[Locb],  gamma,    gpos[...])   # mirrored entry
    # using QMBCertify.reduce!(a; L, lattice="square") on every monomial.

    # ---- SU(2) projection (QMBCertify native) ----
    QMBCertify.add_SU2_equality!(model, tsupp, cons; L=L, lattice="square")

    # ---- objective + solve (identical to SpectralGap) ----
    @variable(model, λ)
    cons[1] += λ
    @objective(model, Max, λ)
    @constraint(model, cons .== 0)
    optimize!(model)
    return termination_status(model) == MathOptInterface.OPTIMAL ? 1 : 0
end
```

Driver (caller-side), identical bisection structure to SpectralGap
`example/example.jl` (§2):

```julia
L, g, d = 4, 0.5, 2
H       = heisenberg_J1J2_hamiltonian(L, g)   # uses slabel indexing (§3 caveat)
ub, lb  = 4.0, 0.0
while ub - lb > 1e-2
    gamma = (ub+lb)/2
    flag  = certify_Heisenberg_square_gap(L, H, gamma, d)
    flag == 1 ? (lb = gamma) : (ub = gamma)
end
println("certified upper bound on Δ_bulk ≈ ", ub)
```

## 8. Open questions for Jie Wang (integration, not theory)

The basis enumeration and SU(2)/D₄ machinery are no longer open — QMBCertify has
them. What remains is integration:

1. **Where does the function live?** Recommend *inside QMBCertify* (native
   convention). Confirm with Jie — he owns both packages and may prefer a port
   into SpectralGap for the gap-paper repo consistency.
2. **`gbasis`/bulk-basis split.** SpectralGap's kagome gap uses a separate
   `gbasis` (bulk, d−1) coupled to `gpos`. Confirm whether the square gap needs
   the same bulk-restriction or whether a single d−1 basis per sector suffices.
3. **`posepsd9!` reuse.** Kagome uses the 9-site Pauli-tensor PSD block. For
   L≥4 square, confirm whether to reuse it or add `posepsd16!`.
4. **Mosek 11 compatibility.** Team README flags a zero-dim PSD cone bug in the
   kagome path under Mosek 11; confirm whether the square path inherits it and
   whether the Clarabel fallback (patched in the fork) covers it.

## 9. Validation ladder (no new compute needed beyond what's planned)

1. **g=0 Shastry–Sutherland** (Δ_bulk = 1 exact, product of singlets) — must
   recover Γ → 1. This simultaneously validates H construction, sector
   enumeration, and labels the OPTIMAL/INFEASIBLE flag (§2).
2. **Square J1-J2 g=0, L=3, d=2** — smallest *non-degenerate* square run (L=2
   is PBC-pathologic, see §3); exposes whether the QMBCertify basis/SU(2)
   integration is correctly wired.
3. **Square J1-J2 g=0.5, L=3→4, d=2** — the contested regime; compare Γ_{L,d}
   against ED/DMRG finite-size gaps (must stay above them, since Γ is an upper
   bound).
