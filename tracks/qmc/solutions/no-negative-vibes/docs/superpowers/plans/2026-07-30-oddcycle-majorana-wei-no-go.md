# Oddcycle Majorana/Wei No-Go Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a solver-independent exact certificate that excludes Wei's full ten-Majorana contraction-semigroup sufficient condition for the final oddcycle alphabet, including arbitrary fixed complex orthogonal Majorana basis changes.

**Architecture:** Pull every possible Wei contraction metric into the number-conserving Nambu representation.  Reuse the frozen exact Gordan--Stiemke dual to force any nonstrict contraction to the group boundary, prove the four-letter commutant is scalar by exact rational rank, and reject the only surviving boundary form with the orthogonal-complex-structure compatibility identity.

**Tech Stack:** Python 3, SymPy exact arithmetic, existing frozen oddcycle dual, pytest, JSON.

## Global Constraints

- Run every Python command and every scientific/exact calculation on WSL, never on local Windows.
- Do not run an SDP, eigensolver, random sampler, parameter scan, or logarithm.
- Reuse `exact_no_common_metric_certificate()`; do not duplicate its large rational multipliers.
- Keep the current narrow novelty wording unless every exact acceptance gate passes.
- Do not repeat the completed 12,325-cell frontier or 6,266-cell dual scan.
- Preserve all existing WSL worktrees and results.

---

## File structure

- Create `oracle/oddcycle_majorana_wei_audit.py`: exact Nambu reduction,
  commutant rank, boundary form, compatibility identity, and JSON summary.
- Create `tests/test_oddcycle_majorana_wei_audit.py`: one publication-gate
  regression.
- Modify `docs/ODDCYCLE_PAPER_DRAFT.md`: upgrade the theorem and scope only
  after the exact test passes.
- Modify `docs/ODDCYCLE_CHALLENGE_AUDIT.md`: update the requirement table and
  remaining blockers.
- Modify `docs/EXPERIMENT_LOG.md`: record RED/GREEN evidence and reusable
  algebraic lessons.
- Modify `oracle/oddcycle_final_certificate.py`: add the new exact gate to the
  main one-command publication certificate.
- Modify `tests/test_oddcycle_final_certificate.py`: require the new gate.
- Create `protocols/oddcycle-final-certificate-v1/majorana-wei-result.json`
  only from a clean WSL replay at the committed source SHA.

### Task 1: Publication-gate test

**Files:**
- Create: `tracks/qmc/solutions/no-negative-vibes/tests/test_oddcycle_majorana_wei_audit.py`

**Interfaces:**
- Consumes: future
  `oracle.oddcycle_majorana_wei_audit.majorana_wei_no_go_summary()`.
- Produces: the exact public schema and acceptance values used by the final
  certificate.

- [ ] **Step 1: Write the failing test**

```python
import importlib


def test_exact_nambu_reduction_excludes_full_wei_contraction():
    audit = importlib.import_module(
        "oracle.oddcycle_majorana_wei_audit"
    )

    result = audit.majorana_wei_no_go_summary()

    assert result["status"] == "exact-no-wei-contraction-certificate"
    assert result["alphabet"] == {
        "dimension": 5,
        "points": ("1/1000", "4/5"),
        "letter_count": 4,
        "determinant": 8,
    }
    assert result["dual"] == {
        "exact_cancellation": True,
        "normalization_trace": {"numerator": 1, "denominator": 1},
        "positive_definite_multipliers": 4,
        "nonstrict_gaps_forced_to_zero": True,
    }
    assert result["commutant"] == {
        "ambient_dimension": 25,
        "constraint_rank": 24,
        "nullity": 1,
        "scalar_only": True,
    }
    assert result["boundary"] == {
        "diagonal_blocks_zero": True,
        "off_diagonal_block": "k*I_5",
    }
    assert result["compatibility"] == {
        "wei_sign": -1,
        "boundary_sign": 1,
        "compatible": False,
    }
    assert len(result["exact_certificate_sha256"]) == 64
```

