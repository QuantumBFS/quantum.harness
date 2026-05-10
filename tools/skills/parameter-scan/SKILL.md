---
name: parameter-scan
description: Use when the user wants to sweep one or more declared axes for a produced quantity. Generic over axes, payload schema, quantity, and implementation. For cluster execution composes with `/slurm`.
---

# parameter-scan

Sweep a Cartesian product of declared axes, holding other payload fields fixed. Produces a structured grid-indexed result, an auto-generated plot, shape labels, and a brief report.

This primitive subsumes any single-axis or multi-axis scan whose cells can be represented as opaque `params` plus optional `settings`.

## When to activate

- User asks "how does this depend on `[parameter]`?" - single-axis scan.
- User asks for a two-axis or higher-dimensional grid.
- A calling workflow needs a sweep to characterize a response, locate a feature, or support an extrapolation.
- After any single-point calculation, this is the canonical follow-up offered through `solve`.

## Inputs

- *Calling workflow* and *anchor configuration* - fixed payload fields not on any axis.
- *Axes* - list of named axes with value lists. Axis names and values are opaque to this primitive; the calling workflow or entrypoint resolves them.
- *Quantity* - output field or artifact selected by the caller.
- *Default value lists* - provided by the caller or user. This primitive does not infer domain-specific ranges.
- *Optional* - per-cell settings overrides for any correctness-affecting or budget-affecting payload.

## Workflow

1. **Plan**: enumerate cells (Cartesian product of axes). Plan output: `results/<run>/parameter-scan.plan.json` listing cell ids and their parameter assignments.
2. **Resume detection**: walk `results/<run>/cells/` and identify completed cells via their manifests. Build the *to-run* set.
3. **Execute**:
   - **Local** (laptop, no cluster profile active): loop over cells, dispatching the caller's calculation per cell.
   - **Cluster** (`tools/cluster/active.md` symlink or `HARNESS_CLUSTER_PROFILE` env var present): compose with `/slurm`, handing it the per-cell script and cell map. The slurm skill submits an sbatch array job, monitors, fetches.
4. **Auto-bump controlling settings**: if the caller declares a retry policy and a cell reports non-convergence, apply the declared bump and re-run.
5. **Collect**: walk `results/<run>/cells/*/manifest.json` and assemble `results/<run>/parameter-scan.csv` with axis values, selected quantity, uncertainty, controlling settings, runtime, and status.
6. **Auto-plot**: emit one or more plots via `scientific-visualization` based on axis arity:
   - 1D: `observable(parameter)` line plot with error bars.
   - 2D: family of `observable(axis_1)` curves indexed by `axis_2` (or vice versa); plus an optional `observable(axis_1, axis_2)` heatmap when both axes are continuous.
7. **Shape detection** (auto labels — see below).
8. **Hand back**: table + plot + shape label list to the calling skill (or `solve`).

## Cell Spec Contract

For cluster or resumable execution, `/parameter-scan` writes `results/<run>/run_spec.json` with opaque cells. The only reusable contract is `cell_id`, `params`, optional per-cell `settings`, shared `settings`, and shared `provenance`:

```json
{
  "run_id": "example-run",
  "run_dir": "results/example-run",
  "settings": {"control_knob": 30, "budget": 1000000},
  "provenance": {"protocol_hash": "...", "sources": ["..."], "claims": ["..."]},
  "cells": [
    {"cell_id": "cell-0001", "params": {"axis_1": 16, "axis_2": 0.8}}
  ]
}
```

The primitive treats `params`, `settings`, and `provenance` as data, not schema. It never knows what a key physically or methodologically means. The entrypoint maps those opaque values into its own code and writes `results/<run>/cells/<cell_id>/manifest.json`. Domain-shaped names are allowed in a specific run spec when the entrypoint expects them, but they are payload keys, not harness-level types.

