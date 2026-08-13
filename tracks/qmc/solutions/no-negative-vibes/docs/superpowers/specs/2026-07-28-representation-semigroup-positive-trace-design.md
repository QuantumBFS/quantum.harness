# Representation–semigroup–positive-trace discovery design

Date: 2026-07-28

Status: written design for collaborator review

Owner: Zibo (`work/zibo/representation-cones`)

Challenge: [Quantum Harness #121](https://github.com/QuantumBFS/quantum.harness/issues/121)

## 1. Objective and non-negotiable completion criteria

The project will search for a new structured family of auxiliary-field
generators whose arbitrary words have nonnegative fermionic weight. A result is
challenge-complete only if all of the following are present:

1. a precise matrix or Fock/Spin representation class;
2. a human-readable arbitrary-depth positivity proof;
3. exact certificates for every claimed counterexample;
4. a written reduction audit against split orthogonal, contraction-semigroup,
   Kramers, Majorana-reflection/MTR, flavor-doubling, total-nonnegative (TN),
   stoquastic/Jordan–Wigner, and block-triangular mechanisms;
5. a local interacting Hamiltonian and a positive-coefficient
   Hubbard–Stratonovich (HS) or Gaussian-branch decomposition;
6. a reproducible implementation, protocols, compact fixtures, and tests;
7. a paper draft that states both positive and negative results without
   promoting numerical survival to a theorem.

The organizer-facing branch and PR are not part of this design. They may only
be updated in a separately approved publication step.

## 2. Baseline and deduplication boundary

The common baseline is merge commit `04e72bd`. It includes the teammate's
rigorous odd-order positive-monomial and block-TN results, 192,000 determinant
weights, 640 parity-resolved Majorana histories, four falsified relaxations,
and 199 passing solution tests.

This branch will not rescan those families. It claims three different questions:

- whether a non-induced four-mode exterior/Fock cone can survive overlapping
  local clusters;
- whether that representation cone can generate a positive HS gate for a
  genuinely interacting local Hamiltonian;
- whether simultaneous vector and two half-spin positivity under `D4`
  triality yields branch-safe information beyond the already closed split
  `SO(4,4)` determinant mechanism.

The proposal ledger and individual candidate cards are the authoritative claim
records.

## 3. Unifying mathematical framework

### 3.1 Number-conserving identity

For a one-particle propagator `B` on `V`,

```text
Gamma(B) = direct_sum_k Lambda^k(B)
Tr_F Gamma(B) = sum_k Tr Lambda^k(B) = det(I + B).
```

Thus a sufficient condition is not fundamentally “positive eigenvalues.” It
is the existence of one fixed, layer-independent representation basis in which
every allowed propagator belongs to a multiplicatively closed semigroup whose
trace is nonnegative.

For fixed real invertible transforms `T_k`, define

```text
C(T_*) = {
  A : T_k A^[k] T_k^(-1) is real Metzler for every k = 0,...,n
}.
```

Here `A^[k]` is the additive compound. If every time slice lies in the same
`C(T_*)`, then

```text
T_k exp(A_l)^(k) T_k^(-1)
  = exp(T_k A_l^[k] T_k^(-1))
```

is entrywise nonnegative. Products remain entrywise nonnegative, so every
sector trace and their sum are nonnegative. The transforms must be fixed
across time slices and fields, real in the asserted positive basis, and include
all sectors. Layer-dependent cones are explicitly excluded.

### 3.2 General triplet

The common abstraction is a **representation–semigroup–positive-trace
triplet**

```text
(rho, S, tau)
```

with:

- `rho` a physically correct representation, including the actual Spin lift
  when pairing is present;
- `S` a semigroup closed under every allowed time-slice product;
- `tau` the physical determinant, Fock trace, parity trace, or Pfaffian branch,
  proved nonnegative on `S`.

Exterior-sector Metzler cones, Fock-basis cones, CP-semigroup cones, and
projected positive faces fit this language. Spectral-pairing/topological
mechanisms remain separate modules; the design does not pretend they are all
simplex-cone positivity.

### 3.3 What counts as new

Independent sector transforms first have genuine freedom at `n=4`, `k=2`.
Non-inducedness is necessary but not sufficient. A publishable mechanism must
also:

- survive at least two overlapping clusters under one global transform;
- contain two noncommuting physical rays;
- escape common single-particle gauges and known bilinear-form cones;
- retain a correct parity/Spin branch;
- yield a positive local HS dictionary.

The four-mode Klein–Hodge transform is therefore a seed, not a discovery.

## 4. Research architecture

The work follows a counterexample-guided loop:

```text
proposal card
  -> exact representation compiler
  -> LP/SDP or symbolic feasibility
  -> adversarial word oracle
  -> exact reconstruction or Farkas/separation certificate
  -> known-mechanism audit
  -> target-first HS construction
  -> arbitrary-depth proof
  -> paper claim
```

Every arrow leaves a versioned trace:

- `PROPOSAL_LEDGER.md` records hypotheses and falsifiable predictions;
- `EXPERIMENT_LOG.md` records every completed experiment, successful or not;
- protocol directories record machine-readable parameters and provenance;
- compact JSON fixtures record exact or reconstructed certificates;
- tests replay every fixture;
- `RESEARCH_OPERATIONS.md` records reusable operational lessons.

A scientific experiment is complete only after its log entry, code/config
commit, and push. Large raw arrays remain outside Git; summaries, seeds,
manifests, counterexamples, and hashes are committed.

## 5. Research package R01: overlapping Klein/Fock circuit cone

### 5.1 Hypothesis

Let `u_K` act as the fixed Klein–Hodge basis change in the two-particle sector
of four complex modes and as the identity in the other number sectors. On six
modes define

```text
U_6 = u_(3456) u_(1234).
```

The falsifiable hypothesis is that there exists a real local quadratic BdG
generator `Q` with a genuine cross-cluster term such that both parity blocks of

```text
U_6 Q U_6^(-1)
```

are Metzler. The useful form of the hypothesis additionally requires two
noncommuting feasible rays and a support graph containing a loop or degree-3
vertex.

### 5.2 Compiler and feasibility problem

The exact compiler will provide:

1. Jordan–Wigner creation/annihilation matrices;
2. real number-conserving and BdG quadratic operator bases;
3. exact four-mode Klein–Hodge gates and their six/eight-mode embeddings;
4. parity-block extraction;
5. a linear inequality matrix for every transformed off-diagonal entry.

The cone is homogeneous, so the zero solution is removed by enumerating a
cross-cluster anchor coefficient and fixing it to `+1` or `-1`. Coefficients
receive finite box bounds only for numerical conditioning; feasibility is
rechecked without interpreting the box as physics. A relative-interior margin
is maximized only over inequality rows not identically zero on the constrained
linear span. This avoids incorrectly demanding strict positivity at structural
zeros.

### 5.3 Escalation ladder

1. `N=4` reproduces the exact Klein–Hodge seed.
2. `N=6` tests two plaquettes overlapping in two modes.
3. If and only if `N=6` has a certified cross-cluster survivor, `N=8` tests
   open and periodic brickwork at depths one to three.
4. Word depths `2..12` and adversarial noncommuting rays audit the
   implementation; they do not replace the cone proof.

### 5.4 Exact and novelty checks

Survivors are reconstructed over `Q(sqrt(2))` or rationals. Failed
architectures are upgraded to a rational/algebraic Farkas certificate when
possible. Every survivor is checked for:

- induced exterior transformation via Plücker/decomposability tests;
- diagonal Fock gauge and GF(2) sign-coboundary solutions;
- exchange-loop holonomy and open-path Jordan–Wigner reduction;
- common split metric, contraction metric, Kramers, Majorana reflection, and
  MTR constraints;
- block diagonalization and disconnected-cluster support.

### 5.5 Stop and success conditions

Stop the architecture when an exact dual certificate forces every
cross-cluster coefficient to zero or every feasible support to an open
path/disconnected block. Record this as a no-go theorem.

Promote it only when there is an exact cross-cluster cone with two
noncommuting rays, a shared global transform, nontrivial exchange topology,
and no known reduction.

## 6. Research package R02: positive local HS cone

### 6.1 Physical target

Work target-first on a fixed four-mode plaquette. The target family may include
anisotropic hopping, explicit pairing, density interaction, chemical potential,
and ring exchange:

```text
h_X =
  - sum_(ij) t_ij (c_i^dag c_j + h.c.)
  - Delta (P+ + P-)
  + V (n_1 - n_3)(n_2 - n_4)
  - mu sum_i n_i
  + J_ring (c_1^dag c_2 c_3^dag c_4 + h.c.).
```

At least one successful point must leave the half-filled bipartite template,
for example by nonzero `mu`, explicit pairing, or ring exchange.

### 6.2 Allowed branches

The initial branch cone is the four-mode Klein–Spinor cone:

```text
Q = dGamma(A) + u P+ + v P-
```

where `A` lies in the exact Klein–Hodge cone and the fixed even/odd Fock
transforms make both parity blocks Metzler. Hermitian slices require the
appropriate adjoint relation, such as `A=A^dag` and `u=v`; individual HS
branches may be non-Hermitian only when the total local gate is Hermitian
positive definite.

Two positive constructions are tested:

```text
E_X(dt) = sum_s lambda_s(dt) exp(Q_s(dt)),  lambda_s >= 0,
```

and the dagger-stable Gram form

```text
R(dt) = sum_r a_r(dt) exp(Q_r(dt)),
E_X(dt) = epsilon(dt) I + R(dt)^dag R(dt).
```

If a product lacks a single structured logarithm, it remains a fixed-length
Gaussian micro-word; no arbitrary dense global logarithm is introduced.

### 6.3 Small-time gate matching

Interaction generation is tested correctly at small time. Symmetric branches
may scale as

```text
Q_s(dt) = sqrt(dt) X_s + dt Y_s + ...
```

so cancellation of `sqrt(dt)` terms leaves quadratic squares at order `dt`.
The first feasibility test matches:

```text
E_X(0) = I,
-d E_X / d(dt) at 0 = h_X,
```

including quartic operator coefficients. A first-order ansatz containing only
`O(dt)` quadratic exponents is rejected as incapable of generating an
interaction. Only after tangent/moment feasibility will nonlinear finite-`dt`
membership be attempted.

### 6.4 Physical acceptance criteria

A physical success requires:

- nonnegative coefficients on an interval `0 < dt < dt_0`, not one isolated
  fitted point;
- exact or analytically controlled gate equality;
- a common sign-free branch certificate for all lattice placements;
- positive scalar auxiliary-field prefactors;
- bounded cluster support and an explicit body-order expansion of
  `-log(E_X)/dt`;
- a tiling/Trotter prescription whose overlapping gates share one global
  certificate.

An exact Hermitian separating functional is a publishable negative outcome if
the target lies outside the allowed Gaussian cone hull.

## 7. Research package R03: branch-safe `D4` triality

This is a cheap secondary audit, not the main determinant claim. In a rational
Chevalley/Clifford realization, impose simultaneous Metzler inequalities on
the vector and both half-spin representations of `so(8)` after fixed transforms.

The search must force:

- nonzero pairing;
- two noncommuting roots;
- a plaquette/loop support mask;
- exclusion of the number-conserving `gl(4)` Levi.

The teammate already showed that the ordinary `D4` simple-root family lies in
known split `SO(4,4)`. Therefore a vector-level determinant result alone is
automatically a known reduction. R03 advances only if the two spinor
representations give a new, convention-stable parity/Pfaffian branch theorem
or a new physical HS dictionary. Otherwise the expected deliverable is a
Farkas/symbolic no-go identifying the surviving Levi/Borel/split cone.

## 8. Deferred reserve directions

The following are not implemented in the first plan:

- sector `C*`/CP-generator cones;
- gauge/ancilla projected positive faces;
- general signed compound cones;
- unrestricted nonlinear searches over arbitrary Fock transforms.

They remain reserve proposals because R01 provides a cheaper scalability
decision and R02 directly tests the physical bottleneck. A reserve direction
needs its own candidate card before work begins.

## 9. Compute and data flow

### WSL worker

The verified WSL worker has 16 logical CPUs and 31 GiB RAM. It runs unit tests,
exact/symbolic construction, small LPs, and smoke scans with:

```text
workers = 14
OMP_NUM_THREADS = MKL_NUM_THREADS = OPENBLAS_NUM_THREADS = 1
```

### CPU worker

The CPU worker is reachable only through WSL. Its scheduler and resource count
must be probed before use. It will use:

```text
workers = max(1, logical_cpus - 2)
BLAS threads per worker = 1
```

No large scan is submitted before its generator passes local tests and a
small deterministic smoke cell. Parameter cells are disjoint and resumable.
The two machines receive disjoint protocol cell ranges or independent
verification seeds, never duplicate production work.

### Reproducibility

Every run records:

- proposal and experiment IDs;
- source commit;
- protocol version and full parameter axes;
- deterministic seed derivation;
- Python and dependency versions;
- host role, logical CPU count, worker count, and BLAS limits;
- start/end time, exit status, sample counts, anomalies, and output hashes.

Raw output is not committed when large. A compact summary, manifest, exact
certificate, and experiment-log entry are committed and pushed immediately
after interpretation.

## 10. Testing and error handling

Implementation follows test-first development:

- exact CAR/Jordan–Wigner identities;
- additive/multiplicative compound identities;
- Klein transform and parity-block fixtures;
- LP inequality compilation against direct matrices;
- positive and deliberately negative Metzler controls;
- exact certificate replay;
- Spin-lift branch controls, including a `2 pi` rotation;
- deterministic protocol partitioning and resume behavior.

Numerical policies:

- a negative float is not a counterexample until high-precision and exact
  reconstruction succeed;
- near-zero and ill-conditioned weights are `uncertain`, never evidence;
- LP feasibility is rechecked from the returned primal residual;
- exact dual certificates are preferred for no-go claims;
- a randomized zero-failure run is reported only as bounded survival.

## 11. Deliverable sequence

1. Commit candidate cards, ledgers, and this design.
2. Build and verify the exact representation/LP core.
3. Close R01 at `N=6` as survivor or no-go before any wide `N=8` scan.
4. In parallel after the shared core exists, run R02 tangent HS feasibility
   and R03 triality LP.
5. Allocate the CPU worker only to surviving, protocolized parameter axes.
6. Convert every terminal outcome into a proof/certificate and reduction
   audit.
7. Develop the best physically viable branch into a lattice model,
   reproducible QMC formulation, and complete paper draft.

The design intentionally optimizes for sharp conclusions. An exact
overlapping-cluster no-go, an HS separation theorem, or a triality reduction
is retained as paper-grade evidence even if that particular candidate fails.

## 12. Implementation-plan boundaries

This design contains three research packages, but it is not one monolithic
coding plan.

- Plan A covers the shared exact representation/LP core and closes the
  six-mode stage of R01.
- Plan B starts after Plan A's representation interfaces are stable and covers
  R02 small-time HS moment feasibility.
- Plan C may run in parallel with Plan B and covers the independent R03
  Chevalley/triality compiler and LP audit.
- An `N=8` production scan receives a separate plan only if R01 survives
  `N=6`; no plan is written for a disproved branch.

This boundary keeps each plan reviewable and prevents speculative compute from
getting ahead of exact low-dimensional evidence.
