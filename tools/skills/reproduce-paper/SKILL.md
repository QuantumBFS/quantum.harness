---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end — plans the multi-fig sequence, surfaces methodology / verification / convergence-diagnostic figs alongside substantive figs, and composes the harness's existing primitives. Generic over papers; not paper-specific.
---

# reproduce-paper

Plan and orchestrate a paper reproduction across multiple figures and main results. Generic over the paper. Composes existing primitives (`/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/verify`, and `/slurm` for cluster compute). Plans the figure dependency graph, surfaces methodology and verification figures alongside the substantive ones, runs the assembled set as a coherent session, and closes with a consolidated runnable script + structured run report (the writeup-handoff per AGENTS.md, embedded here rather than delegated).

## When to activate

- The user types "reproduce paper X", "redo the figures of Y", or "I want to follow paper Z end-to-end".
- A `solve` session is moving through several figures of the same paper and the user signals they want the full set rather than one figure at a time.
- After `download-ref` lands a paper under `knowledge-base/literature/<method>/`, the user wants to put it through the harness as a calibration target.

## Inputs

- A *paper identifier* — arXiv id, DOI, or a path under `knowledge-base/literature/<method>/` to a rendered methodology reference. The skill reads the paper's index card (`INDEX.md`) and figure list.
- A *coverage scope* — full-paper, "main results only", or a user-specified figure subset. Default: full-paper.
- A *budget* — wall-clock or compute envelope. Defaults from the model skill / cluster profile.

## Workflow

1. **Parse the paper.** Read `knowledge-base/literature/<method>/<paper>/INDEX.md` (or the rendered markdown) for figure list, model coverage, observable list, and the main-results enumeration. If no `INDEX.md` exists, prompt the user to run `download-ref` first.

2. **Categorize each figure.** Tag every figure with one of:
   - **Substantive** — a physics result the paper is built around (e.g., a phase diagram, a critical exponent, an order parameter).
   - **Methodology** — illustrates how the calculation works (e.g., a partition schematic, a sampling-tree diagram, a noise-model cartoon).
   - **Verification** — a convergence diagnostic the paper itself ran (e.g., bond-dim convergence, autocorrelation time, finite-size trend). These are *internal* to the paper's verification chain; reproducing them is also reproducing the paper's *trust*.
   - **Cross-check** — a comparison to a competing diagnostic (e.g., magic vs Binder cumulant, deterministic vs stochastic estimator).

3. **Plan the figure dependency graph.** Identify which figures share a model + parameter point + wavefunction, so the underlying calculation can be reused. Output: `results/<run>/reproduce-paper.plan.json` with figure ids, their categorizations, the model / observable / parameter point each requires, and the dependency edges (Fig X reuses the wavefunction from Fig Y).

4. **Plan the orchestration.** For each figure:
   - Pick the model skill and method card from the paper's reported setup.
   - Pick the primitive (`/parameter-scan`, `/scaling-fit`, `/cross-method-check`) that runs the calculation.
   - For multi-stage method-card pipelines (e.g., `methods/pauli-markov.md` Stages 0–3), the per-cell compute script reads its method-card-declared stage list and writes a per-stage manifest into `results/<run>/cells/<cell_id>/<stage>.manifest.json`. Stage-execution is plain shell, not a separate skill — the method card declares what; the script does it.
   - For embarrassingly-parallel grids on a cluster, `/parameter-scan` composes with `/slurm` (which submits the sbatch array, monitors, fetches). Cluster profile is `tools/cluster/<active>.md`.

5. **Surface the methodology / verification / cross-check figs as default deliverables.** This is the discipline that distinguishes paper reproduction from a sequence of `solve` runs: the user gets the verification figures *automatically*, not on request. Without this, a Pragmatist persona running through the paper sees only the substantive figs and absorbs no methodology judgment. Concretely:
   - Verification figs always run (bond-dim convergence, autocorrelation, finite-size trend).
   - Methodology figs are emitted when they are derivable from the harness (schematics may not always be — fall back to citing the paper directly).
   - Cross-check figs run when the harness has the secondary diagnostic available; route via `/cross-method-check`.

6. **Execute.** Walk the plan; each figure is one or more primitive calls. `/parameter-scan` for sweeps (single- or multi-axis), `/scaling-fit` for collapses, `/cross-method-check` for verification, `/slurm` underneath for cluster compute. Each cell writes a manifest into `results/<run>/cells/<cell_id>/manifest.json`; each primitive writes its summary table into `results/<run>/`.

7. **/verify the figures.** Before claiming a figure reproduced, dispatch `/verify` in `script` mode (script vs paper methodology) and `result` mode (numbers vs paper-reported values). Catches estimator-class proxies and regime-gaps before they propagate into the writeup.

8. **Assemble the close** (writeup handoff per AGENTS.md, embedded here):
   - Walk the run directory: collect every cell manifest, every primitive's CSV / PNG, every script.
   - Generate `results/<run>/consolidated.{jl,py}`: all parameters explicit, no environment-var defaults, reproducible from a fresh checkout against the harness's installed stack.
   - Generate `results/<run>/run-report.md` with:
     - **Setup** — model, lattice, sector, parameters per figure.
     - **Settings** — method, convergence parameters, sample sizes; cite `knowledge-base/methods/<name>.md`.
     - **Result per figure** — final observable value(s) with uncertainty; one-line interpretation.
     - **Verification status** — limit / symmetry / convergence / cross-method status, plus the `/verify` report references. Cite `knowledge-base/...` for benchmarks compared against.
     - **Residual uncertainty** — what is *not* settled (frontier-flag content, convergence at boundary parameters, contested regime).
     - **Reproduction** — paths to the consolidated script + run command.
   - Embed the auto-generated plots inline (markdown image links to `results/<run>/figs/*.png`).

