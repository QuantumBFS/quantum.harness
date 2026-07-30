# Challenge #15 submission: symmetric NQS for the chiral graviton

Team **BOTS:848** — Shaojie Tai, Huanjing Gong, Bohan Jia

This directory is our submission for
[Quantum Harness issue #15](https://github.com/QuantumBFS/quantum.harness/issues/15).
It contains a complete `N=6`, `2Q=15` benchmark solution and a separately
identified scalable Route D+ research implementation. All energies below use
`e^2/(epsilon*l_B)` and the pair-only chord-distance Coulomb convention.

## Headline result

The submitted Benchmark v0 candidate uses one shared `tanh` random-feature
network on strict-LLL Slater occupations, sector-specific linear heads, exact
angular-momentum projection, and a ladder-generated `L=2` tower. Independent
categorical VMC sampling is used for the reported estimator.

| Quantity | Candidate | Exact diagonalization |
| --- | ---: | ---: |
| `E(L=0)` | `3.871634914021250 +/- 1.0000000013e-12` | `3.871634914021243` |
| `E(L=2)` | `4.003323325986342 +/- 1.0000000023e-12` | `4.003323325986342` |
| `Delta_2` | `0.13168841196509184 +/- 1.4142135649e-12` | `0.13168841196509895` |

The absolute gap discrepancy is `7.11e-15`. The quoted uncertainties combine
the independently sampled MC standard error with the `1e-12` floating-point
projection floor. Each of the ground component and five excited components
uses `20,000` independent samples, with ESS equal to the sample count. The
complete per-`M` errors are in the
[final result report](docs/benchmark-v0-final-result.md).

## Acceptance checklist

| Issue #15 deliverable | Evidence | Status |
| --- | --- | --- |
| Exchange-antisymmetric, SO(3)-equivariant NQS | Shared neural trunk; strict-LLL Slater basis; exact `L` projection; scalar and `D^(2)` finite-rotation tests | Pass |
| `E0`, `E2`, `Delta` with statistical errors | Table above, machine-readable summary, and Attempt 02 journal | Pass |
| `L=2` Casimir | Maximum `|<L^2>-6| = 4.38e-15`; maximum `Var(L^2) = 4.69e-26` | Pass |
| Fivefold `M=-2,...,2` multiplet | Ladder-generated tower; splitting `2.66e-15` | Pass |
| Numerical equivariance check | Particle-swap residual `0`; random SO(3) residual `2.89e-14` | Pass |
| Small-N ED cross-check | Same Hamiltonian and normalization; gap discrepancy `7.11e-15` | Pass |
| Documented code and short report | This file, [Benchmark v0](docs/benchmark-v0.md), source, tests, and journals | Pass |
| Strong-version thermodynamic/chirality result | Not claimed | Extension |

All frozen gates are true: `lll_valid`, `antisymmetry_valid`,
`so3_equivariance_valid`, `l2_casimir_valid`,
`fivefold_multiplet_valid`, `mc_error_valid`, `ed_crosscheck_valid`, and
`reproducible_run_valid`.

## Reproduce the accepted benchmark

Create a Python 3.11 environment and install the pinned minimal dependencies:

```bash
python3.11 -m pip install \
  -r tracks/qmc/solutions/BOTS-848/benchmark_v0/requirements.txt
```

Then, from a clean repository checkout:

```bash
python tracks/qmc/solutions/BOTS-848/run_nqs_benchmark.py \
  --output tracks/qmc/results/BOTS-848-benchmark-v0/run.json \
  --samples 20000
```

The scoped verification suite is:

```bash
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
```

The benchmark implementation entered the integrated repository at commit
`25582f94364957165916a62265a9755cc72b7add`. The final clean GPU reproduction
at `557cb896ba55def10c1b34bf9eba122ca30eddb7` passed 31 focused tests and all
eight gates on Slurm job `23033264`. See the
[final result](docs/benchmark-v0-final-result.md),
[Attempt 02](logs/attempt-02.md), and
[result-summary.json](submission/result-summary.json).

## Ansatz design

The shared feature map acts on occupation bitstrings in the fixed `N=6`,
`2Q=15` LLL Hilbert space. Projection produces a scalar `L=0` head and one
`L=2,M=0` head; angular-momentum ladder operators generate the other four
components. This makes all five states members of one irrep and one
variational family. In continuous coordinates, the determinant expansion is
strictly antisymmetric. A finite random rotation checks scalar transformation
for `L=0` and Wigner-`D^(2)` mixing for the five-component tower.

The exact projector and Rayleigh-Ritz head optimization make this a valid
small-`N` acceptance solution and regression oracle, but not a beyond-ED
scaling claim.

## Route D+: scalable research solution and current status

The scalable route replaces the exact projector with:

1. a strict-LLL coordinate layer on the Haldane sphere;
2. an analytic Laughlin `L=0` mother and rank-two projected-density
   `Phi_(2M)` mother;
3. normal-ordered rotational-scalar neural dressing shared by ground and
   tower states;
4. continuous-coordinate VMC, multiplet-invariant sampling, real-parameter
   gradients, stochastic reconfiguration, delayed acceptance, and
   hash-addressed Slurm certificates.

Phases 1–5 and Phase 6A are certified on hpccube GPU nodes. The Phase 6A
continuous backend agrees with its proof backend to `3.47e-22`, has LLL
reconstruction error `4.22e-15`, delayed-acceptance correction rate `1.0`,
and an independent schema/hash readback.

The first ED reveal of the frozen three-seed D+0 family is also archived:

- ED: `E0=3.8716349140212514`, `E2=4.003323325986342`,
  `Delta=0.1316884119650905`;
- D+0 mean gap: `0.1416830415985421`;
- absolute gap error: `0.009994629633451574`;
- mean ground fidelity: `0.9974076391890695`;
- mean tower fidelity: `0.8773095598450243`;
- ground/tower span ceilings: `0.9999615444874744` /
  `0.9780601427938913`.

The preregistered diagnosis is **optimization failure**, not capacity failure,
so the capacity action is `keep-D+0`. These D+0 values are research-progress
diagnostics and are not substituted for the passing Benchmark v0 result.
See [Route D+ Phase 7](docs/route-d-plus-phase7-result.md) and the independent
machine-readable certificates in [`submission/`](submission/).

## Submission map

- `SUBMISSION.md`: evaluator-facing report and acceptance matrix.
- `submission/result-summary.json`: portable machine-readable headline result.
- `submission/FINAL_CHECKLIST.md`: exact final PR handoff and claim boundary.
- `submission/PR_BODY.md`: prepared final body for the existing registration PR.
- `benchmark_v0/`: Hamiltonian, exact oracle, projected NQS, VMC, and symmetry
  implementation.
- `run_nqs_benchmark.py`: one-command benchmark entry point.
- `tests/`: physics, symmetry, schema, and regression tests.
- `route_d_plus/`: scalable coordinate-space implementation and Slurm gates.
- `docs/` and `logs/`: designs, certificates, resource evidence, and attempt
  journals.
