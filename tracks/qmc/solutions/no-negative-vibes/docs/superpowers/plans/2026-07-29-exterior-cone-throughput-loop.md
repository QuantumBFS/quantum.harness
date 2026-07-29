# Exterior-Cone Throughput Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Prelaunch amendment:** Before Task 2, read
> `2026-07-29-exterior-cone-throughput-loop-prelaunch-amendment.md`.
> Its exact-atom, exact-first, transform-union, promotion, and protocol-count
> clauses override conflicting text in Tasks 2--9 below.

**Goal:** Launch a resumable 76-shard WSL/CPU discovery loop that rapidly
falsifies fixed local Gaussian atom sets, searches survivors for non-induced
exterior-cone certificates, records every outcome, and automatically promotes
only the best survivors.

**Architecture:** Freeze the existing weight/exact/high-precision oracles.
Add one mathematical exterior-power module, one deterministic typed-candidate
module, and one thin scan/manifest entrypoint. Use the existing
`scripts/parameter_scan.py` for Cartesian enumeration and collection; split
its run spec deterministically into 76 sequential shards and run 14 on WSL
and 62 on the CPU machine.

**Tech Stack:** Python 3.11, NumPy 2.4.6, SciPy 1.17.1, SymPy 1.14.0, pytest,
existing `oracle.weights`, `oracle.high_precision`, parameter-scan manifests,
Git bundles, WSL/CPU plain SSH.

## Global Constraints

- Base design commit:
  `00d8ca88ab824880bd28bdc88292e6f0912e5d41`.
- Do not modify determinant, Spin-trace, high-precision, raw-evidence, R01, or
  generic parameter-scan implementations unless a failing characterization
  test proves an existing bug.
- Do not implement or continue `classify_r01_fixture`.
- All random behavior is generated from a canonical candidate hash and
  recorded seed.
- Candidate atoms are fixed before word sampling.
- Every non-control atom set is transpose-closed, contains a noncommuting pair,
  and has loop or cross-block support.
- Stage 1 uses exactly histories `64`, depths `[2,3,4]`, and scales
  `[0.25,1.0,3.0]`.
- Stop a candidate immediately on the first negative or complex weight.
- `uncertain` goes only to high-precision replay; it is not a survivor.
- WSL uses at most 14 processes; CPU uses at most 62; all three BLAS thread
  variables equal `1`.
- Raw manifests/results stay under
  `tracks/qmc/results/no-negative-vibes/` and out of Git.
- Record every attempt in Markdown and update strategy after every round.
- Push only `work/zibo/representation-cones` to the shared team repository.
- Do not touch the organizer-facing branch or PR #178.
- No tracked edit after a frozen candidate's final verification.

---

### Task 1: Exterior-power mathematics

**Files:**

- Create:
  `tracks/qmc/solutions/no-negative-vibes/oracle/exterior_cone.py`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_cone.py`

**Interfaces:**

- Produces:

  ```python
  def subset_basis(size: int, grade: int) -> tuple[tuple[int, ...], ...]
  def compound_matrix(matrix: np.ndarray, grade: int) -> np.ndarray
  def determinant_from_compound_traces(matrix: np.ndarray) -> complex
  def transformed_nonnegative_margin(
      matrices: tuple[np.ndarray, ...],
      transform: np.ndarray,
      *,
      tolerance: float,
  ) -> float | None
  def common_transform_certificate(
      atoms: tuple[np.ndarray, ...],
      transform_library: Mapping[int, tuple[tuple[str, np.ndarray], ...]],
      *,
      tolerance: float,
  ) -> dict[str, object] | None
  ```

- `None` from `transformed_nonnegative_margin` means at least one transformed
  entry is below `-tolerance`; otherwise the float is the smallest real
  transformed entry.
- `common_transform_certificate` requires one fixed transform per grade for
  every atom and returns JSON-like arrays/lists only.

- [ ] **Step 1: Write exact-characterization RED tests**

Add tests that require:

```python
def test_subset_basis_is_lexicographic_and_validates_grade() -> None:
    assert subset_basis(4, 2) == (
        (0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)
    )
    with pytest.raises(ValueError):
        subset_basis(3, 4)


