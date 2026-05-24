---
name: reproduce-paper-onboard
description: Use when a beginner wants guided paper reproduction, tutorial-style reproduction, size/time help before running, or phrases like "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", or "explain while reproducing".
---

# reproduce-paper-onboard

Beginner-facing paper reproduction with a brainstorm-first surface. The skill iterates a plan with the user one question at a time, writes the agreed plan to `results/<run>/plan.md`, then executes the single approved tier and reports.

This is a forked workflow, not a wrapper around `/reproduce-paper`. If the user later wants evidence-grade certification, hand the produced artifacts to `/reproduce-paper`.

## Pipeline

```text
Brainstorm  ──▶  Plan  ──▶  Execute  ──▶  Report
 (7 Qs)         plan.md     (1 tier)     + next step
```

Each phase has a clear input/output. Brainstorm yields a plan; plan ratification gates Execute; Execute yields manifests and figures; Report consumes those and offers next-step buttons. Failures inside Execute pop back to a brainstorm-style fork (repair / record deviation / stop), not silent fallback.

## Audience Contract

The user may know the physics goal but not harness vocabulary, method scaling, finite-size choices, or cluster tradeoffs. They need information while waiting, not a black box.

Every interaction should answer one of:

- What are we trying to reproduce?
- What exactly does the paper plot?
- What parameters and sizes matter?
- Which computational method, tool/stack, and setup are we using, and why?
- Which symmetry, approximation, and solver settings are being used, and why?
- How long will each size take?
- What will we learn from this run?
- What changed from the paper setup, if anything?

## Core Rule

Before compute, always confirm the exact setup and time estimate with the user by writing `plan.md` and asking them to approve the plan. A tiny import check or `--help` / `--dry` invocation is allowed before approval; nothing more.

The plan summary must include:

- target figure/result;
- method and stack;
- bundled method setup: method introduction, available tools with recommendation, and a setup guide with parameter explanations;
- Hamiltonian or model parameters;
- boundary conditions, sector, filling, lattice/geometry, and observables when relevant;
- selected size tier;
- symmetry choice and approximation choice when relevant;
- solver configuration and the reason it is recommended;
- local vs cluster route;
- expected wall time and memory;
- output files that will be produced.

## 1. Brainstorm (7 questions)

Each question is one `AskUserQuestion` call through the host question tool. Skip any question whose answer is already in the user's opening message. The first option in every list is the recommended one, labeled `(Recommended)`. Every option must be real and executable; the user can pick any without penalty. If the host question tool is unavailable, state that explicitly and do not pretend the choice was ratified.

### Q1 — Target

If the user named both paper and figure in the opener, skip. Otherwise:

> "Which paper and which figure or main result should we reproduce?"

When the paper is known but the figure isn't, list 2–3 candidate figures from the paper, smallest-meaningful first (recommended).

### Q2 — Map check

Inspect primary sources and produce a plain-language reproduction map:

- "The paper plots …"
- "The code must compute …"
- "The important parameters are …"
- "The sizes in the paper are …"
- "The closest beginner run is …"

Then ask:

> "Does this map match what you want to reproduce?"

Options: "Looks right" (Recommended) / "Wrong observable" / "Wrong state-selection". The wrong-* options reopen the map and let the user correct the offending field.

Caption reading is mandatory for figure-producing targets. Record the caption text, axis labels, normalization, state-selection language, sector, window, and excluded nearby states into `protocol.toml` — but explain it to the user as:

> "`plan.md` is the human-readable summary of what we're about to run. `protocol.toml` is the paper-to-code contract the broader harness uses — same content, machine-readable."

### Q3 — Tier (size ladder)

Always offer a size ladder. Use method-card scaling, primary-source sizes, and a tiny pilot when uncertain.

