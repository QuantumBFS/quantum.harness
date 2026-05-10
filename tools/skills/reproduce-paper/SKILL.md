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
- An optional *protocol TOML* — an authored or prior generated contract. If absent, create `results/<run>/protocol.toml` from primary-source extraction before compute.

## Protocol TOML

The protocol is generic. It records what the paper claims, how each claim is sourced, and what evidence must exist before the harness may call the run a reproduction. `/reproduce-paper` treats claim names as opaque strings; it does not know domain concepts such as Hamiltonians, samplers, lattices, estimators, or symmetries. Domain-specific knowledge belongs in the source text, method cards, authored scripts, and command checks. Do not add hardcoded domain oracle types to the protocol; add a generic `command`, `verify`, or manifest check that points at a domain script instead.

The authoring agent may draft the protocol, scripts, and checks, but cannot be the only verifier. Every protocol, important script/check command, aggregator, and final result report needs independent `/verify` or separate-agent review before it can advance the reproduction gate. This is separate from local smoke tests: smoke tests prove the artifact runs; independent review checks whether it is the right artifact.

Required sections:

- `[artifact]` — paper id, scope, run id, and coverage target.
- `[[sources]]` — primary paper, supplement, official code/data, and optional KB hints. KB entries are hints only per AGENTS.md; primary sources control conflicts.
- `[[claims]]` — paper-derived obligations. Each claim has `id`, `statement`, `sources`, `scope`, and optional `assumption = true` when primary confirmation is unavailable.
- `[[checks]]` — executable or auditable evidence requirements. Built-in `kind` values are mechanical only:
  - `source_audit` — audit claims against declared sources, typically via `/verify --mode protocol`.
  - `command` — run a command that emits pass/fail evidence, preferably JSON.
  - `manifest_fields` — require fields to exist in produced manifests.
  - `manifest_consensus` — require manifests to agree on declared fields.
  - `numeric_compare` — compare declared artifact values against declared references and tolerances.
  - `freshness` — require artifacts to be generated after the protocol/script hash they claim.
  - `verify` — dispatch `/verify` in a declared mode.
- `[[deviations]]` — deliberate differences from the paper method. A deviation is allowed only when it is explicit and has its own checks.
- `[budgets]` — wall-clock, sample, grid, cluster, or approximation budgets expressed as data, not interpreted by this skill unless a check command consumes them.

For `kind = "numeric_compare"`, the generic runner is `tools/cli/harness_validate_numeric.jl`. The check declares artifact selectors and tolerances as data; the runner does not know what the numbers mean. It can run against a standalone validation spec (either a single check object or `{ checks = [...] }`) or a full protocol TOML filtered by `--check-id`. Minimal protocol shape:

```toml
[[checks]]
id = "trusted_reference_compare"
kind = "numeric_compare"
gate = "preflight"
runner = "tools/cli/harness_validate_numeric.jl"

  [[checks.compare]]
  name = "small-scale reference"
  actual = { path = "cells/cell-0001/manifest.json", field = "observable" }
  reference = { path = "references/exact.json", field = "observable_exact" }
  uncertainty = { path = "cells/cell-0001/manifest.json", field = "stderr" }
  tolerance = { abs = 0.05, sigma = 5.0, mode = "any" }
```

Selectors may use `field = "nested.key"` for simple JSON/TOML paths or `pointer = "/nested/0/key"` for JSON Pointer. Names like `observable`, `observable_exact`, or `stderr` are example payload fields, not harness-level types.

## Workflow

Steps 1–8 build and validate the complete protocol; steps 9–13 are the pre-compute discipline; steps 14–18 run paper-grade compute and close. The workflow only advances past a gate when every declared check for that gate passes or a deviation is explicitly recorded. Any material edit to the protocol, checks, scripts, aggregators, or final report invalidates downstream gates for that artifact; return to the relevant audit before advancing. Where a step puts a real choice in front of the user, invoke `Superpowers:brainstorming` to present 2–3 options with pros / cons and a recommendation. Other steps run silently with sensible defaults.

**Gate failure handling.** Any failed check kind (`source_audit`, `command`, `manifest_fields`, `manifest_consensus`, `numeric_compare`, `freshness`, or `verify`) stops the workflow. Surface the failing evidence, write or link the check output in the run directory, then present 2–3 real options via `Superpowers:brainstorming`: repair the artifact/check, narrow the scope, record a justified deviation/assumption when scientifically honest, or stop. Do not continue to expensive compute, assembly, or final reporting from a failed gate.

1. **Collect sources.** Locate primary sources first: paper PDF/rendered text, supplement, official code/data when available. Read KB cards and prior scripts only as hints. If no primary source is available locally, prompt the user to run `download-ref` or provide the source.

2. **Extract the protocol.** From primary sources, extract the claims needed for the requested scope: target result, setup, method, parameters, approximations, uncertainty, and artifact requirements. Write or update `results/<run>/protocol.toml`. If a KB hint conflicts with a primary source, record the conflict in the run notes and follow the primary source.

