# Challenge 194 Standalone Coarse-Grid P0 Extension v2 Design

## Decision, scope, and claim boundary

The approved next campaign is the versioned exploratory
`pilot-p0-extension-v2`. It samples only sigma `0.9` and `1.0`, uses the
original P0 lengths, and applies the existing frozen P1 selector physics
byte-for-byte to a new standalone five-point coarse grid for each blocked
sigma.

The purpose is narrowly preregistered as:

1. test the observed sensitivity of the mean-based four-sector mark to
   coupling-grid topology; and
2. authorize exploratory P1 only if the unchanged selector passes its existing
   fail-closed rule.

**P0 extension v2, the authorization decision, and any resulting P1 are
exploratory. They cannot support a transition, critical-point, exponent,
scaling, density-jump, universality, or other physical claim. Later
confirmatory sampling with a disjoint RNG phase, frozen production protocol,
and preregistered analysis remains mandatory.**

This document freezes design only. Implementation, deployment, sampling,
artifact publication, P1 execution, and scientific claims are out of scope.

## Authenticated immutable inputs

Construction and every later authorization operation must require explicit
absolute canonical non-symlink paths to the relevant artifacts. Filenames,
checkout-local discovery, and self-declared hashes are not trust anchors.

### Original P0

- evidence root: `results/challenge-194/pilot-p0-739880d`;
- verified cardinality: 96 cells and 96 trajectories;
- source revision:
  `739880d9ccdcffbfc8a15310250349bd11d63bbb`;
- `run_spec.json` file SHA256:
  `d17d3df9528a09f0d834ebe9d5ce6f283e488d2326f6cb14873a90923c5d9840`;
- `progress.json` file SHA256:
  `ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f`;
- `p0_analysis.json` document SHA256:
  `e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8`;
- `p0_analysis.json` file SHA256:
  `44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b`;
- original bracket document SHA256:
  `fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403`.

The historical P0 analysis remains immutable. It is authenticated by its exact
bytes and exact evidence root, not recomputed under a plan revision whose
committed bytes differ from the plan bound by the historical run spec.

### P0 extension v1 and combined-v2 evidence

- v1 design SHA256:
  `5426e3007e9d83039f371ca6a9372f1868ef9d5447b66a12b1643ecf72907aba`;
- protocol document SHA256:
  `a37ab41f3224594e61f4eebbe292975aeec449b9ecb7893e3e54f18d82d53321`;
- protocol file SHA256:
  `e363a60f842b11b32972c7a68ec1c5f237741bc45bc79ab8bf93f51f6760d84d`;
- source revision:
  `9308087c5c609519234da48136b88cdd60f79667`;
- v1 run-spec file SHA256:
  `c1ca9b6c8ba751919c6d9337fe1cd4c09a57ed9b99abbb9d3ebfed7f89c3d32e`;
- v1 progress file SHA256:
  `c78d1fb03daf19297ef9e0617410c68a6a364bffc2f2888dfa9067e7e8d6b65f`;
- v1 analysis document SHA256:
  `79232574d314348c29a40cd2fbb7690e96f3cae5f26843bd4f1cf07cb6a1f45b`;
- v1 analysis file SHA256:
  `d8fdd60a6de83cf3818349d4440f49f4a38bb5acd7fff1dab9b56ded4da913e5`;
- combined-v2 analysis document SHA256:
  `36f85c40e9159ef2e69742672c261769fb28d2f3c947780ba63e4ef5fe5975c3`;
- combined-v2 analysis file SHA256:
  `6c38e3e18a4577da41bc70c5610b5449e0316b1588291cb178e437099fb78929`;
- combined-v2 bracket document SHA256:
  `098f19d8883097d5f1f274ce759416328c086958fa5301c034a0b46dcbd562df`;
- combined-v2 bracket file SHA256:
  `7a84d545b4526d94aa6f93ca4f0d264dcf01e518f2f9b04383921634786c9962`.

