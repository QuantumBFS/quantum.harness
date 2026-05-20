---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end. Plans the multi-figure sequence, composes the harness primitives, and closes with a declared entry plus run report. Generic over papers.
---

# reproduce-paper

Outcome: a `flow`-backed run directory whose `close` gate passes, with every claim backed by a current-run manifest and every audit attempt closed by a spawned-subagent's returned verify report. This skill sequences the eight gates of the spine and composes the primitives; it does not advance state on its own — `flow attempt finish` does.

## Non-negotiables

<checklist name="rules">

- **N1.** Primary sources first. KB cards, old scripts, previous figures, notes, and summaries are hints until confirmed or regenerated against a primary source.
- **N2.** Fill `[[cells]]` before any cell-producing script lands. Each executable cell carries seven fields: `method`, `stack`, `route`, `source`, `check`, `state`, `scope`.
- **N3.** Method and stack live as data values in `protocol.toml`. `flow` records gates, attempt roles, and check kinds without seeing them.
- **N4.** When a canonical stack fails locally, the next move is to record that cell's `state = "failed"` (or `"pending"`) in `protocol.toml`. `fallback` or `deviation` is declared only after that record; until then, the alternate stack is unobserved.
- **N5.** Fallback means the method card's next recommended stack. A source note's bibliography order and installed packages are not stack priority.
- **N6.** Target shape is fixed. Any change to paper setup, route, data, budget, scope, or uncertainty is a `[[deviations]]` row before compute.
- **N7.** Settings are constant only after consensus. Assemble from all manifests; never infer global state from one cell.
- **N8.** Failed gates trigger the correction loop. Classify the mismatch, repair the earliest wrong layer, invalidate downstream artifacts, rerun, then re-verify.
- **N9.** Every `[[figures]]` entry carries the paper's caption text verbatim before any cell-producing script for that figure lands. The `script` and `result` audit modes refuse to pass without this; see [Pre-compute figure invariant](#pre-compute-figure-invariant).

</checklist>

### Pre-compute figure invariant

