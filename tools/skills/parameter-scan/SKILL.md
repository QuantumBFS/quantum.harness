---
name: parameter-scan
description: Use when the user wants to sweep one or more parameter axes (Hamiltonian couplings, estimator knobs, system size `L`, …) for any observable on any model. Generic over axes, observable, and model. For cluster execution composes with `/slurm`.
---

# parameter-scan

Sweep a Cartesian product of parameter axes — single-axis (1D scan) or multi-axis (`(L, h)`, `(χ, N_S)`, `(U/t, doping)`, …) — for a single observable, holding other parameters fixed. Produces a structured grid-indexed result, an auto-generated plot, a feature-detection label, and a brief report.

This primitive subsumes the previous `/finite-size-scan` (which is just `/parameter-scan` with `L` as the size axis).

## When to activate

- User asks "how does this depend on `[parameter]`?" — single-axis scan.
- User asks for a `(L, parameter)` grid for finite-size scaling — two-axis scan, feeds `/scaling-fit`.
- A model-skill workflow needs a parameter sweep to locate a transition, characterize a regime, or extrapolate.
- After any single-point calculation, this is the canonical follow-up offered through `solve`.

## Inputs

- *Model skill* and *anchor configuration* (fixed parameters not on any axis; sector; lattice).
- *Axes* — list of named axes with value lists. Each axis is either a Hamiltonian coupling (`h`, `Δ`, `D`, `J2/J1`, `U/t`, …), a size axis (`L`, `L_x`, `L_y`), or an estimator knob (`χ`, `N_S`, Trotter step, basis size). The skill does not know the physics meaning — the model skill / method card resolves the name.
- *Observable* — name resolved by the model skill.
- *Default value lists* — when the user does not specify, 9-15 evenly spaced points spanning the prompt's regime. Size axes default to a geometric/quadratic sequence (e.g., `[8, 16, 32, 64, 128]` for 1D entry-level work). The calling skill or user overrides; this primitive does not hardcode physics-specific values.
- *Optional* — convergence-parameter override per cell (e.g., `χ(L)` ramp).

## Workflow

1. **Plan**: enumerate cells (Cartesian product of axes). Plan output: `results/<run>/parameter-scan.plan.json` listing cell ids and their parameter assignments.
2. **Resume detection**: walk `results/<run>/cells/` and identify completed cells via their manifests. Build the *to-run* set.
3. **Execute**:
   - **Local** (laptop, no cluster profile active): loop over cells, dispatching the model-skill calculation per cell.
   - **Cluster** (`tools/cluster/active.md` symlink or `HARNESS_CLUSTER_PROFILE` env var present): compose with `/slurm`, handing it the per-cell script and cell map. The slurm skill submits an sbatch array job, monitors, fetches.
4. **Auto-bump convergence** (per AGENTS.md "Convergence" verification rule §3): if the model skill flags non-convergence at a cell, bump the convergence parameter and re-run.
5. **Collect**: walk `results/<run>/cells/*/manifest.json` and assemble `results/<run>/parameter-scan.csv` with `(axis_1, axis_2, …, observable, uncertainty, convergence_param, runtime, status)` rows.
6. **Auto-plot**: emit one or more plots via `scientific-visualization` based on axis arity:
   - 1D: `observable(parameter)` line plot with error bars.
   - 2D: family of `observable(axis_1)` curves indexed by `axis_2` (or vice versa); plus an optional `observable(axis_1, axis_2)` heatmap when both axes are continuous.
7. **Feature detection** (auto labels — see below).
8. **Hand back**: table + plot + feature label list to the calling skill (or `solve`).

## Cell Spec Contract

For cluster or resumable execution, `/parameter-scan` writes `results/<run>/run_spec.json` with opaque cells. The only reusable contract is `cell_id`, `params`, optional per-cell `settings`, shared `settings`, and shared `provenance`:

```json
{
  "run_id": "example-run",
  "run_dir": "results/example-run",
  "settings": {"convergence_knob": 30, "sample_budget": 1000000},
  "provenance": {"protocol_hash": "...", "sources": ["..."], "claims": ["..."]},
  "cells": [
    {"cell_id": "cell-0001", "params": {"axis_1": 16, "axis_2": 0.8}}
  ]
}
```

