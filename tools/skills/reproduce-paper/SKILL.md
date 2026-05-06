---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end — plans the multi-fig sequence, surfaces methodology / verification / convergence-diagnostic figs alongside substantive figs, and composes the harness's existing primitives. Generic over papers; not paper-specific.
---

# reproduce-paper

Plan and orchestrate a paper reproduction across multiple figures and main results. Generic over the paper. Composes existing primitives (`/finite-size-scan`, `/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/run-stage`, `/run-report`, and `/slurm-grid` on a cluster). The skill plans the figure dependency graph, surfaces methodology and verification figures alongside the substantive ones, and runs the assembled set as a coherent session rather than as disconnected one-shot calculations.

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
   - Pick the primitive (`/finite-size-scan`, `/parameter-scan`, `/scaling-fit`, `/cross-method-check`) that runs the calculation.
   - For multi-stage method-card pipelines (e.g., `methods/pauli-markov.md` Stages 0–3), schedule the stages via `/run-stage`.
   - For embarrassingly-parallel `(L, parameter)` grids, route through `/slurm-grid` if a cluster profile is active (see `tools/cluster/`).

5. **Surface the methodology / verification / cross-check figs as default deliverables.** This is the discipline that distinguishes paper reproduction from a sequence of `solve` runs: the user gets the verification figures *automatically*, not on request. Without this, a Pragmatist persona running through the paper sees only the substantive figs and absorbs no methodology judgment. Concretely:
   - Verification figs always run (bond-dim convergence, autocorrelation, finite-size trend).
   - Methodology figs are emitted when they are derivable from the harness (schematics may not always be — fall back to citing the paper directly).
   - Cross-check figs run when the harness has the secondary diagnostic available; route via `/cross-method-check`.

6. **Execute.** Walk the plan; each figure is one or more primitive calls. Use `/run-stage` for multi-stage pipelines, `/slurm-grid` for parallelizable grids. Each primitive emits a manifest into the same `results/<run>/` tree.

7. **Assemble.** After execution completes, call `/run-report` to assemble the consolidated artifacts. The report has one section per figure (substantive, methodology, verification, cross-check), plus a top-level summary that maps each main result to its supporting figures and verification anchors.

8. **Surface gaps honestly.** Figures the harness cannot reach (proprietary data, hardware experiments, models out of scope) are listed with the gap classification — not silently skipped. The user can then decide to fill the gap manually or accept the partial reproduction.

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
| Per-figure manifest | `results/<run>/manifests/fig-<id>.json` | Always. |
| Consolidated runnable script | `results/<run>/consolidated.{jl,py}` | Always (via `/run-report`). |
| Run report mapping main results → figs → verification status | `results/<run>/run-report.md` | Always (via `/run-report`). |

## Composition

This skill is *purely an orchestrator*. It does not run any calculation directly; every step is a delegation:

- **Wavefunction stages** → model skill + method card (DMRG / TTN / ED / TEBD / VMC-NQS).
- **Parameter sweeps** → `/parameter-scan` and `/finite-size-scan`.
- **Critical scaling** → `/scaling-fit`.
- **Cross-checks** → `/cross-method-check`.
- **Multi-stage pipelines** → `/run-stage` walks the method card's stages.
- **Cluster execution** → `/slurm-grid` for parallel grids; cluster profile picked from `tools/cluster/<active>.md`.
- **Assembly** → `/run-report` produces the consolidated artifacts.

The orchestrator's value is in the *plan* (the dependency graph and the methodology / verification surfacing), not in the execution. If the user disagrees with the plan, they edit `reproduce-paper.plan.json` and re-run.

## Resume semantics

- The plan file is durable; re-running the skill on an existing `results/<run>/` reuses figures already produced (manifest-driven, same as `/slurm-grid`).
- A failed figure is surfaced with its failure mode (transient / logic / OOM / convergence-out-of-budget) and offered for retry. Failed figs are *not* automatically retried.

## Notes

- This skill is *paper-agnostic*: any paper with an `INDEX.md` and a recognizable model + method coverage can be run through it. It is not magic-paper-specific.
- For papers covering models out of harness scope, the plan stage surfaces the gap and offers (a) a partial-coverage run, (b) escalation to `arxiv-search` for related papers in scope, or (c) cancellation.
- Methodology absorption (the Pragmatist's blind spot) is the *purpose* of this skill — emitting verification and methodology figs alongside substantive ones is what distinguishes paper reproduction from a `solve`-loop chain. A user who asked for the "main result" gets the result *plus* the verification anchors that earn the result.
- Per AGENTS.md "Writeup handoff", `/run-report` is offered after the figure set completes; the user can route to `scientific-writing` / `latex-paper-en` / `scientific-visualization` / `jupyter-notebook` for downstream artifacts.

## Related skills

- `solve` — the single-problem interactive loop. `reproduce-paper` runs *atop* solve when the user wants the full paper rather than one calculation at a time.
- `download-ref` — populates `knowledge-base/literature/<method>/` with the `INDEX.md` this skill consumes.
- `/run-report`, `/run-stage`, `/slurm-grid`, `/finite-size-scan`, `/parameter-scan`, `/scaling-fit`, `/cross-method-check` — the primitives this skill orchestrates.
- `arxiv-search` — for frontier-regime literature framing when the paper is in a contested area.