Setup that affects correctness or uncertainty also belongs in `settings` as opaque payload. The entrypoint must echo the payload it actually used into each manifest and emit machine-readable evidence for any declared constraint it verifies. `/parameter-scan` only checks presence/freshness and assembles cells; it does not hardcode setup types.

If the caller needs stricter assembly gates, `run_spec.json` may carry `assembly.manifest_contract`, `assembly.consensus_fields`, and `assembly.provenance_fields`. The contract is generic over manifest field paths: required/nonempty fields, equality checks, list membership, numeric fields, optional numeric fields, numeric bounds, and evidence-set bindings. Domain requirements are encoded as payload values in the protocol/run spec and echoed by manifests, not as new `/parameter-scan` types.

Assemblers must validate each manifest's `settings` and declared provenance against the merged shared+cell payload from `run_spec.json`, then report settings as constant vs varying across cells. Never treat the first manifest's settings or provenance as global unless `assembly.consensus_fields` declares and passes that invariant.

## Shape detection (auto labels)

The skill labels only the shape of the data:

- **Monotone** — observable goes one direction across an axis range.
- **Asymptoting** — successive differences along a declared axis shrink monotonically; an extrapolation check may be appropriate.
- **Power-law-like trend** - log-log slope is approximately stable across a declared axis; pass to `/scaling-fit` if the calling skill needs exponents.
- **Drifting / oscillating** - neither asymptoting nor a clean power-law-like trend; surface the unresolved shape and the controlling settings.
- **Extremum** - peak or valley at an interior point on an axis.
- **Crossing** - curves indexed by one axis cross at one value of another axis.
- **Step-like** - a sharp jump relative to neighboring points; flag for follow-up.

Labels are descriptive, not interpretive. The calling workflow decides what the shape means.

## Output

- `results/<run>/parameter-scan.plan.json` — the plan (cell ids + parameter assignments).
- `results/<run>/cells/<cell_id>/manifest.json` — per-cell manifest (one per cell).
- `results/<run>/parameter-scan.csv` — assembled grid table.
- `results/<run>/parameter-scan.png` — auto-generated plot(s).
- A 2-3-line report: shape label(s), recommended next step.
- `scripts/<run>/parameter-scan.jl` — reproducible script.

## Resume semantics

- Re-running on a partial run reuses cells with `success`-tagged manifests; re-submits cells without manifests.
- Cells tagged `failed` are *not* automatically retried — the user ratifies the retry. (Avoids wasting compute on logic errors.)
- The plan file is immutable per run id; if axes or values change, the user starts a new run id.

## Composition

- For embarrassingly-parallel cluster sweeps, this skill composes with `/slurm` (which submits the sbatch array job + monitors + fetches). The user does not call `/slurm` directly for grids; `/parameter-scan` handles the cell decomposition and delegates.
- Declared scaling grids can feed `/scaling-fit` for collapse or exponent extraction.
- Common follow-ups (offered via `AskUserQuestion`):
  - `/scaling-fit` (Recommended for power-law-like / extremum / crossing labels when the calling skill needs scaling).
  - `/cross-method-check` — independent confirmation at one cell.
  - Done.

## Notes

- The user or calling workflow picks the axes; the primitive does not care what they mean.
- This skill does *not* know the meaning of any axis. It is generic over parameter names and values.
- Retry and convergence logic delegate to the calling workflow and declared check commands.
- For literature-dependent interpretation, the calling workflow should invoke its source-search or source-audit mechanism before interpreting; this primitive only produces data.
- Per-cell manifest schema lives at `results/<run>/cells/<cell_id>/manifest.json` and is consumed by `/run-report` at session close. Each cell's compute script writes its own manifest; this skill does not invent a parallel format.

## Anti-patterns (auto-reject)

- Hardcoding domain-specific axis ranges or default values.
- Bundling sbatch / ssh / rsync logic into this skill - that's `/slurm`'s job.
- Inventing a new manifest format - the per-cell manifest convention is shared with `/run-report` and `/reproduce-paper`.
- Silent skip of failed cells - every failed cell must be classified and surfaced.
