---
name: reproduce-paper
description: Use when the user wants to reproduce a paper's figure or main result. Triggers include "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", "explain while reproducing", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Beginner-facing paper reproduction. This skill is the **spine of the reproduction workflow**: it owns step 0 (clarify the problem), steps 4–5 (review the plan, write the plan HTML), and the implementation stage (run, verify, report). It **delegates** method selection, software selection, and parameter setup (steps 1–3) to `/method-*` and `/using-*`, and model facts to `.knowledge/models/`. Brainstorm the science with the user one decision at a time, keep choices pending until the planning questions are complete, then save one `run.json`, build one standalone HTML report (proposal first, results appended), and run only the approved plan.

The workflow, end to end:

```
0. Clarify the problem        — owned here
1. Select method              — /method-*  (triggering)
2. Select software            — /method-*  (routing) → /using-*
3. Configure                  — method setup in /method-*, software params in /using-*
4. Review the plan            — owned here
5. Write the plan HTML        — owned here
Implementation                — run + intermediate output + verify (checks from /method-*)
```

## UX — top priority, always on

Everything here serves one reader: a capable physicist new to this paper's methods and to these tools. Keep their mental load low.

- **Plain English — assume nothing about jargon.** Before any term, setting, symbol, or axis label reaches that reader, ask whether they would know this exact token; if it feels obvious to *you*, that is the signal to check it, not skip it. Lead with the plain-English name, never let a symbol or abbreviation appear before the words that define it, and prefer plain words in labels (an axis reading "overlap with the Néel state" beats a bare "$|\langle Z_2|\psi\rangle|^2$"). Make each gloss the *consequence*, not just a definition — "`k_states` = how many low-lying states we compute; 1 = ground state only, so no excited-state tower" — since the point is to help them decide. Only the common method families (ED, DMRG, QMC, VMC, NQS) need no gloss.
- **One decision at a time**, Superpowers brainstorming style: 2–3 options, each one line, each real and executable or explicitly marked "needs setup." Use the question tool when available; otherwise number the choices (`1.`, `2.`, `3.`) so the user can answer with a number. Mark a choice as recommended only when there is a real technical reason, and say the reason in the option line. Never bundle two decisions in one prompt.
- **Paper-stated facts are confirmations, not forks.** If the primary source unambiguously fixes the model, lattice, boundary condition, symmetry sector, plotted observable, normalization, or state selection, state the inferred value with the source phrase and ask for confirmation, not a menu of alternative setups. The confirmation choices are: `1. Confirm`, `2. Show source`, `3. Override/correct`. Only offer alternative setups as choices when the paper is ambiguous, the user asks to deviate, or the choice is genuinely about scope / cost / tooling.
- **Key points only — never a wall of terminal text.** Every message is a few sentences or one compact table that covers the key points. This holds everywhere: questions, setup, runs, waits — short status lines, never raw log dumps. A single question buried in many words is itself a failure. Confirmations are terse: a small table of what's inferred, then a clear choice.

## Expose everything that can drift

Surface **every** choice that could make the reproduction diverge from the paper — never hide one behind a silent default. But separate paper-stated facts from real user choices: confirm source-fixed facts, and ask the user to choose only when there is an actual branch. Low user burden is the job of clarity and brevity *per question*, **not** of asking fewer questions. The drift-relevant decisions are enumerated across the workflow steps below: the shared computation (model, method, software, size) first, then each figure's view of it. Skip a question only when the user already answered it or it carries no scientific consequence — and still show that choice in the proposal so nothing is hidden.

## One source of data: `run.json`

During questioning, do not create a run directory, `run.json`, report, script, plot, or paper-panel image. Keep a compact pending plan in the conversation only until all planning questions are answered. Then write the complete plan once to a timestamped run directory: `tracks/<track>/results/YYYYMMDD-HHMMSS-<paper-or-model>-<brief>/run.json`. Use local time for the timestamp, keep the suffix short and slug-safe, and never reuse a prior run directory. Re-read `run.json` before building the report, before running, and before reporting. **Never** reconstruct a parameter from conversation memory after `run.json` exists — context is not a safe store.

Scripts go to `tracks/<track>/solutions/<script>.{jl|py}` — committed code that can be re-run. Generated data and figures go to `tracks/<track>/results/` — gitignored, not committed.