9. **Surface gaps honestly.** Figures the harness cannot reach (proprietary data, hardware experiments, models out of scope) are listed with the gap classification — not silently skipped. The user can then decide to fill the gap manually or accept the partial reproduction.

## Categorization heuristics

The skill uses these heuristics when the paper's `INDEX.md` does not pre-tag the figures:

- *Substantive*: caption mentions a phase, a transition, an exponent, an order parameter, a phase diagram, or a quantitative claim.
- *Methodology*: caption is a "schematic", "diagram", "cartoon", "illustration", or describes the algorithm itself.
- *Verification*: caption mentions "convergence", "vs `χ`", "vs `N_S`", "autocorrelation", "finite-size", "Trotter", or any numerical-stability diagnostic.
- *Cross-check*: caption compares two methods (DMRG vs ED, magic vs Binder, exact vs sampled, etc.) on the same problem.

When ambiguous, ask the user via `AskUserQuestion` with the closest 2–3 categorizations.

## Default deliverables (the discipline)

Per AGENTS.md output norms, reports stay terse — but paper reproduction has a stricter rule because methodology figs *are* the methodology absorption. The default deliverable for a full-paper reproduction is:

| Artifact | Where | When |
|---|---|---|
| One figure per substantive figure in the paper | `results/<run>/figs/fig-<id>.png` | Always. |
| Convergence-diagnostic plot per substantive calculation (the AGENTS.md norm) | `results/<run>/figs/convergence-<calc>.png` | Always. |
| Verification figures the paper ran | `results/<run>/figs/verification-<id>.png` | Always (unless paper does not declare them). |
| Cross-check figures (e.g., magic-vs-Binder) | `results/<run>/figs/cross-<id>.png` | When the secondary diagnostic is in the harness. |
| Methodology figures (schematics) | `results/<run>/figs/method-<id>.png` | When derivable; otherwise paper-citation note. |
| Per-cell / per-figure manifest | `results/<run>/cells/<cell_id>/manifest.json`, `results/<run>/manifests/fig-<id>.json` | Always. |
| `/verify` reports per figure | `results/<run>/verify_<figure>_<date>.md` | Always (script mode + result mode). |
| Consolidated runnable script | `results/<run>/consolidated.{jl,py}` | Always (Step 8 close). |
| Run report mapping main results → figs → verification status | `results/<run>/run-report.md` | Always (Step 8 close). |

## Composition

This skill is *primarily an orchestrator* (with the close embedded in Step 8). Most steps delegate:

- **Wavefunction stages** → model skill + method card (DMRG / TTN / ED / TEBD / VMC-NQS).
- **Parameter sweeps** (single- or multi-axis) → `/parameter-scan`.
- **Critical scaling** → `/scaling-fit`.
- **Cross-checks** → `/cross-method-check`.
- **Verification** (script / result against paper) → `/verify`.
- **Multi-stage compute scripts** → method card declares stages; the per-cell compute script walks them and writes per-stage manifests. Plain shell, not a separate skill.
- **Cluster execution** → `/slurm` (called by `/parameter-scan` for grid sweeps; can be called directly for single big runs). Cluster profile from `tools/cluster/<active>.md`.

The orchestrator's value is in the *plan* (the dependency graph + methodology/verification surfacing) and the *close* (consolidated script + run report), not in the per-cell execution. If the user disagrees with the plan, they edit `reproduce-paper.plan.json` and re-run.

## Resume semantics

- The plan file is durable; re-running the skill on an existing `results/<run>/` reuses figures already produced (manifest-driven, same as `/parameter-scan` and `/slurm`).
- A failed figure is surfaced with its failure mode (transient / logic / OOM / convergence-out-of-budget) and offered for retry. Failed figs are *not* automatically retried.

## Notes

- This skill is *paper-agnostic*: any paper with an `INDEX.md` and a recognizable model + method coverage can be run through it. It is not magic-paper-specific.
- For papers covering models out of harness scope, the plan stage surfaces the gap and offers (a) a partial-coverage run, (b) escalation to `arxiv-search` for related papers in scope, or (c) cancellation.
- Methodology absorption (the Pragmatist's blind spot) is the *purpose* of this skill — emitting verification and methodology figs alongside substantive ones is what distinguishes paper reproduction from a `solve`-loop chain. A user who asked for the "main result" gets the result *plus* the verification anchors that earn the result.
- Per AGENTS.md "Writeup handoff", the consolidated script + run report is the close of this skill (Step 8); the user can route to `scientific-writing` / `latex-paper-en` / `scientific-visualization` / `jupyter-notebook` for downstream artifacts.

## Related skills

- `solve` — the single-problem interactive loop. `reproduce-paper` runs *atop* solve when the user wants the full paper rather than one calculation at a time.
- `download-ref` — populates `knowledge-base/literature/<method>/` with the `INDEX.md` this skill consumes.
- `/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/verify`, `/slurm` — the primitives this skill orchestrates.
- `arxiv-search` — for frontier-regime literature framing when the paper is in a contested area.
