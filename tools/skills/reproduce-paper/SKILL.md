---
name: reproduce-paper
description: Use when the user wants to reproduce a paper's figure or main result. Triggers include "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", "explain while reproducing", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Beginner-facing paper reproduction. Brainstorm the science with the user one decision at a time, save every choice to `run.json`, build one standalone HTML report (proposal first, results appended), and run only the approved plan.

## UX — top priority, always on

Everything here serves one reader: a capable physicist new to this paper's methods and to these tools. Keep their mental load low.

- **Plain English — assume nothing about jargon.** Before any term, setting, symbol, or axis label reaches that reader, ask whether they would know this exact token; if it feels obvious to *you*, that is the signal to check it, not skip it. Lead with the plain-English name, never let a symbol or abbreviation appear before the words that define it, and prefer plain words in labels (an axis reading "overlap with the Néel state" beats a bare "$|\langle Z_2|\psi\rangle|^2$"). Make each gloss the *consequence*, not just a definition — "`k_states` = how many low-lying states we compute; 1 = ground state only, so no excited-state tower" — since the point is to help them decide. Only the common method families (ED, DMRG, QMC, VMC, NQS) need no gloss.
- **One decision at a time**, Superpowers brainstorming style: 2–3 options, recommended first, each one line, each real and executable or explicitly marked "needs setup." Never bundle two decisions in one prompt.
- **Key points only — never a wall of terminal text.** Every message is a few sentences or one compact table that covers the key points. This holds everywhere: questions, setup, runs, waits — short status lines, never raw log dumps. A single question buried in many words is itself a failure.
- Confirmations are terse: a small table of what's inferred, then a clear choice.

## Expose everything that can drift

Surface **every** choice that could make the reproduction diverge from the paper — never hide one behind a silent default. Low user burden is the job of clarity and brevity *per question*, **not** of asking fewer questions. The drift-relevant decisions — the shared computation first, then each figure:

- which figure(s) or panel(s) — one run can reproduce several from the same computation;
- model + couplings, lattice, boundary;
- method, and whether it is exact or an approximation;
- the parameters that method needs (whatever knobs it actually has — e.g. the symmetry sector for ED, the bond dimension for DMRG);
- size / scope, and where it runs;
- **for each figure:** the observable plotted (the y-axis) + normalization + which states it uses; the x-axis — the parameter swept, its range and spacing; what we expect to see and what would count as reproduced.

Skip a question only when the user already answered it or it carries no scientific consequence — and still show that choice in the proposal so nothing is hidden.

## One source of data: `run.json`

The run's memory lives in `results/<run>/run.json`. Write each confirmed choice to it the moment it is made; re-read it before building the report, before running, and before reporting. **Never** reconstruct a parameter from conversation memory — context is not a safe store.

