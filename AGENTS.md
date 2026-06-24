# Quantum Many-Body Physics Harness

Problem-solving harness for quantum many-body lattice problems, ground-state and finite-temperature. Which methods, tools, and languages apply is owned by the method and tool skills (discovered at runtime); this file stays method-agnostic.

**Audience.** This file is user-facing — loaded into every harness session. Dev-side scaffolding (milestones, design logs) lives under `docs/`, never inlined here.

## Core Harness Philosophy

The harness is fixed at runtime. Users encounter a stable system; only the user learns — by being guided through the workflow in Superpowers brainstorming style, feeling each decision as it's made, with the reports as the durable record. Harness changes happen in dev cycles, never during user sessions.

### Pushback and reconsideration

When the user disagrees with a result, recommendation, or interpretation ("are you sure?", "that doesn't look right", "I think it's X"), the response is genuine reconsideration — not capitulation, not defense.

1. Restate the prior reasoning in one or two lines.
2. Take the user's input seriously: how would the picture change if they're right?
3. If the conclusion should change, change it. Otherwise present the case for both interpretations and let the user re-ratify.

Never default to "you're right, sorry, let me redo." That erodes the calibrated judgment that is the agent's actual value. Equally, never argue back at length to defend a prior answer — reconsider, then state the result of reconsideration.

### Confirm the setup, even when it seems unambiguous

Before any compute, surface the consequential setup the agent is about to commit to — the exact Hamiltonian (with its sign and coupling convention), lattice, boundary, conserved sector, target observable, and system size — and get an explicit confirm-or-correct. Do this *even when there is no apparent decision to make*: a setup that looks obvious to the agent often encodes a silent assumption the user would catch at a glance (a sign convention, a factor of 2, a boundary choice, a sector). One line of confirmation is far cheaper than a full run on the wrong system.

This is not an `AskUserQuestion` fork — there may be no branch to choose. It is the model cards' "propose for ratification" step applied unconditionally: state the assumption, then let the user ratify or correct. In `reproduce-paper`, restate the Hamiltonian and the key setup explicitly and wait for ratification before running, even when the paper reads as unambiguous.

## Problem-Driven Skill Design

Domain content is organized around problems, not lessons, methods, tools, metrics, or roadmaps. Two dispatcher skills + paired cards:

```text
skills/model/    SKILL.md auto-fires when user names a model;   reads .knowledge/models/<name>/MODEL.md
skills/physics/  SKILL.md auto-fires on cross-model questions;  reads .knowledge/physics/<topic>/PHYSICS.md
```

`.knowledge/models/` cards cover canonical Hamiltonian or Hilbert-space problem families.
`.knowledge/physics/` cards cover cross-model organizing questions: phases, mechanisms, dynamics, solvability, and diagnostics.

Methods such as DMRG, DMFT, QMC, VMC, and fuzzy sphere belong inside the model/physics cards, not in problem-dispatcher skill names. If a card mentions a method, it should include enough method, software, setup, output, and validation guidance for an agent with no chat history to act sensibly.

Method-level skills (`skills/method-*`) are the narrow exception for beginner reproduction and challenge-track onboarding. Each `SKILL.md` carries workflow and routing on top, then the per-algorithm reference (notation, code shape, knobs, pitfalls) in a `## Details` section. They carry generic method insight and route to the right tool-using skill; the method↔tool mapping lives in each card's *Select software* section, not here. They do not replace model/physics cards and do not own paper facts.

Dimension, lattice, filling, doping, boundary condition, disorder strength, and coupling regime are runtime choices unless they define a truly distinct canonical problem.

## Knowledge Base Role

`.knowledge/` carries data and literature reference. It is not a curriculum, reading path, or task catalog.

Current cards:

