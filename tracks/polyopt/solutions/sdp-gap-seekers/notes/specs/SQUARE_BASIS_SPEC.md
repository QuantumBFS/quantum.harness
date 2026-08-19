# Square J1-J2 gap certifier — structured-basis interface spec

> ## ⚠️ CORRECTION BANNER (2026-07-28, per advisor P1 review)
>
> This document was written before the advisor audit and contains **several
> claims now known to be wrong**. Do not implement it verbatim. The authoritative
> plan is the older `spectralgap-refactor-plan.md` (generic, unsymmetrized
> baseline first). Specific retractions:
>
> 1. **"Square Heisenberg g=0 is gapped / positive gap ~1" is FALSE.** The 2D
>    spin-1/2 square Heisenberg antiferromagnet has Néel order + gapless
>    Goldstone modes. A finite relaxation may return a positive number, but that
>    does not certify a physical gap. The correct **positive-gap calibration is
>    Shastry-Sutherland g=0 (Δ_bulk = 1)** — also an official #88 target.
> 2. **The kagome `reduce!` does NOT supply Square spatial symmetry.** For
>    `model="kagome"` it does component-count parity zeroing + cyclic X/Y/Z
>    identification (`reduce_perm`). It applies **no** square translations, C4
>    rotations, or mirrors, and is **not a full SU(2) irrep quotient**. Treat
>    `label ∈ {1..4}` as legacy word-selection sectors, not scalar/vector SU(2)
>    blocks, until a representation-theoretic derivation exists.
> 3. **Recommended order (advisor):** (a) explicit unsymmetrized positive/gap/
>    stationarity basis first — no hidden symmetry; (b) review PR #3's
>    `basis_manifest(problem, role)` directly before treating Square as
>    unblocked; (c) coefficient-by-coefficient legacy regression against a TFIM
>    or kagome wrapper; (d) only then connect the Square Hamiltonian; (e) add
>    symmetry generators one at a time, each tested as a Hamiltonian automorphism.
> 4. The validated `ncpoly` H construction in `src/SquareGapCertify.jl`
>    (term counts, spin normalization) remains reliable — only the *basis +
>    symmetry* parts above are retracted.
>
> ---

> Target: a `certify_Heisenberg_square_gap` that produces upper bounds
> on the bulk spectral gap of the 2D square-lattice J1-J2 Heisenberg model,
> filling the one gap in `SpectralGap.jl`'s turnkey certifiers (Ising + kagome
> exist; square does not). This doc specifies the missing piece — the
> square-structured basis — as the integration target for
> `feature/structured-basis-assembly`.
>
> Status: the H construction + patch geometry are DONE + validated
> (`src/SquareGapCertify.jl`, see below). The structured basis is the open piece.

## What is already done (xcai side, this branch)

`src/SquareGapCertify.jl` provides, validated against exact bond counts:

- `square_j1j2_terms(L; g, J1)` → `(supp, coe, N, patch)`: the Hamiltonian in
  SpectralGap `ncpoly` encoding (site `i` → `3i-2=X, 3i-1=Y, 3i=Z`), with
  `H = J1·Σ_{J1} S_i·S_j + J2·Σ_{J2} S_i·S_j`, `S_i·S_j = ¼(XX+YY+ZZ)`, `J2=g·J1`.
  Validated: L=1 → 9 sites / 60 terms / coefs {0.25, 0.125}; L=2 → 25 sites / 216 terms.
- `square_patch_geometry(L; g)` → `(N, inner_ids, j1_bonds, j2_bonds, patch)`:
  the geometry the basis must cover (outer `N=(2L+1)²` sites; one-layer-eroded
  inner `(2L-1)²` sites where stationarity/gap constraints live; J1 NN +
  J2 diagonal-NNN bond lists).

These mirror how `certify_Heisenberg_kagome_gap` consumes `(N, H, triples, edges,
inner_triples, inner_edges)` — square replaces "triples/edges" with "J1/J2 bonds".

## What is needed: `get_square_basis` + `get_square_bulkbasis`

Two functions, exact analogs of `get_kagome_basis` / `get_kagome_bulkbasis`
(`SpectralGap.jl` is pinned at commit `a1171c9`, NOT modified — these live in the
team module or a downstream package and reach SpectralGap's exported `ncpoly` +
the SDP assembly):

```julia
get_square_basis(N, j1_bonds, j2_bonds, d; label)        # positivity basis, degree d
get_square_bulkbasis(N, inner_j1, inner_j2, d; label)    # gap basis, degree d-1, inner patch
```

