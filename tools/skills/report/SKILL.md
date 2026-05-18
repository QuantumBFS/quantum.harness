---
name: report
description: Use after a reproduction run completes to render a shareable single-page interactive HTML report. Triggers on "render report", "make HTML report", "publish reproduction", "share results". Generic over papers, observables, and data shapes.
---

# report

Thin orchestrator. Renders a figure-first HTML page from a run dir whose `close` gate has passed. Audience: collaborators, grad students, lab visitors — `~5 seconds` to decide if the page is worth their time.

Discipline lives in `protocol.toml`'s `[[checks]]`, evaluated by `tools/cli/flow`. This skill only sequences the steps and dispatches the subagents.

## When to activate

- Terminal step of `/reproduce-paper` (after the `close` gate passes).
- Standalone via `/report <run-dir>` for any run with `protocol.toml` + `run-report.md` + `cells/` + `verify/` + `figs/` populated.
- User says "send me a report", "publish this run", "share these results", "make an HTML report".

## Inputs

A `<run-dir>` containing:

| Required | Path | Purpose |
|---|---|---|
| ✓ | `protocol.toml` | Contract: `[artifact]`, `[[sources]]`, `[[claims]]`, `[[deviations]]`, `[[checks]]`, `[[figures]]` |
| ✓ | `run-report.md` | Bounded narrative from `/reproduce-paper`'s close step |
| ✓ | `cells/<id>/manifest.json` | Per-cell evidence |
| ✓ | `verify/verify_<artifact>_<date>.md` | Audit reports backing the chip statuses |
| ✓ | `figs/<id>.png` + `figs/<id>.json` | One pair per `[[figures]]` entry |
| optional | `progress/events.jsonl` | Flow event log — read for provenance footer |
| optional | `editorial.json` | Polish subagent output; regenerated when inputs change |

## Workflow

1. **Verify close passed.** `flow require <run-dir> close`. If it errors, stop and surface the blocker via the host's option API. The `report` gate is pre-declared in `tools/flow/templates/reproduce-paper.toml` with `requires = ["close"]`.

2. **Dispatch the polish subagent** as a `produce`-kind attempt on the `report` gate. The subagent reads the full evidence pack and writes `<run-dir>/editorial.json`. Brief: terse scientific tone, ≤ 100 words above the fold, every sentence carries a `sourced_by` pointer to a file:line in the evidence pack. Use the same model id and effort as the main agent. The subagent must be a distinct actor from whoever authored the run.

3. **Render the HTML.** `python tools/skills/report/scripts/render.py <run-dir>`. The renderer is mechanical — it composes the figure-first template, falls back to declared statements when editorial fields are missing, and stamps the provenance footer.

4. **Dispatch the audit subagent** as an `audit`-kind attempt on the `report` gate (`--actor` distinct from the polish actor). The subagent traces every editorial sentence to its `sourced_by` pointer, checks DESIGN.md compliance, checks mobile rendering. Writes `verify/verify_report_<date>.md`. Finish the attempt with `--report <path>`.

5. **`flow attempt finish`** on the audit attempt. `flow` runs the `report` gate's `[[checks]]` and derives status. If pass, the run ships. If fail, see *Failed checks*.

Output: `<run-dir>/report_<run-id>_<date>.html` plus `report_latest.html` symlink.

## Failed checks

When the audit `[[checks]]` fail (editorial sentence with no `sourced_by`, chip backed by hint-class evidence, paper figure missing, subagent actor matches producer, etc.) flow refuses to pass the `report` gate. Four real options via the host's option API:

| Option | What happens |
|---|---|
| Repair editorial | Polish subagent re-runs with the failing finding as input. |
| Repair evidence | Re-run the upstream audit that should have provided the missing verify report. |
| Override | `flow override <run-dir> <check-id> --reason "<text>"`. Recorded forever; the HTML banner shows ⊘. |
| Stop | The report is not produced. |

Never edit `render.py`, `run-report.md`, or `editorial.json` from the main agent to make a check pass. The renderer is mechanical; if it can't ship, the upstream evidence is missing.

## Bypass banner

Every recorded override surfaces in the rendered HTML:

```
⊘ Bypasses: N
  · <check-id> — "<reason>"
```

The ⊘ icon distinguishes bypasses from declared deviations (⚠). Clean runs show neither.

## Subagent discipline

- **Polish subagent**: read-only on `<run-dir>`; writes only `editorial.json`. Same model id / effort / sandbox as the main agent.
- **Audit subagent**: read-only; writes only `verify/verify_report_<date>.md`. Different actor id from the polish subagent.
- The main agent never authors prose. Editorial sentences and audit findings come from subagents.

## Mandatory genre elements

The renderer refuses to compose the page without these:

- Paper figure embed (one PNG per `[[figures]]` entry).
- Claim line (from `editorial.headline.text` or `[[claims]][0].statement`).
- Side-by-side hero (paper PNG | interactive plot).
- Status chip strip (at least one chip).
- Contract panel (from `protocol.toml`).
- Provenance footer (from `progress/state.toml` when flow is in use).

## Output

- `<run-dir>/report_<run-id>_<YYYY-MM-DD>.html` (1MB soft cap; 5MB hard refuse).
- `<run-dir>/report_latest.html` (symlink; copy on Windows).

## Composition

- Called as the terminal step of `/reproduce-paper`.
- Calls `tools/cli/flow` for gate, attempt, override, and event log.
- Does NOT call `/parameter-scan`, `/slurm`, `/scaling-fit`, or `/cross-method-check` — those are upstream evidence producers.

## Notes

- Paper-specific words (figure ids, claim ids, observable names) live in `protocol.toml`. This skill is paper-agnostic.
- The polish subagent's brief must be precise but never the place where the genre lives — the genre is `docs/DESIGN.md` and the template. Polish supplies words; the template supplies layout.