The v1 root must again verify as exactly 96 cells and 96 trajectories.
Extension-v2 construction must deeply authenticate original P0, v1, and
combined-v2 evidence and require semantic recomputation of combined-v2 from
its two source analyses. A copied combined JSON file alone is insufficient.

### Correctness package and design binding

The implementation must retain the checked-in
`pilot_correctness_approval.json` trust boundary:

- approval/source revision:
  `877ab9393f320bfe31ff74a26c3db1fb205d7ef3`;
- report SHA256:
  `036b4b8a06164716aff5f40cc38ac4855a212026a556e1c5fe33ce32ce0babb8`;
- validation run-spec SHA256:
  `5b3eea4c460e14a57aec9df606447137d787a5c66dd7e98e1dffdcf566f430e2`;
- protocol SHA256:
  `c7e980eeadaf8ed75e4d20cebb1e2c5d5f57a1cfc329afa7678ae586f5b7f488`;
- check-registry SHA256:
  `6e25ea41899544f2a9de3589beb1ee94b1f3dc505638b8f8e5164a4322b56a1d`;
- scientific-engine aggregate SHA256:
  `457fa669da897e59b03681039db6121fde4d7be9295bb46a743c8448875b3ee9`.

The v2 protocol must bind the SHA256 of the committed bytes of this design and
the exact clean implementation revision. That design hash is computed and
frozen by implementation after this spec commit; it is not self-declared in
this document.

## Quantitative rationale

The immutable combined-v2 selector remains unresolved for sigma `0.9` and
`1.0`, while sigma `0.8` and `1.1` retain their exact frozen windows.

For sigma `0.9`, combined-v2 has a primary `Q_G` marked component from
`0x1.6a9c200000000p-1` through `0x1.97a7600000000p-1`, but no four-sector
marked interval. On the adjacent interval
`[0x1.6a9c200000000p-1, 0x1.8121c00000000p-1]`, the four-sector means are:

- length `16384`: `0.7500 ± 0.1118` to `0.9375 ± 0.0625`;
- length `262144`: `0.4375 ± 0.1281` to `0.8125 ± 0.1008`.

The rise is present, but no single fine-grid interval starts at or below
`0.25` and ends at or above `0.75`. The proposed coarse interval
`[0x1.5416800000000p-1, 0x1.97a7600000000p-1]` has, in the authenticated
combined-v2 means, a positive-to-negative `Q_G(16384)-Q_G(262144)` sign change
and a four-sector rise spanning the selector's closed target range.

For sigma `1.0`, the four-sector component is
`[0x1.e848000000000p-1, 0x1.006ef90000000p+0]`, while the primary `Q_G`
component begins at its upper endpoint and continues through
`0x1.2881c30000000p+0`. The components are adjacent but share no interval.
At `0x1.006ef90000000p+0`, the `Q_G` size difference is
`+0.1391 ± 0.0740`; at `0x1.14785e0000000p+0` it is
`-0.00294 ± 0.0230`. The proposed coarse interval
`[0x1.d8cb280000000p-1, 0x1.14785e0000000p+0]` spans both the observed
four-sector rise and the observed `Q_G` sign change.

These observations motivate a grid-topology sensitivity experiment. They do
not establish that v2 will pass, do not authorize interpolation, and do not
turn the exploratory data into physical evidence.

## Frozen v2 scientific protocol

### Axes and exact grids

Sigma order is:

```text
[
  "0x1.ccccccccccccdp-1",
  "0x1.0000000000000p+0"
]
```

Length order is `[1024, 16384, 262144]`, exactly the original P0 lengths.

The sigma `0.9` grid is exactly:

```text
[
  "0x0.0p+0",
  "0x1.270b400000000p-1",
  "0x1.5416800000000p-1",
  "0x1.97a7600000000p-1",
  "0x1.e848000000000p-1"
]
```