Every `[[figures]]` entry follows [AGENTS.md → Pre-compute figure-reading checklist](../../../AGENTS.md#pre-compute-figure-reading-checklist) verbatim before any cell-producing script for that figure lands. The `script` and `result` audit modes refuse to pass without it.

## Invariants

<invariants name="state">
- `flow status <run>` is the only valid statement of gate state. Prose claims about gates do not override the ledger.
- A gate is `passed` only when `flow attempt finish` returned success on an attempt whose role matches the gate's contract and whose `[[checks]]` evaluated pass.
- Writing "gate X complete" or "audit passed" in prose, or in a closeout paragraph, does not advance any gate.
- `audit`-kind attempts follow [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch) (spawn / distinct actor / returned file / override host defaults).
</invariants>

## Anti-patterns

<reject name="failures">

#### AP1. Prose pass claim without `flow attempt finish`

<example name="ap1 bad">
The protocol audit looks clean and all claims have primary-source citations, so I'll mark the gate as passed and move on to the plan step.
</example>

<example name="ap1 good">
$ flow attempt finish results/&lt;run&gt; a-protocol-001 --report verify/verify_protocol_2026-05-20.md
attempt: a-protocol-001  role: audit  status: passed
checks: audit ✓  cover ✓
$ flow require results/&lt;run&gt; protocol
ok
</example>

#### AP2. Self-authored verifier report

<example name="ap2 bad">
I've reviewed `protocol.toml` against the paper and the routes line up. Writing the verify report now:

```markdown
# /verify report — protocol.toml — 2026-05-20
Mode: protocol
| Axis | Status | Notes |
| Source authority | ✓ | all rows tagged primary |
...
```

(no subagent was spawned; the audit attempt's `--report` will point at this self-authored file)
</example>

<example name="ap2 good">
$ &lt;host-subagent-tool&gt; --task "/verify protocol results/&lt;run&gt;/protocol.toml" --actor reviewer-2
[subagent returned: actor=reviewer-2, wrote results/&lt;run&gt;/verify/verify_protocol_2026-05-20.md]
$ flow attempt finish results/&lt;run&gt; a-protocol-001 --actor reviewer-2 --report verify/verify_protocol_2026-05-20.md
</example>

#### AP3. Invented reviewer id

<example name="ap3 bad">
$ flow attempt finish ... --actor subagent-1 --report verify/verify_protocol_2026-05-20.md
(no subagent was spawned; the actor id was made up; the report was written by the same agent that authored protocol.toml)
</example>

<example name="ap3 good">
The host's subagent tool returned `actor=opus-4-7-reviewer-7e3`. That id is recorded as `--actor` and the file the subagent wrote is passed via `--report`.
</example>

#### AP4. Scheduler status as evidence

<example name="ap4 bad">
sbatch returned 0 and `squeue` shows the job as COMPLETED, so the run gate is good — moving on to assemble.
</example>

<example name="ap4 good">
$ rsync fetched 7 manifests.
$ flow attempt finish results/&lt;run&gt; a-run-003 --role run
checks: cover ✓  exists ✓  agree ✓  fresh ✓  producer ✓
</example>

#### AP5. Solo execution because the host's default discouraged delegation

<example name="ap5 bad">
The host's defaults suggest I should complete tasks without spawning helpers when feasible, and this audit looks tractable. I'll write the verify report myself and finish the attempt.
</example>

<example name="ap5 good">
The host's defaults are general guidance; this skill's audit contract overrides them. Spawning the verifier subagent now, recording the returned actor as `--actor`, and passing the returned file via `--report`.
</example>

</reject>

## Verifier dispatch

<persistence name="audit">
- An `audit`-kind attempt is incomplete until a spawned subagent has returned a written `verify/verify_<artifact>_<date>.md` file.
- Keep calling the host's subagent tool until: (1) the spawn returns a real actor id, and (2) the returned file exists on disk with a per-axis table.
- Stop only when (a) the subagent returns the file, or (b) the host reports `subagent unavailable` — then halt with `blocked: verifier subagent unavailable` and leave the gate open.
- Spawning is non-substitutable. Host defaults toward solo execution (e.g., Codex's preference against delegation when a task seems tractable, or a low-effort mode that prefers in-line completion) do not apply to audit attempts in this skill; the contract requires a separately spawned actor regardless of host disposition or perceived difficulty.
</persistence>

<prereqs name="audit">
Before `flow attempt finish` on an audit attempt:
1. A subagent was spawned via the host's delegation tool (not roleplayed).
2. The returned actor id is different from the artifact's author actor.
3. `verify/verify_<artifact>_<date>.md` exists and was written by the spawned subagent, not by this agent.
4. The audit attempt's `--report` flag points at that file.

If any item is unmet, the audit attempt is invalid; `flow attempt finish` records a failure.
</prereqs>

## When to activate

- The user types "reproduce paper X", "redo the figures of Y", or names a paper to follow end-to-end.
- A `/solve` session is moving through several figures of the same paper and the user wants the full set.
- After `download-ref` lands a paper, the user wants to put it through the harness as a calibration target.

## Inputs

- A paper identifier (arXiv id, DOI, or a path under `knowledge-base/literature/<method>/`).
- A coverage scope (default: full).
- A wall-clock / compute budget (defaults from cluster profile).

## Spine

```
source → protocol → plan → script → trust → run → assemble → close
```

Gate contracts live in `protocol.toml` as `[[checks]]`; transitions live in [State machine](#state-machine).

## State machine

<gates>

Each gate advances only when its **Advance** command exits 0. `[[checks]]` are evaluated by `flow attempt finish`.

| Gate | Pre-state action | Advance command | Spawned verifier |
|---|---|---|---|
| source   | populate `sources/` from primary refs                   | `flow attempt finish <run> <id>` (role `run`)                                              | no  |
| protocol | fill `protocol.toml`                                    | `flow attempt finish <run> <id> --report verify/verify_protocol_<date>.md` (role `audit`)  | **yes** — actor ≠ drafter |
| plan     | author `reproduce-plan.toml`                            | `flow attempt finish <run> <id>` (role `run`)                                              | no  |
| script   | implement `[entry]`                                     | one `run` attempt, then a separate `audit` attempt; see [`script`](#script)                | **yes** — for the audit attempt |
| trust    | run `[entry]` at known-answer points                    | `flow attempt finish <run> <id>` (role `trial`); check kind `near`                         | no  |
| run      | dispatch via `/parameter-scan` + `/slurm`               | `flow attempt finish <run> <id>` (role `run`); checks `cover` / `exists` / `agree` / `fresh` / `producer` | no  |
| assemble | walk all manifests, render figures                      | `flow attempt finish <run> <id>` (role `run`)                                              | no  |
| close    | `run-report.md` + register `[entry]` artifact           | `flow attempt finish <run> <id> --report verify/verify_close_<date>.md` (role `audit`)     | **yes** — actor ≠ report writer |

Gate 0 (`flow init <run>`) is the prerequisite of every row; see [`init`](#init).

</gates>

## Gate contracts

Each gate's commands run in the listed order. Skipping a `flow` call leaves the ledger out of sync with the file system; `flow attempt finish` then refuses to record success.

### init

<prereqs name="init">
- `results/<run>/progress/events.jsonl` exists.
- `results/<run>/progress/state.toml` exists with the gate sequence from the template.
- If either is missing, `tools/cli/flow init results/<run> --template tools/flow/templates/reproduce-paper.toml` runs before any other run-dir write.
</prereqs>

### source

<gate id="source">
1. Place primary references under `sources/`. Prefer rendered Markdown; if only a PDF exists, render via `python3 tools/skills/download-ref/scripts/render.py --pdf <pdf> --out <markdown>` and cite the Markdown.
2. Fill `[artifact]`, `[[sources]]`, and the `source` gate check paths in `protocol.toml`.
3. `flow attempt start <run> source --role run --actor <id>`
4. `flow attempt finish <run> <attempt>`
5. `flow require <run> source` exits 0 before the next gate begins.
</gate>

### protocol

<gate id="protocol">
1. Fill the rest of `protocol.toml` from primary sources: `[entry]`, `[[claims]]`, `[[cells]]`, `[[checks]]`, `[[figures]]`, optional `[[deviations]]`, `[[repairs]]`, `[[pending]]`. One-word check kinds (`audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, `support`); unique check ids; attempt roles `audit` / `trial` / `run` / `report`.
2. Spawn the verifier per `<persistence name="audit">` with the verbatim brief: *"Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."*
3. `flow attempt start <run> protocol --role audit --actor <verifier-actor-id>` — the actor id is the one returned by the host's subagent tool, distinct from whoever drafted the protocol.
4. The verifier writes `verify/verify_protocol_<date>.md`.
5. `flow attempt finish <run> <attempt> --report verify/verify_protocol_<date>.md`
</gate>

### plan

<gate id="plan">
1. `flow attempt start <run> plan --role run --actor <id>`
2. Author `reproduce-plan.toml` — figure ids, categorisations (substantive / methodology / verification / cross-check), dependency edges, producing `cell` ids.
3. `flow artifact add <run> reproduce-plan reproduce-plan.toml --kind plan --producer <attempt>`
4. `flow attempt finish <run> <attempt>`
</gate>

### script

<gate id="script">

Two attempts; finish independently.

| Step | Role | Required commands |
|---|---|---|
| 6a — register entry | `run` | `flow attempt start <run> script --role run --actor <id>`; implement `[entry]`; `flow artifact add <run> entry <entry-path> --kind entry --producer <attempt>`; `flow attempt finish <run> <attempt>` |
| 6b — audit entry | `audit` | spawn verifier per `<persistence name="audit">`; `flow attempt start <run> script --role audit --actor <distinct>`; `flow attempt finish <run> <attempt> --report verify/verify_script_<date>.md` |

<checklist name="entry">
- `[entry] help` and `[entry] dry` exit before any evidence IO.
- The script echoes each cell's `method`, `stack`, `route`, `source`, `check`, `state`, `scope`.
- Every produced manifest echoes the same seven fields.
</checklist>

</gate>

### trust

<gate id="trust">

For each substantive figure:

1. `flow attempt start <run> trust --role trial --actor <id>`
2. Run `[entry]` at a known-answer point (analytic limit, exact small instance, official benchmark).
3. `flow artifact add <run> trust-<fig-id> trust/<fig-id>.json --kind trust --producer <attempt>`
4. `flow attempt finish <run> <attempt>`

Check kind: `near`. A `trust` failure blocks `run`; the only positive next move is to repair the entry or the trusted reference and retry.

</gate>

### run

<gate id="run">
1. `flow attempt start <run> run --role run --actor <id>`
2. Dispatch via `/parameter-scan` + `/slurm` (or the declared primitive). Cell wrappers register manifests via `flow artifact add ... --kind manifest --producer <attempt>`.
3. `flow attempt finish <run> <attempt>`
</gate>

<output name="evidence">

The `run` gate accepts as evidence only:

| Check kind | What it enforces |
|---|---|
| `cover`    | Every claim's required cells produced a manifest. |
| `exists`   | Each registered manifest file is on disk and parseable. |
| `agree`    | Each manifest's route fields match its `[[cells]]` row. |
| `fresh`    | Manifest hash matches current registration; no post-hoc edits. |
| `producer` | Each manifest's producer attempt has role `run`. |

All five evaluate pass before the gate advances. Scheduler state, `ssh` exit codes, and on-cluster log files are operational signals; they do not satisfy this contract.

</output>

### assemble

<gate id="assemble">
1. `flow attempt start <run> assemble --role run --actor <id>`
2. Walk every `cells/<id>/manifest.json`; require consensus on settings tagged constant and route-field agreement with `[[cells]]`. No claim about consensus is admissible from the first completed manifest alone.
3. Render each `[[figures]]` entry as `figs/<id>.png` + `figs/<id>.json`.
4. For each rendered figure:
   - `flow artifact add <run> fig-<id> figs/<id>.png --kind figure --producer <attempt>`
   - `flow artifact add <run> fig-<id>-json figs/<id>.json --kind figure-data --producer <attempt>`
5. `flow attempt finish <run> <attempt>`
</gate>

### close

<gate id="close">

Two attempts; the audit's `--actor` is strictly different from the report writer's.

| Step | Role | Required commands |
|---|---|---|
| 10a — write report | `report` | `flow attempt start <run> close --role report --actor <writer>`; generate `run-report.md` with `[entry]` commands runnable and all parameters explicit; `flow artifact add <run> run-report run-report.md --kind close-report --producer <attempt>`; `flow attempt finish <run> <attempt>` |
| 10b — audit close | `audit` | spawn verifier per `<persistence name="audit">`; `flow attempt start <run> close --role audit --actor <distinct>`; `[entry] help` and `[entry] dry` execute during the audit; `flow attempt finish <run> <attempt> --report verify/verify_close_<date>.md` |

`fresh` checks catch any evidence mutation during 10b. After `close` passes, `/report` renders the HTML deliverable.

</gate>

## Composition

- **Parameter sweeps** → `/parameter-scan`
- **Critical scaling** → `/scaling-fit`
- **Cross-checks** → `/cross-method-check`
- **Audits** (gate audit attempts in any mode) → `/verify`. See [Verifier dispatch](#verifier-dispatch).
- **Cluster execution** → `/slurm` (called by `/parameter-scan`).
- **HTML deliverable** → `/report` consumes the run dir after `close` passes.
- **User-facing forks** → see [AGENTS.md → Output norms](../../../AGENTS.md#ui-ux) (AskUserQuestion at genuine forks; 2–3 options; recommended first).

## Cell routes

See N3: `flow` is a ledger; method and stack live in protocol data, not in `flow` vocabulary. `reproduce-paper` never hardcodes method or stack names; it requires the protocol to name them.

Per executable cell:

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
state = "passed"     # passed | failed | skipped
scope = "full"       # full | partial | sketch
deviation = ""
```

Meanings:

- `paper` — primary source or official code/data specifies the route.
- `canonical` — harness method card plus `tools/software/stacks/<stack>.toml` authorize the route.
- `fallback` — next recommended fallback stack in the method card, with source cited.
- `deviation` — any other route; `deviation` names a `[[deviations]]` row before compute.

<example name="deviation bad">
route = "deviation"
deviation = "no built-in basis"
</example>

<example name="deviation good">
route = "deviation"
deviation = "custom basis would cost 3× wall-time vs raw LAPACK; see [[deviations]] row dev.basis-cost"
</example>

`flow` remains method-blind. It records the protocol, artifacts, and check outcomes; `/verify` decides whether the declared route is supported by the cited source and whether the script/manifests match it.

`state` is the route-check result. Set to `passed` only after the check has actually run or the primary/official route has been inspected enough to support the claim. A `failed`, `skipped`, or empty state blocks compute unless the cell is explicitly scoped as `deviation` or `pending`.

If the route check fails because of a local environment problem, stop at the failed state. Do not inspect Python, QuSpin, SciPy, quimb, or any alternate stack unless the protocol already declares that stack as `fallback` or `deviation`. For ED, the Python fallback is `quspin`; generic NumPy/SciPy ED is a deviation unless it is official paper code.

## Failed checks

<invariants name="repair">
- Repairs change evidence. The script, the protocol, the run report, and `editorial.json` are downstream of evidence; editing them so a check passes is a contract violation.
- The only legal responses to a failing check are: repair evidence, record a deviation, record a repair, present a decision, override (with reason), or stop.
</invariants>

When `flow attempt finish` reports a failing check, pick one:

1. **Backchain first.** Inspect the earliest failed gate and its declared inputs. Do not patch a downstream report to hide an upstream failure.
2. **Repair the evidence.** Fix the artifact, run a new attempt.
3. **Record a deviation.** `flow deviate <run> --id <id> --statement "..." --reason "..."` for runtime departures, or declare in `protocol.toml`'s `[[deviations]]` upfront. Both surface as ⚠ in `flow status`.
4. **Record a repair.** Add a `[[repairs]]` row with one-word fields: `from`, `wrong`, `changed`, `invalidate`, `state`.
5. **Present a decision.** Use `AskUserQuestion` then `flow decide <run> --id <id> --question "..." --choice "..."`. Decisions surface in `flow status`.
6. **Override.** `flow override <run> <check-id> --reason "<text>"`. The override is recorded forever; downstream artifacts show ⊘.
7. **Stop.** Always a real option.

## Closeout

<output name="closeout">
- Every turn ends by emitting `tools/cli/flow status <run>` (or `--json` for tools).
- The verbatim `flow status` projection is the closeout statement. No paraphrase, no upgrade, no synthesis.
- `--full` is used only when the user asks for details.
</output>

<example name="closeout good">
$ flow status results/&lt;run&gt;
gate: close (pending)
first blocker: audit attempt not finished
next: dispatch close audit subagent
</example>

<verify name="preemit">
Before ending the turn:
- The latest `flow attempt finish` exit code was 0 (or its failure is described in `flow status`).
- Any audit attempt finished in this turn has `--actor` distinct from the artifact's author and `--report` pointing at a file written by the spawned subagent.
- `flow status <run>` is the closeout statement, not a paraphrase.
- If any item above is unmet, the turn ends with the unmet item described in `flow status` projection terms.
</verify>

Before the agent declares the reproduction complete, the `close` gate passes: `tools/cli/flow require <run> close` exits 0. The default protocol template gates per-figure `figs/<id>.{png,json}` in `assemble`, then gates `run-report.md`, the explicit entry artifact, and `[entry] help` / `[entry] dry` in `close` — so completion cannot pass with missing deliverables or unsafe inspection entrypoints. If `close` fails, repair the evidence or record a deviation; do not stop with an open `close` gate.

## Resume

<output name="resume">
On re-entry into an existing run dir:
- Figures with valid `figs/<id>.{png,json}` and registered manifests passing `fresh` are reused.
- Failed figures appear in `flow status` with their failure mode; retry requires user ratification via the host's option API.
- `progress/events.jsonl` is the durable ledger of all attempts; nothing is recomputed without an explicit user choice.
</output>

## Notes

- Paper-specific words (claim ids, figure ids, deviation labels) live as data values in `protocol.toml`. Never in `flow`'s vocabulary, never in this skill's check-kind names.
- Method- and stack-specific words also live as data values in `protocol.toml` and stack cards. Never add method-specific check kinds or `flow` gates.
- Methodology absorption is a side-effect of running the verification figures the paper declares — they appear alongside the substantive figures because they are also `[[figures]]` entries with `claim_ids`.
- The writeup-handoff close (declared entry + run report) happens in the `close` gate. Route to `scientific-writing` / `latex-paper-en` / `scientific-visualization` / `jupyter-notebook` for downstream artifacts.

## Related

- `/solve` — single-problem loop. This skill runs atop solve when the user wants the full paper.
- `/report` — renders the run dir as a shareable HTML page.
- `/verify` — audit subagent dispatcher; the audit-kind attempt this skill records is a `/verify` call.
- `/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/slurm` — primitives this skill orchestrates.
