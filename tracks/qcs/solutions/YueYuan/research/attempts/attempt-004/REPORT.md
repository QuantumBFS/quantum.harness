# YueYuan Attempt 004 Report

## Summary

Attempt 004 evaluates whether a low-dimensional Hessian subspace extracted from a
differentiable quantum-gate model reduces noisy black-box calibration cost.

## Model

The implementation includes a one-qubit `X` target and a two-qubit `CZ` target with
piecewise-constant controls. Fidelity is phase-insensitive:
`F = |Tr(U_target^dagger U)|^2 / d^2`.

## Method

The model pulse is optimized with JAX gradients. The Hessian at the model optimum
provides candidate subspaces. The true device is queried only through a finite-shot
scalar infidelity interface.

## Baselines

The report compares model-only, full-space Nelder-Mead, random-subspace Nelder-Mead,
and Hessian-subspace Nelder-Mead with shared budgets, seeds, shot counts, and stopping
rules.

## Results

Run `make_figures.py` after a smoke or full sweep to regenerate summary tables and the
seven required figures.

## Verification

Local verification was run with the smoke configuration.

- Attempt-004 tests: passing (`17 passed`).
- YueYuan validator and attempt tests: passing (`37 passed`).
- Validator self-test: passing (`"status": "passed"`).
- Smoke output: `tracks/qcs/results/YueYuan/attempt-004/smoke/`.
- Required figures: generated under `tracks/qcs/results/YueYuan/attempt-004/smoke/figures/`.

The generated files are intentionally ignored by git.

## HPC Verification

HPC verification was not completed in this run. A noninteractive key probe failed
before any remote checkout or job submission, and no password was used. The committed
Slurm scripts are ready for conservative CPU/GPU execution after local tests pass.

## Failure Mode

The large mismatch level introduces rotated error channels. The expected failure
symptom is stagnation or loss of Hessian advantage at too-small `k`.

## Limitations

This is simulated software calibration, not real hardware calibration. Python privacy
enforces the black-box boundary by interface discipline, not by cryptographic isolation.
