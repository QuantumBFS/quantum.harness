---
name: report
description: Use when a `/reproduce-paper` run reaches the `plan` gate and the user needs to ratify the plan before heavy compute, or after the `close` gate when the user wants the shareable HTML deliverable — phrases like "render report", "publish reproduction", "share results", "make the plan doc", "ratify before run".
---

# report

Outcome: one self-contained HTML at `<run-dir>/report_<run-id>_<date>.html`. Every sentence traces to `sources/paper.md`, `protocol.toml`, a current-run manifest, or a verify report. Compute belongs upstream to `/reproduce-paper`.

## Non-Negotiables

<audit required="true">
- `--stage plan` requires `flow require <run-dir> plan` before rendering.
- `--stage append` requires `flow require <run-dir> close` before rendering.
- The polish pass is a spawned `report`-kind subagent, not inline prose editing by the caller.
- The final report audit is a spawned `audit`-kind subagent. Self-audit is invalid.
- Audit dispatch follows AGENTS.md -> Audit dispatch: spawned actor, distinct from producer, returned `verify/verify_report_<date>.md`, sibling `.toml`, same model and effort, host solo defaults overridden.
- Polish and audit subagent prompts MUST contain the literal repo-relative filenames from the Subagent Reference Files section that apply to that subagent. Caller-written summaries alone are insufficient.
- If a required subagent cannot be spawned, stop with `blocked: report subagent unavailable` or `blocked: report audit subagent unavailable`.
- The audit brief includes exactly: "Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."
- Audit closes only via `flow attempt finish ... --report <md-path>`. A prose "looks good" is not evidence.
</audit>

## Main Contract

Do not load report references for main workflow. Main workflow obligations are in this file. Reference files under `tools/skills/report/references/` are subagent prompt inputs only.

`editorial.json` is the polish subagent's only write target. It is optional for the renderer but required for a polished report. Every editorial sentence carries a `cite` resolving to `sources/paper.md`, `protocol.toml`, `run-report.md`, a manifest, or a verify report.

Top-level `editorial.json` keys:

- `problem.blocks[]`: `{ kind, text, cite, scope }`, with `kind` such as `background`, `open_question`, or `why_it_matters`.
- `methodology.models[]`: `{ id, name, paper, ours }`, plus optional `equation`, `summary`, `key_facts[]`, `dimension`, and `delta_from_paper`.
- `methodology.methods[]`: `{ id, name, paper, ours }`, plus optional `deviation`, `badge`, `headline`, and `operational[]`.
- `methodology.params[]`: `{ name, values, scope, why }`, plus optional audience labels and math display fields.
- `methodology.assumptions[]`: `{ text, scope, why }`, plus optional audience labels and math display fields.
- `verdict`: `{ status, label, detail, cite, key_results[] }`, where `status` is `match`, `partial`, `fail`, or `unknown`.
- `headline`: `{ text, cite }`.
- `chips[]`: `{ id, label, popover, status, cite }`, where status is `ok`, `warn`, or `muted`.
- `deviations[]`: one entry per protocol deviation, with audience label, headline, paper-vs-ours delta, and cite.
- `figures[]`: one entry per declared figure, with paper-side and run-side captions.

Rendering rules:

- `scope` is `null`, `model:<id>`, `method:<id>`, or another namespace declared by the protocol.
- LaTeX uses KaTeX syntax in `tex` / `value_tex`; JSON double-escapes backslashes.
- `unicode_fallback` carries equivalent plain Unicode for accessibility and render fallback.
- Math in prose fields uses `$...$`; do not use ASCII fallbacks such as `Delta`, `Omega`, `<=`, or `|<E|Z2>|^2`.
- Every `[[deviations]]` row in `protocol.toml` has a required, non-empty, audience-readable `why` field before rendering.

## Subagent Reference Files

These files are not main-agent reading requirements. They must appear literally in the relevant subagent prompt.

Polish prompt filenames:

- `tools/skills/report/SKILL.md`
- `tools/skills/report/references/report-checklists.md`
- `tools/skills/report/references/subagent-briefs.md`

Audit prompt filenames:

- `tools/skills/report/SKILL.md`
- `tools/skills/report/references/report-checklists.md`
- `tools/skills/report/references/subagent-briefs.md`
- `AGENTS.md#audit-dispatch`

## When

- Plan gate passed and user needs ratification: `/report <run-dir> --stage plan`.
- Close gate passed and user wants shareable HTML: `/report <run-dir> --stage append`.

## Workflow

1. Gate preflight: `flow require <run-dir> plan` or `flow require <run-dir> close`; stop on failure.
2. Check the inline Main Contract above; do not load subagent reference files into main context.
3. Dispatch polish: start `report` attempt, spawn polish subagent with every Polish prompt filename above named in the prompt, write only `<run-dir>/editorial.json`, register as editorial artifact, finish attempt.
4. Render: `node tools/skills/report/site/build.mjs <run-dir> --stage <stage>`.
5. Dispatch audit: start `audit` attempt, spawn audit subagent with every Audit prompt filename above named in the prompt, require `verify/verify_report_<date>.md` plus `.toml`.
6. Close audit with `flow attempt finish ... --report verify/verify_report_<date>.md`, then require the report gate.
7. Plan stage: present HTML with **Yes - run it**, **Revise**, **Stop**.
8. Append stage: surface the final HTML path once the report gate passes.

## Failed Checks

Legal responses to audit `fail`: rerun polish with finding as input, repair upstream evidence and rerender, record user-approved override, or stop. Do not edit `editorial.json`, `protocol.toml`, scripts, or run report merely to satisfy a check unless the underlying evidence changed first.

## Output

- `<run-dir>/report_<run-id>_<YYYY-MM-DD>.html`
- `<run-dir>/report_latest.html`
- `<run-dir>/editorial.json`
- `<run-dir>/verify/verify_report_<YYYY-MM-DD>.{md,toml}`
