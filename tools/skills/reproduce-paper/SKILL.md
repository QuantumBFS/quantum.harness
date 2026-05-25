---
name: reproduce-paper
description: Use when the user wants to reproduce a paper's figure or main result. Triggers include "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", "explain while reproducing", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Beginner-facing paper reproduction with a brainstorm-first surface. The skill iterates a plan with the user one question at a time, writes the agreed plan to `results/<run>/plan.md`, then executes the single approved tier and reports.

## Pipeline

```text
Brainstorm  ──▶  Plan  ──▶  Execute  ──▶  Report
 (questions)    plan.md     (1 tier)     + next step
```

Brainstorm yields a plan; plan approval gates Execute; Execute yields manifests and figures; Report consumes those and offers next-step options. Failures inside Execute pop back to a brainstorm-style fork (repair / record deviation / stop), not silent fallback.

## Audience Contract

The user may know the physics goal but not harness vocabulary, method scaling, finite-size choices, or cluster trade-offs. They need information while waiting, not a black box.

Every interaction should answer one of:

- What are we trying to reproduce?
- What exactly does the paper plot?
- What parameters and sizes matter?
- Which computational method, tool, and setup are we using, and why?
- Which symmetry, approximation, and solver settings are being used, and why?
- How long will each size take?
- What will we learn from this run?
- What changed from the paper setup, if anything?

## Principles

1. **One workflow.** The skill is a conversational front end to paper reproduction.
2. **Every decision point is asked.** Decisions the user could meaningfully shape are surfaced via Q&A, never hidden in script defaults. If the host question tool is unavailable, state that explicitly and do not pretend the choice was ratified.
3. **One question at a time.** Never bundle multiple decisions in one prompt. If a topic needs multiple decisions, split it.
4. **Plain English. No jargon.** Never expose harness vocabulary (`cell`, `manifest`, `route`, `deviation`, `trust point`) to the user. Translate to plain language at the question; keep structured form in artifacts.
5. **Paper-specific abbreviations get a one-sentence introduction on first use.** When the paper uses a non-standard abbreviation for a model, method, or quantity (PXP, FSA, RVB, AKLT, …), introduce it once with a one-sentence plain-English explanation when it first appears in a user-facing message.
6. **Terse messages. Cover key points, never overload.** Each message summarizes in a few sentences or a compact table.
7. **Skip any question whose answer is already known.** Check the user's opening message, primary sources, and `protocol.toml` before each question; skip those already answered. Never ask the same thing twice.
8. **Confirmation phases use two options: proceed / fix.** A table of inferred facts is shown; the user accepts the whole table or branches into a follow-up to correct one row.
9. **Selection phases use Superpowers brainstorming style.** 2–3 options, recommended option first, each with a one-sentence reason. Every option must be real and executable, or explicitly marked as needing setup before compute; the user can pick any without penalty. A free-text alternative is available when "Other" is needed.

## Core Rule

Before compute, always confirm the exact setup and time estimate with the user by writing `plan.md` and asking them to approve the plan. A tiny import check or `--help` / `--dry` invocation is allowed before approval; nothing more.

The plan summary must include:

- target figure/result;
- method and tool;
- bundled method setup: method introduction, available tools with recommendation, and a setup guide with parameter explanations;
- Hamiltonian or model parameters;
- boundary conditions, sector, filling, lattice/geometry, and observables when relevant;
- selected size tier;
- symmetry choice and approximation choice when relevant;
- solver configuration and the reason it is recommended;
- local vs cluster route;
- expected wall time and memory;
- output files that will be produced.

## Phases

The skill marches the user through a fixed sequence of phases. Each phase is one or more questions; each question is skipped if its answer is already known. The phases are: Identify → Reproduction map → Scope → Method+Tool → Settings → Where → Approve. An eighth phase fires only on a check failure during Execute.

### Phase 1 — Identify

Two questions. Each is skipped if its answer is already in the user's opening message or in a `protocol.toml` from a prior run.

**1.1 Paper.** Free-text.

> Which paper?

**1.2 Target.** Selection style. List candidate figures or quoted results from the paper, smallest-meaningful first as recommended.

> **Which figure or result from this paper?**
>
> - **<smallest meaningful figure> (recommended)** — <one-line description>
> - **<medium figure>** — <one-line description>
> - **<larger figure>** — <one-line description>