The primitive treats `params` and `settings` as data, not schema. It never knows whether a key is a Hamiltonian parameter, lattice size, sampler knob, algorithm choice, or something else. The model/method entrypoint maps those opaque values into domain code and writes `results/<run>/cells/<cell_id>/manifest.json`. Domain-shaped names such as `L`, `h`, `U/t`, `χ`, or `n_steps` are allowed in a specific run spec when the entrypoint expects them, but they are payload keys, not harness-level types.

## Feature detection (auto labels)

The skill labels what it found on the data:

- **Monotone** — observable goes one direction across an axis range.
- **Asymptoting** (size-axis-aware) — successive size-differences shrink monotonically; thermodynamic-limit extrapolation is sensible.
- **Critical-like** (size-axis-aware) — power-law-looking growth or decay with `L`; flag for `/scaling-fit`.
- **Drifting / oscillating** (size-axis-aware) — neither asymptoting nor a clean power-law; surface the failure mode (insufficient sizes, χ too small, wrong sector).
- **Extremum** — peak or valley at an interior point on a parameter axis. Often a critical-point indicator.
- **Crossing** (multi-axis) — curves at different size cross at one parameter value. Binder-cumulant-like diagnostic for transitions.
- **Discontinuity-like step** — sharp jump suggesting a first-order transition or a sector / convergence problem; flag for follow-up.

Labels are descriptive, not interpretive. The calling skill (e.g., `physics/criticality`, `physics/magic`, `physics/confinement`) interprets the label.

## Output

- `results/<run>/parameter-scan.plan.json` — the plan (cell ids + parameter assignments).
- `results/<run>/cells/<cell_id>/manifest.json` — per-cell manifest (one per cell).
- `results/<run>/parameter-scan.csv` — assembled grid table.
- `results/<run>/parameter-scan.png` — auto-generated plot(s).
- A 2-3-line report: feature label(s), recommended next step.
- `scripts/<run>/parameter-scan.jl` — reproducible script.

## Resume semantics

- Re-running on a partial run reuses cells with `success`-tagged manifests; re-submits cells without manifests.
- Cells tagged `failed` are *not* automatically retried — the user ratifies the retry. (Avoids wasting compute on logic errors.)
- The plan file is immutable per run id; if axes or values change, the user starts a new run id.

## Composition

- For embarrassingly-parallel cluster sweeps, this skill composes with `/slurm` (which submits the sbatch array job + monitors + fetches). The user does not call `/slurm` directly for grids; `/parameter-scan` handles the cell decomposition and delegates.
- 2D `(L, parameter)` grids feed `/scaling-fit` for finite-size collapse and exponent extraction.
- Common follow-ups (offered via `AskUserQuestion`):
  - `/scaling-fit` (Recommended for critical-like / extremum / crossing labels).
  - `/cross-method-check` — independent confirmation at one cell.
  - Done.

## Notes

- The same primitive sweeps a Hamiltonian coupling (`h`, `Δ`, `D`, `U/t`, …), a size axis (`L`, `L_y`), or an estimator knob (`χ`, `N_S`, Trotter step). The user / calling skill picks the axes; the primitive does not care.
- This skill does *not* know the physics meaning of any axis. It is generic over the parameter type.
- The convergence-parameter logic delegates to the model skill (and method card) — `parameter-scan` does not know what `χ` should be at `L = 128`; the model skill does.
- For frontier regimes, the calling physics skill should invoke `arxiv-search` *before* interpretation; this primitive only produces the data.
- Per-cell manifest schema lives at `results/<run>/cells/<cell_id>/manifest.json` and is consumed by `/run-report` at session close. Each cell's compute script writes its own manifest; this skill does not invent a parallel format.

## Anti-patterns (auto-reject)

- Hardcoding physics-specific axis ranges or default values — those are model-skill's concern.
- Bundling sbatch / ssh / rsync logic into this skill — that's `/slurm`'s job.
- Inventing a new manifest format — the per-cell manifest convention is shared with `/run-report` and `/reproduce-paper`.
- Silent skip of failed cells — every failed cell must be classified and surfaced.
