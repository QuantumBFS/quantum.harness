---
name: solve
description: Use when the user brings a concrete quantum many-body research problem — phrases like "ground state of Heisenberg N = 20", "is kagome a spin liquid", "Hubbard at U/t = 8", "compute the gap for TFIM at h = 1", "what does VMC give for J1-J2 at 0.5". Also fires when `/onboard` routes here or when the user pivots to a new problem mid-session.
---

# Solve

The main interactive skill. Drives the conversation from problem intake to verified result to next steps. Uses the Superpowers brainstorming pattern at every decision point.

## Audience definition (binding)

<audience name="binding">
The active user is mid-research, technical, expects 3-line answers and a plot. They have NOT memorized the model/physics/method card library. They expect zero pre-flight questions when defaults are obvious. They expect every post-result option to be real (executable, not padding).
</audience>

## When to activate

- User states a concrete QMB problem ("ground state of Heisenberg N=20", "is kagome a spin liquid", "Hubbard at U/t=8").
- After `onboard` routes here.
- Any time the user brings a new problem mid-session.

## Loop

```
Intake → Match skill → Act → Report → Next-steps → (user picks) → Act → Report → ... → Done
```

## Flow / audit contract

<invariants name="flow">
- Every `/solve` result is flow-backed. Computed and interpretive claims close only after `tools/cli/flow require <run> audit` exits 0.
- Use `tools/flow/templates/solve.toml`: `run -> audit -> close`.
- `run` is a `run` attempt that registers the result artifact(s).
- `audit` is a spawned subagent attempt. Self-audit, roleplayed review, or invented reviewer id is invalid.
- The audit check uses `kind = "audit"`, `mode = "solve"`, `coverage = true`, and one-word `items` appropriate to the claim. Default items: `setup`, `limits`, `symmetry`, `convergence`, `claim`.
- The audit sidecar contains typed fields: `status`, `mode`, `target`, `hash`, `author`, `reviewer`, `brief`, `coverage`, and `[[items]]`.
- If no subagent is available, stop with `blocked: verifier subagent unavailable`; do not present the result as verified.
- Final user-facing report happens after the audit gate passes. If a turn ends earlier, emit `tools/cli/flow status <run>`.
</invariants>

Minimal solve protocol shape:

```toml
[[checks]]
id = "run"
kind = "exists"
gate = "run"
paths = ["result.json"]

[[checks]]
id = "audit"
kind = "audit"
gate = "audit"
mode = "solve"
target = "result.json"
coverage = true
items = ["setup", "limits", "symmetry", "convergence", "claim"]

[[checks]]
id = "close"
kind = "exists"
gate = "close"
paths = ["run-report.md"]
```

### 1. Intake

<instructions name="intake">

Infer the problem from the user's prompt. Defaults are clear if the user named a specific model (e.g., Heisenberg N=20) AND the model card's diagnose section maps directly to one method recommendation. In that case, run the calculation without any pre-flight question. Ask exactly one `AskUserQuestion` only when the prompt could match two or three distinct model cards OR two or more distinct method recommendations on the same card.

</instructions>

### 2. Match skill

<instructions name="match-skill">

Find the matching model card (`knowledge-base/models/<name>/MODEL.md`) and any relevant physics card (`knowledge-base/physics/<topic>/PHYSICS.md`). Read the card's Diagnose section for canonical defaults. Read the method recommendation table for which method card to use, then read that method card's canonical software stack and `tools/software/stacks/<stack>.toml` install contract.

If the problem hits a branch table redirect (e.g., dynamics → `spectral.md`, finite-T → `finite-t.md`), follow it immediately.

</instructions>

### 3. Act

<instructions name="act">

Run the calculation without narrating the process to the user (no "Now I am setting up DMRG…", no "Sweep 1 complete…"). The user sees the final report only. Tool calls and computation should still flush their own progress to stdout/logs per the harness's progress-flush rule.

Initialize a solve flow before claim-producing work: `tools/cli/flow init results/<run> --template tools/flow/templates/solve.toml`. Use the method card's code shape. If the canonical stack is missing, install the selected stack profile first; for remote runs, let `/slurm` run the profile's smoke test in the declared place (`login` or `compute`). Auto-generate a convergence plot. Save script to `scripts/` and results to `results/`.

After the run attempt finishes, spawn the audit subagent with the artifact, protocol, model/method cards used, and the exact claim to audit. The brief includes: *"Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."* Finish the audit attempt with `--report verify/verify_<artifact>_<date>.md`; do not report the result to the user until the audit gate passes.

<checklist name="branch-rules">

