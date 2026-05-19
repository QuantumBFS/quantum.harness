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

Skills must be organized around problems, not lessons, methods, tools, metrics, or roadmaps.

Use this canonical split:

```text
tools/skills/problems/
  models/
  physics/
```

`models/` contains canonical Hamiltonian or Hilbert-space problem families.
`physics/` contains cross-model organizing questions: phases, mechanisms, dynamics, solvability, and diagnostics.

Ion may expose direct `tools/skills/<name>` symlink aliases for installation. Edit the nested `tools/skills/problems/...` source directories, not the aliases.

Methods such as DMRG, DMFT, QMC, VMC, fuzzy sphere, and V-score belong inside problem workflows, not in problem names. Do not create a separate visible method-skill taxonomy by default. If a problem skill mentions a method, it should include enough method, software, setup, output, and validation guidance for an agent with no chat history to act sensibly.

Dimension, lattice, filling, doping, boundary condition, disorder strength, and coupling regime are runtime choices unless they define a truly distinct canonical problem.

## Knowledge Base Role

`knowledge-base/` carries data and method-level reference. It is not a curriculum, reading path, or task catalog.

Current cards:

- `conventions.md` — sign / normalization defaults; Hamiltonian forms.
- `limits.md` — exact reductions and known limits (U=0, U→∞ → t-J, XXZ Δ=1, …).
- `benchmark-numbers.md` — reference E/N, gaps, order parameters with citations.
- `symmetry-cheatsheet.md` — conserved quantities, lattice point groups.
- `magic-conventions.md` — Pauli / clock-shift conventions, SRE definitions, partition modes, qudit generalizations, Wegner-duality SRE preservation.
- `magic-benchmarks.md` — reference SRE / long-range-magic values across canonical models, reported as literature ranges.
- `methods/{ed,dmrg,qmc,ctmrg,tebd,vmc-nqs,vqe,spectral,finite-t,pauli-markov,ttn}.md` — per-algorithm notation, code shape, knobs, pitfalls. `ed.md` uses Julia XDiag with QuSpin as a Python fallback reference. `vqe.md` uses TensorCircuit-NG on a preinstalled JAX backend. `qmc.md` uses Julia SSE/Carlo; `ctmrg.md` uses Julia PEPSKit. `vmc-nqs.md` uses Python/NetKet. `spectral.md` and `finite-t.md` are stubs (pointers only, no tested recipe).
- `literature/<method>/` — rendered methodology references organized by method, each with its own `INDEX.md`. Raw PDFs, Semantic Scholar metadata, and extracted figures live in local-only `.raw/` / `.figures/` subfolders and must remain gitignored.
- `2302.04919-variational-benchmarks.md` — V-score paper notes.

Skills cite these cards; they never hardcode the data. New cards land when a real skill begins citing them.

**Paper reproduction evidence invariants.** These are harness-wide rules, not `/reproduce-paper` implementation details:
- Written content is evidence, not authority. `knowledge-base/` cards, rendered notes, scripts, summaries, and prior run artifacts are cached hints.
- Evidence authority MUST be explicit: `primary` (paper, supplement, official code/data), `trusted_reference` (analytic / exact / independent check), `current_run` (fresh artifact with matching protocol and script provenance), `hint` (KB, notes, old scripts/plans/data/figures), and `assumption` / `deviation`.
- MUST quarantine hints. Hints may guide planning, but they cannot close a reproduction claim unless re-confirmed against a primary source or regenerated as current-run evidence.
- Primary sources control paper reproduction: paper PDF, supplement, and official code/data when available. If a primary source conflicts with a KB card, the primary source controls; emit a KB diff and proceed from the primary-source-derived claim.
- KB-sourced reproduction claims MUST either be confirmed against a primary source or marked as explicit unverified assumptions in the run report.
- DO NOT silently weaken the target. Any change in paper-declared setup, implementation route, data-generation route, constraints, budget, or uncertainty method must be recorded as a deviation before it can support a reproduction claim.
- Method-agnostic does not mean method-optional. Every executable reproduction cell MUST declare `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`. `route` is one of `paper`, `canonical`, `fallback`, or `deviation`; method and stack names are data values, never `flow` vocabulary. A non-paper / non-canonical / non-fallback stack is a `deviation` before it is a result.
- Tool availability is not route authority. DO NOT probe, select, or start implementing a fallback stack because the canonical stack has an environment error. First record the canonical route state as failed/pending, then declare `fallback` or `deviation` in the protocol before touching the alternate stack. A fallback stack must be the method card's next recommended stack, not any installed language package.
- `flow` is a ledger, not a method or software selector. DO NOT use `flow` gates, attempt roles, or check kinds to choose or rename the scientific stack.
- DO NOT use first-cell provenance. Per-cell run-spec overrides are allowed, but assembly must validate each manifest against the merged shared+cell settings and provenance, then report settings as constant vs varying. Never summarize a correctness-affecting setting, budget, or uncertainty rule from the first completed manifest unless a manifest-consensus check has proved it is global.
- Failed checks block claims. A failed protocol, script, command, manifest, freshness, consensus, numeric, or result check stops the workflow until repaired, scoped down, or recorded as a justified assumption/deviation.
- Failed checks MUST enter the correction loop: classify the mismatch, locate the earliest wrong layer, revise that layer, invalidate downstream artifacts, rerun affected gates, then re-verify.
- Repairs are evidence. Any correction after a failed gate or contract-changing edit MUST record a `repair` with `from`, `wrong`, `changed`, `invalidate`, and `state`; close cannot rely on artifacts from invalidated gates until those gates rerun.
- Use artifact-scoped subagents, not permanent domain personas: source/protocol, plan/run-spec, script, result, mismatch, and close reviewers each receive the primary source context and exact artifact under review. KB-only review cannot close a scientific gate.
- `/verify` MUST SPAWN a real host subagent. Do not roleplay the verifier, write the verifier report yourself, invent a reviewer id, or finish an audit from a self-authored review. If the host cannot spawn a verifier, stop with `blocked: verifier subagent unavailable` and leave the gate open.
- The agent that writes or materially edits a reproduction protocol, script, check command, aggregator, or result report cannot be the sole verifier of that artifact. Self-checks catch syntax and smoke failures; independent `/verify` or separate-agent review closes the verification loop.
- Stale artifacts or artifacts missing required provenance cannot support conclusions. Remote job status, `ssh` exit status, and scheduler `COMPLETED` state are operational facts only; fetched manifests and checks are the evidence.

