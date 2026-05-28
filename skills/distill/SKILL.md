---
name: distill
description: Use when distilling a method contributor's published work into the concrete tricks they use — for expert-interview prep or method-skill enrichment. Triggers include "distill <researcher>", "what tricks does <expert> use for <method>", "prep to interview <contributor>", "extract <expert>'s method craft".
---

# distill

Distill how a contributor *uses a method*, mined from their papers, into a curated list of concrete **tricks** — grouped by concern and rendered as one webpage, for preparing an expert interview. (The paper-based sibling of sci-brain's `soul-extraction`, which mines conversations, not papers.)

## Scope

This skill owns intake → corpus → trick extraction → one HTML dossier. It does not run calculations or reproduce figures. Ingest composes with `/download-ref`; rendering composes with `/report`; it does not duplicate either.

## What a "trick" is

A repeatable technical move the contributor uses to make the method work better / cheaper / more trustworthy — not a result or a topic. Keep a trick only if it passes **all four** tests:

- **decision-changing** — changes whether the result is right or feasible;
- **non-obvious / method-specific** — a competent practitioner would *not* do it by default, and it is **specific to this method's own challenges**, not shared across the broader domain. (A convergence knob common to the whole method family is trivial; a trade-off intrinsic to this method's own core step is worth keeping. Also cut "benchmark against the exact solution" and similar table-stakes.)
- **transferable** — a reader could apply it to their own calculation;
- **attributable** — pinned to a specific location (figure / equation / section).

No frequency gate: a trick used in a single paper still counts if it passes the four tests.

## The lens (how to hunt tricks)

Sweep each paper through these concerns; only populated ones reach the output.

