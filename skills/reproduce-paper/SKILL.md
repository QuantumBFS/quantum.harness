---
name: reproduce-paper
description: Use when the user wants to reproduce a paper's figure or main result. Triggers include "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", "explain while reproducing", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Beginner-facing paper reproduction. Brainstorm the science with the user one decision at a time, keep choices pending until the planning questions are complete, then save one `run.json`, build one standalone HTML report (proposal first, results appended), and run only the approved plan.

## UX — top priority, always on

Everything here serves one reader: a capable physicist new to this paper's methods and to these tools. Keep their mental load low.

- **Plain English — assume nothing about jargon.** Before any term, setting, symbol, or axis label reaches that reader, ask whether they would know this exact token; if it feels obvious to *you*, that is the signal to check it, not skip it. Lead with the plain-English name, never let a symbol or abbreviation appear before the words that define it, and prefer plain words in labels (an axis reading "overlap with the Néel state" beats a bare "$|\langle Z_2|\psi\rangle|^2$"). Make each gloss the *consequence*, not just a definition — "`k_states` = how many low-lying states we compute; 1 = ground state only, so no excited-state tower" — since the point is to help them decide. Only the common method families (ED, DMRG, QMC, VMC, NQS) need no gloss.
- **One decision at a time**, Superpowers brainstorming style: 2–3 options, each one line, each real and executable or explicitly marked "needs setup." Use the question tool when available; otherwise number the choices (`1.`, `2.`, `3.`) so the user can answer with a number. Mark a choice as recommended only when there is a real technical reason, and say the reason in the option line. Never bundle two decisions in one prompt.
- **Initial target-selection question is neutral.** When the user invokes this skill without a paper or figure, ask what target to reproduce with no recommended option. Include known paper targets if already provided by the user or by another skill handoff. For an unknown target, use a neutral option like `Another paper — track unknown until the paper is named`. Do not read track READMEs here; `/track-starter` owns track-paper selection.
- **Paper-stated facts are confirmations, not forks.** If the primary source unambiguously fixes the model, lattice, boundary condition, symmetry sector, plotted observable, normalization, or state selection, state the inferred value with the source phrase and ask for confirmation, not a menu of alternative setups. The confirmation choices are: `1. Confirm`, `2. Show source`, `3. Override/correct`. Only offer alternative setups as choices when the paper is ambiguous, the user asks to deviate, or the choice is genuinely about scope / cost / tooling.
- **Show the setup card before method knobs.** After the target figure/result is selected and the paper-fixed setup has been read, print a compact card with the objective, model introduction, model parameter setup, and method introduction before asking for method parameters. Do not ask about tolerance, sectors, bond dimension, samples, sweeps, seeds, or other method knobs until this card has appeared.
- **Configuration step is mandatory.** After the setup card and before proposal materialization, guide the user through method and runtime parameters one at a time. Each parameter question must state what the parameter controls, why it matters for reproducing the selected figure, the paper-stated value if one exists, and the consequence of each option. Finish with a compact configuration summary before estimating or writing files.
- **Scale questions are estimate-first and neutral.** Before asking the user to choose size / scope / where-to-run, show two estimates: (1) the paper-size run cost, and (2) the largest size a normal local PC can plausibly finish in about 15 minutes. Then ask the user to pick among feasible scale options without a recommended label. Give reasons in the estimate/tradeoff text, not by biasing the choice. If an option is infeasible, label it infeasible with the concrete cost reason.
- **Key points only — never a wall of terminal text.** Every message is a few sentences or one compact table that covers the key points. This holds everywhere: questions, setup, runs, waits — short status lines, never raw log dumps. A single question buried in many words is itself a failure.
- Confirmations are terse: a small table of what's inferred, then a clear choice.

## Expose everything that can drift

