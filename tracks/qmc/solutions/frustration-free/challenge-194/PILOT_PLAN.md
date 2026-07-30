# Challenge 194 Physical Pilot Plan

## Boundary

Pilot P0 is a post-engine, exploratory window-selection phase. Its output may
select the deterministic P1 refinement window, but it is not confirmatory data
and authorizes no transition, critical-point, exponent, scaling, or universality
claim. Zero coupling is retained as an invariant checkpoint and is excluded
from later interpolation.

## Frozen P0 protocol

- Sigma order: binary64 values `0.8`, `0.9`, `1.0`, `1.1`, serialized and
  reconstructed only with `float.hex()` and `float.fromhex()`.
- Length order: `2**10`, `2**14`, `2**18`.
- Replica order: integers `0..7`.
- Canonical nesting: sigma, then length, then replica, exactly 96 cells.
- Couplings: exact binary64
  `[0.0] + [0.25 * 1.25**j for j in range(15)]`, serialized as hex strings.
- Master seed: `19_420_260_729`; phase namespace: `"pilot"`.
- Sigma identity:
  `pilot-p0-v1|sigma-f64=<exact float.hex() representation>`.
- One trajectory, one existing-artifact run directory, and one immutable outer
  success marker per cell.

The canonical JSON bytes of this document are not substituted for the document
itself: `analysis_plan_sha256` is the SHA256 of the committed bytes of this
file.

## Correctness and provenance

Pilot construction requires the passing immutable production-v1 correctness
package approved at orchestration revision
`fd0aa314f324dc357918926e80f93f4356083fc0`: its report, exact 120-cell
validation run spec and check registry, embedded historical validation-source
revision, runtime evidence, and lock hash. The report source must exactly match
the validation run spec; it is not falsely rewritten to the approval revision.
Later orchestration commits may change the current clean revision without
changing scientific semantics.

The checked-in canonical approval registry is
`pilot_correctness_approval.json`. It authenticates the Wuzh02
`validation-prod-fd0aa31-compute` package with report SHA256
`22b5e87d8fcf48461c0e42d0fbdc403fe70d09337989316a5aa283e36c825ce9`,
validation run-spec SHA256
`a6e4ff45cef7d9e331179665dc492cc3ed6624566ccda2ad3cf4591aebb10f7e`,
protocol SHA256
`c7e980eeadaf8ed75e4d20cebb1e2c5d5f57a1cfc329afa7678ae586f5b7f488`,
check-registry SHA256
`6e25ea41899544f2a9de3589beb1ee94b1f3dc505638b8f8e5164a4322b56a1d`,
and scientific-module aggregate
`a5fe99d23de9003eda565a4de71aaabf1393b909fc9feb57b5b7dff92ff95dab`.
The registry's canonical bytes are independently pinned in code to SHA256
`8ef77104299bdf8e0355cf23d3215f560e1773332a5face9c79ea7a261ac33e8`;
the registry cannot redefine its own trusted digest. No merely structurally
valid alternate report can authorize Pilot.

The frozen scientific whitelist is:

- `model.py`, `kernel.py`;
- `counter_rng.py`, `alias.py`, `edge_set.py`;
- `observables.py`, `production_union_find.py`;
- `trajectory.py`, `poisson_reference.py`, `poisson_sweep.py`.

Each path is rooted at `src/long_range_percolation/`. Every file SHA256 and
their canonical aggregate are checked against the correctness run spec and the
current checkout. Any drift blocks Pilot. The current clean orchestration
revision is separately recorded. The run spec also binds the correctness
report hash, validation run-spec hash, `uv.lock`, compute-node runtime
capability, complete 96-cell RNG assignment, every request and kernel hash,
and this plan.

## Capability waiver and resources

The user waived Task 10's 120-second/4-GiB capability gate and Task 11
optimization only after the correctness gate. This waiver must never be called
a pass. Its record is:

- reason: `user-waived-after-correctness-gate`;
- benchmark status: `cancelled-without-capability-report`;
- immutable UTC build timestamp.

Runtime capability is generated when the run spec is built and rechecked by
each worker on its compute node. Login-node capability is not presumed portable
to a compute kernel.

Heavy trajectories run only on clusters. The original P0 campaign used one
single-core Slurm array with tasks `1-96` and 1800 MiB per task. The versioned
P0 extension uses the exact resources frozen below. Local work is limited to
bounded tiny protocols used by private test helpers.

The build-spec compute step and every array worker use the same influential
environment contract. Before Python starts, inherited `NUMBA_*`, `PYTHONHOME`,
`PYTHONUSERBASE`, `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONINSPECT`,
`PYTHONWARNINGS`, `PYTHONBREAKPOINT`, `PYTHONSAFEPATH`, `LD_PRELOAD`,
`LD_LIBRARY_PATH`, `LD_AUDIT`, and `LIBRARY_PATH` are removed. Then
`NUMBA_DISABLE_JIT=0`, `NUMBA_NUM_THREADS=1`, `PYTHONNOUSERSITE=1`,
`PYTHONHASHSEED=0`, `PYTHONUNBUFFERED=1`, and
`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=VECLIB_MAXIMUM_THREADS=1`
are pinned. The only restored `PYTHONPATH` is the absolute committed `src`
directory. Build deployment must apply that exact cleanup/pinning fragment,
using a private node-local absolute non-symlink `NUMBA_CACHE_DIR`. Each cache
leaf must be absent before launch, created exactly once with mode restricted by
`umask 077`, owned by the task user, writable, canonical, and empty immediately
after creation; pre-existing empty directories are rejected as well as
non-empty directories and symlinks. The Slurm wrapper applies these rules
independently to every worker, and the documented build-spec command must do
the same.

The compute-node build command uses a numeric Slurm job ID and the same
single-owner creation rule (after the environment cleanup above):

```bash
[[ "${SLURM_JOB_ID}" =~ ^[0-9]+$ ]] || exit 64
CACHE_BASE="${SLURM_TMPDIR:?}"
[[ "${CACHE_BASE}" == /* && ! -L "${CACHE_BASE}" &&
   -d "${CACHE_BASE}" && -w "${CACHE_BASE}" ]] || exit 73
[[ "$(realpath -s -- "${CACHE_BASE}")" == "$(realpath -e -- "${CACHE_BASE}")" ]] ||
  exit 73
export NUMBA_CACHE_DIR="${CACHE_BASE%/}/challenge-194-pilot-build-${SLURM_JOB_ID}"
umask 077
mkdir -- "${NUMBA_CACHE_DIR}" || exit 73
[[ ! -L "${NUMBA_CACHE_DIR}" && -O "${NUMBA_CACHE_DIR}" &&
   -d "${NUMBA_CACHE_DIR}" && -w "${NUMBA_CACHE_DIR}" &&
   "$(realpath -e -- "${NUMBA_CACHE_DIR}")" == "${NUMBA_CACHE_DIR}" ]] ||
  exit 73
shopt -s nullglob dotglob
CACHE_ENTRIES=("${NUMBA_CACHE_DIR}"/*)
shopt -u nullglob dotglob
(( ${#CACHE_ENTRIES[@]} == 0 )) || exit 73
```

## Restart and publication

Each cell owns:

```text
cells/<cell-id>/run/{request.json,environment.json,kernel/,
  seed-manifest.json,capability.json,trajectories/,batches/,
  progress.json,manifest.json}
cells/<cell-id>/manifest.json
```

All run-spec paths are relative to the downloaded Pilot root. Existing success
cells are deeply verified. A complete trajectory may resume batch, progress,
and outer-marker publication. Surviving `.partial` or `.intent` files block
recovery and are never deleted. Duplicate workers serialize at the cell
directory: one publishes without clobbering; the loser succeeds only after
full verification. Different cells may be created concurrently: the shared
`cells/` descriptor remains bound to the same directory, owner, mode, device,
and inode while its legitimate child-count and timestamp metadata may change.
Immutable ancestors and each exact target cell retain strict generation
binding; shared-directory substitution and cell swap/restore still fail.

