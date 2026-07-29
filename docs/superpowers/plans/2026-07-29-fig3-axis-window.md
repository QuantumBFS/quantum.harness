# Fig. 3 Axis Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display the complete Fig. 3 comparison with ω/Ω∈[0,10] for longitudinal driving and ω/Ω∈[0,4] for transversal driving.

**Architecture:** Change only the Matplotlib view limits for both the continuous-spectrum and delta-weight axes. Preserve all loaded CSV rows, reference comparisons, error calculations, and stored high-frequency delta peaks.

**Tech Stack:** Python 3, Matplotlib, pytest.

## Global Constraints

- Longitudinal upper and lower axes use exactly `(0.0, 10.0)`.
- Transversal upper and lower axes use exactly `(0.0, 4.0)`.
- Numerical artifacts are not rewritten or truncated.

---

### Task 1: Drive-Specific Fig. 3 Windows

**Files:**
- Modify: `scripts/tests/test_floquet_plot_results.py`
- Modify: `tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/plot_results.py`

**Interfaces:**
- Consumes: existing Fig. 3 CSV artifacts and `plot_fig3(args)`.
- Produces: a PNG whose paired axes share the requested drive-specific limits.

- [ ] **Step 1: Write a failing source-level regression test**

Assert that the plotting module exposes:

```python
FIG3_X_LIMITS = {
    "longitudinal": (0.0, 10.0),
    "transversal": (0.0, 4.0),
}
```

and applies each tuple to both axes for that drive.

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest scripts/tests/test_floquet_plot_results.py -q
```

Expected: failure because `FIG3_X_LIMITS` is absent.

- [ ] **Step 3: Implement the limits**

Add the constant and call `set_xlim(*FIG3_X_LIMITS[drive])` for the continuous-spectrum and delta-weight axes.

- [ ] **Step 4: Verify GREEN and regenerate**

Run the plotting test, regenerate `fig3_full_validation.png`, and visually inspect that both rows align at 0–10 and 0–4.

- [ ] **Step 5: Commit**

Commit the plan, test, and plotting script together with message:

```text
fix: focus Fig. 3 frequency windows
```
