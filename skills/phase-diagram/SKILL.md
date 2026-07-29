---
name: phase-diagram
user-invocable: false
description: Use when the user wants to map or refine a numerical phase diagram from finite-size data, especially a phase boundary identified by crossings of a dimensionless observable; supports coarse scans, uncertainty-aware bracket refinement, increased statistics, sequential size promotion, resumable local or Slurm execution, and explicit completion on the final adjacent size pair.
---

# phase-diagram

Locate finite-size phase boundaries with a bounded, auditable loop. The phase controller and its durable state run only in the local harness checkout through `uv`; never copy or execute this controller on a cluster. Use a deterministic crossing guard to choose the next cells; use `/parameter-scan` to build compute-only cells; use `/using-slurm` to ship those cells, register receipts, monitor them, and fetch manifests back locally.

## User contract

Before compute, propose one compact setup for ratification:

> We will scan **CONTROL** over **BOUNDS** at sizes **SIZES**, hold **FIXED PARAMETERS** fixed, and locate the boundary from crossings of **DIMENSIONLESS OBSERVABLE**. Completion requires a width ≤ **TARGET WIDTH** at **SIGMA σ** on the final adjacent size pair. Correct anything here before I generate or submit cells.

The model card or caller must supply the Hamiltonian, lattice, boundary conditions, conserved sector, fixed parameters, observable definition, and method. Do not infer a phase label from a crossing alone.

Then ask one execution question: run the generated compute cells locally or through `/using-slurm` based on the up-front cost estimate. In either case, keep phase policy, observations, reports, and controller state local.

## Supported pattern

The bundled guard implements `finite_size_crossing`:

1. **Coarse grid** — evaluate declared initial control points on the initial size prefix.
2. **Bracket** — require opposite signs in ΔR = R(L_large) − R(L_small), significant at the configured σ.
3. **Statistics** — if ΔR is inconclusive, double the cell budget up to the fixed multiplier.
4. **Refine** — bisect the narrowest significant bracket until its width reaches the target.
5. **Promote size** — evaluate bracket endpoints at exactly the next declared size.
6. **Complete** — accept only a target-width bracket supported by the final adjacent size pair for every slice.
7. **Escalate** — failed cells, exhausted statistics, no in-bounds bracket, or ambiguous recovery require the user.

For first-order diagnostics, hysteresis, energy-level crossings, order-parameter thresholds, gap closure, or data collapse, do not force this pattern. Keep their acceptance rule in a project-owned guard and use the transactional lifecycle in `references/contracts.md`.

## Start a project

Use the bundled controller from the repository root. `uv` locks the declared Python version and dependencies from the script metadata; do not invoke it with system `python3`:

```bash
uv run --script skills/phase-diagram/scripts/phase_diagram.py scaffold \
  --directory results/<run>/phase-diagram
```

This creates only runtime inputs:

```text
results/<run>/phase-diagram/phase-policy.json
results/<run>/phase-diagram/observations.json
```

Modify `phase-policy.json`, then show the exact policy to the user for ratification. Field definitions and a two-axis example are in `references/contracts.md`.

Initialize durable controller state:

```bash
uv run --script skills/phase-diagram/scripts/phase_diagram.py init \
  --policy results/<run>/phase-diagram/phase-policy.json \
  --state results/<run>/phase-diagram/state.json
```

Keep runtime policy, observations, reports, state, and action specs under the local `results/<run>/`; do not add them to the reusable skill and do not sync them as executable controller inputs to a cluster.

## Build observations

Each successful compute cell must write a normal `/parameter-scan` manifest. After `/using-slurm` fetches `results/<run>/cells/` back to the local checkout, set the policy's dot-separated `value_field`, `error_field`, and `budget_field`, then build `observations.json` locally and deterministically:

```bash
uv run --script skills/phase-diagram/scripts/phase_diagram.py collect \
  --policy results/<run>/phase-diagram/phase-policy.json \
  --cells-dir results/<run>/cells \
  --output results/<run>/phase-diagram/observations.json
```

Never transcribe numerical results manually from unvalidated text or plots. Build every observation from a validated manifest. The collected record is:

```json
{
  "params": {"coupling": 0.5, "L": 12},
  "status": "success",
  "value": 0.61,
  "error": 0.02,
  "budget": 1000,
  "artifact": "results/example/cells/cell-0004/manifest.json"
}
```

Use `pending` only after a job receipt is registered. Use `failed` for terminal scheduler, artifact, or convergence failure; the guard will stop for a user decision. Records are unique by `(slice, control, size)`. Collection selects the highest-budget manifest as the replacement and rejects equal-budget duplicates as ambiguous.

