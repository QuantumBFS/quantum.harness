# Issue 128 Final Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a reviewer-ready Issue 128 package that freezes the certified 4.050498x result, adds exact data summaries and a polished PDF, and updates the existing PR without claiming an unproved fivefold certificate.

**Architecture:** The committed certificate and exact sidecars remain the scientific source of truth. A small standard-library Python packager checks frozen hashes, projects exact fields into JSON/text, captures verifier evidence, and binds release files with SHA-256. LaTeX presents the same values for human review; remote publication happens only after an allowlisted audit.

**Tech Stack:** Python 3.11+, pytest, existing `trottercert`, LaTeX/latexmk, BibTeX, Poppler, Git, GitHub CLI.

## Global Constraints

- Official result: 97 steps, 2,911 groups, exact ratio `11791/2911`.
- Baseline: 393 steps and 11,791 groups.
- The 97-step exact-rational error bound passes `1e-6`; the 96-step bound fails.
- Main certificate SHA-256: `0a09623ce3b292a3637065c870fb3153bbdcddce30aef968565c4db3ddfc7201`.
- D4 sidecar SHA-256: `a397414bb0229fb1ebdb38798aa781fb89dbb9d5cdbed94c7cd2e9120da62718`.
- D5 is follow-up evidence only; 78 steps and fivefold are not certified.
- Use standard `article` because no challenge template exists.
- Never touch the dirty main workspace, use `git add -A`, force-push, or create a competing PR.

---

### Task 1: Restore and Validate Exact D5 Follow-up Evidence

**Files:**
- Create: `src/trottercert/cubic_field.py`
- Create: `src/trottercert/cubic_local.py`
- Create: `src/trottercert/support_groups.py`
- Create: `scripts/build_d5_certificate.py`
- Create: `tests/test_cubic_field.py`
- Create: `tests/test_cubic_local.py`
- Create: `tests/test_support_groups.py`
- Generate: `certificates/issue128-d5-groups.json.gz`

**Interfaces:**
- Consumes: the existing four-fragment Heisenberg symplectic evaluator and exact rational intervals.
- Produces: exact `Q(alpha)` Suzuki coefficients (`alpha^3=4`), an exact D5 Pauli density, deterministic same-support groups, canonical gzip bytes, and solver-free verification.

- [ ] Run focused tests:

```bash
pytest -q tests/test_cubic_field.py tests/test_support_groups.py
```

- [ ] Build with deterministic discovery and hard regression gates:

```bash
env PYTHONHASHSEED=0 PYTHONPATH=src \
  python scripts/build_d5_certificate.py
```

Require 605,832 terms, 123,106 groups, exact site bound
`44948270001027856175670154896253/4000000000000000000000000000000`, and canonical SHA-256
`c5e8968a93b4497b41fe42c0e364324388272e183e1fcd20a536bc988f5361dd`.

- [ ] Verify from disk without discovery:

```bash
PYTHONPATH=src python scripts/build_d5_certificate.py --verify-only
```

- [ ] Stage only the seven source/test files and the sidecar; commit as a single exact-follow-up unit.

### Task 2: Deterministic Delivery Packager

**Files:**
- Create: `scripts/package_delivery.py`
- Create: `scripts/__init__.py`
- Create: `tests/test_delivery_package.py`
- Generate: `artifacts/issue128-summary.json`
- Generate: `artifacts/issue128-summary.txt`
- Generate: `artifacts/verification-transcript.txt`

**Interfaces:**
- Produces: `build_summary(root)`, `render_summary_text(summary)`, `capture_verification(root)`, `write_sha_manifest(root)`, and CLI modes `--manifest`/`--check`.

- [ ] Write tests that require exact 393/97 steps, 11,791/2,911 groups,
  frozen hashes, exact ratio, 97/96 boundary, D4/D5 counts, and
  `fivefold_followup.status == "not_certified"`.
- [ ] Confirm the tests fail before the module exists.
- [ ] Implement exact invariant checks and canonical `sort_keys=True` JSON.
- [ ] Render a text summary containing `FIVEFOLD STATUS: NOT CERTIFIED` and
  `No 78-step global error certificate is claimed or supplied.`
- [ ] Capture stdout/stderr and exit codes for:

```bash
PYTHONPATH=src python scripts/verify.py certificates/issue128-certificate.json
PYTHONPATH=src python scripts/build_d5_certificate.py --verify-only
```

