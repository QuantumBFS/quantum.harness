# MPS Track Stage Project Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render a dated, evidence-backed, self-contained HTML stage report for the MPS track using only results available on 2026-07-30.

**Architecture:** Treat existing run artifacts as immutable inputs, stage only selected figures into a new dated result directory, and encode the narrative as generic `report.json` blocks. Render with the repository's existing report renderer and verify source paths, embedded images, status language, and offline output.

**Tech Stack:** JSON, Markdown, Python 3 standard library, matplotlib, `skills/report/render_report.py`.

## Global Constraints

- Do not launch new scientific compute or cluster jobs.
- Do not overwrite any existing run or result artifact.
- Distinguish engineering verification from scientific completion.
- Use the evidence precedence defined in `docs/superpowers/specs/2026-07-30-stage-project-report-design.md`.
- Write the snapshot to `tracks/mps/results/20260730-stage-project-report/`.
- Do not commit or push before the existing Stage 9 review gate.

---

### Task 1: Freeze the report evidence and assets

**Files:**
- Create: `tracks/mps/results/20260730-stage-project-report/figs/*`
- Create: `tracks/mps/results/20260730-stage-project-report/evidence.json`

**Interfaces:**
- Consumes: existing `run.json`, assessment, selection, manifest, CSV, PNG, and progress-status files.
- Produces: a dated evidence ledger and local figure paths consumed by `report.json`.

- [ ] Copy only the selected existing PNG figures into the dated `figs/` directory.
- [ ] Generate a status-overview PNG from the evidence ledger without running scientific code.
- [ ] Record source path, source date, evidence role, status, and key numbers in `evidence.json`.
- [ ] Parse `evidence.json` with a standard JSON parser and verify that every copied source exists.

### Task 2: Assemble the four-section report document

**Files:**
- Create: `tracks/mps/results/20260730-stage-project-report/report.json`

**Interfaces:**
- Consumes: the Task 1 evidence ledger and staged figures.
- Produces: a generic report document accepted by `skills/report/render_report.py`.

- [ ] Add the approved title, snapshot lede, and four report sections.
- [ ] Add a completion matrix that separates verified, partial, in-progress, and blocked work.
- [ ] Add exact numerical result tables for LTRG, paper VMCRG, Issue 28 N3, MPS/TT support, and Hard Goal Stage 4-6.
- [ ] Add verdict blocks whose labels match the underlying result classifications.
- [ ] Add source paths and a next-gate table; do not convert predictions into results.
- [ ] Parse the document and verify all `figures.items[].src` paths resolve from the run directory.

### Task 3: Render and verify the offline deliverable

**Files:**
- Create: `tracks/mps/results/20260730-stage-project-report/report.html`

**Interfaces:**
- Consumes: Task 2 `report.json` and Task 1 staged PNG files.
- Produces: one self-contained HTML stage report.

- [ ] Run `python3 skills/report/render_report.py tracks/mps/results/20260730-stage-project-report`.
- [ ] Verify the renderer exits successfully and `report.html` is non-empty.
- [ ] Verify the HTML contains all four section headings, the current date, all status labels, and no unresolved missing-figure note.
- [ ] Verify every report image is embedded as a data URL and no external stylesheet or script is required.
- [ ] Recompute SHA-256 values for `evidence.json`, `report.json`, and `report.html` and record them in the handoff.

### Task 4: Review the snapshot against the source evidence

**Files:**
- Review: `tracks/mps/results/20260730-stage-project-report/report.json`
- Review: `tracks/mps/results/20260730-stage-project-report/report.html`

**Interfaces:**
- Consumes: the rendered report and the source artifacts listed in `evidence.json`.
- Produces: a final factual-completeness decision and user-facing artifact handoff.

- [ ] Check that the LTRG main reproduction is not conflated with the failed endpoint extension.
- [ ] Check that Issue 28 N3/N4/N5 are not marked complete.
- [ ] Check that Hard Goal Stage 5 PASS is not promoted to a Stage 6 or T_c result.
- [ ] Check that the 16,384-sweep packages are labeled preview-only and unsubmitted.
- [ ] Check that MPS/TT experiments are labeled auxiliary evidence.
- [ ] Surface the HTML, JSON, evidence ledger, design, and one-line rerender command.

## Execution choice

Execute inline in the current session. Multi-agent execution is not requested, and the active repository instructions prohibit implicit delegation.
