---
name: reproduce-paper
description: Use when the user wants to reproduce a paper's figure or main result. Triggers include "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", "explain while reproducing", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Beginner-facing paper reproduction. Brainstorm the science with the user one decision at a time, save every choice to `run.json`, build one standalone HTML report (proposal first, results appended), and run only the approved plan.

## UX — top priority, always on

- **Plain English, no jargon.** Translate internal or code-level terms at the question. A paper-specific abbreviation (PXP, FSA, RVB, AKLT, …) gets one plain-English intro the first time it appears in a user-facing message; common families (ED, DMRG, QMC, VMC, NQS) need none.
- **One decision at a time**, Superpowers brainstorming style: 2–3 options, recommended first, each one line, each real and executable or explicitly marked "needs setup." Never bundle two decisions in one prompt.
- **Key points only — never a wall of terminal text.** Every message is a few sentences or one compact table that covers the key points. This holds everywhere: questions, setup, runs, waits — short status lines, never raw log dumps. A single question buried in many words is itself a failure.
- Confirmations are terse: a small table of what's inferred, then a clear choice.

## Expose everything that can drift

Surface **every** choice that could make the reproduction diverge from the paper — never hide one behind a silent default. Low user burden is the job of clarity and brevity *per question*, **not** of asking fewer questions. The drift-relevant decisions:

- which figure or panel;
- model + couplings, lattice, boundary;
- observable + normalization + state selection + symmetry sector;
- method, and whether it is exact or an approximation;
- the parameters that method needs;
- size / scope;
- where it runs.

Skip a question only when the user already answered it or it carries no scientific consequence — and still show that choice in the proposal so nothing is hidden.

## One source of data: `run.json`

The run's memory lives in `results/<run>/run.json`. Write each confirmed choice to it the moment it is made; re-read it before building the report, before running, and before reporting. **Never** reconstruct a parameter from conversation memory — context is not a safe store.

`run.json` is the *only* data source. The HTML report is built one-way from it and is never read back; there is no second copy of the data anywhere. Representative shape (the `results` block fills in after the run):

```json
{
  "paper":    { "id": "arXiv:2302.04919", "title": "…", "url": "…" },
  "figure":   { "id": "Fig 2a", "plots": "<y> vs <x>", "x": "…", "y": "…", "expected": "what we should see and why" },
  "model":    { "name": "…", "H": "…", "couplings": { "J": 1.0 }, "lattice": "…", "boundary": "PBC" },
  "observe":  { "quantity": "…", "normalization": "…", "sector": "k=0, Sz=0", "states": "…" },
  "method":   { "family": "ED", "exact": true, "tool": "XDiag", "settings": { } },
  "scope":    { "label": "beginner", "sizes": [12, 16, 20] },
  "estimate": { "wall": "~6 min", "memory": "~2 GB" },
  "where":    "local",
  "risks":    ["observable not built-in — implement by hand"],
  "results":  { "figure": "figs/fig2a.png", "numbers": {}, "match": "", "why": "", "wall": "", "changes": [], "rerun": "" }
}
```

## The report: one standalone HTML

Built from `run.json` into `results/<run>/report.html` — a single self-contained file, like a PDF: inline CSS, math rendered with KaTeX (styles and fonts inlined), the figure embedded. It opens anywhere with no companion files, no build step, and no server. Visual reference: `docs/ed/ed_review.html` and `docs/ed/ed_interview.html` — match that family, but aim a little more polished.

Two moments, same file:

- **Proposal** (before compute) — the plan laid out in plain English: figure, model, observable, method, parameters, scope, where — plus a **cost table** (size → estimated wall time → memory) and a short note of anything likely to be finicky or custom. Results area marked pending.
- **Results** (after compute) — the figure inline (the paper's panel beside ours when we have it), a small table of the key numbers, an honest "matched / partly / didn't — because…", the settings and wall-time that actually ran, and one rerun line.

## Flow

1. **Brainstorm** each drift-relevant decision above, one at a time, saving each to `run.json` as it is confirmed.
2. **Estimate carefully.** Use the scaling rules below to fill the cost table — it drives the user's scope and where-to-run choices. Flag finicky or custom parts up front so they're anticipated, but don't over-plan.
3. **Build the proposal** HTML from `run.json`; give its path and, on a laptop, offer to open it.
4. **Approve / Change / Discuss** — one question once the proposal is built. *Approve* (recommended) locks the plan and runs; *Change <which>* jumps back to that one choice; *Discuss* opens it up. This is the run's only approval.
5. **Run** the approved plan. The script lands at `scripts/<model>_<brief>.{jl|py}` and saves its figure under `results/<run>/`. Fix ordinary code breakage quietly and rerun; interrupt the user only when a real choice is needed (e.g., the chosen tool genuinely can't express this target).
6. **Append results** to the same HTML and the `results` block of `run.json`. Then offer 2–3 next steps drawn from the outcome (larger scope, cross-check via `/cross-method-check`, or stop).

A cluster run composes with `/slurm` (ship / submit / monitor / fetch); installs compose with `/setup-julia`. This skill does not duplicate those.

## Estimating cost

- **ED** — estimate the symmetry-reduced Hilbert dimension `D` first; dense memory ≈ `D² × 8` bytes, dense diagonalization ≈ `O(D³)`; sparse/Lanczos scales with matvec cost × requested states.
- **DMRG / MPS** — wall ~ `sweeps × L × χ³`; memory ~ `L × χ² × 8`. Calibrate with a short low-`χ` run when unsure.
- **QMC** — `cost_per_sample × samples × chains`; short pilot for the sample rate.
- **VMC / NQS** — `steps × samples × model_eval_cost`; short pilot for the step rate.

A tiny, clearly-labeled timing probe is allowed before approval *only* to make the estimate honest; no other compute before Approve.

## Parameters each method needs

Ask the knobs the chosen method actually uses (skip any already pinned), each as its own crisp choice:

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
- Report the result honestly against the "expected" written at plan time — matched, partly, or didn't, and why.

## Not this

- No compute before Approve, beyond the one labeled timing probe.
- No failure-fork, no auto-review, no walls of terminal text.
- Don't hide downsizing, fallback tools, missing observables, or changes from the paper.
- Don't make the user read internal files to understand the plan — the proposal page is the plain-English surface.
- Don't keep a second copy of the run's data; `run.json` is the single source.