3. **Categorize each figure.** Tag every figure with one of:
   - **Substantive** — a physics result the paper is built around (e.g., a phase diagram, a critical exponent, an order parameter).
   - **Methodology** — illustrates how the calculation works (e.g., a partition schematic, a sampling-tree diagram, a noise-model cartoon).
   - **Verification** — a convergence diagnostic the paper itself ran (e.g., bond-dim convergence, autocorrelation time, finite-size trend). These are *internal* to the paper's verification chain; reproducing them is also reproducing the paper's *trust*.
   - **Cross-check** — a comparison to a competing diagnostic (e.g., magic vs Binder cumulant, deterministic vs stochastic estimator).

4. **Plan the figure dependency graph.** Identify which figures share generated artifacts, so the underlying calculation can be reused. Output: `results/<run>/reproduce-paper.plan.json` with figure ids, their categorizations, the artifact each requires, and the dependency edges.

5. **Plan the orchestration.** For each figure:
   - Pick the model skill and method card from the paper's reported setup.
   - Pick the primitive (`/parameter-scan`, `/scaling-fit`, `/cross-method-check`) that runs the calculation.
   - For scans or arrays, write `results/<run>/run_spec.json` using the generic cell contract: each cell has an opaque `cell_id`, a `params` object, optional `settings`, and shared `provenance`. `/reproduce-paper` does not define domain-specific parameter types; the model/method entrypoint interprets `params`.
   - For multi-stage method-card pipelines (e.g., `methods/pauli-markov.md` Stages 0–3), the per-cell compute script reads its method-card-declared stage list and writes a per-stage manifest into `results/<run>/cells/<cell_id>/<stage>.manifest.json`. Stage-execution is plain shell, not a separate skill — the method card declares what; the script does it.
   - For embarrassingly-parallel grids on a cluster, `/parameter-scan` composes with `/slurm` (which submits the sbatch array, monitors, fetches). Cluster profile is `tools/cluster/<active>.md`.

6. **Pick trusted references and record them in the protocol.** *Always a fork.* For each substantive figure, identify one parameter point where the same claim has a known-correct or independently checkable answer — analytic limit, independent method, published benchmark, or brute force on a smaller problem. The reference need not lie on the paper's grid; what matters is that the script's code path reaches it. Invoke `Superpowers:brainstorming` with 2–3 candidate references, then record the chosen reference as claim/check entries in the protocol.

7. **Audit the complete protocol with an independent verifier.** Dispatch `/verify --mode protocol` against `results/<run>/protocol.toml` and the declared primary sources. The verifier must be a separate agent from the one that drafted or last materially edited the protocol. On ✓ continue. On ✗ or ⚠ stop and surface the audit report; user steers whether to correct the protocol, record an assumption, or narrow the scope. If any later step adds or changes claims/checks/deviations, return here before running the affected gate.

8. **Run declared preflight checks.** Execute all `[[checks]]` whose `gate = "preflight"` or whose gate is omitted and cheap. `/reproduce-paper` only dispatches the mechanical check kind; domain-specific logic lives in the referenced command or `/verify` prompt. Do not run expensive compute until preflight passes.

9. **Surface the methodology / verification / cross-check figs as default deliverables.** This is the discipline that distinguishes paper reproduction from a sequence of `solve` runs: the user gets the verification figures *automatically*, not on request. Without this, a Pragmatist persona running through the paper sees only the substantive figs and absorbs no methodology judgment. Concretely:
   - Verification figs always run (bond-dim convergence, autocorrelation, finite-size trend).
   - Methodology figs are emitted when they are derivable from the harness (schematics may not always be — fall back to citing the paper directly).
   - Cross-check figs run when the harness has the secondary diagnostic available; route via `/cross-method-check`.

10. **Audit the script with an independent verifier.** Dispatch `/verify` in `script` mode against (a) the protocol TOML and (b) the primary methodology source. The verifier must be a separate agent from the one that wrote or last materially edited the script/check command. The audit answers whether the script produces evidence for the declared claims, and whether any differences are recorded as deviations. On ✓ continue silently. On ✗ or ⚠ stop and surface the audit report; user steers.

11. **Run the script at the trusted reference, compare.** Execute at the chosen reference parameter point — at whatever scale the reference requires (laptop, cluster, anywhere). Dispatch the declared check (`numeric_compare`, `command`, or `/verify result`) against the reference value. On ✓ continue silently. On ✗ stop.

12. **Estimator-validity gate.** For stochastic estimators, compare the estimator itself against a feasible exact or deterministic small-scale reference before trusting any production-scale error bar. The gate must exercise the same observable path, sampling distribution, proposal / sampler family, sector restrictions, and error-estimation code used in production, except for scale. Record the exact value, estimated value, multi-seed scatter or iid variance diagnostic when available, and the pass/fail tolerance in the protocol. A stable block error bar is not sufficient evidence if the exact/deterministic gate fails; stop and repair the estimator or record a new method deviation.

