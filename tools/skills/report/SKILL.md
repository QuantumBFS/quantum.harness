---
name: report
description: Use when a `/reproduce-paper` run reaches the `plan` gate and the user needs to ratify the plan before heavy compute, or after the `close` gate when the user wants the shareable HTML deliverable — phrases like "render report", "publish reproduction", "share results", "make the plan doc", "ratify before run".
---

# report

Outcome: a single self-contained HTML at `<run-dir>/report_<run-id>_<date>.html` with **Problem**, **Methodology**, and **Results** sections. Every sentence traces to `sources/paper.md`, `protocol.toml`, a current-run manifest, or a verify report. Compute belongs upstream to `/reproduce-paper`; this skill renders and audits the shareable document.

## Non-negotiables

<checklist name="binding">
- `--stage plan` requires `flow require <run-dir> plan` to pass before rendering.
- `--stage append` requires `flow require <run-dir> close` to pass before rendering.
- The polish pass is a spawned `report`-kind subagent, not inline prose editing by the caller.
- The final report audit is a spawned `audit`-kind subagent. Self-audit is invalid.
- Audit dispatch follows [AGENTS.md -> Audit dispatch](../../../AGENTS.md#audit-dispatch): spawned actor, distinct from producer, returned `verify/verify_report_<date>.md`, sibling `.toml`, same model and effort, host solo defaults overridden.
- If a required subagent cannot be spawned, stop with `blocked: report subagent unavailable` or `blocked: report audit subagent unavailable`; leave the gate open.
- The audit brief contains this exact line: "Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."
- `flow attempt finish` with `--report <md-path>` is the only way an audit attempt closes. A prose statement that the report "looks good" is not evidence.
</checklist>

## References

Consult only when the corresponding step is reached:

- [references/editorial-schema.md](references/editorial-schema.md) — `editorial.json` shape and visual-anchor fields. Consult before spawning the polish subagent or changing the renderer contract.
- [references/report-checklists.md](references/report-checklists.md) — A-E audience, structure, tone, evidence, and sourcing checks. Consult before both polish and audit dispatch.
- [references/subagent-briefs.md](references/subagent-briefs.md) — full Role / Goal / Constraints / Output / Stop briefs for polish and audit subagents. Consult immediately before spawning either subagent.

## Activation

- `/reproduce-paper`'s `plan` gate has passed and the user needs to decide "yes, run this" via `/report <run-dir> --stage plan`.
- `/reproduce-paper`'s `close` gate has passed and the user wants the shareable HTML via `/report <run-dir>` or `/report <run-dir> --stage append`.
- User says "render the report", "publish this run", "share these results", "make the plan doc", or "ratify before compute".

## Inputs

| Required at | Path | Purpose |
|---|---|---|
| both | `protocol.toml` | Declared artifact, sources, claims, checks, figures, cells, deviations |
| both | `sources/paper.md` | Primary source for paper-side content |
| `append` | `cells/<id>/manifest.json` | Current-run evidence |
| `append` | `figs/<id>.{png,json}` | Rendered paper/reproduction panels |
| `append` | `verify/verify_<artifact>_<date>.md` | Audit reports backing status chips |
| `append` | `run-report.md` | Close-gate narrative |
| optional | `progress/state.toml` | Provenance footer |
| optional | `editorial.json` | Polish subagent output; regenerated when inputs change |

## Workflow

1. **Gate preflight.** Run `flow require <run-dir> plan` for `--stage plan`, or `flow require <run-dir> close` for `--stage append`. Stop on failure and surface the blocker.
2. **Load report references.** Consult [references/report-checklists.md](references/report-checklists.md), [references/editorial-schema.md](references/editorial-schema.md), and [references/subagent-briefs.md](references/subagent-briefs.md).
3. **Dispatch polish.** Start a `report`-kind attempt on the `report` gate. Spawn the polish subagent with the full brief. It writes only `<run-dir>/editorial.json`. Register it with `flow artifact add ... --kind editorial --producer <attempt>`, then `flow attempt finish`.
4. **Render.** Run `node tools/skills/report/site/build.mjs <run-dir> --stage <stage>`. The build consumes `protocol.toml`, `editorial.json`, `sources/paper.md`, and append-stage evidence; it writes the single HTML file and updates `report_latest.html`.
5. **Dispatch audit.** Start an `audit`-kind attempt on the `report` gate. Spawn the audit subagent with the full brief and checklist. It writes `verify/verify_report_<date>.md` plus `verify_report_<date>.toml`.
6. **Close audit.** Run `flow attempt finish <run-dir> <audit-attempt> --report verify/verify_report_<date>.md`. If any check fails, follow [Failed Checks](#failed-checks).
7. **Plan-stage ratification.** At `--stage plan`, present the rendered HTML with three real options: **Yes — run it** (recommended when budget fits and checks pass), **Revise the plan first**, **Stop**.
8. **Append-stage publish.** At `--stage append`, once the report gate passes, surface the HTML path.

## Checklist Kernel

The detailed checklist lives in [references/report-checklists.md](references/report-checklists.md). Keep these headings in every polish and audit brief:

| Group | Audit meaning |
|---|---|
| A. Audience | No internal ids, paths, raw check kinds, or agent infrastructure in user-facing text; math and abbreviations rendered for a scientist reader. |
| B. Structure | Paper panel, reproduction panel, verdict band, chips, provenance footer, mobile rendering, and all three sections are present. |
| C. Tone | Above-the-fold text states the result, every sentence cites evidence, caveats appear after the claim. |
| D. Evidence | Chips are backed by verify reports; audit actor differs from producer; figures come from current-run manifests. |
| E. Sourcing | Paper-side text resolves to `sources/paper.md`; ours-side text resolves to `protocol.toml`; deviations have `why`. |

The audit subagent emits one verdict per item in A1-A9, B1-B9, C1-C5, D1-D4, and E1-E7. Missing rows block the report gate.

## Failed Checks

<invariants name="repair">
- Repairs change evidence. Editing `editorial.json`, `protocol.toml`, scripts, or the run report merely to satisfy a check is a contract violation unless the underlying evidence changed first.
- Legal responses to `fail`: repair editorial via a new polish subagent attempt, repair upstream evidence and rerender, record an override with a human-readable reason, or stop.
- `warn` does not pass silently; it queues follow-up work and stays visible in `flow status`.
</invariants>

When audit returns `fail`, present four real options:

| Option | What happens |
|---|---|
| Repair editorial | Re-run polish with the failing finding as input. |
| Repair evidence | Re-run the upstream gate that should have produced the missing artifact. |
| Override | `flow override <run-dir> <check-id> --reason "<text>"`; the HTML surfaces the reason. |
| Stop | Leave the report gate open. |

Never edit `editorial.json` from the main agent to make a check pass without changing the underlying evidence.

## Output

- `<run-dir>/report_<run-id>_<YYYY-MM-DD>.html` (3 MB soft cap; 10 MB hard refuse).
- `<run-dir>/report_latest.html` (symlink; copy on Windows).
- `<run-dir>/editorial.json`.
- `<run-dir>/verify/verify_report_<YYYY-MM-DD>.{md,toml}`.

## Composition

- Called by `/reproduce-paper` at `plan` and after `close`.
- Calls `tools/cli/flow` for gate, attempt, artifact, override, and event-log operations.
- Calls `node tools/skills/report/site/build.mjs` for static build and single-file inlining.
- Does not call `/parameter-scan`, `/slurm`, `/scaling-fit`, or `/cross-method-check`; those are upstream evidence producers.