def test_compound_matrix_uses_fixed_minor_convention() -> None:
    matrix = np.array([[1, 2, 0], [0, 3, 4], [5, 0, 6]], dtype=float)
    expected = np.array([
        [3, 4, 8],
        [-10, 6, 12],
        [-15, -20, 18],
    ])
    np.testing.assert_allclose(compound_matrix(matrix, 2), expected)


def test_compound_is_multiplicative() -> None:
    left = np.array([[1, 1, 0], [0, 1, 2], [1, 0, 1]], dtype=float)
    right = np.array([[2, 0, 1], [1, 1, 0], [0, 1, 1]], dtype=float)
    np.testing.assert_allclose(
        compound_matrix(left @ right, 2),
        compound_matrix(left, 2) @ compound_matrix(right, 2),
    )


def test_compound_trace_sum_reconstructs_det_i_plus_b() -> None:
    matrix = np.array([[0.5, 1.0], [-0.25, 2.0]])
    assert determinant_from_compound_traces(matrix) == pytest.approx(
        np.linalg.det(np.eye(2) + matrix)
    )
```

Also test square/finite/invertible-transform rejection, imaginary residue
rejection above tolerance, a positive diagonal control certificate, and
failure when one atom has an unavoidable negative diagonal entry.

- [ ] **Step 2: Run RED on WSL**

Run from the solution directory:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=. python -m pytest tests/test_exterior_cone.py -q
```

Expected: collection fails only because `oracle.exterior_cone` is absent.
Append command, exit status, duration, and interpretation to
`docs/EXPERIMENT_LOG.md`.

- [ ] **Step 3: Commit RED**

```bash
git add tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_cone.py \
        tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md
git commit -m "test: specify exterior cone certificates"
```

- [ ] **Step 4: Implement the minimal GREEN mathematics**

Use `itertools.combinations`; compute each compound entry as the determinant
of the declared row/column minor. Grades `0` and `N` are supported. Validate
one common square size, finite values, invertible transforms, and matching
compound dimensions. Use `np.linalg.solve(transform, compound @ transform)`
instead of materializing an inverse.

`common_transform_certificate` iterates grades `0..N`, then the declared
library order. It stops at the first transform that works for every atom in
that grade and returns:

```python
{
    "dimension": N,
    "basis_convention": "lexicographic-subsets",
    "grades": [
        {
            "grade": k,
            "transform_id": str,
            "transform": list[list[float]],
            "minimum_entry": float,
        },
    ],
}
```

- [ ] **Step 5: Run GREEN**

Run the focused module, then existing weight/scan tests:

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_cone.py -q
PYTHONPATH=. python -m pytest tests/test_weights.py tests/test_scan.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/exterior_cone.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_cone.py
git commit -m "feat: add exterior cone certificate search"
```

---

### Task 2: First-tranche fixed atom grammars

**Files:**

- Create:
  `tracks/qmc/solutions/no-negative-vibes/oracle/exterior_candidates.py`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_candidates.py`

**Interfaces:**

- Produces:

  ```python
  def candidate_card(
      *,
      template: str,
      seed: int,
  ) -> dict[str, object]
  def candidate_id(card: Mapping[str, object]) -> str
  def generators_from_card(
      card: Mapping[str, object],
  ) -> tuple[np.ndarray, ...]
  def finite_atoms(
      generators: tuple[np.ndarray, ...],
      *,
      scale: float,
  ) -> tuple[np.ndarray, ...]
  def candidate_structure_residual(
      card: Mapping[str, object],
      generators: tuple[np.ndarray, ...],
  ) -> float
  ```

