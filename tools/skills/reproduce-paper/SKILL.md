---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end — plans the multi-fig sequence, surfaces methodology / verification / convergence-diagnostic figs alongside substantive figs, and composes the harness's existing primitives. Generic over papers; not paper-specific.
---

# reproduce-paper

Plan and orchestrate a paper reproduction across multiple figures and main results. Generic over the paper. Composes existing primitives for scans, scaling, cross-checks, verification, and cluster compute. Plans the figure dependency graph, surfaces methodology and verification figures alongside the substantive ones, runs the assembled set as a coherent session, and closes with a consolidated runnable script + structured run report.

## When to activate

- The user types "reproduce paper X", "redo the figures of Y", or "I want to follow paper Z end-to-end".
- A `solve` session is moving through several figures of the same paper and the user signals they want the full set rather than one figure at a time.
- After `download-ref` lands a paper under `knowledge-base/literature/<method>/`, the user wants to put it through the harness as a calibration target.

## Inputs

- A *paper identifier* — arXiv id, DOI, or a path under `knowledge-base/literature/<method>/` to a rendered methodology reference. The skill reads the paper's index card (`INDEX.md`) and figure list.
- A *coverage scope* — full-paper, "main results only", or a user-specified figure subset. Default: full-paper.
- A *budget* - wall-clock or compute envelope. Defaults from the calling workflow / cluster profile.
- An optional *protocol TOML* — an authored or prior generated contract. If absent, create `results/<run>/protocol.toml` from primary-source extraction before compute.

## Minimal scientific spine

Fresh agents should keep the whole run anchored to this spine:

```text
source -> protocol -> executable route -> trusted check -> production run -> evidence close
```

Each stage answers one question:

- **Source**: what did the paper, supplement, or official code/data actually say?
- **Protocol**: what checkable claims and deviations define the requested reproduction?
- **Executable route**: what plan, script, run spec, and stack will generate evidence for those claims?
- **Trusted check**: does the same code path and observable path work where the answer is known?
- **Production run**: are the requested figures generated as fresh `current_run` artifacts?
- **Evidence close**: which claims are supported, partial, failed, or out of scope?

The detailed workflow below expands this spine. If a run becomes confusing, return to the earliest spine stage whose evidence is missing or contradictory.

## Evidence authority

The workflow separates navigation from evidence. Existing repo content may help the agent find a plausible route, but it cannot close a reproduction claim.

Evidence classes:

- `primary` — paper PDF/rendered text, supplement, official code, or official data. Primary sources control paper claims.
- `trusted_reference` — analytic limit, exact small-system calculation, official benchmark, or independent method check chosen before production.
- `current_run` — artifact generated under the current protocol hash and script hash, with matching manifest provenance.
- `hint` — KB cards, rendered notes, old scripts, old plans, old results, old figures, summaries, and prior run reports.
- `assumption` / `deviation` — explicit unsupported or altered setup, visible in the protocol and final report. These can bound a partial reproduction, but cannot silently support a paper-equivalent claim.

Hard rule: a hint can influence what to try, but every gate ignores hints when deciding whether a claim is supported unless the hinted fact has been re-confirmed against a primary source or regenerated as current-run evidence.

## Protocol TOML

The protocol is generic. It records what the paper claims, how each claim is sourced, and what evidence must exist before the harness may call the run a reproduction. `/reproduce-paper` treats claim names, parameter names, method names, and artifact fields as opaque strings. Domain-specific knowledge belongs in the source text, method cards, authored scripts, and command checks. Do not add hardcoded domain oracle types to the protocol; add a generic `command`, `verify`, or manifest check that points at a domain script instead.

The authoring agent may draft the protocol, scripts, and checks, but cannot be the only verifier. Every protocol, important script/check command, aggregator, and final result report needs independent `/verify` or separate-agent review before it can advance the reproduction gate. This is separate from local smoke tests: smoke tests prove the artifact runs; independent review checks whether it is the right artifact.

Required sections:

- `[artifact]` — paper id, scope, run id, and coverage target.
- `[[sources]]` — primary paper, supplement, official code/data, trusted references, and optional hints. Each row carries `id`, `kind`, `path` or `url`, and `authority = "primary" | "trusted_reference" | "hint"`. KB entries, prior scripts, old plans, and old artifacts are always `hint` until re-confirmed or regenerated.
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
- `[budgets]` - wall-clock, grid, compute, data-generation, or approximation budgets expressed as data, not interpreted by this skill unless a check command consumes them.

