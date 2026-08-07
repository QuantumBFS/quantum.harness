# VQETape Submission Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a reviewer-readable, machine-auditable VQETape submission package before the 2026-07-30 20:00 CST deadline and update the existing pull request without overstating the TensorCircuit-NG comparison.

**Architecture:** A reproducible Python builder reads the committed canonical JSON evidence, derives the matched benchmark table, and emits the same claims into TSV, plain text, JSON, Markdown, HTML, and PDF. The PDF is rendered separately for visual QA; the PR README is the stable reviewer entry point.

**Tech Stack:** Python 3.12, standard library, ReportLab 4, pypdf/pdfinfo/pdftoppm for verification, pytest, Git, GitHub CLI.

## Global Constraints

- Preserve the exact matched protocol: open-boundary TFIM, `n=10`, `L=4`, plus initial state, RZZ-then-RX ansatz, seed 33, complex64, RTX 3090.
- Derive performance values from committed JSON; label any Slurm/NVML annotations by their source.
- State the result boundary explicitly: VQETape spatial wins `compile + first + 100 warm` and host RSS, but loses warm runtime and does not establish a device-memory or formal Fig. 2 victory.
- Do not start a new PR. Update the existing `codex/issue-33-vqetape` branch and PR #263.
- Stop all PR updates by 20:00 CST.

---

### Task 1: Build the reproducible submission artifacts

**Files:**
- Create: `scripts/build_submission_report.py`
- Create: `submission/vqetape-matched-benchmark.tsv`
- Create: `submission/submission-status.txt`
- Create: `submission/report.json`
- Create: `submission/vqetape-technical-report.md`
- Create: `submission/report.html`
- Create: `submission/output/pdf/vqetape-technical-report.pdf`
- Create: `submission/artifact-manifest.json`

- [x] Parse the four matched RTX 3090 benchmark JSON files and the Fig. 2 smoke JSON.
- [x] Compute the declared 100-step objective, speed ratios, and host RSS deltas.
- [x] Emit all text and tabular formats from one in-memory evidence model.
- [x] Fail the build if source evidence is absent or correctness tolerances fail.

### Task 2: Verify content and PDF rendering

**Files:**
- Test: `submission/output/pdf/vqetape-technical-report.pdf`
- Test: `submission/artifact-manifest.json`

- [x] Parse all generated JSON and TSV outputs.
- [x] Confirm the PDF page count and extractable text.
- [x] Render every PDF page to PNG and visually inspect for clipping, overlap, missing glyphs, and unreadable tables.
- [x] Re-run the targeted baseline/Fig. 2 tests and static checks.

### Task 3: Update the reviewer entry point

**Files:**
- Modify: `README.md`

- [x] Link the PDF, Markdown report, HTML report, TSV, status text, and manifest.
- [x] Put the measured win and the warm-runtime/device-memory limitations in the first screen.
- [x] Provide one reproducible rebuild command.

### Task 4: Publish the final state

**Files:**
- Modify: existing Git commit history and PR #263 metadata only.

- [x] Review the diff and secret scan.
- [x] Commit with the repository-required trailer.
- [x] Push `codex/issue-33-vqetape` to `JunkaiWang-TheoPhy/quantum.harness`.
- [x] Update the existing upstream PR body with direct artifact links and the honest result matrix.
- [x] Confirm the PR is open, ready for review, mergeable, and points to the pushed commit.