| Tier        | Purpose                                  | Size choice                          | Time estimate              | What the user learns                     |
|-------------|------------------------------------------|--------------------------------------|----------------------------|------------------------------------------|
| Smoke       | Check definitions, imports, plotting path | smallest nontrivial size             | seconds to minutes         | Whether the setup is coherent            |
| Beginner    | See the qualitative trend                 | modest size below paper target       | minutes to tens of minutes | Whether the figure logic works           |
| Paper-like  | Compare against the paper                 | paper sizes or nearest feasible set  | hour-scale, often cluster  | Whether the result reproduces the target |

Scaling rules:

- ED: estimate Hilbert dimension first; dense memory is about `D^2 * 8` bytes and dense diagonalization scales as `O(D^3)`. Sparse/Lanczos depends on matvec cost and number of requested states.
- DMRG / MPS: `sweeps * L * chi^3` wall trend and `L * chi^2 * 8` memory trend; calibrate with a short low-`chi` run when uncertain.
- QMC / Monte Carlo: `cost_per_sample * samples * chains`; use a short pilot to estimate sample rate.
- VMC / NQS: `steps * samples * model_eval_cost`; use a short pilot to estimate step rate.
- Unknown stack: run a tiny pilot only after telling the user it is a timing probe, then update the estimate before the real run.

Ask the tier as one `AskUserQuestion`; each option's description includes the wall-time and memory estimate for that tier.

### Q4 — Computational method / setup introduction

> "Use which computational method setup?"

Before symmetry, approximation, solver, or route selection, walk the user through the computational method setup in this order:

```text
Method introduction -> Available tools -> Setup guide -> AskUserQuestion
```

This is not a lecture; it is the minimum context a beginner needs to understand the recommendation and choose among real setups.

#### Step 1 — Method introduction

First introduce the computational method itself:

- method family (`ED`, `DMRG`, `QMC`, `VMC/NQS`, dynamics, etc.) and what it computes;
- why this method is appropriate for the paper target and selected tier;
- what its main cost driver is (`Hilbert dimension`, `bond dimension`, `samples`, `network size`, etc.);
- what output it will produce for the target figure/result.

#### Step 2 — Available tools

Then introduce the available tool/stack options with a recommendation. Do not use a fixed list. Build the candidate list dynamically from the current target:

- official paper code/data availability from primary sources;
- the method card's canonical and fallback stack guidance;
- stack contracts under `tools/software/stacks/*.toml`;
- installed stack checks and import/dry-run status;
- existing local scaffolds or prior run artifacts for the same paper/figure;
- user-stated method/tool preference;
- feature fit for the target's basis, observable, symmetry, and output needs.

Read `tools/software/stacks/*.toml` before presenting available tools. Select stack candidates by matching the target method against each card's `canonical_for` entries, then keep the relevant card data with the option:

- `stack_card`: path such as `tools/software/stacks/xdiag.toml`;
- stack id/name/language;
- supported profiles and default profile;
- install command and notes;
- smoke test command and where it runs;
- docs / KB links when present.

Official paper code and existing local scaffolds may also be candidates, but they are not software-stack cards. Label them as `official-code` or `local-scaffold/deviation` and still show why they outrank or trail stack-card candidates.

Each option includes:

- tool/stack name discovered for this target;
- stack-card path or explicit non-stack provenance (`official-code`, `local-scaffold/deviation`);
- method family;
- setup state (`ready`, `import-check needed`, `install needed`, `official code unavailable`, etc.);
- install command and smoke test when the option comes from a stack card;
- why it matches or departs from the paper target;
- consequence for later symmetry / solver choices.

Recommendation rules:

- Prefer the paper's official code when it exists, is available, and fits the beginner tier.
- Otherwise prefer the method card's canonical stack as confirmed by its matching stack card, then the method card's fallback stack as confirmed by its matching stack card, then an explicit deviation only when needed.
- If the target requires a constrained basis, observable, symmetry sector, or data route that the canonical stack cannot express cleanly, still present the canonical stack-card option, then present the viable fallback/deviation option. The recommended option may be the deviation only if the reason is concrete and recorded before compute.
- Do not probe or implement a fallback just because the canonical stack has an environment error. First record the canonical stack state, then let the user choose the fallback/deviation option.
- A recommendation must cite the stack-card path or non-stack provenance that supports it, plus the feature-fit reason. Do not recommend a tool solely because it is installed.

