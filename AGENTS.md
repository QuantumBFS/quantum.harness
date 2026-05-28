# Quantum Many-Body Physics Harness

Problem-solving harness for ground-state lattice problems in quantum many-body physics. Computational approaches: DMRG, ED, TEBD, VMC/NQS via Julia (ITensors) and Python (NetKet).

**Audience.** This file is user-facing — loaded into every harness session. Dev-side scaffolding (milestones, design logs) lives under `docs/`, never inlined here.

## Core Harness Philosophy

The harness is fixed at runtime. Users encounter a stable system; only the user learns, by absorbing judgment from the harness's reports. Harness changes happen in dev cycles, never during user sessions.

### Pushback and reconsideration

When the user disagrees with a result, recommendation, or interpretation ("are you sure?", "that doesn't look right", "I think it's X"), the response is genuine reconsideration — not capitulation, not defense.

1. Restate the prior reasoning in one or two lines.
2. Take the user's input seriously: how would the picture change if they're right?
3. If the conclusion should change, change it. Otherwise present the case for both interpretations and let the user re-ratify.

Never default to "you're right, sorry, let me redo." That erodes the calibrated judgment that is the agent's actual value. Equally, never argue back at length to defend a prior answer — reconsider, then state the result of reconsideration.

## Problem-Driven Skill Design

Domain content is organized around problems, not lessons, methods, tools, metrics, or roadmaps. Two dispatcher skills + paired cards:

```text
skills/model/    SKILL.md auto-fires when user names a model;   reads .knowledge/models/<name>/MODEL.md
skills/physics/  SKILL.md auto-fires on cross-model questions;  reads .knowledge/physics/<topic>/PHYSICS.md
```

`.knowledge/models/` cards cover canonical Hamiltonian or Hilbert-space problem families.
`.knowledge/physics/` cards cover cross-model organizing questions: phases, mechanisms, dynamics, solvability, and diagnostics.

Methods such as DMRG, DMFT, QMC, VMC, fuzzy sphere, and V-score belong inside the model/physics cards, not in problem-dispatcher skill names. If a card mentions a method, it should include enough method, software, setup, output, and validation guidance for an agent with no chat history to act sensibly.

Method-level skills are the narrow exception for beginner reproduction and challenge-track onboarding: `method-ed`, `method-mps`, `method-peps`, `method-qmc`, `method-vmc`, and `method-qcs`. They carry generic method insight and choose the right tool-using skill; they do not replace model/physics cards and do not own paper facts.

Dimension, lattice, filling, doping, boundary condition, disorder strength, and coupling regime are runtime choices unless they define a truly distinct canonical problem.

## Knowledge Base Role

`.knowledge/` carries data and method-level reference. It is not a curriculum, reading path, or task catalog.

Current cards:

- `conventions.md` — sign / normalization defaults; Hamiltonian forms.
- `limits.md` — exact reductions and known limits (U=0, U→∞ → t-J, XXZ Δ=1, …).
- `benchmark-numbers.md` — reference E/N, gaps, order parameters with citations.
- `symmetry-cheatsheet.md` — conserved quantities, lattice point groups.
- `magic-conventions.md` — Pauli / clock-shift conventions, SRE definitions, partition modes, qudit generalizations, Wegner-duality SRE preservation.
- `magic-benchmarks.md` — reference SRE / long-range-magic values across canonical models, reported as literature ranges.
- `methods/<method>.md` — per-algorithm notation, code shape, knobs, pitfalls. Cards match the challenge method labels: `mean-field.md`, `ed/METHOD.md` (Julia XDiag with QuSpin as Python fallback), `mps-based-algorithm.md` (DMRG + TEBD via ITensors.jl), `ltrg.md` (finite-temperature LTRG via ITensors.jl), `peps-based-algorithm.md` (CTMRG via PEPSKit.jl), `quantum-monte-carlo.md` (SSE via Carlo.jl), `variational-monte-carlo-neural-quantum-states.md` (NetKet), `quantum-circuit-simulation.md` (TensorCircuit-NG on JAX).
- `literature/<method>/` — rendered methodology references organized by method, each with its own `INDEX.md`. Raw PDFs, Semantic Scholar metadata, and extracted figures live in local-only `.raw/` / `.figures/` subfolders and must remain gitignored.