- `conventions.md` — sign / normalization defaults; Hamiltonian forms.
- `limits.md` — exact reductions and known limits (U=0, U→∞ → t-J, XXZ Δ=1, …).
- `symmetry-cheatsheet.md` — conserved quantities, lattice point groups.
- Per-method reference (notation, code shape, knobs, pitfalls) lives in the `## Details` section of each `skills/method-*/SKILL.md`, not in the knowledge base — see "Problem-Driven Skill Design".
- `literature/<method>/` — rendered methodology references organized by method, each with its own `INDEX.md`. Raw PDFs, Semantic Scholar metadata, and extracted figures live in local-only `.raw/` / `.figures/` subfolders and must remain gitignored.

Skills cite these cards; they never hardcode the data. New cards land when a real skill begins citing them.

**Provenance discipline.** Every numerical anchor on a KB card must carry one of three tags: *Literal* (a verbatim passage from a rendered literature file under `.knowledge/literature/<method>/`, with line number), *Analytic* (closed-form derivation from a stated definition or limit), or *Harness anchor* (verified empirical value from a tagged run in this repo, with a cross-check method named). Untagged numerical entries are not trustworthy.

## Card shapes

Domain content lives in cards under `.knowledge/`, dispatched by the `/model` and `/physics` meta-skills:

- **Model cards** (`.knowledge/models/<name>/MODEL.md`) drive calculations: `Diagnose → Workflow → Method recommendations → Branch table → Verification`.
- **Physics cards** (`.knowledge/physics/<topic>/PHYSICS.md`) evaluate evidence: `Diagnose → Evidence to gather → Cross-checks → Interpretation rules → Model hooks`.

Cards hold the domain content (definitions, conventions, numerical anchors, code shapes, workflow). Skills (verbs like `/solve`, `/parameter-scan`, `/scaling-fit`) hold workflow generic across domains. Cite, never embed: a card may cite a method card or another reference card, never duplicate the numbers.

## Verification practice

Verification is **opt-in**: run these checks only when the user challenges a result and debugging hasn't resolved it — never as default compute spend. When invoked, in priority order:

1. **Limit checks** — sign convention and trivial-parameter limits via `.knowledge/limits.md`.
2. **Symmetry** — conserved quantities respected; expected sector occupied.
3. **Convergence** — bond-dim / basis-size / Trotter-step / bath-size sweeps that asymptote.
4. **Internal consistency** — energy variance small relative to E².
5. **Cross-method validation (when feasible)** — re-run with an independent method (e.g. DMRG + imaginary-time TEBD, an ED cross-check via `/method-ed`, or LTRG vs QMC at finite temperature) and confirm agreement within both methods' accuracy budgets. Disagreement → setup error or insufficient convergence in one method.
6. **Literature comparison (when a published reference exists)** — compare against the published value, and for contested values against the literature *range*, not a single number.

When the problem is in a frontier regime (frontier flag in the card), search recent literature before interpretation — a tailored query with `<lattice> <model> <regime>` — so the agent's conclusion sits inside the current debate, not outside it.

## Writeup handoff

After verification completes for a model card workflow, surface the writeup handoff as a final step. The default deliverable is two artifacts:

1. **Consolidated runnable script** — all parameters explicit, the calculation reproducible from a fresh checkout against the harness's installed stack.
2. **Short run report** — setup, settings, result, verification status (limit / symmetry / convergence / cross-method), residual uncertainty.

After the artifacts are in hand, if the user wants to publish, present, or share, render the run into a self-contained HTML report (figures included) via `/report`.

The handoff is offered, not forced. If the user just wants the result, that's a complete session.

## Future directions

Out of scope for the current harness, added as new skills only when real problems demand them:

- Real-time dynamics (`S(q,ω)`, quench dynamics, ETH).
- Open quantum systems (Lindbladian dynamics, dissipation).
- Topological order beyond spin liquids (SPT, fractons).
- Continuum-limit / field-theory methods (CFT identification, fuzzy sphere, RG).
- Empirical method-on-problem lore (per-problem bond-dim / size / failure-mode notes).
- Composition layer for multi-aspect research questions.

Do not preemptively scaffold these. When a real problem creates the demand, add the corresponding skill (and KB cards) following the same problem-driven design.

## Compute resources