### Phase 2 — Reproduction map

Confirmation style. One question, table format. Inspect the primary source and produce a plain-language reproduction map covering what the paper plots, what the code must compute, the important parameters, the paper sizes, and the closest beginner pilot.

> **Reproduction map**
>
> From the paper I read it as:
>
> | Item                   | Reading                                                                                            |
> | ---------------------- | -------------------------------------------------------------------------------------------------- |
> | Paper plots            | <y-axis quantity> vs <x-axis variable>                                                              |
> | Code must compute      | <observable; on which state(s); with which selection rule; normalization; excluded nearby states>   |
> | Important parameters   | <Hamiltonian (name + operator gist); couplings; lattice; boundary>                                  |
> | Sizes in the paper     | <L list, or the paper-side size range>                                                              |
> | Closest beginner pilot | <approachable subset, e.g. smallest size that still captures the figure>                            |
>
> - **Looks right** (recommended)
> - **Fix something** — follow-up picks the row, then asks for the corrected value

Caption text, axis labels, normalization, state-selection language, sector, window, excluded nearby states, Hamiltonian, couplings, lattice, and boundary are recorded verbatim into `protocol.toml` after confirmation. Any paper-specific abbreviation appearing in the map is introduced with one sentence below the table on first use.

### Phase 3 — Scope

Selection style. Three options, each with size choice, wall-time and memory estimate computed from the paper's presumed method using the scaling rules below.

> **How deep should this run go?**
>
> - **Quick check (recommended start)** — smallest nontrivial size; seconds–minutes; confirms the setup runs.
> - **Beginner** — modest size below the paper target; minutes–tens of minutes; shows the qualitative trend.
> - **Paper-like** — paper sizes or the nearest feasible set; hour-scale, often cluster; reproduces the target.

Scaling rules used to compute the per-option estimates:

- **ED**: estimate Hilbert dimension first; dense memory is about `D^2 * 8` bytes and dense diagonalization scales as `O(D^3)`. Sparse/Lanczos depends on matvec cost and number of requested states.
- **DMRG / MPS**: wall trend ~ `sweeps * L * chi^3`; memory trend ~ `L * chi^2 * 8`. Calibrate with a short low-`chi` run when uncertain.
- **QMC**: `cost_per_sample * samples * chains`. Use a short pilot to estimate sample rate.
- **VMC / NQS**: `steps * samples * model_eval_cost`. Use a short pilot to estimate step rate.
- **Unknown stack**: run a tiny pilot only after telling the user it is a timing probe, then update the estimate before the real run.

### Phase 4 — Method and tool

#### 4.1 Method introduction + selection

Before asking which method to use, present a short method introduction:

- the method family (`ED`, `DMRG`, `QMC`, `VMC/NQS`, dynamics, etc.) and what it computes;
- why this method is appropriate for the paper target and selected scope;
- what its main cost driver is (`Hilbert dimension`, `bond dimension`, `samples`, `network size`, etc.);
- what output it will produce for the target.

Then ask, selection style:

> **Which method?**
>
> For <target>, I recommend <method> — <one-sentence reason citing what the target needs>.
>
> - **<recommended method> (recommended)** — <one-sentence reason>
> - **<alternative 1>** — <one-sentence reason; if paper-specific, include one-sentence intro for the abbreviation>
> - **<alternative 2>** — <one-sentence reason>

#### 4.2 Tool selection

Selection style. Build the candidate list dynamically from the current target. Read `tools/software/stacks/*.toml` before presenting, and consider:

- the paper's official code/data availability from primary sources;
- the method card's canonical and fallback stack guidance;
- installed-stack import/dry-run status;
- existing local scaffolds or prior run artifacts for the same paper/figure;
- user-stated method/tool preference;
- feature fit for the target's basis, observable, symmetry, and output needs.

Select stack candidates by matching the target method against each card's `canonical_for` entries. Each option includes:

- tool/stack name (user-facing label);
- stack-card path (e.g., `tools/software/stacks/xdiag.toml`) or explicit non-stack provenance (`official-code`, `local-scaffold/deviation`);
- stack id and language (from the stack card);
- supported profiles and default profile (from the stack card);
- setup state (`ready`, `import-check needed`, `install needed`, `official code unavailable`, etc.);
- install command and notes;
- smoke test command and where it runs;
- docs / KB links when present;
- why it matches or departs from the paper target;
- consequence for later symmetry / solver choices.

