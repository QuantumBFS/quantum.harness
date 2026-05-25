---
name: reproduce-paper
description: Use when the user wants to reproduce a paper's figure or main result. Triggers include "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", "walk me through reproducing this paper", "beginner reproduction", "I don't know what size to choose", "explain while reproducing", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Beginner-facing paper reproduction with a brainstorm-first surface. The skill iterates a plan with the user one question at a time, writes the agreed plan to `results/<run>/plan.md`, then executes the single approved size and reports.

## Pipeline

```text
Brainstorm  ──▶  Plan  ──▶  Execute  ──▶  Report
 (questions)    plan.md     (1 size)     + next step
```

Brainstorm yields a plan; approving the plan starts Execute; Execute produces the figure and report. A failed check during Execute pops back to a small fork (fix / note the change / stop), never a silent fallback.

## Audience Contract

The user may know the physics goal but not the computational method, finite-size choices, or cluster trade-offs. They need information while waiting, not a black box. Every interaction should help answer:

- What are we reproducing, and what exactly does the paper plot?
- What parameters and sizes matter?
- Which method, tool, and settings are we using, and why?
- How long will each size take?
- What changed from the paper, if anything?

## Principles

1. **One workflow.** A conversational front end to paper reproduction.
2. **Ask only the forks that matter.** Surface decisions the user could meaningfully shape; skip anything already answered in their message or a prior run, and anything with a clear default. Never ask the same thing twice. If the question tool is unavailable, say so — don't pretend a choice was ratified.
3. **One question at a time.** Never bundle multiple decisions in one prompt; split a multi-part topic.
4. **Plain English. No jargon.** Keep internal or code-level terms out of user prompts; translate to plain language at the question.
5. **Introduce paper-specific abbreviations once.** A non-standard abbreviation for a model, method, or quantity (PXP, FSA, RVB, AKLT, …) gets a one-sentence plain-English introduction the first time it appears in a user-facing message. Common method families (ED, DMRG, QMC, VMC, NQS) need no introduction.
6. **Terse messages.** A few sentences or a compact table; cover the key points, never overload.
7. **Confirmation uses two options: proceed / fix.** Show a table of inferred facts; the user accepts it or branches to correct one row.
8. **Selection uses the Superpowers brainstorming style.** 2–3 options, recommended first, each one line. Every option is real and executable, or explicitly marked as needing setup first; the user can pick any without penalty.

## Core Rule

Before compute, confirm the exact setup and time estimate by writing `plan.md` and asking the user to approve it. A tiny import check or `--help` / `--dry` run is allowed before approval; nothing more. The Phase 7 plan table is the canonical summary the user approves.

## Phases

A short sequence of questions, each skipped if its answer is already known: Identify → Reproduction map → Scope → Method & tool → Settings → Where → Approve. A final fork fires only if a check fails during Execute.

### Phase 1 — Identify

One question; skip if the opener already names both paper and figure. If the paper is known but the figure isn't, list 2–3 candidate figures, smallest-meaningful first (recommended).

> **Which paper, and which figure or result?**
>
> - **<smallest meaningful figure> (recommended)** — <one-line description>
> - **<medium figure>** — <one-line description>
> - **<larger figure>** — <one-line description>

### Phase 2 — Reproduction map

Confirmation style, one table. Read the primary source and lay out, in plain language, what the paper plots, what the code must compute, the parameters that matter, the paper's sizes, and the closest beginner pilot.

> **Reproduction map** — from the paper I read it as:
>
> | Item                   | Reading                                                                          |
> | ---------------------- | -------------------------------------------------------------------------------- |
> | Paper plots            | <y-axis quantity> vs <x-axis variable>                                           |
> | Code must compute      | <observable; on which state(s); selection rule; normalization; excluded states> |
> | Parameters that matter | <Hamiltonian name + operator gist; couplings; lattice; boundary>                 |
> | Sizes in the paper     | <L list, or paper-side size range>                                               |
> | Closest beginner pilot | <smallest size that still captures the figure>                                   |
>
> - **Looks right** (recommended)
> - **Fix something** — follow-up picks the row, then asks for the corrected value

Caption text, axis labels, normalization, state-selection language, sector, window, excluded states, Hamiltonian, couplings, lattice, and boundary are recorded for the run once the user confirms. Any paper-specific abbreviation in the map gets its one-sentence introduction below the table on first use.

### Phase 3 — Scope

Selection style, three options. Each carries a size and a wall-time / memory estimate computed from the paper's presumed method using the scaling rules below.

> **How deep should this run go?**
>
> - **Quick check (recommended start)** — smallest nontrivial size; seconds–minutes; confirms the setup runs.
> - **Beginner** — modest size below the paper target; minutes–tens of minutes; shows the qualitative trend.
> - **Paper-like** — paper sizes or the nearest feasible set; hour-scale, often cluster; reproduces the target.

