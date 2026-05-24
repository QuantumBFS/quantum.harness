---
name: parameter-scan
description: Use when the user wants to vary one or more parameters and see how a quantity responds — phrases like "how does X depend on Y", "sweep U/t from 0 to 10", "scan J2/J1 across the transition", "finite-size series at L = 12, 16, 20, 24", "bond-dimension sweep chi=50 to 400", a single-axis scan, or a multi-axis grid.
---

# parameter-scan

Sweep a Cartesian product of declared axes while holding other payload fields fixed. Produces a grid-indexed table, plot, shape labels, and a short report. This primitive is generic over axis names, physical meaning, payload schema, and per-cell implementation.

## Binding Scope

<audience>
The caller is `solve`, a model/physics card, `/reproduce-paper`, or another workflow skill. The user sees only the final 2-3-line report and artifacts. This primitive does not choose domain ranges, interpret physics, or define the per-cell manifest schema.
</audience>

<checklist name="binding">
- Axis names and values are opaque. The caller/entrypoint resolves their meaning.
- Resume detection walks every `results/<run>/cells/*` directory; failed/missing cells stay visible.
- Settings are constant only after manifest consensus across all cells.
- The first manifest is never global provenance or global settings.
- Cluster execution composes with `/slurm`; sbatch/ssh logic does not live here.
- Every compute script writes its own `results/<run>/cells/<cell_id>/manifest.json`.
</checklist>

## Activation

- User asks how a quantity depends on a parameter.
- User asks for a finite-size, bond-dimension, coupling, or multi-axis grid.
- A calling workflow needs a sweep to characterize a response, locate a feature, or support an extrapolation.
- A single-point calculation naturally offers a scan follow-up.

## Inputs

- Fixed payload from caller.
- Axes: named value lists, treated as opaque payload.
- Quantity: manifest field or artifact selected by caller.
- Optional per-cell settings overrides.
- Optional retry policy declared by caller.

## Workflow

1. **Plan.** Enumerate Cartesian product and write `results/<run>/parameter-scan.plan.json`.
2. **Build run spec.** For resumable or cluster execution, write `results/<run>/run_spec.json` using the generic contract below.
3. **Resume detect.** Identify cells with success manifests, failed manifests, missing manifests, or no cell directory.
4. **Execute.** Run locally for small scans; compose with `/slurm` for cluster scans.
5. **Retry only by policy.** Auto-bump controlling settings only for cells whose manifest reports non-convergence and whose caller declared a retry policy.
6. **Collect.** Assemble every manifest into `results/<run>/parameter-scan.csv`; failed/missing cells appear with status.
7. **Plot.** Emit `results/<run>/parameter-scan.png`; choose line/errorbar, family curves, or heatmap based on axis arity.
8. **Shape labels.** Apply generic shape labels from the reference; no physical interpretation.
9. **Hand back.** Return table, plot, shape labels, and recommended next step to caller.

## Assemble Invariants

<invariants name="assemble">
- Validate every manifest's settings against merged shared+cell payload from `run_spec.json`.
- Validate every manifest's provenance against run-spec provenance.
- Report settings as constant only after checking every manifest.
- Surface varying settings and provenance mismatches explicitly.
- Include failed or missing manifests in the assembled CSV.
</invariants>

Observed cell manifests must exactly match declared run-spec cells. Trial artifacts belong outside the covered path unless declared.

## Run Spec Contract

For cluster or resumable execution, write:

```json
{
  "run_id": "example-run",
  "run_dir": "results/example-run",
  "settings": { "control_knob": 30, "budget": 1000000 },
  "provenance": { "protocol_hash": "...", "sources": ["..."], "claims": ["..."] },
  "cells": [
    { "cell_id": "cell-0001", "params": { "axis_1": 16, "axis_2": 0.8 } }
  ]
}
```

Reusable fields:

- `cell_id`
- `params`
- optional per-cell `settings`
- shared `settings`
- shared `provenance`

The primitive treats `params`, `settings`, and `provenance` as data, not schema.
Domain-shaped names are allowed only as payload consumed by the entrypoint.
Correctness- or uncertainty-affecting setup belongs in `settings`. The
entrypoint echoes the payload it actually used into each manifest and emits
machine-readable evidence for declared constraints.

Optional strict assemble fields:

- `assemble.manifest_contract`
- `assemble.consensus_fields`
- `assemble.provenance_fields`

These are generic field-path checks: required/nonempty, equality, list
membership, numeric bounds, optional numeric fields, and evidence-set bindings.

## Shape Labels

Labels describe data shape only. The caller decides interpretation.

| Label | Detection | Handoff |
|---|---|---|
| Monotone | Observable moves one direction across an axis. | Surface direction. |
| Asymptoting | Successive differences shrink monotonically. | Suggest extrapolation check. |
| Power-law-like | Log-log slope is approximately stable. | Pass to `/scaling-fit` if exponents are needed. |
| Drifting/oscillating | No clean asymptote or power-law-like trend. | Surface unresolved shape and controlling settings. |
| Extremum | Peak/valley at an interior point. | Surface location; possible `/scaling-fit`. |
| Crossing | Curves indexed by one axis cross along another. | Surface crossing; possible critical fit. |
| Step-like | Sharp jump relative to neighbors. | Flag for follow-up. |

Bad:

```python
bond_dim_axis = [16, 32, 64, 128]
```

Good:

```python
axes = caller.axes
```

Bad: silently omit failed cells from `parameter-scan.csv`.

Good: include every planned cell with `status = success | failed | missing | pending`.

## Output

- `results/<run>/parameter-scan.plan.json`
- `results/<run>/run_spec.json` for resumable/cluster scans
- `results/<run>/cells/<cell_id>/manifest.json`
- `results/<run>/parameter-scan.csv`
- `results/<run>/parameter-scan.png`
- `scripts/<run>/parameter-scan.jl` or `.py`
- 2-3-line report: shape labels and next step

## Resume

- Reuse cells with success-tagged manifests.
- Do not auto-retry failed cells without user ratification unless the caller declared a retry policy.
- If axes or values change, start a new run id.

## Composition

- `/slurm` handles cluster array submission, monitoring, and fetch.
- `/scaling-fit` consumes power-law-like, extremum, or crossing scans when the caller needs exponents/collapse.
- `/cross-method-check` verifies one selected point independently.
- Literature-dependent interpretation belongs to the caller's source-search/source-audit path.

## Anti-patterns

<checklist name="reject">
- Hardcoding domain-specific axis ranges.
- Bundling sbatch/ssh/rsync logic here.
- Inventing a new manifest format.
- Silently dropping failed cells.
- Interpreting a shape as a phase or mechanism without caller/domain-card evidence.
</checklist>
