# Oddcycle local-Hamiltonian portfolio design

Date: 2026-07-30

Owner: Zibo (`work/zibo/representation-cones`)

Starting checkpoint:
`d69a0d357cb756f7ffa240b974002edf730c396e`

## Objective

Use the already certified four-letter oddcycle alphabet

```text
A = {B0, B0.T, B1, B1.T}
B0 = B(1/1000, 1, 1)
B1 = B(4/5,    1, 1)
```

to construct a portfolio of Hermitian physical Hamiltonians with
positive-coefficient Gaussian auxiliary-field decompositions.  The main target
is an exact, geometrically local, interacting Hamiltonian that is not merely a
fixed-basis stoquastic/TN reformulation.

The arbitrary-word determinant theorem and its exact oracle are frozen.  This
work must not repeat the completed 12,325-cell frontier scan, dual ranking,
top-five promotion, cell-4321 robustness run, final certificate, or
Majorana/Wei audit.

## Existing baseline and gap

Two exact reverse maps already exist.

1. For one transpose pair,

   ```text
   H = -q [Gamma(B) + Gamma(B.T)], q > 0,
   ```

   is Hermitian and has a positive two-branch continuous-time expansion.  It is
   generally nonlocal and may contain up to five-body terms.

2. For the final four-letter alphabet,

   ```text
   T = 37 I
       + Gamma(B0) + Gamma(B0.T)
       + Gamma(B1) + Gamma(B1.T)
   ```

   is exactly positive definite.  After vacuum normalization it equals
   `exp(-H)` for a Hermitian, number-conserving, genuinely interacting
   five-mode cluster Hamiltonian.  The exact Gaussian mismatch has 58 nonzero
   entries.  Locality is not claimed.

The earlier TN/Jacobi construction gives a local correlated-hopping
Hamiltonian, but a Jordan-Wigner audit maps it exactly to
ferromagnetic/stoquastic XY physics.  Positive sums of fixed-basis TN Gaussian
operators are therefore a closed known-mechanism boundary, not the new search
space.

The missing result is an exact cancellation or target construction that keeps
the oddcycle arbitrary-history theorem while removing the unwanted nonlocal
and high-body terms.

## Central observation: word lifts enlarge the same-A physical cone

Let `A*` be the finite words in the four certified letters.  For every word

```text
W = A_k ... A_2 A_1
```

the number-conserving Fock lift is multiplicative:

```text
Gamma(W) = Gamma(A_k) ... Gamma(A_2) Gamma(A_1).
```

The transpose word `W.T` is again a word in `A*`.  Define the Hermitian
word-pair operator

```text
Phi_W = Gamma(W) + Gamma(W.T).
```

For any finite dictionary `D subset A*` and positive coefficients,

```text
H = E0 I - sum_(W in D) q_W Phi_W,
E0 real, q_W > 0.                                      (1)
```

Equation (1) is an exact positive-coefficient **continuous-time**
Gaussian/circuit auxiliary-field decomposition:

```text
Tr exp(-beta H)
  = exp(-beta E0)
    sum_(n >= 0) beta^n/n!
    sum_(macro events and transpose branches)
      (product of q_W) det(I + concatenated original-letter word).
```

At expansion order `n`, choosing a branch from each `Phi_W` concatenates the
corresponding original letters.  Thus every Fock trace is

```text
Tr Gamma(W_n ... W_1) = det(I + W_n ... W_1) > 0
```

by the existing arbitrary-word theorem.  No new determinant scan or
unproved closure assumption is needed.

The arbitrary real scalar `E0` factors out as the positive number
`exp(-beta E0)`.  It is not an auxiliary event and is not allowed to satisfy
locality or interaction constraints by itself.  A nonnegative identity branch
may alternatively be retained, but is unnecessary.

This word-pair cone is much larger than the existing four-ray construction
while using exactly the same certified alphabet.

## Shared exact operator compiler

All search routes use one operator-coordinate compiler.

For five number-conserving fermion modes, use the complete normal-ordered basis

