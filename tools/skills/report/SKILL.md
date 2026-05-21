---
name: report
description: Use when a `/reproduce-paper` run reaches the `plan` gate and the user needs to ratify the plan before heavy compute, or after the `close` gate when the user wants the shareable HTML deliverable — phrases like "render report", "publish reproduction", "share results", "make the plan doc", "ratify before run".
---

# report

Outcome: a single self-contained HTML at `<run-dir>/report_<run-id>_<date>.html` with three audience-readable sections — **Problem**, **Methodology**, **Results** — every sentence traceable to either `sources/paper.md` or a `protocol.toml` row. The doc is rendered twice in a run's life: once at `plan` (Problem + Methodology filled, Results pending) for the user to ratify, once at `close` (all three filled). The renderer is the deliverable; the polish subagent supplies the prose; the audit subagent walks every item.

This skill is paper-agnostic; the contract below is GENERIC across papers, models, and methods. It is the doc layer; compute belongs to `/reproduce-paper` and its primitives.

## When to activate

- `/reproduce-paper`'s `plan` gate has passed and the user needs to decide "yes, run this" — `/report <run-dir> --stage plan`.
- `/reproduce-paper`'s `close` gate has passed — `/report <run-dir>` (default `--stage append`).
- User says "render the report", "publish this run", "share these results", "make the plan doc", "ratify before compute".

## Inputs

| Required at | Path | Purpose |
|---|---|---|
| both | `protocol.toml` | Contract: `[artifact]`, `[[sources]]`, `[[claims]]`, `[[deviations]]`, `[[checks]]`, `[[figures]]`, `[[cells]]` |
| both | `sources/paper.md` | Primary source for every `problem.blocks[*].cite` and every `methodology.{models,methods}[*].paper.cite` |
| `append` | `cells/<id>/manifest.json` | Per-cell evidence; Results-side chips |
| `append` | `figs/<id>.{png,json}` | One pair per `[[figures]]` row |
| `append` | `verify/verify_<artifact>_<date>.md` | Audit reports backing chip statuses |
| `append` | `run-report.md` | Narrative from the `close` step |
| optional | `progress/state.toml` | Read for the provenance footer |
| optional | `editorial.json` | Polish subagent output; regenerated whenever inputs change |

## Audience

<audience>

Two reads of the same doc:

1. **User (ratifier).** Reads Problem + Methodology at `plan` stage, before compute, to decide yes / no. They see the parameter grid, the assumptions, the wall-clock estimate, and a `Why?` callout on every choice.
2. **Non-author scientist (collaborator).** Reads the published doc after `close`, with no agent context, no internal vocabulary, ≤ 5 seconds to decide if it's worth their time.

Every sentence in every section must satisfy both. Identifiers, file paths, and harness vocabulary are forbidden in any user-facing string. The polish subagent writes for this audience; the audit subagent rejects anything that doesn't.

</audience>

## Schema (editorial.json)

The polish subagent's sole output. Schema is generic over model count, method count, parameter axes, and assumption shape: every section's content is a list of typed blocks, each carrying an optional `scope`.