The harness can use a remote cluster profile at `skills/using-slurm/profiles/active.toml` for any task larger than a few minutes of local compute. **Compute feasibility is decided BEFORE the first run**, not discovered after watching a local process for an hour.

Before launching any non-trivial computation:

1. **Estimate the cost up front.** For dense ED: D² × 8 bytes is the matrix memory; wall ≈ O(D³) / aggregate-GFLOPS. For DMRG: χ² × L × 8 bytes is the MPS, wall ≈ #sweeps × (D × χ³). For QMC: per-MCS cost × n_MCS × n_chains.
2. **Pick local vs remote with a clear threshold:**
   - Local: < 10 min wall, < 16 GB resident, fits within normal use of one CPU node.
   - Remote sbatch: everything else.
3. **Read the cluster card BEFORE picking a partition.** `skills/using-slurm/profiles/<active>.toml` lists partition memory / core / wall caps and recent usage notes. The default partition is a hint, not authority — an idle partition that matches needs beats a contested default. Concrete example: the Turner 2018 reproduction had L=30 dense ED take ~50 min locally vs ~10 min on a 64-core cluster node, and L=32 was infeasible locally entirely. That asymmetry should be caught BEFORE the first local run.
4. **Compose with `/using-slurm`** (single-job or array) and `/parameter-scan` (multi-axis grids). The cluster mechanism handles ship-code → submit → monitor → fetch end-to-end.

NEVER run a multi-hour calculation locally because the agent forgot the cluster exists. The cluster IS the default for non-trivial compute; declare a deviation if local-only is actually justified.

## Repository Layout

- Scripts: `scripts/` — atomic shell helpers and generated runnable calculations
- Skills: `skills/` — conversational workflows (managed by Ion)
- Method-level skills: `skills/method-*/SKILL.md` — method insight and tool-skill selection for challenge tracks.
- Software stack skills: `skills/<stack>/SKILL.md` with machine-readable setup in `skills/<stack>/stack.toml`.
- Cluster profiles: `skills/using-slurm/profiles/` — per-cluster defaults (partitions, sbatch idioms, modules) consulted by cluster-aware skills via `skills/using-slurm/profiles/active.toml` symlink or `HARNESS_CLUSTER_PROFILE=<name>` env var. Skills stay cluster-agnostic; cluster specifics live in profile cards.

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

- Run `make skills` at the start of setup to install/sync Ion-managed workflow skills. Tell the user this is the baseline skill sync before domain-tool installation or workflow-specific setup choices.
- Install domain tools with `make install <tool>` after the active workflow or user has selected that tool. Running `make help` lists the currently installable tools.
- Adding a new installable tool: append its name to the `INSTALLABLE` variable in the `Makefile` and add a matching `install-<tool>` recipe. Keep recipes idempotent (check before installing).
- When suggesting a command that requires a tool, first check that tool is in `INSTALLABLE` (and installed) — otherwise tell the user to run `make install <tool>` before proceeding.

<a id="ui-ux"></a>
## UI/UX

### Output norms — users' attention is expensive