```text
O_(I,J) = c_I^dagger c_J, |I| = |J| = k, k = 0,...,5.
```

It has

```text
sum_k binomial(5,k)^2 = 252
```

coordinates and spans every number-conserving Fock operator.  The compiler
maps each exact rational `Phi_W` to these 252 coefficients by a frozen
triangular CAR/Mobius transform.  It also records:

- body order `k`;
- support `I union J`;
- support diameter on a declared graph;
- diagonal versus hopping, exchange, pair-hopping, and correlated-hopping
  type;
- exact Fock-basis off-diagonal signs;
- transpose-word orbit and duplicate-matrix hash.

Two independent checks are required:

1. reconstruct the complete `32 x 32` Fock matrix from the coordinates;
2. compare selected low-body coefficients with direct CAR matrices.

The compiler reuses `exact_gaussian_fock_lift()` and the existing CAR
operators in `fock_basis.py`; only the new 252-coordinate triangular transform
is implemented.

Floating-point screening may use cached dense or sparse coordinate columns.
Every promoted survivor is reconstructed with exact rational arithmetic.

## Route A: free local-cone discovery

This is the recommended first route because locality of (1) is linear in the
positive weights.

Partition the 252 coordinates into:

- `F`: forbidden terms, initially every term above two-body and every term
  whose support exceeds the chosen graph range;
- `P`: permitted physical terms;
- `C`: the scalar identity coordinate.

For a word dictionary `D`, solve

```text
F sum_W q_W Phi_W = 0,
q_W >= 0,
sum_W q_W = 1.                                      (2)
```

The normalization removes the zero solution.  The scalar coordinate is
ignored during feasibility because it can be shifted by `E0 I`.

Initial graph/term ladders are:

1. five-site path, terms supported within one declared nearest-neighbor edge;
2. five-site ring, terms supported within one declared nearest-neighbor edge;
3. five-site path or ring, terms supported within one explicit contiguous
   three-site interval/arc, with correlated hopping allowed;
4. arbitrary two-body five-mode cluster as a looser diagnostic.

Locality is implemented with explicit allowed support sets, not only graph
diameter.  In particular, the five-site ring has graph diameter two, so a
diameter-two rule alone would be vacuous.

For every feasible face, secondary linear objectives seek:

- nonzero density-density, exchange, pair-hopping, or correlated-hopping
  interaction;
- at least two noncommuting active word pairs;
- a gauge-frustrated off-diagonal sign cycle;
- sparse support and a large rational feasibility margin;
- a small number of active rays for a readable HS dictionary.

A survivor is rejected as a physical discovery if it is only a constant,
quadratic/Gaussian Hamiltonian, disconnected one-site sum, or the previously
closed TN/stoquastic construction.

### Search ladder

Build transpose-orbit and exact-matrix-deduplicated dictionaries in stages:

```text
word lengths 1-2 -> 1-4 -> 1-6 -> selected 7-10
```

Do not enumerate the final range blindly.  Use dual residuals and active-ray
statistics from each completed stage to prioritize extensions.  Failure at a
short length is a dictionary-specific result, not a no-go theorem.

## Route B: target-first physical reconstruction

The free search may find a mathematically local but physically opaque point.
The independent target-first route asks whether named local model families
lie in the same word-pair cone.

The first target library contains:

- path/ring hopping plus nearest-neighbor density interaction;
- next-neighbor hopping plus tunable density-assisted hopping;
- pair hopping and exchange on consecutive three- or four-site supports;
- gauge-frustrated hopping loops combined with local interactions;
- particle-hole-symmetric or inversion-symmetric subfamilies when compatible
  with the oddcycle coordinates.

For a target operator `K(theta) = -H(theta)`, solve

```text
sum_W q_W Phi_W = K(theta) + s I,
q_W >= 0, s real,                                  (3)
```

or optimize over `theta` in a normalized physical parameter box.  Route B
uses the same exact compiler but different constraints and therefore provides
an independent interpretation of any Route-A face.