Its canonical grid SHA256, over canonical
`{"kappas":[<the strings above>]}` plus one trailing newline, is
`28155d7f982584787089f4a80d617783bd82b84e2ed833df3dcaa98955254d24`.

The sigma `1.0` grid is exactly:

```text
[
  "0x0.0p+0",
  "0x1.b0b85e0000000p-1",
  "0x1.d8cb280000000p-1",
  "0x1.14785e0000000p+0",
  "0x1.3c8b280000000p+0"
]
```

Its canonical grid SHA256 is
`b9abfff153302b8556312fbc5a59e6a8e7c98d8bd3c301cb90252c85a5c473f4`.

Every value above is an exact canonical `float.hex()` value already present
on the deeply authenticated combined-v2 axis; zero also occurs on the
authenticated original P0 axis. No rounded decimal value, arithmetic
regeneration, midpoint rule, or later substitution is permitted. Protocol
construction must load the authenticated source axes, copy these exact
strings, prove membership, prove strict numeric order, and prove the two grid
hashes.

Zero coupling remains an invariant checkpoint and the interval beginning at
zero remains ineligible for selection under the unchanged selector.

### Replica and RNG identity

- replica labels, in order: integers `40..71`, exactly 32 labels;
- master seed: `19_420_263_729`;
- phase: `"pilot"`;
- grid namespace: `"pilot-p0-extension-v2"`;
- loop order: sigma, length, replica;
- one trajectory per cell.

Replica labels are disjoint from original P0 `0..7`, reserved P1 `8..23`, and
v1 `24..39`. The master seed is distinct from original P0
`19_420_260_729`, P1 `19_420_261_729`, and v1 `19_420_262_729`.

The per-sigma grid identities are exactly:

```text
pilot-p0-extension-v2|sigma-f64=0x1.ccccccccccccdp-1|source-combined-analysis=36f85c40e9159ef2e69742672c261769fb28d2f3c947780ba63e4ef5fe5975c3|grid-sha256=28155d7f982584787089f4a80d617783bd82b84e2ed833df3dcaa98955254d24
pilot-p0-extension-v2|sigma-f64=0x1.0000000000000p+0|source-combined-analysis=36f85c40e9159ef2e69742672c261769fb28d2f3c947780ba63e4ef5fe5975c3|grid-sha256=b9abfff153302b8556312fbc5a59e6a8e7c98d8bd3c301cb90252c85a5c473f4
```

Every request digest and counter-RNG stream-material digest must be unique
within v2 and disjoint from the deeply verified original P0 and v1
assignments and deterministically reconstructed reserved P1 assignments. Any
collision blocks protocol publication.

### Cardinality and observables

- cells and trajectories: `2 * 3 * 32 = 192`;
- checkpoints per trajectory: exactly 5;
- total trajectory checkpoints: `192 * 5 = 960`;
- standalone v2 estimate rows: `2 * 3 * 5 = 30`;
- authorization-evidence rows: `30 + 2 * 3 * 16 = 126`.

The scientific engine, ten-column trajectory schema, realization policy,
stopping policy, and basic observables are unchanged. V2 aggregates `Q_G`,
four-sector crossing, `S1/L`, and `S2/L`. Checkpoints from one monotone
trajectory remain correlated and are never counted as replicas.

## Standalone evidence and selector boundary

### No union of blocked-sigma points

For sigma `0.9` and `1.0`, authorization uses only the 32-replica standalone
v2 estimates on the five-point v2 grid. It must not union, pool, interpolate,
or otherwise combine those blocked-sigma estimates with original P0 or v1
points.

The original P0, v1, and combined-v2 artifacts remain immutable, preserved,
authenticated inputs. Their omission from the blocked-sigma selector axis is
an explicit preregistered grid-topology sensitivity boundary, not deletion or
replacement of evidence. V1 remains reportable as an unresolved exploratory
result.

### Untouched controls