Skills cite these cards; they never hardcode the data. New cards land when a real skill begins citing them.

**Provenance discipline.** Every numerical anchor on a KB card must carry one of three tags: *Literal* (a verbatim passage from a rendered literature file under `.knowledge/literature/<method>/`, with line number), *Analytic* (closed-form derivation from a stated definition or limit), or *Harness anchor* (verified empirical value from a tagged run in this repo, with a cross-check method named). Untagged numerical entries are not benchmarks.

## Card shapes

Domain content lives in cards under `.knowledge/`, dispatched by the `/model` and `/physics` meta-skills:

- **Model cards** (`.knowledge/models/<name>/MODEL.md`) drive calculations: `Diagnose → Workflow → Method recommendations → Branch table → Verification`.
- **Physics cards** (`.knowledge/physics/<topic>/PHYSICS.md`) evaluate evidence: `Diagnose → Evidence to gather → Cross-checks → Interpretation rules → Model hooks`.

Cards hold the domain content (definitions, conventions, numerical anchors, code shapes, workflow). Skills (verbs like `/solve`, `/parameter-scan`, `/scaling-fit`) hold workflow generic across domains. Cite, never embed: a card may cite a method card or a benchmark file, never duplicate the numbers.

## Verification practice

Default verification, in priority order:

1. **Limit checks** — sign convention and trivial-parameter limits via `.knowledge/limits.md`.
2. **Symmetry** — conserved quantities respected; expected sector occupied.
3. **Convergence** — bond-dim / basis-size / Trotter-step / bath-size sweeps that asymptote.
4. **Internal consistency** — energy variance small relative to E².
5. **Cross-method validation (when feasible)** — re-run with an independent method (e.g., DMRG + TEBD imaginary-time) and confirm agreement within both methods' accuracy budgets. Use ED only after `.knowledge/methods/ed/METHOD.md` is rebuilt. Disagreement → setup error or insufficient convergence in one method.
6. **Benchmark comparison (when published reference exists)** — `.knowledge/benchmark-numbers.md`. For contested values, compare against the literature *range*, not a single number.

When the problem is in a frontier regime (frontier flag in the card), invoke the `arxiv-search` skill before interpretation: a tailored query with `<lattice> <model> <regime>` should return recent literature so the agent's conclusion sits inside the current debate, not outside it.

## Writeup handoff

After verification completes for a model card workflow, surface the writeup handoff as a final step. The default deliverable is two artifacts:

1. **Consolidated runnable script** — all parameters explicit, the calculation reproducible from a fresh checkout against the harness's installed stack.
2. **Short run report** — setup, settings, result, verification status (limit / symmetry / convergence / cross-method), residual uncertainty.

After the artifacts are in hand, if the user wants to publish, present, or share, route to:

- `scientific-visualization` — figures.

The handoff is offered, not forced. If the user just wants the result, that's a complete session.

## Future directions

Out of scope for the current harness, added as new skills only when real problems demand them:

- Real-time dynamics (`S(q,ω)`, quench dynamics, ETH).
- Finite-temperature physics (METTS, susceptibility vs T, specific heat).
- Open quantum systems (Lindbladian dynamics, dissipation).
- Topological order beyond spin liquids (SPT, fractons).
- Continuum-limit / field-theory methods (CFT identification, fuzzy sphere, RG).
- Empirical method-on-problem lore (per-problem bond-dim / size / failure-mode notes).
- Composition layer for multi-aspect research questions.

Do not preemptively scaffold these. When a real problem creates the demand, add the corresponding skill (and KB cards) following the same problem-driven design.

## Tools & Languages

