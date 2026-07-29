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
full verification.

## Deterministic P1 outline

P1 may be defined only after P0 is downloaded and verified. For each sigma, a
deterministic rule documented before execution will select a narrower kappa
window from nonzero P0 checkpoints, add exact binary64 refinement points, and
assign fresh replica identities in a separately hashed protocol. P1 remains
exploratory unless a later, preregistered confirmatory phase uses a disjoint
phase namespace and untouched data.