For ED, the tool options must distinguish tool/stack from solver/symmetry. Example for a Turner/PXP-like target only; do not reuse as a fixed menu:

| Option | Description |
|---|---|
| `Julia custom constrained ED (Recommended)` | Best for a beginner PXP/Fibonacci constrained-sector run because it already represents the no-adjacent-excitation basis and small sectors transparently; record as a deviation from XDiag. |
| `XDiag canonical ED` | Harness default ED stack; choose if the constrained basis can be represented in XDiag or if the user wants to try canonical-stack implementation first. |
| `QuSpin user_basis` | Python fallback ED stack; useful for cross-checking but requires custom `user_basis` implementation. |

For other papers or methods, replace these with the tools actually discovered for that target. Never present irrelevant tools just because they appear in this example.

#### Step 3 — Setup guide

Then guide the user through the recommended setup. The setup guide includes a compact parameter table. Each row must say what each parameter controls and why it matters:

| Parameter | What it controls | Why it matters | Recommendation |
|---|---|---|---|
| `<name>` | `<plain-language role>` | `<correctness / cost / convergence consequence>` | `<recommended value or rule>` |

The setup guide starts immediately after the tool/stack choice. Do not insert a separate "feasibility path", "route check", or "tool investigation" question between tool choice and parameter setup. Any import check, API limitation, feature gap, or installation status discovered for the chosen tool is reported as setup context and, when relevant, as a parameter-table row such as `tool readiness`, `basis support`, or `stack limitation`.

Parameter confirmation is item-by-item. After presenting the setup table, ask one `AskUserQuestion` per setup parameter, in order. Each question has exactly 2-3 options, the recommended option first, and asks only about the current parameter. Do not bundle multiple setup parameters into a single "approve all" question. The user's answer to one parameter may change the recommendation for later parameters.

For ED, include at least these configurable parameters before the user chooses the setup:

- tool/stack;
- basis representation;
- boundary condition;
- symmetry sector/block policy;
- approximation/full-spectrum policy;
- diagonalization mode;
- residual/check tolerance;
- size list;
- dense-memory/workspace estimate.

For DMRG/MPS, include at least `chi`, sweeps, cutoff, initialization, boundary condition, observable, and convergence comparison.
For QMC, include thermalization, samples, chains, bins, update type, estimator, and uncertainty target.
For VMC/NQS, include ansatz/model size, optimizer, learning rate, samples, steps, seeds, and validation observable.

#### Step 4 — Confirm setup parameters with question tool

After the method introduction, available tools, and setup guide, confirm the setup one item at a time. Use one `AskUserQuestion` per setup parameter, with 2-3 options. The first option is recommended and its description states the reason in one sentence. Every option must be executable or explicitly marked as needing setup before compute.

The user's tool choice is the entry point to setup parameters, not permission to start a new tool-selection loop. If the chosen tool has a feature gap, present the closest executable setup parameters for that tool and explicitly mark the consequence (`faithful`, `fallback`, `deviation`, or `blocked-before-compute`). Only ask the user to switch tools after showing the setup parameter consequences for the chosen tool.

The user must choose or confirm each method setup item before symmetry, approximation, solver, or route selection. Record the bundle in `protocol.toml` as `method_setup`, with nested `method_introduction`, `available_tools`, `setup_guide`, `tool_choice`, `tool_reason`, `parameter_choices`, and `stack_card` or `non_stack_provenance` fields; if the tool is a fallback, deviation, or blocked-before-compute route, record that status before compute. Do not create a separate parameter-introduction question or plan field.

### Q5 — Solver / symmetry configuration

> "Use which solver and symmetry configuration?"

Confirm solver and symmetry configuration one item at a time before asking local vs cluster. Use one `AskUserQuestion` per solver/symmetry parameter, with exactly 2-3 options per question. Ask only about the current item; do not bundle symmetry, approximation, and solver into one prompt. The first option is recommended and its description states the reason in one sentence. Each option includes the consequence for:

- symmetry sector or quantum-number block to use, if the method has one;
- approximation status (`exact within selected sector`, `Lanczos selected states`, `FSA approximation`, `truncated MPS`, `Monte Carlo estimate`, etc.);
- solver family and concrete knobs (`dense full spectrum`, `Lanczos k=...`, `chi/sweeps/cutoff`, `samples/chains/bins`, `steps/samples/seeds`, etc.);
- why it matches or departs from the paper target;
- expected effect on wall time and memory;
- the verification or convergence check it enables.

Recommendation rules:

- **ED, every target**: explicitly discuss the symmetry sector or block before route selection. Name each symmetry used by the paper or method (`k=0`, inversion parity, total `Sz`, particle number, point group, translation, boundary condition, etc.), say why the recommended sector is correct, and identify any exact symmetry that is not used. Confirm each ED item with the user one question at a time before continuing to Route. The minimum ED sequence is: boundary condition if not already confirmed; basis/block representation; translation or momentum sector; inversion/parity sector when applicable; exact symmetry not used as a block; approximation/full-spectrum policy; diagonalization mode; residual/check tolerance; size list and memory estimate if not already confirmed.
- **ED, full-spectrum targets** such as overlap scatter or level statistics: recommend dense full diagonalization when the selected symmetry-sector dimension keeps dense memory and workspace inside the approved tier budget. State the approximation as `exact within the selected symmetry sector`. Use sparse/Lanczos only when the target needs selected eigenpairs. If sparse/Lanczos is used to approximate a full-spectrum paper plot, record it as a deviation before compute.
- **ED, large full-spectrum targets**: recommend cluster/high-memory dense ED when the paper-like size exceeds the local threshold. Do not silently switch to a selected-state solver just because dense ED is expensive.
- **ED, approximate routes**: if using FSA, Krylov selected states, reduced windows, no symmetry reduction, or a smaller symmetry sector than the paper, present it as an approximation/deviation with the scientific consequence. Do not call an approximation a reproduction of a full-spectrum ED panel.
- **DMRG / MPS**: recommend a sweep schedule, maximum bond dimension, cutoff, and at least one convergence comparison appropriate to the tier. Beginner tiers may use lower `chi`; paper-like tiers use the paper/method-card setting or an explicit convergence ladder.
- **QMC / Monte Carlo**: recommend thermalization, samples, chains, binning, and target uncertainty. Smoke tiers may use low statistics, but must be labelled as smoke-quality.
- **VMC / NQS**: recommend optimizer steps, samples per step, model size, seed count, and a validation observable.
- **Unknown stack**: run only a tiny timing/import pilot after telling the user it is a probe, then update this solver estimate before the real plan approval.

For ED, every item-level `AskUserQuestion` must include 2-3 concrete choices and name the current field in user-facing language. Do not ask a combined question that names all fields at once.

| Field | Example |
|---|---|
| Symmetry | `PBC, k = 0, inversion even; particle-hole symmetry checked but not block-diagonalized` |
| Approximation | `Exact dense diagonalization within that sector` |
| Solver | `Dense full spectrum, all eigenvectors, residual check` |

Record the chosen configuration in `protocol.toml` as `symmetry`, `approximation`, `solver_config`, `solver_reason`, and `itemized_confirmations`. Do not leave symmetry, approximation, or solver settings as hidden script defaults.

### Q6 — Route

> "Run locally or on the cluster?"

Recommend local only when the chosen tier and solver configuration are expected to stay under 10 minutes and 16 GB. Otherwise recommend cluster and explain in one sentence (e.g., "dense ED at L = 32 needs ~100 GB workspace, so this belongs on a high-memory Slurm node"). The cluster route composes with `/slurm` for ship / submit / monitor / fetch — this skill does not duplicate cluster idioms.

### Q7 — Approve the plan

Show a compact plan summary and ask:

> "Approve the plan?"

