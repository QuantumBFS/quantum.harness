# Success-first high-throughput scan plan

## Global constraints

- Numerical computation runs only on WSL or the 64-core CPU machine.
  The local Windows workspace is for editing, Git, and result collection.
- Reuse the frozen determinant oracle and existing exact certificate code.
- Stop a candidate at its first failed gate.  A failed candidate is logged
  but does not trigger a no-go proof.
- Every cell writes an atomic manifest and can be resumed without
  recomputing successful cells.
- BLAS libraries use one thread per worker.  Leave two logical CPU cores
  unused on each compute machine.
- `AGENT_HANDOFF.md` is private and must never be staged or uploaded.

## Task 1: oddcycle pair runner

Implement a resumable pair-grid entry point for alphabets

`{B(p_low,q,r), B(p_low,q,r)^T, B(p_high,q,r), B(p_high,q,r)^T}`.

The first frozen grid is:

- `p_low`:
  `1e-5,2e-5,5e-5,1e-4,2e-4,5e-4,1e-3,2e-3,3e-3,5e-3,7.5e-3,1e-2,1.5e-2,2e-2,3e-2,4e-2,5e-2`;
- `p_high = 0.55 + 0.025*k`, `k=0..28`;
- `q,r = 0.9,0.95,1.0,1.05,1.1`.

This gives 12,325 cells and includes the successful control
`(p_low,p_high,q,r)=(0.001,0.8,1,1)`.

Per-cell gates:

1. frozen determinant oracle on every word through depth 6;
2. strict common quadratic metric at each endpoint;
3. reject a strict joint common quadratic metric;
4. last-letter path-metric SDP with inertia validation;
5. numerical coherent time-orientation sign synchronization.

The manifest records the first failure, all margins, runtime, and a compact
candidate score.  It must support deterministic virtual-worker sharding.
Exact rationalization is a survivor-promotion step, not part of every cell.

## Task 2: non-induced exterior-grade runner

Implement a discovery runner for `d=5` four-letter transpose-closed
alphabets generated from a strict totally-positive Jacobi-factor core,
small signed non-nearest-neighbor shears, and independent exterior-grade
orthogonal gauges:

- `Q1=Q4=I`;
- `Q2` is a rational Givens rotation in the grade-2 compound basis;
- `Q3=* Q2 *^{-1}` under the fixed Hodge identification.

First axes:

- Jacobi strengths `1/4,1/2,1,2`;
- diagonal condition ratios `1,2,4,8`;
- signed chord shear magnitudes
  `1/64,1/32,1/16,1/8,1/4,1/2`;
- chord patterns `{02,31}`, `{03,42}`, `{02,24,40}`;
- rational Givens half-angles `0,1/64,1/32,1/16,1/8,1/4`;
- six fixed grade-2 coordinate-plane pairs;
- two-atom scale ratios `1/2,4/5,1,5/4,2`.

Per-cell early-stop gates:

1. finite, invertible, positive determinant, condition number below `1e10`;
2. every transformed grade `1..4` compound has relative entry margin
   above `1e-8`;
3. at least one original order-2 minor is below `-1e-6`;
4. the grade-2 gauge has non-induced Klein/Pluecker residual above `1e-6`;
5. mixed-word determinant stress only for survivors of gates 1--4.

The arbitrary-word theorem for a promoted hit is

`det(I+W)=sum_k trace(C_k(W)) >= 1`,

because every transformed compound belongs to one entrywise nonnegative
semigroup.  Promotion requires exact rational compound replay and the
existing positive-field Hermitian interacting Fock-transfer construction.

## Deployment

- WSL: Task 1, virtual workers `0..13`.
- CPU machine: Task 1 virtual workers `14..75`, then Task 2 with 62
  single-threaded workers.
- After Task 1 is stable, Task 2 may occupy the CPU machine while WSL
  continues oddcycle survivor promotion.
- Each completed scan appends success/failure lessons to
  `docs/EXPERIMENT_LOG.md` and pushes manifests plus summaries to the
  shared team branch.
