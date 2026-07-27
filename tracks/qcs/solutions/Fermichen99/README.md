# Sim-to-Real Quantum Gate Calibration

## Team

| | |
|---|---|
| **Team name** | Fermichen99 |
| **Members** | [@Fermichen99](https://github.com/Fermichen99) |
| **Challenge** | [#113 — Sim-to-Real for Quantum Gates](https://github.com/QuantumBFS/quantum.harness/issues/113) |
| **Track** | Quantum control · differentiable programming |

This is a reproducible, query-counted implementation of the challenge's
three-stage pipeline:

1. optimize a Fourier pulse in a differentiable model;
2. extract its active Hessian directions, either explicitly or with
   Hessian-vector products (HVPs) and a Krylov eigensolver;
3. warm-start a strictly query-only, finite-shot device and calibrate it with
   derivative-free optimization.

The model and device are separate objects. Closed-loop optimizers receive only
one reported scalar infidelity per query. The simulator's exact fidelity is
retained only for offline scoring and is never exposed to the optimizer.

## Main result

The current study asks a geometric question before designing another
optimizer:

> How many leading model-Hessian parameter directions are needed to cover all
> `d²−1=15` true endpoint-generator directions?

For each structural mismatch `ε`, the 15-dimensional right-singular subspace
of the true endpoint Jacobian is compared with the first `k` model-Hessian
eigenvectors. The squared principal cosines are the coverage spectrum. The
smallest cosine gives a worst-generator certificate, and `kτ` is the smallest
`k` for which every generator direction has coverage at least `τ`.

![Required Hessian directions](artifacts/generator_coverage_required_k_vs_epsilon.png)

The formal scan uses 21 values of `ε`, five independent drift directions, and
every integer `k=15,…,40`. At the main 95% threshold:

| `ε` region | Median required `k₉₅` |
|---|---:|
| `ε≤0.10` | 15 |
| `ε=0.15` | 16 |
| `ε=0.20` | 25 |
| `ε=0.25` | 31 |
| `ε=0.30` | 35 |
| `ε=0.40` | 36 |
| `ε=0.50` | 39 |
| `ε≥0.75` | 40 |

For small mismatch, the lost worst-direction coverage follows
`1−cmin(k=15) ≈ 2.06 ε²`; the fitted exponent is 2.000 with log-space
`R²=0.931`. Thus the physical generator count remains 15, while the number of
*model-ranked parameter directions required to cover those generators* grows
from 15 toward the full 40-dimensional pulse space.

The threshold is essential: exact algebraic rank can remain 15 even when one
generator combination has only a tiny projection into the chosen parameter
space. `k₉₅` measures robust worst-direction coverage, not merely nonzero rank.

This is a structural-mismatch result. It does not yet propose a fixed-rank
adaptive optimizer or estimate the subspace through finite-shot queries.

## Noise and invariant checks

![Finite-shot noise boundary](artifacts/success_vs_shots.png)

At `ε=0.3`, the top-15 success rate rose from 0/10 at 4,096 shots/query, to
4/10 at 16,384, and 9/10 at both 65,536 and 262,144. The raw 40-parameter
search reached at most 2/10 in the same sweep. More shots are not free: the
reported artifacts include both query counts and total measurement shots.

![Hessian rank invariant](artifacts/hessian_rank_invariant.png)

The active-rank prediction was checked on two systems:

| Gate | `d` | Pulse parameters | Predicted `d²−1` | Hessian rank | Endpoint-Jacobian rank |
|---|---:|---:|---:|---:|---:|
| single-qubit X | 2 | 20 | 3 | 3 | 3 |
| two-qubit CNOT | 4 | 40 | 15 | 15 | 15 |

The explicit two-qubit Hessian subspace and the HVP/Krylov subspace agree to
numerical precision.

## Reproduce

From the repository root:

```bash
make install jax EXTRA=cpu
uv pip install --python .venv/bin/python \
  -r tracks/qcs/solutions/Fermichen99/requirements.txt

.venv/bin/python tracks/qcs/solutions/Fermichen99/run_calibration.py
.venv/bin/python tracks/qcs/solutions/Fermichen99/run_reachability.py
.venv/bin/python tracks/qcs/solutions/Fermichen99/run_dimension_sweep.py
.venv/bin/python tracks/qcs/solutions/Fermichen99/run_noise_sweep.py
.venv/bin/python tracks/qcs/solutions/Fermichen99/run_invariant_check.py
.venv/bin/python tracks/qcs/solutions/Fermichen99/run_generator_coverage.py

.venv/bin/python -m unittest discover \
  -s tracks/qcs/solutions/Fermichen99/tests -q
```

The scripts write full per-run data under `tracks/qcs/results/`, which is
intentionally gitignored. Compact summaries and figures from the reference run
are committed in [`artifacts/`](artifacts/).

The reference CPU run used Python 3.13.5, JAX 0.7.1, NumPy 2.2.5, SciPy 1.15.3,
and Matplotlib 3.10.3. The complete calibration, reachability, dimension,
noise, and invariant metadata are in the committed `*_run.json` files.

## Source map

| File | Purpose |
|---|---|
| `sim_to_real.py` | dynamics, unitary integrators, model construction, mismatch, strict black-box device |
| `landscapes.py` | Hessian, HVP/Krylov extraction, endpoint Jacobian, subspace diagnostics |
| `optimizers.py` | differentiable diagnostics, COBYQA and SPSA query-only baselines |
| `run_calibration.py` | notebook reproduction and numerical calibration |
| `run_reachability.py` | privileged mismatch/reachability screen |
| `run_black_box.py` | focused simple-baseline comparison |
| `run_dimension_sweep.py` | headline dimension/gap experiment with seeds and error bars |
| `run_noise_sweep.py` | shot-budget experiment |
| `run_invariant_check.py` | `d²−1` check for `d=2` and `d=4` |
| `run_generator_coverage.py` | dense `ε×k` scan of Hessian-direction coverage of all true generators |
| `REPORT.md` | methods, results, interpretation, and limitations |
| `challenge_report.html` | self-contained step-by-step challenge report |

## Scope and honest failure

This submission uses a software black box with drift mismatch
`H₀,true = H₀ + εV`; it does not claim a real-hardware run. The finite-shot
oracle samples the trace fidelity as a binomial probability, which is a useful
controlled noise model but not a complete randomized-benchmarking protocol.

The generator-coverage scan uses exact simulated endpoint Jacobians. It
therefore identifies the geometric number of model-Hessian directions needed,
not the query cost of learning that number on hardware. The reported trend is
checked across five drift directions and three propagation resolutions, but
still uses one base Hamiltonian/control instance.
