# Core sim-to-real calibration direction

This directory is the agent-readable, reproducible package for the team's
Challenge 113 calibration direction.

## Read first

1. [`docs/AGENT_HANDOFF.md`](docs/AGENT_HANDOFF.md) — current state, claim
   boundary, and next integration steps.
2. [`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md) — compact scientific result.
3. [`docs/ATTEMPT50_PROTOCOL.md`](docs/ATTEMPT50_PROTOCOL.md) — final-package
   contract.
4. [`docs/ATTEMPT49_REPORT.md`](docs/ATTEMPT49_REPORT.md) — immutable formal
   confirmation.
5. [`docs/REFLECTION_REPORT_05.md`](docs/REFLECTION_REPORT_05.md) — what
   worked, what failed, and why the core experiment now stops.

## Result

Attempt 49 was preregistered before opening 24 fresh synthetic CNOT truth
cells. Across four nested finite-shot replicates per cell, the frozen
model-informed `k=15` method achieved 90.625% success (empirical
family-stratified truth-cell bootstrap 95% interval 81.25–97.92%), versus 25%
for completed model-informed `k=40` and 0% for raw-coordinate `k=40`.

The `k=15` method uses 66/166 = 39.76% of the deterministic full query cap and
2,099,200/5,376,000 = 39.05% of the full shot cap of either `k=40` method.
All six preregistered gates passed, all 288 runs completed, and the independent
Attempt-50 reconstruction passed 18/18 checks.

The Challenge-113 queries-to-target deliverable is derived without new device
queries from sealed Attempts 44 and 49. On the fresh confirmation it gives
48.76 restricted-mean post-hoc queries to target for `k=15`, versus 160.63
for completed model-informed `k=40` and 166 for raw `k=40`. Failures are
charged their complete method cap. This is a benchmark metric, not an online
stopping certificate.

The supported mechanism is specific: the nominal CNOT Hessian supplies 15
positive-curvature directions, while completing the same basis to 40
directions adds nominally flat coordinates that consume queries and inject
finite-shot noise into the global update.

Attempt 52 closes the remaining issue deliverables from sealed development
evidence: model-truth-gap failure curves and a conditional local
endpoint/Hessian-rank invariant across `d=2,3,4`. It performs no new simulator
query, passes 22/22 audit checks, and does not turn those curves into fresh
confirmation evidence.

## Reproduce

From the repository root:

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

`--mwe` is a fast end-to-end demonstration on one public development truth
and retains every query-ledger row. `--full` replays the now-public 288-run
Attempt-49 benchmark into a new ignored output directory. It is reproducibility
evidence, not a second independent fresh confirmation.

Organizer-compatible compact artifacts are under [`final/`](final/):
`run.json`, `report.json`, three embedded result figures, and the single-file
offline `report.html`.

## Claim boundary

- Synthetic two-qubit CNOT benchmark only; no real-hardware claim.
- The neutral-atom adapter is perfect-blockade and not cesium-specific.
- Success is post-hoc oracle-scored, not an online target certificate.
- The headline cost is a deterministic frozen full cap.
- The attempted cheaper online stopping rule failed.
- The unconditional rank law is rejected; the observed cross-size rank
  equality is conditional on controllability, accessibility, and convergence.
- Cross-dimension resource advantage was not identifiable in Attempt 28.
- Truth cell, not nested shot-noise replicate, is the independent unit.

Never modify or stage the protected upstream notebook.