Surface **every** choice that could make the reproduction diverge from the paper — never hide one behind a silent default. But separate paper-stated facts from real user choices: confirm source-fixed facts, and ask the user to choose only when there is an actual branch. Low user burden is the job of clarity and brevity *per question*, **not** of asking fewer questions. The drift-relevant decisions — the shared computation first, then each figure:

- which figure(s) or panel(s) — one run can reproduce several from the same computation;
- model + couplings, lattice, boundary;
- method, and whether it is exact or an approximation;
- the parameters that method needs (whatever knobs it actually has — e.g. the symmetry sector for ED, the bond dimension for DMRG);
- size / scope, and where it runs;
- **for each figure:** the observable plotted (the y-axis) + normalization + which states it uses; the x-axis — the parameter swept, its range and spacing; what we expect to see and what would count as reproduced.

Skip a question only when the user already answered it or it carries no scientific consequence — and still show that choice in the proposal so nothing is hidden.

## Setup card before method parameters

Once the target is selected and the source-fixed setup has been identified, show a compact setup card before asking method-parameter questions. This is a reader-facing orientation card, not a proposal file and not a saved artifact during the questioning phase.

Required card rows:

| Row | Content |
|---|---|
| Objective | The exact figure/panel or result being reproduced, and what "reproduced" means. |
| Model | Plain-English model introduction plus the Hamiltonian name or formula if known. |
| Model parameters | Couplings, lattice, boundary, size, sector, initial/state selection, and observable fixed by the paper. |
| Method | Plain-English method introduction, exact vs approximate status, and recommended tool-using skill when known. |

After the card, **pause and confirm the setup with the user** before entering the configuration step. Present the card and ask `1. Confirm`, `2. Show source`, `3. Override/correct`. Do not proceed to tool selection or parameter questions until the user confirms the setup card.

## Configuration step

Guide setup parameters before writing files. This is the bridge between "what the paper did" and "what this run will actually do."

Use this source order:

1. **Paper** — caption, axis labels, body, supplement, and verified official code. This fixes scientific facts.
2. **Track-starter handoff / Track README** — only when `/track-starter` selected the target; use it as track-scoped objective context, not for target selection.
3. **Method skill** — `/method-ed`, `/method-mps`, `/method-peps`, `/method-qmc`, `/method-vmc`, or `/method-qcs`; this is the source for generic method insight and tool-skill selection.
4. **Selected tool skill** — `Parameter setup` and `Time estimate`; this is the source for software-specific knobs and cost.
5. **Stack contract** — `skills/<stack>/stack.toml`; install, smoke test, runtime profile, docs, CPU/GPU/MPI setup.
6. **Method/model cards** — fallback notation, code shape, pitfalls, and verification when paper/method/tool skill are silent.
7. **User override** — deliberate deviation; record the consequence.

For each unresolved parameter, ask one numbered question with: parameter, why it matters, paper value, source, and 2-3 real options. Recommend only tool/setup choices. Scale choices stay neutral after showing the paper-size estimate and the largest local-PC-in-15-min estimate from the selected tool skill.

Finish with a compact summary table containing `Parameter`, `Value`, and `Source`, then materialize the proposal.

## One source of data: `run.json`

During questioning, do not create a run directory, `run.json`, report, script, plot, or paper-panel image. Keep a compact pending plan in the conversation only until all planning questions are answered. Then write the complete plan once to a timestamped run directory: `tracks/<track>/results/YYYYMMDD-HHMMSS-<paper-or-model>-<brief>/run.json`. Use local time for the timestamp, keep the suffix short and slug-safe, and never reuse a prior run directory. Re-read `run.json` before building the report, before running, and before reporting. **Never** reconstruct a parameter from conversation memory after `run.json` exists — context is not a safe store.

Scripts go to `tracks/<track>/solutions/<script>.{jl|py}` — committed code that can be re-run. Generated data and figures go to `tracks/<track>/results/` — gitignored, not committed.

