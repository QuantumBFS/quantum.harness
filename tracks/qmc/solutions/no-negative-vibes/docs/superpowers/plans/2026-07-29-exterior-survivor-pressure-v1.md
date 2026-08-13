# Exterior Survivor Pressure v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse the reviewed thin-scan infrastructure to run an immutable,
resumable depth-5..8 exhaustive screen over only the 1,713 Stage-1 survivors.

**Architecture:** Generalize `oracle.exterior_thin_scan` with explicit,
hash-bound protocol depths and a parent-survivor planning entrypoint while
retaining the exact Stage-1 defaults.  The same runner validates, executes,
resumes, and collects both protocols; Stage-2 artifacts have a new run id and
never mutate Stage 1.

**Tech Stack:** Python 3.11, NumPy, pytest, existing exact candidate cards,
existing determinant oracle, Git bundles, WSL/CPU plain SSH.

## Global Constraints

- Design:
  `docs/superpowers/specs/2026-07-29-exterior-survivor-pressure-v1-design.md`.
- Parent run id is exactly `exterior-thin-first-v1`.
- Parent protocol hash is exactly
  `e7d4a3223a383687db462b582f0c675a443a620cc16f74181df5782fbd21aa43`.
- Stage 2 run id is exactly `exterior-survivor-pressure-v1`.
- Depths are exactly `[5,6,7,8]`; the two-atom word count is exactly `472`.
- Select only `survivor-shallow-zero-failure`; uncertain and rejected
  candidates never enter this run.
- Keep Stage-1 default behavior and hashes backward compatible.
- Reuse `oracle.weights.classify_product`; do not modify frozen oracles.
- Stop at the first negative, complex, or uncertain classification.
- Use 76 owners; WSL processes 14 and CPU processes 62; all BLAS threads are
  one.
- Raw results are ignored; every outcome and strategy change is Markdown.
- Do not touch organizer PR #178 or the teammate branch.

---

### Task 1: Parent-bound survivor pressure protocol

**Files:**

- Modify:
  `tracks/qmc/solutions/no-negative-vibes/oracle/exterior_thin_scan.py`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_thin_scan.py`

**Interfaces:**

- Preserve:

  ```python
  def plan_run(
      *,
      run_dir: str | Path,
      source_commit: str,
      run_id: str = "exterior-thin-first-v1",
      smoke_count: int = 4,
      shards: int = 76,
  ) -> dict[str, object]
  ```

- Add:

  ```python
  PRESSURE_DEPTHS = (5, 6, 7, 8)

  def plan_survivor_run(
      *,
      parent_run_dir: str | Path,
      run_dir: str | Path,
      source_commit: str,
      run_id: str = "exterior-survivor-pressure-v1",
      smoke_count: int = 4,
      shards: int = 76,
  ) -> dict[str, object]
  ```

- Extend the CLI with:

  ```text
  python -m oracle.exterior_thin_scan plan-survivors \
    --parent-run-dir <stage-1> \
    --run-dir <stage-2> \
    --source-commit <40-hex> \
    --run-id exterior-survivor-pressure-v1
  ```

- [ ] **Step 1: Write RED tests**

Add tests with hand-built parent fixtures that require:

1. only validated `survivor-shallow-zero-failure` identities are planned;
2. negative, complex, uncertain, missing, stale, duplicate, and unresolved
   operational parent outcomes cannot leak into the survivor set;
3. any nonzero parent missing/stale/duplicate/unresolved count fails planning;
4. parent run id/protocol hash, source/card identity, status, and selection
   tampering fail closed;
5. `mixed_words(2, depths=PRESSURE_DEPTHS)` contains exactly 472 unique words
   in depth-then-lexicographic order and excludes only `(0,...,0)` and
   `(1,...,1)` at each depth;
6. Stage-2 plan/spec/protocol hashes bind depths and parent provenance;
7. a Stage-2 run writes `survivor-pressure-zero-failure` after 472 positives
   and early-stops correctly on negative, complex, or uncertain;
8. Stage-1 plan/spec hashes and focused behavior remain byte-for-byte
   compatible with the existing test fixtures;
9. Stage-2 resume, wrong owner/role, protocol tampering, smoke isolation,
   operational exit code, collection, and promotion fields have the same
   fail-closed guarantees as Stage 1.

- [ ] **Step 2: Run RED**

From the solution directory in WSL:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=. python -m pytest tests/test_exterior_thin_scan.py -q
```

