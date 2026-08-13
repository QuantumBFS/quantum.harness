# Challenge 194 Versioned P0 Extension Design

## Decision and scope

The approved extension is a new exploratory `pilot-p0-extension-v1`
campaign. It samples only sigma `0.9` and `1.0`, at all three P0 lengths,
with 16 fresh replicas and one fixed 17-point binary64 grid per sigma. The
extension is designed only to resolve the existing mismatch between the
two frozen P1 bracket estimators. It does not alter P0, relax the selector,
run P1, add extended observables, or authorize a scientific claim.

This document is the complete design. Implementation, cluster submission,
data generation, and P1 publication are out of scope.

## Binding existing evidence

The extension is derived from, and must remain bound to, these immutable
inputs:

- verified P0 root:
  `results/challenge-194/pilot-p0-739880d`;
- P0 verifier result:
  `{"cells": 96, "status": "verified", "trajectories": 96}`;
- P0 run-spec SHA256:
  `d17d3df9528a09f0d834ebe9d5ce6f283e488d2326f6cb14873a90923c5d9840`;
- P0 merged-progress SHA256:
  `ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f`;
- immutable analysis:
  `results/challenge-194/p0_analysis.json`;
- embedded analysis-document SHA256:
  `e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8`;
- complete canonical analysis-file SHA256:
  `44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b`;
- current frozen bracket-document SHA256:
  `fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403`;
- P0 source/orchestration revision:
  `739880d9ccdcffbfc8a15310250349bd11d63bbb`.

The current selector uses lengths `16384` and `262144`. It selects sigma
`0.8` on
`[0x1.f400000000000p-2, 0x1.3880000000000p-1]` and the sigma `1.1`
crossover on
`[0x1.312d000000000p+0, 0x1.7d78400000000p+0]`, but fails closed for
sigma `0.9` and `1.0` with
`no_nonzero_interval_marked_by_both_estimators`. Consequently
`p1_protocol.json` does not exist.

The protocol builder must verify all hashes above before publishing an
extension protocol. The extension protocol also records the SHA256 of the
committed bytes of this design and the implementation source revision. A
hash, schema, source, environment, or path mismatch is fatal.

## Exact range derivation from real P0

### Original P0 coupling indices

The nonzero part of the original ordered P0 grid relevant to this design is:

| Index | Exact binary64 coupling |
|---:|---|
| 4 | `0x1.f400000000000p-2` |
| 5 | `0x1.3880000000000p-1` |
| 6 | `0x1.86a0000000000p-1` |
| 7 | `0x1.e848000000000p-1` |
| 8 | `0x1.312d000000000p+0` |
| 9 | `0x1.7d78400000000p+0` |
| 10 | `0x1.dcd6500000000p+0` |
| 12 | `0x1.74876e8000000p+1` |
| 13 | `0x1.d1a94a2000000p+1` |
| 14 | `0x1.2309ce5400000p+2` |
| 15 | `0x1.6bcc41e900000p+2` |

An interval index `i` means the closed interval from coupling `i` to
coupling `i + 1`.

### Deterministic component rule

The extension range is derived without changing the frozen selector:

1. Recompute all original-P0 interval marks using the current selector's
   exact rules and the two largest lengths.
2. Group contiguous marked intervals separately for `Q_G` and four-sector
   crossing.
3. For each blocked sigma, choose the four-sector component at the lowest
   coupling. Choose the `Q_G` component with the smallest interval-index gap
   to that four-sector component, breaking an equal gap by lower coupling.
4. Take the closed span of those two components.
5. Add exactly one original-P0 interval immediately below and one immediately
   above that span.
6. Use the resulting outer endpoints for four recursive binary64 midpoint
   levels, producing 17 ordered points.

The component rule is used only to preregister the extension range. The final
selector still examines every adjacent nonzero interval in the combined
evidence. In particular, this rule does not discard candidates from final P1
selection.

This component rule handles the exact high-coupling P0 evidence explicitly.
At sigma `0.9`, `Q_G` also marks the disconnected component `13..14`; at
sigma `1.0`, it also marks `12..14`. Their endpoint differences are at
binary64 saturation scale, neither component is marked by the four-sector
estimator, and both are farther from the lowest four-sector component than
the selected `Q_G` component. They therefore do not enlarge the extension
range, but they remain available to the frozen selector after evidence is
combined.

### Sigma 0.9

Exact sigma identity: `0x1.ccccccccccccdp-1`.

- Four-sector marked component: interval `5`, from
  `0x1.3880000000000p-1` to `0x1.86a0000000000p-1`.
