# Figures 3–4 and Table 3 Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Produce the approved two-panel Figure 3, power-correction Figure 4,
and corrected Table 3 reference values without changing numerical results.

**Architecture:** A focused plotting script reads the accepted Phase 8 and
Phase 9 JSON analyses and writes the two human-report PNG files. Tests inspect
the Matplotlib objects and reviewer-facing Markdown.

**Tech Stack:** Python 3.11, Matplotlib, pytest, Markdown.

## Global Constraints

- Do not recompute physics quantities.
- Do not alter source JSON or raw result artifacts.
- Use uppercase bold panel labels for multi-panel figures.
- Keep Figure 4 focused on the power-correction sensitivity.

### Task 1: Add failing presentation tests

**Files:**
- Create: `tests/test_human_report_figures.py`

- [ ] Assert that Figure 3 has exactly two axes labeled A and B.
- [ ] Assert that Figure 4 plots `z_eff` against `L_eff` and contains the
  stored power-correction curve.
- [ ] Assert that Table 3 contains `0.93(2) / 1.00(3)`.
- [ ] Run the test and verify that it fails because the figure builder does
  not yet exist.

### Task 2: Implement the reusable figure builder

**Files:**
- Create: `scripts/build_human_report_figures.py`

- [ ] Load only the accepted Phase 8/9 analysis JSON files.
- [ ] Implement the approved Figure 3 and Figure 4 layouts.
- [ ] Export 300-dpi PNG files into `report_Human/figures/`.
- [ ] Run the focused test and verify that it passes.

### Task 3: Synchronize reviewer-facing prose

**Files:**
- Modify: `report_Human/main.md`
- Modify: `report_Human/figures/README.md`
- Modify: `report_Human/tables/README.md`

- [ ] Remove Figure 3 panel-C references.
- [ ] Describe Figure 4 as the power-correction plot.
- [ ] Replace the sigma=1.8 Table 3 reference values with
  `0.93(2) / 1.00(3)`.

### Task 4: Render and verify

- [ ] Run the figure builder.
- [ ] Run the focused and report-generation tests.
- [ ] Inspect both PNG files visually.
- [ ] Verify that numerical JSON and raw artifacts retain their original
  checksums.
