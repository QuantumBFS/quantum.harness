# report editorial schema reference

Read before spawning the polish subagent or changing the renderer contract.

`editorial.json` is the polish subagent's only write target. The schema is paper-agnostic: every section is a list of typed blocks, each carrying a citation and optional `scope`.

## Top-level shape

```json
{
  "problem": {
    "blocks": [
      { "kind": "background", "text": "...", "cite": "sources/paper.md:67-83", "scope": null },
      { "kind": "open_question", "text": "...", "cite": "sources/paper.md:84-92", "scope": null },
      { "kind": "why_it_matters", "text": "...", "cite": "sources/paper.md:abstract", "scope": null }
    ]
  },
  "methodology": {
    "models": [],
    "methods": [],
    "params": [],
    "assumptions": []
  },
  "verdict": {
    "status": "match | partial | fail | unknown",
    "label": "...",
    "detail": "...",
    "cite": "run-report.md:...",
    "key_results": []
  },
  "headline": { "text": "...", "cite": "verify/...:line" },
  "claims": [],
  "chips": [],
  "deviations": [],
  "figures": []
}
```

## Methodology objects

`methodology.models[]` fields:

- `id`, `name` — reference keys; never shown directly if raw.
- `paper { text, cite }` — what the paper declares.
- `ours { text, cite }` — what the protocol/run declares.
- Optional visual anchors:
  - `equation { tex, unicode_fallback?, cite? }`
  - `summary { text, cite }`
  - `key_facts[] { label, value | value_tex + value_unicode, cite? }`
  - `dimension { value_tex, value_unicode?, at?, cite? }`
  - `delta_from_paper` — one-line "Matches the paper." or "Differs: <one phrase>."

`methodology.methods[]` fields:

- `id`, `name`
- `paper { text, cite }`
- `ours { text, cite }`
- Optional `deviation`
- Optional `badge { label, tone? }`, where `tone` is `primary | olive | stone`
- Optional `headline { tex, unicode_fallback? }`
- Optional `operational[] { name, value | value_tex + value_unicode }`

`methodology.params[]` fields:

- `name`, `values`, `scope`
- `label`, `scope_label`
- Optional `values_tex`, `values_unicode`
- `why { text, cite }`

`methodology.assumptions[]` fields:

- `text`, `scope`
- `label`, `text_tex`, `text_unicode`, `scope_label`
- `why { text, cite }`

## Results objects

`verdict.key_results[]` holds the 3-5 most important scan-first values:

```json
{ "label": "...", "value_tex": "...", "value_unicode": "...", "cite": "..." }
```

`chips[]`:

```json
{ "id": "...", "label": "...", "popover": "...", "status": "ok|warn|muted", "cite": "..." }
```

`deviations[]`:

```json
{
  "id": "...",
  "display_label": "...",
  "headline": "...",
  "discrepancy_paragraph": "...",
  "paper_did": { "tex": "...", "unicode_fallback": "...", "badge": { "label": "...", "tone": "olive | primary | stone" }, "cite": "..." },
  "ours_did": { "tex": "...", "unicode_fallback": "...", "badge": { "label": "...", "tone": "primary" }, "cite": "..." },
  "cite": "protocol.toml:[[deviations]] ..."
}
```

`figures[]` has one entry per declared figure:

```json
{ "id": "...", "caption_paper": "...", "caption_ours": "..." }
```

## Rendering rules

- `scope` is `null`, `"model:<id>"`, `"method:<id>"`, or another explicit namespace if the protocol declares it.
- `tex` strings are authoritative LaTeX in KaTeX dialect; double-escape backslashes in JSON.
- `unicode_fallback` carries the same content as plain Unicode for SSR failure and accessibility tools.
- Results prose fields that contain math wrap math spans in `$...$`: `verdict.detail`, `chips[].label`, figure captions, and deviation text.
- Never use ASCII fallbacks such as `Delta`, `Omega`, `<=`, or `|<E|Z2>|^2` in visible prose.

## Protocol addition

Every `[[deviations]]` row in `protocol.toml` has a required, non-empty, audience-readable `why` field:

```toml
[[deviations]]
id        = "dev.fig2.itebd_to_ed"
statement = "Paper uses iTEBD in the thermodynamic limit for Fig 2; we use ED Krylov at finite L."
why       = "iTEBD bond-dim convergence is the paper's bottleneck; ED at L=24 resolves the same oscillation period without the iTEBD tuning loop."
```