```json
{
  "problem": {
    "blocks": [
      { "kind": "background",     "text": "…", "cite": "sources/paper.md:67-83",   "scope": null },
      { "kind": "open_question",  "text": "…", "cite": "sources/paper.md:84-92",   "scope": null },
      { "kind": "why_it_matters", "text": "…", "cite": "sources/paper.md:abstract","scope": null }
    ]
  },
  "methodology": {
    "models": [ {
      "id": "pxp", "name": "PXP / Fibonacci chain",
      "paper":   { "text": "…", "cite": "sources/paper.md:147-168" },
      "ours":    { "text": "…", "cite": "protocol.toml:[[claims]].model.pxp" },
      "equation":  { "tex": "H = \\sum_i P_{i-1} X_i P_{i+1}",
                     "unicode_fallback": "H = ∑ᵢ Pᵢ₋₁ Xᵢ Pᵢ₊₁",
                     "cite": "sources/paper.md:147-168" },
      "summary":   { "text": "Short one-sentence what-is-this", "cite": "sources/paper.md:147-168" },
      "key_facts": [
        { "label": "Initial state",   "value_tex": "|Z_2\\rangle", "value_unicode": "|Z₂⟩" },
        { "label": "Hilbert basis",   "value": "Fibonacci (constrained)" },
        { "label": "Boundary",        "value": "Periodic" },
        { "label": "Symmetry sector", "value_tex": "k = 0,\\ I = +1", "value_unicode": "k = 0, I = +1" }
      ],
      "dimension": { "value_tex": "D_{0+} = 77\\,436", "value_unicode": "D₀₊ = 77 436",
                     "at": "at L = 32", "cite": "sources/paper.md:170" },
      "delta_from_paper": "Matches the paper. Dimension cross-checked at L = 12."
    } ],
    "methods": [ {
      "id": "ed_dyn", "name": "Time evolution from |Z₂⟩",
      "paper":   { "text": "…", "cite": "sources/paper.md:201-215" },
      "ours":    { "text": "…", "cite": "protocol.toml:[[cells]].cell-fig2-dyn" },
      "deviation": "dev.fig2.itebd_to_ed",
      "badge":     { "label": "Exact diagonalization (Krylov)", "tone": "primary" },
      "headline":  { "tex": "|\\psi(t)\\rangle = e^{-iHt}\\,|Z_2\\rangle \\text{ at } L = 24",
                     "unicode_fallback": "|ψ(t)⟩ = e^{−iHt}|Z₂⟩  at L = 24" },
      "operational": [
        { "name": "Solver",       "value": "Krylov sparse matrix exponentiation" },
        { "name": "System size",  "value": "L = 24" },
        { "name": "Boundary",     "value": "Periodic" },
        { "name": "Initial state","value_tex": "|Z_2\\rangle", "value_unicode": "|Z₂⟩" }
      ]
    } ],
    "params": [ {
      "name": "L", "values": [12,16,20,24,28,32], "scope": "method:ed_dyn",
      "label": "Chain length", "scope_label": "Time evolution",
      "why": { "text": "…", "cite": "sources/paper.md:172-180" }
    } ],
    "assumptions": [ {
      "text": "Diagonalization is restricted to the (k=0, I=+1) sector.",
      "scope": "method:ed_static",
      "label":          "Zero-momentum, inversion-symmetric sector only",
      "text_tex":       "\\text{Restrict to the } (k = 0,\\ I = +1) \\text{ sector.}",
      "text_unicode":   "Restrict to the (k = 0, I = +1) sector.",
      "scope_label":    "Static spectrum",
      "why": { "text": "…", "cite": "sources/paper.md:172-180" }
    } ]
  },
  "verdict": {
    "status": "match | partial | fail | unknown",
    "label":  "…",
    "detail": "… with $math$ markers; ≤ 1 sentence; no caveats",
    "cite":   "run-report.md:…",
    "key_results": [
      { "label": "…", "value_tex": "…", "value_unicode": "…", "cite": "…" }
    ]
  },
  "headline":    { "text": "…", "cite": "verify/…:line" },
  "claims":      [ { "id": "…", "display_label": "…", "popover": "…", "cite": "…" } ],
  "chips":       [ { "id": "…", "label": "… with $math$ markers", "popover": "plain English", "status": "ok|warn|muted", "cite": "…" } ],
  "deviations": [
    {
      "id":             "…",
      "display_label":  "…",
      "headline":       "One-line summary; may contain $math$",
      "discrepancy_paragraph": "Optional follow-up paragraph; may contain $math$",
      "paper_did":      { "tex": "…", "unicode_fallback": "…", "badge": { "label": "…", "tone": "olive | primary | stone" }, "cite": "…" },
      "ours_did":       { "tex": "…", "unicode_fallback": "…", "badge": { "label": "…", "tone": "primary" }, "cite": "…" },
      "cite":           "protocol.toml:[[deviations]] …"
    }
  ],
  "figures":     [
    {
      "id":            "…",
      "caption_paper": "Paper-side caption with $math$ markers",
      "caption_ours":  "Run-side caption with $math$ markers"
    }
  ]
}
```

`problem.blocks[*]` and `methodology.{models,methods,params,assumptions}` are the top-level objects; the lower half (headline, claims, chips, deviations, figures) is the existing Results-side editorial pack. Field names are single-word throughout.

`scope` is a string namespace: `null`, `"model:<id>"`, `"method:<id>"`. New axes (e.g. `"regime:low_T"`) require no schema change.

