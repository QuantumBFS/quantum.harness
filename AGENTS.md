# Quantum Many-Body Physics Harness

Problem-solving harness for ground-state lattice problems in quantum many-body physics. Computational approaches: DMRG, ED, TEBD, VMC/NQS via Julia (ITensors) and Python (NetKet).

**Audience.** This file is user-facing — loaded into every harness session. Dev-side scaffolding (milestones, design logs) lives under `docs/`, never inlined here.

## Core Harness Philosophy

Agents solve concrete problems under light human steering. Users bring problems; agents diagnose, recommend, execute, verify, and surface only the decisions that genuinely matter. Good judgment is demonstrated through action — users absorb it by watching competent work happen.

The harness is fixed at runtime. Users encounter a stable system; only the user learns, by absorbing judgment from the harness's reports. Harness changes happen in dev cycles, never during user sessions.

### Strategic Steering Principle

Use the Superpowers brainstorming pattern as the strategic model: when a task has meaningful branches, understand the context, then present 2-3 real options with concise tradeoffs. Lead with the recommended option and explain why.

This is a strategic design pattern, not user-facing language. Do not mention "fake steering wheel", psychological steering, or autonomous-driving metaphors to users. Locally, the interaction should simply look like competent technical judgment.

Every option offered must be real and executable. The first option may be recommended, but the other options must not be fake, punitive, or low-effort. If the user chooses a non-recommended path, follow it faithfully unless there is a concrete technical blocker. If blocked, explain the blocker and offer the closest viable alternatives.

The goal is agent-led, user-ratified work: the agent drives the workflow; the user controls goal, assumptions, depth, method preference, risk tolerance, and final interpretation.

The user's control is exercised by *ratifying* harness-recommended options — clicking the recommended button, ignoring the diagnose proposal, or overriding when desired — not by pre-specifying. A fresh user may have no method preference; the harness still produces a plan, and the user ratifies by silence or selection. Pre-specification is welcome but never required.

### Act first, offer alternatives after

When defaults are clear from the user's prompt, the agent acts immediately and reports in ≤3 lines. Alternatives are offered AFTER the result, not before. The steering wheel is in the follow-up ("Want to also..."), not in a pre-approval gate.

| Situation | Pattern |
|---|---|
| Clear defaults | Act → report with embedded reasoning (method + why + verification, ≤3 lines) → next-steps via `AskUserQuestion` |
| Real branch (genuinely ambiguous) | `AskUserQuestion` with 2–3 options → act → report |
| Frontier "is it X?" | Act on literature summary → report → "Want me to also run [compute]?" |
| Off-scope | Act on closest in-scope thing → report → "For the off-scope part: [options]" |

"Just do it" from the user means the agent asked one question too many. The goal is zero questions for clear problems.

The steering wheel lives in the report and the next-steps, not in pre-approval. The report always embeds one-line reasoning: what method was chosen and why, what was verified and how. A convergence plot is auto-generated with every calculation. Over many sessions, users absorb this reasoning and develop judgment — without ever being asked to make the call themselves.

Next-steps are always offered as `AskUserQuestion` options. Common next-steps (in rough priority):
- **Richer visualization** — correlations, structure factor, density profile, or publication figure via `scientific-visualization`.
- **Parameter scan or finite-size extrapolation** — the natural research follow-up.
- **Writeup** — declared entry + run report, then route to writing skills.
- **Stop here** — always a real option, never padded.

Never march through a checklist of questions. If the user's prompt is too vague to infer anything (rare), present 2–3 starting points via `AskUserQuestion`.

### Pushback and reconsideration

When the user disagrees with a result, recommendation, or interpretation ("are you sure?", "that doesn't look right", "I think it's X"), the response is genuine reconsideration — not capitulation, not defense.

1. Restate the prior reasoning in one or two lines.
2. Take the user's input seriously: how would the picture change if they're right?
3. If the conclusion should change, change it. Otherwise present the case for both interpretations and let the user re-ratify.

Never default to "you're right, sorry, let me redo." That erodes the calibrated judgment that is the agent's actual value. Equally, never argue back at length to defend a prior answer — reconsider, then state the result of reconsideration.