Default stack: **Julia + ITensors.jl** (ITensors.jl, ITensorMPS.jl, MPSKit.jl, KrylovKit.jl). Method cards in `.knowledge/methods/` use this stack for canonical code shapes. For reproduction, benchmark, or multi-tool workflows, treat tool choice and installation as decision points: expose the recommended stack and viable alternatives before installing unless the user explicitly asks for setup only.

Python (`quimb` + `cotengra`) remains available as a fallback for tensor-network sketches via `make install quimb`. Skills can route to either when both work; method cards are Julia-flavored.

## Compute resources

The harness can use a remote cluster profile at `skills/using-slurm/profiles/active.md` for any task larger than a few minutes of local compute. **Compute feasibility is decided BEFORE the first run**, not discovered after watching a local process for an hour.

Before launching any non-trivial computation:

1. **Estimate the cost up front.** For dense ED: D² × 8 bytes is the matrix memory; wall ≈ O(D³) / aggregate-GFLOPS. For DMRG: χ² × L × 8 bytes is the MPS, wall ≈ #sweeps × (D × χ³). For QMC / Pauli-Markov: per-MCS cost × n_MCS × n_chains.
2. **Pick local vs remote with a clear threshold:**
   - Local: < 10 min wall, < 16 GB resident, fits within normal use of one CPU node.
   - Remote sbatch: everything else.
3. **Read the cluster card BEFORE picking a partition.** `skills/using-slurm/profiles/<active>.md` lists partition memory / core / wall caps and recent usage notes. The default partition is a hint, not authority — an idle partition that matches needs beats a contested default. Concrete example: the Turner 2018 reproduction had L=30 dense ED take ~50 min locally vs ~10 min on a 64-core cluster node, and L=32 was infeasible locally entirely. That asymmetry should be caught BEFORE the first local run.
4. **Compose with `/using-slurm`** (single-job or array) and `/parameter-scan` (multi-axis grids). The cluster mechanism handles ship-code → submit → monitor → fetch end-to-end.

NEVER run a multi-hour calculation locally because the agent forgot the cluster exists. The cluster IS the default for non-trivial compute; declare a deviation if local-only is actually justified.

## Repository Layout

- Scripts: `scripts/` — atomic shell helpers and generated runnable calculations
- Skills: `skills/` — conversational workflows (managed by Ion)
- Method-level skills: `skills/method-*/SKILL.md` — method insight and tool-skill selection for challenge tracks.
- Software stack skills: `skills/<stack>/SKILL.md` with machine-readable setup in `skills/<stack>/stack.toml`.
- Cluster profiles: `skills/using-slurm/profiles/` — per-cluster defaults (partitions, sbatch idioms, modules) consulted by cluster-aware skills via `skills/using-slurm/profiles/active.md` symlink or `HARNESS_CLUSTER_PROFILE=<name>` env var. Skills stay cluster-agnostic; cluster specifics live in profile cards.

## Ion skill management