After the planning questions are complete, `run.json` is the *only* data source. The report is built one-way from it — `run.json` → a generic `report.json` (the render input) → `report.html` — and never read back. `report.json` and the HTML are *derived* views, regenerated from `run.json`; they are never edited or treated as a second source. A run is **one computation** (model + method + sizes → one spectrum/dataset) and a list of **figures**, each a single view of it — so several figures from the same data share one run, never copied across files. Representative shape (each figure's `results` block and the run's `actual` fill in after the run):

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

- **Proposal** (before compute) — the plan in plain English: the model; the method (with a one-line plain-English `note` on the tool and its settings — what XDiag is, what `k_states`/`tol` do) and its parameters; scope and where — plus a **cost table** with one row per run point (run point → estimated wall time → memory) and a short note of anything likely to be finicky or custom. Then, for each figure, what it plots, the observable, what's expected, and **the paper's target panel captured as `paper_image`** — so the figs-to-reproduce are in the proposal report, not just after the run; its result area marked pending.
- **Results** (after compute) — for each figure: our figure beside the paper's target panel already captured at proposal, so the two sit side by side — a small table of the key numbers, an honest verdict (`match`: `yes` / `partly` / `no`, rendered as Reproduced / Partial match / Did not match) with a one-line `why`, the wall time that ran and any changes from the plan, and one rerun line. The **cost table** also gains an Actual column beside each estimate, filled from the run's consumed wall time and memory (`actual`).

### Showing figures and opening the report

- **Discussion stage** — once the target figure/panel is identified, show the user the paper's figure being reproduced so they see the target while deciding. On the app, embed it inline as a markdown image link to the figure file (`![Fig 2a — from the paper](path/to/figure.png)`); in a terminal, open the image file instead (`open` / `xdg-open`). Surface is the AGENTS.md → Equation Rendering signal (`CLAUDE_CODE_ENTRYPOINT`). No run files are written yet.
- **When the report is built or rebuilt** (the proposal, then again after results) — auto-open `report.html`, which carries the figs-to-reproduce beside our reproduction, in a browser on both terminal and app (`open` on macOS, `xdg-open` on Linux). Open it; don't merely offer.

## Flow

