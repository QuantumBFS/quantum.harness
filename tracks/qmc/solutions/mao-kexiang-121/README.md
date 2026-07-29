# Polyhedral and Perron-compound sign-free generator supports

## Team

| | |
|---|---|
| **Team name** | Mao-Kexiang |
| **Members** | Kexiang Mao ([@Mao-Kexiang](https://github.com/Mao-Kexiang)) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Find structured fermionic Gaussian-vertex sets with det(I + product exp(A_i)) >= 0 beyond the known split-orthogonal and fixed-metric semigroup principles, and map any survivor to an interacting QMC weight. |
| **Catalog issue** | Addresses #121 - Sign-problem free hunter, released by Lei Wang, Institute of Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/qmc/` — from the issue's `Method: Quantum Monte Carlo` field. |

## Bottom line

This submission reports **substantial progress toward #121, not a claimed closure of the whole research challenge**.

The main analytic candidate is an open, two-orbit family of real 3 x 3 generators whose arbitrary positive-time words have positive determinant weights. The supplied support has an exact obstruction to every common quadratic contraction metric and a proof under internal review of nonembedding in one fixed complex-CAR Wei structure. An S3 Fock-space twirl maps the same twelve vertices to an engineered Hermitian interacting Hamiltonian with an exact determinant-valued continuous-time Gaussian-vertex series expansion; this is not a standard auxiliary-field DQMC formulation.

Two major gaps remain. First, the final A/B family does not yet ship with its own randomized cross-dimension harness, so the survival claim currently rests on the analytic common-norm proof and internal proof audit. Second, the contraction Hamiltonian has a frustration-free vacuum ground state at chemical potential zero, while the finite-occupancy extension factorizes into number-conserving cells with no itinerant intercell hopping. We do not claim a scalable finite-density phase, a production sampler, publication priority, or Hamiltonian-level exclusion of every alternative Hubbard-Stratonovich, fermion-bag, Majorana, Jordan-Wigner, or stoquastic representation.

## 1. Main theorem candidate

For epsilon > 0 and kappa > 0, define

```text
A(epsilon,kappa) =
[ -1-epsilon-kappa     1          -epsilon ]
[       0          -1-kappa          1     ]
[       2              0          -2-kappa ]

S = diag(1,1,-1),     B = S A S,
C = S3 orbit of A union S3 orbit of B.
```

On the open parameter region

```text
epsilon > 0,  kappa > 0,  40 epsilon + 59 kappa < 2,
```

the accompanying proof draft establishes:

1. Every X in C has logarithmic infinity norm mu_infinity(X) = -kappa.  Thus every positive-time word T obeys ||T||_infinity < 1 on the isolated three-mode space and det(I+T) > 0.  Embedded local words obey det(I+T) >= 0.
2. No common H > 0 can satisfy X^T H + H X <= 0 for all X in C.  At epsilon=1/100 and kappa=1/1000, permutation averaging reduces H to I+r ee^T, while A requires r <= -1541/24791 and B requires r >= 1541/42609.
3. The twelve generators span all of M_3(R); the standard-isotypic minor is 162(2 epsilon^3 + epsilon^2 - 4 epsilon + 3), which is positive in the stated region.
4. For odd one-particle dimension and full span, the number-conserving Nambu support cannot be put into Wei's fixed complex-CAR semigroups without inducing the forbidden common H.  A compactness argument also excludes alternate logarithms of this same discrete support for sufficiently small time step.
5. The result is not tied to one decimal matrix.  `main_theorem.md` gives a seven-parameter signed directed-triangle design cone with a nonempty open feasible region.

The determinant proof itself is short: a common induced norm puts every eigenvalue of the real product T in the closed unit disk.  Real eigenvalues contribute nonnegative factors 1+lambda, and nonreal conjugate pairs contribute |1+lambda|^2.

## 2. Interacting physical realization

For X=A or B, define the three-site Fock-space twirl

```text
M_X(tau) = (1/6) sum over sigma in S3 of
           exp[tau c^dagger (P_sigma X P_sigma^T) c].
```

The exterior-power representations of the natural S3 representation are real and multiplicity-free in every three-mode number sector, so M_X is Hermitian.  At the rational interior point and sufficiently small positive tau, both twirls are non-Gaussian and interacting.  Their exact local operator content is

```text
constant + chemical potential + uniform hopping + density interaction
+ correlated hopping + three-body density.
```

For positive couplings, overlapping triangular clusters give

```text
H = - sum over triangles Delta of [g_A M_A,Delta + g_B M_B,Delta].
```

Expanding exp(-beta H) and resolving every twirl insertion into one of the twelve Gaussian orbit vertices gives nonnegative scalar activities and fermion factor det(I + product exp(τ X_j)) >= 0 at arbitrary depth. A sampled orbit vertex need not be Hermitian or a positive operator; Hermiticity belongs to the complete twirl.

This meets the issue's minimum “route to a physical determinant weight” requirement in the broad sense of an exact grand-canonical Gaussian-vertex series. It is not a standard auxiliary-field DQMC decomposition of a two-body model. At chemical potential zero the vacuum minimizes every positive-coupling contraction term; positive chemical potential leaves the certified cone, and canonical weights are not automatically positive.

`finite_density_extension.md` develops a Perron-plus-second-compound criterion that permits one expanding positive mode. Its decoupled D4 cell Hamiltonian has a unique one-particle local ground state at mu=0, and the full cell-factorized fermionic expansion has positive grand-canonical determinant weights. The conserved one-particle-per-cell sector carries qutrit compass terms, but projected qutrit weights, an active low-energy qutrit manifold, and itinerant intercell fermion exchange are not proved sign-free.

## 3. Novelty boundary

Established ingredients include logarithmic norms, common polyhedral Lyapunov functions, cone-preserving matrices, compound matrices, and group twirling.  The candidate contribution is their QMC combination:

- an explicit nonzero-volume arbitrary-depth determinant-positive vertex family;
- exact separation from every common ellipsoidal contraction certificate;
- a full-span odd-dimensional obstruction for the same support against Wei's fixed complex-CAR classes;
- an interacting Hermitian realization using the original safe vertices;
- a separate Perron-compound route and an exact map of its finite-density limitations.

A targeted primary-source audit found no direct QMC use of this common-polyhedral construction or the Perron-plus-compound combination.  That search is not proof of priority.  The real-determinant pseudo-unitary observation in Appendix A of Phys. Rev. X 9, 021022 (2019), the total-positivity route independently submitted in PR #259, and all standard split-orthogonal/Kramers/Majorana/Wei reductions are treated as prior or competing work rather than claimed here.

The one-dimensional total-nonnegative/Jordan-Wigner route was deliberately excluded from this submission because PR #259 already contains it.  See `novelty_audit.md` and `reduction_checklist.md` for the detailed filter.

## 4. Reproducibility and evidence

The committed baseline oracle independently constructs the Fock-space lift of c_i^dagger c_j and checks

```text
Tr_Fock product exp(c^dagger A_i c) = det(I + product exp(A_i)).
```

It includes analytic O(1,1), randomized O(n,n) identity-component positive controls, all four O(1,1) components, the exact rational negative certificate det(I+T)=-4/3 in O^{--}, and the four-site Wang et al. 2015 Hubbard/spin-flip construction.

The code was developed with Python 3.13.9. From the repository root, install the minimal dependencies and run the regression tests with

```bash
python -m pip install -r tracks/qmc/solutions/mao-kexiang-121/requirements.txt
python -m pytest -q tracks/qmc/solutions/mao-kexiang-121/test_sign_problem_hunter.py
```

These team-local tests are not discovered by the repository's default `make test` target. To reproduce the complete preregistered Wang-2015 baseline of 256 configurations at orders 0 through 8, including three independent 256-dimensional Fock checks, use the committed manifest:

```bash
run_dir="$(mktemp -d)"
cp tracks/qmc/solutions/mao-kexiang-121/wang2015_run_template.json "$run_dir/run.json"
python tracks/qmc/solutions/mao-kexiang-121/sign_problem_hunter.py --run-dir "$run_dir"
```

Final A/B-specific randomized validation is not yet included; the earlier A/D/F development harness was excluded as superseded. The arbitrary-word A/B statement currently rests on the analytic common-norm proof and the internal proof audit. No new scientific calculation was run merely to prepare this PR.

## 5. File map

| File | Role |
|---|---|
| [`main_theorem.md`](main_theorem.md) | Open A/B family, exact no-ellipsoid and full-span certificates, fixed-CAR Wei obstruction, and seven-parameter cone. |
| [`physical_realization.md`](physical_realization.md) | Exact S3-twirl operator classification, correlated-hopping tuning, and three-body/vacuum no-go results. |
| [`finite_density_extension.md`](finite_density_extension.md) | Perron-compound theorem, D4 finite-occupancy construction, and explicit non-itinerant limitation. |
| [`novelty_audit.md`](novelty_audit.md) | Closest primary literature and cautious priority language. |
| [`reduction_checklist.md`](reduction_checklist.md) | Split-orthogonal, Kramers, Majorana, Wei, stoquastic, and physical-realizability novelty filter. |
| [`sign_problem_hunter.py`](sign_problem_hunter.py) | Reproducible split-orthogonal/Wang-2015 determinant and independent Fock oracle. |
| [`test_sign_problem_hunter.py`](test_sign_problem_hunter.py) | Exact and numerical baseline regression tests. |
| [`wang2015_run_template.json`](wang2015_run_template.json) | Path-free manifest for the full 256-configuration baseline. |

## 6. Honest completion audit against issue #121

| Issue requirement | Status |
|---|---|
| Rebuild determinant/Fock oracle with positive and exact negative controls | Substantially complete. |
| Validate the known fixed-metric semigroup cone independently | Incomplete in the committed baseline. |
| Map known literature and run a novelty filter | Substantial targeted internal audit; historical priority remains unproved. |
| New structured support with arbitrary-depth proof | Analytic theorem candidate after internal audit; dedicated A/B randomized harness still missing. |
| Interacting physical determinant weight | Exact for an engineered grand-canonical Gaussian-vertex series; not a standard auxiliary-field DQMC formulation and vacuum-limited. |
| Nontrivial scalable finite-density itinerant model and benchmark | Incomplete. |
| Exclude every alternative positive decomposition of the same Hamiltonian | Incomplete and not claimed. |
| Public MathOverflow/arXiv endgame and external review | Not yet done. |

For these reasons this is a non-closing PR that addresses #121. The core matrix question has a serious candidate answer; the strongest physical interpretation of the challenge has not yet been solved.