## Problem-Driven Skill Design

Domain content is organized around problems, not lessons, methods, tools, metrics, or roadmaps. Two dispatcher skills + paired cards:

```text
tools/skills/model/    SKILL.md auto-fires when user names a model;   reads .knowledge/models/<name>/MODEL.md
tools/skills/physics/  SKILL.md auto-fires on cross-model questions;  reads .knowledge/physics/<topic>/PHYSICS.md
```

`.knowledge/models/` cards cover canonical Hamiltonian or Hilbert-space problem families.
`.knowledge/physics/` cards cover cross-model organizing questions: phases, mechanisms, dynamics, solvability, and diagnostics.

Methods such as DMRG, DMFT, QMC, VMC, fuzzy sphere, and V-score belong inside the model/physics cards, not in skill names. If a card mentions a method, it should include enough method, software, setup, output, and validation guidance for an agent with no chat history to act sensibly.

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
- `methods/<method>.md` — per-algorithm notation, code shape, knobs, pitfalls. Cards match the challenge method labels: `mean-field.md`, `ed/METHOD.md` (Julia XDiag with QuSpin as Python fallback), `mps-based-algorithm.md` (DMRG + TEBD via ITensors.jl), `peps-based-algorithm.md` (CTMRG via PEPSKit.jl), `quantum-monte-carlo.md` (SSE via Carlo.jl), `variational-monte-carlo-neural-quantum-states.md` (NetKet), `quantum-circuit-simulation.md` (TensorCircuit-NG on JAX).
- `literature/<method>/` — rendered methodology references organized by method, each with its own `INDEX.md`. Raw PDFs, Semantic Scholar metadata, and extracted figures live in local-only `.raw/` / `.figures/` subfolders and must remain gitignored.

Skills cite these cards; they never hardcode the data. New cards land when a real skill begins citing them.

**Paper reproduction evidence invariants.** These are harness-wide rules, not `/reproduce-paper` implementation details:
- Written content is evidence, not authority. `.knowledge/` cards, rendered notes, scripts, summaries, and prior run artifacts are cached hints.
- Evidence authority MUST be explicit: `primary` (paper, supplement, official code/data), `trusted_reference` (analytic / exact / independent check), `current_run` (fresh artifact with matching protocol and script provenance), `hint` (KB, notes, old scripts/plans/data/figures), and `assumption` / `deviation`.
- MUST quarantine hints. Hints may guide planning, but they cannot close a reproduction claim unless re-confirmed against a primary source or regenerated as current-run evidence.
- Primary sources control paper reproduction: paper PDF, supplement, and official code/data when available. If a primary source conflicts with a KB card, the primary source controls; emit a KB diff and proceed from the primary-source-derived claim.
- KB-sourced reproduction claims MUST either be confirmed against a primary source or marked as explicit unverified assumptions in the run report.
- DO NOT silently weaken the target. Any change in paper-declared setup, implementation route, data-generation route, constraints, budget, or uncertainty method must be recorded as a deviation before it can support a reproduction claim.
- Method-agnostic does not mean method-optional. Every executable reproduction cell MUST declare `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`. `route` is one of `paper`, `canonical`, `fallback`, or `deviation`. A non-paper / non-canonical / non-fallback stack is a `deviation` before it is a result.
- Tool availability is not route authority. DO NOT probe, select, or start implementing a fallback stack because the canonical stack has an environment error. First record the canonical route state as failed/pending, then declare `fallback` or `deviation` in the protocol before touching the alternate stack. A fallback stack must be the method card's next recommended stack, not any installed language package.
- Feature-gap is not route authority. The canonical / fallback stack (XDiag, QuSpin, ITensors, NetKet, …) lacking a built-in basis, constraint, projector, or observable for the target model is NOT a reason to drop to raw NumPy / SciPy / matplotlib. Custom bases belong INSIDE the canonical framework: QuSpin's `user_basis` with a Numba precheck, XDiag's `Spinhalf` with a custom representation, ITensors' custom site type, etc. The harness deliberately rides on canonical frameworks so the result interoperates with the broader research community — that interoperability is the protocol value, not just numerical correctness. Drop the canonical stack only when (a) the customization measurably degrades wall-time by >2× vs a hand-rolled implementation, OR (b) the customization itself is more code than the bare LAPACK/sparse primitives it would replace. Either justification MUST appear as an explicit `[[deviations]]` row before compute, naming the cost or complexity in concrete terms (no hand-waves like "no built-in basis").
- Audit the active stack at protocol-author time. The script's actual imports MUST match the protocol's declared `stack` field on every cell. Importing `quspin` only as a route-check (`python -c 'import quspin'`) while the compute uses raw `scipy.linalg.eigh` is a silent drift — file a deviation immediately or rewrite the script to use QuSpin in fact, not in label.
- DO NOT use first-cell provenance. Per-cell run-spec overrides are allowed, but assembly must validate each manifest against the merged shared+cell settings and provenance, then report settings as constant vs varying. Never summarize a correctness-affecting setting, budget, or uncertainty rule from the first completed manifest unless a manifest-consensus check has proved it is global.
- Failed checks block claims. A failed protocol, script, command, manifest, freshness, consensus, numeric, or result check stops the workflow until repaired, scoped down, or recorded as a justified assumption/deviation.
- Stale artifacts ≠ evidence. Remote job status, `ssh` exit status, and scheduler `COMPLETED` state are operational facts only; fetched manifests and checks are the evidence.

