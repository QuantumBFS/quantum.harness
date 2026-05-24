---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end — phrases like "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Outcome: a `results/<run>/` directory whose `run-report.md` lists primary-source-grounded claims, current-run manifests, and reproduced figures.

## Non-Negotiables

<rules>
- Primary sources control; KB cards, notes, old scripts, old data, and old figures are hints until reconfirmed or regenerated.
- Fill `[[cells]]` before cell-producing scripts. Each executable cell declares `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.
- Canonical-stack failure is recorded before fallback/deviation. Fallback means the method card's next recommended stack.
- Paper setup, route, data, budget, scope, or uncertainty changes require a deviation before they support claims.
- Constant settings require manifest consensus across every cell.
- Failed checks enter correction: classify mismatch, repair earliest wrong layer, invalidate downstream artifacts, rerun.
- Every figure entry carries caption verbatim and figure-reading fields before script or assembly code lands.
- Figure semantics are paper contracts: each figure entry names the plotted metric/observable, basis or representation, operator or bra/ket objects for overlaps, state-selection rule, sector, window, normalization, and nearby states explicitly excluded. Proxy selectors such as nearest energy, highest overlap, or a convenient representative must be validated against the paper-defined identity or recorded as deviations.
</rules>

## Spine

```text
source -> protocol -> plan -> script -> trust -> run -> assemble -> close
```

| Step | Action |
|---|---|
| source | populate `sources/` and source rows |
| protocol | fill `protocol.toml` from primary sources |
| plan | author `reproduce-plan.toml` |
| script | implement `[entry]` |
| trust | run known-answer points |
| run | execute cells via `/parameter-scan` and `/slurm` |
| assemble | walk manifests and render figures |
| close | write `run-report.md` and register deliverables |

## Step Contracts

### source

1. Place primary references under `sources/`. Prefer rendered Markdown; if only a PDF exists, render with `download-ref`.
2. Fill `[artifact]`, `[[sources]]`, and source paths in `protocol.toml`.

### protocol

1. Fill `[entry]`, `[[claims]]`, `[[cells]]`, `[[figures]]`, optional `[[deviations]]` and `[[repairs]]` from primary sources.
2. For figure-producing claims, fill paper-defined figure semantics: metric/observable, basis or representation, overlap bra/ket or operator objects, state-selection rule, sector, window, normalization, excluded nearby states, and any proxy selector validation/deviation.

### plan

Author `reproduce-plan.toml`: figure ids, substantive/methodology/verification/cross-check categories, dependency edges, and producing cell ids.

### script

Entry contract:

- `[entry] help` and `[entry] dry` exit before evidence IO.
- The script echoes each cell's `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.
- Every manifest echoes the same seven fields.
- Actual imports and library calls match declared `stack`.
- Figure-producing code implements the protocol's paper-defined metric/basis/state/overlap contract. A proxy state selector must write evidence that the selected object satisfies the paper identity.

### trust

1. Run `[entry]` at a known-answer point: analytic limit, exact small instance, official benchmark, or trusted reference.
2. Save `trust/<fig-id>.json`.

Near-failure blocks `run`; repair entry or trusted reference before proceeding.

### run

1. Dispatch cells via `/parameter-scan` and `/slurm` or the declared primitive.
2. Each cell wrapper writes `cells/<cell_id>/manifest.json`.

Required manifest properties:

| Property | Meaning |
|---|---|
| coverage | Declared cells exactly match observed manifests. |
| exists | Manifest files exist and parse. |
| agree | Manifest route fields match `[[cells]]`. |
| fresh | Hashes match current registration. |

Scheduler state and logs are not evidence until manifests are fetched.

### assemble

1. Walk every `cells/<id>/manifest.json`.
2. Validate each manifest against merged shared+cell settings and provenance.
3. Report settings as constant only after manifest consensus proves it.
4. Render each `[[figures]]` entry as `figs/<id>.png` and `figs/<id>.json`.

### close

Generate `run-report.md` with runnable `[entry]` commands and explicit parameters. Register deliverables and resolve outstanding deviations or repairs.

## Evidence

Scheduler status, `ssh` exit, and `COMPLETED` are operational facts only. Evidence is fetched manifests, protocol rows, and figures from current-run data. Never patch downstream prose or figures to hide an upstream failure.

## Failure

Choose one real path: repair earliest wrong layer and rerun; record deviation/repair then rerun downstream; ask the user between concrete options; record user-approved override; or stop and report.

## Cell Routes

Each executable cell declares:

```toml
[[cells]]
id = "cell-0001"
claims = ["claim.example"]
figures = ["fig1a"]
method = "ed"
stack = "xdiag"
route = "canonical"  # paper | canonical | fallback | deviation
source = ".knowledge/methods/ed/METHOD.md"
check = "julia --project=julia-env -e 'using XDiag'"
state = "passed"     # passed | failed | skipped | pending
scope = "full"       # full | partial | sketch
deviation = ""
```

Route meanings:

- `paper` — primary source or official code/data specifies the route.
- `canonical` — harness method card plus stack profile authorizes it.
- `fallback` — next recommended fallback stack in the method card.
- `deviation` — any other route, justified by a `[[deviations]]` row before compute.

`state = "passed"` requires the check to have actually run or a primary/official route to have been inspected enough to support the claim. `failed`, `skipped`, or `pending` blocks compute unless explicitly scoped as `deviation` or `pending`.

If a route check fails from local environment problems, record failed/pending first. Do not inspect alternate stacks until the protocol declares fallback/deviation. For ED, the Python fallback is `quspin`; generic NumPy/SciPy ED is a deviation unless official paper code uses it.

## Closeout

Completion requires `run-report.md` with all declared claims backed by current-run manifests or recorded deviations. Then `/report` may render the shareable HTML.

## Resume

- Reuse figures with valid registered `figs/<id>.{png,json}` and fresh manifests.
- Do not recompute without explicit user choice.