Recommendation rules:

- Prefer the paper's official code when it exists, is available, and fits the chosen scope.
- Otherwise prefer the method card's canonical stack as confirmed by its matching stack card, then the method card's fallback stack as confirmed by its matching stack card, then an explicit deviation only when needed.
- If the target requires a constrained basis, observable, sector, or data route that the canonical stack cannot express cleanly, still present the canonical stack-card option, then present the viable fallback/deviation. The recommended option may be the deviation only if the reason is concrete and recorded before compute.
- Do not probe or implement a fallback just because the canonical stack has an environment error. Record the canonical stack state first, then let the user choose the fallback/deviation option.
- A recommendation must cite the stack-card path or non-stack provenance, plus the feature-fit reason. Do not recommend a tool solely because it is installed.

> **Which tool for <method>?**
>
> - **<recommended tool> (recommended)** — <stack-card path or provenance>; <one-sentence reason>
> - **<alternative tool>** — <provenance>; <one-sentence reason>
> - **<alternative tool>** — <provenance>; <one-sentence reason>

### Phase 5 — Settings

Setup parameter questions start immediately after the tool/stack choice in Phase 4.2. Do not insert a separate "feasibility path", "route check", or "tool investigation" question between tool choice and parameter setup. Any import check, API limitation, feature gap, or installation status discovered for the chosen tool is reported as setup context and, when relevant, as a parameter-table row such as `tool readiness`, `basis support`, or `stack limitation`.

The user's tool choice is the entry point to setup parameters, not permission to start a new tool-selection loop. If the chosen tool has a feature gap, present the closest executable setup parameters for that tool and explicitly mark the consequence (`faithful`, `fallback`, `deviation`, or `blocked-before-compute`). Only ask the user to switch tools after showing the setup parameter consequences for the chosen tool.

Selection style. One question per method-specific setting, in a fixed order per method. Each setting is preceded by a compact parameter table:

| Parameter | What it controls          | Why it matters                                | Recommendation                |
| --------- | ------------------------- | --------------------------------------------- | ----------------------------- |
| `<name>`  | `<plain-language role>`   | `<correctness / cost / convergence consequence>` | `<recommended value or rule>` |

Each setup question uses exactly 2–3 options. Every option must carry, in plain English, the consequences a beginner would weigh:

- **value or configuration** — e.g., `exact within selected sector`, `Lanczos k=...`, `chi=200, sweeps=8, cutoff=1e-9`, `samples=10^6, chains=8`;
- **paper-fit** — matches the paper target, or departs and why;
- **feasibility** — does it actually run on the chosen route and budget (`fits in workspace`, `needs cluster`, `marginal at L=20`, `blocked-before-compute`);
- **cost** — wall-time and memory estimate (`~30 s, < 1 GB`, `~2 h, ~80 GB`);
- **accuracy or quality** — expected precision against the paper target (`exact`, `~4-digit residual`, `~2% Monte Carlo error`, `truncation 1e-9`);
- **verification** — convergence or correctness check enabled (`residual check`, `convergence ladder`, `bin-error estimate`).

Then ask:

> **<Setting> — use <recommended value>?**
>
> - **<recommended value> (recommended)** — <config>; <paper-fit>; <feasibility>; ~<wall>, ~<memory>; <accuracy>; <verification>
> - **<alternative 1>** — <config>; <paper-fit>; <feasibility>; ~<wall>, ~<memory>; <accuracy>; <verification>
> - **<alternative 2>** — <config>; <paper-fit>; <feasibility>; ~<wall>, ~<memory>; <accuracy>; <verification>

The user's answer to one setting may change the recommendation for later settings; re-derive each recommendation from the current state before asking the next question.

Setting ladders per method:

- **ED**: basis representation, boundary condition, symmetry sector / block policy, approximation / full-spectrum policy, diagonalization mode, residual / check tolerance, size list, dense-memory / workspace estimate.
- **DMRG / MPS**: maximum bond dimension `chi`, sweeps, cutoff, initialization, boundary condition, observable, convergence comparison.
- **QMC**: thermalization, samples, chains, bins, update type, estimator, uncertainty target.
- **VMC / NQS**: ansatz / model size, optimizer, learning rate, samples, steps, seeds, validation observable.

