# Exterior-Cone High-Throughput Discovery Loop

Date: 2026-07-29

Status: approved by the user for autonomous execution and iteration.

## 1. Objective

Prioritize discovery of a successful, physically realizable, sign-problem-free
QMC matrix structure. Reuse the existing determinant, Spin-trace,
high-precision, exact-certificate, parameter-scan, and manifest machinery.
Do not extend the R01 no-go classifier or rebuild generic infrastructure.

The loop is:

```text
typed candidate generation
  -> cheap structural checks
  -> 64-history direct-weight screen
  -> 1024-history survivor screen
  -> 16384-history adversarial screen
  -> high-precision replay
  -> exact exterior-cone or other analytic certificate
  -> novelty reduction audit
  -> positive-coefficient physical HS/Hamiltonian reconstruction
  -> next round seeded by all successes and failures
```

Every attempt, including operational failures, must be summarized in
Markdown. A failed family is stopped early and informs the next candidate
distribution. A surviving family is promoted automatically without waiting
for user confirmation.

## 2. Search hypotheses

### 2.1 Primary hypothesis: non-induced exterior cones

For an \(N\times N\) finite Gaussian propagator \(B\),

\[
\det(I+B)=\sum_{k=0}^{N}\operatorname{tr}(\wedge^k B).
\]

For a finite atom set \(\mathcal B=\{B_s\}\), search for fixed invertible
matrices \(T_k\) such that, for every atom and every particle sector,

\[
T_k^{-1}(\wedge^k B_s)T_k\geq0
\quad\text{entrywise}.
\]

Exterior powers are multiplicative. Therefore every word
\(D=B_{s_L}\cdots B_{s_1}\) has entrywise-nonnegative transformed exterior
powers, nonnegative sector traces, and

\[
\det(I+D)\geq0
\]

at arbitrary depth.

The route is potentially new only when the collection \(\{T_k\}\) is not
induced by one common one-particle basis change \(T_1\), and is not reducible
to ordinary TN, odd monomial/P0, split/contraction, compact orthogonal,
Kramers, Majorana reflection, or an abelian diagonal Gaussian channel.

### 2.2 Secondary hypothesis: direct survivor evolution

The exterior-cone library is deliberately incomplete. In parallel, evolve
fixed finite atom sets using only direct determinant/Spin-trace survival as
the early fitness signal. Mutations preserve:

- real Gaussian realizability \(B_s=\exp(A_s)\);
- transpose-paired atoms \(A_s,A_s^{\mathsf T}\) for a possible Hermitian
  positive-coefficient local vertex;
- declared sparse/local support;
- deterministic canonical serialization and candidate hashes.

Long-lived direct survivors are returned to the primary route to infer an
exterior-cone, symmetry, or factorization certificate. A zero-failure direct
scan alone is never a theorem.

## 3. Candidate grammar

Each candidate card fixes all atoms; histories sample only words in that
fixed alphabet. The first round uses these typed generator grammars:

1. `sparse-hopping`: directed sparse real hopping on connected graphs with
   one loop or one degree-three vertex;
2. `graded-block`: two or three locally coupled blocks with off-diagonal
   grade constraints, excluding already registered triangular controls;
3. `block-circulant`: noncommuting block-circulant atoms with independently
   transformed particle sectors;
4. `clifford-paired`: real Clifford/graded atoms closed under transpose,
   excluding a declared common Kramers operator;
5. `palindromic-microword`: finite atoms formed from short local
   \(e^Xe^Ye^{X^{\mathsf T}}\) words, stored as one macro-factor while
   retaining their real-generator decomposition;
6. `bdg-paired`: small real Nambu/BdG atoms with explicit
   creation/annihilation pairing convention, checked by the existing
   Spin/Fock oracle after determinant screening.

Dimensions are \(N=4,6,8\). Atom counts are \(2,3,4\). Every non-control
candidate must contain a noncommuting pair and a declared cross-block or loop
support feature. Known TN, split, compact, odd-monomial, commuting, and common
Euclidean contraction/expansion examples remain in the run only as controls
and cannot be promoted as discoveries.

## 4. Exterior-cone transformation library

The initial library is finite and cheap:

- signed diagonal and signed permutation gauges;
- block Hadamard transforms;
- exact sparse unimodular transforms with entries in
  \(\{-1,0,1\}\) and determinant \(\pm1\);
- exterior-sector transforms inherited from the existing Klein-Hodge,
  parity, and block bases;
- tensor products and direct sums of the preceding transforms when the
  compound dimension matches.

All transforms are canonicalized and hashed. Exact integer/rational
transforms are preferred. Float candidates may screen numerically but cannot
be promoted to a proof without rational/algebraic reconstruction.

For each \(k\), the compound matrix is computed in the fixed lexicographic
subset basis. A structural certificate records \(T_k\), \(T_k^{-1}\), the
basis order, the smallest transformed entry across all atoms, and whether the
full collection is induced from a common one-particle transform.

## 5. Staged screening and early stopping

### Stage 0: structural and one-slice gate