After the planning questions are complete, `run.json` is the *only* data source. The report is built one-way from it — `run.json` → a generic `report.json` (the render input) → `report.html` — and never read back. `report.json` and the HTML are *derived* views, regenerated from `run.json`; they are never edited or treated as a second source. A run is **one computation** (model + method + sizes → one spectrum/dataset) and a list of **figures**, each a single view of it — so several figures from the same computation share one run, never copied across files. Representative shape (each figure's `results` block and the run's `actual` fill in after the run):

```json
{
  "paper":    { "id": "arXiv:2302.04919", "title": "…", "url": "…" },
  "model":    { "name": "…", "H": "H = J_1 \\sum_{\\langle ij\\rangle} \\mathbf{S}_i\\cdot\\mathbf{S}_j", "couplings": { "$J_1$": 1.0 }, "lattice": "…", "boundary": "PBC" },
  "method":   { "family": "ED", "exact": true, "tool": "XDiag", "settings": { "sector": "k=0, Sz=0", "k_states": 1 }, "note": "what the tool is and what its key settings mean, in plain English" },
  "scope":    { "label": "beginner" },
  "estimate": [ { "point": "N=16", "wall": "~30 s", "memory": "~0.2 GB" }, { "point": "N=20", "wall": "~6 min", "memory": "~2 GB" } ],
  "actual":   [ { "point": "N=16", "wall": "22 s", "memory": "0.2 GB" } ],
  "where":    "local",
  "risks":    ["observable not built-in — implement by hand"],
  "figures":  [
    {
      "id": "Fig 2a", "paper_image": "figs/paper_fig2a.png", "plots": "$m^2$ vs $J_2/J_1$", "x": "$J_2/J_1$", "x_range": "0 → 1, step 0.05", "y": "$m^2$",
      "observe":  { "quantity": "…", "normalization": "…", "states": "ground state only" },
      "expected": "what we should see, and what would count as reproduced",
      "results":  { "figure": "figs/fig2a.png", "numbers": {}, "match": "", "why": "", "wall": "", "changes": [], "rerun": "" }
    }
  ]
}
```

## The report: built from `run.json`, rendered by `/report`

Two stdlib-only, offline steps. First `python3 skills/reproduce-paper/build_report.py <run-dir>` maps `run.json` → a generic `report.json`, laying the reproduction out as **Model / Method / Figures**. Then `/report` renders that into one self-contained `tracks/<track>/results/<run>/report.html` (`python3 skills/report/render_report.py <run-dir>`). This skill owns the *plan, the data in `run.json`, and that layout* (`build_report.py`); `/report` owns only generic rendering and the LaTeX→MathML conversion. Write math as LaTeX in `run.json` — `model.H` as a display equation, any other string carrying `$…$` inline, moduli and bra-kets as `\left|\langle Z_2|\psi\rangle\right|^2` so the exponent sits on the whole `|…|` — and it flows through to MathML.

Two moments, same file, per figure:

- **Proposal** (step 5, before compute) — the plan in plain English: the model; the method (with a one-line plain-English `note` on the tool and its settings) and its parameters; scope and where — plus a **cost table** with one row per run point (run point → estimated wall time → memory) and a short note of anything likely to be finicky or custom. Then, for each figure, what it plots, the observable, what's expected, and **the paper's target panel captured as `paper_image`** — so the figs-to-reproduce are in the proposal report, not just after the run; its result area marked pending.
- **Results** (after compute) — for each figure: our figure beside the paper's target panel already captured at proposal, so the two sit side by side — a small table of the key numbers, an honest verdict (`match`: `yes` / `partly` / `no`, rendered as Reproduced / Partial match / Did not match) with a one-line `why`, the wall time that ran and any changes from the plan, and one rerun line. The **cost table** also gains an Actual column beside each estimate, filled from the run's consumed wall time and memory (`actual`).

### Showing figures and opening the report

- **Discussion stage** — once the target figure/panel is identified (step 0), show the user the paper's figure being reproduced so they see the target while deciding. On the app, embed it inline as a markdown image link to the figure file (`![Fig 2a — from the paper](path/to/figure.png)`); in a terminal, open the image file instead (`open` / `xdg-open`). Surface is the AGENTS.md → Equation Rendering signal (`CLAUDE_CODE_ENTRYPOINT`). No run files are written yet.
- **When the report is built or rebuilt** (the proposal at step 5, then again after results) — auto-open `report.html`, which carries the figs-to-reproduce beside our reproduction, in a browser on both terminal and app (`open` on macOS, `xdg-open` on Linux). Open it; don't merely offer.

## Flow — the workflow spine

### Step 0 — Clarify the problem