Settings already pinned in `protocol.toml` are skipped.

For ED, the discipline is stricter: explicitly discuss the symmetry sector before route selection. Name each symmetry used by the paper or method (`k=0`, inversion parity, total `Sz`, particle number, point group, translation, boundary condition, etc.), say why the recommended sector is correct, and identify any exact symmetry that is not used. Confirm each ED item with the user one question at a time before continuing.

Recommendation rules per method:

- **ED, full-spectrum targets** (overlap scatter, level statistics): recommend dense full diagonalization when the selected symmetry-sector dimension fits the approved scope budget. State the approximation as "exact within the selected symmetry sector." Use sparse/Lanczos only when the target needs selected eigenpairs.
- **ED, large full-spectrum targets**: recommend cluster/high-memory dense ED when the paper-like size exceeds the local threshold. Do not silently switch to a selected-state solver just because dense ED is expensive.
- **ED, approximate routes** (FSA = Forward Scattering Approximation, an approximate method that builds a small basis from successive Hamiltonian applications; Krylov selected states; reduced windows): present as an approximation/deviation with the scientific consequence. Do not call an approximation a reproduction of a full-spectrum ED panel.
- **DMRG / MPS**: recommend a sweep schedule, maximum bond dimension, cutoff, and at least one convergence comparison appropriate to the scope.
- **QMC**: recommend thermalization, samples, chains, binning, and target uncertainty. Quick-check scope may use low statistics, but the result must be labelled as quick-check quality.
- **VMC / NQS**: recommend optimizer steps, samples per step, model size, seed count, and a validation observable.

Record chosen settings in `protocol.toml` under `method_setup`, with nested `method_introduction`, `available_tools`, `setup_guide`, `tool_choice`, `tool_reason`, `parameter_choices`, and `stack_card` (or `non_stack_provenance`).

### Phase 6 — Where to run

Selection style. Two options.

> **Run here or on the cluster?**
>
> - **<recommended route> (recommended)** — <one-sentence reason citing wall/memory estimate>
> - **<alternative>** — <one-sentence reason>

Recommend local only when the chosen scope and setup are expected to stay under 10 minutes and 16 GB. Otherwise recommend cluster. The cluster route composes with `/slurm` for ship / submit / monitor / fetch — this skill does not duplicate cluster idioms.

### Phase 7 — Approve

Confirmation style. Compact plan table.

> **Plan**
>
> | Field          | Value                                                  |
> | -------------- | ------------------------------------------------------ |
> | Paper / target | <citation, figure id>                                  |
> | Method / tool  | <method>, <tool>                                       |
> | Model          | <H, params, lattice, BC, L list>                       |
> | Sector         | <symmetry choice>                                      |
> | Solver         | <approximation + solver configuration>                 |
> | Scope          | <quick check / beginner / paper-like>                  |
> | Where          | <this machine / cluster>, ~<wall>, ~<memory>           |
> | Outputs        | a written plan, the computed data, the figure, and a short report |
>
> - **Approve** (recommended)
> - **Change something** — follow-up picks which row to change, jumps back to that phase
> - **Cancel**

A non-approval rewinds to the relevant earlier phase — never silently downsize.

## Plan Artifacts

After Phase 7 approval, write `results/<run>/plan.md`:

```markdown
# Plan: <paper-short> Fig <id>

**Paper.** <citation, primary-source path>
**Target.** <figure/result, caption excerpt>
**Method/tool.** <e.g., ED / XDiag>
**Method setup.** <method introduction, available tools, setup guide, and parameter table: parameter / controls / why it matters / recommendation>
**Tool choice.** <selected tool>
**Tool reason.** <why this tool is recommended or chosen, including fallback/deviation status>
**Setup guide.** <how to set up the selected tool before compute>
**Parameters.** <J, lattice, BC, sector, …>
**Tier.** <quick-check | beginner | paper-like>
**Sizes.** <L = …>
**Symmetry.** <sector / block / unresolved symmetries>
**Approximation.** <exact within selected sector | selected-state approximation | …>
**Solver configuration.** <dense full ED | Lanczos k=… | DMRG chi/sweeps/cutoff | …>
**Solver reason.** <why this config is recommended for the target and scope>
**Route.** <local | cluster>
**Estimate.** <wall, memory>
**Deviations.** <list, or "none">
**Outputs.** protocol.toml, manifests, figs/<id>.png, run-report.md
```