Claim granularity: make each claim small enough to pass, fail, or be marked partial independently. Bad: "reproduce Fig. 3." Good: "Fig. 3a energy density curve uses this setup and observable", "Fig. 3b gap extrapolation uses these sizes and fit form", "Fig. 3 inset convergence diagnostic supports the reported tolerance." For multi-panel figures, create multiple claims that share sources and artifacts where appropriate.

For `kind = "numeric_compare"`, the generic runner is `tools/cli/harness_validate_numeric.jl`. The check declares artifact selectors and tolerances as data; the runner does not know what the numbers mean. It can run against a standalone validation spec (either a single check object or `{ checks = [...] }`) or a full protocol TOML filtered by `--check-id`. Minimal protocol shape:

```toml
[[checks]]
id = "trusted_reference_compare"
kind = "numeric_compare"
gate = "trusted_check"
runner = "tools/cli/harness_validate_numeric.jl"

  [[checks.compare]]
  name = "small-scale reference"
  actual = { path = "cells/cell-0001/manifest.json", field = "observable" }
  reference = { path = "references/exact.json", field = "observable_exact" }
  uncertainty = { path = "cells/cell-0001/manifest.json", field = "stderr" }
  tolerance = { abs = 0.05, sigma = 5.0, mode = "any" }
```

Selectors may use `field = "nested.key"` for simple JSON/TOML paths or `pointer = "/nested/0/key"` for JSON Pointer. Names like `observable`, `observable_exact`, or `stderr` are example payload fields, not harness-level types.

Check `gate` values use the same flow gates as the run ledger: `source`, `protocol`, `plan`, `script`, `trusted_check`, `production`, `assembly`, or `close`. Do not introduce separate stage names such as `preflight`, `compute`, or `report`; those are ordinary prose, not gate ids.

For manifest assembly, a run spec may include `assembly.manifest_contract` with only generic clauses: `required_fields`, `nonempty_fields`, `equals`, `list_contains`, `numeric_fields`, `optional_numeric_fields`, `numeric_bounds`, and `evidence_sets`. These clauses refer to manifest field paths; they do not introduce domain types. Run-level provenance such as `sources`, `claims`, and `deviations` is declared once in the protocol / run spec and mechanically compared against the manifest payload; do not repeat paper-specific deviation strings as reusable contract logic, and do not add domain-specific oracle types to the reusable contract.

## Run directory contract

Human-authored contracts are TOML; machine-generated cell maps may stay JSON when called primitives already use JSON. Inspired by ColliderAgent's staged run layout, each reproduction keeps a durable progress spine that survives local or remote execution:

```text
results/<run>/
  protocol.toml
  flow.toml
  reproduce-plan.toml
  run_spec.json
  progress/events.jsonl
  progress/state.toml
  scripts/
  cells/<cell_id>/manifest.json
  checks/
  figs/
  verify/
  execution_summary.md
  run-report.md
  consolidated.jl|py
```

For any full-paper, remote, or multi-agent reproduction, initialize the generic gate ledger as the first run-directory action, before source/protocol/plan artifacts are recorded:

```bash
tools/cli/flow init results/<run> --template results/<run>/flow.toml
```

`flow.toml` declares gates and invalidation edges. `progress/events.jsonl` is the append-only state source; `progress/state.toml` is the rebuilt human summary. Record each verifier, worker, local command, or remote job as an `attempt`; record important files as `artifact`s; use `require` before advancing gates. Re-adding an artifact with the same id and a different SHA-256 invalidates the producing gate and downstream gates. Remote jobs never write the event log directly: the main agent records the attempt only after fetching manifests/check outputs.

Default gates are `source`, `protocol`, `plan`, `script`, `trusted_check`, `production`, `assembly`, and `close`. Split a gate only when a separate artifact can fail or be invalidated independently. Use the template in `tools/flow/README.md` as the starting point.

For long sessions, pair the run with a `/goal` condition whose proof is `tools/cli/flow require results/<run> close`. The goal keeps the agent moving; the flow ledger decides whether the scientific run is actually closed. In Codex or Claude Code, the optional Stop hook documented in `tools/flow/README.md` can deterministically continue the session while `tools/cli/flow next results/<run>` has a runnable gate.

