# Spec — `certify_Heisenberg_square_gap` for the square-lattice J1-J2 model

> Implementation specification for the square-lattice spin-1/2 J1-J2 Heisenberg
> gap-certification SDP, by faithful translation of
> `certify_Heisenberg_kagome_gap` in `wangjie212/SpectralGap`.
>
> **Status:** spec, not runnable yet. Everything below is determined except the
> hand-enumerated basis lists in `get_square_basis` / `get_square_bulkbasis`
> (§5), which must be adapted from `get_kagome_basis` to square geometry and
> validated against the Shastry–Sutherland g=0 → Δ=1 benchmark.
>
> **Confidence:** the encoding, the H construction, the flag/bisection
> semantics (§3), and the SU(2) sector prescription (§4) are confirmed by
> reading `src/basicfunction.jl`, `src/sdp.jl`, and `example/example.jl`. The
> basis enumeration (§5) is the one open implementation task.

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

## 4. SU(2) sector selection — the one piece with no Ising analog

This is the crux and the main theoretical content. Both the kagome and square
Heisenberg models have global SU(2) spin symmetry; the ground state is a singlet
(S=0) and the first bulk excitation is a triplet (S=1). The gap SDP separates
them by building the moment matrices in definite SU(2) sectors. The kagome code
realises this through the `label` argument of `get_kagome_basis`:

| `label` | SU(2) sector | Content pattern (kagome) | Square analog |
|---|---|---|---|
| 1 | **S = 0 (scalar)** | even-parity pair monomials `σ^α_i σ^β_j`; `isz` = all component counts even | ground-state matrix `pos` |
| 2 | **S = 1, x-component** | `σ^x_i` + paired structures | gap matrix `gpos` (vector sector) |
| 3 | **S = 1, y-component** | `σ^y_i` + paired structures | (only with full symmetry) |
| 4 | **S = 1, z-component** | `σ^z_i` + paired structures | (only with full symmetry) |

`certify_Heisenberg_kagome_gap` (sign-symmetry ON) uses **labels [1, 2]** —
label 2 collects the vector sector after the additional Z₂ sign reduction. The
`_nosignsymmetry` variant uses **labels [1,2,3,4]**.

**Prescription for the square Heisenberg:**
- **Ground-state matrix `pos`** → square `label=1` basis, pruned by
  `isz(model="kagome")` (the all-counts-even SU(2)-scalar rule — reuse verbatim,
  it is not kagome-specific).
- **Gap matrix `gpos`** → square `label=2` basis (S=1 vector sector).
- The further block-diagonalisation by lattice translations + D₄ (Problem C of
  the original note) is an **additional** reduction for scaling, not required
  for correctness. Implement the `_nosignsymmetry`-style path first (no momentum
  blocking), validate, then add symmetry blocking to push L.

## 5. What must be written new: `get_square_basis` / `get_square_bulkbasis`

These are the only genuinely new code. They enumerate, per `label` and degree
`d`, the monomials spanning each SU(2) sector, structured by the square geometry
(edges / triangles / plaquettes) — exactly as `get_kagome_basis` enumerates by
`triples`/`edges`. **Adapt line-by-line from `get_kagome_basis`, replacing
triangle geometry with square geometry.** Required content per label:

```julia
# REQUIRED (signature mirrors kagome; plaquettes/triangles replace triples)
function get_square_basis(N, edges, triangles, plaquettes, d; label=1)
    # label == 1 : S=0 scalar sector — even-parity σ^α_i σ^β_j pairs over edges,
    #              plus (d>2) plaquette-scalar 4-operator combinations.
    #              Reuse the label==1 block structure of get_kagome_basis,
    #              swapping `triples` for `triangles`/`plaquettes` as appropriate.
    # label == 2 : S=1 x-component — single σ^x_i at each site, plus paired
    #              structures built from edges/triangles (mirror of kagome label 2).
    # labels 3,4 : S=1 y,z-components (only needed for the nosignsymmetry path).
    ...
end

function get_square_bulkbasis(N, edges, triangles, plaquettes, d; label=1)
    # same sector content at one degree lower, restricted to "bulk" sites
    # (interior, cf. get_kagome_bulkbasis which restricts to inner triangles).
    ...
end
```

The kagome versions are ~80 lines of explicit monomial lists; the square
versions will be similar in size. **This is the one task to do with Jie Wang
(or by lifting the square-Heisenberg symmetry reduction already present in
`QMBCertify.jl`, which certifies the square-Heisenberg *energy* and therefore
already enumerates these sectors).** Validate by running the g=0
Shastry–Sutherland benchmark (Δ=1 exact) — wrong sector enumeration will not
recover Δ=1.

## 6. Component-by-component map: kagome gap → square gap

Everything outside §5 carries over **verbatim** from
`certify_Heisenberg_kagome_gap` / `certify_Heisenberg_kagome_gap_nosignsymmetry`:

| Component | Kagome | Square |
|---|---|---|
| basis construction | `get_kagome_basis` | `get_square_basis` (§5, new) |
| bulk basis | `get_kagome_bulkbasis` | `get_square_bulkbasis` (§5, new) |
| symmetry reducer | `reduce_perm` (triangle S₃) | `reduce_square_sym` (D₄ on plaquettes — new, optional for v1) |
| sector pruning | `isz(model="kagome")` | **identical** (SU(2) scalar rule) |
| `reduce!`, `bfind`, `PSDstate_entry`, `arrange`, `generate_mons*`, `filter_mons` | — | **identical** (geometry-agnostic) |
| PSD block strengthening `posepsd9!` | kagome-specific Pauli tensor block | reuse `posepsd9!` or add `posepsd16!` if pushing L≥4 (see `strengthening.jl`) |
| SDP assembly (`pos`, `gpos`, the γ-shift, `Max λ`, `cons .== 0`) | — | **identical** |
| bisection driver | — | **identical** (§2) |

## 7. Skeleton (`certify_Heisenberg_square_gap`)

Structural — the body is the kagome function with the four substitutions from
§6. Lines marked `# ==` are verbatim; `# NEW` need the §5 helpers.

```julia
function certify_Heisenberg_square_gap(N::Int, H::ncpoly, edges, triangles,
                                       plaquettes, inner_edges, inner_triangles,
                                       inner_plaquettes, gamma, d::Int;
                                       lso=4, QUIET=false)
    # ---- basis (NEW: square geometry versions of get_kagome_basis) ----
    basis  = [get_square_basis(N, edges, triangles, plaquettes, d, label=i) for i in 1:2]   # NEW
    lb     = length.(basis)
    gbasis = [get_square_bulkbasis(N, inner_edges, inner_triangles, inner_plaquettes,
                                   d-1, label=i) for i in 1:2]                                # NEW
    lgb    = length.(gbasis)

    # ---- support collection, PSD variable assembly, γ-shift, Max λ ----
    # == verbatim from certify_Heisenberg_kagome_gap, with model="kagome" kept ==
    # == on every reduce!/PSDstate_entry/filter_mons call (the SU(2) isz rule  ==
    # == is identical), and reduce_perm left as-is or replaced by reduce_square_sym.

    # ---- strengthening ----
    posepsd9!(model, cons, tsupp)   # == ; upgrade to posepsd16! only for L>=4

    @variable(model, λ)
    cons[1] += λ
    @objective(model, Max, λ)
    @constraint(model, cons .== 0)
    optimize!(model)
    flag = termination_status(model) == MathOptInterface.OPTIMAL ? 1 : 0
    return flag
end
```

Driver (caller-side), identical structure to `example/example.jl`:

```julia
L, g, d = 4, 0.5, 2
geo      = square_geometry(L)
H        = heisenberg_J1J2_hamiltonian(L, g)
igeo     = square_geometry(L-1)          # "bulk"/inner geometry, cf. kagome inner triples
ub, lb   = 4.0, 0.0                       # widen as needed
while ub - lb > 1e-2
    gamma = (ub+lb)/2
    flag  = certify_Heisenberg_square_gap(geo.N, H, geo.j1, geo.tri, geo.plaq,
                                          igeo.j1, igeo.tri, igeo.plaq, gamma, d)
    flag == 1 ? (lb = gamma) : (ub = gamma)
end
println("certified upper bound on Δ_bulk ≈ ", ub)
```

## 8. Open questions for Jie Wang (the basis enumeration)

1. **`get_square_basis` content per label** — confirm the square-geometry
   analog of each kagome monomial list. Best route: lift the square-Heisenberg
   sector enumeration already implemented in `QMBCertify.jl` (energy
   certification for this exact model) rather than re-derive.
2. **D₄ plaquette symmetry reducer** — `reduce_perm` handles triangle S₃; the
   square needs a D₄ equivalent. Optional for v1 (the `_nosignsymmetry` path
   skips it), required to reach L ≥ 4.
3. **`posepsd9!` vs higher** — the kagome path uses the 9-site Pauli-tensor PSD
   block (`strengthening.jl`). Confirm whether to reuse it or add a 16-site
   `posepsd16!` for L = 4.
4. **Mosek 11 compatibility** — the team README flags a zero-dim PSD cone bug in
   the existing kagome path under Mosek 11; confirm whether the square path
   inherits it and whether the Clarabel fallback (already patched in the fork)
   covers it.

## 9. Validation ladder (no new compute needed beyond what's planned)

1. **g=0 Shastry–Sutherland** (Δ_bulk = 1 exact, product of singlets) — must
   recover Γ → 1. This simultaneously validates H construction, sector
   enumeration, and labels the OPTIMAL/INFEASIBLE flag (§2).
2. **Square J1-J2 g=0, L=3, d=2** — smallest *non-degenerate* square run (L=2
   is PBC-pathologic, see §3); exposes whether `get_square_basis` is correctly
   wired.
3. **Square J1-J2 g=0.5, L=2→4, d=2** — the contested regime; compare Γ_{L,d}
   against ED/DMRG finite-size gaps (must stay above them, since Γ is an upper
   bound).
