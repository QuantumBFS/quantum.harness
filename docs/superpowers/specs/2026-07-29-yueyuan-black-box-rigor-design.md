# YueYuan Black-Box Rigor Design

## Goal

Improve attempt 004's no-real-hardware challenge solution by making the
software true-device boundary harder to criticize, adding a sealed holdout
evaluation, and running a moderate device-informed sweep that remains honest
about the lack of real hardware.

## Context

Challenge 113 does not require real hardware. It requires a differentiable model
and a true device that can only be queried for finite-shot noisy scalar
feedback. Attempt 004 already implements that route, but the previous review
identified four remaining weaknesses:

- closed-loop methods carry an audit object inside the optimizer functions;
- the device-informed method has only a small hard-cell smoke comparison;
- there is no dev/holdout separation for hidden mismatch seeds;
- the true-device perturbations are useful but still simple.

## Approved Execution Mode

Use local implementation and verification first, then submit a conservative
moderate CPU sweep on the user's HPC system. Do not use more than 200 CPU cores
or one GPU at a time. This pass should prefer CPU jobs; GPU use is optional only
if the environment already works.

## Design

### 1. Sealed Black-Box Boundary

Introduce a transcript-oriented optimizer path. During closed-loop optimization,
the optimizer sees only:

- pulse parameters it proposes;
- noisy scalar return values from `QueryOnlyDevice.query()`;
- cumulative query and shot counters.

Exact fidelity scoring moves to a post-run scoring helper. The helper may use
the hidden true system because it is outside the optimizer boundary and exists
only to label results after the transcript is complete. Existing baseline APIs
can remain for compatibility, but a new sealed path must be tested and used by
the new holdout runner.

### 2. Sealed Holdout Evaluation

Add a small manifest of dev and holdout seed offsets. Dev seeds are allowed for
method design and smoke tuning. Holdout seeds are evaluated once by the runner
and reported separately. The holdout runner must not choose hyperparameters
based on holdout outcomes.

### 3. Fuller Device-Informed Sweep

Add a moderate runner that compares:

- full-space Nelder-Mead;
- random benchmark-rank subspace;
- fixed Hessian benchmark-rank subspace;
- widen-only adaptive Hessian;
- device-informed adaptive Hessian.

The runner should cover both one-qubit and two-qubit systems, at least medium
and large gaps, multiple shot budgets, and multiple dev plus holdout seeds. It
should write JSONL transcripts, aggregate CSV tables, and a compact summary.

### 4. More Realistic Software True Device

Extend the true-device mismatch with a pulse-distortion mode that remains
black-box compatible. The model still optimizes raw pulse parameters, while the
true device internally evaluates a distorted pulse, such as smoothed controls
with a small deterministic memory effect. The optimizer cannot inspect this
distortion. Existing small/medium/large modes remain unchanged for backward
compatibility; the new mode is used by the holdout runner.

### 5. Conservative HPC Sweep

Add a Slurm script for the moderate holdout/device-informed sweep. It should use
no more than 4 CPU cores per task and a low array concurrency such that total
CPU use stays well under the user's 200-core limit. Generated logs and results
must stay under ignored results directories.

## Success Criteria

- Tests prove sealed optimization does not call exact true-device scoring.
- Tests prove holdout rows are labeled and separated from dev rows.
- Tests prove pulse distortion changes true-device query behavior while keeping
  finite-shot/query accounting intact.
- Local fast runner completes and writes device-informed dev/holdout summaries.
- Moderate Slurm job is submitted with conservative CPU settings.
- README, REPORT, PR body, and version ledger explain the stronger black-box
  boundary and the no-real-hardware limitation.

## Non-Goals

- Do not claim real quantum hardware execution.
- Do not replace the existing full CPU sweep already reported.
- Do not force a three-qubit closed-loop calibration.
- Do not stage or publish unrelated files such as `Ion.lock`.
- Do not commit generated results, private machine names, account names,
  hostnames, keys, passwords, or SSH commands.