- Nearest `Q_G` marked component: interval `6`, from
  `0x1.86a0000000000p-1` to `0x1.e848000000000p-1`.
- Estimator union: intervals `5..6`.
- Added left guard: interval `4`.
- Added right guard: interval `7`.
- Final extension span: intervals `4..7`, with endpoints
  `0x1.f400000000000p-2` and `0x1.312d000000000p+0`.

The exact 17-point grid is:

```text
[
  "0x1.f400000000000p-2",
  "0x1.1085a00000000p-1",
  "0x1.270b400000000p-1",
  "0x1.3d90e00000000p-1",
  "0x1.5416800000000p-1",
  "0x1.6a9c200000000p-1",
  "0x1.8121c00000000p-1",
  "0x1.97a7600000000p-1",
  "0x1.ae2d000000000p-1",
  "0x1.c4b2a00000000p-1",
  "0x1.db38400000000p-1",
  "0x1.f1bde00000000p-1",
  "0x1.0421c00000000p+0",
  "0x1.0f64900000000p+0",
  "0x1.1aa7600000000p+0",
  "0x1.25ea300000000p+0",
  "0x1.312d000000000p+0"
]
```

### Sigma 1.0

Exact sigma identity: `0x1.0000000000000p+0`.

- Four-sector marked component: intervals `6..7`, from
  `0x1.86a0000000000p-1` to `0x1.312d000000000p+0`.
- Nearest `Q_G` marked component: interval `8`, from
  `0x1.312d000000000p+0` to `0x1.7d78400000000p+0`.
- Estimator union: intervals `6..8`.
- Added left guard: interval `5`.
- Added right guard: interval `9`.
- Final extension span: intervals `5..9`, with endpoints
  `0x1.3880000000000p-1` and `0x1.dcd6500000000p+0`.

The exact 17-point grid is:

```text
[
  "0x1.3880000000000p-1",
  "0x1.6092ca0000000p-1",
  "0x1.88a5940000000p-1",
  "0x1.b0b85e0000000p-1",
  "0x1.d8cb280000000p-1",
  "0x1.006ef90000000p+0",
  "0x1.14785e0000000p+0",
  "0x1.2881c30000000p+0",
  "0x1.3c8b280000000p+0",
  "0x1.50948d0000000p+0",
  "0x1.649df20000000p+0",
  "0x1.78a7570000000p+0",
  "0x1.8cb0bc0000000p+0",
  "0x1.a0ba210000000p+0",
  "0x1.b4c3860000000p+0",
  "0x1.c8cceb0000000p+0",
  "0x1.dcd6500000000p+0"
]
```

For each span, generation starts with the two endpoints and repeats four
levels of `left + (right - left) / 2.0` over the current sorted adjacent
pairs. Values are deduplicated by exact `float.hex()` identity, sorted by
numeric value, and required to yield exactly 17 points with unchanged
endpoints. The protocol stores only the canonical hex strings and hashes each
ordered grid. The grid hash is SHA256 of canonical
`{"kappas":[<ordered hex strings>]}` plus one trailing newline. The exact
hashes are:

- sigma `0.9`:
  `76dc7e07639ed085873a8f291cc2aaee0e8942ddac8efce3982743dd67491071`;
- sigma `1.0`:
  `d40b4a2afac533d74965513513fff1870918831000b2e040063ca2a0e29ad091`.

## Alternatives considered

### Selected: one targeted 17-point grid per blocked sigma

This design fixes both grids before any new data exist, covers the complete
gap between the nearest estimator-marked components, and includes one
original-P0 guard interval on each side. It costs 96 trajectories and 1,632
trajectory checkpoints. It is broad enough to detect modest finite-size
drift without spending samples on sigma values that already passed the
selector.

### Full four-sigma P0 replacement

A replacement using four sigmas, three lengths, and 16 fresh replicas would
cost 192 trajectories and 3,264 checkpoints at the same 17-point density.
It would duplicate adequate evidence for sigma `0.8` and `1.1`, create an
unnecessary choice between old and replacement evidence, and increase
cluster and review cost without addressing a broader failure. It is rejected.

### Adaptive or disjoint estimator-centered refinements

Two small grids, or a first refinement followed by a data-dependent second
grid, could reduce work when the estimators rapidly align. They would leave
an unsampled gap or let extension data choose later sampling locations,
creating another exploratory decision and publication round. A single
precommitted 17-point span is easier to authenticate, restart, combine, and
audit. The adaptive/disjoint approach is rejected.

## Frozen protocol identities and cardinality