- Frontier problems (the matching card has a `frontier` flag): dispatch `arxiv-search` BEFORE compute. Treat the literature summary as the solve result, run it through the `solve` audit gate, then report it. Offer compute as a next-step option in step 5, not as part of step 3.
- Off-scope problems (no model or physics card matches): follow the closest-card's stub instructions, OR present 2-3 candidate redirections via `AskUserQuestion`. Never silently run a calculation outside the card library.
- Stub-redirect problems (card's branch table sends you elsewhere): follow the redirect immediately.

</checklist>

</instructions>

### 4. Report

<instructions name="report">

Per [AGENTS.md → Output norms](../../../AGENTS.md#ui-ux) (≤3 lines + plot; embedded one-line reasoning).

First line must be audit state. If `tools/cli/flow require <run> audit` has not passed, do not present the claim as final; emit `tools/cli/flow status <run>` and the blocker instead.

<example name="report bad">
I ran DMRG on the Heisenberg chain. I set D=200 and the energy converged. I then cross-checked with ED and the values agree well. The Bethe ansatz value at infinite size is around -0.4431, which is consistent given finite-size effects.
</example>

<example name="report good">
E/N = -0.4341 via DMRG (1D chain, D=200, converged). Cross-checked with ED — agrees to 5 digits. Bethe ansatz ≈ -0.4431 at thermodynamic limit — finite-size correction consistent. ✓
</example>

Show the run command: `julia --project=julia-env scripts/<name>.jl`

</instructions>

### 5. Next-steps

<instructions name="next-steps">

User-facing forks → [AGENTS.md → Output norms](../../../AGENTS.md#ui-ux) (AskUserQuestion; 2–3 options; recommended first; Done always real).

Common next-steps (pick the 2 or 3 most relevant — and ALWAYS include Done as one of the slots). The filter is genre, not laziness: if a parameter scan, a visualization, AND a cross-method check are all real follow-ups, pick the two with the highest information-per-compute and Done, not the single most obvious. When uncertain whether an option is relevant, include it; the user does the final filter by clicking.

| Option | When to offer |
|---|---|
| Visualization (correlations, structure factor, publication figure) | Always after a ground-state calculation. |
| Parameter scan (U/t sweep, J2/J1 sweep, finite-size extrapolation) | When the user has one data point and the natural next step is a sweep. |
| Deeper analysis (gap, entanglement, order parameter) | When the ground state is done but the physics question isn't answered. |
| Cross-method check (DMRG ↔ TEBD, DMRG ↔ VMC) | When verification is thin or the problem is hard. |
| Literature context (arxiv-search) | When approaching a frontier regime. |
| Writeup (declared entry + run report → writing skills) | When the user seems done with computation. |
| Different problem | When the user pivots. |
| Done | Always. |

</instructions>

### 6. Loop

<instructions name="loop">

User picks a next-step → go to step 3 (Act) with the new task. Repeat until the user picks "Done" or pivots to a different problem (restart from step 1).

</instructions>

### 7. Done

<instructions name="done">

Step 7 fires when the user picks Done from the next-steps options, OR types an explicit stop phrase ("I'm done", "that's it", "stop here", "enough for today"). Do not enter step 7 just because the conversation has been quiet — the loop in step 6 is the default; step 7 is an explicit exit.

When the user stops:
- Save a one-paragraph session summary to `results/session_summary.md`.
- List all scripts and results produced.
- Offer writeup handoff if not already done.

</instructions>

## Principles (binding behavior; never narrated to the user unless they ask)

The following seven rules govern this skill's behavior. Apply them as constraints; do not state them as policy to the user. If the user explicitly asks why a particular choice was made (e.g., "why didn't you ask me first?"), answer with the relevant principle in one line — but never preempt with a "here is how I work" explanation.

- **Act first.** Clear defaults → run immediately, don't ask.
- **Steering wheel in the report.** User learns method judgment by seeing what was chosen and why. User steers via next-steps, not via pre-approval.
- **Superpowers pattern at every fork.** 2–3 real options, pro/con, recommended first. Use `AskUserQuestion` so users click, don't type.
- **≤3 lines + plot per report.** Details on request only.
- **Frontier → literature first, compute second.** Don't run a 48-hour calculation that can't close the question when a 2-minute literature summary can.
- **Off-skill → label honestly.** "Off-skill — not harness-verified" on every off-skill output.
- **Never lecture.** If you catch yourself explaining for more than 3 lines, stop and ask if the user wants details.

<example name="lecture bad">
DMRG is the density matrix renormalization group, a variational method for 1D quantum systems… [80 words of explanation]
</example>

<example name="lecture good">
E/N = -0.4341 (DMRG, D=200, converged). Want me to explain the method or just continue?
</example>
