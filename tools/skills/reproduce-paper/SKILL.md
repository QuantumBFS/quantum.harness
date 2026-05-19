---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end. Plans the multi-figure sequence, composes the harness primitives, and closes with a declared entry plus run report. Generic over papers.
---

# reproduce-paper

Thin orchestrator. The discipline lives in `protocol.toml`: `[[cells]]` declares the method route and `[[checks]]` declares the evidence checks evaluated mechanically by `tools/cli/flow`. This skill only sequences the work and composes the primitives.

## Non-negotiables

- Start from primary sources. KB cards, old scripts, previous figures, notes, and summaries are hints until confirmed or regenerated.
- Fill `[[cells]]` before coding. Every executable cell MUST name `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.
- Method-agnostic is not method-optional. `flow` is a ledger; DO NOT use `flow` gates, attempt roles, or check kinds as the software-stack choice.
- DO NOT probe fallback tooling just because the paper/canonical stack fails locally. Record the canonical route as `failed` or `pending`; only then declare `fallback` or `deviation` before touching the alternate stack.
- Fallback means the method card's next recommended stack. A source note's bibliography order and installed packages are not stack priority.
- DO NOT silently weaken the target. Any change to paper setup, route, data, budget, scope, or uncertainty is a `[[deviations]]` row before compute.
- DO NOT trust the first manifest as global. Assemble from all manifests; report settings as constant only after consensus.
- Failed gates are not status text. Classify the mismatch, repair the earliest wrong layer, invalidate downstream artifacts, rerun, then re-verify.

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

Each gate's contract lives in `protocol.toml` as `[[checks]]`. `flow` runs the checks on `flow attempt finish` and derives the gate status. The agent never declares pass.

## Workflow

1. **Init the ledger.** `tools/cli/flow init results/<run> --template tools/flow/templates/reproduce-paper.toml`. This is the first run-dir action.

2. **Acquire sources.** Copy `tools/templates/reproduce-paper/protocol.toml` to `results/<run>/protocol.toml`, fill `[artifact]`, `[[sources]]`, and the `source` gate check paths from primary sources, then start a `run` attempt on `source`. Use Markdown as the readable source: if an official or rendered Markdown source exists, place it under `sources/` and cite that; if only a PDF exists, store the PDF under `sources/` and render it with `python3 tools/skills/download-ref/scripts/render.py --pdf <pdf> --out <markdown>`. Finish the attempt, then `flow require <run> source` before protocol audit.

3. **Author the contract.** Fill the rest of `protocol.toml` from the primary source: `[entry]`, `[[claims]]`, `[[cells]]`, `[[checks]]`, `[[figures]]`, optional `[[deviations]]`, `[[repairs]]`, and `[[pending]]`. Each executable cell declares one route with one-word fields: `method`, `stack`, `route`, `source`, `check`, `state`, `scope`. Do this before implementing scripts or running compute. Use one-word check kinds: `audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, `support`; keep check ids unique because they are override handles. Use attempt roles `audit`, `trial`, `run`, `report`.

4. **Audit the contract.** MUST SPAWN a real verifier subagent for an `audit`-kind attempt on the `protocol` gate (different `--actor` from whoever drafted the protocol). Do not write the verifier report yourself. If no verifier can be spawned, stop with `blocked: verifier subagent unavailable` and leave the gate open. Finish the attempt only after the verifier returns a report, using `--report <path>`.

5. **Plan the figure graph.** Author `results/<run>/reproduce-plan.toml` (figure ids, categorisations — substantive / methodology / verification / cross-check — dependency edges, and the `cell` ids that produce them). Start and finish the `plan` attempt.

