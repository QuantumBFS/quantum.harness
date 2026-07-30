# Survivor-A-guided Hamiltonian reverse-construction design

Date: 2026-07-30

Status: independently reviewed and approved; execution awaits the versioned
implementation plan and batch manifest

Upstream checkpoint:
`f7da2e3928cbd1181b3fbb69d603675f89ad8e40`

## Decision

The next search uses Survivor A as a physical and numerical guide, but it
does not search fictitious Hermitian logarithm branches of its fixed transfer.
For a fixed positive-definite transfer, normalization, and time step, the
Hermitian logarithm is unique.

The success-first order is:

1. close the fixed-Survivor-A question with one high-precision,
   interval-checkable audit;
2. search the same certified alphabet's continuous-time positive word cone
   for exact local Hamiltonians, guided by Survivor A's dominant local and
   forbidden coordinates;
3. search nearby positive discrete transfers only as numerical candidate
   generators;
4. exact-promote every candidate through rational word weights, exact
   forbidden-coordinate cancellation, and full-Fock replay; and
5. attempt a connected lattice embedding only after an exact five-mode local
   survivor exists.

No scientific calculation in this protocol runs on local Windows. WSL owns
high-precision analysis and exact promotion. The CPU machine owns column
generation, scoring, and sharded numerical screening.

## Frozen source and terminology

The certified one-particle alphabet is

```text
A = {B(1/1000), B(1/1000)^T, B(4/5), B(4/5)^T}.
```

`A` in this document always denotes that alphabet. The label **Survivor A**
denotes one specific discrete-transfer record and is not a second use of the
mathematical symbol.

Survivor A is frozen by all of:

- source result:
  `protocols/oddcycle-local-hs-v1/result.json`;
- source result SHA-256:
  `12e8ac1e0dcb8b06130556b9ea91392e558521ca20d3b7aeb71413fa77b5d01c`;
- source cell: `portfolio-l2`;
- source cell payload SHA-256:
  `b93465d16f4c9d796bac26104b035ae74f85c1e1e297cc94ff2cb8e4373e2c42`;
- source raw-file SHA-256:
  `c16d32355448d9bd89e282323fbaa64852a408edc8439404feb82ff5bc21cae7`;
- seed and sample: `20260730`, sample `122`;
- the twelve tracked word/transpose-word pairs and their positive rational
  weights;
- additive transfer shift `42`;
- vacuum value `44`; and
- exact minimum row margin `12213/15625`.

Writing `Phi_W = Gamma(W) + Gamma(W)^T` for the transpose-paired Fock lift,
the exact seed transfer is

```text
T_A = 42 I + sum_W q_W Phi_W,
X_A = T_A / 44.
```

Its exact transfer positivity and arbitrary discrete-history positivity are
already certified. Its Hamiltonian profile is currently numerical:

```text
H_A = -log X_A,
body-order norms 1..5 =
  0.1931038727, 0.5508039418, 0.4566425597,
  0.2251054012, 0.1832933442,
cluster-two-body forbidden norm = 0.5411019488,
interaction norm = 0.7721245374.
```

Those numbers make Survivor A a useful interacting seed, but they are not an
exact-locality certificate.

The transfer's SPD gate is stronger than entrywise or history positivity.
The exact row margin is recomputed as

```text
min_i ((T_A)_(ii) - sum_(j != i) |(T_A)_(ij)|)
  = 12213/15625 > 0.
```

Together with exact symmetry, this is a strict symmetric
diagonal-dominance certificate. It also makes every diagonal entry positive,
so every Gershgorin interval lies in the positive real axis and `T_A` is
exactly SPD. Route 0 may not invoke a Hermitian logarithm unless this
certificate, or an exact `LDL^T`/principal-minor replacement, replays.

## Fixed-transfer theorem and invalid search directions

### Unique Hermitian logarithm

Let `X` be positive definite, `Delta tau > 0`, and let `H` be Hermitian. If

```text
exp(-Delta tau H) = X,
```

then

```text
H = -(1 / Delta tau) log X,
```

where `log X` is the principal spectral logarithm.

Indeed, diagonalize `H = sum_j h_j P_j`. Then
`X = sum_j exp(-Delta tau h_j) P_j`. The real exponential is injective, so
the eigenvalues and spectral projectors of `H` are recovered uniquely from
`X`. A degenerate eigenspace of `X` adds no freedom: `H` is scalar on that
eigenspace. General matrix-logarithm branches contain imaginary multiples of
`2 pi` and are not Hermitian.

For a scalar normalization `s > 0`,

```text
exp(-Delta tau H) = T_A / s
```

