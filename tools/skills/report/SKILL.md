---
name: report
description: Use when a `/reproduce-paper` run finishes and the user wants the shareable HTML deliverable, or when a `/reproduce-paper-onboard` beginner run finishes and wants the same HTML — phrases like "render report", "publish reproduction", "share results", "render the onboard run".
---

# report

Outcome: one self-contained HTML at `<run-dir>/report_<run-id>_<date>.html`. Every sentence traces to `sources/paper.md`, `protocol.toml`, a current-run manifest, or `run-report.md`. Compute belongs upstream to `/reproduce-paper` or `/reproduce-paper-onboard`.

## Editorial

`editorial.json` is the polish target. It is optional for the renderer but required for a polished report. Every editorial sentence carries a `cite` resolving to `sources/paper.md`, `protocol.toml`, `run-report.md`, or a manifest.

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

## When

- `/reproduce-paper` run finished and user wants shareable HTML: `/report <run-dir> --stage append`.
- Beginner onboard run finished and user wants the polished HTML: `/report <run-dir> --stage append`.
- Beginner wants to preview the plan before approve: `/report <run-dir> --stage plan`.

## Workflow

1. Optionally polish: inline polish pass writes `editorial.json` from `sources/paper.md`, `protocol.toml`, `run-report.md`, and manifests. If polish is skipped, the renderer falls back to plain prose from `plan.md` and `protocol.toml`.
2. Render: `node tools/skills/report/site/build.mjs <run-dir> --stage <stage>`.
3. Plan stage: present HTML with **Approve and run**, **Revise**, **Stop**.
4. Append stage: surface the final HTML path.

## Failed Checks

Repair upstream evidence and rerender. Do not edit `editorial.json`, `protocol.toml`, scripts, or run report merely to satisfy a check unless the underlying evidence changed first.

## Output

- `<run-dir>/report_<run-id>_<YYYY-MM-DD>.html`
- `<run-dir>/report_latest.html`
- `<run-dir>/editorial.json`