6. **Implement the entry.** One declared `[entry]` runs the reproduction. Start a `run` attempt on `script`; register the entry as an artifact (`flow artifact add`); start a separate `audit` attempt; finish both. The entry's `help` and `dry` commands must exit before evidence IO. The script and every manifest must echo each cell's `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.

7. **Trust.** Start a `run` attempt on `trust`. For each substantive figure, run the entry at a point where the answer is known (analytic limit, exact small instance, official benchmark), write trust artifacts under `trust/`, register them, and finish the attempt. Declare the check as `kind = "near"`. Failure here blocks `run`.

8. **Run.** Dispatch via `/parameter-scan` + `/slurm` (or the declared primitive). The cell wrappers register manifests as artifacts with `--producer <run-attempt>`. The `run` gate's `[[checks]]` enforce `cover`, `exists`, `agree`, `fresh`, and `producer = "run"`. A manifest whose route fields do not match its `[[cells]]` block is invalid evidence. Remote job status, `ssh` exit status, and scheduler `COMPLETED` are operational facts only; fetched manifests and checks are the evidence.

9. **Assemble.** Start a `run` attempt on `assemble`. Walk all run manifests, validate consensus/support and route-field agreement, and produce each figure as `figs/<id>.png` plus `figs/<id>.json` (interactive plot source). Never infer global settings from the first completed cell. Register assembled artifacts such as `figs/*` with the `run` attempt and finish it.

10. **Close.** Start a `report` attempt on `close`; generate `run-report.md`; keep the declared `[entry]` commands runnable with all parameters explicit. Register close-stage artifacts such as `run-report.md` with the `report` attempt; the entry artifact remains producer `run`. Finish the report attempt, then independently audit the close. The close gate runs `[entry].help` and `[entry].dry`; any evidence mutation should be caught by `fresh`.

11. **Render the deliverable.** `/report` consumes the run dir.

## Composition

- **Parameter sweeps** → `/parameter-scan`
- **Critical scaling** → `/scaling-fit`
- **Cross-checks** → `/cross-method-check`
- **Audits** (gate audit attempts in any mode) → MUST SPAWN a real verifier subagent with the host subagent/delegation tool; pass it the protocol + primary source + artifact under review; have it write `verify/verify_<artifact>_<date>.md`; record the audit attempt with the returned verifier actor id. Role text is not verification.
- **Cluster execution** → `/slurm` (called by `/parameter-scan`).
- **User-facing forks** → host platform's option API (Claude Code: `AskUserQuestion`; Codex: equivalent). Three options max, recommended first.

## Cell routes

`reproduce-paper` is method-agnostic, not method-optional. It never hardcodes method or stack names; it requires the protocol to name them.

Per executable cell:

```toml
[[cells]]
id = "cell-0001"
claims = ["claim.example"]
figures = ["fig1a"]
method = "ed"
stack = "xdiag"
route = "canonical"  # paper | canonical | fallback | deviation
source = "knowledge-base/methods/ed.md"
check = "julia --project=julia-env -e 'using XDiag'"
state = "passed"     # passed | failed | skipped
scope = "full"       # full | partial | sketch
deviation = ""
```

Meanings:

- `paper` — primary source or official code/data specifies the route.
- `canonical` — harness method card plus `tools/software/stacks/<stack>.toml` authorize the route.
- `fallback` — next recommended fallback stack in the method card, with source cited.
- `deviation` — any other route; `deviation` must name a `[[deviations]]` row before compute.

`flow` remains method-blind. It records the protocol, artifacts, and check outcomes; `/verify` decides whether the declared route is supported by the cited source and whether the script/manifests match it. Do not invent method-specific gates or use `flow` commands to force a stack choice.

`state` is the route-check result. Do not set it to `passed` until the check has actually run or the primary/official route has been inspected enough to support the claim. A `failed`, `skipped`, or empty state blocks compute unless the cell is explicitly scoped as `deviation` or `pending`.

If the route check fails because of a local environment problem, stop at the failed state. Do not inspect Python, QuSpin, SciPy, quimb, or any alternate stack unless the protocol already declares that stack as `fallback` or `deviation`. For ED, the Python fallback is `quspin`; generic NumPy/SciPy ED is a deviation unless it is official paper code.

## Failed checks

When `flow attempt finish` reports a failing check:

1. **Backchain first** — inspect the earliest failed gate and its declared inputs. Do not patch a downstream report to hide an upstream failure.
2. **Repair the evidence** — fix the artifact, run a new attempt.
3. **Record a deviation** — `flow deviate <run> --id <id> --statement "..." --reason "..."` for runtime departures, or declare in `protocol.toml`'s `[[deviations]]` upfront. Both surface as ⚠ in `flow status`.
4. **Record a repair** — for any failed gate or contract-changing edit, add a `[[repairs]]` row with one-word fields: `from`, `wrong`, `changed`, `invalidate`, `state`.
5. **Record a decision** — at any runtime fork the user hasn't pre-specified, present `AskUserQuestion` then `flow decide <run> --id <id> --question "..." --choice "..."`. Decisions surface in `flow status`.
6. **Override** — `flow override <run> <check-id> --reason "<text>"`. The override is recorded forever; downstream artifacts show ⊘.
7. **Stop** — always a real option.

Never edit the script, the protocol, or the run report to *make* a check pass without changing the underlying evidence.

## Closeout

End every turn with `tools/cli/flow status <run>` (or `flow status <run> --json` for tools). The default projection is terse: current gate, first blocker, next command. Use `flow status <run> --full` only when a human asks for details. Do not author a separate closeout paragraph that upgrades the gate status; the truthful summary always lives in the projection.

Before the agent declares the reproduction complete, the close gate must pass: `tools/cli/flow require <run> close` exits 0. The default protocol template gates per-figure `figs/<id>.{png,json}` in `assemble`, then gates `run-report.md`, the explicit entry artifact, and `[entry].help` / `[entry].dry` in `close` — so completion cannot pass with missing deliverables or unsafe inspection entrypoints. If close fails, repair the evidence or record a deviation; do not stop with an open close gate.

## Resume

The plan file and `progress/events.jsonl` are durable. Re-running this skill on an existing run dir reuses figures already produced (manifest-driven). Failed figures surface with their failure mode; not auto-retried.

## Notes

- Paper-specific words (claim ids, figure ids, deviation labels) live as data values in `protocol.toml`. Never in `flow`'s vocabulary, never in this skill's check-kind names.
- Method- and stack-specific words also live as data values in `protocol.toml` and stack cards. Never add method-specific check kinds or `flow` gates.
- Methodology absorption is a side-effect of running the verification figures the paper declares — they appear alongside the substantive figures because they are also `[[figures]]` entries with `claim_ids`.
- The writeup-handoff close (declared entry + run report) happens in Step 10. Route to `scientific-writing` / `latex-paper-en` / `scientific-visualization` / `jupyter-notebook` for downstream artifacts.

## Related

- `/solve` — single-problem loop. This skill runs atop solve when the user wants the full paper.
- `/report` — renders the run dir as a shareable HTML page.
- `/verify` — audit subagent dispatcher; the audit-kind attempt this skill records is a `/verify` call.
- `/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/slurm` — primitives this skill orchestrates.