## Frozen versioned P0 extension

The only approved extension is `pilot-p0-extension-v1`. It is bound to design
SHA256 `5426e3007e9d83039f371ca6a9372f1868ef9d5447b66a12b1643ecf72907aba`,
P0 run-spec SHA256
`d17d3df9528a09f0d834ebe9d5ce6f283e488d2326f6cb14873a90923c5d9840`,
P0 progress SHA256
`ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f`,
P0 analysis document SHA256
`e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8`,
canonical analysis-file SHA256
`44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b`,
bracket SHA256
`fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403`,
and P0 revision `739880d9ccdcffbfc8a15310250349bd11d63bbb`.

Its schemas are exactly:

- `challenge-194-p0-extension-protocol-v1`;
- `challenge-194-p0-extension-run-spec-v1`;
- `challenge-194-p0-extension-progress-v1`;
- `challenge-194-p0-extension-analysis-v1`;
- `challenge-194-p0-combined-analysis-v2`;
- `challenge-194-p1-brackets-v2`.

The axes are sigmas `0x1.ccccccccccccdp-1` and
`0x1.0000000000000p+0`, lengths `1024`, `16384`, `262144`, and replicas
`24..39`, in sigma/length/replica order. This gives exactly 96 cells and
trajectories, 17 checkpoints per trajectory, 1,632 checkpoints, and 102
extension estimate rows. The master seed is `19_420_262_729`, phase is
`"pilot"`, and grid namespace is `"pilot-p0-extension-v1"`. Replica, request,
and RNG identities must be disjoint from P0 replicas `0..7` and reserved P1
replicas `8..23`.

The deterministic component rule recomputes the unchanged selector's original
P0 marks using lengths `16384` and `262144`, groups contiguous marked
intervals separately, chooses the lowest-coupling four-sector component and
the nearest `Q_G` component (equal gaps choose lower coupling), takes their
closed union, and adds exactly one original-P0 guard interval on each side.
Four recursive binary64 midpoint levels then produce exactly 17 ordered
points. The sigma `0.9` grid is:

```text
0x1.f400000000000p-2, 0x1.1085a00000000p-1,
0x1.270b400000000p-1, 0x1.3d90e00000000p-1,
0x1.5416800000000p-1, 0x1.6a9c200000000p-1,
0x1.8121c00000000p-1, 0x1.97a7600000000p-1,
0x1.ae2d000000000p-1, 0x1.c4b2a00000000p-1,
0x1.db38400000000p-1, 0x1.f1bde00000000p-1,
0x1.0421c00000000p+0, 0x1.0f64900000000p+0,
0x1.1aa7600000000p+0, 0x1.25ea300000000p+0,
0x1.312d000000000p+0
```

Its grid SHA256 is
`76dc7e07639ed085873a8f291cc2aaee0e8942ddac8efce3982743dd67491071`.
The sigma `1.0` grid is:

```text
0x1.3880000000000p-1, 0x1.6092ca0000000p-1,
0x1.88a5940000000p-1, 0x1.b0b85e0000000p-1,
0x1.d8cb280000000p-1, 0x1.006ef90000000p+0,
0x1.14785e0000000p+0, 0x1.2881c30000000p+0,
0x1.3c8b280000000p+0, 0x1.50948d0000000p+0,
0x1.649df20000000p+0, 0x1.78a7570000000p+0,
0x1.8cb0bc0000000p+0, 0x1.a0ba210000000p+0,
0x1.b4c3860000000p+0, 0x1.c8cceb0000000p+0,
0x1.dcd6500000000p+0
```

