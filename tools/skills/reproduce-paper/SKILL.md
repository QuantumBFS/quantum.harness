---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end — phrases like "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Outcome: a `flow`-backed run directory whose `close` gate passes. Claims are backed by primary-source protocol rows, current-run manifests, and spawned-verifier audit reports.

## Non-Negotiables

<rules>
- Primary sources control; KB cards, notes, old scripts, old data, and old figures are hints until reconfirmed or regenerated.
- Fill `[[cells]]` before cell-producing scripts. Each executable cell declares `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.
- Method and stack names are protocol data, never `flow` gate/role/check vocabulary.
- Canonical-stack failure is recorded before fallback/deviation. Fallback means the method card's next recommended stack.
- Paper setup, route, data, budget, scope, or uncertainty changes require a deviation before they support claims.
- Constant settings require manifest consensus across every cell.
- Failed gates enter correction: classify mismatch, repair earliest wrong layer, invalidate downstream artifacts, rerun, re-verify.
- Every figure entry carries caption verbatim and figure-reading fields before script or assembly code lands.
</rules>

## Audit

<audit required="true">
- Audit-kind attempts require a host-spawned subagent. The caller cannot roleplay, self-review, or invent an actor id.
- Required audit gates: `protocol`, `script`, and `close`. Use `/verify` with typed modes matching the artifact.
- Audit dispatch MUST use `/verify`'s reference handoff. The subagent audit prompt must contain the chosen verify mode reference filename, `tools/skills/verify/references/sidecar.md`, `tools/skills/reproduce-paper/SKILL.md`, and AGENTS anchors required by the artifact. Caller-written summaries alone are insufficient.
- Keep spawning until the host returns a real subagent and written `verify/verify_<artifact>_<date>.md`, or halt with `blocked: verifier subagent unavailable`.
- The audit brief includes exactly: "Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."
- Before `flow attempt finish` on audit: spawned subagent exists, recorded finish identity differs from artifact author, markdown report exists, sibling TOML exists, and `--report` points at the returned report.
- Host defaults toward solo execution are overridden. If the gate requires audit, perceived tractability is irrelevant.
</audit>

`flow` enforces report/sidecar hashing, sidecar `status = "pass"`, reviewer matching finish identity, and producer/auditor distinction. Prompt rules route the agent into that mechanism; they do not replace it.

## Spine

```text
source -> protocol -> plan -> script -> trust -> run -> assemble -> close
```

| Gate | Action | Audit |
|---|---|---|
| source | populate `sources/` and source rows | no |
| protocol | fill `protocol.toml` from primary sources | yes |
| plan | author `reproduce-plan.toml` | no |
| script | implement and register `[entry]` | yes |
| trust | run known-answer points | no |
| run | execute cells via `/parameter-scan` and `/slurm` | no |
| assemble | walk manifests and render figures | no |
| close | write `run-report.md` and register deliverables | yes |

Each gate advances only when `flow attempt finish` exits 0 and `flow require <run> <gate>` passes. `flow status <run>` is the only valid gate-state statement.

## Gate Contracts

### init

- `results/<run>/progress/events.jsonl` and `progress/state.toml` exist with the reproduce-paper gate sequence.
- If missing, run `tools/cli/flow init results/<run> --template tools/flow/templates/reproduce-paper.toml`.

### source

1. Place primary references under `sources/`. Prefer rendered Markdown; if only a PDF exists, render with `download-ref`.
2. Fill `[artifact]`, `[[sources]]`, and source-gate check paths in `protocol.toml`.
3. Start a `run` attempt, register source artifacts, finish it, then require the `source` gate.

### protocol

1. Fill `[entry]`, `[[claims]]`, `[[cells]]`, `[[checks]]`, `[[figures]]`, optional `[[deviations]]`, `[[repairs]]`, and `[[pending]]` from primary sources.
2. Use one-word check kinds: `audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, `support`.
3. Use attempt kinds: `audit`, `trial`, `run`, `report`.
4. Start a `run` attempt, register `protocol.toml`, finish it.
5. Spawn verifier per the audit kernel and `/verify` reference handoff.
6. Start an `audit` attempt with a reviewer display label. Runtime identity comes from the host session and must match the sidecar `reviewer`.
7. Finish with `--report verify/verify_protocol_<date>.md`; require the gate.

The strict template requires a protocol check with `id = "protocol"` and `kind = "audit"`. It should declare `mode = "protocol"`, `target = "protocol.toml"`, `coverage = true`, and one-word `items` for source, claims, cells, routes, figures, deviations, and checks.