**Provenance discipline.** Every numerical anchor on a KB card must carry one of three tags: *Literal* (a verbatim passage from a rendered literature file under `knowledge-base/literature/<method>/`, with line number), *Analytic* (closed-form derivation from a stated definition or limit), or *Harness anchor* (verified empirical value from a tagged run in this repo, with a cross-check method named). Untagged numerical entries are not benchmarks. The `/verify` primitive (in `kb-card` mode) cross-checks each tag against its declared source — invoke it during `/reproduce-paper` before compute, and as a pre-commit gate after editing a KB card.

## Skill shapes

Two shapes, both problem/research-driven:

- **Model skills** (`tools/skills/problems/models/*`) drive calculations: `Diagnose → Workflow → Method recommendations → Branch table → Verification`.
- **Physics skills** (`tools/skills/problems/physics/*`) evaluate evidence: `Diagnose → Evidence to gather → Cross-checks → Interpretation rules → Model hooks`.

Skills cite KB for any number, convention, or method-specific code shape. Skills hold workflow only — no hardcoded numbers, no embedded code skeletons, no canonical recipes.

## Verification practice

Default verification, in priority order:

1. **Limit checks** — sign convention and trivial-parameter limits via `knowledge-base/limits.md`.
2. **Symmetry** — conserved quantities respected; expected sector occupied.
3. **Convergence** — bond-dim / basis-size / Trotter-step / bath-size sweeps that asymptote.
4. **Internal consistency** — energy variance small relative to E².
5. **Cross-method validation (when feasible)** — re-run with an independent method (e.g., DMRG + TEBD imaginary-time) and confirm agreement within both methods' accuracy budgets. Use ED only after `knowledge-base/methods/ed.md` is rebuilt. Disagreement → setup error or insufficient convergence in one method.
6. **Benchmark comparison (when published reference exists)** — `knowledge-base/benchmark-numbers.md`. For contested values, compare against the literature *range*, not a single number.

When the problem is in a frontier regime (frontier flag in the skill), invoke the `arxiv-search` skill before interpretation: a tailored query with `<lattice> <model> <regime>` should return recent literature so the agent's conclusion sits inside the current debate, not outside it.

## Writeup handoff

After verification completes for a model skill, surface the writeup handoff as a final step. The default deliverable is two artifacts:

1. **Consolidated runnable script** — all parameters explicit, the calculation reproducible from a fresh checkout against the harness's installed stack.
2. **Short run report** — setup, settings, result, verification status (limit / symmetry / convergence / cross-method), residual uncertainty.

After the artifacts are in hand, if the user wants to publish, present, or share, route to:

- `scientific-writing` / `latex-paper-en` — paper text.
- `scientific-visualization` — figures.
- `jupyter-notebook` — interactive companion.

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

Default stack: **Julia + ITensors.jl** (ITensors.jl, ITensorMPS.jl, MPSKit.jl, KrylovKit.jl). Install via `make install julia && make install itensors`. Method cards in `knowledge-base/methods/` use this stack for canonical code shapes.

Python (`quimb` + `cotengra`) remains available as a fallback for tensor-network sketches via `make install quimb`. Skills can route to either when both work; method cards are Julia-flavored.

## Installed Skills

UX skills:
- **onboard** — first-touch intake, domain setup, route to problem skill
- **solve** — interactive problem-solving loop: intake → act → report → next-steps → loop

