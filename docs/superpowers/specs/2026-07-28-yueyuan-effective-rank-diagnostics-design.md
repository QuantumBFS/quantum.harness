# YueYuan Effective-Rank Diagnostics Design

## Goal

Add explicit Hessian effective-dimension evidence to attempt 004 so the challenge
claim does not rely only on the benchmark ranks `d^2 - 1`.

## Context

Challenge #113 asks the solution to determine effective dimension from the model
Hessian spectrum rather than assuming the rank is exactly `d^2 - 1`. Attempt 004
already computes Hessian spectra and has an `effective_rank()` helper, but the
generated artifacts currently emphasize eigenvalue plots and benchmark `k`
values. Reviewers could reasonably ask where the measured effective dimension is
recorded.

## Approach

Add a small spectrum-diagnostics path that summarizes each saved Hessian spectrum
and aggregates the result into machine-readable tables. The diagnostics should
include:

- measured effective rank above an absolute eigenvalue threshold;
- benchmark rank from the system definition;
- total absolute curvature;
- fraction of absolute curvature captured at benchmark rank;
- minimum `k` needed to capture 90%, 95%, and 99% of absolute curvature.

The feature stays analytical. It should not change optimizer behavior, query
budgets, or existing run records.

## Files

- `hessian.py`: add reusable helpers for curvature fractions and minimum
  curvature-covering `k`.
- `experiments.py`: include effective-rank metadata in each
  `hessian_spectra.json` entry.
- `analysis.py`: write a new `spectrum_summary.csv` table from saved spectra.
- `plotting.py`: keep calling `analysis.write_summary_tables()` so the new table
  is generated with existing figure runs.
- `test_attempt_004_hessian.py`: test the new helper logic on deterministic
  spectra.
- `test_attempt_004_smoke.py`: assert the smoke figure/table path writes
  `spectrum_summary.csv` with the new fields.
- `REPORT.md` and `README.md`: explain that measured effective dimension is now
  surfaced explicitly and how it supports the checklist.

## Validation

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py --fast --out /tmp/yueyuan-attempt004-candidate.json
```

Also run a private-marker scan over committed solution and docs paths before
publishing the PR update.

## Non-Goals

- Do not run a new large Slurm sweep for this pass.
- Do not tune or change the reported optimizer results.
- Do not claim the hard two-qubit large-gap case is solved.
- Do not add any private account, hostname, SSH, or credential details.
