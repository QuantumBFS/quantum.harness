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
- Polish and audit subagent prompts MUST contain the literal repo-relative filenames from the References section that apply to that subagent. Caller-written summaries alone are insufficient.
- If a required subagent cannot be spawned, stop with `blocked: report subagent unavailable` or `blocked: report audit subagent unavailable`.
- The audit brief includes exactly: "Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."
- Audit closes only via `flow attempt finish ... --report <md-path>`. A prose "looks good" is not evidence.
</audit>

## References

Consult immediately before the matching step. For subagent dispatch, the relevant repo-relative filenames must appear literally in the subagent prompt:

- [tools/skills/report/references/editorial-schema.md](references/editorial-schema.md) — `editorial.json` contract.
- [tools/skills/report/references/report-checklists.md](references/report-checklists.md) — A-E checklist; audit emits one row per item.
- [tools/skills/report/references/subagent-briefs.md](references/subagent-briefs.md) — full polish/audit briefs.

## When

- Plan gate passed and user needs ratification: `/report <run-dir> --stage plan`.
- Close gate passed and user wants shareable HTML: `/report <run-dir> --stage append`.

## Workflow

1. Gate preflight: `flow require <run-dir> plan` or `flow require <run-dir> close`; stop on failure.
2. Consult the three references above.
3. Dispatch polish: start `report` attempt, spawn polish subagent with `tools/skills/report/references/editorial-schema.md` and `tools/skills/report/references/subagent-briefs.md` named in the prompt, write only `<run-dir>/editorial.json`, register as editorial artifact, finish attempt.
4. Render: `node tools/skills/report/site/build.mjs <run-dir> --stage <stage>`.
5. Dispatch audit: start `audit` attempt, spawn audit subagent with `tools/skills/report/references/report-checklists.md` and `tools/skills/report/references/subagent-briefs.md` named in the prompt, require `verify/verify_report_<date>.md` plus `.toml`.
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