**Provenance discipline.** Every numerical anchor on a KB card must carry one of three tags: *Literal* (a verbatim passage from a rendered literature file under `.knowledge/literature/<method>/`, with line number), *Analytic* (closed-form derivation from a stated definition or limit), or *Harness anchor* (verified empirical value from a tagged run in this repo, with a cross-check method named). Untagged numerical entries are not benchmarks.

<a id="pre-compute-figure-reading-checklist"></a>
**Pre-compute figure-reading checklist.** Reproducing a paper figure without first reading its caption verbatim and matching every plotted quantity to a paper-stated definition is the single biggest waste of computational budget in this harness. The main agent MUST work through this checklist BEFORE writing any cell script or assembly code that contributes to a figure.

For each figure panel:

1. **Caption verbatim.** Quote the paper's caption text for the panel into the protocol's `[[figures]]` entry. Not paraphrased — verbatim. Subsequent steps refer to this exact text, not to a summary.
2. **x-axis.** Identify the variable name, units, range, and scale (linear / log). The printed axis label on the figure image is the source of truth; the body text may name the variable but not its scale or normalization.
3. **y-axis.** Identify the variable name, units, range, scale, AND any normalization factor (× L, × N, divided by D, log₂ vs log₁₀, etc.). A missing or extra normalization factor is the most common silent error and is invisible from numerical values alone — it must be read off the printed axis label.
4. **Per-curve identity.** For every line / marker / color in the panel: which state(s)? which subset of states? which sector? which observable? Match each to a single concrete object in code, named the same way the caption names it.
5. **State-selection language is a contract.** Phrases like "state in the special band adjacent to E = 0", "lowest |E|>0 eigenstate", "middle of the band", "ground state in the symmetry sector", and "exact zero mode" each select a DIFFERENT specific state. Treat them as distinct contracts. Write down which exact eigenstate the caption picks, in code-precise terms, BEFORE picking it in code.
6. **Window / sub-region.** Captions like "averaged over the middle 2/3 of the band", "i ∈ [D/5, D/2 − 500]", "excluding zero modes" define the data subset. Encode the window precisely; off-by-one and misread bounds silently change results.
7. **Stated numerical anchors.** If the body text quotes a number for the panel ("ΔE/E ≈ 1%", "peak at n = L/2", "tower spacing 2Ω"), record it as a benchmark. Code output must reproduce each anchor within reported uncertainty before any further claim is considered settled.
8. **What the figure is NOT.** Captions often distinguish closely-related states ("ground state" vs "first special state above zero" vs "exact zero mode"). Note explicitly which related-but-distinct states the panel does NOT plot, so the code does not accidentally pick one of them.