- **Scope / tooling / cost** — what the method does · typical cases (concrete problems + sizes reached) · best-fit scenario · boundary (what it can't do) · software & tools · implementation difficulty (lines of code + hardest parts) · compute-cost estimate (CPU core-hours).
- **Method-usage** — setup & parameters · success / validation · failure modes · taking the limit · systematic bias.
- **Scientific** — problem framing & mappings · observable design · model / regime choice.
- **Open problems (gaps)** — research-relevant open problems the *paper itself* flags, in its statements or its own data (e.g. a regime where its own figure shows accuracy breaking down) · the directions that would close them.

**Method-focused, not problem-focused.** Every concern is about *this method* (and the contributor's own codes), never a menu of alternative methods for the same problem — e.g. *software & tools* lists what implements this method, not what else could solve the problem. The method's own lineage (its successors / developed family) is in scope; genuinely *other* methods get at most a line or two for contrast, never a focus.

**Gaps come from the paper, not the agent.** A gap is filled **only** from what the paper states or shows in its own data — each pinned to a location, never the agent's outside knowledge or a guess. A candidate the paper does not support is **demoted to an interview target**, not asserted. The *directions* that would close a gap come from the expert, so they too stay as interview targets, not filled.

**Reconcile gaps across the corpus.** Because the corpus spans the expert's family, a gap an early paper flags may be **closed by the expert's own later paper**. Check every gap against the rest of the corpus and present such a case as its trajectory (*flagged in X → addressed in Y by …*, grounded in Y); the open-gaps table keeps only genuinely **still-open** problems.

## Flow

1. **Intake (ask first).** Ask for the **expert name**, the **method / variant** (a single variant, or the **family the expert developed** — the originating method together with the successor variants built on it), and optionally a **publication source** (Scholar / arXiv / ORCID link or a paper list). If the name is ambiguous (several researchers share it), the method span is unclear (one variant vs. the family), or the source is missing, clarify in brainstorming style — one question at a time, never guess. Also fix the **output path** (method-group dir + variant abbreviation); these can diverge — e.g. a family successor with no method skill of its own routes to the family's method-group dir yet keeps its own abbreviation, so the dir and the filename prefix come from different stems — present 2–3 path options and confirm, never guess.
2. **Resolve corpus.** Find the expert's papers on this method **and the related variants they developed** (the method's own family — *not* other methods for the same problem), from the given source, else web-search the name + method. This intersection (expert ∩ method-family) is the corpus. Rank by relevance + impact; keep a working set (~15–25).
3. **Confirm papers before downloading.** Print a table — `Paper | Authors | Method usage | Year` — with the **chosen expert's name bolded** in each author list (this also disambiguates identity). Ask the user to confirm or trim the set. Download nothing until confirmed.
4. **Download** the confirmed set via `/download-ref` into `.knowledge/literature/<method>/`.
5. **Sweep & extract.** Read each paper through the lens; pull the technical *moves* (the "how", not the results) and the **open problems the paper flags**, each tagged with its **source paper** and evidence location (the corpus spans several). Method-level concerns — typical cases, software & tools, implementation difficulty — may need a brief survey beyond the corpus (web, parallel subagents); mark anything the sources don't state as an interview target rather than inventing it. Gaps in particular come only from the paper's own statements or data.
6. **Select by importance.** Apply the four tests; drop the trivial.
7. **Confirm one at a time.** Present each surviving trick — and each candidate **gap** — to the user individually with its evidence; never batch. For a gap, give a **Pro** (how strongly the paper backs it: explicit statement > shown in its own data > a reading of positive framing) and a **Con** (the weakness), and flag if a **later paper in the corpus** already closes it; the user keeps / cuts / rewords, **demotes** a weakly-grounded gap to an interview target, or recasts a closed one as a trajectory.
8. **Render the dossier** via `/report`, sections in this order: **Scope, tooling & cost** → **Method-usage tricks** → **Scientific tricks** → **Open problems & improvement directions**. Open the HTML.

## Output shape

One webpage at `docs/<method-group>/<method-abbrev>-<expert>-distillation.html`. The group dir matches the existing `docs/<method>/` convention (those dirs already hold `interview.html` / `review.html`); the filename prefixes the specific method variant and the expert, both fixed at intake. Four sections, scientific-report register — declarative and impersonal, abbreviations spelled out, no colloquialisms.

**Scope, tooling & cost** — one table (only rows with real content; method-level rows may be surveyed beyond the corpus):

| Item | Content | Evidence |
|---|---|---|
| What it does | … | … |
| Typical cases | concrete problems + sizes / temperatures reached | … |
| Best-fit | … | … |
| Boundary | … | … |
| Software & tools | what implements *this* method + its own key parameters | … |
| Implementation | lines of code + hardest parts | … |
| Compute cost (core-hours) | … | … |

**Method-usage tricks** and **Scientific tricks** — one table each:

| Trick | What it is | Why it matters | Evidence |
|---|---|---|---|

**Open problems & improvement directions** — a final section pairing the paper-sourced **gaps** (a table — *Open problem (from the paper)* · *Why it matters* · *Evidence* — each row a statement or datum the paper itself supplies) with an **Interview targets** list (the directions that would close them, plus any candidate demoted for weak grounding). Only **still-open** gaps go in the table; a gap the expert's own later work resolved is shown as a one-line trajectory (*flagged in X → addressed in Y*), not as open. The gaps are filled; the directions are not.

Evidence names the **source paper and** the location (e.g. `<Method>'10 Fig. 4`, `<Variant>'18 §III`) — the corpus spans several papers, so a bare "Fig. 4" is ambiguous. Mark the scannable keypoints with `==…==` (renders as a yellow highlight) and bold each trick name, so a human can skim the page. Keep `$…$` math **outside** `==…==` and `**…**` spans — a highlight or bold span cannot contain math and will silently fail to render. This is a property of Markdown-plus-math rendering, not of the report renderer alone: it breaks the same way in **your own chat messages** — the confirmation tables especially, where bolded trick names and expert names sit beside symbols — so never nest `$…$` inside `**…**` or `==…==` anywhere; put the symbol outside the span, or use plain words inside it (write `**N-site cluster**`, not `**$N$-site cluster**`).

For readability, give each table a `widths` list that keeps the label and *Evidence* columns narrow so the prose columns get the room, and mark the *Evidence* column `muted` so citations recede. The page's section navigation (a left rail / chip-bar that tracks the active section) is added by `/report` automatically — no work needed here.

Build the sections as `/report` `table` blocks, then render and place the page:

1. write `report.json` into a working dir `docs/<method-group>/<method-abbrev>-<expert>/`;
2. `python3 skills/report/render_report.py docs/<method-group>/<method-abbrev>-<expert>` — emits `report.html` in that dir;
3. move it up to the flat page: `docs/<method-group>/<method-abbrev>-<expert>-distillation.html`;
4. open it (`open` on macOS, `xdg-open` on Linux).

The working dir keeps `report.json` as the source, so the page re-renders after edits.

## UX rules

- **One decision at a time**, brainstorming style (the `superpowers:brainstorming` approach — explore intent, never batch): 2–3 real options per question, recommend only with a stated reason; use the question tool when available, else number choices.
- **Key points only — never a wall of text.** Every message is a few sentences or one compact table.
- **Confirm anything unclear, never guess.** Not only expert identity, method scope, or paper set — any unclear choice (output path, a trick's wording, whether a gap is grounded) → stop and ask, in the one-decision-at-a-time style above. Always confirm the paper table before any download.
- **Precise, concise, self-defining.** Declarative and impersonal — no casual or colloquial wording (e.g. "the answer for free", "which knob to turn"). Keep the technical terms a method genuinely needs, but be precise and economical, and define every paper-specific term and piece of notation before (or at) its first use with a short plain-language explanation — assume nothing (if you write $D_c$, say what $D$ is too).
- **Stay honest.** Each trick cites a real location; if a paper doesn't state something (e.g. core-hours), say so and mark it an interview target rather than inventing it.
