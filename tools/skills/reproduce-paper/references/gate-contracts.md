# reproduce-paper gate contracts reference

Read before authoring or advancing a gate. The parent `SKILL.md` carries the audit kernel; this file carries detailed mechanics.

## init

- `results/<run>/progress/events.jsonl` exists.
- `results/<run>/progress/state.toml` exists with the reproduce-paper gate sequence.
- If missing, run:

```bash
tools/cli/flow init results/<run> --template tools/flow/templates/reproduce-paper.toml
```

## source

1. Place primary references under `sources/`. Prefer rendered Markdown; if only a PDF exists, render with `download-ref`.
2. Fill `[artifact]`, `[[sources]]`, and source-gate check paths in `protocol.toml`.
3. Start a `run` attempt, finish it, then require the `source` gate.

## protocol

1. Fill `[entry]`, `[[claims]]`, `[[cells]]`, `[[checks]]`, `[[figures]]`, optional `[[deviations]]`, `[[repairs]]`, and `[[pending]]` from primary sources.
2. Use one-word check kinds: `audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, `support`.
3. Use attempt kinds: `audit`, `trial`, `run`, `report`.
4. Start a `run` attempt for the protocol authoring work, register `protocol.toml`, finish it.
5. Spawn verifier per the audit kernel. The brief includes the exact coverage line from the parent skill.
6. Start an `audit` attempt with the returned subagent id as the actor label.
7. Finish with `--report verify/verify_protocol_<date>.md`; require the gate.

The strict template requires a protocol check with `id = "protocol"` and `kind = "audit"`. It should declare `mode = "protocol"`, `target = "protocol.toml"`, `coverage = true`, and one-word `items` for source, claims, cells, routes, figures, deviations, and checks.

## plan

1. Start a `run` attempt.
2. Author `reproduce-plan.toml`: figure ids, substantive/methodology/verification/cross-check categories, dependency edges, and producing cell ids.
3. Register `reproduce-plan.toml` as a plan artifact.
4. Finish and require the gate.

## script

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

## trust

For each substantive figure:

1. Start a `trial` attempt.
2. Run `[entry]` at a known-answer point: analytic limit, exact small instance, official benchmark, or trusted reference.
3. Register `trust/<fig-id>.json` as a trust artifact.
4. Finish the attempt.

`near` failures block `run`; repair entry or trusted reference before proceeding.

## run

1. Start a `run` attempt.
2. Dispatch cells via `/parameter-scan` and `/slurm` or the declared primitive.
3. Each cell wrapper writes `cells/<cell_id>/manifest.json`.
4. Register manifests with `producer = <run-attempt>`.
5. Finish the attempt.

Required checks:

| Check | Meaning |
|---|---|
| `cover` | Declared cells exactly match observed manifests. |
| `exists` | Manifest files exist and parse. |
| `agree` | Manifest route fields match `[[cells]]`. |
| `fresh` | Hashes match current registration. |
| `producer` | Manifests come from a `run` attempt, not `trial`. |

Scheduler state and logs are not evidence until manifests are fetched and checks pass.

## assemble

1. Start a `run` attempt.
2. Walk every `cells/<id>/manifest.json`.
3. Validate each manifest against merged shared+cell settings and provenance.
4. Report settings as constant only after manifest consensus proves it.
5. Render each `[[figures]]` entry as `figs/<id>.png` and `figs/<id>.json`.
6. Register figure artifacts and finish.

## close

Two attempts:

| Step | Kind | Required work |
|---|---|---|
| write report | `report` | Generate `run-report.md` with runnable `[entry]` commands and explicit parameters; register as close artifact. |
| audit close | `audit` | Spawn verifier; audit report, declared entry, manifests, and `[entry] help` / `[entry] dry`; finish with `--report verify/verify_close_<date>.md`. |

`fresh` checks catch evidence mutation during close audit.

The strict template requires check ids:

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

## Failed Checks

Legal responses:

1. Backchain to the earliest failed gate.
2. Repair the evidence and run a new attempt.
3. Record a deviation via `flow deviate` or a `[[deviations]]` row.
4. Record a repair row with `from`, `wrong`, `changed`, `invalidate`, `state`.
5. Present a concrete user decision via the host option API.
6. Record a user-approved override.
7. Stop.

## Resume

- Reuse figures with valid registered `figs/<id>.{png,json}` and fresh manifests.
- Failed figures appear in `flow status` with failure mode.
- `progress/events.jsonl` is durable; do not recompute without explicit user choice.
