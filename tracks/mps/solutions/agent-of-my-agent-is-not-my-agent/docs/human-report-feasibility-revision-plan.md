# Human Report Feasibility Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Simplify the uncertainty presentation and make local computational
feasibility a central, evidence-backed conclusion.

**Architecture:** Reviewer-facing Markdown contains the concise title,
three-row uncertainty table, and resource discussion. Detailed provenance
remains in `report_AI/`; no numerical artifact is regenerated.

**Tech Stack:** Markdown and pytest.

## Global constraints

- Do not change numerical JSON, CSV, checkpoints, or fit outputs.
- Do not claim an achieved DMRG size beyond L=128.
- State that DMRG and QMC scaling and estimators differ.

### Task 1: Add failing report-structure tests

- [ ] Check the exact project title.
- [ ] Check that Figure 5 and its Markdown reference are absent.
- [ ] Check that Table 4 contains one L=128 MPS row and no correction-coordinate
  row.
- [ ] Check the resource statements and the 1.76-hour sigma=1.8 runtime.

### Task 2: Revise the human report

- [ ] Replace the placeholder title.
- [ ] Remove Figure 5 and simplify Table 4.
- [ ] Add the computational-feasibility subsection and calibrated comparison.
- [ ] Synchronize figure/table planning notes.

### Task 3: Synchronize the technical archive

- [ ] Record resource provenance and the interpretation boundary.
- [ ] Reclassify the former Figure 5 source as Table 4 evidence.

### Task 4: Verify

- [ ] Run focused report tests.
- [ ] Check Markdown consistency.
- [ ] Verify result-artifact checksums are unchanged.