This checklist applies to figure-producing cell scripts AND to assembly / plot code. A wrong y-axis label or a wrong state pick in `assemble.py` wastes the same compute as a wrong cell script — the figure is re-rendered from wrong-but-correctly-stored data, but the user-facing result is still wrong.

Wasted-compute lesson on record: in the Turner 2018 reproduction, Fig 3(c) was first composed against `|⟨n|ψ⟩|²` instead of `|⟨n|ψ⟩|² L` (missed the L factor in the printed y-axis label) AND picked the highest-overlap exact zero mode instead of the lowest-|E|>0 special state ("adjacent to E = 0" was misread as "AT E = 0"). The fix required re-running L = 12, 14, 16, 18, 20, 22, 24, 26, 28 cells. Both errors were directly visible in the paper's printed caption and figure if the checklist had been worked through before compute.

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

- `scientific-writing` — paper text.
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

Default stack: **Julia + ITensors.jl** (ITensors.jl, ITensorMPS.jl, MPSKit.jl, KrylovKit.jl). Install via `make install julia && make install itensors`. Method cards in `.knowledge/methods/` use this stack for canonical code shapes.

Python (`quimb` + `cotengra`) remains available as a fallback for tensor-network sketches via `make install quimb`. Skills can route to either when both work; method cards are Julia-flavored.

## Compute resources

The harness has a remote cluster (`tools/cluster/active.md` → currently `hpc2.md`) for any task larger than a few minutes of local compute. **Compute feasibility is decided BEFORE the first run**, not discovered after watching a local process for an hour.

Before launching any non-trivial computation:

1. **Estimate the cost up front.** For dense ED: D² × 8 bytes is the matrix memory; wall ≈ O(D³) / aggregate-GFLOPS. For DMRG: χ² × L × 8 bytes is the MPS, wall ≈ #sweeps × (D × χ³). For QMC / Pauli-Markov: per-MCS cost × n_MCS × n_chains.
2. **Pick local vs remote with a clear threshold:**
   - Local: < 10 min wall, < 16 GB resident, fits within normal use of one CPU node.
   - Remote sbatch: everything else.
3. **Read the cluster card BEFORE picking a partition.** `tools/cluster/<active>.md` lists partition memory / core / wall caps and recent usage notes. The default partition is a hint, not authority — an idle partition that matches needs beats a contested default. Concrete example: the Turner 2018 reproduction had L=30 dense ED take ~50 min locally vs ~10 min on a 64-core cluster node, and L=32 was infeasible locally entirely. That asymmetry should be caught BEFORE the first local run.
4. **Compose with `/slurm`** (single-job or array) and `/parameter-scan` (multi-axis grids). The cluster mechanism handles ship-code → submit → monitor → fetch end-to-end.

NEVER run a multi-hour calculation locally because the agent forgot the cluster exists. The cluster IS the default for non-trivial compute; declare a deviation if local-only is actually justified.

## Installed Skills

UX skills:
- **onboard** — first-touch intake, domain setup, route to `/model` or `/physics`
- **solve** — interactive problem-solving loop: intake → act → report → next-steps → loop.

Problem dispatchers (auto-triggered; read cards under `.knowledge/{models,physics}/<name>/`):
- **model** — fires when user names a harness-tracked model. Reads `MODEL.md` card and follows its workflow.
- **physics** — fires when user asks a cross-model phenomenon question. Reads `PHYSICS.md` card and follows its evidence rubric.