**Visual-anchor fields (additive, paper-agnostic).** The renderer treats the original `paper.text` / `ours.text` prose as a fallback. When the paper centrally identifies a model with a defining equation, key facts, or a Hilbert-space dimension, the polish subagent emits the structured anchor fields so the rendered Methodology page has a visual anchor instead of a wall of prose:

- `models[].equation { tex, unicode_fallback?, cite? }` — authoritative LaTeX for the model's defining equation. `tex` is rendered with KaTeX as a centered display equation; `unicode_fallback` is used if KaTeX rendering fails.
- `models[].summary { text, cite }` — ≤ 50-word one-sentence "what is this" paragraph. Separate from the full `paper.text` so the anchor pane stays short.
- `models[].key_facts[] { label, value | value_tex + value_unicode, cite? }` — 3–5 quantities the paper centrally identifies (initial state, basis, sector, boundary, …). `value_tex` is rendered inline KaTeX.
- `models[].dimension { value_tex, value_unicode?, at?, cite? }` — emitted only when the paper centrally states a Hilbert-space dimension.
- `models[].delta_from_paper` — one-line "matches the paper" / "Differs: <one phrase>". When the implementation matches, this is one short phrase; do not restate the paper in the `ours` slot.
- `methods[].badge { label, tone? }` — method family pill (e.g. "Exact diagonalization", "Tensor network", "Monte Carlo", "Variational"). `tone` ∈ `primary | olive | stone`.
- `methods[].headline { tex, unicode_fallback? }` — one-line, math-mixed sentence the method card opens with.
- `methods[].operational[] { name, value | value_tex + value_unicode }` — table-row pairs (Solver, Sizes, Sector, Outputs, …). Renderer shows them as a responsive grid of stat-chips.
- `params[].label` — audience phrase replacing raw `name`. `params[].scope_label` — audience phrase replacing `"method:<id>"`. `params[].values_tex` / `values_unicode` — when values contain math (kets, Greek).
- `assumptions[].label` — short chip headline. `assumptions[].text_tex` / `text_unicode` — math-typeset form. `assumptions[].scope_label` — audience phrase.

All anchor fields are **optional**. The renderer falls back to the paper/ours prose pair when an anchor field is absent. The Polish-subagent brief below makes this an "emit-when-the-paper-supports-it" responsibility — every reproduction has a defining equation or a defining operational table; the schema doesn't care which.

## One field added to `protocol.toml`

`[[deviations]].why` — required, non-empty, audience-readable. The protocol author owns it (they chose to deviate). Editorial renders it; the audit fails E6 for any row missing it.

```toml
[[deviations]]
id        = "dev.fig2.itebd_to_ed"
statement = "Paper uses iTEBD in the thermodynamic limit for Fig 2; we use ED Krylov at finite L."
why       = "iTEBD bond-dim convergence is the paper's bottleneck; ED at L=24 already resolves the same oscillation period without the iTEBD tuning loop."
```

## Lifecycle

`/report` is invoked twice. Same command, different `--stage`. `/report` owns rendering and the ratification UI; compute belongs to the caller.

<gates>

| Stage    | Pre-state                                  | Renders                                     | After                                                                 |
|----------|--------------------------------------------|---------------------------------------------|----------------------------------------------------------------------|
| `plan`   | `plan` gate passed in `/reproduce-paper`   | Problem + Methodology; Results = pending    | `AskUserQuestion` ratification; on yes, control returns to the caller |
| `append` | `close` gate passed in `/reproduce-paper`  | All three sections                          | Report ships; URL surfaced                                            |

</gates>

In `plan` stage, the Results section is rendered visibly as "Pending — confirm to run.", with `budgets.wall_clock` and `methodology.expected_output_summary` lifted to the top of the section. The user reads, then ratifies via the host's option API.

`/report` does NOT execute compute. The caller (`/reproduce-paper`) executes `script` / `trust` / `run` / `assemble` / `close` and re-invokes `/report --stage append` after `close` passes.

## Workflow

1. **Verify the upstream gate.** `--stage plan` requires `flow require <run-dir> plan` to exit 0; `--stage append` requires `flow require <run-dir> close`. On error, surface the blocker via the host's option API and stop.