- First-tranche templates:

  ```text
  sparse4-pair2-loop
  sparse6-pair2-degree3
  sparse8-pair2-two-loop
  graded4-pair2-bicoupled
  graded6-pair2-overlap
  graded8-pair3-overlap
  blockcirc4-pair2
  blockcirc6-pair2
  blockcirc8-pair3
  ```

- Cards contain only JSON scalars/lists/dicts and encode all integer/rational
  coefficients explicitly. `candidate_id` is SHA-256 of compact sorted JSON.

- [ ] **Step 1: Write RED tests**

Require exact deterministic cards/hashes, distinct seeds, JSON round trip,
transpose closure, shapes 4/6/8, finite real matrices, at least one
noncommuting pair, declared loop/cross-block support, residual below `1e-12`,
and exact equality
`finite_atoms(generators, scale)[i] == scipy.linalg.expm(scale*generator_i)`.

Require invalid template/seed/card keys to raise and ensure a card never
contains hostname, username, path, package, or runtime fields.

- [ ] **Step 2: Run and commit RED**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_candidates.py -q
git add tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_candidates.py
git commit -m "test: specify fixed exterior candidate cards"
```

- [ ] **Step 3: Implement deterministic grammars**

Use only NumPy/SciPy already installed. Sample small integer coefficients from
the seed, normalize each generator to Frobenius norm `sqrt(N)`, append its
transpose unless already symmetric, and reject/reseed deterministically up to
32 attempts until the noncommutator norm exceeds `1e-8`. Never sample new
generators during history screening.

- [ ] **Step 4: Run and commit GREEN**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_candidates.py \
  tests/test_exterior_cone.py -q
git add tracks/qmc/solutions/no-negative-vibes/oracle/exterior_candidates.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_candidates.py
git commit -m "feat: add fixed exterior candidate grammars"
```

---

### Task 3: Transform library and induced-gauge novelty flag

**Files:**

- Modify:
  `tracks/qmc/solutions/no-negative-vibes/oracle/exterior_cone.py`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_cone.py`

**Interfaces:**

- Produces:

  ```python
  def transform_library(
      *,
      size: int,
      family: str,
      seed: int,
  ) -> dict[int, tuple[tuple[str, np.ndarray], ...]]
  def induced_exterior_residual(
      certificate: Mapping[str, object],
      one_particle_transform: np.ndarray,
  ) -> float
  ```

- Families are exactly:
  `signed`, `hadamard`, `unimodular`, `klein-block`.

- [ ] **Step 1: RED tests**

Require deterministic ordering, invertibility, correct dimensions for every
grade, signed controls, normalized Hadamard blocks, exact integer unimodular
determinants `+1/-1`, and stable seed dependence. Test an explicitly induced
certificate with residual below `1e-12` and an independently perturbed
grade-2 transform with residual above `1e-4`.

- [ ] **Step 2: Run and commit RED**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_cone.py -q
git add tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_cone.py
git commit -m "test: specify exterior transform libraries"
```

- [ ] **Step 3: Implement and run GREEN**

Cap each grade/family library at 64 transforms. Canonicalize each transform by
normalizing the first nonzero entry in every column positive when that does
not change the declared family. Store `induced_residual` and
`induced_from_one_particle = residual <= 1e-10` in the certificate.

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_cone.py -q
```

- [ ] **Step 4: Commit**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/exterior_cone.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_cone.py
git commit -m "feat: search noninduced exterior gauges"
```

---

### Task 4: Early-stop candidate screening and manifest

**Files:**