13. **Convergence at one point.** Vary the method's declared controlling knob at one parameter point. Confirm the answer asymptotes using the protocol's declared check. On drift, stop. (Defense layer against "converges to a stable but wrong value with small error bar"; steps 11–12 are the primary catch.)

14. **Paper-grade compute with compute-gate checks.** Dispatch the full requested run via `/parameter-scan` + `/slurm` or the declared primitive. Inherit the paper's settings by default. Invoke `Superpowers:brainstorming` only if the cluster offers a real budget choice. Every produced manifest must include `protocol_hash`, source artifact paths, script hash or git hash when available, declared deviation ids, and the fields required by the protocol's manifest checks. Each cell/stage runs all `[[checks]]` whose `gate = "compute"` before it is marked complete; a failed compute gate blocks dependent cells, aggregation, plots, and reports until repaired or explicitly scoped/deviated.

15. **Validate produced artifacts.** Run all `[[checks]]` whose `gate = "assembly"` or `gate = "report"`: freshness, manifest fields, manifest consensus, numeric comparisons, and `/verify result` reports. Plots and run reports are blocked until these pass or explicit deviations are recorded.

16. **Assemble the close** (writeup handoff per AGENTS.md, embedded here):
   - Walk the run directory: collect every cell manifest, every primitive's CSV / PNG, every script.
   - Generate `results/<run>/consolidated.{jl,py}`: all parameters explicit, no environment-var defaults, reproducible from a fresh checkout against the harness's installed stack.
   - Generate `results/<run>/run-report.md` with:
     - **Setup** — model, lattice, sector, parameters per figure.
     - **Settings** — method, convergence parameters, sample sizes; cite primary sources first and KB cards only as hints or secondary references.
     - **Result per figure** — final observable value(s) with uncertainty; one-line interpretation.
     - **Verification status** — limit / symmetry / convergence / cross-method status, plus the `/verify` report references. Cite `knowledge-base/...` for benchmarks compared against.
     - **Protocol status** — path to `protocol.toml`, protocol hash, passed checks, assumptions, deviations, and source/KB conflicts.
     - **Residual uncertainty** — what is *not* settled (frontier-flag content, convergence at boundary parameters, contested regime).
     - **Reproduction** — paths to the consolidated script + run command.
   - Embed the auto-generated plots inline (markdown image links to `results/<run>/figs/*.png`).

17. **Independently review the close.** Dispatch `/verify --mode close` or a separate review agent against the final `run-report.md`, consolidated script, protocol TOML, verification reports, and manifest set. The reviewer must be separate from the agent that assembled the close. This review checks that the report only claims what the protocol and artifacts support, and that assumptions/deviations/gaps are visible. The reproduction is not complete until this review passes.

18. **Surface gaps honestly.** Figures the harness cannot reach (proprietary data, hardware experiments, models out of scope) are listed with the gap classification — not silently skipped. The user can then decide to fill the gap manually or accept the partial reproduction.

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
| Protocol contract | `results/<run>/protocol.toml` | Always before compute. |
| Per-cell / per-figure manifest | `results/<run>/cells/<cell_id>/manifest.json`, `results/<run>/manifests/fig-<id>.json` | Always. |
| `/verify` reports for protocol / figures / close | `results/<run>/verify_<artifact>_<date>.md` | Always (protocol, script, result, and close modes as applicable). |
| Consolidated runnable script | `results/<run>/consolidated.{jl,py}` | Always (Step 16 close). |
| Run report mapping main results → figs → verification status | `results/<run>/run-report.md` | Always (Step 16 close, then Step 17 review). |

## Composition

This skill is *primarily an orchestrator* (with the close embedded in Steps 16–17). Most steps delegate:

- **Wavefunction stages** → model skill + method card (DMRG / TTN / ED / TEBD / VMC-NQS).
- **Parameter sweeps** (single- or multi-axis) → `/parameter-scan`.
- **Critical scaling** → `/scaling-fit`.
- **Cross-checks** → `/cross-method-check`.
- **Verification** (protocol / script / result / close against primary sources, protocol, artifacts, or trusted reference) → `/verify`.
- **Protocol audit** → `/verify --mode protocol` before compute; this checks source support and generic check coverage.
- **User-facing forks** (trusted-reference pick, cluster budget choice, post-audit redirects) → `Superpowers:brainstorming`. Option presentation lives there, not duplicated in this skill.
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
- Per AGENTS.md "Writeup handoff", the consolidated script + independently reviewed run report is the close of this skill (Steps 16–17); the user can route to `scientific-writing` / `latex-paper-en` / `scientific-visualization` / `jupyter-notebook` for downstream artifacts.

## Related skills

- `solve` — the single-problem interactive loop. `reproduce-paper` runs *atop* solve when the user wants the full paper rather than one calculation at a time.
- `download-ref` — populates `knowledge-base/literature/<method>/` with the `INDEX.md` this skill consumes.
- `/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/verify`, `/slurm` — the primitives this skill orchestrates.
- `arxiv-search` — for frontier-regime literature framing when the paper is in a contested area.