`run.json` is the *only* data source. The report is built one-way from it — `run.json` → a generic `report.json` (the render input) → `report.html` — and never read back. `report.json` and the HTML are *derived* views, regenerated from `run.json`; they are never edited or treated as a second source. A run is **one computation** (model + method + sizes → one spectrum/dataset) and a list of **figures**, each a single view of it — so several figures from the same data share one run, never copied across files. Representative shape (each figure's `results` block fills in after the run):

```json
{
  "paper":    { "id": "arXiv:2302.04919", "title": "…", "url": "…" },
  "model":    { "name": "…", "H": "H = J_1 \\sum_{\\langle ij\\rangle} \\mathbf{S}_i\\cdot\\mathbf{S}_j", "couplings": { "$J_1$": 1.0 }, "lattice": "…", "boundary": "PBC" },
  "method":   { "family": "ED", "exact": true, "tool": "XDiag", "settings": { "sector": "k=0, Sz=0", "k_states": 1 }, "note": "what the tool is and what its key settings mean, in plain English" },
  "scope":    { "label": "beginner" },
  "estimate": [ { "point": "N=16", "wall": "~30 s", "memory": "~0.2 GB" }, { "point": "N=20", "wall": "~6 min", "memory": "~2 GB" } ],
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

Two stdlib-only, offline steps. First `python3 tools/skills/reproduce-paper/build_report.py <run-dir>` maps `run.json` → a generic `report.json`, laying the reproduction out as **Model / Method / Figures**. Then `/report` renders that into one self-contained `results/<run>/report.html` (`python3 tools/skills/report/render_report.py <run-dir>`). This skill owns the *plan, the data in `run.json`, and that layout* (`build_report.py`); `/report` owns only generic rendering and the LaTeX→MathML conversion. Write math as LaTeX in `run.json` — `model.H` as a display equation, any other string carrying `$…$` inline, moduli and bra-kets as `\left|\langle Z_2|\psi\rangle\right|^2` so the exponent sits on the whole `|…|` — and it flows through to MathML.

Two moments, same file, per figure:

- **Proposal** (before compute) — the plan in plain English: the model; the method (with a one-line plain-English `note` on the tool and its settings — what XDiag is, what `k_states`/`tol` do) and its parameters; scope and where — plus a **cost table** with one row per run point (run point → estimated wall time → memory) and a short note of anything likely to be finicky or custom. Then, for each figure, what it plots, the observable, what's expected, and the paper's target panel (when captured); its result area marked pending.
- **Results** (after compute) — for each figure: our figure beside the paper's original panel — capture that panel as an image (`paper_image`) so the two sit side by side — a small table of the key numbers, an honest verdict (`match`: `yes` / `partly` / `no`, rendered as Reproduced / Partial match / Did not match) with a one-line `why`, the wall time that ran and any changes from the plan, and one rerun line.

## Flow

1. **Brainstorm** each drift-relevant decision above, one at a time, saving each to `run.json` as it is confirmed. When the target figure is pinned, save the paper's panel as an image (`paper_image`) so the report can sit it beside ours.
2. **Estimate carefully.** Use the scaling rules below to fill the cost table — it drives the user's scope and where-to-run choices. Flag finicky or custom parts up front so they're anticipated, but don't over-plan.
3. **Build the proposal** page — `build_report.py`, then render via `/report`; give its path and, on a laptop, offer to open it.
4. **Approve / Change / Discuss** — one question once the proposal is built. *Approve* (recommended) locks the plan and runs; *Change <which>* jumps back to that one choice; *Discuss* opens it up. This is the run's only approval.
5. **Run** the approved plan. The script lands at `scripts/<model>_<brief>.{jl|py}` and saves its figure under `results/<run>/`. Fix ordinary code breakage quietly and rerun; interrupt the user only when a real choice is needed (e.g., the chosen tool genuinely can't express this target).
6. **Append results** — fill each figure's `results` block in `run.json`, re-run `build_report.py`, and re-render via `/report`. Then offer a couple of next steps drawn from the outcome (e.g., a larger scope, another figure from the same data, or stop).

Rendering composes with `/report`; a cluster run composes with `/slurm` (ship / submit / monitor / fetch); installs compose with `/setup-julia`. This skill does not duplicate those.

## Estimating cost

- **ED** — estimate the symmetry-reduced Hilbert dimension `D` first; dense memory ≈ `D² × 8` bytes, dense diagonalization ≈ `O(D³)`; sparse/Lanczos scales with matvec cost × requested states.
- **DMRG / MPS** — wall ~ `sweeps × L × χ³`; memory ~ `L × χ² × 8`. If unsure, the probe below times a few low-`χ` sweeps.
- **QMC** — `cost_per_sample × samples × chains`; the probe times a short batch for the per-sample rate.
- **VMC / NQS** — `steps × samples × model_eval_cost`; the probe times a few steps for the per-step rate.

Exactly one tiny, clearly-labeled timing probe may run before approval, and only to measure a rate (per sweep / sample / step) so the estimate is honest. It yields no scientific result and is discarded. Fill one cost-table row per run point. No other compute before Approve.

## Parameters each method needs

Ask the knobs the chosen method actually uses (skip any already pinned), each as its own crisp choice — each glossed in plain English per the UX rule, and that gloss recorded in `method.note` so the report carries it too.

- **ED** — basis, boundary, symmetry sector, full-spectrum vs selected-state policy, diagonalization mode, tolerance, size list.
- **DMRG / MPS** — bond dimension `χ`, sweeps, cutoff, initialization, boundary, observable, a convergence check.
- **QMC** — thermalization, samples, chains, bins, update type, estimator, target uncertainty.
- **VMC / NQS** — ansatz / model size, optimizer, learning rate, samples, steps, seeds, validation observable.

**ED needs care on symmetry.** Name each symmetry the paper or method uses (momentum `k`, inversion, total `Sz`, particle number, point group, boundary), say why the chosen sector is right, and flag any exact symmetry left unused. State a dense full-spectrum run as "exact within the chosen sector." Never present an approximation — FSA (Forward Scattering Approximation: a small basis built from repeated Hamiltonian applications), a few Krylov states, or a reduced window — as a full-spectrum reproduction; present it as an approximation with its scientific consequence.

## Picking the tool

Read `tools/software/stacks/*.toml` before offering tools. Recommend the paper's official code when it exists and runs; otherwise the method's canonical stack, then its fallback. Each option shows its setup state (ready / needs install / official code unavailable) and a one-line reason. Don't recommend a tool just because it is installed, and don't silently switch tools on an install error — say so and let the user choose.

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
