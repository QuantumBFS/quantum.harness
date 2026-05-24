---
name: solve
description: Use when the user brings a concrete quantum many-body research problem — phrases like "ground state of Heisenberg N = 20", "is kagome a spin liquid", "Hubbard at U/t = 8", "compute the gap for TFIM at h = 1", "what does VMC give for J1-J2 at 0.5". Also fires when `/onboard` routes here or when the user pivots to a new problem mid-session.
---

# Solve

Interactive problem-solving loop: infer problem, run the right harness path, report, offer next steps.

<audience>
User is technical, expects concise results and a plot, and should not answer setup questions when defaults are clear.
</audience>

## When

- User states a concrete QMB problem.
- `/onboard` routes here.
- User pivots to a new problem.

## Loop

```text
intake -> match -> run -> report -> options -> repeat
```

## Intake

Infer defaults from the user prompt and model/physics cards. Ask one narrow question only when the prompt maps to multiple model cards or materially different method branches.

Consult:

- `.knowledge/models/<name>/MODEL.md`
- relevant `.knowledge/physics/<topic>/PHYSICS.md`
- the selected method card and stack contract

If a card redirects to dynamics, finite-T, or another stub, follow the redirect immediately.

## Run

Use the selected method card's code shape. Install missing canonical stack profiles before compute; route remote/non-trivial compute through `/slurm`. Save scripts under `scripts/`, results under `results/`, and generate a convergence/stability plot.

Frontier card flag: run literature search first, present the literature-backed interpretation as the solve result, and offer compute as a next step.

Off-scope: use the closest card only if honest; label output "Off-skill — not harness-verified" or ask the user to choose among real redirects.

## Report

Keep it to <=3 lines plus the plot: primary quantity, method/reason, verification state. Include the rerun command, e.g. `julia --project=julia-env scripts/<name>.jl`.

## Options

Offer 2-3 real next steps, recommended first, with `Done` always available. Common options: richer visualization, parameter scan, deeper observable, cross-method check, literature context, writeup, different problem.

## Done

When the user explicitly stops or picks Done, save `results/session_summary.md`, list produced scripts/results, and offer writeup handoff if appropriate.