The first pass is numerical LP/conic feasibility.  A promoted result must
have:

- an exact rational target point or exact algebraic relation;
- exact nonnegative weights, with zero numerical weights removed;
- exact full-Fock equality;
- a human-readable local Hamiltonian;
- an exact arbitrary-history reduction to the frozen oddcycle theorem.

If a requested target is separated from the cone, retain the dual functional
as a target-specific no-go certificate but immediately move to the next
target.  The project prioritizes successful constructions over broad no-go
classification.

## Route C: local circuit and scalable-lattice promotion

Every macro-field `Gamma(W)` is already a finite Gaussian circuit made from
the original letters, even when `W` has no single real logarithm.  For each
surviving HS dictionary:

1. factor every original `B(p)` or macro-word into the shortest available
   sparse one-/two-mode real Gaussian micro-gates;
2. report circuit depth and geometric support on path, ring, and star
   layouts;
3. distinguish an exact local circuit per auxiliary event from a static local
   Hamiltonian;
4. test overlapping embeddings beyond the five-mode cluster before making any
   scalable-lattice claim.

The five-mode arbitrary-word theorem does **not** automatically survive
overlapping embeddings in a larger one-particle space.  A connected-lattice
family that scales beyond one five-mode cluster requires one of:

- a new fixed global cone/metric certificate;
- an exact block factorization of the full determinant into certified
  five-mode word determinants;
- a telescoping moving-frame/groupoid construction with periodic boundary
  closure; or
- another explicit positive-trace proof.

Disjoint cluster tiling is a valid implementation baseline but is not a
scalable connected-lattice result.  A geometrically local five-site path or
ring is already a connected finite cluster and belongs at `L2`; it must not be
conflated with this stronger promotion.

Route C starts only after a Route-A or Route-B exact local survivor exists.

## Route D: discrete-transfer portfolio

Retain a low-risk family for diversity and numerical seeds:

```text
T(c,q) = c I + sum_W q_W Phi_W,
H(c,q) = -log(T / T_vac).
```

Exact row dominance or exact Sylvester minors certify `T > 0`.  The same word
concatenation proves every discrete auxiliary-field history positive.
High-precision normal-ordered coefficients of `H` rank:

- body-order suppression;
- graph-range suppression;
- interaction strength;
- distance from a Gaussian transfer.

This route can produce many rigorously Hermitian interacting Hamiltonians, but
small high-body coefficients are only a numerical observation.  It does not
satisfy the exact-locality target unless those coefficients are independently
proved to vanish.

## Novelty and physical gates

Every exact local survivor must pass the following gates before promotion.

1. **Hermiticity:** exact transpose pairing and exact operator equality.
2. **Locality:** forbidden normal-ordered coefficients vanish exactly.
3. **Interaction:** at least one exact two-body coefficient is nonzero, or the
   Gaussian transfer identity fails when the route uses a discrete transfer.
4. **Positive HS:** every retained scalar coefficient is strictly positive.
5. **Arbitrary depth:** every macro-history reduces by word concatenation to
   the frozen four-letter determinant theorem.
6. **Non-stoquastic evidence:** the Fock-basis off-diagonal sign graph of
   `H`—not of the positive generator `-H`—contains an exact gauge-invariant
   frustrated cycle, or a stronger exact obstruction.
7. **Known-mechanism audit:** compare with TN/Jordan-Wigner, split-orthogonal,
   Kramers, block decomposition, and the already completed Wei/Majorana
   sufficient-class audit.  The existing Wei no-go applies to the original
   alphabet, but the physical interpretation still needs its own reduction
   audit.
8. **Reproducibility:** exact replay, schema, source commit, payload digest,
   focused tests, and a clean-worktree archival run.

Number-conserving word lifts cannot create anomalous pairing terms.  Pairing
requires a separately designed Nambu/Spin extension and is outside the first
implementation batch.

## Success hierarchy

- `L0` — exact Hermitian interacting five-mode cluster transfer (already
  achieved).
- `L1` — a batch of same-A Hamiltonians with exact positive HS
  decompositions and ranked body/locality profiles.