Problem-solving primitives (generic; topic-agnostic, compose with the dispatchers above):
- **parameter-scan** — sweep one or more declared axes for any produced quantity. Composes with `/slurm` for cluster execution.
- **scaling-fit** — finite-size collapse, exponent extraction with uncertainty.
- **cross-method-check** — verify the same observable with an independent method or diagnostic.
- **slurm** — agent-does-ssh cluster mechanism: ship code, submit (single or array), monitor, fetch. Reads cluster specifics from `tools/cluster/<active>.md`. Dispatches `/setup-julia` when the cluster's Julia env isn't instantiated. Does NOT know about parameter grids — that's `/parameter-scan`'s job.
- **setup-julia** — install Julia (juliaup or `module load`), configure package mirror (defaults to Chinese mirror if cluster `region == mainland_china`), instantiate the project env. Generic over target (local laptop or remote ssh alias). Idempotent.
- **reproduce-paper** — orchestrate end-to-end paper reproduction: plans the figure dependency graph, surfaces methodology / verification / cross-check figs alongside substantive ones, composes the primitives above. Generic over papers. Absorbs the writeup-handoff close (declared entry + run report).
- **reproduce-paper-onboard** — beginner-guided paper reproduction: explains the paper-to-code mapping, estimates time by size tier, confirms setup before compute, and preserves the same core artifacts for later upgrade to the full workflow.

External/support skills:
- **arxiv-search** — Semantic arXiv search via Valyu
- **scientific-visualization** — Publication-quality figures (matplotlib/seaborn/plotly)
- **scientific-writing** — Scientific manuscript drafting
- **download-ref** — Add arXiv/DOI/book methodology references under `.knowledge/literature/<method>/`; rendered markdown is tracked, raw PDFs/metadata/figures are local-only.

## Tool Hierarchy

- CLI tools: `tools/cli/` — atomic shell scripts
- Skills: `tools/skills/` — conversational workflows (managed by Ion)
- Cluster profiles: `tools/cluster/` — per-cluster defaults (partitions, sbatch idioms, modules) consulted by cluster-aware skills via `tools/cluster/active.md` symlink or `HARNESS_CLUSTER_PROFILE=<name>` env var. Skills stay cluster-agnostic; cluster specifics live in profile cards.

## Ion skill management

Ion (`Roger-luo/Ion`, installed at `~/.local/bin/ion`) is the skill manager.
Local skill sources live in `tools/skills/`; Ion installs them (symlinks)
into `.claude/skills/` per `Ion.toml`'s `[options.targets]`. `.claude/skills/`
is git-ignored — the source of truth is `tools/skills/`. Reload Claude Code
after any `ion add` / `ion remove` so the session picks up changes.

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
ion skill new <name>                     # Scaffold tools/skills/<name>/SKILL.md
ion skill validate tools/skills/<name>   # Lint before committing
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
- Install domain tools **on demand** with `make install <tool>`. Running `make help` lists the currently installable tools.
- Adding a new installable tool: append its name to the `INSTALLABLE` variable in the `Makefile` and add a matching `install-<tool>` recipe. Keep recipes idempotent (check before installing).
- When suggesting a command that requires a tool, first check that tool is in `INSTALLABLE` (and installed) — otherwise tell the user to run `make install <tool>` before proceeding.

<a id="ui-ux"></a>
## UI/UX

### Output norms — users' attention is expensive

- **Remember there is a human on the other side.** Keep interactions precise and concise. Name the concrete paper, file, tool, command, or result before discussing it; do not rely on shorthand, hidden session context, or agent-only labels. Avoid jargon unless it is necessary, and define it when used. Never assume the user has the same context as the agent or any subagent.
- **Report results in ≤3 lines + a plot.** Primary quantity, verification status, one-line reasoning. Auto-generate the relevant convergence or stability plot with every calculation; this is the visual proof the result is trustworthy. Save the plot and display it. No extra user action needed.
- **Use `AskUserQuestion` at genuine forks** — pre-action branches and post-result next-steps. Never for pre-flight ratification of clear defaults; never silently at a real fork. Both interrogating clear defaults and silently picking at real forks deny the user the steering wheel. At a real fork, think faithfully like a human: surface 2–3 options with pros / cons and the recommended one (the Superpowers brainstorming pattern in UI form). User clicks, doesn't type. Each option: short label + one-line with pro and con. Recommended option first, labeled "(Recommended)". Example:
  - `"Primary method (Recommended)"` — "Matches the paper's route most closely; uses the declared compute budget."
  - `"Independent check"` — "Catches setup mistakes; usually restricted to a reduced instance."
  - `"Source audit first"` — "Cheaply anchors expectations; no new computed data."
