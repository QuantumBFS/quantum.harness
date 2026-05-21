# parameter-scan run-spec and shape reference

Read before writing `run_spec.json`, assembler code, shape labels, or a resumable/cluster scan.

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

The primitive treats `params`, `settings`, and `provenance` as data, not schema. Domain-shaped names are allowed only as payload consumed by the entrypoint.

Correctness- or uncertainty-affecting setup belongs in `settings`. The entrypoint echoes the payload it actually used into each manifest and emits machine-readable evidence for declared constraints.

Optional strict assemble fields:

- `assemble.manifest_contract`
- `assemble.consensus_fields`
- `assemble.provenance_fields`

These are generic field-path checks: required/nonempty, equality, list membership, numeric bounds, optional numeric fields, and evidence-set bindings.

## Assembler Obligations

- Validate every manifest against merged shared+cell settings.
- Validate every manifest provenance against run-spec provenance.
- Report constants vs varying values after checking all cells.
- Never treat the first completed manifest as global.
- Keep failed/missing cells in the CSV with status.

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

## Examples

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
