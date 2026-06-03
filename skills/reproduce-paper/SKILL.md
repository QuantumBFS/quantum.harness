---
name: reproduce-paper
description: Use when the user wants to reproduce a paper's figure or main result. Triggers include "reproduce paper X", "redo the figures of Y", "reproduce arXiv <id>", "put this paper through the harness as a calibration target", "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", "explain while reproducing", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Beginner-facing paper reproduction. This skill is the **spine of the reproduction workflow**: it owns step 0 (clarify the problem), steps 4–5 (review the plan, write the plan HTML), and the implementation stage (run, report, and opt-in verification on user request). It **delegates** method selection, software selection, and parameter setup (steps 1–3) to `/method-*` and `/using-*`, and model facts to `.knowledge/models/`. Brainstorm the science with the user one decision at a time, keep choices pending until the planning questions are complete, then save one `run.json`, build one standalone HTML report (proposal first, results appended), and run only the approved plan.

The workflow, end to end:

```
0. Clarify the problem        — owned here
1. Select method              — /method-*  (triggering)
2. Select software            — /method-*  (routing) → /using-*
3. Configure                  — method setup in /method-*, software params in /using-*
4. Review the plan            — owned here
5. Write the plan HTML        — owned here
Implementation                — run + intermediate output + report (verification opt-in, on user request)
```

## UX — top priority, always on

Everything here serves one reader: a capable physicist new to this paper's methods and to these tools. Keep their mental load low *per question* — but the real goal is that they **learn judgment**: walk them warmly through each decision — a sentence on what the knob does and how the choice would move the result — so they *feel* the tradeoff and build intuition they carry to the next problem. The explaining *is* the value, not overhead; so guide and explain each consequential choice, never silently default one, and never batch them behind a terse "use the standard settings."

- **Plain English — assume nothing about jargon.** Before any term, setting, symbol, or axis label reaches that reader, ask whether they would know this exact token; if it feels obvious to *you*, that is the signal to check it, not skip it. Lead with the plain-English name, never let a symbol or abbreviation appear before the words that define it, and prefer plain words in labels (an axis reading "overlap with the Néel state" beats a bare "$|\langle Z_2|\psi\rangle|^2$"). Make each gloss the *consequence*, not just a definition — "`k_states` = how many low-lying states we compute; 1 = ground state only, so no excited-state tower" — since the point is to help them decide. Only the common method families (ED, DMRG, QMC, VMC, NQS) need no gloss.
- **One decision at a time**, Superpowers brainstorming style: 2–3 options, each one line, each real and executable or explicitly marked "needs setup." Use the question tool when available; otherwise number the choices (`1.`, `2.`, `3.`) so the user can answer with a number. Mark a choice as recommended only when there is a real technical reason, and say the reason in the option line. Never bundle two decisions in one prompt.
- **Paper-stated facts are confirmations, not forks.** If the primary source unambiguously fixes the model, lattice, boundary condition, symmetry sector, plotted observable, normalization, or state selection, state the inferred value with the source phrase and ask for confirmation, not a menu of alternative setups. The confirmation choices are: `1. Confirm`, `2. Show source`, `3. Override/correct`. Only offer alternative setups as choices when the paper is ambiguous, the user asks to deviate, or the choice is genuinely about scope / cost / tooling.
- **Key points only — never a wall of terminal text.** Every message is a few sentences or one compact table that covers the key points. This holds everywhere: questions, setup, runs, waits — short status lines, never raw log dumps. A single question buried in many words is itself a failure. Confirmations are terse: a small table of what's inferred, then a clear choice.

## Expose everything that can drift

Surface **every** choice that could make the reproduction diverge from the paper — never hide one behind a silent default. But separate paper-stated facts from real user choices: confirm source-fixed facts, and ask the user to choose only when there is an actual branch. Low user burden is the job of clarity and brevity *per question*, **not** of asking fewer questions. The drift-relevant decisions are enumerated across the workflow steps below: the shared computation (model, method, software, size) first, then each figure's view of it. Skip a question only when the user already answered it or it carries no scientific consequence — and still show that choice in the proposal so nothing is hidden.

