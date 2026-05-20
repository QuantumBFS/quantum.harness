---
name: solve
description: Use when the user brings a concrete quantum many-body problem to solve. Drives the interactive problem-solving loop: intake → act → report → next-steps → loop until done.
---

# Solve

The main interactive skill. Drives the conversation from problem intake to verified result to next steps. Uses the Superpowers brainstorming pattern at every decision point.

## When to activate

- User states a concrete QMB problem ("ground state of Heisenberg N=20", "is kagome a spin liquid", "Hubbard at U/t=8").
- After `onboard` routes here.
- Any time the user brings a new problem mid-session.

## Loop

```
Intake → Match skill → Act → Report → Next-steps → (user picks) → Act → Report → ... → Done
```

### 1. Intake

Infer the problem from the user's prompt. Do NOT ask clarifying questions if defaults are clear. If genuinely ambiguous (can't tell which model), use `AskUserQuestion` with 2–3 candidate models.

### 2. Match skill

Find the matching model card (`knowledge-base/models/<name>/MODEL.md`) and any relevant physics card (`knowledge-base/physics/<topic>/PHYSICS.md`). Read the card's Diagnose section for canonical defaults. Read the method recommendation table for which method card to use, then read that method card's canonical software stack and `tools/software/stacks/<stack>.toml` install contract.

If the problem hits a branch table redirect (e.g., dynamics → `spectral.md`, finite-T → `finite-t.md`), follow it immediately.

### 3. Act

Run the calculation silently using the method card's code shape. If the canonical stack is missing, install the selected stack profile first; for remote runs, let `/slurm` run the profile's smoke test in the declared place (`login` or `compute`). Auto-generate a convergence plot. Save script to `scripts/` and results to `results/`.

For frontier problems: act on literature first (run `arxiv-search`), then offer compute as a follow-up.

For off-scope / stub problems: follow the stub's instructions (present options via `AskUserQuestion`).

### 4. Report

≤3 lines + convergence plot. Embed one-line reasoning: what method was chosen, why, what was verified.

Example: "E/N = -0.4341 via DMRG (1D chain, D=200, converged). Cross-checked with ED — agrees to 5 digits. Bethe ansatz ≈ -0.4431 at thermodynamic limit — finite-size correction consistent. ✓"

Show the run command: `julia --project=julia-env scripts/<name>.jl`

### 5. Next-steps

Always offer via `AskUserQuestion` — Superpowers brainstorming pattern:

- 2–3 options, each with short label + one-line pro/con.
- Recommended option first, labeled "(Recommended)".
- "Done" is always a real option, never padded.

Common next-steps (pick the 2–3 most relevant):

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

### 6. Loop

User picks a next-step → go to step 3 (Act) with the new task. Repeat until the user picks "Done" or pivots to a different problem (restart from step 1).

### 7. Done

When the user stops:
- Save a one-paragraph session summary to `results/session_summary.md`.
- List all scripts and results produced.
- Offer writeup handoff if not already done.

## Principles (embedded, not stated to user)

- **Act first.** Clear defaults → run immediately, don't ask.
- **Steering wheel in the report.** User learns method judgment by seeing what was chosen and why. User steers via next-steps, not via pre-approval.
- **Superpowers pattern at every fork.** 2–3 real options, pro/con, recommended first. Use `AskUserQuestion` so users click, don't type.
- **≤3 lines + plot per report.** Details on request only.
- **Frontier → literature first, compute second.** Don't run a 48-hour calculation that can't close the question when a 2-minute literature summary can.
- **Off-skill → label honestly.** "Off-skill — not harness-verified" on every off-skill output.
- **Never lecture.** If you catch yourself explaining for more than 3 lines, stop and ask if the user wants details.