| Field        | Choice |
|--------------|--------|
| Target       | Fig. 3(a), structure factor |
| Method/stack | ED / XDiag |
| Method setup | ED computes exact finite-size spectra; setup parameters include tool/stack, basis, BC, symmetry block, full-spectrum policy, residual tolerance, sizes, and memory estimate |
| Available tools | Julia custom constrained ED, XDiag, QuSpin `user_basis` |
| Tool choice | Julia custom constrained ED |
| Tool reason | XDiag is canonical, but the beginner PXP constrained basis is already represented in the custom Julia scaffold; record as a stack deviation |
| Setup guide | use the ready custom constrained ED scaffold for beginner sizes, with parameters documented in the setup table; optionally cross-check with canonical/fallback stack later |
| Parameters   | `J1 = 1`, `J2/J1 = 0.5`, PBC |
| Tier         | Beginner |
| Sizes        | `L = 12, 16, 20` |
| Symmetry     | PBC, `k = 0`, inversion even |
| Approximation | exact dense diagonalization within the selected sector |
| Solver config | dense full diagonalization in the selected symmetry sector |
| Solver reason | Fig. 3(a) needs all eigenstates; selected-sector dimensions fit the beginner budget |
| Route        | local |
| Estimate     | 8–12 minutes, < 4 GB |
| Outputs      | `plan.md`, `protocol.toml`, manifests, `figs/<id>.png`, `run-report.md` |

Options: "Approve" (Recommended) / "Smaller tier" / "Change params" / "Cancel". A non-approval rewinds to the relevant earlier question — never silently downsize.

## 2. Plan

After Q7 approval, write `results/<run>/plan.md`:

```markdown
# Plan: <paper-short> Fig <id>

**Paper.** <citation, primary-source path>
**Target.** <figure/result, caption excerpt>
**Method/stack.** <e.g., ED / XDiag>
**Method setup.** <method introduction, available tools, setup guide, and parameter table: parameter / controls / why it matters / recommendation>
**Tool choice.** <selected tool / stack>
**Tool reason.** <why this tool is recommended or chosen, including fallback/deviation status>
**Setup guide.** <how to set up the selected tool/stack before compute>
**Parameters.** <J, lattice, BC, sector, …>
**Tier.** <smoke|beginner|paper-like>
**Sizes.** <L = …>
**Symmetry.** <sector / block / unresolved symmetries>
**Approximation.** <exact within selected sector | selected-state approximation | FSA | truncated MPS | Monte Carlo estimate | none>
**Solver configuration.** <dense full ED | Lanczos k=… | DMRG chi/sweeps/cutoff | QMC samples/chains/bins | VMC steps/samples/seeds>
**Solver reason.** <why this config is recommended for the target and tier>
**Route.** <local|cluster>
**Estimate.** <wall, memory>
**Deviations.** <list, or "none">
**Outputs.** protocol.toml, manifests, figs/<id>.png, run-report.md
```

Fill `results/<run>/protocol.toml` from the same brainstorm answers. `plan.md` is the friendly user-facing artifact; `protocol.toml` is the machine-readable paper-to-code contract. Both are required and co-located.

## 3. Execute

Run the approved tier only. The script lands at `scripts/<model>_<brief>.{jl|py}` and writes manifests under `results/<run>/cells/<cell_id>/manifest.json`.