- Create:
  `tracks/qmc/solutions/no-negative-vibes/oracle/exterior_scan.py`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_scan.py`

**Interfaces:**

- Produces:

  ```python
  def screen_candidate(
      card: Mapping[str, object],
      *,
      histories: int,
      depths: tuple[int, ...],
      scales: tuple[float, ...],
      tolerance: float,
      transform_family: str,
  ) -> dict[str, object]
  def shard_owner(candidate_id: str, *, shards: int = 76) -> int
  def split_run_spec(
      run_spec: Mapping[str, object],
      *,
      shards: int = 76,
  ) -> tuple[dict[str, object], ...]
  def run_spec(path: str | Path) -> dict[str, int]
  ```

- Reuses `oracle.weights.classify_product` without modification.
- CLI:

  ```text
  python -m oracle.exterior_scan <shard-run-spec.json>
  ```

- [ ] **Step 1: RED tests**

Require:

- owner is `int(candidate_id[:16],16) % 76`;
- all planned cells appear in exactly one shard;
- an injected first negative stops after one history;
- complex stops immediately;
- uncertain stops and writes `uncertain-high-precision`;
- a zero-failure path returns one of
  `survivor-exterior-certificate` or `survivor-no-certificate`;
- counts sum to `tested_histories`;
- the first failure contains word indices, depth, scale, phase, margin, and
  serialized factors/generators;
- manifest has every field in the design contract;
- atomic `.json.tmp` files do not remain after success;
- an existing success manifest is reused;
- operational exceptions write `operational-error` and do not masquerade as
  scientific rejection.

- [ ] **Step 2: Run and commit RED**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_scan.py -q
git add tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_scan.py
git commit -m "test: specify early-stop exterior screening"
```

- [ ] **Step 3: Implement minimal runner**

The deterministic word order is:

1. alternating every ordered noncommuting atom pair;
2. repeated single-atom words;
3. hash-seeded uniform words.

For each scale, precompute every atom once. Before direct histories, run
structure/transpose/noncommutator/one-slice gates. After direct zero-failure,
run `common_transform_certificate`; do not search a certificate for rejected
or uncertain candidates.

- [ ] **Step 4: GREEN and commit**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_scan.py \
  tests/test_exterior_candidates.py tests/test_exterior_cone.py \
  tests/test_weights.py -q
git add tracks/qmc/solutions/no-negative-vibes/oracle/exterior_scan.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_scan.py
git commit -m "feat: add early-stop exterior screening"
```

---

### Task 5: Stage-1 protocol and 76-way shard generation

**Files:**

- Create:
  `tracks/qmc/solutions/no-negative-vibes/protocols/exterior-cone-throughput-v1/axes.json`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/protocols/exterior-cone-throughput-v1/settings.json`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/protocols/exterior-cone-throughput-v1/provenance.json`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/protocols/exterior-cone-throughput-v1/README.md`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_scan.py`

**Interfaces:**

- `axes.json`:

  ```json
  {
    "template": [
      "sparse4-pair2-loop",
      "sparse6-pair2-degree3",
      "sparse8-pair2-two-loop",
      "graded4-pair2-bicoupled",
      "graded6-pair2-overlap",
      "graded8-pair3-overlap",
      "blockcirc4-pair2",
      "blockcirc6-pair2",
      "blockcirc8-pair3"
    ],
    "transform_family": [
      "signed", "hadamard", "unimodular", "klein-block"
    ],
    "seed": {"start": 0, "stop": 256, "step": 1}
  }
  ```

The README command expands the compact seed range to a literal temporary
axes JSON before calling existing `scripts/parameter_scan.py plan`; the
versioned compact form remains human-reviewable.

- `settings.json`:

  ```json
  {
    "stage": 1,
    "histories": 64,
    "depths": [2, 3, 4],
    "scales": [0.25, 1.0, 3.0],
    "tolerance": 1e-10,
    "shards": 76,
    "progress_every": 16
  }
  ```

- [ ] **Step 1: RED protocol tests**

Require exact keys/values, nine templates, four transform families, 256
seeds, resulting candidate count `9*4*256 = 9216`, exact stage settings, and
every shard count differing from the mean by at most 25%.

- [ ] **Step 2: Run and commit RED**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_scan.py -q
git add tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_scan.py
git commit -m "test: specify exterior throughput protocol"
```

- [ ] **Step 3: Write protocol and README**