Brainstorm each drift-relevant decision one at a time; keep choices pending (no files yet). Cover:

- **Description** — is the target clear enough to reproduce? When the user invokes this skill without a paper or figure, ask what to reproduce with **no** recommended option (include known targets if a prior handoff named them; for an unknown target use a neutral option like `Another paper — track unknown until the paper is named`; do not read track READMEs here — `/track-starter` owns track-paper selection).
- **Problem setup** — model + couplings, lattice, boundary; system size; symmetry sector; interaction strength; initial/state selection. These are mostly paper-stated facts → confirm, don't fork.
- **Output** — which figure(s)/panel(s) (one computation can feed several); and **per figure**: the observable plotted (y-axis) + normalization + which states it uses; the x-axis (parameter swept, range, spacing); what we expect to see and what would count as reproduced.
- **Per-problem-type extras — confirm what this kind of problem needs.** A finite-temperature target needs the temperature / β grid (and, for an imaginary-time method, the Trotter step); a stochastic target needs sample/sweep counts and seeds; a tensor-network target needs the bond-dimension target. Surface the ones the chosen method will need (the `/method-*` card lists them) and confirm them as part of the setup.

Once the target figure/panel is identified, **show the user that paper figure** (see *Showing figures and opening the report*).

**Close step 0 with the setup card**, then pause and confirm before any method-parameter question. The card is a reader-facing orientation card, not a saved artifact:

| Row | Content |
|---|---|
| Objective | The exact figure/panel or result being reproduced, and what "reproduced" means. |
| Model | Plain-English model introduction plus the Hamiltonian name or formula if known. |
| Model parameters | Couplings, lattice, boundary, size, sector, initial/state selection, and observable fixed by the paper. |
| Method | Plain-English method introduction, exact vs approximate status, and the recommended `/method-*` route when known. |

Present the card and ask `1. Confirm`, `2. Show source`, `3. Override/correct`. Do not proceed to steps 1–3 until the user confirms the setup card.

### Steps 1–3 — Select method, select software, configure (delegate)

These three steps are owned by the method and tool skills; this spine only enforces the user interaction (one decision at a time, recommendation-first, plain English). Resolve unknowns in this source order:

1. **Paper** — caption, axis labels, body, supplement, verified official code. Fixes scientific facts.
2. **Track-starter handoff / Track README** — only when `/track-starter` selected the target; track-scoped objective context, not target selection.
3. **`/method-*` skill** — `/method-ed`, `/method-mps`, `/method-peps`, `/method-qmc`, `/method-ltrg`, `/method-vmc`, `/method-qcs`, `/method-mf`. Source for **step 1** (which method suits the target) and **step 2** (which tool the method routes to), plus **step 3 method setup** (the conceptual knobs and tricks).
4. **Selected `/using-*` skill** — `Parameter setup`, `Knobs`, and `Time estimate`. Source for **step 3 software parameters** (the package-specific values) and software-specific cost.
5. **Stack contract** — `skills/<stack>/stack.toml`: install, smoke test, runtime profile, docs, CPU/GPU/MPI setup.
6. **Method/model cards** — fallback notation, code shape, pitfalls, verification when the paper / method skill / tool skill are silent.
7. **User override** — deliberate deviation; record the consequence.

**Step 1 — select method.** Recommend the right `/method-*` route first, with a concrete reason drawn from its *Select method* section (what problems it suits, sizes solved). Invoking the method skill is how this step is answered; do not re-derive method suitability here.

**Step 2 — select software.** From the method skill's *Select software* section, present the recommended tool as "Use /<tool-skill>" with a concrete reason, then 1–2 real alternatives. **Tool introduction is mandatory** — what the package is, who maintains it, what it does, and why it suits *this* problem; do the same (shorter) for alternatives. One option must be `Search web for official paper code / setup` unless the user forbade web access or official code is already verified this turn. Each option shows setup state (`ready`, `needs install`, `needs web check`, `official code unavailable`) and a one-line consequence. Don't recommend a tool just because it is installed, and don't silently switch tools on an install error — say so and let the user choose.

**Step 3 — configure.** Guide parameters one at a time, skipping any already pinned by the paper or user. Pull **method-side knobs** (tricks, what each controls, how it affects results) from the `/method-*` *Method setup* section, and **software parameter values** from the `/using-*` *Parameter setup* / *Knobs* sections. Each question states: the parameter, why it matters for reproducing this figure, the paper-stated value if one exists, its source, and the consequence of each option. Record each gloss in `method.note` so the report carries it. *(Method-specific care travels with the method card — e.g. `/method-ed` requires naming every symmetry and flagging any approximation; `/method-qmc` requires the sign / equilibration checks; `/method-ltrg` requires the normalization bookkeeping.)* Finish with a compact configuration summary table (`Parameter`, `Value`, `Source`).

