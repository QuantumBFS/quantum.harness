---
name: report
description: Use to render the HTML deliverable of a reproduction run — the proposal before compute or the results after. Triggers include "render report", "build the report", "publish reproduction", "share results", or `/reproduce-paper` composing its proposal/results page.
---

# report

Render one self-contained HTML report from a reproduction run's `run.json`. Compute belongs upstream to `/reproduce-paper`; this skill only renders.

## Outcome

`python3 tools/skills/report/render_report.py <run-dir>` reads `<run-dir>/run.json` and writes `<run-dir>/report.html` — a single offline file, like a PDF: inline CSS, each figure base64-embedded, equations as inline MathML. No dependencies, no network, no build step; it opens anywhere. Surface the path, and on a laptop offer to open it.

## One source of data

`run.json` is the single source of truth; its schema (one shared computation + a `figures` list) is defined and filled by `/reproduce-paper`. The report is a one-way view of it and is never read back — render again after `run.json` changes. There is no separate editorial, polish, or provenance file.

## Layout

**Model / Method / Figures** — the shared computation, then one block per figure. Each figure block shows the paper's own panel (`paper_image`) and, once present, our reproduction beside it. The same file serves both moments: before compute the figure result areas read *pending* (a proposal); after compute they fill in (the results) — `/reproduce-paper` decides what content each block carries.

Visual reference: `docs/ed/ed_review.html` and `docs/ed/ed_interview.html` — same family, a little more polished.

## Math

`model.H` is a bare equation and renders as a centered display block; any other string may carry inline math in `$…$`. The bundled stdlib LaTeX→MathML converter covers the physics subset (sub/superscripts, sums and products with limits, fractions, roots, Greek, `\mathbf`/`\vec`, common operators, and `\left…\right` for grouped, sized delimiters — write moduli and bra-kets as `\left|\langle Z_2|\psi\rangle\right|^2` so the exponent sits on the whole `|…|`); unknown commands render literally.