`execution_summary.md` is the terse operational summary: what ran, where, what passed, what failed, and which artifacts support the next gate. It is not evidence by itself; it points to manifests, check outputs, and the flow state.

## Artifact-scoped cooperation

Use subagents as artifact-scoped reviewers or workers, not as permanent domain personas. The main agent owns run state and final synthesis; subagents challenge or produce bounded artifacts.

| Assignment | When | Required context | Output |
|---|---|---|---|
| Source verifier | After `protocol.toml` draft | Raw/rendered paper, supplement/code/data when available, protocol | `/verify protocol` report |
| Plan verifier | After `reproduce-plan.toml` and `run_spec.json` | Protocol, plan, run spec, method cards, primary-source passages | `/verify plan` report |
| Script verifier | Before trusted check | Protocol, script/check command, primary methodology source | `/verify script` report |
| Result verifier | After trusted or production result | Protocol, manifests, figures/data, paper values/figures | `/verify result` report |
| Close verifier | Before claiming reproduction | Report, consolidated script, protocol, manifests, verify reports | `/verify close` report |
| Skeptic verifier | On nontrivial mismatch or repeated repair failure | Failed check, expected evidence, protocol, relevant artifacts | `/verify mismatch` report |
| Worker | When implementation or remote execution can proceed independently | Narrow file/run ownership and current protocol | Script, run artifact, or job result |

Verifier context must include primary evidence or exact primary-source excerpts when available. A KB-only verifier repeats the over-trust failure mode and cannot close a scientific gate.

## Correction loop

Gate failures are normal scientific feedback. Do not just "try something else"; classify and repair the earliest wrong layer.

```text
failed gate -> classify mismatch -> locate earliest wrong layer
-> revise that layer -> invalidate downstream artifacts -> rerun affected gates
```

Mismatch classes:

- `source_misread` — protocol or report says something the primary source does not support.
- `unsupported_assumption` — claim relies on a hint, guess, or missing source passage.
- `convention_mismatch` — Hamiltonian sign, normalization, units, boundary condition, sector, or estimator differs.
- `plan_gap` — `reproduce-plan.toml` or `run_spec.json` does not actually cover a protocol claim.
- `script_bug` — implementation, observable path, estimator, aggregation, or plotting logic is wrong.
- `stack_or_remote_failure` — environment, scheduler, package, GPU/CPU profile, or fetch/monitoring failed.
- `stale_or_provenance_gap` — artifact exists but lacks current protocol/script provenance.
- `insufficient_convergence` — controlling knob, sample count, bond dimension, chi, beta, or finite-size range is not enough.
- `statistical_noise` — uncertainty estimate is too large or autocorrelation/repeatability is unresolved.
- `paper_ambiguity` — primary source is genuinely underspecified.
- `out_of_scope` — required data, code, hardware, or method is outside the harness.

Earliest wrong layer and invalidation:

| Revised layer | Invalidate and rerun |
|---|---|
| Primary-source extraction / protocol | Protocol audit, plan audit, script audit, trusted check, production cells, assembly, report, close |
| Trusted-reference choice | Related checks, trusted run, script adequacy judgment, production gate if it depended on that reference |
| `reproduce-plan.toml` / `run_spec.json` | Plan audit, affected scripts/job wrappers, affected cells, assembly, report, close |
| Script / check command / aggregator | Script audit, trusted check, affected production cells or derived figures, result verify, report, close |
| Stack / cluster profile / remote ship path | Stack smoke/bootstrap, affected cells, fetched manifests, assembly, report |
| Raw current-run cells only | Assembly, figures, result verify, report, close; protocol and script audits may stand |
| Figure/report text only | Result or close verify; raw cells may stand |

When the cause is not obvious, or when one repair attempt fails, dispatch a skeptic verifier with `/verify mismatch`. The skeptic classifies the mismatch and invalidation scope; the main agent presents repair / narrow / deviation / stop options to the user.

## Workflow

