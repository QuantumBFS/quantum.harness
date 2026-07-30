## Team

| | |
|---|---|
| **Team name** | BOTS:848 |
| **Members** | Shaojie Tai, Huanjing Gong, Bohan Jia |

## Challenge

Addresses #15: construct an exchange-antisymmetric, SO(3)-equivariant neural
quantum state for the `nu=1/3` chiral graviton and compute
`Delta_2 = E(L=2) - E(L=0)`.

## Headline result

For `N=6`, `2Q=15` on the Haldane sphere under the strict-LLL chord-distance
Coulomb interaction:

| Quantity | NQS/VMC | Exact diagonalization |
| --- | ---: | ---: |
| `E0` | `3.871634914021250 +/- 1.0000000013e-12` | `3.871634914021243` |
| `E2` | `4.003323325986342 +/- 1.0000000023e-12` | `4.003323325986342` |
| `Delta_2` | `0.13168841196509184 +/- 1.4142135649e-12` | `0.13168841196509895` |

The absolute gap discrepancy is `7.11e-15`. Each of the ground component and
five `L=2` components uses 20,000 independent determinant samples.

## Symmetry certificate

- particle-swap residual: `0`;
- finite SO(3) rotation residual: `2.89e-14`;
- maximum `|<L^2>-6|`: `4.38e-15`;
- maximum `Var(L^2)`: `4.69e-26`;
- fivefold multiplet splitting: `2.66e-15`;
- all eight Benchmark v0 gates pass.

## What is implemented

The acceptance candidate uses a shared width-128 `tanh` feature trunk on
strict-LLL occupations, sector-specific linear heads, exact `L^2` projection,
and a ladder-generated five-component `L=2` tower. The submitted code includes
the Hamiltonian, ED oracle, NQS/VMC estimator, numerical symmetry tests,
focused tests, pinned dependencies, and a GPU Slurm runner.

Route D+ is the scalable research contribution: a strict-LLL coordinate layer,
analytic Laughlin and quadrupole mothers, normal-ordered rotational-scalar
neural dressing, continuous-coordinate VMC/SR, delayed acceptance, and
hash-addressed Slurm certificates. Phases 1–5 and 6A are certified. Its first
three-seed ED reveal is honestly classified as an optimization failure:
ground/tower fidelities `0.99741/0.87731`, gap error `0.009995`, and span
ceilings `0.99996/0.97806`.

The other merged scalable routes are preserved with explicit claim boundaries:

| Route | Integrated status | Scientific status |
| --- | --- | --- |
| A — occupation autoregressive | Reviewed implementation and N=8 smoke path; formal three-seed training not run | No checkpoint or final result; route not frozen |
| C — strict-LLL Operator-NQS | Exact one-layer implementation and partial production traces | Cut off before checkpoint; diagnostics only |
| D+ — coordinate VMC/SR | Phases 1–5 and 6A certified; Phase 7/readback complete | Optimization failure; not used for the acceptance claim |

## Review package

- [Submission report](https://github.com/TensorSpicyJ/quantum.harness/blob/challenge/qmc-chiral-graviton/tracks/qmc/solutions/BOTS-848/SUBMISSION.md)
- [Final Benchmark v0 result](https://github.com/TensorSpicyJ/quantum.harness/blob/challenge/qmc-chiral-graviton/tracks/qmc/solutions/BOTS-848/docs/benchmark-v0-final-result.md)
- [Portable machine-readable summary](https://github.com/TensorSpicyJ/quantum.harness/blob/challenge/qmc-chiral-graviton/tracks/qmc/solutions/BOTS-848/submission/result-summary.json)
- [Route A honest closeout](https://github.com/TensorSpicyJ/quantum.harness/blob/challenge/qmc-chiral-graviton/tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a05.md)
- [Route C honest closeout](https://github.com/TensorSpicyJ/quantum.harness/blob/challenge/qmc-chiral-graviton/tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a03.md)
- [Route D+ Phase 7 result](https://github.com/TensorSpicyJ/quantum.harness/blob/challenge/qmc-chiral-graviton/tracks/qmc/solutions/BOTS-848/docs/route-d-plus-phase7-result.md)
- [Final handoff checklist](https://github.com/TensorSpicyJ/quantum.harness/blob/challenge/qmc-chiral-graviton/tracks/qmc/solutions/BOTS-848/submission/FINAL_CHECKLIST.md)

Clean GPU reproduction: Slurm `23033264`, source `557cb89`, 31 focused tests,
`run.json` SHA-256 `62a6d0eec15b34f12563076d9f18b055a6831856009cee1fadfa2c4b7be8298d`.
The offline challenge report was rendered on Slurm `23033430`; SHA-256
`cb97ce0b030d79d7a696a9e200b2e20d08166355ad518c445bd34001416d5501`.

## Reproduce

```bash
python3.11 -m pip install \
  -r tracks/qmc/solutions/BOTS-848/benchmark_v0/requirements.txt
python tracks/qmc/solutions/BOTS-848/run_nqs_benchmark.py \
  --output tracks/qmc/results/BOTS-848-benchmark-v0/run.json \
  --samples 20000
```

The exact-projector candidate is a valid small-`N` acceptance solution, not a
beyond-ED claim. Thermodynamic extrapolation and chirality decomposition are
not claimed.
