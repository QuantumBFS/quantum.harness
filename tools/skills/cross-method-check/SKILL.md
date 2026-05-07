---
name: cross-method-check
description: Use when the user wants to confirm a result by re-running with an independent method (or independent diagnostic) at matched parameters and comparing. Generic over the methods and the observable. Implements AGENTS.md verification rule §5.
---

# cross-method-check

Re-run the same observable at the same parameter point with an *independent* method (or an independent diagnostic on the same wavefunction), within a small but meaningful instance, and report whether the two paths agree within both methods' accuracy budgets. AGENTS.md "Verification practice §5" names this pattern; this skill is the named primitive for it.

## When to activate

- After a single-method calculation when the calling skill (or the user) wants verification.
- When a single-method result lies near a phase boundary, in a frontier regime, or at a bond-dim where truncation may bias the answer.
- When the same observable is computable in two distinct ways (e.g., DMRG-MPS vs TTN, magic-crossing vs Binder cumulant on the same dual model, `L(ρ_AB)` via Markov chain vs Pauli-basis MPS lift).
- AGENTS.md verification rule §5: cross-method validation is a default check whenever feasible.

## Inputs

- A *primary result*: `(method_A, observable, parameter point, accuracy budget)`.
- A *secondary method or diagnostic*: pickable from the model skill's method-recommendation table or a related `physics/*` skill. Default selection (skill picks; user ratifies):

  | Primary | Default secondary | Why |
  |---|---|---|
  | DMRG / MPS at small `L` | ED on the same `L` | Independent algorithm; agreement gates DMRG truncation. |
  | TTN sampling | DMRG-MPS perfect-sampling on the same wavefunction (different proposal class) | Independent sampler; agreement gates Markov-chain bias. |
  | DMRG-MPS at moderate `L` | TEBD imaginary-time on the same `L` | Independent ground-state projector. |
  | Pauli-Markov sampling for magic | Deterministic Pauli-basis MPS lift (`methods/pauli-markov.md` runtime variant) | Sampling vs deterministic; orthogonal error budgets. |
  | Magic crossing as critical detector | Binder cumulant on the dual order parameter | Independent diagnostic on the same wavefunction; the canonical "magic-vs-Binder" cross-check at fixed `χ`. |
  | DMRG cylinder geometry | Different cylinder width at same `L_x` | Independent geometry; agreement gates cylinder bias on frustrated 2D. |

- A *small-but-meaningful instance* — large enough that the comparison is non-trivial, small enough that the secondary method runs cheaply. Defaults from the model skill; the calling skill / user override.

## Workflow

1. Lock the primary configuration (parameter point, sector, observable definition).
2. Translate to the secondary method's setup: confirm the *exact same observable* is being computed (sign conventions, normalization, sector match). For diagnostics that differ in form (`magic` vs `Binder`), confirm both target the *same physical question* (e.g., transition location).
3. Run the secondary calculation at the same instance.
4. Compare the two values. The calling skill provides an accuracy budget per method — this skill does *not* invent tolerance.
5. Tag the result:
   - **Agreement** — the two values overlap within both budgets.
   - **Disagreement** — the values do not overlap. Per AGENTS.md, this implies setup error or insufficient convergence in one of the two methods. Surface the failure mode; do not average.
   - **Diagnostic split** (for `magic`-vs-`Binder` style cross-checks) — when the two diagnostics disagree about the *interpretation* (e.g., one detects a transition, the other does not), report this as a method-on-problem robustness claim, not as a numerical disagreement.
6. Persist the comparison: `results/<run>/cross-method-check.csv` with both method outputs, the budgets, and the tag.
7. Hand back the tag to the caller.

## Output

- `results/<run>/cross-method-check.csv` — `(method, observable, value, uncertainty, instance, tag)`.
- A 2–3-line report: agreement status with embedded reasoning (which methods, why those, what was at stake).
- `scripts/<run>/cross-method-check.{jl,py}` — reproducible script bundling both runs.

## On disagreement

Disagreement is information, not a failure. Per AGENTS.md, disagreement implies:

- Setup error in one of the methods (sign convention, sector, normalization, factor of 2).
- Insufficient convergence in one (bond-dim too small, basis too small, autocorrelation too long).
- A genuine method-on-problem split (the secondary method has a known failure mode in this regime; the primary is more reliable).

The skill *surfaces* the disagreement; the calling skill (or `superpowers:systematic-debugging` if dispatched) diagnoses. Do not silently average.

## Composition

- After this skill runs, common follow-ups (offered via `AskUserQuestion`):
  - Acceptance: write up. (Route to `/reproduce-paper` close or the writing skills.)
  - Disagreement: dispatch a debug pass. (Route to `superpowers:systematic-debugging`.)
  - Tighten budgets and re-run. (Bond-dim sweep, longer chains, larger basis.)
  - Done.

## Notes

- This skill does *not* invent the secondary method. Defaults come from the model skill's method-recommendation table; the calling skill or the user can override.
- Cross-diagnostic checks (e.g., magic vs Binder) are a special case where the two paths differ in physical content but converge on the same physical question; surface the methodological claim transparently.
- For frontier regimes, cross-method checks often reveal the literature debate rather than closing it. Surface that as well.