Steps 1–8 build and validate the complete protocol; steps 9–13 are the pre-compute discipline; steps 14–18 run paper-grade compute and close. The workflow only advances past a gate when every declared check for that gate passes or a deviation is explicitly recorded. In a flow-backed run, record the gate attempt, finish it with `pass|fail|blocked`, and run `require` before advancing. Any material change to the protocol, checks, scripts, aggregators, or final report invalidates downstream gates for that artifact; return to the relevant audit before advancing. Where a step puts a real choice in front of the user, invoke `Superpowers:brainstorming` to present 2–3 options with pros / cons and a recommendation. Other steps run silently with sensible defaults.

**Gate failure handling.** Any failed check kind (`source_audit`, `command`, `manifest_fields`, `manifest_consensus`, `numeric_compare`, `freshness`, or `verify`) stops the workflow. Surface the failing evidence, write or link the check output in the run directory, run the correction loop above, then present 2–3 real options via `Superpowers:brainstorming`: repair the earliest wrong layer, narrow the scope, record a justified deviation/assumption when scientifically honest, or stop. Do not continue to expensive compute, assembly, or final reporting from a failed gate.

1. **Initialize state, then collect and classify sources.** Create `results/<run>/flow.toml` from the default gate template and run `tools/cli/flow init` before recording source artifacts. Locate primary sources first: paper PDF/rendered text, supplement, official code/data when available. Classify every input by evidence authority before using it. KB cards, prior scripts, old plans, old results, and existing figures start as `hint`. If no primary source is available locally, prompt the user to run `download-ref` or provide the source.

2. **Extract the protocol.** From primary sources, extract the claims needed for the requested scope: target result, setup, method, parameters, approximations, uncertainty, and artifact requirements. Create or update `results/<run>/protocol.toml`. If a hint conflicts with a primary source, record the conflict and follow the primary source. If a claim cannot be primary-sourced, mark it as an assumption instead of letting a hint support it.

3. **Categorize each figure.** Tag every figure with one of:
   - **Substantive** - a result the paper is built around.
   - **Methodology** - illustrates how the paper's procedure works.
   - **Verification** - a diagnostic the paper itself ran to justify the result. These are *internal* to the paper's verification chain; reproducing them is also reproducing the paper's *trust*.
   - **Cross-check** - a comparison to an independent route for the same claim.

4. **Plan the figure dependency graph.** Identify which figures share generated artifacts, so the underlying calculation can be reused. Output: `results/<run>/reproduce-plan.toml` with figure ids, their categorizations, the artifact each requires, and the dependency edges. Existing plans may be read as hints, but the current plan must derive its claims and gates from the current protocol.

5. **Plan the orchestration.** For each figure:
   - Pick the applicable domain workflow and method card from the paper's reported setup.
   - Pick the primitive (`/parameter-scan`, `/scaling-fit`, `/cross-method-check`) that runs the calculation.
   - For scans or arrays, write `results/<run>/run_spec.json` using the generic cell contract from `/parameter-scan`: each cell has an opaque `cell_id`, a `params` object, optional `settings`, and shared `provenance`. `/reproduce-paper` does not define domain-specific parameter types; the model/method entrypoint interprets `params`.
   - Manifest assembly validates that each cell echoed the merged run-spec provenance it was supposed to use. Cell-specific provenance overrides are allowed, but they are still data; the reusable layer only checks equality of declared payload fields.
   - For multi-stage method-card pipelines, the per-cell compute script reads its method-card-declared stage list and writes a per-stage manifest into `results/<run>/cells/<cell_id>/<stage>.manifest.json`. Stage-execution is plain shell, not a separate skill; the method card declares what, and the script does it.
   - For embarrassingly-parallel grids on a cluster, `/parameter-scan` composes with `/slurm` (which submits the sbatch array, monitors, fetches). Cluster profile is `tools/cluster/<active>.md`.

6. **Pick trusted references and record them in the protocol.** *Always a fork.* For each substantive figure, identify one point or reduced setting where the same claim has a known-correct or independently checkable answer: analytic limit, independent implementation, official benchmark, or exhaustive calculation on a smaller instance. The reference need not lie on the paper's grid; what matters is that the script's code path reaches it. Invoke `Superpowers:brainstorming` with 2-3 candidate references, then record the chosen reference as claim/check entries in the protocol.

