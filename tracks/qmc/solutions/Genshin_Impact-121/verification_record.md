# Issue #121 formal verification record

This tracked record summarizes the all-pass formal run without committing the 9.6 MB row-level sample table.

## Identity and provenance

| Field | Value |
|---|---|
| Executable commit | [`9fe85a6317132983b48c12cbe3628b2da2945a19`](https://github.com/QuantumBFS/quantum.harness/commit/9fe85a6317132983b48c12cbe3628b2da2945a19) |
| Pull request | [#261](https://github.com/QuantumBFS/quantum.harness/pull/261) |
| Protocol ID | `ae54430bfb17790c197fabed523138ed6ba3a632881978b5665367e1517a2e20` |
| Remote artifact path | `tracks/qmc/results/Genshin_Impact-121/20260730-021845-9fe85a6/` |
| Challenge report | `tracks/qmc/results/Genshin_Impact-121/20260730-021845-9fe85a6/challenge-report/report.html` |
| Slurm metadata | `tracks/qmc/results/Genshin_Impact-121/20260730-021845-9fe85a6/slurm_jobs.json` |
| Tracked compact snapshot | [`formal_run_snapshot/`](formal_run_snapshot/) |
| Pilot / full / audit Slurm jobs | `42169 / 42171 / 42173` |
| Formal status | `pass`; 224/224 cells; COMPLETE present |

The run used Python 3.13.9, NumPy 2.5.1, SciPy 1.18.0, and mpmath 1.4.1 on a `t02-server` Slurm CPU job with 1 CPU, 2048 MB, no GPU, and a 20-minute limit. Base seed: `1212026`.

## Content hashes

| Object | SHA256 |
|---|---|
| Source manifest `issue121_full_run.json` | `17493ccc50f7979eff41b2308f6946dc48f1830036e0447b75db8b4f0ea2bbb1` |
| Canonical manifest protocol hash | `7a04a1e9a4293e85f47ddf4901ae8b20e7b034d7ee50b9d3e8317f805b2f4b12` |
| Materialized `manifest.json` | `d2fb2be0d2cb179ecf77036683c1c3d50283a28bcfa0b458859d910751f2016e` |
| Verifier `issue121_verification.py` | `e566f1a0f300d5201a354cfcd3c45b022631ac3175d98af3fa3b898c954993c4` |
| Independent support `sign_problem_hunter.py` | `fea156818fafdfc9635fb9e7c797470aa34758d82a24e69b6dd3b62d2e04f780` |
| `run.json` | `68336dcafe9f5cf130ddb41d983c9bc83dede8dfcdb9eddeb29e3be9bf47521f` |
| `report.json` | `52c8fb5419d2fdf463b4a56643f63de216aa45ac73b9fe46d149da9eb27390be` |
| `report.md` | `727f5f0c54cc4b277a19503f5c2f865249c09f317c5251dc8c2b8f579c4fb8a9` |
| `samples.csv` (40,320 rows; not tracked) | `27a81a5400780b1851f031a725926cf964da7b0b97e27a4b5acde7fd599711a7` |
| `exact_certificates.json` | `4276fd469722894796cd4152c2f11f8cb3b977ee8dcc867062a48c57dec79034` |
| `twirl_checks.json` | `1234ee7b8e419b404c0cd667ea1cce7d26a12d72bff4a4a4676ef33a0da2b56a` |
| `physical_benchmark.json` | `5b9029d962c6db0b3768a93d5e9512bcd607883c9cf052d8dbd7c2ecdea6c75a` |
| `COMPLETE` | `7e2499c8b8a43db184444f3d64926c2663ef8d199f2b59259d9f173c31c4b200` |

The COMPLETE payload independently records the same protocol and the report JSON/Markdown hashes. The tracked [`formal_run_snapshot/`](formal_run_snapshot/) carries the materialized manifest, compact reports, and certificates unchanged; the source manifest remains [`issue121_full_run.json`](issue121_full_run.json). The 9.6 MB `samples.csv` and per-cell artifacts remain only in the durable remote run directory; their row count and SHA256 are recorded above.

## Preregistered workload and classifications

| Stage | Cells | Random words | Result |
|---|---:|---:|---|
| A/B candidate: 4 parameter regimes x d=3,4,6,8,12 x depths 1,2,4,8,16,32,64 | 140 | 35,840 | 35,840 positive; 0 negative or unexpected inconclusive |
| Split-orthogonal O(n,n), n=1,...,4 | 28 | 1,792 | pass |
| Fixed-metric Wei semigroup, n=1,...,4 | 28 | 1,792 | pass |
| Four O(1,1) components | 28 | 896 | pass; 448 expected exact-zero mixed-component controls |
| Core total | 224 | 40,320 | pass |
| Four-site physical Poisson strings, 4,096 per beta | - | 16,384 | all nonnegative |
| Total randomized words including physical | - | 56,704 | pass |

The candidate regimes were center, near the proved boundary, kappa approaching zero, and Dirichlet-random points in the open triangle. The run performed 672 high-precision rebuilds. All 448 raw inconclusive determinant classifications were preregistered exact-zero O(1,1) controls; unexpected inconclusive count was zero.

The independent direct-Fock oracle performed 336 checks through d=8. Maximum absolute determinant/Fock error was `5.400124791776761e-13`. Exact Fraction certificates, the four twirl interaction/non-Gaussian certificates, and all known signed anchors passed. The regression suite passed 39 tests.

## Four-site interacting benchmark

Setup: spinless number-conserving Fock space, four open sites, overlapping triples (1,2,3) and (2,3,4), epsilon=1/100, kappa=1/1000, vertex strength s=1/10, g_A=g_B=1/4, chemical potential mu=0.

| beta | Exact ED Z_bar | Poisson absolute error | Registered allowance |
|---:|---:|---:|---:|
| 1/4 | 15.316353408389649 | 0.02808869231030009 | 0.1727116598757571 |
| 1/2 | 14.669103080374773 | 0.03512955219626335 | 0.2233055507021328 |
| 1 | 13.475392271305402 | 0.02453568366674652 | 0.2857508015621753 |
| 2 | 11.439331388535233 | 0.0461209100548885 | 0.33059523654337436 |

All 16,384 sampled physical configurations were nonnegative. The overall minimum sampled determinant weight was `4.330910819303328`. The shifted Hamiltonian had minimum eigenvalue `4.440892098500626e-16` and Frobenius hermiticity residual `1.7216638914240724e-17`. Exact 16-dimensional diagonalization, deterministic shifted-series reconstruction, determinant/Fock equality, and the normalized positive Poisson estimator all passed their registered tolerances.

## Reproduce

From the repository root:

```bash
python -m pip install -r tracks/qmc/solutions/Genshin_Impact-121/requirements.txt
python -m pytest -q \
  tracks/qmc/solutions/Genshin_Impact-121/test_sign_problem_hunter.py \
  tracks/qmc/solutions/Genshin_Impact-121/test_issue121_verification.py

output=tracks/qmc/results/Genshin_Impact-121/REPRODUCE-$(date -u +%Y%m%d-%H%M%S)
python tracks/qmc/solutions/Genshin_Impact-121/issue121_verification.py \
  --manifest tracks/qmc/solutions/Genshin_Impact-121/issue121_full_run.json \
  --output "$output"
sha256sum "$output"/{manifest.json,report.json,report.md,samples.csv,COMPLETE}
```

For the full run on `t02-server`, submit the runner as a 1-CPU, 2-GB, no-GPU Slurm job. The output is atomic and resumable, and COMPLETE is written only after all cells and auxiliary stages pass.

## Claim boundary

This record verifies reproducibility of the preregistered implementation checks. Random sampling is not the arbitrary-depth proof; the common-polyhedral-norm theorem supplies that proof. Passing does not prove literature priority, exclude ancillas or every alternative Hubbard-Stratonovich/fermion-bag/Jordan-Wigner/stoquastic representation, establish a finite-density sign-free phase, guarantee efficient autocorrelation, imply publication readiness, or constitute maintainer acceptance of issue #121.