Reject immediately on:

- nonfinite entries or failed real exponential construction;
- structure residual above `1e-10`;
- missing transpose partner;
- commuting non-control atom set;
- no declared loop/cross-block support;
- a negative, complex, or uncertain one-slice weight;
- mismatch between determinant and Spin/Fock oracle where both apply.

### Stage 1: coarse discovery

- histories: `64` per declared depth/scale cell;
- depths: `2,3,4`;
- scales: `0.25,1.0,3.0`;
- deterministic seeds from the candidate hash;
- stop the candidate on the first `negative` or `complex` result;
- retain `uncertain` only for immediate high-precision replay.

### Stage 2: survivor screen

- histories: `1024`;
- depths: `4,8,16`;
- scales: `0.5,1.0,2.0,4.0`;
- adversarial word selection favors alternating noncommuting atoms and the
  smallest prior singular-value margin.

### Stage 3: pressure screen

- histories: `16384`;
- depths: `8,16,32`;
- all Stage 2 scales plus targeted scales from the weakest margin;
- high-precision replay of every uncertain cell and the ten smallest
  `sigma_min(I+D)` histories.

Any failure stops later stages for that candidate. Only the top `0.1%` of
zero-failure candidates, ranked first by exact exterior certificate and then
by worst numerical margin, reach proof/physics work.

## 6. Machine partition and throughput

Use exactly 76 process shards:

- WSL: shards `0..13`, at most 14 Python processes;
- CPU machine: shards `14..75`, at most 62 Python processes;
- `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1` everywhere.

The owner is

```text
int(candidate_sha256[:16], 16) mod 76
```

so no candidate is duplicated. Each process executes one sequential shard
run-spec and writes one manifest per candidate/stage. The existing
`scripts/parameter_scan.py` owns Cartesian enumeration, collection, resume
detection, and CSV output. The new code owns only candidate construction,
one-candidate screening, and shard-file emission.

Direct GitHub access is not required on the CPU machine. Code moves by
verified complete Git bundle through WSL. Raw results remain under
`tracks/qmc/results/no-negative-vibes/` and outside Git.

## 7. Data contract

Every candidate manifest contains:

```text
schema_version
candidate_id
candidate_card
source_commit
stage
machine_role
shard
settings
oracle_versions
status
tested_histories
first_failure
counts
worst_margin
exterior_certificates
known_mechanism_flags
artifacts
runtime_seconds
```

Allowed terminal stage statuses:

```text
rejected-structure
rejected-negative
rejected-complex
uncertain-high-precision
survivor-no-certificate
survivor-exterior-certificate
known-reduction-control
operational-error
```

Atomic writes use `.json.tmp` followed by rename. Existing successful
manifests are reused; failed/missing cells remain visible. Retry is automatic
only for `operational-error` or `uncertain-high-precision`, never for a
certified negative.

## 8. Automatic learning loop

After every round:

1. collect all manifests, including failed/missing cells;
2. append one round section to `docs/EXPERIMENT_LOG.md`;
3. append genuinely reusable mechanical lessons to
   `docs/RESEARCH_OPERATIONS.md`;
4. write an ignored detailed round report with commands, hashes, timings,
   candidate counts, and failure examples;
5. update grammar weights:
   - zero weight for exact/robust negative structural subfamilies;
   - halve weight for families failing before depth 4;
   - double weight for distinct noncommuting survivors;
   - reserve 20% exploration probability uniformly across nonclosed
     grammars to avoid premature convergence;
6. generate a new immutable run id and provenance hash;
7. commit/push the tracked summary and any reviewed code before the next
   scientific source commit is frozen.

No loop iteration may silently widen a theorem. A new grammar, basis
convention, oracle, or physical constraint receives a new protocol/run id.

## 9. Success gates

A computational survivor requires:

- zero negative/complex histories through Stage 3;
- every uncertainty replayed at high precision;
- at least one noncommuting atom pair;
- no immediate known-control flag;
- exact canonical candidate card and source provenance.

A mathematical candidate additionally requires an exact arbitrary-depth
certificate, preferably the exterior-cone certificate above.

A physical candidate additionally requires:

- local real quadratic generators or a declared finite real micro-word;
- positive auxiliary scalar coefficients;
- Hermitian Hamiltonian vertex, normally by transpose/conjugate pairing;
- exact accounting of constant, quadratic, quartic, and higher-body terms;
- a common sign-free certificate when a free quadratic drift is included.

A paper candidate additionally requires independent method/oracle replay,
known-mechanism and literature audit, scaling beyond the discovery dimension,
reproducible code/data, and a theorem whose scope matches the physical model.

## 10. Non-goals

- Do not finish the R01 no-go classifier.
- Do not rescan closed classical/AZ/split/Majorana families without a new
  structural hypothesis.
- Do not call zero random failures a proof.
- Do not rebuild determinant, Spin-trace, high-precision, raw-evidence,
  parameter-scan, or Git transport infrastructure.
- Do not push or update the organizer-facing branch or PR #178.