7. **Audit the complete protocol and execution plan with independent verifiers.** First dispatch `/verify --mode protocol` against `results/<run>/protocol.toml` and the declared primary sources. The verifier must be a separate agent from the one that drafted or last materially changed the protocol. It must reject hint-backed claims that are not explicitly marked as assumptions. After protocol pass, dispatch `/verify --mode plan` against `reproduce-plan.toml` and `run_spec.json`; by this point trusted references from Step 6 must already be recorded, so the plan audit can check trusted-reference reachability. On pass, continue. On fail or warning, stop and surface the audit report; user steers whether to correct the protocol/plan, record an assumption, or narrow the scope. If any later step adds or changes claims/checks/deviations/routes, return here before running the affected gate.

8. **Run declared cheap checks.** Execute all cheap `[[checks]]` attached to `source`, `protocol`, `plan`, or `script`. `/reproduce-paper` only dispatches the mechanical check kind; domain-specific logic lives in the referenced command or `/verify` prompt. Do not run expensive production compute until these gates pass.

9. **Surface the methodology / verification / cross-check figs as default deliverables.** This is the discipline that distinguishes paper reproduction from a sequence of isolated runs: the user gets the verification figures *automatically*, not on request. Concretely:
   - Verification figs always run when the paper declares them.
   - Methodology figs are emitted when they are derivable from the harness (schematics may not always be — fall back to citing the paper directly).
   - Cross-check figs run when the harness has the secondary diagnostic available; route via `/cross-method-check`.

10. **Audit the script with an independent verifier.** Dispatch `/verify` in `script` mode against (a) the protocol TOML and (b) the primary methodology source. Include the planned route and run spec when they affect the script. The verifier must be a separate agent from the one that wrote or last materially changed the script/check command. The audit answers whether the script produces evidence for the declared claims, and whether any differences are recorded as deviations. On pass continue silently. On fail or warning, stop and run the correction loop.

11. **Run the script at the trusted reference, compare.** Execute at the chosen reference parameter point — at whatever scale the reference requires (laptop, cluster, anywhere). The trusted point should exercise the same code path, observable path, convention path, and uncertainty path as production, only at easier scale. Dispatch the declared check (`numeric_compare`, `command`, or `/verify result`) against the reference value. On pass continue silently. On fail, stop and run the correction loop.

12. **Data-generation validity check.** When a generated estimate is material to a claim, declare a check that compares the production evidence path against a feasible trusted reference before trusting production-scale uncertainty. The check should exercise the same quantity path, data-generation family, constraints, and uncertainty code used in production, except for scale. Record the reference value, generated value, repeatability or variance diagnostic when available, and the pass/fail tolerance in the protocol. A stable internal error bar is not sufficient evidence if the trusted-reference check fails; stop and repair the method or record a new deviation.

13. **Convergence at one point.** Vary the method's declared controlling setting at one point. Confirm the answer stabilizes using the protocol's declared check. On drift, stop. This is a defense layer against "stable but wrong"; steps 11-12 are the primary catch.

14. **Paper-grade compute with production-gate checks.** Dispatch the full requested run via `/parameter-scan` + `/slurm` or the declared primitive. Inherit the paper's settings by default. Invoke `Superpowers:brainstorming` only if the cluster offers a real budget choice. Remote execution is a cell runner only: `squeue`, ssh exit status, and a completed Slurm job are not evidence until fetched manifests and declared checks pass. Every produced manifest must include `evidence_class = "current_run"`, `protocol_hash`, source artifact paths, script hash or git hash when available, declared claim ids, declared deviation ids, stack/profile identity, the setup payload actually used, and the fields required by the protocol's manifest checks. Each cell/stage runs all `[[checks]]` whose `gate = "production"` before it is marked complete; a failed production gate blocks dependent cells, aggregation, plots, and reports until repaired or explicitly scoped/deviated.

    If any cell overrides shared settings, the assembler must validate the manifest against the merged shared+cell settings and surface a constant/varying settings summary in the result artifact. Do not let a first completed cell define global provenance by accident.

15. **Validate produced artifacts.** Run all `[[checks]]` whose `gate = "assembly"` or `gate = "close"`: freshness, manifest fields, manifest consensus, numeric comparisons, and `/verify result` reports. Reject stale artifacts, old figures, and old data unless their hashes and provenance match the current protocol/script contract. Plots and run reports are blocked until these pass or explicit deviations are recorded.