Ion (`Roger-luo/Ion`, installed at `~/.local/bin/ion`) is the skill manager.
All skills live under `skills/` (Ion's `skills-dir`): local skills are
committed real directories; remote skills are fetched there by `ion add` as
symlinks into Ion's cache (gitignored; pinned in `Ion.lock`). Claude Code reads
them through the committed `.claude/skills → ../skills` symlink, so
`skills/` is the single source of truth. Do **not** add an
`[options.targets]` stanza pointing Ion at `.claude/skills`: that path is itself
a symlink back into `skills/`, so Ion would write its per-skill target
links into the source dir and clobber every skill with self-referential,
dangling links. Reload Claude Code after any `ion add` / `ion remove` so the
session picks up changes.

**Conventions:**
- `AGENTS.md` is canonical; `CLAUDE.md` is a one-liner (`treat @AGENTS.md the
  same as this file`) that Ion treats as a managed (gitignored) artifact.
- Local skills use `{ type = "local" }`; remote skills use registry shorthand
  like `anthropics/skills/skill-creator` (discover with `ion search`).

**Everyday commands:**

```bash
ion add                                  # Install/sync all skills from Ion.toml
ion add anthropics/skills/skill-creator  # Add one remote skill (registry shorthand)
ion add --rev <sha|tag|branch> <source>  # Pin a remote skill to a ref
ion remove <name>                        # Remove a skill
ion update                               # Bump installed skills to latest
ion search "<query>"                     # Search skills.sh registry
ion search -i                            # Interactive TUI search
```

**Authoring local skills:**

```bash
ion skill new <name>                     # Scaffold skills/<name>/SKILL.md
ion skill validate skills/<name>         # Lint before committing
```

**Project / meta:**

```bash
ion init                                 # Initialize a new project (creates Ion.toml)
ion agents --help                        # Manage AGENTS.md templates
ion cache gc                             # Clear the search cache
ion self --help                          # Manage the Ion install
```

## Setup & Tool Installation

- Run `make skills` to install Ion-managed skills.
- Install domain tools with `make install <tool>` after the active workflow or user has selected that tool. Running `make help` lists the currently installable tools.
- Adding a new installable tool: append its name to the `INSTALLABLE` variable in the `Makefile` and add a matching `install-<tool>` recipe. Keep recipes idempotent (check before installing).
- When suggesting a command that requires a tool, first check that tool is in `INSTALLABLE` (and installed) — otherwise tell the user to run `make install <tool>` before proceeding.

<a id="ui-ux"></a>
## UI/UX

### Output norms — users' attention is expensive

- **Remember there is a human on the other side.** Keep interactions precise and concise. Name the concrete paper, file, tool, command, or result before discussing it; do not rely on shorthand, hidden session context, or agent-only labels. Never assume the user has the same context as the agent or any subagent.
- **Plain English in user-facing messages.** Internal harness vocabulary (`cell`, `manifest`, `route`, `deviation`, `run.json`) stays in artifacts and code, not in user prompts. Paper-, model-, or method-specific abbreviations that are non-standard for this field (PXP, FSA, RVB, AKLT, …) get a one-sentence plain-English introduction on first use; common method families (ED, DMRG, QMC, VMC, NQS) need no introduction. Other jargon, if necessary, gets defined when first used. Each message is terse — a few sentences or a compact table covering key points, no overload.
- **Report results in ≤3 lines + a plot.** Primary quantity, verification status, one-line reasoning. Auto-generate the relevant convergence or stability plot with every calculation; this is the visual proof the result is trustworthy. Save the plot and display it. No extra user action needed.
- **Use `AskUserQuestion` at genuine forks** — pre-action branches and post-result next-steps. At a real fork, think faithfully like a human: surface 2–3 options with pros / cons and the recommended one (the Superpowers brainstorming pattern in UI form). User clicks, doesn't type. Each option: short label + one-line with pro and con. Recommended option first, labeled "(Recommended)". Example:
  - `"Primary method (Recommended)"` — "Matches the paper's route most closely; uses the declared compute budget."
  - `"Independent check"` — "Catches setup mistakes; usually restricted to a reduced instance."
  - `"Source audit first"` — "Cheaply anchors expectations; no new computed data."
- **Do not dump walls of checklists, verification details, convention notes, or method-card content** unless the user explicitly asks. When a skill requires source confirmation, setup cards, or proposal approval, present the required material compactly and one decision at a time.
- **For final results, lead with the answer.** "quantity = value, converged, matches declared reference" — not "I checked 5 things and here they are." During planning or reproduction setup, lead with the current decision and the recommended option's reason.
- **Auto-save scripts and results.** Every calculation produces a script saved to `scripts/<model>_<brief>.jl` and results (data + plot) saved to `results/`. Show the one-line run command: `julia --project=julia-env scripts/<name>.jl`. Never make the user ask for the script.
- **Flush stdout after each progress line in any long-running script.** Block-buffered stdout (the default when redirected to a file, a slurm log, or any non-TTY sink) hides progress until the process exits — looks like a hang. Julia: `flush(stdout)` after each `println` / `@printf`. Python: `print(..., flush=True)` or `python -u`. Pair with per-cell incremental writes (manifest after each cell) so a kill or sleep loses at most one cell. Sbatch-side helpers (`srun --unbuffered`, `stdbuf -oL`) belong in cluster profiles (`skills/using-slurm/profiles/<name>.md`), not in scripts.
- **Long iterative computes must emit intermediate estimates, not just final values.** A multi-hour run without progress output is a blind spot: the user cannot sanity-check whether the running estimate, error proxy, acceptance/progress counters, or convergence diagnostics are stabilizing. Print a partial estimate every K steps, where K is chosen so the user sees roughly 10-50 updates over the run. The script's standard runner enforces this via a `progress_every` knob; method cards declare a sensible default.
- **Monitor before declaring success — don't fire-and-forget remote actions.** A "RUNNING" status / a 0 exit code from `ssh` is not success; only verified output is. After any non-trivial remote action, stay engaged through a *settle-time* before reporting "✓ done":
  - **Lightweight tasks** (env setup, install, instantiate, single ssh command): tail output in real-time. If silent for >30 sec on a non-precompile command, suspect (PATH issue, hung lock, missing prereq).
  - **Cluster jobs**: cluster-specific settle-time discipline (partition selection from queue card, `PD → R` transition check, first-cell log tail, multi-hour periodic checks) lives in `skills/using-slurm/SKILL.md`. Compose with `/using-slurm` instead of inlining the rules here.
  - **Multi-hour local jobs**: periodic log checks every 30–60 min. Surface progress via short status lines, not silence.
  Settle-time scales with how far the job has to go before producing meaningful output. The cost of an extra 1–3 min of monitoring is much less than the cost of returning hours later to find 28 cells silently failed in the first minute — or that all 28 cells are still queued.
- **Caveat-after, not caveat-first.** For contested regimes, state the consensus framing first, then qualify the unresolved point. Never open with the hedge.
- **One question at a time** when questions are needed; prefer `AskUserQuestion` with options over open-ended text.
- **Avoid walls of words.** Keep each turn compact; when more is required by a skill, split it into one decision at a time with 2–3 options, concise pros and cons, and one recommended option when technically justified.

### Terminal Formatting

- Short bullet lists over prose paragraphs.
- Tables for comparisons.
- Blockquotes for single confirmations.

### Equation Rendering

Match equation notation to the reader's surface — **chat messages only** (reports always render LaTeX; plots use matplotlib mathtext):

- **Default UTF-8 unicode math** — renders in any surface: `⟨ψ|H|ψ⟩`, `E₀/N = −0.4438`, `J₂/J₁ ≈ 0.5`, `gap Δ`, `S=½`, `Σ ∏ √ ⊗ † ≤ ≥ ± ∞`.
- **LaTeX (`$…$`) only on a math-rendering app** (KaTeX/MathJax): `$E_0/N = -0.4438$`. Never in a terminal — it shows literal `$` and backslashes.
- **Detect once per session; unknown → UTF-8** (the universal-safe default). Claude: `CLAUDE_CODE_ENTRYPOINT` (`cli` = terminal, `claude-desktop`/web/IDE = app). Codex: CLI = terminal, markdown-math cloud/IDE = app. Generic test: does the surface render `$x^2$` as math?

## Agent guidelines

Agents working in this project should:
1. Use existing `skills/`, `scripts/`, Makefile targets, and `.knowledge/` cards rather than reimplementing operations.
2. Run `make help` to discover available workflow targets.
3. Check `Ion.toml` (or `ion` CLI) for installed / available skills.
4. For methodology references, use `download-ref`; keep different methods in different `.knowledge/literature/<method>/` folders and never commit `.raw/` or `.figures/`.
5. Install Ion skills with `make skills`; install heavy domain tools only after the active workflow or user selects that tool. Before recommending a tool-dependent command, verify the tool is in `INSTALLABLE` and expose install/setup as a user-facing option when it affects the plan.

## Daily Workflow

Run `make help` to see available Makefile targets.