The extension protocol schema is
`challenge-194-p0-extension-protocol-v1`.
The corresponding run-spec, merged-progress, extension-analysis, combined-
analysis, and combined-bracket schemas are respectively:

- `challenge-194-p0-extension-run-spec-v1`;
- `challenge-194-p0-extension-progress-v1`;
- `challenge-194-p0-extension-analysis-v1`;
- `challenge-194-p0-combined-analysis-v2`;
- `challenge-194-p1-brackets-v2`.

- Sigmas, in order:
  `0x1.ccccccccccccdp-1`,
  `0x1.0000000000000p+0`.
- Lengths, in order: `1024`, `16384`, `262144`.
- Replicas, in order: integers `24..39`.
- Loop order: sigma, length, replica.
- Cells: `2 * 3 * 16 = 96`.
- Trajectories: exactly 96, one per cell.
- Couplings per trajectory: exactly 17, selected by sigma.
- Trajectory checkpoints: `96 * 17 = 1,632`.
- Aggregate extension estimate rows: `2 * 3 * 17 = 102`.
- Phase: existing exploratory phase string `"pilot"`.
- Master seed: `19_420_262_729`.
- Grid namespace: `"pilot-p0-extension-v1"`.

Replica labels do not overlap P0 `0..7` or the reserved P1 labels `8..23`.
The new master seed and sigma grid IDs provide an additional disjoint RNG
identity boundary. The exact per-sigma grid IDs are:

```text
pilot-p0-extension-v1|sigma-f64=0x1.ccccccccccccdp-1|source-analysis=e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8|range=0x1.f400000000000p-2:0x1.312d000000000p+0
pilot-p0-extension-v1|sigma-f64=0x1.0000000000000p+0|source-analysis=e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8|range=0x1.3880000000000p-1:0x1.dcd6500000000p+0
```

Every request digest and every counter-RNG stream material digest must be
unique within the extension and disjoint from the verified P0 assignments
and the deterministically reserved P1 assignments. Any collision blocks
protocol publication.

The extension uses the existing ten-column basic observable schema and the
same trajectory realization/stopping policy as P0. It aggregates `Q_G`,
four-sector crossing, `S1/L`, and `S2/L`. Adding the future extended
observable schema is a separate P1 task and is not part of this extension.

## Interfaces and compatibility boundaries

Implementation will add versioned entry points while preserving every
existing P0 and P1 behavior:

- `build_p0_extension_protocol(p0_analysis: Mapping[str, object]) -> dict[str, object]`
  validates the exact P0 analysis, recomputes the ranges and grids, assigns
  RNG identities, and produces the canonical extension protocol.
- `build_p0_extension_run_spec(output_root: Path, validation_report: Path,
  protocol: Mapping[str, object]) -> dict[str, object]` produces the 96-cell
  immutable run spec using the existing approved scientific engine and
  correctness registry.
- Existing cell execution, pending, merge, and download-verification machinery
  is generalized by schema dispatch. The current production P0 loader remains
  strict and must not accept an extension as P0.
- `aggregate_p0_extension(run_spec: Path,
  protocol: Mapping[str, object]) -> dict[str, object]` uses the same retained,
  bounded verified-snapshot mechanism as `aggregate_p0` and emits the 102
  extension estimates.
- `combine_p0_evidence(p0_analysis: Mapping[str, object],
  extension_analysis: Mapping[str, object]) -> dict[str, object]` produces a
  versioned per-sigma combined document.
- `select_p1_brackets(analysis: Mapping[str, object]) -> dict[str, object]`
  gains schema dispatch for the combined document, but calls the same interval
  marking, candidate selection, and tie-break logic. The original P0-analysis
  path and its exact output remain regression locked.
- `build_p1_protocol(analysis: Mapping[str, object],
  brackets: Mapping[str, object] | None = None) -> dict[str, object]` accepts
  the verified combined document only after the acceptance gate below. Its
  existing four-sigma, three-length, 16-replica P1 cardinality, master seed,
  grid namespace, and fail-closed behavior do not change.

The CLI grammar is below. Uppercase names are argparse metavariables for the
absolute paths whose concrete artifact names are fixed in the publication
section; they are not undecided protocol values.

