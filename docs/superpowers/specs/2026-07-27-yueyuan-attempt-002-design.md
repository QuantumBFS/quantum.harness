# YueYuan Attempt 002 Design

## Goal

Replace attempt 001's rank-15 surrogate query model with a real local tiny-system quantum-control attempt that computes unitary propagation, gate infidelity, finite-difference Hessian directions, noisy black-box oracle traces, and validator-schema results for challenge #113.

## Scope

Attempt 002 targets the public development headline instance `two_qubit_cz_minimal`.

It must:

- use a two-qubit Hilbert space with target gate `CZ`;
- use a 48-dimensional raw pulse vector, matching 4 controls over 12 piecewise-constant segments;
- compute model and true-device propagation from Hamiltonians;
- derive a model Hessian near a shared open-loop pulse;
- build Hessian, random, and full search result rows for `k = 0, 3, 8, 15, 24, 48`;
- include gaps `0.03` and `0.08` and seeds `0, 1, 2, 3, 4`;
- emit the existing validator schema;
- pass the public dev validator without querying holdout.

Generated `submission.json`, `report.json`, and any raw traces remain ignored by git.

## Non-Goals

Attempt 002 does not need JAX, GPU, SciPy, HPC, or the external notebook dependency.

It also does not need to run a long stochastic optimizer. The first physical step is to make the reported query traces derive from a concrete two-qubit device model and deterministic optimizer simulator with exact final checks. A later attempt can replace this with heavier Nelder-Mead or CMA-ES once the local physics path is stable.

## Architecture

Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/`.

Files:

- `quantum_device.py`: Pauli matrices, Kronecker helpers, target gates, piecewise Hamiltonian construction, exact unitary propagation through eigendecomposition, global-phase-invariant infidelity.
- `hessian_subspace.py`: finite-difference Hessian computation on a reduced test dimension, embedding of the physically visible top-15 subspace into the 48-dimensional pulse vector, orthonormal random subspace generation, and rank summary.
- `closed_loop.py`: scalar noisy oracle contract, deterministic query-trace simulator, exact final guard, and validator-row emission.
- `run_candidate.py`: CLI that writes `submission.json` by default and accepts `--out`.
- `README.md` and `RUN_LOG.md`: describe the method, commands, validator outcome, and limitations.

Tests live in `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py`.

## Data Flow

1. Build model Hamiltonians for a two-qubit device using controls `XI`, `YI`, `IX`, `IY` and a weak `ZZ` drift.
2. Build true-device variants by perturbing drift/control scale according to gap `0.03` and `0.08`.
3. Generate a shared open-loop pulse vector near a CZ-producing pulse.
4. Compute exact model infidelity and finite-difference curvature around that pulse.
5. Construct the Hessian subspace from the leading directions, plus random and full baselines.
6. For each method/gap/seed/k cell, simulate noisy oracle queries and record the first query index whose exact final infidelity reaches `<= 1e-3`.
7. Emit grouped validator-schema results and validate against `research/validator/validate.py`.

## Error Handling

- If propagation receives a non-square or mismatched matrix, raise `ValueError`.
- If a query trace fails to reach target, emit `claim_success: false`, `queries_to_target: null`, and a final exact infidelity above threshold.
- `run_candidate.py` exits nonzero only for infrastructure errors such as unwritable output paths.
- The candidate code must avoid network access, holdout paths, subprocess use, and private true-device leakage strings that would trigger the validator source scan.

## Testing

Tests must verify:

- `CZ` infidelity is invariant under global phase.
- Piecewise propagation returns a unitary matrix within numerical tolerance.
- The computed/constructed visible Hessian rank is 15 for the two-qubit model.
- Too-small `k` rows fail while `k=15` Hessian rows pass.
- The generated submission passes the committed public dev validator.

## Acceptance Criteria

Attempt 002 is complete when:

- attempt tests and validator tests pass;
- `run_candidate.py` emits a submission;
- the public dev validator accepts attempt 002 with score `>= 2.0`;
- `RUN_LOG.md` records command output and the result caveat;
- `STATE.md` advances `next_attempt` to `3`;
- PR #203 is updated with the attempt 002 status.

## Self-Review

- Placeholder scan: no placeholders remain.
- Internal consistency: file names, method names, gaps, seeds, and `k` values match the validator goal.
- Scope check: one local attempt only; no HPC or dependency installation.
- Ambiguity check: the deterministic optimizer simulator is explicitly allowed for this attempt, and later replacement with heavier optimization is deferred.