Expected: the new tests fail only because `PRESSURE_DEPTHS`,
`plan_survivor_run`, protocol generalization, or the new CLI/status are
absent.  Record the command, exit code, duration, and expected failure in the
task report.

- [ ] **Step 3: Commit RED**

```bash
git add tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_thin_scan.py
git commit -m "test: specify survivor pressure protocol"
```

- [ ] **Step 4: Implement minimal GREEN**

Make depths, survivor status, and optional parent provenance explicit inputs
to the existing private plan/spec/protocol hashing helpers.  Keep
`plan_run` defaults identical.  `plan_survivor_run` must validate the parent
with the existing collector, require 2,304 terminal results and no
missing/stale/duplicate/unresolved operational candidates, reconstruct every
selected exact card, keep its existing owner, and write a new immutable plan.

`run_spec` derives the word list from the validated spec depths and maps the
zero-failure terminal status from the protocol.  It must not accept arbitrary
depths or statuses that are absent from the hash-bound plan.  Collection must
use the plan's validated depths/status and emit exact survivor identities,
minimum margins, first failures, per-template/dimension counts, and machine
execution evidence without hard-coded depth columns.

- [ ] **Step 5: Run GREEN and regressions**

```bash
PYTHONPATH=. python -m pytest tests/test_exterior_thin_scan.py -q
PYTHONPATH=. python -m pytest \
  tests/test_exterior_candidates.py \
  tests/test_exterior_cone.py \
  tests/test_exterior_thin_scan.py \
  tests/test_weights.py tests/test_scan.py -q
```

Expected: all pass.  Record exact counts and durations in the task report.

- [ ] **Step 6: Commit GREEN**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/exterior_thin_scan.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_exterior_thin_scan.py
git commit -m "feat: add survivor pressure protocol"
```

- [ ] **Step 7: Independent task review**

Review the complete RED..GREEN diff against this brief.  Both spec compliance
and task quality must pass before launch; Important/Critical findings enter
the SDD fix loop.

---

### Task 2: Freeze and dual-host Stage-2 launch

**Files:**

- Modify:
  `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Modify private/untracked:
  `tracks/qmc/solutions/no-negative-vibes/AGENT_HANDOFF.md`

**Interfaces:**

- Produces ignored run tree:
  `tracks/qmc/results/no-negative-vibes/exterior-survivor-pressure-v1/`.

- [ ] **Step 1: Freeze**

Verify the focused launch slice, create a complete bundle at the reviewed
GREEN commit, and require identical SHA-256 plus exact clean source commit on
Windows, WSL, and CPU.

- [ ] **Step 2: Plan and smoke**

Plan from the complete Stage-1 WSL run.  Require exactly 1,713 candidates,
808,536 planned words, 76 disjoint owner shards, and two candidates on each
machine in the isolated smoke namespace.  Run both smokes and require zero
operational errors and matching direct replay.

- [ ] **Step 3: Launch**

Run shards 00--13 with 14 WSL processes and 14--75 with 62 CPU processes.
All BLAS thread variables equal one.  Retry only missing or operational
failures; never retry a scientific terminal result.

- [ ] **Step 4: Collect and learn**

Merge by exact candidate identity without overwrite.  Require 1,713 terminal
manifests and zero missing/stale/duplicate/unresolved operational candidates.
Record exact counts, first-failure depth/word distribution, runtimes,
minimum-margin survivors, machine split, and the next strategy in
`EXPERIMENT_LOG.md` and the private handoff.  Commit and push the tracked
evidence to `work/zibo/representation-cones`.