Each returns a `Vector{Tuple{Vector{Int}, Vector{Vector{Int}}}` of (word,
state-symbols) pairs in the same format as the kagome basis (consumed verbatim
by the SDP assembly). `label` ∈ {1,…,4} selects the **SU(2) spin-rotation
sector** (scalar + 3 vector components) — identical sector structure to kagome,
since both are Heisenberg (SU(2)-symmetric).

### Reduction rules (REUSE — no new code)

Square Heisenberg is SU(2)-symmetric, so it uses the **same reduction as kagome**:
`reduce!(..., model="kagome")` applies `reduce_perm` (the X→Y→Z cyclic /
spin-rotation reduction) and `isz(..., model="kagome")` gives the SU(2) parity.
No `model="square"` branch is needed — the kagome branch is the SU(2) branch.
(The Ising `reduce_mirror` is the Z₂ *spatial* mirror of the 1D chain and does
NOT apply to the 2D square patch.)

### Basis content per label + degree (the curation R&D)

Following `get_kagome_basis`'s pattern, per label enumerate symmetry-distinct
Pauli words on the square patch, by degree:

| degree | content (square analogue of kagome) |
|---|---|
| 1 | single-site words (`[3i-2]` etc.) + their state-symbol lifts |
| 2 | two-site words on **J1 bonds** and **J2 bonds**: `[3i-2;3j-2]`, `[3i-1;3j-1]`, `[3i;3j]` (XX/YY/ZZ) per bond |
| 3 | three-site words on J1-J1 / J1-J2 paths (the square has no triangles — use right-angle 3-site paths on plaquettes instead of kagome's chiral triangle words) |
| 4 | four-site **plaquette** words (the square's elementary loop — the analogue of the kagome triangle) — these first appear at d>2, as in kagome |

The square plaquette (4-site loop) is the geometric analogue of the kagome
triangle — it carries the frustration/chirality structure for J1-J2. Which
specific plaquette words appear per label is the SU(2)-sector curation that
mirrors lines 325–338 of `get_kagome_basis`.

### Lattice symmetry handling

The basis selects **representative** words; full symmetry reduction (translation,
C4 rotation, mirror of the square) is applied during SDP assembly via `reduce!`
+ the locality filter. The basis need only list one representative per orbit, as
`get_kagome_basis` does for kagome.

## `certify_Heisenberg_square_gap` — signature + assembly (template)

```julia
function certify_Heisenberg_square_gap(N, H, j1_bonds, j2_bonds,
                                       inner_j1, inner_j2, gamma, d; lso=5, QUIET=false)
    # identical SDP assembly to certify_Heisenberg_kagome_gap (sdp.jl:347),
    # with exactly two substitutions:
    #   get_kagome_basis(...)      -> get_square_basis(N, j1_bonds, j2_bonds, d; label)
    #   get_kagome_bulkbasis(...)  -> get_square_bulkbasis(N, inner_j1, inner_j2, d-1; label)
    # reduction stays model="kagome" (SU(2)). Everything else (positivity block,
    # gap block with -gamma*c + gamma*mirror-variance term, lso stationarity,
    # Mosek solve, flag=(status==OPTIMAL)) is unchanged.
end
```

The assembly body is ~150 lines and copies verbatim from `sdp.jl:347` with those
two call-site substitutions. It is not written here because (a) it cannot be
tested without the basis, and (b) copying SpectralGap's unexported internals
(`PSDstate_entry`, `generate_mons`, `filter_mons`) is fragile — cleaner to add
`certify_Heisenberg_square_gap` + `get_square_basis` as a thin extension once the
basis exists, reaching SpectralGap's exported `ncpoly` only.

## Validation plan (once the basis lands)

1. **Sanity (g=0, L=1):** the 3×3 patch with only J1 bonds should give a finite,
   positive gap upper bound of order ~1 (the square Heisenberg is gapped); no
   MosekError / empty-block (the d=2-kagome failure mode).
2. **Frustration (g=0.5, L=2):** the 5×5 patch at the challenge point should give
   a finite bound; the J2 bonds add frustration but the SDP must remain feasible
   at small γ.
3. **Monotonicity:** as L or d increase, the bound must be **non-increasing**
   (SPEC §1 / arXiv:2606.03836) — the SPEC §12 Gate 6 check.
4. **Direction:** feasible at small γ, infeasible above γ*, no reversals (the
   same dual-run check Sihan's side applies to kagome).

## Division of labor

| piece | owner | status |
|---|---|---|
| H construction + patch geometry (`SquareGapCertify.jl`) | xcai | **done + validated** |
| `get_square_basis` / `get_square_bulkbasis` | structured-basis-assembly (Sihan) | spec'd here, pending |
| `certify_Heisenberg_square_gap` (assembly template) | xcai | blocked on basis (template above) |
| dual-run repro + §8 witness audit | both | after first square result |