Scaling rules for the estimates:

- **ED**: estimate Hilbert dimension first; dense memory ≈ `D² × 8` bytes, dense diagonalization ≈ `O(D³)`. Sparse/Lanczos depends on matvec cost and number of requested states.
- **DMRG / MPS**: wall ~ `sweeps × L × χ³`; memory ~ `L × χ² × 8`. Calibrate with a short low-`χ` run when uncertain.
- **QMC**: `cost_per_sample × samples × chains`; short pilot for the sample rate.
- **VMC / NQS**: `steps × samples × model_eval_cost`; short pilot for the step rate.
- **Unknown stack**: run a tiny pilot only after telling the user it is a timing probe, then update the estimate before the real run.

### Phase 4 — Method and tool

**Method introduction, then selection.** Before asking, give a short introduction: the method family (ED, DMRG, QMC, VMC/NQS, dynamics, …) and what it computes; why it fits this target and scope; its main cost driver (Hilbert dimension, bond dimension, samples, network size); and what output it produces. Then:

> **Which method?** For <target>, I recommend <method> — <one-line reason>.
>
> - **<recommended method> (recommended)** — <one-line reason>
> - **<alternative>** — <one-line reason; one-sentence intro if it's a paper-specific abbreviation>
> - **<alternative>** — <one-line reason>

**Tool.** Build the candidate list from the current target — the paper's official code/data, the method card's canonical and fallback stacks, what's installed, any prior scaffold for this paper, and whether the tool can actually handle this target (the needed basis, symmetry, observable, and output). Read `tools/software/stacks/*.toml` before presenting. Each option shows the tool name, its setup state (ready / needs install / official code unavailable), and a one-line reason.

> **Which tool for <method>?**
>
> - **<recommended tool> (recommended)** — <ready / needs install>; <one-line reason>
> - **<alternative tool>** — <state>; <one-line reason>
> - **<alternative tool>** — <state>; <one-line reason>

Recommend the paper's official code when it exists and runs; otherwise the method card's canonical stack, then its fallback. Don't recommend a tool just because it is installed. If the canonical stack has an install or import error, say so and let the user choose — don't silently switch to a different tool.

### Phase 5 — Settings

