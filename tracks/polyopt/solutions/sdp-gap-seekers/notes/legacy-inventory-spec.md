# Legacy inventory snapshot — spec

> Reference-data capture for `spectralgap-refactor-plan.md` §3 D1 ("snapshot
> tests for every old block size and affine-constraint count") and acceptance
> test 6 ("Legacy Ising/Kagome wrappers reproduce old basis/block inventories").
> Also feeds the coefficient-by-coefficient comparison against the generic
> adapter (`GenericGapModel.legacy_ncpoly_data`).

## What is captured

`scripts/dump_legacy_inventory.jl` emits, for each of the two validated small
cases, a deterministic plain-text record:

| field | meaning |
|---|---|
| `H.supp` / `H.coe` | the legacy `ncpoly` (support monomials + coefficients) |
| `basis.label{1,2}.length` + entries | `get_basis` / `get_kagome_basis` block at level d, sector 1/2 |
| `gbasis.label{1,2}.length` + entries | `get_bulkbasis` / `get_kagome_bulkbasis` block at level d−1 (the gap block) |

Each basis entry is `(word::Vector{Int}, aux::Vector{Vector{Int}})` in the legacy
SpectralGap encoding (Pauli index `3*(site-1)+α`, α: x=1, y=2, z=3).

## Cases (copied from `example/example.jl`)

- **1D transverse-field Ising, N=9, g=0.5, d=2** — the TFIM benchmark that
  `certify_Ising_gap` already solves (Δ ≤ 0.258).
- **Kagome Heisenberg, N=5, d=2** — the smallest kagome cluster (two corner-sharing
  triangles), geometry `triples=[[1,2,3],[1,4,5]]`, `edges=[]`.

## Closed-form expectations (assert these on the first run)

These are derivable by hand and must match the dump; they gate trust in the
script before its basis-size output is used as reference:

- **Ising H:** `(N−1)` ZZ-bond terms with coefficient `−1` (`[3i; 3(i+1)]`,
  i=1..8) plus `N` transverse-field σ^x terms with coefficient `g=0.5`
  (`[3i−2]`, i=1..9). Total `H.supp_count == 17`.
- **Kagome H:** `9 * |triples|` terms, every coefficient exactly `0.25` (the
  spin-1/2 factor). For N=5: `H.supp_count == 18`. Each triangle contributes 3
  pairs × 3 components (xx, yy, zz).

The basis-block **sizes** (`basis.label1.length`, etc.) are deterministic in
`(N, d, label)` but tedious to hand-compute; the dump establishes them as the
reference. Once captured, the refactor's legacy wrappers must reproduce them
byte-for-byte (acceptance test 6).

## How it maps to the refactor gates

1. **Run on SCNet** (`julia --project=julia-env scripts/dump_legacy_inventory.jl
   > legacy_inventory.txt`). Solver-free — calls only `get_basis` /
   `get_kagome_basis` / `ncpoly`, so it does **not** hit the Mosek-11 zero-dim-PSD
   bug that blocks `certify_*_gap`.
2. Commit the captured `legacy_inventory.txt` as the frozen reference.
3. Sihan's D1 legacy wrappers and the generic adapter's `legacy_ncpoly_data`
   must both reproduce `H.supp` / `H.coe` exactly (these already match by
   construction — the adapter uses the same `3*(site-1)+α` convention) and the
   basis-block sizes once the structured basis lands.

## Status / caveats

- The script was written by reading `src/basicfunction.jl` + `example/example.jl`
  and is **not yet executed** (no local solver environment, per the laptop
- compute constraint). The first remote run must be checked against the
  closed-form expectations above before its basis-size output is trusted.
- It captures `H` + basis entries but **not** the assembled `tsupp` affine
  constraints or the `pos`/`gpos` PSD variable layout — those live inside
  `certify_*_gap` and would require either instrumenting that function or
  refactoring it to return an `AssembledGapSDP` (refactor D2). The basis+H
  inventory is the part needed for acceptance test 6 as written.