## One source of data: `run.json`

During questioning, do not create a run directory, `run.json`, report, script, plot, or paper-panel image. Keep a compact pending plan in the conversation only until all planning questions are answered. Then write the complete plan once to a timestamped run directory: `tracks/<track>/results/YYYYMMDD-HHMMSS-<paper-or-model>-<brief>/run.json`. Use local time for the timestamp, keep the suffix short and slug-safe, and never reuse a prior run directory. Re-read `run.json` before building the report, before running, and before reporting. **Never** reconstruct a parameter from conversation memory after `run.json` exists — context is not a safe store.

Scripts go to `tracks/<track>/solutions/<script>.{jl|py}` — committed code that can be re-run. Generated data and figures go to `tracks/<track>/results/` — gitignored, not committed.

After the planning questions are complete, `run.json` is the *only* data source. The report is built one-way from it — `run.json` → a generic `report.json` (the render input) → `report.html` — and never read back. `report.json` and the HTML are *derived* views, regenerated from `run.json`; they are never edited or treated as a second source. A run is **one computation** (model + method + its run points — system sizes, bond dimensions, or a temperature grid → one dataset: a spectrum, a curve, or thermodynamic functions) and a list of **figures**, each a single view of it — so several figures from the same computation share one run, never copied across files. Representative shape (each figure's `results` block and the run's `actual` fill in after the run):