- **Never dump checklists, verification details, convention notes, or method-card content** unless the user explicitly asks. The agent runs verification internally; the user sees the result, not the process.
- **Lead with the answer, qualify only if asked.** "quantity = value, converged, matches declared reference" — not "I checked 5 things and here they are."
- **Auto-save scripts and results.** Every calculation produces a script saved to `scripts/<model>_<brief>.jl` and results (data + plot) saved to `results/`. Show the one-line run command: `julia --project=julia-env scripts/<name>.jl`. Never make the user ask for the script.
- **Flush stdout after each progress line in any long-running script.** Block-buffered stdout (the default when redirected to a file, a slurm log, or any non-TTY sink) hides progress until the process exits — looks like a hang. Julia: `flush(stdout)` after each `println` / `@printf`. Python: `print(..., flush=True)` or `python -u`. Pair with per-cell incremental writes (manifest after each cell) so a kill or sleep loses at most one cell. Sbatch-side helpers (`srun --unbuffered`, `stdbuf -oL`) belong in cluster profiles (`tools/cluster/<name>.md`), not in scripts.
- **Long iterative computes must emit intermediate estimates, not just final values.** A multi-hour run without progress output is a blind spot: the user cannot sanity-check whether the running estimate, error proxy, acceptance/progress counters, or convergence diagnostics are stabilizing. Print a partial estimate every K steps, where K is chosen so the user sees roughly 10-50 updates over the run. The script's standard runner enforces this via a `progress_every` knob; method cards declare a sensible default.
- **Monitor before declaring success — don't fire-and-forget remote actions.** A "RUNNING" status / a 0 exit code from `ssh` is not success; only verified output is. After any non-trivial remote action, stay engaged through a *settle-time* before reporting "✓ done":
  - **Lightweight tasks** (env setup, install, instantiate, single ssh command): tail output in real-time. If silent for >30 sec on a non-precompile command, suspect (PATH issue, hung lock, missing prereq).
  - **Cluster jobs**: cluster-specific settle-time discipline (partition selection from queue card, `PD → R` transition check, first-cell log tail, multi-hour periodic checks) lives in `tools/skills/slurm/SKILL.md`. Compose with `/slurm` instead of inlining the rules here.
  - **Multi-hour local jobs**: periodic log checks every 30–60 min. Surface progress via short status lines, not silence.
  Settle-time scales with how far the job has to go before producing meaningful output. The cost of an extra 1–3 min of monitoring is much less than the cost of returning hours later to find 28 cells silently failed in the first minute — or that all 28 cells are still queued.
- **Caveat-after, not caveat-first.** For contested regimes, state the consensus framing first, then qualify the unresolved point. Never open with the hedge.
- **One question at a time** when questions are needed; prefer `AskUserQuestion` with options over open-ended text.
- **Keep prose output under 10 lines.** `AskUserQuestion` options are rendered as buttons — they don't count toward this limit. If more prose is needed, ask before continuing.

### Content Rendering

- Use `tools/cli/render` for equations, diagrams, or structured explanations — don't dump raw LaTeX in the terminal.

### Terminal Formatting

- Short bullet lists over prose paragraphs.
- Tables for comparisons.
- Blockquotes for single confirmations.

## Agent guidelines

Agents working in this project should:
1. Treat the core harness philosophy and problem-driven skill design above as the controlling design contract.
2. Use tools from `tools/` rather than reimplementing operations.
3. Run `make help` to discover available workflow targets.
4. Check `Ion.toml` (or `ion` CLI) for installed / available skills.
5. For methodology references, use `download-ref`; keep different methods in different `.knowledge/literature/<method>/` folders and never commit `.raw/` or `.figures/`.
6. Install Ion skills with `make skills` and heavy domain tools on demand via `make install <tool>`. Before recommending a tool-dependent command, verify the tool is in `INSTALLABLE` (and installed); if not, instruct the user to run `make install <tool>` first.

## Daily Workflow

Run `make help` to see available Makefile targets.
