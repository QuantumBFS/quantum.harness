# Phase-diagram contracts

## Policy

The bundled guard accepts this schema:

```json
{
  "schema_version": 1,
  "goal_id": "public-stable-name",
  "pattern": "finite_size_crossing",
  "axes": {
    "control": {
      "name": "coupling",
      "bounds": [0.0, 1.0],
      "initial_points": [0.0, 0.5, 1.0]
    },
    "size": {
      "name": "L",
      "values": [8, 12, 16, 20],
      "initial_count": 2
    },
    "slice": {
      "name": "temperature",
      "values": [0.1, 0.2]
    }
  },
  "observable": {
    "name": "dimensionless_ratio",
    "value_field": "observables.ratio.value",
    "error_field": "observables.ratio.error",
    "budget_field": "settings.budget"
  },
  "criteria": {
    "sigma": 2.0,
    "target_width": 0.05,
    "max_statistics_multiplier": 8,
    "final_pair_required": true
  },
  "execution": {
    "controller": "local",
    "runner": "uv",
    "base_budget": 1000,
    "poll_seconds": 1800,
    "max_actions": 200
  }
}
```

`slice` is optional. Without it, the workflow locates one boundary point. With it, the same fixed policy is applied independently to every slice value to trace a line in a two-dimensional phase diagram.

- `controller` and `runner`: fixed to `local` and `uv`; phase decisions and durable state never execute remotely.
- `control`: parameter refined by bisection.
- `size`: ordered legal finite-size sequence. Promotion is prefix-only.
- `observable`: dimensionless quantity expected to cross for adjacent sizes; dot-separated fields map validated manifests to value, error, and budget.
- `sigma`: significance threshold for the sign of ΔR.
- `target_width`: maximum accepted control-parameter bracket width.
- `max_statistics_multiplier`: fixed ceiling relative to `base_budget`.
- `final_pair_required`: documents the mandatory final adjacent-size check; schema 1 always enforces it.

Do not put authentication material, user names, cluster aliases, allocation identifiers, or non-public locations in the policy. Keep the policy, observations, report, state, and phase controller in the local harness checkout. A remote job receives only its compute entrypoint and `/parameter-scan` cell/run spec; fetch its manifest locally before adapting it.

## Observation adapter

The local project converts validated, locally fetched per-cell manifests into:

```json
{
  "schema_version": 1,
  "records": [
    {
      "params": {"coupling": 0.5, "L": 12, "temperature": 0.1},
      "status": "success",
      "value": 0.61,
      "error": 0.02,
      "budget": 1000,
      "artifact": "results/example/cells/cell-0004/manifest.json"
    }
  ]
}
```

Allowed statuses:

| Status | Meaning | Required fields |
|---|---|---|
| `pending` | durable execution receipt is registered | `params`, `status`, `budget`, receipt or artifact reference |
| `success` | artifact and convergence contract passed | `params`, `status`, `value`, `error`, `budget`, `artifact` |
| `failed` | terminal operational or validation failure | `params`, `status`, failure evidence in `artifact` or project metadata |

A successful record's uncertainty must be the standard error appropriate to the caller's estimator. Correlated data require a validated blocking, jackknife, bootstrap, or equivalent method before conversion. The guard combines independent size errors in quadrature; if size estimates are correlated, the adapter must provide an uncertainty for ΔR through a project-owned guard instead.

## Report

The deterministic `check` command emits:

```json
{
  "schema_version": 1,
  "status": "ACTION_REQUIRED",
  "checked_at": "2030-01-02T03:04:05Z",
  "reason": "2 phase-diagram cells are required",
  "evidence": [],
  "actions": [
    {
      "spec": {
        "kind": "phase-diagram-cell",
        "params": {"coupling": 0.25, "L": 12},
        "budget": 1000
      },
      "reason": "bisect the crossing bracket"
    }
  ],
  "accepted_artifacts": []
}
```

Statuses:

| Status | Controller response |
|---|---|
| `ACTION_REQUIRED` | Persist and execute exactly the recommended specs. |
| `WAITING` | Create no work; monitor at `next_wake_at`. |
| `HUMAN_REQUIRED` | Ask the included `question`; do not alter policy. |
| `COMPLETE` | Stop autonomous work and report accepted artifacts. |

Action identity is the first 20 hexadecimal characters of SHA-256 over canonical JSON, prefixed by `act-`. A changed parameter or budget is a new action.

## Transaction states

```text
PLANNED -> PREPARED -> SUBMITTING -> SUBMITTED -> REGISTERED
PLANNED | PREPARED | SUBMITTING | SUBMITTED -> ABORTED
```

`SUBMITTING` means the irreversible call may have happened but no receipt was persisted. Resolve it against the local process table, scheduler, or service idempotency key before proceeding.

## Pattern limits

The bundled crossing guard assumes:

- one scalar dimensionless observable per cell;
- independent uncertainty between the two compared sizes;
- a boundary bracketed by a significant sign change of ΔR;
- midpoint refinement is valid along the control axis;
- the declared ordered size sequence is the only legal promotion path.

Use a project-owned deterministic guard when these assumptions fail. It may emit the same report and action contracts, allowing the controller lifecycle to remain unchanged.