Its grid SHA256 is
`d40b4a2afac533d74965513513fff1870918831000b2e040063ca2a0e29ad091`.
The basic ten-column trajectory schema, scientific engine, realization and
stopping policy, correctness registry, capability waiver, and exploratory
phase are unchanged. No interpolation, uncertainty rescue, threshold change,
nearest-interval fallback, manual choice, adaptive extension, new observable,
P1 execution, or confirmatory use is permitted.

The immutable artifact names are
`p0_extension_v1_protocol.json`, `pilot-p0-extension-v1/run_spec.json`,
`pilot-p0-extension-v1/progress.json`, `p0_extension_v1_analysis.json`,
`p0_combined_analysis_v2.json`, `p0_combined_brackets_v2.json`, and,
conditionally, `p1_protocol.json`. Canonical finite UTF-8 JSON uses sorted
keys, compact separators, one trailing newline, atomic publication, and
no-clobber verification.

Wuzh02 execution uses `wzacnormal03`: one CPU, 1800 MiB, 40-minute wall time,
no GPU, and a private node-local Numba cache per worker. Array IDs `1..96` map
to cell indices `0..95`. The three submission batches are smoke `1-2%2`,
light/medium `3-32,49-80%16`, and heavy `33-48,81-96%8`.

Restart requires the identical protocol, run spec, source, runtime, request,
and RNG assignment. Completed cells are deeply verified. A published
trajectory may resume only missing batch, progress, or outer-manifest
publication. Duplicate workers serialize. Surviving `.partial` or `.intent`
files, malformed markers, substitutions, drift, or unexpected paths are
preserved and fail closed. Merge requires exactly 96 cells and trajectories.

The six acceptance checks are:

1. The protocol verifies against the exact P0 evidence and committed design.
2. The downloaded root verifies exactly 96 cells and 96 trajectories.
3. Extension and combined analyses pass canonical, hash, identity, source,
   schema, and semantic recomputation.
4. Both sigma `0.9` and `1.0` obtain a nonzero adjacent interval marked by
   both unchanged estimators.
5. Sigma `0.8` and `1.1` reproduce their exact existing transition and
   crossover brackets.
6. The bracket says `requires_p0_extension=false` and an independent
   recomputation is byte-identical.

P1 remains absent unless all six acceptance checks pass. An unresolved
extension is valid and cannot trigger extra points or a relaxed selector.

## Deterministic P1 selection and boundary

P1 may be defined only after P0 is downloaded, verified, and aggregated into a
source-hash-bound analysis document. The frozen selector is:

1. Use the two largest P0 sizes.
2. Mark each adjacent nonzero-coupling interval containing a sign change in
   the difference of the two sizes' mean `Q_G`.
3. Independently mark an interval when either size's four-sector crossing
   probability spans the closed range `[0.25, 0.75]`.
4. For sigma at most one, retain only intervals marked by both estimators,
   select the narrowest interval, and break equal-width ties by lower coupling.
   No common interval requires a new versioned P0 extension; it never permits
   post-hoc interpolation or a fabricated bracket.
5. For sigma `1.1`, select the interval with maximum absolute finite-difference
   slope of the largest-size crossing probability, breaking ties by lower
   coupling. This is labeled only as crossover refinement.

Every selected window would produce nine ordered binary64 points: the exact
endpoints and seven recursively bisected interior points. The separately
hashed P1 protocol uses master seed `19_420_261_729`, the existing `"pilot"`
phase, a new `pilot-p1-v1` grid identity, and fresh replicas `8..23`. P0
replicas are not reused.

P0 and P1 remain exploratory. Neither can enter confirmatory likelihoods or
authorize transition, critical-point, exponent, scaling, or universality
claims. Any later confirmatory phase must be preregistered, use a disjoint RNG
phase namespace, and use untouched data.

The current immutable P0 analysis selects windows for sigma `0.8` and the
sigma `1.1` crossover control, but sigma `0.9` and `1.0` have no common
nonzero interval. Therefore P1 publication and execution are blocked pending
execution, download, and verification of the frozen extension above.