- [ ] **Step 2: Copy the test to the preserved WSL verification clone**

Run from PowerShell only as a file-transfer operation:

```powershell
wsl.exe -e bash -lc 'cp /mnt/c/Users/45518/Documents/quantum_harness/no-negative-vibes-collab/.worktrees/representation-cones/tracks/qmc/solutions/no-negative-vibes/tests/test_oddcycle_majorana_wei_audit.py /home/zibojin/code/nnv-final-verify/tracks/qmc/solutions/no-negative-vibes/tests/'
```

- [ ] **Step 3: Run the RED test on WSL**

Run:

```bash
cd /home/zibojin/code/nnv-final-verify/tracks/qmc/solutions/no-negative-vibes
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python -m pytest -q \
  tests/test_oddcycle_majorana_wei_audit.py
```

Expected: one failure inside the test with
`ModuleNotFoundError: oracle.oddcycle_majorana_wei_audit`.

- [ ] **Step 4: Commit only after Task 2 reaches GREEN**

Do not create a RED-only commit on the shared branch.

### Task 2: Exact Nambu no-go certificate

**Files:**
- Create: `tracks/qmc/solutions/no-negative-vibes/oracle/oddcycle_majorana_wei_audit.py`
- Test: `tracks/qmc/solutions/no-negative-vibes/tests/test_oddcycle_majorana_wei_audit.py`

**Interfaces:**
- Consumes:
  `oddcycle_metric_dual.exact_no_common_metric_certificate`,
  `oddcycle_path_metric.EXACT_POINTS`, and
  `oddcycle_final_certificate._source_commit`.
- Produces:
  `exact_main_alphabet() -> tuple[sp.ImmutableMatrix, ...]`,
  `exact_commutant_certificate() -> dict[str, object]`,
  `exact_nambu_boundary_certificate() -> dict[str, object]`, and
  `majorana_wei_no_go_summary() -> dict[str, object]`.

- [ ] **Step 1: Construct the exact alphabet**

Use this implementation shape:

```python
def _base_matrix(p: str) -> sp.ImmutableMatrix:
    return sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, sp.Rational(p), 0],
            [0, 0, 0, 1, 1],
            [0, 0, -1, 0, 1],
        ]
    )


def exact_main_alphabet() -> tuple[sp.ImmutableMatrix, ...]:
    bases = tuple(_base_matrix(point[0]) for point in EXACT_POINTS)
    return tuple(atom for base in bases for atom in (base, base.T))
```

Assert internally that there are four distinct \(5\times5\) matrices and
every determinant equals eight.

- [ ] **Step 2: Build the exact commutant system**

For each standard basis matrix \(E_{ab}\), make one column by stacking every
entry of

```python
E_ab * atom - atom * E_ab
```

for all four atoms.  Form the integer/rational constraint matrix from the 25
columns and compute its exact SymPy rank.  Return:

```python
{
    "ambient_dimension": 25,
    "constraint_rank": rank,
    "nullity": 25 - rank,
    "scalar_only": rank == 24,
}
```

Also verify directly that the identity matrix is in the nullspace.  Raise
`RuntimeError` unless rank is exactly 24.

- [ ] **Step 3: Replay the frozen dual**

Call:

```python
dual = exact_no_common_metric_certificate()
```

Require its exact status, exact zero cancellation, trace one, and four
positive-definite multipliers.  Convert those gates to:

```python
{
    "exact_cancellation": True,
    "normalization_trace": {"numerator": 1, "denominator": 1},
    "positive_definite_multipliers": 4,
    "nonstrict_gaps_forced_to_zero": True,
}
```

The last field is a theorem-level consequence of positive-semidefinite gaps,
positive-definite multipliers, and zero trace sum; document that implication
in the function docstring.

- [ ] **Step 4: Verify the Nambu compatibility sign**