only adds `(log s / Delta tau) I` to the Hamiltonian. Changing `Delta tau`
rescales every non-scalar coupling. Neither operation removes a forbidden
non-scalar coordinate. Changing the additive transfer shift `42 I`, in
contrast, changes the non-scalar logarithm and therefore defines a genuinely
different transfer.

### Valid and invalid freedoms

The following are valid but do not create a second Hamiltonian for fixed
`T_A`:

- alternative positive word decompositions of the same transfer change the
  auxiliary representation, not `H_A`;
- integer time blocking gives `X_A^m = exp(-m H_A)`;
- mode permutations and diagonal sign/phase gauges relabel the same physical
  support;
- a conjugation by an orbital unitary creates a conjugate alphabet and
  transfer, not a new logarithm of the original transfer; and
- Cholesky, square-root, or micro-gate factorizations leave the unique
  logarithm unchanged.

Dense orbital rotations are not allowed to manufacture locality: they
redefine physical sites. Number-conserving orbital rotations also preserve
body-order grading, so nonzero three-, four-, or five-body components cannot
be rotated into a two-body Hamiltonian.

A noncommuting product of local transfers is a local circuit, not proof that
its static logarithm is local; Baker-Campbell-Hausdorff terms generally
restore nonlocal terms.

An ancilla compression is not a local realization of `H_A` unless an exact
invariant-code intertwiner or exact partition-function reduction is proved.
Compression and logarithm do not commute. Any dilation also needs a new
arbitrary-history positivity proof on the enlarged system.

These observations exclude branch search, dense-gauge optimization, generic
matrix factorization, and unproved ancilla gadgets from the first batch.

## Route 0: close the fixed seed once

The first executable stage reconstructs `T_A` exactly and computes `H_A` at a
declared precision ladder, initially 80, 120, and 180 decimal digits.

It compares reconstructed Hamiltonian matrices and normal-ordered
coordinates between precision levels, not eigenvectors, because eigenvectors
inside a degenerate subspace may rotate. It independently checks
`exp(-H_A) = X_A` at every precision.

For each locality ladder it stores:

- all 252 number-conserving normal-ordered coordinates as decimal strings;
- body-order norms;
- allowed and forbidden coordinate norms in `L2` and `Linf`;
- the full-Fock reconstruction residual;
- dominant Hermitian coordinate orbits; and
- interval or multi-precision enclosures for the largest forbidden
  coordinates.

One forbidden coordinate whose enclosure excludes zero closes exact locality
of fixed `H_A` for that locality. Because the current forbidden and high-body
norms are order one, this is expected to early-stop quickly. It is an audit,
not a no-go research program.

## Route 1: primary exact-local continuous-time cone

The main search changes the transfer/generator while retaining the certified
alphabet. It seeks

```text
H(q) = E0 I - sum_W q_W Phi_W,    q_W > 0.
```

Every `Phi_W` is exactly Hermitian. The Taylor histories of
`exp(beta sum_W q_W Phi_W)` have positive scalar coefficients, and each
matrix history concatenates into a word over the frozen alphabet. Therefore
the existing arbitrary-word determinant theorem applies at arbitrary
expansion depth.

Explicitly, with `G = sum_W q_W Phi_W`,

```text
exp(beta G)
  = sum_(n >= 0) beta^n/n!
      sum_(W_1,...,W_n) q_(W_1)...q_(W_n)
        Phi_(W_1)...Phi_(W_n).
```

Expanding each
`Phi_W = Gamma(W) + Gamma(W^T)` gives `2^n` terms with positive
coefficients. The exterior representation is multiplicative in the frozen
product convention, so every term is `Gamma(U)` for one concatenated word
`U` over the four-letter alphabet, including every independent transpose
choice. Its grand-canonical Fock trace is `det(I + U) > 0` by the frozen
arbitrary-word theorem. The `n=0` empty history contributes
`Tr(I_Fock) = 2^5 > 0`. This is the auditable arbitrary-depth positive-event
proof; it does not assume the `Phi_W` commute.

In the 252-coordinate normal-ordered basis, exact locality is linear:

```text
F_local q = 0.
```

Target reconstruction is also affine and linear:

```text
sum_W q_W Phi_W = s I - H_target.
```

This route has two coordinated modes.

### Free-cone mode

For each declared locality, solve the normalized positive kernel and signed
permitted two-body objectives. Existing length-at-most-four columns remain
anchors. New length-five and length-six matrix orbits are generated once,
scored once, and selected by deterministic channel quotas.

### Target-first mode