2. **Dispatch the polish subagent** as a `report`-kind attempt on the `report` gate. Spawn per [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch) (model and effort match; actor id distinct from any producer). Brief in [Polish subagent](#polish-subagent). Returns `editorial.json`. Register with `flow artifact add <run-dir> editorial <run-dir>/editorial.json --kind editorial --producer <attempt>`, then `flow attempt finish <run-dir> <attempt>`.

3. **Render the HTML.** `node tools/skills/report/site/build.mjs <run-dir> --stage <stage>`. The build reads `protocol.toml`, `editorial.json`, `sources/paper.md`, and (at `append`) `cells/`, `figs/`, `verify/`; sanitizes the run id into a path-safe slug; writes three per-run files under `site/`: `lib/runs/<slug>.ts` (typed data), `content/<slug>.mdx` (MDX shell that imports the data), and `lib/current-report.tsx` (wrapper that statically imports the MDX as `Content` and re-exports `meta`); runs the Fumadocs / Next.js static export against the tracked `app/page.tsx` shell (which imports from `@/lib/current-report`); inlines every CSS / JS chunk / font / image into a single `<run-dir>/report_<run-id>_<date>.html`. Updates the `report_latest.html` symlink. All three site-side per-run files are gitignored intermediate outputs; the rendered HTML under the run directory is the tracked deliverable.

4. **Dispatch the audit subagent** as an `audit`-kind attempt on the `report` gate. Spawn per [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch); actor id distinct from the polish subagent. Brief in [Audit subagent](#audit-subagent). Returns `verify/verify_report_<date>.md` + sibling `.toml`.

5. **`flow attempt finish`** on the audit attempt with `--report <md-path>`. Flow parses the sidecar verdicts, runs the `report` gate's `[[checks]]`, derives status. If pass, the run ships. If any item is `fail`, see [Failed checks](#failed-checks).

6. **`plan` stage only:** present the rendered HTML to the user via `AskUserQuestion`:
   - **Yes — run it** (Recommended when the wall-clock estimate fits the user's budget and every checklist item passed)
   - **Revise the plan first** — caller edits `protocol.toml`; re-render.
   - **Stop**

7. **`append` stage:** the audit gate-passes, flow registers the report artifact, the user receives the link.

## Checklists (the contract)

Single source of truth for what the rendered doc satisfies. Three roles use it:

- **Main agent** — pre-flight before step 2; halt if any obvious item already fails.
- **Polish subagent** — every item is a constraint that its `editorial.json` must satisfy.
- **Audit subagent** — mechanical pass through every item; one verdict per item.

A and E carry **bad / good** examples because the wording is steering-sensitive; B / C / D are mechanical and need no examples (one exception: C1).

### A. Audience

<checklist name="audience">

Every **user-facing string** — visible labels, tooltips, chip text, section headings, captions, popovers, banners, plot labels — must satisfy ALL A-items.

#### A1. No internal identifiers leaked

No occurrence of underscore-composed identifiers — `trust_dimension`, `protocol_hash`, `script_hash`, `fig3.special_band`, `deviation.stack.numpy_scipy`, etc. — in any user-facing string. Each is translated to a plain-English phrase.

<example name="A1 bad">
near (trust_zero_modes_obc): support holds at L=12..30
</example>

<example name="A1 good">
Zero-mode count matches the expected value at every chain length we ran (L = 12 through L = 30).
</example>

#### A2. No file paths in user-facing strings

No `.md`, `.toml`, `.json`, `.py`, or directory prefixes (`scripts/`, `cells/`, `verify/`, `figs/`, `progress/`, `tools/`) in tooltips or visible labels. Single exception: the provenance footer's source-link slot renders one external citation (paper DOI or official code URL).

<example name="A2 bad">
L=32 manifest fields will land when HPC2 job completes; all present cells (L=12,14,...) carry the required fields. — bypassed by agent:report-skill
</example>

<example name="A2 good">
L = 32 result still computing on the cluster. The other sizes (L = 12 through L = 30) are complete, and the figure is built from those.
</example>

#### A3. No internal vocabulary

No occurrence of: *subagent, polish subagent, audit subagent, actor, attempt, gate, kind, producer, manifest, flow, protocol_hash, freshness sources, above-the-fold, hero, chip, popover, drawer, callout*. The agent infrastructure and the template's design vocabulary stay invisible to the reader.

<example name="A3 bad">
Close-gate audit subagent not dispatched: this Claude Code session has no host subagent / TaskCreate tool available.
</example>

<example name="A3 good">
The final independent review was skipped this run. All other checks ran normally; see "What didn't match" below for details.
</example>

#### A4. No raw check kinds

No occurrence of the pattern `<check_kind> (<check_id>)` in any chip label, tooltip, or panel — e.g., `near (...)`, `exists (...)`, `audit (...)`, `support (...)`. Each chip displays a plain-English statement of what was checked AND the result.

<example name="A4 bad">
exists (source) ✓
</example>

<example name="A4 good">
Paper PDF and rendered Markdown source on file. ✓
</example>

#### A5. Overrides rendered as plain-English reasons

Every recorded override appears as "**Skipped because** &lt;one-sentence non-expert reason&gt;", not "bypassed by &lt;actor&gt;". The reason cites the cause in terms a collaborator can evaluate.

<example name="A5 bad">
Cross-cell protocol_hash consensus across L=12..30 cells holds; L=32 will rejoin consensus when manifest lands. — bypassed by agent:report-skill
</example>

<example name="A5 good">
Skipped because L = 32 is still computing on the cluster. The other ten chain lengths (L = 12 through L = 30) all ran the same code and produced consistent results.
</example>

#### A6. Snake_case rewritten as natural phrases

Identifiers like `special_band`, `zero_modes`, `level_statistics`, `dos_zero_modes`, `pr2_scaling`, `fsa_eigenvalues` are rewritten as natural English phrases in display text.

<example name="A6 bad">
fig3.fsa_eigenvalues: matches paper
</example>

<example name="A6 good">
Forward-scattering approximation eigenvalues — match the paper to within ~1%.
</example>

#### A7. Greek and math symbols rendered

No raw ASCII forms of Greek letters (`alpha`, `beta`, `gamma`, `chi`, `omega`, `Delta`) or math operators (`\Delta`, `\epsilon`, `\approx`, `<=`, `>=`, `+/-`) in user-facing strings. Use Unicode (α, β, γ, χ, ω, Δ, ≈, ≤, ≥, ±) or proper sub/superscript markup.

<example name="A7 bad">
Energy gap Delta E / E approximately 1% (alpha = 0.5)
</example>

<example name="A7 good">
Energy gap ΔE/E ≈ 1% (α = 0.5)
</example>

#### A8. Panel headings use the audience's words

Section and panel headings are words a non-author scientist understands without legend-checking. Forbidden as standalone headings: *Contract, Discrepancy, Provenance, Cell manifest, Cell payload, Deviation, Override, Bypass*. Required replacements:

| Forbidden | Replacement |
|---|---|
| Contract | What was promised |
| Discrepancy | What didn't match |
| Provenance | Where this came from |
| Cell manifest / Cell payload | Run details |
| Deviation | Documented exception |
| Override / Bypass | Skipped check |

<example name="A8 bad">
**Contract** — Reproduction obligations and accepted deviations.
</example>

<example name="A8 good">
**What was promised** — the figures and numerical claims this run committed to reproduce.
</example>

#### A9. Abbreviations spelled out on first appearance

The first occurrence of an abbreviation in user-facing strings is spelled out with the short form in parens. Subsequent uses on the same page may use the short form alone. Applies to (non-exhaustive): `1σ`, `95% CI`, `wall`, `accept`, `vs paper`, `DOS`, `OBC`, `PBC`, `FSA`, `MC`, `ED`, `DMRG`, `TEBD`, `QMC`.

<example name="A9 bad">
± 1σ | 95% CI | wall: 12 min | accept: 0.38 | vs paper
</example>

<example name="A9 good">
± 1 standard deviation (σ) | 95% confidence interval (CI) | wall-clock time: 12 min | acceptance rate: 0.38 | compared to paper
</example>

</checklist>

### B. Structure

<checklist name="structure">

- **B1. Paper figure embed.** At least one paper-side figure (PNG) is embedded, one per declared `[[figures]]` entry.
- **B2. Claim line.** Present, non-empty, ≤ 200 characters.
- **B3. Side-by-side.** Each `[[figures]]` entry has both a paper panel (PNG) and a reproduction panel (interactive plot from `figs/<id>.json`).
- **B4. Verdict band.** Exactly one verdict band appears at the top of the Results section, showing one of: match (✓), partial (◐), fail (✗), or unknown.
- **B5. Status chip strip.** At least one chip below the verdict band. Each chip has both a visible label and a hover/tap popover; both satisfy checklist A.
- **B6. Provenance footer.** Four columns render: Run · Cluster · Source · Harness. Each populated from `progress/state.toml`.
- **B7. Page size.** ≤ 3 MB soft warning; ≤ 10 MB hard refuse. The build enforces; the audit subagent confirms by inspecting the rendered file.
- **B8. Mobile rendering.** No horizontal scrolling at viewport width 375 px (iPhone SE). The audit subagent verifies by simulating the viewport.
- **B9. Three sections present.** Problem, Methodology, and Results all render with a visible heading and are reachable from the sidebar. At `--stage plan`, Results renders as "Pending — confirm to run."; at `--stage append`, all three are filled.

</checklist>

### C. Tone

<checklist name="tone">

- **C1. Above-the-fold is a result, not a procedure.** The Results section's first visible block answers "what did this reproduce?" — not "we built / ran / used …".

<example name="C1 bad">
We diagonalized the PXP model on chains of length L = 12 through L = 30 and computed the special-band overlaps.
</example>

<example name="C1 good">
The PXP chain reproduces the paper's special-band scaling. The forward-scattering approximation matches the exact bands to within ~1% at L = 30.
</example>

- **C2. Headline ≤ 100 words.** The headline body (claim + verdict + key-number recap) is ≤ 100 words.
- **C3. Every editorial sentence carries a `cite` pointer.** Sentences without `cite` are dropped by the polish subagent before write; the renderer falls back to the declared statement.
- **C4. No hedging unless the paper hedges.** Words like *might, appears to, perhaps, seems, possibly* are used only where the paper itself uses them.
- **C5. Caveats after, not before.** Discrepancies and limitations live in their dedicated panel, never in the claim line or above-the-fold prose.

</checklist>

### D. Evidence

<checklist name="evidence">

- **D1. Every chip is backed by a verify report.** Each status chip references a `verify/verify_<artifact>_<date>.md` audit. Chips backed only by `hint`-class evidence are forbidden.
- **D2. Audit actor ≠ producer actor.** The actor that signed off on the chip's underlying check is a different actor id from the producer of the artifact under audit.
- **D3. Every figure is rendered from current-run manifests.** The interactive plot's source data points to manifests with `producer = "run"` and a hash that matches the current registration.
- **D4. Provenance footer is filled from `progress/state.toml`.** Each of the four columns reads from the flow ledger, not from agent memory.

</checklist>

### E. Sourcing

<checklist name="sourcing">

Every extracted sentence traces to a primary source. The paper IS the source of truth for `problem` and `methodology.{models,methods}[*].paper`; `protocol.toml` is the source of truth for `methodology.{models,methods}[*].ours` and the parameter / assumption / deviation rationale.

- **E1.** Every `problem.blocks[*].cite` resolves to text in `sources/paper.md` that supports the block.
- **E2.** Every `methodology.{models,methods}[*].paper.cite` resolves to `sources/paper.md` text.
- **E3.** Every `methodology.{models,methods}[*].ours.cite` resolves to a row in `protocol.toml`.
- **E4.** Every `methodology.params[*].why` is non-empty and materially supports the values chosen.
- **E5.** Every `methodology.assumptions[*].why` is non-empty and materially supports the assumption.
- **E6.** Every `[[deviations]].why` in `protocol.toml` is non-empty.
- **E7.** Every model / method `id` referenced from `[[claims]]` or `[[cells]]` appears in `methodology.{models,methods}` exactly once.

<example name="E1 bad">
{ "kind": "background", "text": "Quantum chaos predicts thermalization.", "cite": "" }
</example>

<example name="E1 good">
{ "kind": "background", "text": "Quantum chaos and ETH predict thermalization in generic isolated systems.", "cite": "sources/paper.md:67-83" }
</example>

<example name="E6 bad">
[[deviations]]
id        = "dev.fig2.itebd_to_ed"
statement = "Paper uses iTEBD; we use ED."
</example>

<example name="E6 good">
[[deviations]]
id        = "dev.fig2.itebd_to_ed"
statement = "Paper uses iTEBD in the thermodynamic limit for Fig 2; we use ED Krylov at finite L."
why       = "iTEBD bond-dim convergence is the paper's bottleneck; ED at L=24 already resolves the same oscillation period without the iTEBD tuning loop."
</example>

</checklist>

## Subagent briefs

Both briefs follow the GPT-5.5 Role / Goal / Constraints / Output / Stop frame, with the verbatim Opus-4.7 coverage line: *"Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."* Both are dispatched per [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch).

### Polish subagent

<persistence name="polish">

- **Role.** Editorial layer for the rendered doc. Read-only on `<run-dir>` and `sources/paper.md`; writes only `<run-dir>/editorial.json`. Same model id and effort as the main agent. Different actor id from any producer.
- **Goal.** Produce `editorial.json` such that every item in **A** · **C** · **E** passes when the build composes the HTML. Cover every model in `[[claims]]`, every distinct method in `[[cells]]`, every axis a cell declares, every implicit choice the protocol makes. One sentence is one fact.
- **Anchor-emission rule.** When the paper centrally identifies a model with a defining equation, an initial state, a basis, a sector, or a Hilbert-space dimension, emit those as `equation`, `key_facts`, `dimension` — not buried inside `paper.text` prose. When the implementation matches the paper, emit a single `delta_from_paper` phrase ("Matches the paper." / "Differs: <one phrase>"); do NOT restate the paper in the `ours` slot. For methods, emit `badge` (method family), `headline` (one-line math-mixed sentence), and `operational` (table-row pairs the protocol fixes — solver, sizes, sector, outputs). For parameters and assumptions, emit `label` and `scope_label` so the renderer can show audience phrases instead of raw `name` / `method:<id>`.
- **Results-anchor rule.** The Results section must NOT put headline quantitative findings only inside `verdict.detail`. Emit `verdict.key_results[]` for the 3–5 most important numbers a collaborator should scan first (gap, exponent, period, dimension, energy error, scaling ratio). Each item has `{ label, value_tex, value_unicode, cite }`. `verdict.detail` becomes a single short sentence about WHAT the run did, math content wrapped in `$...$`; deviation / pending language is hoisted OUT of `verdict.detail` and into the deviations / chips arrays (C5 caveats-after).
- **Deviation-delta rule.** Every `[[deviation]]` in `protocol.toml` becomes a paper-vs-ours delta in **What didn't match**. Emit `deviations[].display_label` (audience eyebrow), `deviations[].headline` (one-line summary), and the two-column delta `deviations[].paper_did { tex, unicode_fallback, badge?, cite }` / `deviations[].ours_did { tex, unicode_fallback, badge?, cite }`. The `badge.label` is a method-family or stack pill (`iTEBD`, `ED Krylov`, `DMRG`, `QMC`, `XDiag.jl`, `NumPy / SciPy`); never a raw id. For stack/route deviations the paper side is the canonical / reference route, not the literal paper. `discrepancy_paragraph` remains a prose fallback only.
- **Math-in-prose rule.** Any Results prose field that contains math must wrap math spans in `$...$`: `verdict.detail`, `chips[].label`, `figures[].caption_paper`, `figures[].caption_ours`, `deviations[].headline`, `deviations[].discrepancy_paragraph`. The renderer's `MathInText` helper splits on `$...$` and renders each span via KaTeX inline; plain text passes through untouched. Do not use ASCII fallbacks (`Delta`, `Omega`, `<=`, `|<E|Z2>|^2`) in visible prose.
- **Figure-caption rule.** Emit one paper-side and one run-side caption per declared figure. Captions name the plotted observable, the state / sector / window, and any normalization that matters. Wrap every math span in `$...$`.
- **Math-rendering rule.** `tex` strings are authoritative LaTeX (KaTeX dialect; double-escape backslashes in JSON). `unicode_fallback` is the same content as plain Unicode for the SSR-failure path and a11y tools. Renderer never falls back to ASCII like `\sum` or `<=`.
- **Constraints.** Every sentence carries a `cite` resolving to a real `file:line` — `sources/paper.md` for paper-side content, `protocol.toml` for ours-side content. Empty `cite` is allowed only when the slot has no source in the evidence pack — leave the slot empty; the renderer falls back to the declared statement. Identifiers (`model.id`, `method.id`, raw `scope`) are reference keys only and must never appear in any user-facing field (A1 / A6).
- **Output.** `editorial.json` matching the schema in [Schema](#schema-editorialjson). One entry per surface: problem block, model (with optional `equation` / `summary` / `key_facts` / `dimension` / `delta_from_paper`), method (with optional `badge` / `headline` / `operational`), parameter (with `label` / `scope_label`), assumption (with `label` / `text_tex` / `scope_label`), chip, figure, override, deviation.
- **Stop.** When every required slot is filled or empty; never invent. *"Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."*

</persistence>

### Audit subagent

<persistence name="audit-report">

- **Role.** Independent reviewer. Read-only on `<run-dir>`, `sources/paper.md`, and the rendered `report_*.html`; writes only `verify/verify_report_<date>.md` + sibling `.toml`. Different actor id from the polish subagent.
- **Goal.** One verdict for every checklist item (A1–A9 · B1–B9 · C1–C5 · D1–D4 · E1–E7 — 34 items); an exact verbatim quote on every `fail` / `warn`.
- **Constraints.** Resolve every `cite` to a real `file:line`. Do not invent line ranges. Do not collapse fails as "minor". One `[[checklist]]` row per item in the sidecar TOML, no merging. Grep the relevant `TACITS.toml` files for every method and model named in `protocol.toml`'s `[[claims]]` / `[[cells]]` before issuing a verdict; a verdict that ignores a matching tacit's signal is itself a failed audit. *"Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."*
- **Output.** `verify/verify_report_<date>.md` (human prose) + sibling `verify_report_<date>.toml` (machine verdicts).

```toml
status = "pass" | "warn" | "fail"        # max severity across all items

[[checklist]]
id      = "A1"
verdict = "pass" | "warn" | "fail"
quote   = "<exact violating text, or empty>"
note    = "<one-sentence finding>"

# One [[checklist]] row per item — 34 total (A1–A9, B1–B9, C1–C5, D1–D4, E1–E7).
```

- **Stop.** Every item has a verdict, OR inputs are missing (halt with halt-reason; the gate stays open).

</persistence>

## Failed checks

<invariants name="repair">
- Repairs change evidence. The script, `protocol.toml`, the run report, and `editorial.json` are downstream of evidence; editing them so a check passes is a contract violation.
- The only legal responses to a `fail` are: repair editorial, repair evidence, override, stop.
</invariants>

When the audit reports any item as `fail`, `flow` refuses to pass the `report` gate. Four real options via the host's option API:

| Option | What happens |
|---|---|
| Repair editorial  | Polish subagent re-runs with the failing finding as input. |
| Repair evidence   | Re-run the upstream gate that should have provided the missing artifact. |
| Override          | `flow override <run-dir> <check-id> --reason "<text>"`. Recorded forever; the HTML surfaces the override per A5. |
| Stop              | The report is not produced. |

Never edit `editorial.json` from the main agent to make a check pass without changing the underlying evidence.

`warn` verdicts do NOT block the gate; they queue follow-up work on the renderer.

## Output

- `<run-dir>/report_<run-id>_<YYYY-MM-DD>.html` (3 MB soft cap; 10 MB hard refuse).
- `<run-dir>/report_latest.html` (symlink; copy on Windows).
- `<run-dir>/editorial.json` (polish subagent's structured output).
- `<run-dir>/verify/verify_report_<YYYY-MM-DD>.{md,toml}` (audit subagent's verdicts).

## Composition

- Called by `/reproduce-paper` at the `plan` gate (`--stage plan`) and after the `close` gate (`--stage append`).
- Calls `tools/cli/flow` for gate, attempt, override, and event-log operations.
- Calls `node tools/skills/report/site/build.mjs` for the Fumadocs static build + single-file inlining.
- Does NOT call `/parameter-scan`, `/slurm`, `/scaling-fit`, `/cross-method-check` — those are upstream evidence producers.

## Notes

- Paper-specific words (figure ids, claim ids, observable names) live in `protocol.toml`. This skill stays paper-agnostic; the checklists above are GENERIC across papers and projects.
- `scope` in `editorial.json` is a string namespace; new axes (e.g. `"regime:low_T"`) require no schema change.
- Renderer / template polish that the polish subagent cannot fix in `editorial.json` (e.g. layout, sidebar grouping, page-load sequence) lands in the MDX page under `tools/skills/report/site/`, not in the polish brief.
