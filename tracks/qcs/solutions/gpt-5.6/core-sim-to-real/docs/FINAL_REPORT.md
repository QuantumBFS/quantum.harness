# Challenge 113 final report

## Result in one sentence

On a preregistered 24-cell synthetic CNOT holdout, the frozen
model-informed `k=15` calibration succeeds in 90.625% of nested runs
(empirical family-stratified truth-cell bootstrap 95% interval
81.25–97.92%), versus 25% for a deterministically completed model-informed
`k=40` search and 0% for raw-coordinate `k=40`, while using 39.76% of their
full query cap and 39.05% of their full shot cap.

The primary online resource quantity is the deterministic 66-query cap for
`k=15`, versus 166 for either `k=40` method. The sealed-results
queries-to-target derivation gives 48.76 restricted-mean post-hoc,
oracle-scored first-hit queries for `k=15` (empirical 95% interval
45.35–52.47), versus 160.63
(153.69–165.84) for completed model-informed `k=40` and 166 for raw `k=40`.
Failures are charged their complete frozen method cap; this is not an online
stopping certificate.

## Problem

Quantum-gate calibration must reconcile a cheap differentiable simulator with
an expensive device that can only be queried through finite-shot
measurements. A two-qubit gate has 40 pulse parameters here, but the nominal
phase-blind Hessian has rank 15. We ask whether those 15 simulator directions
remain a useful calibration subspace after model mismatch.

## Method

The nominal JAX simulator produces:

1. a model-optimal CNOT pulse;
2. the top 15 positive-curvature Hessian eigenvectors; and
3. a deterministic orthogonal completion for a controlled `k=40` comparator.

The true device is hidden behind a scalar interface:

```text
query(parameters, shots) -> sampled fidelity
```

The calibration loop never receives a true-device gradient, Hamiltonian, or
exact fidelity. Each method uses two frozen global-update cycles, paired shot
noise, the same acceptance logic, and a fixed trust radius. Exact fidelity is
attached only after the client closes.

## Fresh confirmation

The benchmark contains:

- three mismatch families: control-map, drift, and combined;
- eight previously unopened truth seeds per family;
- four finite-shot replicates nested in each truth cell; and
- three frozen methods.

All 288 runs completed without exception. The independent Attempt-50 audit
reconstructed the complete grid, paired seeds, aggregate query/shot ledgers,
20,000-draw family-stratified bootstrap, paired differences, exact safety
interval, source seals, and artifact hashes: 18/18 checks passed.

## Interpretation

The useful result is not merely that `k=15` is cheaper. The completed `k=40`
method contains exactly the same 15 principal directions and uses the same
calibration rule, but adds 25 nominally flat complement directions. Under
finite-shot central differences, those directions consume queries and inject
noise into the trust-region step. The wider method therefore performs worse
despite containing the successful subspace.

## Queries-to-target deliverable

The development panel sweeps model-informed dimensions
`k = 5, 10, 15, 20, 40`; the fresh panel compares selected `k=15` with
completed and raw `k=40`. The metric uses the actual black-box query position
of the first accepted pulse that reaches exact post-hoc infidelity `<= 1e-3`.
A failure is retained at its complete method cap.

This plot must be interpreted jointly with success probability. For example,
development `k=5` has a numerical horizon of only 26 queries but succeeds in
0% of truth cells. The selected `k=15` is the smallest tested geometry that
combines high success with a low query horizon.

The exact target event is attached after calibration and is not available to
the optimizer. Attempt 43's proposed online stopping certificate failed, so
the derived figure is a benchmark comparison rather than a deployable online
stop rule.

## Failure boundary and cross-size invariant

Attempt 52 independently verifies the sealed Attempt-45 appendix without a
simulator call. In the historical Joint-15 v1 development package, combined
mismatch success falls from 0.875 at `epsilon=0.05` to 0.15625 at
`epsilon=0.10`; control-map and drift families also degrade at the largest
tested gap. These curves identify a failure boundary but are not a fresh
principal-global confirmation sweep.

At converged audited optima, endpoint-map and phase-blind Hessian ranks agree
as `(3,3)`, `(8,8)`, and `(15,15)` for `d=2,3,4`, with the original `d=4`
CNOT also giving `(15,15)`. The supported invariant is conditional on
controllability, parameter accessibility, and convergence. An earlier `d=4`
rank discrepancy was traced to optimizer-residual/spectral-gap numerics.

## Honest boundaries

- This is synthetic two-qubit CNOT evidence, not real hardware.
- The neutral-atom adapter is perfect-blockade and not cesium-specific.
- Success is oracle-scored after calibration; it is not an online target
  certificate.
- The headline resource quantity is a deterministic full protocol cap.
- The proposed cheaper online stopping rule failed.
- The unconditional `rank(H)=d^2-1` statement is rejected; only the audited
  conditional local rank equality is supported.
- Cross-dimension resource advantage was not identifiable under the frozen
  Attempt-28 epsilon because raw warm starts had zero restricted cost in
  `d=2,3,4`.
- The formal result stores aggregate ledger closure and a canonical row hash,
  not every query row; the MWE retains complete rows.

## Reproduction

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r core-sim-to-real/requirements.txt

python core-sim-to-real/code/attempt50_result_audit.py --verify-only
python core-sim-to-real/code/attempt51_queries_to_target.py --verify-only
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
python core-sim-to-real/run_challenge.py --mwe
python core-sim-to-real/run_challenge.py --full
```

`--mwe` is a fast public development-truth demonstration. `--full` replays
the now-public Attempt-49 benchmark in a new directory and must not be
described as a second independent confirmation.

The organizer-compatible compact artifacts are:

- `final/run.json`;
- `final/report.json`; and
- `final/report.html` (single-file offline report).
