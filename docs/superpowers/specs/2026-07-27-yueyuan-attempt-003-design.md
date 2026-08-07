# YueYuan Attempt 003 Design

## Goal

Upgrade attempt 002 by replacing deterministic query traces with an actual derivative-free optimizer that calls a finite-shot noisy scalar oracle while the validator records exact final infidelity privately.

## Scope

Attempt 003 targets the same public development headline instance, `two_qubit_cz_minimal`.

It must:

- keep the two-qubit CZ toy dynamics from attempt 002;
- keep the 48-dimensional raw pulse vector and rank-15 model Hessian subspace;
- implement a local derivative-free optimizer with no SciPy dependency;
- make optimizer decisions from noisy oracle values, not exact infidelity;
- compute `queries_to_target` from the first candidate whose exact true infidelity is `<= 1e-3`;
- emit rows for full raw, random subspace, and Hessian subspace methods over gaps `0.03` and `0.08`, seeds `0..4`, and `k = 0, 3, 8, 15, 24, 48`;
- pass the existing public dev validator without querying holdout.

Generated `submission.json`, `report.json`, and raw traces remain ignored.

## Architecture

Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/`.

Files:

- `quantum_device.py`: local two-qubit propagation and phase-invariant CZ infidelity.
- `hessian_subspace.py`: deterministic model mixing, finite-difference Hessian, top-Hessian and random/tilted subspaces.
- `optimizer.py`: pure-Python/NumPy Nelder-Mead-style simplex optimizer with a strict query budget and callback for exact private scoring.
- `closed_loop.py`: noisy oracle, method/gap/seed/k runner, grouped validator-schema output, and summary.
- `run_candidate.py`: CLI output writer.
- `README.md` and `RUN_LOG.md`: commands, score, interpretation, and next gap.

Tests live in `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py`.

## Data Flow

1. Build model and true-device mixing for each gap.
2. Build a search subspace for each method:
   - full raw: identity basis;
   - Hessian: top model-Hessian eigenvectors;
   - random: a reproducible tilted visible subspace so it is a fair dimensionality control.
3. Wrap the true device in a noisy scalar oracle. Each optimizer call consumes one query and `1024` shots.
4. Run the simplex optimizer from the shared zero coefficient vector.
5. Track the first query whose exact true infidelity reaches target; the optimizer itself receives only noisy values.
6. Emit validator-schema grouped rows and validate.

## Error Handling

- If a subspace has zero columns, emit an immediate plateau row with no queries-to-target.
- If an optimizer exhausts the query budget without exact success, emit `claim_success: false`, `queries_to_target: null`, and the best exact final infidelity observed.
- The candidate code avoids network access, subprocess use, holdout paths, and private-leakage strings.

## Testing

Tests must verify:

- the noisy oracle increments queries and exposes only scalar noisy values to the optimizer;
- the simplex optimizer improves a small convex quadratic in fewer than 80 queries;
- Hessian `k=15` attempt rows come from optimizer traces and pass the exact final guard;
- too-small `k` rows still fail;
- the generated submission passes the committed public dev validator.

## Acceptance Criteria

Attempt 003 is complete when:

- attempt 003 tests and all existing attempt/validator tests pass;
- `run_candidate.py` emits `submission.json`;
- the public dev validator accepts attempt 003 with score `>= 2.0`;
- `RUN_LOG.md` records commands, score, and caveat;
- `STATE.md` advances `next_attempt` to `4`;
- PR #203 is updated.

## Self-Review

- Placeholder scan: no placeholders remain.
- Internal consistency: file paths, methods, gaps, seeds, and `k` values match the validator.
- Scope check: one local optimizer attempt only; no HPC or dependency installation.
- Ambiguity check: optimizer decisions use noisy values; exact values are used only for private query-to-target and final guard bookkeeping.