```text
analyze_pilot.py build-p0-extension --analysis P0_ANALYSIS_PATH --output EXTENSION_PROTOCOL_PATH
run_pilot.py build-extension-spec --protocol EXTENSION_PROTOCOL_PATH --validation-report APPROVED_VALIDATION_REPORT_PATH --output-root EXTENSION_ROOT --run-spec EXTENSION_RUN_SPEC_PATH
run_pilot.py run-cell --run-spec EXTENSION_RUN_SPEC_PATH --cell-index CELL_INDEX
run_pilot.py pending --run-spec EXTENSION_RUN_SPEC_PATH
run_pilot.py merge --run-spec EXTENSION_RUN_SPEC_PATH
run_pilot.py verify --run-spec EXTENSION_RUN_SPEC_PATH
analyze_pilot.py analyze-extension --run-spec EXTENSION_RUN_SPEC_PATH --protocol EXTENSION_PROTOCOL_PATH --output EXTENSION_ANALYSIS_PATH
analyze_pilot.py combine --p0-analysis P0_ANALYSIS_PATH --extension-analysis EXTENSION_ANALYSIS_PATH --output COMBINED_ANALYSIS_PATH
analyze_pilot.py select --analysis COMBINED_ANALYSIS_PATH --output COMBINED_BRACKETS_PATH
analyze_pilot.py build-p1 --analysis COMBINED_ANALYSIS_PATH --output P1_PROTOCOL_PATH
```

Every command requires canonical absolute paths. Schema dispatch is based on
authenticated document content, never a filename or user-selected permissive
flag. Test-only flexible schemas remain inaccessible from production CLIs.

## Evidence combination

The combined schema is `challenge-194-p0-combined-analysis-v2`. It has a
separate ordered coupling axis for each sigma, allowing the two extension
grids to coexist with the common original P0 grid without fabricating a
rectangular grid.

For sigma `0.8` and `1.1`, the combined document retains the original 16
couplings and eight-replica estimates unchanged. For sigma `0.9` and `1.0`,
it takes the exact sorted binary64 union of the 16 original points and the 17
extension points. Each extension shares exactly its two endpoints with P0 and
has 15 new interior points, so each blocked sigma has 31 distinct couplings.
Across all three lengths, the combined document therefore contains exactly
`3 * (16 + 31 + 31 + 16) = 282` estimate rows.

At an extension-only coupling, the estimate has 16 replicas. At an
original-only coupling, it has eight. At either shared endpoint, P0's eight
and the extension's 16 independent whole trajectories are pooled in fixed
source order, P0 then extension, for 24 replicas. Means and `ddof=1` sample
standard errors are recomputed from the verified whole-trajectory values;
checkpoint rows are never treated as independent replicas. Request hashes are
stored in the same fixed order and must be unique.

Combination revalidates both source analysis digests and both verified run
roots. It records both run-spec hashes, both progress hashes, both analysis
document hashes, ordered request identities, observable columns, source
revisions, and its own unsigned canonical-document SHA256. It never modifies
or replaces either source analysis.

The selector normalizes each sigma entry to its own strictly increasing
coupling sequence, excludes the zero-coupling interval exactly as before,
uses only lengths `16384` and `262144`, and applies the unchanged rules:

1. mark `Q_G` sign-change intervals;
2. mark intervals where either length's four-sector endpoints span the
   closed range `[0.25, 0.75]`;
3. for sigma at most one, select the narrowest interval marked by both,
   then the lower coupling;
4. for sigma `1.1`, select maximum absolute largest-size four-sector slope,
   then the lower coupling.

No interpolation, uncertainty-based rescue, nearest-interval fallback,
threshold adjustment, or manual candidate choice is permitted.

## Artifact and publication boundaries

The planned immutable artifacts are:

1. `results/challenge-194/p0_extension_v1_protocol.json`
   — range derivation, exact grids, identities, source hashes, and complete
   ordered 96-cell assignment.
2. Remote and downloaded root
   `results/challenge-194/pilot-p0-extension-v1/`
   — `run_spec.json`, 96 cell trees, and merged `progress.json`.
3. `results/challenge-194/p0_extension_v1_analysis.json`
   — 102 authenticated aggregate estimates.
4. `results/challenge-194/p0_combined_analysis_v2.json`
   — 282 source-bound combined estimates.
5. `results/challenge-194/p0_combined_brackets_v2.json`
   — the rerun frozen-selector result and its canonical hash.
6. `results/challenge-194/p1_protocol.json`
   — still absent unless all acceptance checks pass.

JSON uses sorted keys, compact separators, finite values only, UTF-8, and one
trailing newline. Each artifact contains a schema version and an internal
SHA256 over the unsigned canonical document. Publication uses the existing
atomic no-clobber boundary: an absent target may be installed once; an
existing byte-identical target returns `verified-existing`; different
existing bytes fail and are never replaced.