16. **Assemble the close** (writeup handoff per AGENTS.md, embedded here):
   - Walk the run directory: collect every cell manifest, every primitive's CSV / PNG, every script.
   - Generate `results/<run>/consolidated.{jl,py}`: all parameters explicit, no environment-var defaults, reproducible from a fresh checkout against the harness's installed stack.
   - Generate `results/<run>/run-report.md` with:
     - **Setup** - paper-defined setup payload per figure.
     - **Settings** - method, controlling settings, budgets; cite primary sources first and KB cards only as hints or secondary references.
     - **Result per figure** - final quantity value(s) with uncertainty; one-line interpretation.
     - **Verification status** - trusted-reference / constraint / convergence / independent-check status, plus the `/verify` report references.
     - **Evidence map** - each reported claim maps to protocol claim id, source ids, manifest/check artifact, and verify report.
     - **Protocol status** - path to `protocol.toml`, protocol hash, passed checks, assumptions, deviations, and source/KB conflicts.
     - **Residual uncertainty** - what is *not* settled.
     - **Reproduction** - paths to the consolidated script + run command.
   - For each figure, produce **both** `figs/<id>.png` (the static plot, already required) **and** `figs/<id>.json` (a companion data file consumed by `/report` to render the interactive plot). The JSON schema is paper-agnostic — `(x, y, curves, err)` over any field names — so the report layer hardcodes nothing about observables or axes:

     ```json
     {
       "label": "<id>",
       "axes": {
         "x":      { "field": "<x_field>",      "label": "<x_axis_label>" },
         "y":      { "field": "<y_field>",      "label": "<y_axis_label>" },
         "curves": { "field": "<curve_field>",  "label_template": "<e.g. \"L = {L}\">" },
         "err":    { "field": "<err_field>" }
       },
       "data": [
         { "<x_field>": <value>, "<y_field>": <value>, "<curve_field>": <value>, "<err_field>": <value>, "manifest": "<basename>.json", "wall": <seconds>, "accept": <fraction>, "when": "<YYYY-MM-DD HH:MM>" }
       ]
     }
     ```

     The producing script declares its own axes and pulls the per-row payload from the cell manifests. For 1D scans omit `curves`; for 3D scans wrap multiple JSONs (one per pinned third axis) and reference them as separate figures.
   - Embed the auto-generated plots inline (markdown image links to `results/<run>/figs/*.png`).

17. **Independently review the close.** Dispatch `/verify --mode close` or a separate review agent against the final `run-report.md`, consolidated script, protocol TOML, verification reports, and manifest set. The reviewer must be separate from the agent that assembled the close. This review checks that the report only claims what the protocol and artifacts support, and that assumptions/deviations/gaps are visible. The reproduction is not complete until this review passes.

18. **Surface gaps honestly.** Figures the harness cannot reach (proprietary data, hardware experiments, or topics out of scope) are listed with the gap classification - not silently skipped. The user can then decide to fill the gap manually or accept the partial reproduction.

## Categorization heuristics

The skill uses these heuristics when the paper's `INDEX.md` does not pre-tag the figures:

- *Substantive*: caption states a quantitative or qualitative result that supports the paper's main claims.
- *Methodology*: caption is a "schematic", "diagram", "cartoon", "illustration", or describes the algorithm itself.
- *Verification*: caption describes convergence, stability, sensitivity, repeatability, uncertainty, or any other diagnostic for trust.
- *Cross-check*: caption compares two routes to the same claim.

When ambiguous, ask the user via `AskUserQuestion` with the closest 2–3 categorizations.

## Default deliverables (the discipline)

Per AGENTS.md output norms, reports stay terse — but paper reproduction has a stricter rule because methodology figs *are* the methodology absorption. The default deliverable for a full-paper reproduction is:

