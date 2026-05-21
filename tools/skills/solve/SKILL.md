---
name: solve
description: Use when the user brings a concrete quantum many-body research problem — phrases like "ground state of Heisenberg N = 20", "is kagome a spin liquid", "Hubbard at U/t = 8", "compute the gap for TFIM at h = 1", "what does VMC give for J1-J2 at 0.5". Also fires when `/onboard` routes here or when the user pivots to a new problem mid-session.
---

# Solve

Interactive problem-solving loop: infer problem, run the right harness path, audit, report, offer next steps.

<audience>
User is technical, expects concise results and a plot, and should not answer setup questions when defaults are clear.
</audience>

## When

- User states a concrete QMB problem.
- `/onboard` routes here.
- User pivots to a new problem.

## Audit

<audit required="true">
- Every `/solve` result is flow-backed with `tools/flow/templates/solve.toml` (`run -> audit -> close`).
- Computed and interpretive claims are NOT final until `tools/cli/flow require <run> audit` exits 0.
- `audit` is a spawned subagent attempt using `/verify --mode solve`; self-audit, roleplayed review, or invented reviewer id is invalid.
- Audit dispatch MUST use `/verify`'s reference handoff; the verifier prompt must contain `tools/skills/verify/references/solve.md` and `tools/skills/verify/references/sidecar.md`.
- Default audit items: `setup`, `limits`, `symmetry`, `convergence`, `claim`.
- If no subagent is available, stop with `blocked: verifier subagent unavailable`; do not present the result as verified.
- The audit brief includes exactly: "Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."
- If a turn ends before audit passes, emit `tools/cli/flow status <run>` and the blocker instead of the claim.
</audit>

## Loop

```text
intake -> match -> run -> audit -> report -> options -> repeat
```

## Intake

Infer defaults from the user prompt and model/physics cards. Ask one narrow question only when the prompt maps to multiple model cards or materially different method branches.

Consult:

- `knowledge-base/models/<name>/MODEL.md`
- relevant `knowledge-base/physics/<topic>/PHYSICS.md`
- the selected method card and stack contract

If a card redirects to dynamics, finite-T, or another stub, follow the redirect immediately.

## Run

Initialize before claim-producing work:

```text
tools/cli/flow init results/<run> --template tools/flow/templates/solve.toml
```

Use the selected method card's code shape. Install missing canonical stack profiles before compute; route remote/non-trivial compute through `/slurm`. Save scripts under `scripts/`, results under `results/`, and generate a convergence/stability plot.

Frontier card flag: run literature search first, audit the literature-backed interpretation as the solve result, and offer compute as a next step.

Off-scope: use the closest card only if honest; label output "Off-skill — not harness-verified" or ask the user to choose among real redirects.

## Audit Step

After the run attempt finishes, spawn the verifier subagent with:

- result artifact and target hash
- protocol/flow state
- model, physics, method, and stack cards used
- exact claim being audited
- `/verify --mode solve`, `tools/skills/verify/references/solve.md`, `tools/skills/verify/references/sidecar.md`, and the default item list unless the claim needs narrower one-word items

Finish the audit attempt only with:

```text
tools/cli/flow attempt finish <run> <audit-attempt> --report verify/verify_<artifact>_<date>.md
tools/cli/flow require <run> audit
```

## Report

Report only after the audit gate passes. Keep it to <=3 lines plus the plot: primary quantity, method/reason, verification state. Include the rerun command, e.g. `julia --project=julia-env scripts/<name>.jl`.

## Options

Offer 2-3 real next steps, recommended first, with `Done` always available. Common options: richer visualization, parameter scan, deeper observable, cross-method check, literature context, writeup, different problem.

## Done

When the user explicitly stops or picks Done, save `results/session_summary.md`, list produced scripts/results, and offer writeup handoff if appropriate.