- `L2` — an exact, geometrically local, interacting five-mode Hamiltonian with
  a positive word-pair HS decomposition.
- `L3` — `L2` plus an exact non-stoquastic/known-mechanism separation.
- `L4` — a scalable connected overlapping-cluster lattice family beyond five
  modes, with a global arbitrary-history positivity proof.

The first publication-quality target is `L3`.  `L4` is the stronger follow-up
and must not be implied by `L2`.

## Compute split and throughput policy

No scientific computation runs on the local Windows workspace.

- **WSL worker:** test-first compiler development, exact rational promotion,
  exact replay, and clean archival runs.
- **CPU machine via WSL:** word enumeration, cached coordinate generation,
  LP/conic screening, target library scans, and high-precision ranking.

Both machines may run concurrently.  Thread counts are set explicitly and
leave two logical cores free on each host.  Every run is resumable and writes
one manifest record per completed cell.  A failure that makes a candidate
impossible stops that candidate immediately; it does not stop unrelated
dictionary/target cells.

The initial batch uses deterministic enumeration and `PYTHONHASHSEED=0`.
Any randomized objective or target sampling stores its explicit seed.

## Durable artifacts and experiment loop

Planned versioned files:

```text
oracle/oddcycle_word_operator.py
oracle/oddcycle_local_hs_scan.py
oracle/oddcycle_local_hs_exact.py
tests/test_oddcycle_word_operator.py
tests/test_oddcycle_local_hs_scan.py
tests/test_oddcycle_local_hs_exact.py
docs/ODDCYCLE_LOCAL_HAMILTONIAN_PORTFOLIO.md
protocols/oddcycle-local-hs-v1/
```

Large column caches and raw solver arrays remain on the remote machines.
Compact manifests, exact weights, separating functionals, commands, seeds,
source commit, host, output paths, and SHA-256 hashes are versioned.

After every completed success or failure:

1. append a concise entry to `docs/EXPERIMENT_LOG.md`;
2. record reusable operational lessons in `docs/RESEARCH_OPERATIONS.md` when
   applicable;
3. update the local-only `AGENT_HANDOFF.md`;
4. commit and push the compact evidence to
   `shared/work/zibo/representation-cones`;
5. verify the remote branch SHA before starting the next scientific stage.

The private handoff is never staged or uploaded.

## First implementation batch

The first batch is deliberately narrow and decisive.

1. Implement and independently test the 252-coordinate normal-ordered
   compiler.
2. Enumerate and deduplicate transpose word orbits through length four.
3. Run Route-A feasibility on the four graph/term ladders.
4. Run a small Route-B target library against the same dictionary.
5. Exact-promote every survivor with at most 32 active rays.
6. If no survivor exists, store dual diagnostics, extend only the most
   promising dictionaries through length six, and repeat.
7. Generate a Route-D portfolio at the same time from the compiled columns;
   this reuses data and is not a separate brute-force scan.

Route C begins only after an exact local survivor is in hand.

## Failure policy

- A numerical survivor is not a result until exact replay.
- A solver failure or tolerance-sensitive residual is `inconclusive`, not
  `infeasible`.
- An exact separating functional closes only its declared dictionary and
  target constraints.
- No broad no-go proof is pursued while untested successful routes remain.
- No completed frontier, dual, robustness, or Majorana/Wei scan is repeated.
- All failed attempts keep their parameters, seed, output location, command,
  and lesson in the research log.

## Acceptance criteria for this design

- The construction uses only words from the already certified alphabet.
- The positive-history proof is explicit under macro-word concatenation.
- Exact locality is posed as linear cancellation before numerical search.
- Free discovery, target-first reconstruction, and lattice promotion are
  separated rather than conflated.
- Known TN/stoquastic results are a deduplication boundary.
- Static local Hamiltonians, local circuits, and scalable connected-lattice
  claims have distinct gates.
- Compute and persistence rules satisfy the user's WSL/CPU and research-log
  requirements.
