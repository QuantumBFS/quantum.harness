---
name: report
description: Use to render a run's HTML report — a reproduction proposal before compute, results after, or any structured run summary. Triggers include "render report", "build the report", "publish results", "share results", or a skill like `/reproduce-paper` composing its report page.
---

# report

Render one self-contained HTML page from a generic report document. `report` draws whatever pieces it is handed, in order, and knows nothing about any particular kind of run; producers (e.g. `/reproduce-paper`) own the document's shape.

## Outcome

`python3 skills/report/render_report.py <run-dir>` reads `<run-dir>/report.json` and writes `<run-dir>/report.html` — a single offline file, like a PDF: inline CSS, each figure base64-embedded, equations as inline MathML. No dependencies, no network, no build step; it opens anywhere. Surface the path, and on a laptop offer to open it.

A document with ≥2 titled sections also gets in-page **navigation**: each section is given an anchor id slugged from its title, a floating left rail lists the sections on wide screens (collapsing to a chip-bar under the hero on narrow ones), and a tiny inline scroll-spy highlights the active section. It stays offline (no network) and is hidden in print.

## The document

`report.json` is generic — a title plus an ordered list of sections, each an ordered list of pieces:

```json
{ "title": "…", "eyebrow": "…", "url": "…", "lede": "…",
  "sections": [ { "title": "…", "note": "…", "blocks": [ … ] } ] }
```

It is a one-way render input, produced from whatever the real source is — for a reproduction, `/reproduce-paper` builds it from `run.json` — and never read back. Render again after it changes. There is no separate editorial, polish, or provenance file.

## Pieces (`block.kind`)

Each block carries a `kind` plus its own fields; unknown kinds are skipped.

| kind | fields | draws |
|---|---|---|
| `heading` | `text`, `level?` | a sub-title inside a section |
| `text` | `text` | a paragraph (inline `$…$` math) |
| `equation` | `tex` | a centered display formula |
| `kv` | `pairs` (`[[k,v]…]` or object) | a label → value list; empty values drop out |
| `table` | `columns`, `rows`, `numeric?`, `muted?`, `widths?` | a table; `numeric`/`muted` are per-column flag lists (tabular no-wrap cells / recessed citation cells), `widths` a per-column CSS-width list applied via `<colgroup>` |
| `figures` | `items` (`[{src, caption}…]`) | images side by side, captioned, base64-embedded |
| `verdict` | `status` (`good`/`warn`/`bad`), `label`, `why` | a colored badge + one-line reason |
| `list` | `items`, `title?` | a bullet list, optionally inside a titled card |
| `code` | `text`, `title?` | a monospaced command box |
| `badge` | `text`, `style` (`good`/`warn`/`neutral`) | a small pill |
| `note` | `text`, `label?`, `style?` (`info`/`pending`) | a highlighted callout (`pending` is the dashed placeholder) |
| `card` | `blocks`, `title?` | a bordered box grouping nested pieces |

Figure `src` paths are relative to `<run-dir>`; a missing file degrades to a small note rather than failing.

## Math

An `equation` block's `tex` is a bare LaTeX equation and renders as a centered display block; any string may carry inline math in `$…$` (or display in `$$…$$`), plus `**bold**` and `==highlight==` (yellow marker) spans for keypoints. The bundled stdlib LaTeX→MathML converter covers the physics subset (sub/superscripts, sums and products with limits, fractions, roots, Greek, `\mathbf`/`\vec`, common operators, and `\left…\right` for grouped, sized delimiters — write moduli and bra-kets as `\left|\langle Z_2|\psi\rangle\right|^2` so the exponent sits on the whole `|…|`); unknown commands render literally.

Visual reference: `docs/ed/review.html` and `docs/ed/interview.html` — same family, a little more polished.