```json
{
  "paper":    { "id": "arXiv:XXXX.XXXXX", "title": "…", "url": "…" },
  "model":    { "name": "…", "H": "H = J_1 \\sum_{\\langle ij\\rangle} \\mathbf{S}_i\\cdot\\mathbf{S}_j", "couplings": { "$J_1$": 1.0 }, "lattice": "…", "boundary": "PBC" },
  "method":   { "family": "ED", "exact": true, "tool": "XDiag", "settings": { "sector": "k=0, Sz=0", "k_states": 1 }, "note": "what the tool is and what its key settings mean, in plain English" },
  "params":   [ { "name": "system size $N$", "value": "16, 20", "source": "we choose — paper used up to 40", "why": "largest size a laptop finishes in minutes; sets the finite-size error", "risk": "too small → finite-size artifacts mask the thermodynamic trend", "fix": "report the size series and extrapolate; cross-check the largest size on the cluster" } ],
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

The example is a ground-state ED run; the same schema flexes for a **finite-temperature** target — `x` becomes temperature or β, a run `point` is a `(Dc, τ)` or temperature setting rather than a size, and `method.settings` holds that method's knobs (e.g. `Dc`, `τ`, `β_max` for LTRG; `sweeps`, `thermalization`, `N_wlk` for QMC), so the computation yields thermodynamic curves instead of a spectrum.

## The report: built from `run.json`, rendered by `/report`

Two stdlib-only, offline steps. First `python3 skills/reproduce-paper/build_report.py <run-dir>` maps `run.json` → a generic `report.json`, laying the reproduction out as **Model / Method / Figures**. Then `/report` renders that into one self-contained `tracks/<track>/results/<run>/report.html` (`python3 skills/report/render_report.py <run-dir>`). This skill owns the *plan, the data in `run.json`, and that layout* (`build_report.py`); `/report` owns only generic rendering and the LaTeX→MathML conversion. Write math as LaTeX in `run.json` — `model.H` as a display equation, any other string carrying `$…$` inline, moduli and bra-kets as `\left|\langle Z_2|\psi\rangle\right|^2` so the exponent sits on the whole `|…|` — and it flows through to MathML.

Two moments, same file, per figure:

- **Proposal** (step 5, before compute) — the plan in plain English: the model; the method (with a one-line plain-English `note` on the tool and its settings); a **Parameter setup table** — one row per configured parameter (parameter → value → source → why this value → risk & implication → mitigation/fix) so every choice that can drift is shown with its rationale and its safety net, not just a number; scope and where — plus a **cost table** with one row per run point (run point → estimated wall time → memory) and a short note of anything likely to be finicky or custom. Then, for each figure, what it plots, the observable, what's expected, and **the paper's target panel captured as `paper_image`** — so the figs-to-reproduce are in the proposal report, not just after the run; its result area marked pending.
- **Results** (after compute) — for each figure: our figure beside the paper's target panel already captured at proposal, so the two sit side by side — a small table of the key numbers, an honest verdict (`match`: `yes` / `partly` / `no`, rendered as Reproduced / Partial match / Did not match) with a one-line `why`, the wall time that ran and any changes from the plan, and one rerun line. The **cost table** also gains an Actual column beside each estimate, filled from the run's consumed wall time and memory (`actual`).

### Showing figures and opening the report

- **Discussion stage** — once the target figure/panel is identified (step 0), show the user the paper's figure being reproduced so they see the target while deciding. Embed the **local extracted file** from `.figures/` (guaranteed by step 0), **never a remote URL** — a remote link makes the user open it manually instead of seeing it inline. On the app, embed it inline as a markdown image (`![Fig 2a — from the paper](path/to/figure.png)`); in a terminal, open the file (`open` / `xdg-open`). Decide terminal vs app from the AGENTS.md → Equation Rendering surface signal (per agent; if unknown, open the file). Don't skip it. No run files are written yet.
- **When the report is built or rebuilt** (the proposal at step 5, then again after results) — auto-open `report.html`, which carries the figs-to-reproduce beside our reproduction, in a browser on both terminal and app (`open` on macOS, `xdg-open` on Linux). Open it; don't merely offer.

## Flow — the workflow spine

### Step 0 — Clarify the problem

Once you know which paper this is, make sure it is available locally **before** showing any figure or writing files:

1. **Check the knowledge base** — `grep` the arXiv id / title across `.knowledge/literature/`, and check for *both* the rendered `.md` *and* its extracted figures under the method's `.figures/`.
2. **Run `/download-ref` if either is missing** — the paper not rendered at all, *or* rendered as `.md` but with no `.figures/` extracted (a common state). It fetches the PDF, renders, and extracts the figures; the figure you show in the discussion stage comes from that extraction.

Then brainstorm each drift-relevant decision one at a time; keep choices pending (no files yet). Cover:

- **Description** — is the target clear enough to reproduce? When the user invokes this skill without a paper or figure, ask what to reproduce with **no** recommended option (include known targets if a prior handoff named them; for an unknown target use a neutral option like `Another paper — track unknown until the paper is named`; do not read track READMEs here — `/track-starter` owns track-paper selection).
- **Problem setup** — model + couplings, lattice, boundary; system size; symmetry sector; interaction strength; initial/state selection. These are mostly paper-stated facts → confirm, don't fork.
- **Output** — which figure(s)/panel(s) (one computation can feed several); and **per figure**: the observable plotted (y-axis) + normalization + which states it uses; the x-axis (parameter swept, range, spacing); what we expect to see and what would count as reproduced. **When the scope options carry materially different costs** (e.g. one panel runs at small size on a laptop while another needs a large lattice / GPU / cluster), the figure-scope question *is* a cost decision: give each option an order-of-magnitude **wall-time band pulled forward from the `/method-*` cost model** — the firm work count (flips / sweeps / matvecs) ÷ a stated assumed rate, with the rate named as the pre-probe unknown — so the choice is never cost-blind. Never present scope options whose cost spans orders of magnitude with only vague hints ("laptop-feasible", "wants a cluster") and no numbers. The detailed per-run-point cost table still comes in step 4; this is only the coarse band needed to choose scope.
- **Method parameters** — the parameters that method needs, whatever knobs it actually has (e.g. the symmetry sector for ED, the bond dimension for DMRG). The `/method-*` card lists the full set; confirm the ones the paper fixes and surface the rest as drift-relevant.
- **Per-problem-type extras — confirm what this kind of problem needs.** A finite-temperature target needs the temperature / β grid (and, for an imaginary-time method, the Trotter step); a stochastic target needs sample/sweep counts and seeds; a tensor-network target needs the bond-dimension target. Surface the ones the chosen method will need and confirm them as part of the setup.

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
3. **`/method-*` skill** — `/method-ed`, `/method-mps`, `/method-peps`, `/method-qmc`, `/method-ltrg`, `/method-mcrg`, `/method-vmc`, `/method-qcs`, `/method-mf`. Source for **step 1** (which method suits the target) and **step 2** (which tool the method routes to), plus **step 3 method setup** (the conceptual knobs and tricks).
4. **Selected `/using-*` skill** — `Parameter setup`, `Knobs`, and `Time estimate`. Source for **step 3 software parameters** (the package-specific values) and software-specific cost.
5. **Stack contract** — `skills/<stack>/stack.toml`: install, smoke test, runtime profile, docs, CPU/GPU/MPI setup.
6. **Method/model cards** — fallback notation, code shape, pitfalls, verification when the paper / method skill / tool skill are silent.
7. **User override** — deliberate deviation; record the consequence.

**Step 1 — select method.** Recommend the right `/method-*` route first, with a concrete reason drawn from its *Select method* section (what problems it suits, sizes solved). Invoking the method skill is how this step is answered; do not re-derive method suitability here.

**Step 2 — select software.** From the method skill's *Select software* section, present the recommended tool as "Use /<tool-skill>" with a concrete reason, then 1–2 real alternatives. **Tool introduction is mandatory** — what the package is, who maintains it, what it does, and why it suits *this* problem; do the same (shorter) for alternatives. One option must be `Search web for official paper code / setup` unless the user forbade web access or official code is already verified this turn. Each option shows setup state (`ready`, `needs install`, `needs web check`, `official code unavailable`) and a one-line consequence. Don't recommend a tool just because it is installed, and don't silently switch tools on an install error — say so and let the user choose. Flag the effort honestly when it differs: most routes run an existing package, but some (e.g. LTRG) have no package and mean implementing the algorithm from the `/method-*` card's `## Details` with the tool's primitives — a larger, more error-prone job to choose with eyes open.