Project the high-precision Survivor-A Hamiltonian onto each declared local
support. Hermitian coordinate orbits are kept together. Normalize by a
declared nonzero pivot and rationalize with a frozen denominator bound.
Reject a projected target if it has no exact two-body term.

The projected targets seed parameterized, human-readable Hamiltonian
families. Search solves their exact coordinate equalities numerically first
and immediately promotes sparse active faces with exact rational arithmetic.

### Column scoring

No opaque blended score is used. New words are ranked independently by:

1. target alignment with `-H_target`;
2. cancellation of Survivor A's forbidden residual;
3. allowed-coordinate norm divided by total non-scalar norm; and
4. coverage quotas over body order and support buckets.

The selected catalog is the deterministic union of fixed per-channel,
per-length quotas. Ties use

```text
(word length, word, transpose word, exact matrix-orbit key).
```

The catalog stores all component scores and selection ranks. Numerical scores
select columns; they never certify feasibility or locality.

The shared `float64` coordinate catalog is discovery-only. Every exact
nullspace, separator, target equality, and forbidden-coordinate cancellation
is recomputed from the exact rational Fock/coordinate columns for the precise
declared dictionary or active support. Floating rank, residual, solver dual,
or nullity never triggers an exact early stop.

## Route 2: nearby discrete transfers

In parallel with Route 1 after the code and protocol are frozen, search

```text
T(c,q) = c I + sum_W q_W Phi_W,   c > 0, q_W > 0,
H(c,q) = -log(T / T_vac).
```

Survivor A supplies the first center in weight space. Additional centers use
sparse perturbations, support-stratified perturbations, and selected
length-five/six columns. Exact strict row dominance certifies transfer
positivity before the logarithm is evaluated.

The numerical objective is lexicographic:

1. forbidden leakage divided by non-scalar interaction norm;
2. maximum body order;
3. graph-range leakage;
4. interaction strength bounded away from zero; and
5. distance from a Gaussian transfer.

Normalization prevents the false optimum `T -> scalar I`.

This route is a discovery engine only. A tiny floating leakage is not an
exact-local result. Promotion requires either:

- an exact structural identity
  `T / s = exp(-Delta tau H_local)` in a tractable commuting/projector
  algebra; or
- conversion of the discovered term pattern into a Route-1 exact affine
  word-cone certificate.

Inverse-local ansatze are preferred over indefinitely minimizing a
transcendental matrix-log objective.

## Route 3: factorization, dilation, and lattice promotion

This route is deferred until Route 1 yields an exact five-mode local
survivor.

A static local Hamiltonian claim from a transfer factorization requires
commuting local factors or an exact logarithmic identity. A local-circuit
claim is recorded separately.

An ancilla/dilation claim requires:

- an exact invariant-code intertwiner or exact partition-function reduction;
- exact locality of the enlarged Hamiltonian;
- exact removal or accounting of ancillary degrees of freedom; and
- a new full-system arbitrary-history positivity proof.

A connected lattice claim requires positivity for arbitrary spatially
varying auxiliary fields and kinetic steps in the full embedded
one-particle space. Five-mode positivity does not imply this. Disjoint
cluster copies remain a baseline, not a connected scalable lattice result.

## Physical target hierarchy

All targets are real, Hermitian, number conserving, and constrained to body
order at most two in fermionic normal ordering. Write

```text
chi_ij = c_i^dagger c_j + c_j^dagger c_i,
delta n_i = n_i - 1/2,
C_ijk = c_i^dagger c_j^dagger c_k c_j + h.c.,
P_ijkl = c_i^dagger c_j^dagger c_l c_k + h.c.
```

### P1: five-orbital frustrated molecular pentagon

The first target is one five-orbital unit cell with

```text
h_C5 =
  -t sum_a eta_a chi_(a,a+1)
  +V sum_a delta n_a delta n_(a+1)
  +X sum_a C_(a,a+1,a+2)
  +P sum_a P_(a,a+1,a+2,a+3),

product_a eta_a = -1.
```

This combines an exact odd-cycle gauge obstruction with density,
density-assisted hopping, and pair motion. It is the cleanest `L2/L3`
finite-cluster target and matches the channels expected from Survivor A's
large quartic component.

Before exact promotion this obstruction means only an exact
diagonal-sign-gauge obstruction already visible in the one-particle `C5`
hopping sector. It is not a claim of many-body non-stoquasticity under every
local basis change. The stronger statement, if available, belongs to the
post-promotion `L3` audit.