Use real symbols `u,v`, `k=u+I*v`, and the two-dimensional coefficient
matrices

```python
omega = sp.ImmutableMatrix([[0, 1], [1, 0]])
boundary = sp.ImmutableMatrix([[0, k], [sp.conjugate(k), 0]])
product = sp.simplify(boundary * omega * boundary.T)
```

Require:

```python
product == sp.expand(u**2 + v**2) * omega
```

Return boundary sign `+1`, Wei sign `-1`, and `compatible=False`.  Explain in
the docstring that tensoring these coefficient matrices with \(I_5\) gives
the full ten-dimensional identity.

- [ ] **Step 5: Assemble the machine-readable summary**

Hash only exact, environment-independent fields:

```python
payload = {
    "alphabet": alphabet_summary,
    "dual": dual_summary,
    "commutant": commutant_summary,
    "boundary": boundary_summary,
    "compatibility": compatibility_summary,
}
digest = hashlib.sha256(
    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
```

Return schema
`oddcycle-majorana-wei-no-go-v1`, source commit, status
`exact-no-wei-contraction-certificate`, payload fields, exact digest, Python
and SymPy versions, and wall time.  Add a `python -m` JSON CLI.

- [ ] **Step 6: Copy the module to WSL and run GREEN**

Run the same environment-limited command from Task 1.  Expected:

```text
1 passed
```

- [ ] **Step 7: Run focused regressions on WSL**

Run:

```bash
python -m pytest -q \
  tests/test_oddcycle_majorana_wei_audit.py \
  tests/test_oddcycle_metric_dual.py \
  tests/test_oddcycle_path_metric.py \
  tests/test_oddcycle_pair_physical.py \
  tests/test_oddcycle_final_certificate.py \
  tests/test_oddcycle_robust_certificate.py
```

Expected: zero failures.

- [ ] **Step 8: Commit**

```bash
git add \
  tracks/qmc/solutions/no-negative-vibes/oracle/oddcycle_majorana_wei_audit.py \
  tracks/qmc/solutions/no-negative-vibes/tests/test_oddcycle_majorana_wei_audit.py
git commit -m "feat(qmc): certify oddcycle outside Wei contraction class"
git push shared work/zibo/representation-cones
```

### Task 3: Integrate the publication gate

**Files:**
- Modify: `tracks/qmc/solutions/no-negative-vibes/oracle/oddcycle_final_certificate.py`
- Modify: `tracks/qmc/solutions/no-negative-vibes/tests/test_oddcycle_final_certificate.py`

**Interfaces:**
- Consumes:
  `majorana_wei_no_go_summary()`.
- Produces:
  final gate key `outside_wei_majorana_sufficient_class`.

- [ ] **Step 1: Add a failing final-certificate assertion**

Extend the expected gates with:

```python
"outside_wei_majorana_sufficient_class": True,
```

and require the compact novelty block:

```python
assert result["majorana_wei"] == {
    "commutant_nullity": 1,
    "boundary_sign": 1,
    "wei_sign": -1,
}
```

- [ ] **Step 2: Run the final-certificate test on WSL**

Expected: FAIL because the gate and block are absent.

- [ ] **Step 3: Add the gate**

Import and call `majorana_wei_no_go_summary()`.  Set the gate true only when
the returned status is exactly
`exact-no-wei-contraction-certificate`.  Include the three compact values
above in the exact digest payload so tampering changes the certificate hash.

- [ ] **Step 4: Run both exact tests**

```bash
python -m pytest -q \
  tests/test_oddcycle_majorana_wei_audit.py \
  tests/test_oddcycle_final_certificate.py
```

Expected: two tests pass.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/qmc/solutions/no-negative-vibes/oracle/oddcycle_final_certificate.py \
  tracks/qmc/solutions/no-negative-vibes/tests/test_oddcycle_final_certificate.py