Transfer state, claims, and transfer logs are sibling paths outside the
immutable downloaded run root, following the current hardened P0 download
contract. Source trees and published analysis artifacts are never edited in
place.

## Cluster resources and restart behavior

Heavy execution remains Wuzh02-only. The extension uses one single-core Slurm
array with tasks `1..96`, task `n` mapping to cell index `n - 1`, and
scheduler-managed concurrency.

Each task requests exactly:

- one CPU;
- 1800 MiB memory;
- 40 minutes wall time;
- one private node-local Numba cache;
- no GPU.

The 40-minute request allows for the increase from 16 to 17 checkpoints per
trajectory. It is a scheduling choice, not a claim that the waived
120-second/4-GiB capability gate passed. The implementation must retain the
current environment sanitization, one-thread pins, approved offline Python,
scientific-source checks, and uniquely created mode-restricted Numba cache.

Cell layout remains:

```text
cells/<cell-id>/run/{request.json,environment.json,kernel/,
  seed-manifest.json,capability.json,trajectories/,batches/,
  progress.json,manifest.json}
cells/<cell-id>/manifest.json
```

Restart is allowed only against the identical extension protocol, run spec,
source revision, runtime contract, request, and RNG assignment. An existing
completed cell is deeply verified and skipped. A completely published
trajectory may resume missing batch, progress, or outer-manifest boundaries.
Duplicate workers serialize at the cell directory; the loser succeeds only
after verifying the winner's exact output.

Any surviving `.partial` or `.intent`, malformed marker, hash mismatch,
unexpected path, cell swap, shared-directory substitution, or source/runtime
drift fails closed and remains for diagnosis. It is never automatically
deleted. A timeout or infrastructure failure is retried only as the same cell
under the same immutable run spec; changing grid, seed, replica, source, or
scientific settings requires a new versioned protocol and root.

Merge requires exactly 96 successful cells and 96 trajectories, no extras,
and complete canonical ordering. Download uses the existing checksummed,
partial-safe, no-delete transfer and local semantic verifier. Analysis begins
only after local verification succeeds.

## Verification and acceptance gate

Implementation tests must establish:

- exact range derivation from the immutable real-P0 fixture, including the
  distant high-coupling `Q_G` components;
- the two exact 17-point grids above, generated rather than copied;
- exact protocol axes, 96-cell order, 1,632 checkpoints, 102 extension rows,
  fresh identities, and collision rejection;
- production-schema separation between P0, extension, combined analysis, and
  P1;
- bounded one-trajectory-at-a-time extension aggregation and retained
  snapshot authentication;
- exact 24-replica pooling at shared endpoints and exact 282-row combined
  cardinality;
- immutable publication, byte-identical rerun verification, and no-clobber
  rejection;
- all existing P0 aggregation, original selector, P1 builder refusal,
  restart, transfer, and artifact tests remain unchanged and passing;
- adversarial rejection of reordered grids, noncanonical floats, missing or
  duplicate replicas, forged source hashes, RNG collisions, nonfinite means,
  stale manifests, swapped roots, and partial markers.

The operational gate passes only when all of the following are true:

1. The extension protocol verifies against the exact existing P0 evidence and
   committed design.
2. The downloaded extension root verifies exactly 96 cells and 96
   trajectories under the immutable protocol.
3. The extension analysis and combined analysis verify by schema, canonical
   bytes, internal hashes, source hashes, request identities, and semantic
   recomputation.
4. Rerunning the frozen selector on the combined evidence returns `selected`
   for both sigma `0.9` and `1.0`, with a nonzero adjacent interval marked by
   both estimators.
5. The rerun reproduces the exact existing sigma `0.8` transition bracket
   `[0x1.f400000000000p-2, 0x1.3880000000000p-1]` and sigma `1.1` crossover
   bracket
   `[0x1.312d000000000p+0, 0x1.7d78400000000p+0]`.
6. The bracket document says `requires_p0_extension=false`, and a fresh
   independent recomputation is byte-identical.

Only after all six checks pass may the existing P1 builder publish
`p1_protocol.json`. If either blocked sigma still lacks a common marked
interval, or if any other check fails, P1 remains absent and blocked. The
result is reported as unresolved; no extra points, threshold changes,
interpolation, or manual bracket may be added under version 1.

## Explicit non-goals

- No P0 or P0-analysis mutation.
- No sigma `0.8` or `1.1` extension trajectories.
- No adaptive second extension.
- No selector, threshold, tie-break, or zero-coupling relaxation.
- No P1 execution or confirmatory sampling.
- No extended-observable implementation.
- No transition, critical-point, exponent, scaling, or universality claim.