**Step 3 — configure (mandatory).** This is the bridge between what the paper did and what this run will actually do, and it is never skipped. Guide parameters strictly **one at a time — one parameter per message; wait for the answer before asking the next, and never present a batch of knobs at once.** Skip any already pinned by the paper or user. Pull **method-side knobs** (tricks, what each controls, how it affects results) from the `/method-*` *Method setup* section, and **software parameter values** from the `/using-*` *Parameter setup* / *Knobs* sections. Each question states: the parameter, why it matters for reproducing this figure, the paper-stated value if one exists, its source, and 2–3 real options, each with its consequence. Recommend only on tool/setup choices, not scientific ones — scale and scientific choices stay neutral. Record each gloss in `method.note` so the report carries it. *(Method-specific care travels with the method card — e.g. `/method-ed` requires naming every symmetry and flagging any approximation; `/method-qmc` requires the sign / equilibration checks; `/method-ltrg` requires the normalization bookkeeping.)* **Finish by recording every configured parameter as a row in `run.json`'s `params` array** — one object per parameter with `name`, `value`, `source`, `why` (why this value, in one plain-English clause), `risk` (what could go wrong and what that drift would do to the result), and `fix` (how to detect or mitigate it). This array is required, not optional: it is what renders the proposal's **Parameter setup** table, so a bare value list is not enough — every row must carry its why, its risk-and-implication, and its fix.

### Step 4 — Review the plan

- **Checklist {survey}.** Run the chosen method's common-error checklist — the *Verification* / *Criticize* items in the `/method-*` card (e.g. QMC: extrapolate Δτ→0, watch the sign, don't read non-commuting observables off the mixed estimator; LTRG: τ→0 and Dc convergence, count log factors once). Confirm the plan already covers them or note the gap.
- **Confirm compute device and estimate resource {survey}.** Read the method skill first to fix the route, then the selected `/using-*` skill's `Time estimate` before any scale question; combine with the method card's cost scaling (e.g. CPMC's ~size³ wall and `>1e11` long-run heuristic, LTRG's O(D⁶·Dc³) per step). Fill the cost table with one row per run point. Exactly one tiny, clearly-labeled timing probe may run before approval — only to measure a rate (matvec / sweep / sample / layer) so the estimate is honest; it yields no scientific result and is discarded. No other compute before Approve.
- **Confirm with the user in the terminal.** Scale questions are **estimate-first and neutral**: show (1) the paper-size run cost and (2) the largest size a normal local PC can plausibly finish in ~15 min, then ask the user to pick among feasible scale / where-to-run options with **no** recommended label (reasons go in the estimate text, not in a biased choice). Label any infeasible option infeasible with the concrete cost reason. This is where the user decides whether to change system size.

