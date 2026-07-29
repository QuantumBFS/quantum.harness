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

Heavy trajectories run only on clusters. The first target is Wuzh02: one
single-core Slurm array with tasks `1-96`, 1800 MiB per task, 30-minute wall
time, and scheduler-managed concurrency so all available account slots are
filled. Local work is limited to bounded tiny protocols used by private test
helpers.

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

## Deterministic P1 outline

P1 may be defined only after P0 is downloaded and verified. For each sigma, a
deterministic rule documented before execution will select a narrower kappa
window from nonzero P0 checkpoints, add exact binary64 refinement points, and
assign fresh replica identities in a separately hashed protocol. P1 remains
exploratory unless a later, preregistered confirmatory phase uses a disjoint
phase namespace and untouched data.