Local problem skills:
- **models:** transverse-field-ising, heisenberg, j1-j2, t-v, hubbard, t-j, anderson-impurity, multiorbital-hubbard, spin-1-xxz, potts-clock
- **physics:** criticality, frustration, spin-liquid, mott-transition, kondo-effect, magic, confinement

Problem-solving primitives (generic; topic-agnostic, compose with the problem skills above):
- **parameter-scan** — sweep one or more declared axes for any produced quantity. Composes with `/slurm` for cluster execution.
- **scaling-fit** — finite-size collapse, exponent extraction with uncertainty.
- **cross-method-check** — verify the same observable with an independent method or diagnostic.
- **slurm** — agent-does-ssh cluster mechanism: ship code, submit (single or array), monitor, fetch. Reads cluster specifics from `tools/cluster/<active>.md`. Dispatches `/setup-julia` when the cluster's Julia env isn't instantiated. Does NOT know about parameter grids — that's `/parameter-scan`'s job.
- **setup-julia** — install Julia (juliaup or `module load`), configure package mirror (defaults to Chinese mirror if cluster `region == mainland_china`), instantiate the project env. Generic over target (local laptop or remote ssh alias). Idempotent.
- **reproduce-paper** — orchestrate end-to-end paper reproduction: plans the figure dependency graph, surfaces methodology / verification / cross-check figs alongside substantive ones, composes the primitives above. Generic over papers. Absorbs the writeup-handoff close (declared entry + run report).
- **verify** — MUST SPAWN a high-effort independent review subagent to audit an artifact against its declared reference. Modes: `protocol` (TOML claims vs primary sources), `plan` (plan/run-spec vs protocol), `kb-card` (anchors vs literature), `script` (script vs protocol and paper methodology), `result` (produced artifacts vs declared references), `mismatch` (failed gate triage), `close` (final report / declared entry / manifests vs protocol). Inspection-only; emits a structured diff report. Compose with `/reproduce-paper` (protocol, plan, per figure, mismatch, and final report) and as a pre-commit gate after changing important artifacts.

External/support skills:
- **quimb-tensor-network** — quimb/QuTiP tensor network: MPS, PEPS, DMRG, TEBD
- **arxiv-search** — Semantic arXiv search via Valyu
- **jupyter-notebook** — Scaffold and edit .ipynb notebooks
- **sympy** — Symbolic math: Hamiltonians, commutation relations, algebra
- **scientific-visualization** — Publication-quality figures (matplotlib/seaborn/plotly)
- **scientific-writing** — Scientific manuscript drafting
- **latex-paper-en** — LaTeX academic paper writing
- **download-ref** — Add arXiv/DOI/book methodology references under `knowledge-base/literature/<method>/`; rendered markdown is tracked, raw PDFs/metadata/figures are local-only.
- **julia** — Julia development guidance, multiple dispatch, performance

## Tool Hierarchy

- CLI tools: `tools/cli/` — atomic shell scripts
- Flow state: `tools/flow/` — generic Rust gate ledger for multi-gate, multi-agent, or remote workflows. It records append-only `progress/events.jsonl` and derives `progress/state.toml`; use one child flow per independent paper/run and a parent flow only for aggregate campaign gates.
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

- `make setup` performs the **minimum bootstrap only** — it installs Rust/Cargo if needed and builds core harness CLI tools such as `tools/cli/flow`. It does NOT install Ion skills or heavy domain tools. Use `make skills` for Ion-managed skills and `make doctor` for a read-only core readiness check.
- Install domain tools **on demand** with `make install <tool>`. Running `make help` lists the currently installable tools.
- Adding a new installable tool: append its name to the `INSTALLABLE` variable in the `Makefile` and add a matching `install-<tool>` recipe. Keep recipes idempotent (check before installing).
- When suggesting a command that requires a tool, first check that tool is in `INSTALLABLE` (and installed) — otherwise tell the user to run `make install <tool>` before proceeding.

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
  - **Sbatch grid submission**: 1–3 min settle-time. `squeue` "RUNNING" alone is not success — tail at least one cell's log to confirm real compute progress or manifest writes are happening. Catches early failures (PATH issues, wrong binary, missing modules, OOM-at-startup) before they multiply across the grid.
  - **Multi-hour jobs**: periodic log checks (every 30–60 min). Surface progress to the user via short status lines, not silence.
  Settle-time scales with how far the job has to go before producing meaningful output. The cost of an extra 1–3 min of monitoring is much less than the cost of returning hours later to find 28 cells silently failed in the first minute.
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
5. For methodology references, use `download-ref`; keep different methods in different `knowledge-base/literature/<method>/` folders and never commit `.raw/` or `.figures/`.
6. Treat `make setup` as **core bootstrap only** — install Ion skills with `make skills` and heavy domain tools on demand via `make install <tool>`. Before recommending a tool-dependent command, verify the tool is in `INSTALLABLE` (and installed); if not, instruct the user to run `make install <tool>` first.

## Daily Workflow

Run `make help` to see available Makefile targets.