- [ ] Run `pytest -q tests/test_delivery_package.py`, then the full default suite.
- [ ] Explicitly stage and commit the packager and its tests.

### Task 3: Technical Report Source

**Files:**
- Create: `docs/report/issue128-technical-report.tex`
- Create: `docs/report/references.bib`
- Modify: `../README.md` (team README relative to the Issue 128 directory).

**Interfaces:**
- Consumes: exact certificate/summary values and primary-source bibliography metadata.
- Produces: a self-contained 6--8 page report and reviewer navigation links.

- [ ] Verify primary metadata for Childs--Su--Tran--Wiebe--Zhu and
  Schubert--Mendl from their primary pages.
- [ ] Write the benchmark/result table with steps, groups, bond propagators,
  CNOT upper bounds, exact ratio, and exact integer boundary.
- [ ] Explain the full-word logarithm, Dynkin--Specht--Wever projection,
  concrete Pauli combination, D4 anticommuting certificate, local Heisenberg
  lemma, right-generator ledger, tail, verifier, and 2x2 cross-check.
- [ ] Add a fivefold feasibility section that reports D5 evidence and names
  the unresolved D4/D8 gates without any affirmative 5x claim.
- [ ] Add copy-paste reproduction commands and links to PDF/JSON/TXT/transcript/manifest.
- [ ] Commit report sources and README links explicitly.

### Task 4: Build and Visually Audit the PDF

**Files:**
- Generate: `docs/report/output/issue128-technical-report.pdf`

- [ ] Generate summaries/transcript:

```bash
PYTHONPATH=src python scripts/package_delivery.py
```

- [ ] Compile:

```bash
cd docs/report
/Library/TeX/texbin/latexmk -pdf -interaction=nonstopmode \
  -halt-on-error -outdir=output issue128-technical-report.tex
```

- [ ] Reject fatal LaTeX errors, undefined references/citations, missing
  glyphs, and visible overfull boxes.
- [ ] Require 6--8 nonblank pages and selectable text via `pdfinfo` and
  `pdftotext`.
- [ ] Render every page at 144 DPI with `pdftoppm`; inspect each PNG for
  clipping, overlap, broken tables, and inconsistent page furniture.
- [ ] Correct source and repeat compilation/rendering until the latest images
  have zero visible defects.

### Task 5: Bind Artifacts and Complete the Local Audit

**Files:**
- Generate: `artifacts/SHA256SUMS`

- [ ] Bind the PDF, summaries, transcript, main certificate, D4/D5 sidecars,
  small cross-check, and report sources.
- [ ] Run `shasum -a 256 -c artifacts/SHA256SUMS` and require every line `OK`.
- [ ] Run:

```bash
pytest -q
PYTHONPATH=src python scripts/verify.py certificates/issue128-certificate.json
PYTHONPATH=src python scripts/build_d5_certificate.py --verify-only
PYTHONPATH=src python scripts/package_delivery.py --check
```

- [ ] Scan for unsupported fivefold language and placeholder/tool tokens.
- [ ] Run `git diff --check c550a6b..HEAD` and audit every changed path.
- [ ] Require a clean worktree after explicitly staging/committing final artifacts.

### Task 6: Fast-forward the Existing PR

**Remote target:** `JunkaiWang-TheoPhy:codex/issue-128-trotter-certificate`

- [ ] Fetch the fork branch and re-read PR #248 head SHA/state.
- [ ] Require `git merge-base --is-ancestor origin/codex/issue-128-trotter-certificate HEAD`.
- [ ] Push `HEAD:codex/issue-128-trotter-certificate` without force.
- [ ] Update PR #248 body with the exact result table, innovation list,
  artifact links, commands, test/verifier results, and visible fivefold non-claim.
- [ ] Fetch again and require remote SHA equals audited local SHA.
- [ ] Report the PDF/data paths, final commit, PR URL, validation evidence,
  achieved 4.050498x ratio, and external maintainer review/merge condition.

## Self-Review

- Every requested deliverable maps to Tasks 1--6.
- Every numerical claim is either an exact certificate field or explicitly
  marked conditional follow-up arithmetic.
- The PDF is not accepted based on compilation alone; every page is rendered
  and inspected.
- The remote write is downstream of all proof, artifact, visual, hash, diff,
  and drift gates.