- One status line per cell start (what's running, expected time). Flush stdout.
- For any cell expected to take > 2 minutes, the script emits ~10–50 progress updates. Method cards declare the per-run `progress_every` default.
- Each cell manifest records `method_setup`, `tool_choice`, `tool_reason`, `setup_guide`, `symmetry`, `approximation`, `solver_config`, and `solver_reason`, matching the approved plan. A mismatch is a failed manifest-consistency check.
- Inline checks at each cell: primary-source match (caption, axes, normalization, state selection), limit or known-answer check when available, manifest consistency, freshness.
- On check failure, open a brainstorm-style `AskUserQuestion` with three options:
  1. **Repair** — fix the offending layer and rerun this cell. Recommended when the failure is a clear bug.
  2. **Record a deviation** — keep the cell, write a deviation row in `protocol.toml` and `plan.md`, continue as a learning run.
  3. **Stop** — keep current artifacts, end the session.
- Cluster route composes with `/slurm`; this skill does not inline cluster idioms.

During waits, communicate at meaningful checkpoints: start, after pilot or smoke, during long runs (current cell, elapsed time, expected remaining), after each tier. Do not fill the conversation with raw logs — summarize useful signal and keep log paths available.

## 4. Report

After execute completes, write `results/<run>/run-report.md`:

- beginner summary (one paragraph);
- paper target vs reproduced target;
- approved setup, bundled method setup, tool choice/reason, setup guide, symmetry, approximation, solver configuration/reason, time estimate, actual runtime;
- produced artifacts (paths);
- verification status: `self-checked` / `partial` / `failed` / `upgrade-recommended`;
- exact rerun command.

For a polished, shareable HTML deliverable, route to `/report`:

- `/report <run-dir> --stage plan` previews the plan in HTML before approve.
- `/report <run-dir> --stage append` renders the final HTML after execute, with a "beginner reproduction, self-checked" provenance chip so a reader can tell it is a beginner run.

Then ask one `AskUserQuestion` for the next step. The agent assembles options from the result state:

| Option                                     | When recommended                                              |
|--------------------------------------------|---------------------------------------------------------------|
| Render shareable HTML                      | User wants to share or archive the result                     |
| Try a larger tier                          | Smoke or beginner passed cleanly                              |
| Cross-check with an independent method     | Result sits near a phase boundary or frontier regime          |
| Upgrade to full `/reproduce-paper`         | User wants evidence-grade certification                       |
| Stop here                                  | Always available, never padded                                |

## Artifact Contract

Keep outputs compatible with the main harness so a directory produced here can be picked up by `/reproduce-paper` without manual fixup:

- `results/<run>/plan.md` — friendly human-readable plan.
- `results/<run>/protocol.toml` — paper-to-code contract, deviations, selected cells, figure definitions.
- `results/<run>/cells/<cell_id>/manifest.json` — one manifest per completed run cell.
- `results/<run>/figs/<figure_id>.png` — reproduced figure image.
- `results/<run>/figs/<figure_id>.json` — plotted data and settings.
- `results/<run>/run-report.md` — plain-language summary, commands, verification status, and next choices.

## What Stays From The Harness Contract

- Primary sources control paper claims; `.knowledge/` cards are hints.
- Figure captions and plotted quantities are read verbatim before coding.
- Deviations from paper setup are recorded in both `plan.md` and `protocol.toml` before the affected cell runs.
- Compute artifacts are reusable by the full reproduction workflow.
- Failed checks are explained and repaired (or scoped as deviations) before claiming success.

## What Not To Do

- Do not present `protocol.toml` as the first thing the user must understand.
- Do not start non-trivial compute without writing `plan.md` and getting the user to approve the plan.
- Do not claim paper-grade certification without the full `/reproduce-paper` workflow.
- Do not hide downsizing, fallback methods, missing observables, failed checks, or deviations.
- Do not choose symmetry or solver settings before the user has seen the method introduction and confirmed the computational setup.
- Do not present tool names without explaining, inside the setup guide, what the computational method does, which parameters are configurable, what each parameter controls, why each matters, and the recommended setup.
- Do not hide symmetry, approximation, or solver settings in script defaults; for ED, the user must confirm these before route selection.
- Do not ask the user to decide a size without giving a size ladder, an estimate, and the corresponding cluster-vs-local recommendation.
- Do not chain tiers automatically; run only the approved tier and offer the next step in the report.

## Handoff

When the user wants the full reproduction workflow:

> "We can upgrade this run to the full reproduction workflow using the artifacts already produced."

Then hand off to `/reproduce-paper` with the run directory, target figure, `plan.md`, `protocol.toml`, manifests, figures, and `run-report.md`.