### Step 4 — Review the plan

- **Checklist {survey}.** Run the chosen method's common-error checklist — the *Verification* / "what the expert would criticize" items in the `/method-*` card (e.g. QMC: extrapolate Δτ→0, watch the sign, don't read non-commuting observables off the mixed estimator; LTRG: τ→0 and Dc convergence, count log factors once). Confirm the plan already covers them or note the gap.
- **Confirm compute device and estimate resource {survey}.** Read the method skill first to fix the route, then the selected `/using-*` skill's `Time estimate` before any scale question; combine with the method card's cost scaling (e.g. CPMC's ~size³ wall and `>1e11` long-run heuristic, LTRG's O(D⁶·Dc³) per step). Fill the cost table with one row per run point. Exactly one tiny, clearly-labeled timing probe may run before approval — only to measure a rate (matvec / sweep / sample / layer) so the estimate is honest; it yields no scientific result and is discarded. No other compute before Approve.
- **Confirm with the user in the terminal.** Scale questions are **estimate-first and neutral**: show (1) the paper-size run cost and (2) the largest size a normal local PC can plausibly finish in ~15 min, then ask the user to pick among feasible scale / where-to-run options with **no** recommended label (reasons go in the estimate text, not in a biased choice). Label any infeasible option infeasible with the concrete cost reason. This is where the user decides whether to change system size.

### Step 5 — Write the plan HTML

After all planning questions are answered: create the timestamped run directory, write `run.json`, capture the paper's target panel as `paper_image`, run `build_report.py`, render via `/report`, then auto-open it (see *Showing figures and opening the report*). **Visually review** the proposal page — the model, method note, cost table, and each figure's target panel beside its pending result area.

Then ask **Approve / Change / Discuss** — one question, the run's only approval. *Approve* (recommended) locks the plan and runs; *Change <which>* jumps back to that one choice; *Discuss* opens it up.

### Implementation

1. **Run** the approved plan. The script lands at `tracks/<track>/solutions/<model>_<brief>.{jl|py}` and saves output (figures, data) under `tracks/<track>/results/<run>/`. Fix ordinary code breakage quietly and rerun; interrupt the user only when a real choice is needed (e.g. the chosen tool genuinely can't express this target).
2. **Intermediate output {survey}.** Long runs must emit partial estimates, not just a final value — and the method card says *which* signal to watch mid-run: QMC the energy-vs-imaginary-time flattening and the average sign; LTRG the finite, smooth log-scale factors and small discarded weight. Surface these as short status lines so correctness is partially confirmed before the run ends.
3. **Verify correctness {survey}.** Apply the `/method-*` *Verification* — final checks (Δτ→0 / τ→0 extrapolation, Dc or bond-dimension convergence, small-system ED cross-check, benchmark comparison) — and report each figure's result honestly against the `expected` written at plan time: set `match` to `yes`, `partly`, or `no`, and say why.
4. **Append results.** Fill each figure's `results` block and the run's `actual` (consumed wall time and memory per run point) in `run.json`, re-run `build_report.py`, re-render via `/report`, then open it. Offer a couple of next steps drawn from the outcome (a larger scope, another figure from the same data, or stop).

Rendering composes with `/report`; a cluster run composes with `/using-slurm` (ship / submit / monitor / fetch); installs compose with `/setup-julia`. This skill does not duplicate those.

## Stay honest

- The primary source controls every paper claim; `.knowledge/` cards and `/method-*` surveys are hints.
- Read captions, axis labels, and normalization verbatim before coding.
- Record any change from the paper's setup in `run.json` before the affected run.
- Report the result honestly against the "expected" written at plan time — set `match` to `yes`, `partly`, or `no`, and say why.

## Not this

- No compute before Approve, beyond the one labeled timing probe.
- No failure-fork, no auto-review, no walls of terminal text.
- Don't hide downsizing, fallback tools, missing observables, or changes from the paper.
- Don't duplicate `/method-*` or `/using-*` content here — delegate steps 1–3 and pull their checklists; this spine owns step 0, steps 4–5, and the implementation flow.
- Don't make the user read internal files to understand the plan — the proposal page is the plain-English surface.
- Don't keep a second copy of the run's data; `run.json` is the single source.