git commit -m "feat(qmc): add Majorana Wei publication gate"
git push shared work/zibo/representation-cones
```

### Task 4: Upgrade the paper only after GREEN

**Files:**
- Create: `tracks/qmc/solutions/no-negative-vibes/docs/ODDCYCLE_MAJORANA_WEI_AUDIT.md`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/ODDCYCLE_PAPER_DRAFT.md`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/ODDCYCLE_CHALLENGE_AUDIT.md`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Modify: `D:/project/quantum_harness/tracks/qmc/solutions/no-negative-vibes/AGENT_HANDOFF.md` locally only

**Interfaces:**
- Consumes: exact JSON from Tasks 2 and 3.
- Produces: paper-level proposition and bounded novelty claim.

- [ ] **Step 1: Write the proof note**

Copy the algebraic derivation from the approved design, add the exact replay
command, and cite the primary sources:

- Wei et al., *Phys. Rev. Lett.* **116**, 250601 (2016),
  arXiv:1601.01994;
- Li, Jiang, and Yao, *Phys. Rev. Lett.* **117**, 267002 (2016),
  arXiv:1601.05780;
- Wei, *Phys. Rev. B* **110**, 075146 (2024),
  arXiv:1712.09412v3.

- [ ] **Step 2: Upgrade the paper scope**

Replace statements that the Wei/Majorana audit is open with:

> The final alphabet lies outside the sufficient class defined by Wei's
> fixed \(J_1,J_2\) contraction conditions, even after a fixed complex
> orthogonal Majorana basis change.

Retain:

> This does not exclude unrelated fermion-bag, loop, worldline, or future
> sign-free mechanisms and is not a classification of all sign-free QMC.

- [ ] **Step 3: Record the exact experiment**

Append the source commit, test commands and counts, certificate SHA-256,
proof boundary, and the reusable Nambu-pullback argument to
`EXPERIMENT_LOG.md` and the private handoff.  Never stage the private handoff.

- [ ] **Step 4: Static-check and commit**

On Windows, run only:

```powershell
git diff --check
git status --short
```

Then:

```bash
git add tracks/qmc/solutions/no-negative-vibes/docs
git commit -m "docs(qmc): prove Majorana Wei novelty boundary"
git push shared work/zibo/representation-cones
```

### Task 5: Clean archival replay

**Files:**
- Create: `tracks/qmc/solutions/no-negative-vibes/protocols/oddcycle-final-certificate-v1/majorana-wei-result.json`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`

**Interfaces:**
- Consumes: clean committed source from Tasks 2--4.
- Produces: submission-commit JSON and SHA-256.

- [ ] **Step 1: Create a preserved clean WSL worktree**

```bash
cd /home/zibojin/code/nnv-final-verify
git fetch shared work/zibo/representation-cones
SOURCE_SHA="$(git rev-parse shared/work/zibo/representation-cones)"
git worktree add /home/zibojin/code/nnv-wei-final-verify "$SOURCE_SHA"
```

Record the full `SOURCE_SHA`; do not infer or abbreviate it.

- [ ] **Step 2: Run the exact CLI and tests**

```bash
cd /home/zibojin/code/nnv-wei-final-verify/tracks/qmc/solutions/no-negative-vibes
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python \
  -m oracle.oddcycle_majorana_wei_audit \
  > /home/zibojin/code/oddcycle-majorana-wei-result.json
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python -m pytest -q \
  tests/test_oddcycle_majorana_wei_audit.py \
  tests/test_oddcycle_final_certificate.py \
  tests/test_oddcycle_robust_certificate.py
sha256sum /home/zibojin/code/oddcycle-majorana-wei-result.json
```

Require zero test failures and exact `source_commit` equality.

- [ ] **Step 3: Archive, commit, and verify remote**

Copy the JSON into the protocol path, record its SHA-256 in the experiment
log, run `git diff --check`, commit, push, and verify with:

```bash
git ls-remote shared refs/heads/work/zibo/representation-cones
```

The remote SHA must equal local `git rev-parse HEAD`.
