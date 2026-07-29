# Polyhedral sign-free generator supports beyond fixed metrics

## Team

| | |
|---|---|
| **Team name** | Genshin_Impact |
| **Members** | Kexiang Mao ([@Mao-Kexiang](https://github.com/Mao-Kexiang)) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Find structured Gaussian-vertex sets with det(I+T)>=0 for arbitrary words beyond split-orthogonal and fixed-metric sufficient principles, then realize one as an interacting QMC weight. |
| **Catalog issue** | [QuantumBFS/quantum.harness issue #121](https://github.com/QuantumBFS/quantum.harness/issues/121) |
| **Pull request** | [PR #261](https://github.com/QuantumBFS/quantum.harness/pull/261) |
| **Track** | `tracks/qmc/` |

## Bottom line

This submission supplies all six explicit deliverables of issue #121: independent determinant/Fock oracles and signed controls; a reduction and literature checklist; a new arbitrary-depth structured family with proof and preregistered stress tests; an interacting physical determinant weight; complete reporting; and a public expert-review draft.

The result is an open two-orbit family of real 3 x 3 generators. A common polyhedral norm proves positivity at every depth. Exact certificates exclude every common quadratic contraction metric and the stated fixed, same-dimensional complex-CAR Wei classes. An S3 Fock-space twirl maps the same twelve vertices to a local Hermitian interacting Hamiltonian with an exact positive continuous-time Gaussian-vertex expansion.

The formal run at executable commit [`9fe85a6`](https://github.com/QuantumBFS/quantum.harness/commit/9fe85a6317132983b48c12cbe3628b2da2945a19) passed 224/224 preregistered cells and every exact, twirl, and physical stage. This meets the literal issue submission standard. It does not imply maintainer acceptance, publication priority, exclusion of every alternative representation, a finite-density breakthrough, or publication readiness.

## 1. Main theorem

For epsilon>0 and kappa>0, define

```text
A(epsilon,kappa) =
[ -1-epsilon-kappa     1          -epsilon ]
[       0          -1-kappa          1     ]
[       2              0          -2-kappa ]

S=diag(1,1,-1),  B=SAS,
C=S3 orbit of A union S3 orbit of B.
```

On the open region

```text
epsilon>0,  kappa>0,  40 epsilon+59 kappa<2,
```

[`main_theorem.md`](main_theorem.md) proves:

1. Every X in C has logarithmic infinity norm mu_infinity(X)=-kappa. Every positive-time word is a strict contraction on the isolated three-mode space, so det(I+T)>0; locally embedded words obey det(I+T)>=0 at arbitrary depth.
2. No common H>0 satisfies X^T H+HX<=0 for all X in C. At epsilon=1/100 and kappa=1/1000, A requires r<=-1541/24791 and B requires r>=1541/42609 after permutation averaging.
3. The twelve generators span M_3(R).
4. The number-conserving Nambu support cannot enter the compared fixed, same-dimensional complex-CAR Wei semigroups under one fixed allowed basis change. The statement includes sufficiently small alternate logarithms of the same discrete support.
5. Section 6 gives a seven-parameter signed directed-triangle design cone, so the displayed rational matrix is not an isolated fitted point.

The determinant step is short: eigenvalues of a real contraction lie in the closed unit disk; real eigenvalues contribute 1+lambda>=0 and nonreal conjugate pairs contribute |1+lambda|^2.

## 2. Interacting physical realization

For X=A or B, define

```text
M_X(s)=(1/6) sum_(sigma in S3)
       exp[s c^dagger(P_sigma X P_sigma^T)c].
```

The complete twirl is Hermitian although a resolved Gaussian vertex need not be. At the rational interior point and sufficiently small s>0, both twirls are interacting and non-Gaussian. Positive couplings on overlapping triples define

```text
H_bar=sum_(Delta,X) g_(Delta,X)[I-M_(Delta,X)].
```

Resolving the continuous-time expansion of exp(-beta H_bar) gives nonnegative scalar activities and configuration weight det(I+U_m...U_1)>=0 at every order. The formal four-site benchmark used overlapping triples (1,2,3) and (2,3,4), s=1/10, g_A=g_B=1/4, mu=0, and beta=1/4,1/2,1,2.

All 16,384 sampled physical configurations were nonnegative. Exact diagonalization and the positive Poisson estimator agreed within every preregistered allowance; the minimum sampled determinant was 4.330910819303328. See [`physical_realization.md`](physical_realization.md) and [`verification_record.md`](verification_record.md).

This is a local, spinless, number-conserving, genuinely interacting model and an implementable continuous-time expansion. It is not a standard two-body Hubbard auxiliary-field decomposition. Its mu=0 ground state is the vacuum; positive chemical potential and canonical finite-density positivity remain open.

## 3. Novelty boundary

Established ingredients include logarithmic norms, polyhedral Lyapunov functions, contraction semigroups, compound matrices, cone preservation, and group twirling. The candidate contribution is their QMC combination:

- an explicit nonzero-volume arbitrary-depth determinant-positive family;
- exact separation from every common ellipsoidal contraction certificate;
- a full-span odd-dimensional obstruction for the same support against the stated fixed complex-CAR classes;
- an interacting Hermitian realization using only certified vertices.

A targeted primary-source audit found no direct QMC use of this common-polyhedral construction. Absence of a search hit is not proof of priority. PR #259's total-nonnegative/Jordan-Wigner route and split-orthogonal, Kramers, Majorana, pseudo-unitary, and Wei results are treated as prior or competing mechanisms. See [`novelty_audit.md`](novelty_audit.md) and [`reduction_checklist.md`](reduction_checklist.md).

## 4. Formal verification result

The compact immutable record is [`verification_record.md`](verification_record.md). Full row-level artifacts remain on `t02-server` at

```text
tracks/qmc/results/Genshin_Impact-121/20260730-021845-9fe85a6/
```

That directory also contains the standalone challenge report at
`challenge-report/report.html` and scheduler provenance at `slurm_jobs.json`.
A compact public copy of the formal evidence, excluding the 9.6 MB row-level
sample table and per-cell files, is tracked in
[`formal_run_snapshot/`](formal_run_snapshot/).

| Check | Result |
|---|---|
| Protocol | `ae54430bfb17790c197fabed523138ed6ba3a632881978b5665367e1517a2e20` |
| Cells / core random words | 224/224 pass; 40,320 |
| Candidate A/B words | 35,840/35,840 positive |
| Direct Fock checks | 336; maximum absolute error 5.400124791776761e-13 |
| High-precision rebuilds | 672 |
| Exact-zero controls | 448 expected; 0 unexpected inconclusive |
| Physical Poisson words | 16,384/16,384 nonnegative |
| Total randomized words | 56,704 |
| Exact certificates / twirl / physical benchmark | pass |
| Regression suite | 39 tests pass |

Sampling audits implementation and boundary behavior; it is not the proof. The exact common-norm theorem proves arbitrary-depth positivity, and exact rational certificates audit the separation claims.

## 5. Reproduce

From the repository root:

```bash
python -m pip install -r tracks/qmc/solutions/Genshin_Impact-121/requirements.txt
python -m pytest -q \
  tracks/qmc/solutions/Genshin_Impact-121/test_sign_problem_hunter.py \
  tracks/qmc/solutions/Genshin_Impact-121/test_issue121_verification.py

python tracks/qmc/solutions/Genshin_Impact-121/issue121_verification.py \
  --manifest tracks/qmc/solutions/Genshin_Impact-121/issue121_full_run.json \
  --validate-only

output=tracks/qmc/results/Genshin_Impact-121/REPRODUCE-$(date -u +%Y%m%d-%H%M%S)
python tracks/qmc/solutions/Genshin_Impact-121/issue121_verification.py \
  --manifest tracks/qmc/solutions/Genshin_Impact-121/issue121_full_run.json \
  --output "$output"
sha256sum "$output"/{manifest.json,report.json,report.md,samples.csv,COMPLETE}
```

The runner writes cells atomically, binds resume state to the protocol and environment, and emits COMPLETE only after every stage passes. On `t02-server`, submit the full command as a 1-CPU, 2-GB, no-GPU Slurm job.

## 6. File map

| File | Role |
|---|---|
| [`main_theorem.md`](main_theorem.md) | Open A/B theorem, exact separation, fixed-CAR boundary, and seven-parameter cone. |
| [`physical_realization.md`](physical_realization.md) | S3-twirl Hamiltonian, positive CT expansion, sampler, and benchmark. |
| [`verification_record.md`](verification_record.md) | Formal-run hashes, counts, environment, results, and claim boundary. |
| [`formal_run_snapshot/`](formal_run_snapshot/) | Tracked compact copy of the materialized manifest, formal reports, exact/twirl/physical evidence, Slurm metadata, COMPLETE, and challenge report; the source manifest remains `issue121_full_run.json` and row-level samples remain remote by hash. |
| [`issue121_full_run.json`](issue121_full_run.json) | Preregistered manifest. |
| [`issue121_verification.py`](issue121_verification.py) | Protocol-bound exact, randomized, Fock, twirl, and physical verifier. |
| [`test_issue121_verification.py`](test_issue121_verification.py) | Formal verifier tests. |
| [`sign_problem_hunter.py`](sign_problem_hunter.py) | Independent split-orthogonal/Wang-2015 determinant and Fock oracle. |
| [`test_sign_problem_hunter.py`](test_sign_problem_hunter.py) | Baseline oracle tests. |
| [`novelty_audit.md`](novelty_audit.md) | Primary-source novelty audit and priority boundary. |
| [`reduction_checklist.md`](reduction_checklist.md) | Known-mechanism and physical-realizability filter. |
| [`external_review_draft.md`](external_review_draft.md) | Expert-review draft with permanent source links. |
| [`finite_density_extension.md`](finite_density_extension.md) | Optional Perron-compound extension and non-itinerant limitation. |
| [`wang2015_run_template.json`](wang2015_run_template.json) | Earlier Wang-2015 baseline manifest. |

## 7. Issue #121 completion audit

| Explicit issue gate | Status | Evidence |
|---|---|---|
| 1. Oracle plus known positive/negative anchors | Completed | Independent determinant/Fock identity; O(n,n), four O(1,1) components, exact -4/3 negative anchor, and 336 Fock checks. |
| 2. State-of-art and reduction checklist | Completed | Targeted primary-source audit and split-orthogonal, Kramers, Majorana, Wei, one-dimensional, stoquastic, and physical filters. |
| 3. New arbitrary-depth structure, tests, and proof | Completed | Open A/B theorem; exact proof; 35,840 candidate words over d=3,4,6,8,12 and depths 1-64; exact separation certificates. |
| 4. Interacting physical determinant weight | Completed | Local overlapping-triple H_bar, positive CT expansion, ED/Poisson benchmark, and 16,384 nonnegative physical configurations. |
| 5. Full reporting and reproducibility | Completed | Protocol-bound manifest, hashes, atomic resume, COMPLETE, tracked verification record, and 39 tests. |
| 6. Public endgame draft | Completed as a draft | [`external_review_draft.md`](external_review_draft.md) is ready for expert circulation; it has not been posted to MathOverflow or arXiv. |

These rows mean PR #261 supplies every artifact explicitly requested by issue #121. They do not prejudge maintainer review. Finite-density physics is special credit rather than a hard gate and remains open; priority and independent specialist proof review also remain open.

## 8. Suggested reading order

1. [`main_theorem.md`](main_theorem.md), Sections 1-3: common polyhedral positivity and the no-ellipsoid certificate.
2. `main_theorem.md`, Section 5: the precise fixed-CAR Wei separation and its limits.
3. [`physical_realization.md`](physical_realization.md), Sections 1-4: Fock twirl, CT expansion, sampler, and benchmark.
4. [`verification_record.md`](verification_record.md), then [`issue121_full_run.json`](issue121_full_run.json): registered checks, counts, and hashes.
5. [`novelty_audit.md`](novelty_audit.md) and [`reduction_checklist.md`](reduction_checklist.md): prior art and defensible novelty.
6. [`finite_density_extension.md`](finite_density_extension.md): optional next research direction, not part of the solved hard gate.
