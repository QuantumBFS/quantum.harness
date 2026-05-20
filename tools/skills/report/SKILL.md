---
name: report
description: Use after a reproduction run completes to render a shareable single-page interactive HTML report. Triggers on "render report", "make HTML report", "publish reproduction", "share results". Generic over papers, observables, and data shapes.
---

# report

Renders a figure-first HTML page from a completed reproduction run, hosted at `<run-dir>/report_<run-id>_<date>.html`. This skill is paper-agnostic; the checklists below are GENERIC across papers and projects.

## Audience definition (binding)

The rendered page is read by a **non-author scientist or collaborator with no agent context**. Concretely, they:

- Have NOT seen this session's conversation, plan, or tool calls.
- Do NOT know the harness's internal vocabulary (subagent, manifest, attempt, gate, check, override, deviation, producer, actor).
- Do NOT recognize internal identifiers (`fig3.special_band`, `trust_dimension`, `deviation.stack.numpy_scipy`).
- Have at most ~5 seconds to decide whether the page is worth their time.

Every checklist in this file is anchored to this audience. The polish subagent writes for them; the audit subagent verifies against them; the main agent halts before dispatch if any obvious item fails.

## When to activate

- Terminal step of `/reproduce-paper` (after the `close` gate passes).
- Standalone via `/report <run-dir>` for any run with `protocol.toml` + `run-report.md` + `cells/` + `verify/` + `figs/` populated.
- User says "send me a report", "publish this run", "share these results", "make an HTML report".

## Inputs

A `<run-dir>` containing:

| Required | Path | Purpose |
|---|---|---|
| ✓ | `protocol.toml` | Contract: `[artifact]`, `[entry]`, `[[sources]]`, `[[claims]]`, `[[deviations]]`, `[[checks]]`, `[[figures]]` |
| ✓ | `run-report.md` | Narrative from `/reproduce-paper`'s close step |
| ✓ | `cells/<id>/manifest.json` | Per-cell evidence |
| ✓ | `verify/verify_<artifact>_<date>.md` | Audit reports backing chip statuses |
| ✓ | `figs/<id>.png` + `figs/<id>.json` | One pair per `[[figures]]` entry |
| optional | `progress/events.jsonl` | Flow event log — read for the provenance footer |
| optional | `editorial.json` | Polish subagent output; regenerated when inputs change |

## Workflow

1. **Verify close passed.** `flow require <run-dir> close`. If it errors, surface the blocker via the host's option API and stop.