Setup questions start right after the tool choice — don't insert a separate "is this feasible?" or "investigate the tool" question. If the chosen tool can't express something directly, say so plainly in the setup options (works directly / needs a smaller version / can't do this target with this tool) and only suggest switching tools after showing those consequences.

Selection style, one question per setting, in a sensible order for the method. Precede each with a compact table:

| Parameter | What it controls        | Why it matters                                   | Recommendation                |
| --------- | ----------------------- | ------------------------------------------------ | ----------------------------- |
| `<name>`  | `<plain-language role>` | `<correctness / cost / convergence consequence>` | `<recommended value or rule>` |

Each option is one line: what it does, whether it matches the paper or departs, and the rough cost. Mark anything that needs setup before it can run.

> **<Setting> — use <recommended value>?**
>
> - **<recommended value> (recommended)** — <plain consequence; matches paper / departs>; ~<wall>, ~<memory>
> - **<alternative>** — <plain consequence>; ~<wall>, ~<memory>
> - **<alternative>** — <plain consequence>; ~<wall>, ~<memory>

An answer to one setting can change the recommendation for later ones; re-derive before asking the next. Ask only the knobs the chosen method and target actually need (the method card lists them); skip any already pinned from a prior run. A quick-check scope may use low statistics or a small size, but its result must be labeled quick-check quality. Rough per-method knob sets:

- **ED**: basis, boundary, symmetry sector, full-spectrum vs selected-state policy, diagonalization mode, tolerance, size list.
- **DMRG / MPS**: bond dimension `χ`, sweeps, cutoff, initialization, boundary, observable, a convergence comparison.
- **QMC**: thermalization, samples, chains, bins, update type, estimator, target uncertainty.
- **VMC / NQS**: ansatz / model size, optimizer, learning rate, samples, steps, seeds, validation observable.

**ED needs extra care on symmetry.** Confirm the symmetry sector before choosing where to run: name each symmetry the paper or method uses (momentum `k`, inversion parity, total `Sz`, particle number, point group, boundary), say why the recommended sector is right, and flag any exact symmetry left unused. State a dense full-spectrum run as "exact within the selected symmetry sector." Don't call an approximation — FSA (Forward Scattering Approximation: an approximate method that builds a small basis from repeated Hamiltonian applications), selected Krylov states, or a reduced window — a reproduction of a full-spectrum panel; present it as an approximation with its scientific consequence.

### Phase 6 — Where to run

Selection style, two options. Recommend local only when the chosen scope and setup should stay under 10 minutes and 16 GB; otherwise recommend the cluster. The cluster route composes with `/slurm` for ship / submit / monitor / fetch — this skill does not duplicate cluster idioms.

> **Run here or on the cluster?**
>
> - **<recommended route> (recommended)** — <one-line reason citing the wall/memory estimate>
> - **<alternative>** — <one-line reason>

### Phase 7 — Approve

Confirmation style, compact plan table.

> **Plan**
>
> | Field          | Value                                                             |
> | -------------- | ----------------------------------------------------------------- |
> | Paper / target | <citation, figure id>                                             |
> | Method / tool  | <method>, <tool>                                                  |
> | Model          | <H, params, lattice, boundary, L list>                           |
> | Sector         | <symmetry choice>                                                 |
> | Solver         | <approximation + solver configuration>                           |
> | Scope          | <quick check / beginner / paper-like>                            |
> | Where          | <this machine / cluster>, ~<wall>, ~<memory>                     |
> | Outputs        | a written plan, the figure, and a short report    |
>
> - **Approve** (recommended)
> - **Change something** — follow-up picks which row to change and jumps back to that phase

Non-approval rewinds to the relevant earlier phase — never silently downsize.

## Plan Artifacts

After approval, write `results/<run>/plan.md` — the friendly, human-readable plan:

```markdown
# Plan: <paper-short> Fig <id>

**Paper.** <citation, primary-source path>
**Target.** <figure/result, caption excerpt>
**Method / tool.** <e.g., ED / XDiag>, <why this tool>
**Parameters.** <couplings, lattice, boundary, sector, …>
**Scope & sizes.** <quick-check | beginner | paper-like>, <L = …>
**Solver.** <dense full ED | Lanczos k=… | DMRG χ/sweeps/cutoff | …>, <why>
**Where & estimate.** <local | cluster>, ~<wall>, ~<memory>
**Changes from the paper.** <list, or "none">
**Outputs.** plan.md, figs/<id>.png, run-report.md
```

## Execute

Run the approved scope only. The script lands at `scripts/<model>_<brief>.{jl|py}` and saves its figure under `results/<run>/`.

- One plain-English status line per step (what's running, expected time). Flush stdout.
- For any step expected to take > 2 minutes, emit ~10–50 progress updates. Method cards declare the `progress_every` default.
- Run a check after a result only when it is scientifically meaningful: does it match the primary source (caption, axes, normalization, state selection), plus any limit or known-answer check. A failure opens Phase 8.
- The cluster route composes with `/slurm`.

### Phase 8 — On check failure

Selection style; fires only when a meaningful check fails.

> **Check failed.** <one sentence: what failed and why it matters>
>
> - **Repair** (recommended when it's a clear bug) — fix the offending layer and rerun this step.
> - **Note the change and continue** — keep the result, record the change in the plan, continue as a learning run.
> - **Stop** — keep current artifacts, end the session.

During waits, communicate at meaningful checkpoints (start, after the pilot or quick check, during long runs with elapsed/remaining, after each scope). Summarize useful signal and keep log paths available rather than dumping raw logs.

## Report

After Execute, write `results/<run>/run-report.md`: a one-paragraph beginner summary; paper target vs reproduced target; the approved setup and actual runtime; produced artifact paths; verification status (`self-checked` / `partial` / `failed`); and the exact rerun command. This run report plus the figure is the deliverable.

Then ask one `AskUserQuestion` with 2–3 next steps chosen from the result state:

| Option                                 | Offer when                                        |
| -------------------------------------- | ------------------------------------------------- |
| Try a larger scope                     | Quick check or beginner passed cleanly            |
| Cross-check with an independent method | The result sits near a phase boundary or frontier |
| Stop here                              | Always available, never padded                    |

## Artifact Contract

What the run produces:

- `scripts/<model>_<brief>.{jl|py}` — the runnable script.
- `results/<run>/plan.md` — friendly human-readable plan.
- `results/<run>/figs/<figure_id>.png` — reproduced figure.
- `results/<run>/run-report.md` — plain-language summary, commands, verification status, next choices.

## What Stays From The Harness Contract

- Primary sources control paper claims; `.knowledge/` cards are hints.
- Figure captions and plotted quantities are read verbatim before coding.
- Any change from the paper's setup is recorded before the affected run.
- Failed checks are explained and repaired (or recorded as a noted change) before claiming success.

## What Not To Do

- Don't start non-trivial compute without writing `plan.md` and getting approval.
- Don't make the user wade through internal files before they understand the plan in plain English.
- Don't hide downsizing, fallback tools, missing observables, failed checks, or changes from the paper.
- Don't choose symmetry or solver settings before the user has seen the method introduction; for ED, confirm the symmetry sector before choosing where to run.
- Don't present a tool name without explaining the method, the configurable settings, and what each controls.
- Don't ask the user to pick a size without a size ladder, an estimate, and a local-vs-cluster recommendation.
- Don't chain scopes automatically; run only the approved scope and offer the next step in the report.