The README contains exact plan, split, smoke, execute, resume, collect, and
hash commands. Provenance pins the design commit, candidate grammars, weight
oracle, claim `"discovery-only-zero-failure-is-not-proof"`, machine shard
ranges, and organizer non-touch boundary.

- [ ] **Step 4: GREEN and commit**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_scan.py -q
git add tracks/qmc/solutions/no-negative-vibes/protocols/exterior-cone-throughput-v1 \
        tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_scan.py
git commit -m "protocol: preregister exterior throughput stage 1"
```

---

### Task 6: Freeze, dual-host smoke, and launch Stage 1

**Files:**

- Modify:
  `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Modify only for a new reusable lesson:
  `tracks/qmc/solutions/no-negative-vibes/docs/RESEARCH_OPERATIONS.md`
- Create ignored:
  `.superpowers/sdd/2026-07-29-exterior-cone-throughput/stage-1-report.md`

**Interfaces:**

- Produces ignored run tree:
  `tracks/qmc/results/no-negative-vibes/exterior-cone-throughput-v1/stage-1/`
- Produces 76 shard run specs and one manifest per candidate.

- [ ] **Step 1: Candidate verification**

Run WSL focused/full and CPU focused tests at one exact clean candidate.
Create a complete bundle, verify/hash it locally/WSL/CPU, and require exact
SHA equality. Review only the new modules/protocol for secret paths,
candidate determinism, early stop, oracle reuse, and manifest completeness.

- [ ] **Step 2: One-cell smokes**

Run one WSL-owned 4-mode cell and one CPU-owned 8-mode cell with histories
`4`, depths `[2]`, scales `[1.0]`. Require terminal manifests, no operational
error, correct source commit, correct shard owner, and matching direct replay.

- [ ] **Step 3: Commit/push the frozen scientific source**

Append pre-freeze implementation/smoke attempts to tracked Markdown, commit,
repeat candidate verification if tracked files changed, then push the exact
verified source to the shared branch. Record post-freeze evidence only in the
ignored stage report.

- [ ] **Step 4: Launch disjoint shard sets**

WSL:

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
printf '%s\n' shard-{00..13}.json |
  xargs -P 14 -n 1 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python \
  -m oracle.exterior_scan
```

CPU:

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
printf '%s\n' shard-{14..75}.json |
  xargs -P 62 -n 1 \
  /home/jzb/miniforge3/envs/quantum-harness/bin/python \
  -m oracle.exterior_scan
```

Use absolute shard paths in the actual command. Detached wrappers write
status last. Do not launch the same shard on both hosts.

- [ ] **Step 5: Monitor without duplication**

Poll manifest counts and process status. Retry only
`operational-error`/missing shards. A scientific negative is terminal and
never retried with a new seed under the same candidate id.

---

### Task 7: Collect, learn, and automatically promote survivors

**Files:**

- Create:
  `tracks/qmc/solutions/no-negative-vibes/oracle/exterior_report.py`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_report.py`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Modify when applicable:
  `tracks/qmc/solutions/no-negative-vibes/docs/RESEARCH_OPERATIONS.md`

**Interfaces:**

- Produces:

  ```python
  def summarize_round(run_dir: str | Path) -> dict[str, object]
  def grammar_weights(summary: Mapping[str, object]) -> dict[str, float]
  def promoted_candidates(
      summary: Mapping[str, object],
      *,
      fraction: float = 0.001,
  ) -> list[str]
  ```

- [ ] **Step 1: RED tests**

Fixture manifests must prove:

- failed/missing/operational cells are never omitted;
- exact/robust negative subfamilies receive zero exploit weight;
- failure before depth 4 halves the prior weight;
- distinct noncommuting survivors double it;
- 20% total exploration mass remains uniformly spread over nonclosed
  grammars;
- promotion uses exterior certificate first, then worst margin, then
  candidate id;
- at least one candidate is promoted when survivors exist;
- no candidate is promoted when all fail.

- [ ] **Step 2: Implement, GREEN, and commit**

Reuse `scripts/parameter_scan.py collect`; do not implement another generic
CSV collector. `exterior_report.py` consumes the assembled manifests/CSV and
writes a JSON summary plus Markdown table.

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_report.py -q
git add tracks/qmc/solutions/no-negative-vibes/oracle/exterior_report.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_report.py
git commit -m "feat: adapt exterior search from round evidence"
```