2. **Dispatch the polish subagent** as a `report`-kind attempt on the `report` gate. Spawn per [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch) (model and effort match; actor id distinct from any producer). It writes `<run-dir>/editorial.json`. Brief and constraints in [Subagent briefs](#subagent-briefs). After return, register the file with `flow artifact add <run-dir> editorial <run-dir>/editorial.json --kind editorial --producer <attempt>`, then `flow attempt finish <run-dir> <attempt>`.

3. **Render the HTML.** `python tools/skills/report/scripts/render.py <run-dir>`. The renderer reads `flow status --json` for derived state, composes the page from the template, and falls back to declared statements when editorial fields are missing. Output: `<run-dir>/report_<run-id>_<date>.html` + `report_latest.html` symlink.

4. **Dispatch the audit subagent** as an `audit`-kind attempt on the `report` gate. Spawn per [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch) (model and effort match; actor id distinct from the polish actor). It mechanically walks every checklist item and writes `verify/verify_report_<date>.md` + sibling `verify_report_<date>.toml`. Brief in [Subagent briefs](#subagent-briefs).

5. **`flow attempt finish`** on the audit attempt with `--report <md-path>`. Flow parses the sidecar verdicts, runs the `report` gate's `[[checks]]`, and derives status. If pass, the run ships. If any item is `fail`, see [Failed checks](#failed-checks).

## Checklists (the contract)

This section is the single source of truth for what the rendered page must satisfy. Three roles consume it:

- **Main agent** — pre-flight before step 2 (dispatch); halt if any obvious item already fails.
- **Polish subagent** — every item is a constraint its `editorial.json` must satisfy.
- **Audit subagent** — mechanical pass through every item; report a verdict for each.

Every item is binary pass/fail. Items A1–A9 carry **bad / good** examples because the wording is steering-sensitive; B/C/D items are mechanical and need no examples (one exception: C1).

Two items (A8 and A9) require a template / `render.py` change, not polish-subagent prose alone. The audit subagent reports them against the rendered HTML; the fix is a renderer follow-up. Their verdict is `warn` (not `fail`) until the renderer ships its fix.

### A. Audience readiness

Every **user-facing string** must satisfy ALL A-items. *User-facing string* = any visible label, tooltip, chip text, section heading, caption, popover, banner, or plot label that the audience reads in the rendered HTML.

<checklist name="audience-readiness">

#### A1. No internal identifiers leaked

No occurrence of underscore-composed identifiers — `trust_dimension`, `protocol_hash`, `script_hash`, `fig3.special_band`, `fig4.level_statistics`, `deviation.stack.numpy_scipy`, etc. — in any user-facing string. Each is translated to a plain-English phrase.

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

Requires a template / `render.py` change; audit verdict is `warn` until the renderer ships the fix.

#### A9. Abbreviations spelled out on first appearance

The first occurrence of an abbreviation in user-facing strings is spelled out with the short form in parens. Subsequent uses on the same page may use the short form alone. Applies to (non-exhaustive): `1σ`, `95% CI`, `wall`, `accept`, `vs paper`, `DOS`, `OBC`, `PBC`, `FSA`, `MC`, `ED`, `DMRG`, `TEBD`, `QMC`.

<example name="A9 bad">
± 1σ | 95% CI | wall: 12 min | accept: 0.38 | vs paper
</example>

<example name="A9 good">
± 1 standard deviation (σ) | 95% confidence interval (CI) | wall-clock time: 12 min | acceptance rate: 0.38 | compared to paper
</example>

Requires a template / `render.py` change; audit verdict is `warn` until the renderer ships the fix.

</checklist>

### B. Structural completeness

<checklist name="structural">

- **B1. Paper figure embed.** At least one paper-side figure (PNG) is embedded, one per declared `[[figures]]` entry.
- **B2. Claim line.** Present, non-empty, ≤ 200 characters.
- **B3. Side-by-side.** Each `[[figures]]` entry has both a paper panel (PNG) and a reproduction panel (interactive plot from `figs/<id>.json`).
- **B4. Verdict band.** Exactly one verdict band appears above the hero area, showing one of: match (✓), partial (◐), fail (✗), or unknown.
- **B5. Status chip strip.** At least one chip below the verdict band. Each chip has both a visible label and a hover/tap popover; both satisfy checklist A.
- **B6. Provenance footer.** Four columns render: Run · Cluster · Source · Harness. Each populated from `progress/state.toml`.
- **B7. Page size.** ≤ 1 MB soft warning; ≤ 5 MB hard refuse. The renderer enforces; the audit subagent confirms by inspecting the rendered file.
- **B8. Mobile rendering.** No horizontal scrolling at viewport width 375 px (iPhone SE). The audit subagent verifies by simulating the viewport.

</checklist>

### C. Tone and genre

<checklist name="tone">

- **C1. Above-the-fold is a result, not a procedure.** The first visible section answers "what did this reproduce?" — not "we built / ran / used …".

<example name="C1 bad">
We diagonalized the PXP model on chains of length L = 12 through L = 30 and computed the special-band overlaps.
</example>

<example name="C1 good">
The PXP chain reproduces the paper's special-band scaling. The forward-scattering approximation matches the exact bands to within ~1% at L = 30.
</example>

- **C2. Headline ≤ 100 words.** The headline body (claim + verdict + key-number recap) is ≤ 100 words.
- **C3. Every editorial sentence carries a `sourced_by` pointer.** Sentences without `sourced_by` are dropped by the polish subagent before write.
- **C4. No hedging unless the paper hedges.** Words like *might, appears to, perhaps, seems, possibly* are used only where the paper itself uses them.
- **C5. Caveats after, not before.** Discrepancies and limitations live in their dedicated panel, never in the claim line or above-the-fold prose.

</checklist>

### D. Evidence and provenance

<checklist name="evidence">

- **D1. Every chip is backed by a verify report.** Each status chip references a `verify/verify_<artifact>_<date>.md` audit. Chips backed only by `hint`-class evidence are forbidden.
- **D2. Audit actor ≠ producer actor.** The actor that signed off on the chip's underlying check is a different actor id from the producer of the artifact under audit.
- **D3. Every figure is rendered from current-run manifests.** The interactive plot's source data points to manifests with `producer = "run"` and a hash that matches the current registration.
- **D4. Provenance footer is filled from `progress/state.toml`.** Each of the four columns reads from the flow ledger, not from agent memory.

</checklist>

## Subagent briefs

### Polish subagent

**Role.** Read-only on `<run-dir>`; writes only `<run-dir>/editorial.json`. Same model id and effort as the main agent. Different actor id from any producer.

**Job.** Produce `editorial.json` such that every item in checklists A and C passes when the renderer composes the HTML. You are writing for a non-author scientist with no agent context (see [Audience definition](#audience-definition-binding)).

**Coverage, not filtering.** Produce a sentence for every chip, every figure, every override, every deviation. Each sentence is one fact. If a fact has no source in the evidence pack, leave the slot empty — do not invent. The renderer falls back to declared statements for empty slots.

**Field schema (`editorial.json`):**

```json
{
  "headline":   {"text": "...", "sourced_by": "<path>:<line>"},
  "claims":     [{"id": "...", "text": "...", "sourced_by": "..."}],
  "chips":      [{"id": "...", "label_display": "...", "popover_display": "...", "sourced_by": "..."}],
  "deviations": [{"id": "...", "text": "...", "sourced_by": "..."}],
  "overrides":  [{"id": "...", "reason_display": "...", "sourced_by": "..."}],
  "figures":    [{"id": "...", "caption_display": "...", "sourced_by": "..."}]
}
```

Each `sourced_by` is a `path:line` pointer into the evidence pack (paper Markdown, verify report, manifest, or method card). The audit subagent traces every `sourced_by` to its target.

### Audit subagent

**Role.** Read-only on `<run-dir>` and the rendered `report_*.html`; writes only `verify/verify_report_<date>.md` + sibling `verify_report_<date>.toml`. Different actor id from the polish subagent.

**Job.** Walk every checklist item (A1–A9, B1–B8, C1–C5, D1–D4 — 26 items) and report a verdict for each. Trace every editorial `sourced_by` to its target file:line; if the target doesn't exist or doesn't support the sentence, that's a `fail`.

**Coverage, not filtering.** Report every violation you find, even ones you are uncertain about or judge minor. Do not suppress findings as "too small to matter" — a downstream step ranks. It is better to surface a finding that later gets filtered than to silently drop one.

**Verdict values:**

- `pass` — item satisfied; nothing to quote.
- `warn` — item violated in the rendered HTML at a layer the polish subagent cannot fix alone (A8 and A9 land here until the renderer ships its fix).
- `fail` — item violated in `editorial.json` (polish subagent's output) or in evidence the run was supposed to provide.

**Sidecar TOML schema (`verify/verify_report_<date>.toml`):**

```toml
status = "pass" | "warn" | "fail"        # max severity across all items

[[checklist]]
id      = "A1"
verdict = "pass" | "warn" | "fail"
quote   = "<exact violating text, or empty>"
note    = "<one-sentence finding>"

# One [[checklist]] per item (26 total).
```

The Markdown report (`verify_report_<date>.md`) carries the same findings in prose form for human reading.

## Failed checks

When the audit reports any item as `fail` (verdict `fail` in the sidecar TOML), `flow` refuses to pass the `report` gate. Four real options via the host's option API:

| Option | What happens |
|---|---|
| Repair editorial | Polish subagent re-runs with the failing finding as input. |
| Repair evidence | Re-run the upstream audit that should have provided the missing verify report. |
| Override | `flow override <run-dir> <check-id> --reason "<text>"`. Recorded forever; the HTML surfaces the override per A5. |
| Stop | The report is not produced. |

Never edit `render.py`, `run-report.md`, or `editorial.json` from the main agent to make a check pass without changing the underlying evidence.

`warn` verdicts do NOT block the gate; they queue follow-up work on the renderer.

## Output

- `<run-dir>/report_<run-id>_<YYYY-MM-DD>.html` (1 MB soft cap; 5 MB hard refuse).
- `<run-dir>/report_latest.html` (symlink; copy on Windows).

## Composition

- Called as the terminal step of `/reproduce-paper`.
- Calls `tools/cli/flow` for gate, attempt, override, and event log operations.
- Does NOT call `/parameter-scan`, `/slurm`, `/scaling-fit`, or `/cross-method-check` — those are upstream evidence producers.
- Renderer / template fixes for A8 and A9 are tracked outside this skill; the audit subagent surfaces them as `warn` until the fix ships.

## Notes

- Paper-specific words (figure ids, claim ids, observable names) live in `protocol.toml`. This skill stays paper-agnostic; the checklists above are GENERIC across papers and projects.
- The polish subagent's brief is precise but never the place where the genre lives — the genre is `docs/DESIGN.md` and the template. Polish supplies words; the template supplies layout.