| Artifact | Where | When |
|---|---|---|
| One figure per substantive figure in the paper | `results/<run>/figs/fig-<id>.png` | Always. |
| Convergence-diagnostic plot per substantive calculation (the AGENTS.md norm) | `results/<run>/figs/convergence-<calc>.png` | Always. |
| Verification figures the paper ran | `results/<run>/figs/verification-<id>.png` | Always (unless paper does not declare them). |
| Cross-check figures | `results/<run>/figs/cross-<id>.png` | When the secondary diagnostic is in the harness. |
| Methodology figures (schematics) | `results/<run>/figs/method-<id>.png` | When derivable; otherwise paper-citation note. |
| Protocol contract | `results/<run>/protocol.toml` | Always before compute. |
| Figure/run plan | `results/<run>/reproduce-plan.toml` | Always after protocol. |
| Flow state | `results/<run>/flow.toml`, `results/<run>/progress/events.jsonl`, `results/<run>/progress/state.toml` | Always for full-paper, remote, or multi-agent runs; updated after each gate. |
| Per-cell / per-figure manifest | `results/<run>/cells/<cell_id>/manifest.json`, `results/<run>/manifests/fig-<id>.json` | Always. |
| `/verify` reports for protocol / plan / figures / close | `results/<run>/verify/verify_<artifact>_<date>.md` | Always (protocol, plan, script, result, mismatch, and close modes as applicable). |
| Execution summary | `results/<run>/execution_summary.md` | Always; operational summary only, not evidence. |
| Consolidated runnable script | `results/<run>/consolidated.{jl,py}` | Always (Step 16 close). |
| Run report mapping main results → figs → verification status | `results/<run>/run-report.md` | Always (Step 16 close, then Step 17 review). |

## Composition

This skill is *primarily an orchestrator* (with the close embedded in Steps 16–17). Most steps delegate:

- **Domain stages** → applicable workflow + method card.
- **Parameter sweeps** (single- or multi-axis) → `/parameter-scan`.
- **Critical scaling** → `/scaling-fit`.
- **Cross-checks** → `/cross-method-check`.
- **Verification** (protocol / plan / script / result / mismatch / close against primary sources, protocol, artifacts, or trusted reference) → `/verify`.
- **Protocol audit** → `/verify --mode protocol` before compute; this checks source support and generic check coverage.
- **Plan audit** → `/verify --mode plan` after `reproduce-plan.toml` and `run_spec.json`; this checks protocol-to-execution coverage.
- **Mismatch audit** → `/verify --mode mismatch` when the correction layer is unclear.
- **User-facing forks** (trusted-reference pick, cluster budget choice, post-audit redirects) → `Superpowers:brainstorming`. Option presentation lives there, not duplicated in this skill.
- **Multi-stage compute scripts** → method card declares stages; the per-cell compute script walks them and writes per-stage manifests. Plain shell, not a separate skill.
- **Cluster execution** → `/slurm` (called by `/parameter-scan` for grid sweeps; can be called directly for single big runs). Cluster profile from `tools/cluster/<active>.md`.

The orchestrator's value is in the *plan* (the dependency graph + methodology/verification surfacing) and the *close* (consolidated script + run report), not in the per-cell execution. If the user disagrees with the plan, they revise `reproduce-plan.toml` and re-run.

## Resume semantics

- The plan file is durable; re-running the skill on an existing `results/<run>/` reuses figures already produced (manifest-driven, same as `/parameter-scan` and `/slurm`).
- A failed figure is surfaced with its failure mode (transient / logic / OOM / convergence-out-of-budget) and offered for retry. Failed figs are *not* automatically retried.

## Notes

- This skill is *paper-agnostic*: any paper with an `INDEX.md` and recognizable workflow + method coverage can be run through it. It is not specific to any one paper, topic, or diagnostic.
- For papers covering topics out of harness scope, the plan stage surfaces the gap and offers (a) a partial-coverage run, (b) source search for related in-scope work, or (c) cancellation.
- Methodology absorption is the *purpose* of this skill: emitting verification and methodology figs alongside substantive ones is what distinguishes paper reproduction from a chain of isolated runs. A user who asked for the "main result" gets the result plus the verification anchors that earn the result.
- Per AGENTS.md "Writeup handoff", the consolidated script + independently reviewed run report is the close of this skill (Steps 16–17); the user can route to `scientific-writing` / `latex-paper-en` / `scientific-visualization` / `jupyter-notebook` for downstream artifacts.

## Related skills

- `solve` — the single-problem interactive loop. `reproduce-paper` runs *atop* solve when the user wants the full paper rather than one calculation at a time.
- `download-ref` — populates `knowledge-base/literature/<method>/` with the `INDEX.md` this skill consumes.
- `/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/verify`, `/slurm` — the primitives this skill orchestrates.
- `arxiv-search` — for frontier-regime literature framing when the paper is in a contested area.