- **Remember there is a human on the other side.** Keep interactions precise and concise. Never assume the user has the same context as the agent or any subagent.
- **Plain English in user-facing messages.** Internal harness vocabulary (`cell`, `manifest`, `route`, `deviation`, `run.json`) stays in artifacts and code, not in user prompts. Paper-, model-, or method-specific abbreviations that are non-standard for this field (PXP, FSA, RVB, AKLT, …) get a one-sentence plain-English introduction on first use; common method families (ED, DMRG, QMC, VMC, NQS) need no introduction. Other jargon, if necessary, gets defined when first used. Avoid undefined abbreviations, internal workflow labels, raw logs, and compressed jargon. Define non-standard abbreviations inline on first use, e.g. `forward-scattering approximation (FSA)` or `PXP chain (Rydberg blockade model)`; after that, the abbreviation may be used.
- **Maintain a reader trace during long workflows.** Every user-facing update, setup card, report caption, and final result should preserve the user's narrative thread: what object is being worked on, what it means, what evidence was produced, and what consequence follows. A reader trace usually names the **object** (paper, figure, model, file, package, command, or result), the **meaning** in plain domain language, the **evidence** (number, residual, source, plot, runtime, artifact), and the **consequence** (confirmed, changed, blocked, or next choice). Name the concrete paper, file, tool, command, or result before discussing it; do not rely on shorthand, hidden session context, or agent-only labels.
- **Do not dump walls of checklists, verification details, convention notes, or method-card content** unless the user explicitly asks.
- **Avoid walls of words.** Each message is terse — a few sentences or a compact table covering key points, no overload. Keep each turn compact; when more is required by a skill, split it into one decision at a time with 2–3 options, concise pros and cons, and one recommended option when technically justified. When a skill requires source confirmation, setup cards, or proposal approval, present the required material compactly and one decision at a time.
- **Decision gates need anchors.** For approval, setup, install, configuration, routing, or compute choices, give a **mental/logical anchor** first: why this decision exists and what consequence it changes. Then give a **visual anchor**: bold only the key consequence phrase(s), not the whole sentence. Shape the prompt as **why → consequence → escape hatch → ask**.
- **Consequential notices need anchors.** For source-fixed facts or technical necessities where there is no real choice, do not fake a fork. Still surface why the step follows, what consequence it changes, and how the user can correct it. Shape the notice as **because → consequence → correction line → proceed**.
  - Examples:
    - Source-material setup: "This task may need source material beyond the local KB. I can install PDF-to-Markdown tools for **cleaner PDF extraction** and **extracted figures**; skipping is fine if local notes are enough. Install PDF rendering tools?"
    - Cluster setup: "This task may need remote compute. I can capture the cluster config now so future jobs can submit without re-asking; local-only is fine if you want to start small. Configure a cluster?"
- **Report results in ≤3 lines + a plot.** Primary quantity, verification status, one-line reasoning. Plot the produced result or an already-collected diagnostic so the user has visual evidence. Do not run extra convergence sweeps, stability checks, or cross-method validation unless verification has been explicitly requested.
- **Use option UI at genuine forks** — pre-action branches and post-result next-steps. Use an interactive option UI when available; otherwise use numbered options. At a real fork, think faithfully like a human: surface 2–3 options with pros / cons and the recommended one (the Superpowers brainstorming pattern in UI form). Each option: short label + one-line with pro and con. Recommended option first, labeled "(Recommended)". Example:
  - `"Primary method (Recommended)"` — "Matches the paper's route most closely; uses the declared compute budget."
  - `"Independent check"` — "Catches setup mistakes; usually restricted to a reduced instance."
  - `"Source audit first"` — "Cheaply anchors expectations; no new computed data."
- **For final results, lead with the answer.** "quantity = value, converged, matches declared reference" — not "I checked 5 things and here they are." During planning or reproduction setup, lead with the current decision and the recommended option's reason.
- **Surface generated artifacts.** When a workflow creates scripts, data, plots, or reports, save them where that workflow specifies and show the user the artifact paths plus the one-line run command. Never make the user ask for the script.
- **Flush stdout after each progress line in any long-running script.** Block-buffered stdout (the default when redirected to a file, a slurm log, or any non-TTY sink) hides progress until the process exits — looks like a hang. Julia: `flush(stdout)` after each `println` / `@printf`. Python: `print(..., flush=True)` or `python -u`. Pair with per-cell incremental writes (manifest after each cell) so a kill or sleep loses at most one cell. Sbatch-side helpers (`srun --unbuffered`, `stdbuf -oL`) belong in cluster profiles (`skills/using-slurm/profiles/<name>.toml`), not in scripts.
- **Long iterative computes must emit intermediate estimates, not just final values.** A multi-hour run without progress output is a blind spot: the user cannot sanity-check whether the running estimate, error proxy, acceptance/progress counters, or convergence diagnostics are stabilizing. Print a partial estimate every K steps, where K is chosen so the user sees roughly 10-50 updates over the run. The script's standard runner enforces this via a `progress_every` knob; method cards declare a sensible default.
- **Monitor before declaring success — don't fire-and-forget remote actions.** A "RUNNING" status / a 0 exit code from `ssh` is not success; only verified output is. After any non-trivial remote action, stay engaged through a *settle-time* before reporting "✓ done":
  - **Lightweight tasks** (env setup, install, instantiate, single ssh command): tail output in real-time. If silent for >30 sec on a non-precompile command, suspect (PATH issue, hung lock, missing prereq).
  - **Cluster jobs**: cluster-specific settle-time discipline (partition selection from queue card, `PD → R` transition check, first-cell log tail, multi-hour periodic checks) lives in `skills/using-slurm/SKILL.md`. Compose with `/using-slurm` instead of inlining the rules here.
  - **Multi-hour local jobs**: periodic log checks every 30–60 min. Surface progress via short status lines, not silence.
  Settle-time scales with how far the job has to go before producing meaningful output. The cost of an extra 1–3 min of monitoring is much less than the cost of returning hours later to find 28 cells silently failed in the first minute — or that all 28 cells are still queued.
