# Challenge 81 Restartable Production Design

## Goal

Complete the four-day acceptance line for Challenge #81 before attempting the
β=100 research extension. The immediate target is a controlled continuous-bath
calculation at β=16 or β=32, followed by a CT-HYB comparison and a complete
observable and resource error budget.

The physical setup remains:

- particle-hole-symmetric spinful Anderson impurity model;
- `D=1`, `U=0.8`, `Gamma=0.1`, `epsilon_d=-U/2`, and `mu=0`;
- deterministic purification of the complete interacting finite-bath
  Hamiltonian;
- impurity occupancy, double occupancy, and spin-resolved `G(tau)` on the
  shared `tau/beta={0,1/4,1/2,3/4,1}` grid.

The existing small-bath MPS-versus-ED gate remains binding at maximum absolute
error `1e-6`. The observed accepted fixture error is approximately `4.63e-8`.

## Current evidence

The first scheduler-bounded `N_b=12`, β=16, `dt=0.05`, `maxdim=512` pilot used
four Julia threads and an 8 GB allocation. It reached thermal step 48 of 320,
or β≈2.4, in 30 minutes before the scheduler timeout. Maximum link dimension
reached 54, peak RSS was approximately 3.1 GB, local Krylov calls converged,
and reported truncation errors remained below `1e-12`.

This is a runtime and restartability failure, not evidence of a numerical
instability. The original wall-time estimator materially underestimated the
direct-star TDVP cost.

## Chosen strategy

Use reliability-first uniform two-site TDVP:

1. make every long thermal and Green-function evolution restartable;
2. calibrate CPU scaling and the wall-time model from measured segments;
3. complete the `N_b=12` β=16 anchor and its controlled sweeps;
4. proceed to β=32 and `N_b=24`;
5. implement QN-conserving purification and star-to-chain mapping before any
   `N_b=48` production execution;
6. run CT-HYB and assemble the final error budget;
7. only then pursue implicit logarithmic evolution, adaptive bond expansion,
   and β=100.

Directly submitting longer non-restartable jobs is rejected because scheduler
or node failures would discard hours of work. Optimization-first development
is deferred because it delays the minimum accepted scientific result.

## Restart architecture

### Checkpoint contents

A checkpoint is an immutable, hash-bound snapshot containing:

- canonical request and request SHA256;
- Julia project, Manifest, model, bath, and source identities;
- solver settings and effective TDVP subdivision settings;
- phase (`thermal`, `green_up_particle`, `green_up_hole`,
  `green_down_particle`, or `green_down_hole`);
- tau-point index where applicable;
- completed step count, current beta endpoint, and target endpoint;
- serialized MPS state and normalization-log accumulator;
- bounded diagnostics accumulated so far;
- wall time, peak RSS, Julia threads, BLAS threads, and actual link dimensions;
- checkpoint schema and writer versions.

Resume is fail-closed. Any mismatch in request, bath, code/runtime identity,
solver settings, phase, dimensions, or diagnostic history rejects the
checkpoint instead of silently starting from it.

### Publication

Each checkpoint is written to a unique same-directory staging path, flushed,
fsynced, independently reloaded and validated, and atomically renamed.
Completion artifacts remain separate from checkpoints and are published only
after all phases and scientific gates pass.

At most one valid current checkpoint exists per convergence cell. Previous
valid checkpoints are retained as immutable audit generations until the cell
completes. Abandoned staging files are archived explicitly.

### Scheduler behavior

The Slurm wrapper obtains the job time limit and start time from Slurm. It
requests a graceful checkpoint before a conservative shutdown margin. SIGTERM
also requests a checkpoint. A checkpointed incomplete cell exits with a
distinct retryable status; scientific or provenance failures remain
non-retryable.

Repeated array submission validates the current checkpoint and resumes the
same cell. It never treats a checkpoint as a completed result.

## Runtime calibration

Run bounded `N_b=12` segments with 4, 8, and 16 CPU threads using identical
physical and solver inputs. Each segment records:

- steps and beta advanced per wall-clock second;
- time per sweep as a function of maximum link dimension;
- Julia and BLAS thread counts actually observed;
- CPU utilization and peak RSS from Slurm;
- checkpoint write/read time and size;
- observable-independent TDVP diagnostics.

Select the smallest allocation within 10% of the best measured throughput per
node. Memory requests use measured peak RSS with a safety factor; unused memory
is not a performance target.

The resource estimator is recalibrated from measured segment telemetry. It
must report uncertainty and a conservative wall-time recommendation rather
than claiming a universal analytic coefficient.

## Production sequence

1. Complete and validate the `N_b=12`, β=16, `dt=0.05`, `maxdim=512` anchor.
2. Complete β=16 timestep controls at `dt={0.2,0.1,0.05}`.
3. Complete β=16 bond controls at `maxdim={128,256,512}`.
4. Repeat the controlled anchor and required controls at β=32.
5. Run the `N_b=24` anchors and quantify bath-size change.
6. Implement and validate QN purification and star-to-chain mapping against
   dense ED and the existing small-bath MPS path.
7. Permit `N_b=48` only after both optimization capability gates pass.
8. Run production CT-HYB with matching model, bath/hybridization convention,
   beta, and tau grid.
9. Publish MPS–ED–CT-HYB comparisons and the split error/resource budget.

Independent cells may run as a Slurm array after their common checkpoint
implementation passes local and reduced-cluster tests. Multiple jobs must not
write the same cell or checkpoint generation.

## Error handling

- Scheduler timeout with a validated checkpoint: retryable and resumable.
- SIGTERM with a validated checkpoint: retryable and resumable.
- OOM, invalid MPS, nonfinite values, failed Krylov convergence, excessive
  truncation, maxdim saturation, or provenance mismatch: fail closed.
- Corrupt or stale checkpoints: archive and reject; never overwrite evidence.
- Missing progress or diagnostics: reject the convergence claim.
- CT-HYB autocorrelation or sampling failure: report as an unresolved
  comparator, not as agreement.

## Verification

Tests must cover:

- exact checkpoint round trip for a small MPS;
- interrupted-versus-uninterrupted equality within named numerical tolerance;
- request/config/source mismatch rejection;
- corrupt and partial checkpoint rejection;
- atomic-publication rollback and concurrent-writer exclusion;
- thermal and every Green branch resume point;
- Slurm shutdown-margin and SIGTERM paths;
- repeated submission skipping completed cells and resuming only incomplete
  cells;
- telemetry and resource-estimator calibration semantics.

A reduced cluster integration test must demonstrate at least two scheduler
jobs continuing one cell before any multi-hour production array is submitted.

## Acceptance

The core milestone is complete only when:

- the existing finite-bath `1e-6` MPS–ED gate remains passing;
- at least one β=16 or β=32 continuous-bath result has controlled timestep,
  bond, and bath errors;
- the result is cross-checked against production CT-HYB or a valid GTEMPO
  reference;
- the final artifact reports observables, split errors, wall time, peak memory,
  and per-bond dimensions with complete provenance.

If controlled β=16 or β=32 cannot be reached, an automated convergence-failure
report is acceptable only when it includes the validated reachable frontier,
resource scaling, error diagnostics, and reproducible restartable workflow.