The new authorization-evidence document contains four ordered sigma entries:

1. sigma `0.8`: byte-for-byte copied estimates, lengths, and 16-point axis
   from authenticated original P0;
2. sigma `0.9`: standalone v2 estimates only;
3. sigma `1.0`: standalone v2 estimates only;
4. sigma `1.1`: byte-for-byte copied estimates, lengths, and 16-point axis
   from authenticated original P0.

Control estimates are not recomputed, pooled, rounded, or rewritten. The
authorization builder deeply authenticates their P0 root and analysis bytes
and requires the exact existing sigma `0.8` transition window
`[0x1.f400000000000p-2, 0x1.3880000000000p-1]` and sigma `1.1` crossover
window
`[0x1.312d000000000p+0, 0x1.7d78400000000p+0]`.

### Byte-identical frozen selector physics

Schema normalization may be added outside the selector, but the existing
selector physics remains byte-identical:

1. use the two largest lengths, `16384` and `262144`;
2. mark each adjacent interval containing a sign change in
   `mean Q_G(16384) - mean Q_G(262144)`;
3. independently mark an interval if either length's four-sector endpoint
   means span the closed range `[0.25, 0.75]`;
4. for sigma at most one, retain intervals marked by both estimators, select
   the narrowest, and break equal-width ties by lower coupling;
5. for sigma `1.1`, select the maximum absolute largest-size four-sector
   slope, breaking ties by lower coupling;
6. exclude the zero-coupling interval exactly as before.

The implementation must leave the current transition-evidence, transition
selection, crossover selection, candidate ordering, thresholds, tie-breaks,
and zero rule function bodies byte-for-byte unchanged. Regression tests must
prove exact original P0 and combined-v2 bracket reproduction before testing
the new authorization schema.

There is no uncertainty rescue, endpoint confidence interval, interpolation,
nearest-component fallback, manual candidate choice, threshold change, or
post-hoc grid change.

## Versioned schemas and immutable artifacts

The exact new schema names are:

- `challenge-194-p0-extension-protocol-v2`;
- `challenge-194-p0-extension-run-spec-v2`;
- `challenge-194-p0-extension-progress-v2`;
- `challenge-194-p0-extension-analysis-v2`;
- `challenge-194-p0-authorization-analysis-v3`;
- `challenge-194-p1-brackets-v3`;
- conditional `challenge-194-p1-protocol-v2`.

The exact artifact names are:

1. `results/challenge-194/p0_extension_v2_protocol.json`;
2. `results/challenge-194/pilot-p0-extension-v2/run_spec.json`;
3. `results/challenge-194/pilot-p0-extension-v2/progress.json`;
4. the immutable 192-cell tree below that run root;
5. `results/challenge-194/p0_extension_v2_analysis.json`;
6. `results/challenge-194/p0_authorization_analysis_v3.json`;
7. `results/challenge-194/p0_authorization_brackets_v3.json`;
8. conditionally, and only after every acceptance check passes,
   `results/challenge-194/p1_protocol_v2.json`.

The v2 protocol records all authenticated input file and document hashes,
design hash, implementation revision, axes, grids and grid hashes, complete
ordered cell assignment, request identities, RNG identities, correctness
package, runtime contract, purpose, and its own document hash.

The v2 analysis binds the protocol, run spec, merged progress, source
revision, design, observable columns, ordered request identities, replica
count 32, 30 estimates, and its own document hash.

Authorization analysis v3 binds the exact P0 and v2 analyses and evidence
roots plus the authenticated v1 and combined-v2 inputs that justified this
preregistration. It records the per-sigma source role (`p0-control` or
`v2-standalone`), separate ordered axes, 126 estimates, request identities,
all source hashes, and its own document hash. It is reconstructed
semantically from trusted sources; supplied authorization JSON is never
trusted alone.

