# Validator Goal

The YueYuan challenge #113 validator accepts a candidate only when the candidate demonstrates Hessian-guided sim-to-real gate calibration on a simulated two-qubit CZ device with finite-shot noisy fidelity estimates.

## Primary Metric

Median true-device oracle queries to reach exact true infidelity `<= 1e-3` over seeds `0, 1, 2, 3, 4`.

## Required Comparison

`hessian_subspace_nelder_mead` must use at least `2x` fewer median queries than `full_raw_nelder_mead` on the headline `two_qubit_cz_minimal` instance. The candidate must also report `random_subspace_nelder_mead` as a dimensionality control.

## Required Sweeps

- `k`: include `0`, `3`, `8`, `15`, `24`, and full raw dimension when allowed.
- Model-truth gap: include at least two nonzero perturbation sizes.
- Shots: use equal shots per query for all compared methods in a cell.

## Guard Rejections

- Reject if final exact true infidelity is above `1e-3`.
- Reject if stopping is based only on noisy fidelity without exact final check.
- Reject if method manifests use unequal initial pulses, query budgets, seeds, stopping rules, or optimizer families.
- Reject if candidate code reads true-device private fields, true gradients, true Hessians, holdout labels, network resources, or files outside the allowed candidate/output roots.
- Reject if no too-small-`k` failure or plateau is reported.

## Confirmed Validation Method

- Public development instances live in `research/benchmark/dev/`.
- Sealed holdout instances live in `research/benchmark/private/` and are gitignored.
- Holdout query budget: one aggregate holdout query per three reflection cycles.
- Per-attempt wall-clock budget: `300` seconds, enforced by the validator process.
- Environment: fallback local Python 3.11 subprocess sandbox because Docker is not installed on this machine.
- Negative controls: `cheater`, `wrong-answer`, `timeout`, `env-escape`, `lucky-noisy-fidelity`, `weak-baseline`, `cherry-picked-k`, `one-seed`, and `too-easy-gap`.
