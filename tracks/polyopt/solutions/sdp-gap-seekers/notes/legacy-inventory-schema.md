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
| `legacy_inventory.math.txt` | an unhashed provenance header plus the mathematical inventory (H, basis, gbasis, tsupp affine rows, pos/gpos block metadata) | canonical payload is **byte-stable**; header provenance may differ |
| `legacy_inventory.runmeta.txt` | solver-run metadata (only present when a solver actually ran) | may vary across machines/runs |

The dump is solver-free, so it produces only the `.math.txt` file and has no
`runmeta` option. A separate, explicitly requested paired solver run may produce
`.runmeta.txt`; then it records optimizer + version, raw
termination/primal/dual status, tolerances, residuals, and runtime. **The math
inventory must never depend on a solver run.**

## 2. Math inventory format (v1)

Deterministic, line-based plain text, UTF-8, `\n` newlines. Sections appear in
fixed order. Within each section, entries are sorted by their stable ID.

### 2.1 Header (excluded from the SHA-256 in §5; hash covers §2.2–2.5)

```
format_version = 1
generator = dump_legacy_inventory.jl
spectralgap_source = git=<40-hex commit|unavailable> dirty=<false|true|unknown> package_version=<version|unknown>
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
  `-1 → -1/1`. No float repr is permitted in the H section. The dump obtains these by
  `rationalize()` on the legacy `ncpoly.coe` (safe for the exact binary values
  used by these models) and asserts the result for known terms.

### 2.3 Basis blocks (positive + bulk/gap)

```
[basis.<scope>.label<L>]
id = basis.<scope>.L<L>
dimension = <int>
entry[<id>] word=[<int>, ...] aux=[[<int>, ...], ...]
...
```

- `<scope>` ∈ {`pos` (level d), `gpos` (level d−1)}.
- `entry.id` is stable (1-based within the block, in `get_basis` emission order).
- `word` is the canonical Pauli monomial; `aux` is the nested legacy
  mirror-equivalence slot (empty for most entries). Integer and nested-integer
  vectors use explicit machine-independent decimal rendering: typed empty
  vectors are always `[]`, one empty inner vector is `[[]]`, and elements are
  separated by comma-space. Julia type names such as `Int64[]` are forbidden.
- Every Pauli word uses 1-based indices, contains at most one component per
  site, and is strictly ordered by site. Ising words may use sites 1–9;
  Kagome H/basis/aux words use sites 1–5, while Kagome `tsupp` may use the
  explicit nine-site strengthening support.

### 2.4 Affine-constraint rows (the `tsupp` inventory)

```
[tsupp]
nrows = <int>
row[<id>] = [[<int>, ...], ...]    # sorted nested support
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

The independent verifier additionally requires the production dimensions and
row counts reported by the first SCNet feasibility run:

- Ising: `lb=[211,50]`, `lgb=[11,14]`, `|tsupp|=2705`.
- Kagome: `lb=[31,22]`, `lgb=[0,1]`, `|tsupp|=10982`.

It parses the complete §2.2–2.5 grammar, requires fixed section order,
consecutive IDs, basis dimension/entry agreement, block-to-basis linkage,
canonical nested-integer rendering, structurally unique and sorted `tsupp`
rows, no unknown/trailing content, and byte-identical parse→render.
All scalar integers are canonical decimal (`0` or no leading zero; never `-0`);
IDs are strictly positive and consecutive.

## 5. Canonical SHA-256

For each model record, the generator first serializes the §2.1 header and the
§2.2–2.5 mathematical payload into separate UTF-8/LF byte strings. In fixed
record order (Ising, then Kagome), the canonical hash input is exactly

```
ising_payload_bytes || kagome_payload_bytes
```

where each payload starts with `[H]\n`, ends with the final `[gpos.blocks]`
entry's `\n`, and has no additional inter-record separator. The dump computes
`sha256` over that exact concatenation. All header bytes—including
`generator`, `spectralgap_source`, and other human/provenance fields—and the
`sha256 =` line itself are excluded. The final line is:

```
sha256 = <64 hex chars>
```

The solver-free verifier reconstructs this scope from the file and fails on a
mismatch:

```
julia --startup-file=no \
  tracks/polyopt/solutions/sdp-gap-seekers/scripts/verify_legacy_inventory.jl \
  --freeze \
  legacy_inventory.math.txt
```

Without `--freeze`, this command validates the full math/schema contract,
including the prescribed `spectralgap_source` grammar, but reports that the
provenance freeze gate was not requested. Valid diagnostic provenance is either
an exact 40-hex Git commit with `dirty=true|false`, or
`git=unavailable dirty=unknown`, plus a semantic-version-shaped package version
or `unknown`. `--freeze` additionally requires both records to name the same
standalone SpectralGap Git checkout, with an exact commit, `dirty=false`
(including untracked files), and a known package version. Diagnostic
dirty/unavailable/unknown states cannot freeze an oracle.

The hash is the freeze mechanism: once v1 is independently validated, any
change to basis selection or generation must change the hash and be
acknowledged explicitly. Provenance-only header edits do not change it.

## 6. Byte-stability rules

- No floating-point numeric representation in the canonical mathematical
  payload. A provenance header may contain a package version string such as
  `0.1.0`.
- No absolute timestamps; no hostnames; no memory addresses.
- Sorting is total (defined tie-breaks for every field).
- Header provenance such as `generator` and `spectralgap_source` may change and
  is compared separately; every mathematical payload byte is frozen by
  `format_version = 1`.
- Header fields that determine mathematical meaning (`model`, `config`,
  `normalization`, `encoding`, and `basis_ordering`) are excluded from the
  byte hash but are fixed-value semantic checks in both verifier modes.

## 7. Status

v1 schema — agreed 2026-07-27. An earlier solver-free SCNet run of the legacy
generator reported the expected §4 Hamiltonian asserts and inventory sizes, but
it used the pre-fix hash scope and did not produce a committed frozen artifact.
The current dump + verifier must be run independently in two clean SCNet
checkouts; matching verified math hashes and recorded spot-check evidence are
required before any output is called the frozen oracle.