- **Caveat-after, not caveat-first.** For contested regimes, state the consensus framing first, then qualify the unresolved point. Never open with the hedge.
- **One question at a time** when questions are needed; prefer `AskUserQuestion` with options over open-ended text.

### Terminal Formatting

- Short bullet lists over prose paragraphs.
- Tables for comparisons.
- Blockquotes for single confirmations.

### Equation Rendering

Chat messages use **UTF-8 unicode math on every surface** (reports render LaTeX via MathML; plots use matplotlib mathtext):

- **Always UTF-8 unicode math in chat** — `⟨ψ|H|ψ⟩`, `E₀/N = −0.4438`, `J₂/J₁ ≈ 0.5`, `gap Δ`, `S=½`, `Σ ∏ √ ⊗ † ≤ ≥ ± ∞`. Renders on any surface.
- **Never emit `$…$` LaTeX in chat.** This harness always runs as **Claude Code**, whose chat panels (terminal, VS Code, desktop app, claude.ai/code) do **not** render `$…$` — they show literal `$` and backslashes. (The conversational claude.ai app *does* render LaTeX, but it is not a Claude Code surface and never the agent's output target here.) LaTeX lives only in the HTML report (→ MathML) and matplotlib mathtext.
- **`CLAUDE_CODE_ENTRYPOINT` still distinguishes terminal vs GUI — for image embedding only** (`cli` = terminal → open files with `open`/`xdg-open`; `claude-desktop`/web/IDE = GUI → embed images inline as markdown). It is **not** a signal for math rendering.
- **Skill cards and reference docs store math in unicode/plain** (`K_c`, `S_α`, `⟨·⟩_V`), surfaced to the user as-is.

## Agent guidelines

Agents working in this project should:
1. Use existing `skills/`, `scripts/`, Makefile targets, and `.knowledge/` cards rather than reimplementing operations.
2. Run `make help` to discover available workflow targets.
3. Check `Ion.toml` (or `ion` CLI) for installed / available skills.
4. For methodology references, use `download-ref`; keep different methods in different `.knowledge/literature/<method>/` folders and never commit `.raw/` or `.figures/`.
5. Install Ion skills with `make skills`; install heavy domain tools only after the active workflow or user selects that tool. Before recommending a tool-dependent command, verify the tool is in `INSTALLABLE` and expose install/setup as a user-facing option when it affects the plan.

## Daily Workflow

Run `make help` to see available Makefile targets. Run `make test` to execute the
Python script test suite (`scripts/tests/`) with coverage.

## Reliable update sources

Runtime config for the weekly advisor (`.cryo/` chamber and the
`zlp-harness:zlp-advisor` skill read this section). Provisional — refine as the
harness's active threads settle.

- Source types: arXiv preprints, DOI/publisher pages, group/lab pages, code
  releases, and web search over reliable/primary sources.
- arXiv queries / categories (`cond-mat.str-el` first, then `quant-ph`):
  - `DMRG OR "matrix product state" frustrated magnet`
  - `PEPS OR iPEPS OR CTMRG "tensor network" 2D`
  - `"quantum Monte Carlo" OR "stochastic series expansion" Hubbard OR Heisenberg`
  - `"neural quantum state" OR "variational Monte Carlo" lattice`
  - `"exact diagonalization" OR Lanczos "quantum many-body scars"`
  - `J1-J2 OR kagome OR triangular "spin liquid"`
- Web-search keywords:
  - DMRG bond-dimension extrapolation
  - iPEPS 2D Heisenberg
  - quantum Monte Carlo sign problem Hubbard
  - neural quantum states frustrated magnetism
  - tensor-network contraction algorithms
  - quantum many-body scars PXP
  - spin-liquid numerical evidence
- People / groups to watch (method contributors, per `README.md`):
  - Chen Cheng (程晨) — exact diagonalization.
  - Wei Li (李伟) — MPS / LTRG / DMRG / TEBD.
  - Hai-Jun Liao (廖海军) — PEPS / CTMRG.
  - Ming-Pu Qin (秦明普) — quantum Monte Carlo.
  - Yan-Tao Wu (武琰涛) — Monte Carlo renormalization group.
  - Shi-Xin Zhang (张士欣) — quantum circuit simulation.
  - Kun Chen (陈锟), Jin-Guo Liu (刘金国) — AI agent / knowledge base.
- Venues: PRX / PRX Quantum, PRB, PRL, Quantum, Nature Physics, SciPost Physics.
- Other reliable sources:
  - <https://arxiv.org/list/cond-mat.str-el/new> — daily strongly-correlated preprints.
  - <https://arxiv.org/list/quant-ph/new> — daily quant-ph preprints.
  - Release notes for the method stack (ITensors.jl, MPSKit.jl, PEPSKit.jl,
    TeNPy, NetKet, TensorCircuit-NG, XDiag.jl) when a discussion depends on a
    feature or version.
- Avoid:
  - unsourced social posts, SEO blogs, and generic news summaries unless the
    user explicitly asks.

## Cryochamber (`.cryo/`) — autonomous weekly advisor

A [cryochamber](https://github.com/GiggleLiu/cryochamber) is parked at `.cryo/`
to run the local advisor workflow automatically every **Monday 09:48
Asia/Shanghai** (staggered after the other harness chambers on this machine). It
wakes, runs the self-contained workflow in `.cryo/plan.md`, posts the digest to
the `weekly advisor` topic on the `ManyBodyHarness` stream, and hibernates. The
plan never terminates; only `cryo cancel` stops it.

The Monday digest is minimalist by design: a header line, a status-tagged
`TODOs` audit, and `Key reads (≤3)` (papers from the last 7 days, or a ≤3-year
paper tied to a recently discussed topic). The chamber reads its "Reliable
update sources" from the section above and never calls Claude Code plugin skills
— it runs unattended under `opencode`, so the weekly path is fully
self-contained.

The chamber **design** (`plan.md`, `cryo.toml`, `README.md`) is committed; the
chamber **runtime** (`messages/`, `*.log`, `timer.json`, `todo.json`,
`NOTES.md`, `.cryo/.cryo/` socket dir) is gitignored as per-machine state. Only
one collaborator's machine should run the daemon at a time, otherwise the digest
gets posted twice. If you ever put real API keys in `cryo.toml`'s `[provider]`
table, gitignore it first.

### Common chamber commands

Run from the chamber directory (`cd .cryo` first):

```sh
cryo status         # is the daemon alive? when does it next wake?
cryo log            # daemon log
cryo watch          # live-tail the current session
cryo receive        # read accumulated outbox messages
cryo restart        # pick up edits to cryo.toml or plan.md
cryo cancel         # stop the daemon and drop the pending TODO
cryo start          # first-time launch (fires a no-op bootstrap session)
cryo send "<text>"  # nudge the agent between Mondays (watch_inbox=true)
```

`cryo start` fires a bootstrap session that only schedules the next
Monday-09:48 run, so starting on a non-Monday will not double-post.