Canonical JSON uses finite values only, sorted keys, compact separators,
UTF-8, and exactly one trailing newline. Every publication is atomic and
no-clobber: an absent target may be created once; a byte-identical existing
target returns `verified-existing`; different existing bytes fail without
replacement.

## Construction, execution, restart, and transfer

Protocol construction, run-spec construction, analysis, authorization,
selection, and conditional P1 construction must use explicit trusted inputs.
Production CLIs must not accept test schemas or infer evidence from the
checkout. Mixed v1/v2 flags, omitted trust roots, extraneous source arguments,
or a schema/path mismatch fail closed.

Each cell retains the existing layout:

```text
cells/<cell-id>/run/{request.json,environment.json,kernel/,
  seed-manifest.json,capability.json,trajectories/,batches/,
  progress.json,manifest.json}
cells/<cell-id>/manifest.json
```

Restart is permitted only for the identical protocol, run spec, source,
runtime, request, kernel, grid, seed, replica, and RNG assignment. Completed
cells are deeply verified and skipped. A complete trajectory may resume only
missing batch, inner-progress, run-manifest, or outer-manifest publication.
Duplicate workers serialize at the cell directory and a loser succeeds only
after verifying the winner's exact artifact.

Surviving `.partial` or `.intent` files, malformed markers, unexpected paths,
source drift, runtime drift, swapped cells, ancestor substitution, hash
mismatch, or stale manifests remain preserved for diagnosis and fail closed.
They are never deleted or repaired automatically. Merge requires exactly 192
successful cells and 192 trajectories, no extras, in canonical order.

Transfer uses the existing checksummed, partial-safe, no-delete download
contract. Claims, source markers, completion state, diagnostics, and logs are
sibling paths outside the immutable run root. A completed download is deeply
reverified without invoking transfer again. Local analysis starts only after
the downloaded root passes semantic verification.

## Wuzh02 deployment and resource contract

Heavy execution is Wuzh02-only. Deployment must use one exact clean committed
repository revision containing the implementation and this design. The
repository-root offline interpreter is:

```text
/work/share/giggleliu/jiangweiqi/quantum.harness-challenge-194/.venv/bin/python
```

Build and worker processes retain the existing influential-environment
sanitization, one-thread pins, approved scientific-source checks, exact lock
and runtime hashes, and a newly created private node-local Numba cache. No
login-node capability is presumed portable.

Each cell requests exactly:

- one CPU;
- 1800 MiB memory;
- 40 minutes wall time;
- no GPU;
- one private node-local Numba cache.

The 40-minute allocation is a scheduling ceiling, not a passed performance
gate. At most 40 cells may run concurrently, and only when account, partition,
and scheduler limits permit; otherwise scheduler-managed concurrency is
lowered without changing any scientific identity.

Slurm array IDs are canonical decimal integers `1..192` and map to cell index
`ID - 1`. Signs, whitespace, leading-zero aliases, non-digits, overflow-sized
values, and out-of-range values fail before arithmetic.

### Smoke gate

Before releasing the remaining array, execute exactly cell indices
`0`, `64`, `96`, and `160`: the first replica at length `1024` and length
`262144` for each sigma. Concurrency is at most four.

The smoke gate passes only if all four jobs:

1. exit successfully under the exact clean deployment;
2. publish one complete immutable trajectory and both manifests;
3. pass immediate deep semantic verification, including request, grid,
   kernel, environment, RNG, and artifact hashes;
4. show no `.partial`, `.intent`, unexpected path, memory failure, timeout,
   oversubscription, or runtime/source drift.

Failure stops release of all remaining cells. Infrastructure retries reuse
the exact same cell identities and artifacts. A scientific, schema, identity,
or provenance failure requires a new reviewed design version; it is not
retried with altered settings.

After smoke approval, remaining cells may be submitted with an array
concurrency cap of 40. Smoke cells are verified and skipped rather than
resampled if included in a complete immutable array specification.

## Verification and acceptance

