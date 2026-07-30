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
| `E(L=0)` | `3.871634914021247` | `3.8716349140212483` |
| `E(L=2)` | `4.003323325986339` | `4.003323325986341` |
| `Delta_2` | `0.1316884119650923` | `0.13168841196509273` |

The absolute gap discrepancy is `4.44e-16`. The reported total gap uncertainty
is `1.414e-12`; it combines the independently sampled MC standard error with
the floating-point projection floor. Each of the ground component and five
excited components uses `20,000` independent samples, with ESS equal to the
sample count.

## Acceptance checklist

| Issue #15 deliverable | Evidence | Status |
| --- | --- | --- |
| Exchange-antisymmetric, SO(3)-equivariant NQS | Shared neural trunk; strict-LLL Slater basis; exact `L` projection; scalar and `D^(2)` finite-rotation tests | Pass |
| `E0`, `E2`, `Delta` with statistical errors | Table above, machine-readable summary, and Attempt 02 journal | Pass |
| `L=2` Casimir | Maximum `|<L^2>-6| = 2.85e-15`; maximum `Var(L^2) = 1.42e-14` | Pass |
| Fivefold `M=-2,...,2` multiplet | Ladder-generated tower; splitting `4.44e-15` | Pass |
| Numerical equivariance check | Particle-swap residual `0`; random SO(3) residual `3.69e-14` | Pass |
| Small-N ED cross-check | Same Hamiltonian and normalization; gap discrepancy `4.44e-16` | Pass |
| Documented code and short report | This file, [Benchmark v0](docs/benchmark-v0.md), source, tests, and journals | Pass |
| Strong-version thermodynamic/chirality result | Not claimed | Extension |

All frozen gates are true: `lll_valid`, `antisymmetry_valid`,
`so3_equivariance_valid`, `l2_casimir_valid`,
`fivefold_multiplet_valid`, `mc_error_valid`, `ed_crosscheck_valid`, and
`reproducible_run_valid`.

## Reproduce the accepted benchmark

Requirements are Python, NumPy, and SciPy. From a clean repository checkout:

```bash
python tracks/qmc/solutions/BOTS-848/run_nqs_benchmark.py \
  --output tracks/qmc/results/BOTS-848-benchmark-v0/run.json \
  --samples 20000
```

The scoped verification suite is:

```bash
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
```

The benchmark implementation entered at commit `e04bc5d`. Its recorded clean
verification was `31 passed in 29.12s`, the CLI exited `0`, the JSON structural
check passed, and stderr was empty. See
[Attempt 02](logs/attempt-02.md) for the full command journal and
[result-summary.json](submission/result-summary.json) for the portable result.

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
- `benchmark_v0/`: Hamiltonian, exact oracle, projected NQS, VMC, and symmetry
  implementation.
- `run_nqs_benchmark.py`: one-command benchmark entry point.
- `tests/`: physics, symmetry, schema, and regression tests.
- `route_d_plus/`: scalable coordinate-space implementation and Slurm gates.
- `docs/` and `logs/`: designs, certificates, resource evidence, and attempt
  journals.