### plan

1. Start a `run` attempt.
2. Author `reproduce-plan.toml`: figure ids, substantive/methodology/verification/cross-check categories, dependency edges, and producing cell ids.
3. Register `reproduce-plan.toml` as a plan artifact.
4. Finish and require the gate.

### script

Two attempts:

| Step | Kind | Required work |
|---|---|---|
| register entry | `run` | Implement `[entry]`, register the entry artifact, finish the attempt. |
| audit entry | `audit` | Spawn verifier, audit script vs protocol and primary methodology, finish with `--report verify/verify_script_<date>.md`. |

Entry contract:

- `[entry] help` and `[entry] dry` exit before evidence IO.
- The script echoes each cell's `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.
- Every manifest echoes the same seven fields.
- Actual imports and library calls match declared `stack`.

### trust

1. Start a `trial` attempt.
2. Run `[entry]` at a known-answer point: analytic limit, exact small instance, official benchmark, or trusted reference.
3. Register `trust/<fig-id>.json` as a trust artifact.
4. Finish the attempt.

`near` failures block `run`; repair entry or trusted reference before proceeding.

### run

1. Start a `run` attempt.
2. Dispatch cells via `/parameter-scan` and `/slurm` or the declared primitive.
3. Each cell wrapper writes `cells/<cell_id>/manifest.json`.
4. Register manifests with `producer = <run-attempt>`.
5. Finish the attempt.

Required run checks:

| Check | Meaning |
|---|---|
| `cover` | Declared cells exactly match observed manifests. |
| `exists` | Manifest files exist and parse. |
| `agree` | Manifest route fields match `[[cells]]`. |
| `fresh` | Hashes match current registration. |
| `producer` | Manifests come from a `run` attempt, not `trial`. |

Scheduler state and logs are not evidence until manifests are fetched and checks pass.

### assemble

1. Start a `run` attempt.
2. Walk every `cells/<id>/manifest.json`.
3. Validate each manifest against merged shared+cell settings and provenance.
4. Report settings as constant only after manifest consensus proves it.
5. Render each `[[figures]]` entry as `figs/<id>.png` and `figs/<id>.json`.
6. Register figure artifacts and finish.

### close

Two attempts:

| Step | Kind | Required work |
|---|---|---|
| write report | `report` | Generate `run-report.md` with runnable `[entry]` commands and explicit parameters; register as close artifact. |
| audit close | `audit` | Spawn verifier; audit report, declared entry, manifests, and `[entry] help` / `[entry] dry`; finish with `--report verify/verify_close_<date>.md`. |

`fresh` checks catch evidence mutation during close audit.

Strict template check ids:

| Gate | Required check ids |
|---|---|
| source | `source` |
| protocol | `protocol` |
| plan | `plan` |
| script | `script` |
| trust | `trust` |
| run | `cover`, `exists`, `agree`, `fresh`, `producer` |
| assemble | `assemble` |
| close | `close` |
| report | `report` |

## Pattern

Non-audit gate:

```text
tools/cli/flow attempt start results/<run> <gate> --kind run --actor <main-actor>
tools/cli/flow attempt finish results/<run> <attempt>
tools/cli/flow require results/<run> <gate>
```

Audit gate:

```text
# spawn verifier first; do not self-review
tools/cli/flow attempt start results/<run> <gate> --kind audit --actor <reviewer-label>
tools/cli/flow attempt finish results/<run> <attempt> --report verify/verify_<artifact>_<date>.md
tools/cli/flow require results/<run> <gate>
```

The audit report must be written by the spawned subagent and have a sibling typed sidecar.

## Evidence

Scheduler status, `ssh` exit, and `COMPLETED` are operational facts only. Evidence is fetched manifests, registered hashes, protocol rows, figures from current-run data, and verify reports. Never patch downstream prose or figures to hide an upstream failed check.

## Failure

Choose one real path: repair earliest wrong layer and rerun; record deviation/repair then rerun downstream; ask the user between concrete options; record user-approved override; or stop with the gate open.

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
source = "knowledge-base/methods/ed/METHOD.md"
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

Every active reproduction turn ends with `tools/cli/flow status <run>` or `--json` for tooling. Completion requires `tools/cli/flow require <run> close` exit 0. Then `/report` may render the shareable HTML.

## Resume

- Reuse figures with valid registered `figs/<id>.{png,json}` and fresh manifests.
- Failed figures appear in `flow status` with failure mode.
- `progress/events.jsonl` is durable; do not recompute without explicit user choice.