Fill `results/<run>/protocol.toml` from the same brainstorm answers. `plan.md` is the friendly user-facing artifact; `protocol.toml` is the machine-readable paper-to-code contract. Both are required and co-located.

## Execute

Run the approved tier only. The script lands at `scripts/<model>_<brief>.{jl|py}` and writes manifests under `results/<run>/cells/<cell_id>/manifest.json`.

- One status line per cell start, in plain English (what's running, expected time). Flush stdout.
- For any cell expected to take > 2 minutes, the script emits ~10–50 progress updates. Method cards declare the per-run `progress_every` default.
- Each cell manifest records `method_setup`, `tool_choice`, `tool_reason`, `setup_guide`, `symmetry`, `approximation`, `solver_config`, and `solver_reason` for transparency in `run-report.md`.
- Inline checks at each cell, only when scientifically meaningful: primary-source match (caption, axes, normalization, state selection) and limit or known-answer check when available. A failure opens Phase 8 (user decides repair / record deviation / stop). Manifest-bookkeeping checks are not enforced.
- Cluster route composes with `/slurm`; this skill does not inline cluster idioms.

### Phase 8 — On check failure

Selection style; fires only when a check fails during Execute.

> **Check failed.**
>
> <one-sentence: what failed and why it matters>
>
> - **Repair** (recommended when the failure is a clear bug) — fix the offending layer and rerun this cell.
> - **Record as a change from the paper and continue** — keep the cell, write a deviation row in `protocol.toml` and `plan.md`, continue as a learning run.
> - **Stop** — keep current artifacts, end the session.

During waits, communicate at meaningful checkpoints: start, after pilot or quick check, during long runs (current cell, elapsed time, expected remaining), after each scope. Do not fill the conversation with raw logs — summarize useful signal and keep log paths available.

## Report

After Execute completes, write `results/<run>/run-report.md`:

- beginner summary (one paragraph);
- paper target vs reproduced target;
- approved setup, bundled method setup, tool choice/reason, setup guide, symmetry, approximation, solver configuration/reason, time estimate, actual runtime;
- produced artifacts (paths);
- verification status: `self-checked` / `partial` / `failed`;
- exact rerun command.

For a polished, shareable HTML deliverable, route to `/report`:

- `/report <run-dir> --stage plan` previews the plan in HTML before approve.
- `/report <run-dir> --stage append` renders the final HTML after execute, with a "beginner reproduction, self-checked" provenance chip so a reader can tell it is a beginner run.

Then ask one `AskUserQuestion` for the next step. The agent assembles options from the result state:

| Option                                 | When recommended                                     |
| -------------------------------------- | ---------------------------------------------------- |
| Render shareable HTML                  | User wants to share or archive the result            |
| Try a larger scope                     | Quick check or beginner passed cleanly               |
| Cross-check with an independent method | Result sits near a phase boundary or frontier regime |
| Stop here                              | Always available, never padded                       |

## Artifact Contract

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
- Failed checks are explained and repaired (or scoped as deviations) before claiming success.

## What Not To Do

- Do not present `protocol.toml` as the first thing the user must understand.
- Do not start non-trivial compute without writing `plan.md` and getting the user to approve the plan.
- Do not bundle multiple decisions into a single prompt.
- Do not expose harness vocabulary (`cell`, `manifest`, `route`, `deviation`, `trust point`) in user-facing messages.
- Do not introduce paper-specific abbreviations without a one-sentence plain-English explanation on first use.
- Do not hide downsizing, fallback methods, missing observables, failed checks, or deviations.
- Do not choose symmetry or solver settings before the user has seen the method introduction and confirmed the computational setup.
- Do not present tool names without explaining the computational method, configurable parameters, what each parameter controls, why each matters, and the recommended setup.
- Do not hide symmetry, approximation, or solver settings in script defaults; for ED, the user must confirm these before route selection.
- Do not ask the user to decide a size without giving a size ladder, an estimate, and the corresponding cluster-vs-local recommendation.
- Do not chain scopes automatically; run only the approved scope and offer the next step in the report.