### Step 5 — Write the plan HTML

After all planning questions are answered: create the timestamped run directory, write `run.json`, capture the paper's target panel as `paper_image`, run `build_report.py`, render via `/report`, then auto-open it (see *Showing figures and opening the report*). **Visually review** the proposal page — the model, method note, cost table, and each figure's target panel beside its pending result area.

Then ask **Approve / Change / Discuss** — one question, the run's only approval. *Approve* (recommended) locks the plan and runs; *Change <which>* jumps back to that one choice; *Discuss* opens it up.

### Implementation

1. **Run** the approved plan. The script lands at `tracks/<track>/solutions/<model>_<brief>.{jl|py}` and saves output (figures, data) under `tracks/<track>/results/<run>/`. Fix ordinary code breakage quietly and rerun; interrupt the user only when a real choice is needed (e.g. the chosen tool genuinely can't express this target).
2. **Intermediate output {survey}.** Long runs must emit partial estimates, not just a final value — and the method card says *which* signal to watch mid-run: QMC the energy-vs-imaginary-time flattening and the average sign; LTRG the finite, smooth log-scale factors and small discarded weight. Surface these as short status lines so correctness is partially confirmed before the run ends.
3. **Append results + honest verdict.** For each figure set `match` to `yes`, `partly`, or `no` against the `expected` written at plan time and say why — a direct comparison of the run's numbers to expectation, no extra compute, always done. Fill each figure's `results` block and the run's `actual` (consumed wall time and memory per run point) in `run.json`, re-run `build_report.py`, re-render via `/report`, then open it. Offer a couple of next steps drawn from the outcome (a larger scope, another figure from the same data, or stop).
4. **Verification is opt-in.** Do NOT run convergence sweeps, extrapolations (Δτ→0 / τ→0), small-system cross-checks, or benchmark reruns on your own — they cost compute and step 3 already reports the result. Invoke them ONLY when the user challenges or is confused about a result. When that happens: read the `/method-*` *Verification* / *Criticize* section and **propose** the relevant checks Superpowers-brainstorming style — 2–3 options, recommendation-first, each one line with what it confirms and its rough cost — then run only the check(s) the user confirms. Never spend compute on verification the user didn't ask for.

Rendering composes with `/report`; a cluster run composes with `/using-slurm` (ship / submit / monitor / fetch); installs compose with the tool skill (`/setup-julia` for Julia, `/using-cpmc-lab` for the MATLAB CPMC-Lab package, and so on). This skill does not duplicate those.

## Stay honest

- The primary source controls every paper claim; `.knowledge/` cards and `/method-*` surveys are hints.
- Read captions, axis labels, and normalization verbatim before coding.
- Record any change from the paper's setup in `run.json` before the affected run.
- Report the result honestly against the "expected" written at plan time — set `match` to `yes`, `partly`, or `no`, and say why.

## Not this

- No compute before Approve, beyond the one labeled timing probe.
- No failure-fork, no auto-review, no walls of terminal text.
- Don't hide downsizing, fallback tools, missing observables, or changes from the paper.
- Don't show the target figure as a remote URL or a bare link the user must open — embed the local extracted image file inline; if none exists, run `/download-ref` first.
- Don't duplicate `/method-*` or `/using-*` content here — delegate steps 1–3 and pull their checklists; this spine owns step 0, steps 4–5, and the implementation flow.
- Don't make the user read internal files to understand the plan — the proposal page is the plain-English surface.
- Don't keep a second copy of the run's data; `run.json` is the single source.