1. **Brainstorm** each drift-relevant decision above, one at a time. Do not write files during this questioning phase; keep choices pending until the full plan is known. Once the target figure/panel is identified, show the user that paper figure (see **Showing figures and opening the report**).
2. **Show the setup card** after the target and source-fixed setup are known, before method-parameter questions.
3. **Configure the run** — guide method/tool/runtime parameters one at a time, then print a compact configuration summary.
4. **Estimate carefully.** Use the scaling rules below to fill the cost table — it drives the user's scope and where-to-run choices. For any scale question, estimate the paper-size run and the largest local-PC-in-15-min run before asking the user to choose. Flag finicky or custom parts up front so they're anticipated, but don't over-plan.
5. **Materialize the proposal** — after all planning questions are answered, create the timestamped run directory, write `run.json`, capture the paper's target panel as `paper_image` (so the figs-to-reproduce are in the proposal report), run `build_report.py`, render via `/report`, then open it per **Showing figures and opening the report**.
6. **Approve / Change / Discuss** — one question once the proposal is built. *Approve* (recommended) locks the plan and runs; *Change <which>* jumps back to that one choice; *Discuss* opens it up. This is the run's only approval.
7. **Run** the approved plan. The script lands at `tracks/<track>/solutions/<model>_<brief>.{jl|py}` and saves its output (figures, data) under `tracks/<track>/results/<run>/`. Fix ordinary code breakage quietly and rerun; interrupt the user only when a real choice is needed (e.g., the chosen tool genuinely can't express this target).
8. **Append results** — fill each figure's `results` block and the run's `actual` (consumed wall time and memory per run point) in `run.json`, re-run `build_report.py`, re-render via `/report`, then open it per **Showing figures and opening the report**. Then offer a couple of next steps drawn from the outcome (e.g., a larger scope, another figure from the same data, or stop).

Rendering composes with `/report`; a cluster run composes with `/using-slurm` (ship / submit / monitor / fetch); installs compose with `/setup-julia`. This skill does not duplicate those.

## Estimating cost

Read the selected method skill first to choose the tool route, then read the selected tool-using skill's `Time estimate` section before asking any scale question. This skill only enforces the user interaction: show the paper-size estimate, show the largest local-PC-in-15-min estimate, then ask a neutral numbered scale question.

Use `skills/<stack>/stack.toml` only for setup/runtime profile facts such as CPU vs GPU, MPI, smoke test, install command, and official docs. Use method/model cards only as fallback context when the paper, method skill, and selected tool skill are silent.

Exactly one tiny, clearly-labeled timing probe may run before approval, and only to measure a rate such as matvec / sweep / sample / step so the estimate is honest. It yields no scientific result and is discarded. Fill one cost-table row per run point. No other compute before Approve.

## Parameters each method needs

Read the selected method skill to determine which tool skill applies. Then read the selected tool-using skill's `Parameter setup` section and ask those knobs one at a time, skipping any already pinned by the paper or user. Each question must gloss the knob in plain English, name its source, and record the gloss in `method.note` so the report carries it too.

**ED needs care on symmetry.** Name each symmetry the paper or method uses (momentum `k`, inversion, total `Sz`, particle number, point group, boundary), say why the chosen sector is right, and flag any exact symmetry left unused. State a dense full-spectrum run as "exact within the chosen sector." Never present an approximation — FSA (Forward Scattering Approximation: a small basis built from repeated Hamiltonian applications), a few Krylov states, or a reduced window — as a full-spectrum reproduction; present it as an approximation with its scientific consequence.

## Picking the tool

Recommend the right method skill first, then the tool-using skill it selects. Method skills carry generic method insight and tool-selection rules; tool skills carry software-specific setup and estimates. For each candidate stack, consult its skill folder and `stack.toml` (for example `/using-xdiag` with `skills/using-xdiag/stack.toml`, `/using-netket` with `skills/using-netket/stack.toml`, `/using-tensorcircuit-ng`, `/using-pepskit`, `/using-itensors`, `/using-quspin`, `/using-sse`, or `/using-jax`). The executable source of truth for installs remains `Makefile` / setup scripts; `stack.toml` names install commands, smoke tests, docs, official URLs, and setup constraints. Method cards may narrow the stack order only after the method skill has selected the method route.

**Tool introduction is mandatory.** When presenting the recommended tool, include a plain-English introduction: what the package is, who maintains it, what it does, and what makes it suited to this specific problem. Give solid, concrete reasons for the recommendation — not just "it supports X" but why X matters for this paper's reproduction. Do the same (shorter) for alternatives so the user can compare.

Tool and setup questions are recommendation-first. Present the recommended route as "Use /<tool-skill>" with a concrete reason, then 1-2 real alternatives. One option must be `Search web for official paper code / setup` unless the user has forbidden web access or the current turn has already verified official code from a primary source. Do not search the web silently; offer it as a selectable option or state that the user already asked for it. Each option shows setup state (`ready`, `needs install`, `needs web check`, `official code unavailable`) and a one-line consequence. Don't recommend a tool just because it is installed, and don't silently switch tools on an install error — say so and let the user choose.

## Stay honest

- The primary source controls every paper claim; `.knowledge/` cards are hints.
- Read captions, axis labels, and normalization verbatim before coding.
- Record any change from the paper's setup in `run.json` before the affected run.
- Report the result honestly against the "expected" written at plan time — set `match` to `yes`, `partly`, or `no`, and say why.

## Not this

- No compute before Approve, beyond the one labeled timing probe.
- No failure-fork, no auto-review, no walls of terminal text.
- Don't hide downsizing, fallback tools, missing observables, or changes from the paper.
- Don't make the user read internal files to understand the plan — the proposal page is the plain-English surface.
- Don't keep a second copy of the run's data; `run.json` is the single source.
