# Legacy inventory — v1 canonical schema

> Contract for the data emitted by `scripts/dump_legacy_inventory.jl`. This is the
> frozen oracle that `GenericGapModel` assembly will be diffed against
> coefficient-by-coefficient (refactor-plan acceptance test 6). Anything not
> byte-stable across runs is a schema bug.
>
> Origin: agreed with Sihan (Feishu, 2026-07-27 19:19). Branch:
> `feature/legacy-affine-inventory`.

## 1. File layout — math inventory and solver-run metadata are separate

| file | contents | stability |
|---|---|---|
| `legacy_inventory.math.txt` | the mathematical inventory (H, basis, gbasis, tsupp affine rows, pos/gpos block metadata) | **byte-stable** — no floats, no timestamps, no machine-specific data |
| `legacy_inventory.runmeta.txt` | solver-run metadata (only present when a solver actually ran) | may vary across machines/runs |

The dump is solver-free, so on a pure inventory run only the `.math.txt` file is
produced. The `.runmeta.txt` file appears only when the dump (or a paired run)
calls a solver — then it records optimizer + version, raw termination/primal/dual
status, tolerances, residuals, runtime. **The math inventory must never depend on
a solver run.**

## 2. Math inventory format (v1)

Deterministic, line-based plain text, UTF-8, `\n` newlines. Sections appear in
fixed order. Within each section, entries are sorted by their stable ID.

### 2.1 Header (excluded from the SHA-256 in §5 by convention; hash covers §2.2–2.5)

```
format_version = 1
generator = dump_legacy_inventory.jl
spectralgap_source = <commit-sha of .external/SpectralGap, or package version, or "unknown">
model = 1D-transverse-field-Ising | kagome-Heisenberg
config = N=<int> g=<num>/<den> d=<int>
normalization = spin-1/2, S=sigma/2, Heisenberg factor 1/4
encoding = Pauli index = 3*(site-1)+alpha; alpha in {1=x,2=y,3=z}
basis_ordering = as returned by get_basis / get_kagome_basis: label=1 block then label=2 block; entries in emission order
```

### 2.2 Hamiltonian (exact-rational coefficients)

```
[H]
nterms = <int>
H[<id>] coeff=<num>/<den> support=[<int>,...]
...
```

- `<id>` is a stable 1-based index assigned after sorting terms by
  `(coeff_num, coeff_den, support_tuple)`.
- **Coefficient is always `num/den` (exact rational).** `0.5 → 1/2`, `0.25 → 1/4`,
  `-1 → -1/1`. No float repr is permitted in this file. The dump obtains these by
  `rationalize()` on the legacy `ncpoly.coe` (safe for the exact binary values
  used by these models) and asserts the result for known terms.

### 2.3 Basis blocks (positive + bulk/gap)

```
[basis.<scope>.label<L>]
id = basis.<scope>.L<L>
dimension = <int>
entry[<id>] word=[<int>,...] aux=[<int>,...]
...
```

- `<scope>` ∈ {`pos` (level d), `gpos` (level d−1)}.
- `entry.id` is stable (1-based within the block, in `get_basis` emission order).
- `word` is the canonical Pauli monomial; `aux` is the legacy mirror-equivalence
  slot (empty for most entries).

### 2.4 Affine-constraint rows (the `tsupp` inventory)

```
[tsupp]
nrows = <int>
row[<id>] = [<int>,...]            # sorted support
...
```

- `tsupp` is built by mirroring the support-collection loops of
  `certify_Ising_gap` / `certify_Heisenberg_kagome_gap` **without** constructing
  any JuMP model — only `reduce!`, `PSDstate_entry`, `reduce_mirror` /
  `reduce_perm` are called. `row.id` is 1-based after `sort!`+`unique!`, matching
  the legacy `bfind` order so `Locb` indices are reproducible.

### 2.5 PSD-block layout (metadata only at v1)

```
[pos.blocks]
block[<id>] kind=pos label=<L> dimension=<lb[L]> basis_id=basis.pos.L<L>
[gpos.blocks]
block[<id>] kind=gpos label=<L> dimension=<lgb[L]> basis_id=basis.gpos.L<L>
```

v1 records block kind/label/dimension/linked basis-id. The full per-entry
`(j,k) → tsupp_row` coefficient map is deferred to v1.1 (it is the wiring detail
inside `certify_*_gap`'s cons-assembly loop; capturing it solver-free is
mechanical but deferred until v1 is frozen and validated).

## 3. Stable IDs

Every H term, basis entry, tsupp row, and block has a stable string/integer ID
deterministic in `(model, config, section)`. IDs never depend on run order or
memory layout. This is what makes the coefficient diff machine-judgeable.

## 4. Dump-time asserts (gate the output before it can be used as oracle)

The dump asserts, and aborts on violation:
- Ising N=9: `H.nterms == 17` (8 ZZ bonds @ −1, 9 transverse-field σ^x @ g).
- Kagome N=5: `H.nterms == 18` (9 per triangle × 2 triangles, all @ 1/4).
- Every Ising ZZ coeff rationalizes to `-1/1`; every transverse-field coeff to the
  configured `g` (here `1/2`); every Kagome coeff to `1/4`.
- `tsupp` has no duplicate rows after `sort!`+`unique!`.

## 5. Canonical SHA-256

The dump computes `sha256` over the exact byte content of §2.2–2.5 (the header in
§2.1 and the `sha256 =` line itself excluded) and writes it as the final line:

```
sha256 = <64 hex chars>
```

Sihan's diff harness recomputes this and fails on mismatch. The hash is the
freeze mechanism: once v1 is validated, any change to basis selection or
generation must change the hash and be acknowledged explicitly.

## 6. Byte-stability rules

- No floats anywhere in `legacy_inventory.math.txt`.
- No absolute timestamps; no hostnames; no memory addresses.
- Sorting is total (defined tie-breaks for every field).
- The `generator` line may change across dump-script versions; everything else is
  frozen by `format_version = 1`.

## 7. Status

v1 schema — agreed 2026-07-27. The matching dump implementation
(`dump_legacy_inventory.jl` at this commit) targets §2.1–2.5 and §4–5; it is
**solver-free and not yet executed locally** (laptop-compute constraint). First
remote run must pass the §4 asserts before its output is trusted as oracle.