Implementation tests must prove:

- exact authentication and semantic recomputation of every input listed here;
- exact five-point source-axis membership, ordering, strings, and grid hashes;
- exact sigma, length, replica, seed, phase, namespace, and loop order;
- 192 unique cells, 192 trajectories, 960 checkpoints, 30 v2 estimates, and
  126 authorization estimates;
- disjoint request and RNG identities across P0, P1, v1, and v2;
- standalone blocked-sigma evidence with no union or pooling;
- byte-identical P0 controls and exact preserved control brackets;
- byte-identical selector physics and exact P0/combined-v2 regression output;
- one-trajectory-at-a-time bounded aggregation and authenticated snapshots;
- immutable publication, byte-identical retry, restart, transfer, and
  no-clobber behavior;
- fail-closed rejection of forged hashes, self-signed sources, reordered or
  rounded grids, duplicate/missing replicas, nonfinite moments, source swaps,
  partial markers, stale manifests, ABA replacement, and unexpected paths.

The operational acceptance rule is conjunctive:

1. the v2 protocol validates against this exact committed design, exact clean
   implementation, correctness package, and all authenticated P0/v1/combined
   inputs;
2. the downloaded v2 root verifies exactly 192 cells and 192 trajectories;
3. standalone v2 analysis recomputes byte-identically with exactly 30
   estimates and replica count 32;
4. authorization analysis v3 recomputes byte-identically with exact untouched
   P0 controls, standalone v2 blocked sigmas, exactly 126 estimates, and no
   blocked-sigma P0/v1 union;
5. the byte-identical frozen selector returns `selected` for both sigma `0.9`
   and `1.0`, each on a nonzero adjacent interval marked by both estimators;
6. sigma `0.8` and `1.1` reproduce their exact existing transition and
   crossover windows;
7. authorization brackets v3 say `requires_p0_extension=false`, and a fresh
   independent authenticated recomputation is byte-identical.

Only if all seven checks pass may `p1_protocol_v2.json` be published. Its
scientific P1 axes, reserved replicas `8..23`, master seed
`19_420_261_729`, `"pilot"` phase, selector-derived nine-point windows, and
exploratory-only purpose remain unchanged from the existing P1 design; the
new schema records authorization-analysis-v3 and brackets-v3 source hashes.
Publishing the protocol does not authorize local or cluster P1 execution
without a separate reviewed execution step.

If any check fails, P1 remains absent and unresolved. No extra replica,
coupling, size, sigma, interpolation, threshold, selector change, manual
window, or adaptive follow-up is permitted under v2. The failed immutable
result is reported as such.

## Rejected alternatives

### More replicas on the v1 17-point grids

Adding replicas at the same fine points could reduce standard errors but
cannot change the adjacency topology. Sigma `0.9` currently has no
four-sector marked interval because the rise is split across fine intervals;
sigma `1.0` has adjacent, non-overlapping estimator components. Joint rescue
by mean movement alone is not supported strongly enough to justify a larger
repeat campaign. This alternative is rejected.

### Richer finite-size or `2^20` exploration

Adding intermediate sizes, more sigmas, or length `2^20` would better diagnose
finite-size drift but would cost substantially more, would not directly test
the observed grid-topology failure, and would cross the existing `2^20`
information-gain/runtime gate. Such a campaign may be preregistered later as
exploratory finite-size science while accepting unresolved P1. It is rejected
for this narrowly scoped authorization extension.

## Explicit non-goals

- no mutation or replacement of P0, v1, combined-v2, or their analyses;
- no union of P0/v1 fine points into blocked-sigma authorization axes;
- no sigma `0.8` or `1.1` v2 sampling;
- no new length, observable, estimator, threshold, tie-break, or selector;
- no adaptive sampling or post-hoc change;
- no P1 execution in this design;
- no confirmatory use of P0, v1, v2, or P1;
- no physical claim of any kind.