## Wake protocol

Run the stages in this order every time work resumes.

### 1. Inspect crash state

```bash
uv run --script skills/phase-diagram/scripts/phase_diagram.py inspect \
  --policy results/<run>/phase-diagram/phase-policy.json \
  --state results/<run>/phase-diagram/state.json
```

If `unresolved_submitting` is nonempty, reconcile each `action_id` with the external system before any new submission. Bind an existing receipt, abort with evidence if absence is proven, or ask the user if uncertain.

### 2. Compute the next decision

```bash
uv run --script skills/phase-diagram/scripts/phase_diagram.py check \
  --policy results/<run>/phase-diagram/phase-policy.json \
  --observations results/<run>/phase-diagram/observations.json \
  --report results/<run>/phase-diagram/report.json
uv run --script skills/phase-diagram/scripts/phase_diagram.py ingest \
  --policy results/<run>/phase-diagram/phase-policy.json \
  --state results/<run>/phase-diagram/state.json \
  --report results/<run>/phase-diagram/report.json
```

Obey the report:

- `ACTION_REQUIRED` — execute only the listed immutable cell specs.
- `WAITING` — perform no new work; monitor at `next_wake_at`.
- `HUMAN_REQUIRED` — present the question and evidence; do not relax policy silently.
- `COMPLETE` — report each slice's bracket, size pair, σ threshold, and accepted manifests.

### 3. Execute authorized cells

For each report action, save its `spec` as `action.json`, then persist it before compute:

```bash
uv run --script skills/phase-diagram/scripts/phase_diagram.py plan \
  --policy results/<run>/phase-diagram/phase-policy.json \
  --state results/<run>/phase-diagram/state.json --spec action.json
```

Map the spec to a `/parameter-scan` compute cell; do not ship `phase_diagram.py`, `state.json`, or controller commands to the remote host:

- `params` becomes the cell parameters;
- `budget` becomes the method-specific statistics or iteration budget;
- fixed model/method settings remain in the shared run spec;
- `action_id` becomes the idempotency key in the cell/job name or manifest.

Advance `PLANNED -> PREPARED` only after the script and run spec exist. Immediately before an irreversible local launch or Slurm submission, advance to `SUBMITTING`. Immediately after obtaining a PID/job ID/other durable receipt, advance to `SUBMITTED --receipt RECEIPT`, then `REGISTERED` after adding the pending observation.

```bash
uv run --script skills/phase-diagram/scripts/phase_diagram.py advance \
  --policy results/<run>/phase-diagram/phase-policy.json \
  --state results/<run>/phase-diagram/state.json \
  --action-id ACTION_ID --to TARGET [--receipt RECEIPT] [--reason TEXT]
```

For multiple actions, plan all compute cells into one `/parameter-scan` run spec and submit one Slurm array where practical, but persist the array receipt mapping for every action in the local state before ending the session.

### 4. Monitor, fetch, validate, repeat

Use `/using-slurm` locally to monitor and fetch remote cells. Scheduler `COMPLETED` is not success: only after manifests are fetched into the local `results/<run>/cells/` and pass the caller's artifact and convergence contract may local `collect` record `success`. Re-run local `check` after every fetched batch.

## Output

Return:

- `results/<run>/phase-diagram/phase-policy.json`
- `results/<run>/phase-diagram/observations.json`
- `results/<run>/phase-diagram/state.json`
- `results/<run>/phase-diagram/report.json`
- `/parameter-scan` run spec, per-cell manifests, CSV, and plot
- final boundary table: `slice | bracket | estimate | final size pair | σ | evidence`

Lead with the boundary estimate and verification status. A crossing supports a finite-size boundary estimate; phase names and thermodynamic interpretation remain with the model/physics card.

## Binding rules

<checklist name="binding">
- Run every phase controller command locally through `uv run --script`; never use system `python3` or a remote interpreter.
- Ship only compute entrypoints and `/parameter-scan` run specs; never ship the phase controller or its durable state.
- Fetch manifests locally before `collect`, `check`, or any scientific acceptance decision.
- Confirm Hamiltonian, lattice, boundary, sector, observable, axes, sizes, and stop rule before compute.
- Estimate cost before the first run; compose with `/using-slurm` when above the local threshold.
- Never mutate bounds, size sequence, σ, target width, or statistics cap without user ratification.
- Never submit a cell not authorized by the latest report.
- Never infer success from scheduler state or visual crossing alone.
- Persist intent before side effects and receipts immediately afterward.
- Reconcile `SUBMITTING` after a crash; never retry it blindly.
- Keep authentication material, host aliases, allocation identifiers, and non-public locations outside runtime contracts.
</checklist>