- [ ] **Step 3: Record Stage 1 and launch Stage 2**

Append exact counts, runtimes, first-failure distribution, survivors,
certificate counts, known controls, machine split, and strategy changes to
Markdown. Stage 2 uses only promoted candidate cards with histories `1024`,
depths `[4,8,16]`, scales `[0.5,1.0,2.0,4.0]`. Freeze a new run id and source
commit; do not mutate Stage 1 manifests.

---

### Task 8: Second-tranche grammars during Stage 1 compute

**Files:**

- Modify:
  `tracks/qmc/solutions/no-negative-vibes/oracle/exterior_candidates.py`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_candidates.py`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/protocols/exterior-cone-throughput-v1/README.md`

**Interfaces:**

- Adds templates:

  ```text
  clifford4-pair2
  clifford8-pair3
  palindrome4-xyxt
  palindrome6-xyxt
  bdg8-pair2
  bdg12-pair2
  ```

- [ ] **Step 1: RED tests**

Require Clifford anticommutator conventions, finite palindromic factor
decomposition, BdG particle-hole convention, transpose/conjugate closure,
determinant/Fock single-slice agreement where applicable, locality, and
noncommutativity.

- [ ] **Step 2: Implement and verify independently**

Do not change the already frozen Stage 1 source. Develop on the topic branch
while Stage 1 runs its frozen bundle. Commit the new grammars only after
focused/full tests and independent review.

- [ ] **Step 3: Register only in a new run**

Add the templates to `exterior-cone-throughput-v2`, not the immutable v1
Stage 1 axes. Launch them as an exploration tranche after their own smoke.

---

### Task 9: Pressure screen, exact reconstruction, and physical route

**Files:**

- Modify:
  `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Create only when a survivor exists:
  `tracks/qmc/solutions/no-negative-vibes/docs/EXTERIOR_CONE_CANDIDATE_RESULTS.md`

**Interfaces:**

- Consumes Stage 2 promoted candidates.
- Produces a Stage 3 result or a documented closed round.

- [ ] **Step 1: Stage 3**

Run histories `16384`, depths `[8,16,32]`, scales
`[0.5,1.0,2.0,4.0]` plus the weakest-margin targeted scale. Replay every
uncertainty and the ten smallest-margin histories at high precision using the
existing oracle.

- [ ] **Step 2: Exact certificate**

For each top survivor, reconstruct every selected transform over integers,
rationals, or a declared algebraic field. Verify every transformed atom
entry exactly and prove the compound trace identity. If exact reconstruction
fails, retain only `survivor-no-certificate`.

- [ ] **Step 3: Novelty audit**

Reject or label controls for induced TN gauge, odd monomial/P0, common
split/contraction/expansion metric, compact orthogonal, Kramers, Majorana
reflection, and abelian diagonal Gaussian channels. Do not infer novelty from
a nonzero site-basis loop alone.

- [ ] **Step 4: Reverse physical construction**

Use positive coefficients and transpose/conjugate-paired Gaussian atoms to
write a local CT-INT/CT-AUX vertex. Expand constant, quadratic, quartic, and
higher-body terms exactly. A discrete-time HS claim requires an exact
finite-field exponential identity; otherwise label it continuous-time.
Any free drift must share the same arbitrary-depth certificate.

- [ ] **Step 5: Loop**

Record success/failure in Markdown, update grammar weights, create a new
immutable protocol/run id, commit/push, and repeat until a paper candidate
passes all mathematical, physical, novelty, and reproducibility gates.