The stronger publication target places these cells on a two-dimensional
Bravais lattice and adds flavor-preserving intercell hopping. This would
give finite-temperature, local-dimension-32 physics. World-line/SSE routes
face fermionic and off-diagonal signs; general off-diagonal hybridization
with pair/spin-flip-like interactions is difficult for impurity QMC; and
finite-temperature two-dimensional tensor networks are approximate and
expensive. These are motivation statements, not impossibility theorems.

The intercell term is not included in an `L4` claim until a full embedded
determinant proof exists.

### P2: triangular correlated-hopping model

If Survivor A's recovered coordinate orbits favor triangle/rhombus channels,
promote a spinless triangular-lattice target with frustrated hopping,
nearest-neighbor density interaction, oriented correlated hopping, and
rhombus pair motion.

This has the highest comparative physics payoff and the highest proof risk:
non-bipartite finite-density fermions with non-density quartic interactions
in two dimensions. Each overlapping local embedding and arbitrary global
history needs a new exact proof. It is not the first batch's required
success.

### P3: exact five-mode fallback

The connected `C5` cluster alone is a valid exact-local challenge result if
the Route-1 identity is found. It is not a practical scaling result because
its Fock dimension is only 32 and exact diagonalization is trivial. Disjoint
copies must not be advertised as a connected lattice.

### Deduplication boundary

The scan does not prioritize:

- ordinary half-filled bipartite Hubbard models;
- known attractive-Hubbard or flavor-paired sign-free windows;
- quadratic/Gaussian generators;
- disconnected density-only models;
- targets reducible by an exact diagonal sign gauge to an unfrustrated
  off-diagonal graph; or
- targets already covered by a known Kramers, particle-hole, block,
  split-orthogonal, or fixed-Majorana sufficient mechanism.

Known-mechanism separation is an exact post-promotion audit, not a numerical
search score.

## Minimal implementation

The first implementation reuses the frozen exact oracle and runner
infrastructure. It adds only:

```text
oracle/oddcycle_survivor_a.py
oracle/oddcycle_survivor_a_runner.py
tests/test_oddcycle_survivor_a.py
tests/test_oddcycle_survivor_a_runner.py
protocols/oddcycle-survivor-a-v1/
```

Small extensions are allowed in:

- `oddcycle_word_operator.py`: construct one selected word-pair column and a
  selected dictionary without materializing every length-six Fock column;
- `oddcycle_local_hs_scan.py`: scan shared coordinate matrices and retain
  full primal residuals, weights, and available solver dual data;
- `oddcycle_local_targets.py`: build exact coordinate-defined targets; and
- `oddcycle_local_hs_exact.py`: exact positive affine promotion and exact
  target certificates.

The frozen first-batch runner's scientific classifications are not changed.
Existing canonical JSON, hashing, atomic-write, manifest-repair, and
validation helpers are reused directly. A third persistence implementation
is not introduced.

### Core records

`SurvivorASeed` binds the source result hash, source cell hash, identity,
words, transpose words, weights, shift, vacuum value, and row margin.

`HamiltonianAnalysis` binds the exact transfer digest, precision ladder,
exponential replays, all 252 decimal coordinates, projections, and
rationalized targets.

`ColumnCatalog` binds every selected word identity, score components,
selection reason/rank, coordinate-array digest, and settings digest.

`SearchAttempt` separates:

- compute status: completed, interrupted, or error; from
- scientific status: numerical candidate, numerically infeasible,
  solver-inconclusive, exact survivor, or exact rejected.

The terminal status `survivor` is not reused as an implicit route/type
contract.

## Exact source reconstruction gates

Before high-precision work, the loader must verify:

- tracked schema and unique label `A`;
- exact source result SHA-256;
- exact source cell payload SHA-256;
- all word/transpose-word pairs;
- strictly positive rational weights summing to one;
- exact symmetry of `T_A`;
- exact positivity of every diagonal entry;
- exact strict symmetric diagonal dominance, with recomputed minimum margin
  `12213/15625`;
- `T_A[0,0] = 44`;
- a frozen canonical rational-matrix digest; and
- exact consistency between every tracked word and its dictionary orbit.

Any mismatch is an operational failure, not a scientific result.

## Sharding, resume, and failure preservation

The CPU machine builds one `252 x N` float64 coordinate array and stores it
as a memory-mappable `.npy` file with hashed metadata. Exact columns are
materialized only for selected words and active promotion supports.

Cells are assigned by stable identity:

```text
owner =
  int(sha256(cell_id)[0:16], 16) mod shard_count.
```

Any randomized cell seed is derived from
`sha256(protocol_seed || cell_id)`. The protocol seed is `20260730`.
`PYTHONHASHSEED=0` and single-thread BLAS/HiGHS settings are explicit.

Each cell has append-only attempts:

```text
cells/<cell-id>/
  attempts/attempt-0001-start.json
  attempts/attempt-0001-result.json
  ...
  terminal.json
```

The start record is durable before compute. Results are atomic. A compute
error records stage, exception type, message, and bounded traceback, and may
be retried as the next attempt. It is never relabeled scientific
inconclusive. Resume skips only a hash-verified terminal scientific result
whose plan, catalog, settings, and code hashes match.

Each shard owns its manifest. Collection rejects missing payloads, duplicate
cell identities, payload conflicts, and cross-shard ownership violations.
No failed cell stops unrelated work.

Every artifact binds:

- source result and source cell hashes;
- source and code commits;
- settings, plan, analysis, and column-catalog hashes;
- Python, NumPy, SciPy, SymPy, and mpmath versions;
- machine role; and
- commands, environment variables, seed, output path, and elapsed time.

## Exact promotion gates

An `L2` continuous-time survivor requires:

1. exact source-word and transpose replay;
2. strictly positive exact weights after zero rays are removed;
3. exact Hermiticity;
4. exact zero for every forbidden normal-ordered coordinate;
5. exact full `32 x 32` Fock equality;
6. no body order above two;
7. at least one exactly nonzero two-body term;
8. exact arbitrary-history reduction to the frozen determinant theorem; and
9. a tracked, human-readable Hamiltonian formula.

An `L3` survivor additionally requires:

- an exact gauge-frustrated/non-stoquastic obstruction; and
- a documented audit against known particle-hole, Kramers/flavor-pairing,
  block, split, and fixed-Majorana mechanisms.

A discrete-transfer survivor additionally requires exact `T > 0` and an
exact structural proof that `T/s = exp(-Delta tau H_local)`. Numerical
matrix-log locality is never promoted by rounding.

An `L4` result additionally requires a full connected-lattice arbitrary-field
history proof. No five-mode or disjoint-tiling evidence substitutes for it.

## Early stops

Stop one candidate immediately when:

- an exact rational forbidden matrix for the declared dictionary has zero
  nullity;
- a one-dimensional exact rational nullspace has mixed signs;
- an exact rational affine separator rejects the declared target and
  dictionary;
- fixed `H_A` has one interval-certified forbidden nonzero coefficient;
- the only leakage improvement sends the interaction norm to zero;
- the survivor is scalar, quadratic, disconnected, gauge-unfrustrated, or a
  known sign-free benchmark; or
- a factorization/dilation lacks its exact static-H and extended-history
  proof obligations.

Numerical solver failure, tolerance sensitivity, and missing dual data are
`inconclusive` or operational failure, never `infeasible`.

## First-batch execution outline

The first batch will run in this order.

1. Reconstruct the exact seed and run the precision-ladder Route-0 audit once
   on WSL.
2. Recover dominant Hermitian coordinate orbits and freeze the `C5`
   projected target family.
3. On the CPU machine, enumerate/deduplicate length-five and length-six word
   orbits once, build the shared coordinate catalog, and apply deterministic
   channel quotas.
4. Run sharded Route-1 free and target cells. Keep all length-at-most-four
   anchors. Preserve full residual and dual evidence.
5. In parallel, run a bounded Route-2 portfolio centered on Survivor A. Its
   output is candidate evidence only.
6. Copy only numerical candidates and compact manifests to WSL. Exact-promote
   active supports.
7. Collect every shard, audit hashes and cell accounting, and produce one
   compact result JSON.
8. Append results and lessons to the research and operations logs, update the
   private handoff without staging it, run an independent evidence review,
   commit, push, and verify the shared remote SHA before defining another
   batch.

The implementation plan must freeze exact quotas, target parameter grids,
shard counts, commands, output directories, and an immutable versioned batch
manifest before step 1 launches. Until that plan and manifest are reviewed
and committed, this section is an execution outline rather than an
executable protocol freeze.

## Acceptance criteria

The design is ready to implement when:

- fixed-transfer logarithm uniqueness and the valid construction freedoms are
  explicit;
- Survivor A is bound by exact tracked identity and cannot drift;
- exact-local and numerical-discovery routes have distinct claims;
- the main search turns locality into exact linear cancellation;
- the first physical model and DQMC advantage boundary are concrete;
- five-mode and connected-lattice claims are separated;
- no local Windows scientific compute is permitted;
- existing exact oracle and persistence infrastructure are reused;
- every cell is independently resumable and every failure is retained; and
- every exact survivor must pass full rational and full-Fock replay.

Execution readiness additionally requires the reviewed implementation plan
and immutable versioned batch manifest named in the first-batch outline.
