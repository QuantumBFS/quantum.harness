---
name: cross-method-check
user-invocable: false
description: Use when the user wants to confirm a single-method result with an independent method or diagnostic at the same parameter point — phrases like "cross-check this", "verify with another method", "is this an artifact of DMRG / VMC / QMC", "does a different method agree", or whenever the result sits near a phase boundary or in a frontier regime.
---

# cross-method-check

Re-run the same observable at the same parameter point with an *independent* method (or an independent diagnostic on the same wavefunction), within a small but meaningful instance, and report whether the two paths agree within both methods' accuracy budgets. AGENTS.md "Verification practice §5" names this pattern; this skill implements it.

## Audience / scope (binding)

<audience>
Callers are model cards, `/reproduce-paper`, a physics card, or `/scaling-fit` as a follow-up. The calling skill consumes the comparison tag (Agreement / Disagreement / Diagnostic split) and routes the next step; the user reads the 2–3-line report with embedded reasoning.

This primitive MUST stay generic over: which methods are compared, which observable, which instance size, and which budgets.
</audience>

## When to activate

- After a single-method calculation when the calling skill (or the user) wants verification.
- When a single-method result lies near a phase boundary, in a frontier regime, or at a bond-dim where truncation may bias the answer.
- When the same observable is computable in two distinct ways (e.g., DMRG-MPS vs TTN, or two independent diagnostics that locate the same transition).
- AGENTS.md verification rule §5: cross-method validation is a default check whenever feasible.

## Inputs

- A *primary result*: `(method_A, observable, parameter point, accuracy budget)`.
- A *secondary method or diagnostic*: **exactly one** of these sources, in priority order: (1) the model card's method-recommendation table; (2) a related physics card; (3) the user's explicit choice. If NONE is available, stop with `blocked: no secondary method declared` — do NOT invent a secondary from prior knowledge. Default selection (skill picks; user ratifies):

  | Primary | Default secondary | Why |
  |---|---|---|
  | DMRG / MPS at small `L` | TEBD imaginary-time on the same `L` | Independent ground-state projector; agreement gates DMRG truncation. |
  | TTN sampling | DMRG-MPS perfect-sampling on the same wavefunction (different proposal class) | Independent sampler; agreement gates Markov-chain bias. |
  | DMRG-MPS at moderate `L` | TEBD imaginary-time on the same `L` | Independent ground-state projector. |
  | DMRG cylinder geometry | Different cylinder width at same `L_x` | Independent geometry; agreement gates cylinder bias on frustrated 2D. |

The "Why" column is jargon-shaped for the calling skill. When the rationale appears in the user-facing 2–3-line report, it MUST be rewritten in plain English:

<example name="rationale bad">
Agreement gates DMRG truncation.
</example>

<example name="rationale good">
DMRG can be biased by truncating the bond dimension. TEBD's imaginary-time evolution doesn't truncate the same way, so agreement means truncation isn't biasing the answer.
</example>

- A *small-but-meaningful instance* — large enough that the comparison is non-trivial, small enough that the secondary method runs cheaply. Defaults from the model card; the calling skill / user override.

## Workflow

1. Lock the primary configuration (parameter point, sector, observable definition).
2. Translate to the secondary method's setup. Confirm the *exact same observable* is being computed by checking **each** of: (a) sign conventions, (b) normalization, (c) sector / symmetry assignment, (d) boundary condition. For diagnostics that differ in form, confirm both target the *same physical question* (e.g., transition location).
3. Run the secondary calculation at the same instance.
4. Compare the two values against the accuracy budgets provided by the calling skill — one budget per method. This skill MUST NOT invent or infer a tolerance. If the calling skill did NOT provide a budget for either method, stop with `blocked: missing accuracy budget for <method>`; do NOT fall back to a default tolerance.

   Cover **every** declared uncertainty source per method (truncation, sampling, autocorrelation, sign, sector, normalization) when forming the budgets; the comparison interval is the central value plus the full budget, not just the statistical error. Do NOT drop uncertainty sources because they seem small.
5. Tag the result:

<checklist name="comparison-tags">

- **Agreement** — central values plus their respective uncertainty intervals overlap within both budgets.
- **Disagreement** — the central-value ± budget intervals do NOT overlap. Per AGENTS.md, this implies setup error or insufficient convergence in one of the two methods. Surface **all candidate failure modes** (sign convention, sector, normalization, bond-dim, autocorrelation, etc.) and the specific evidence pointing to each. NEVER average the two values; NEVER pick one as "more likely correct" without surfacing the decision and its basis.
- **Diagnostic split** — applies only to cross-diagnostic checks where the two diagnostics differ in form (e.g., two independent critical detectors of different construction). When the two diagnostics disagree about the *interpretation* (one detects a transition, the other does not), report this as a method-on-problem robustness claim, not as a numerical disagreement.

</checklist>
6. Persist the comparison: `results/<run>/cross-method-check.csv` with both method outputs, the budgets, and the tag.
7. Hand back the tag to the caller.

## Output

- `results/<run>/cross-method-check.csv` — `(method, observable, value, uncertainty, instance, tag)`.
- A 2–3-line report: agreement status with embedded reasoning (which methods, why those, what was at stake).
- `scripts/<run>/cross-method-check.{jl,py}` — reproducible script bundling both runs.

## On disagreement

Disagreement is information, not a failure. Per AGENTS.md, disagreement implies one of:

<checklist name="disagreement-causes">

- Setup error in one of the methods (sign convention, sector, normalization, factor of 2).
- Insufficient convergence in one (bond-dim too small, basis too small, autocorrelation too long).
- A genuine method-on-problem split (the secondary method has a known failure mode in this regime; the primary is more reliable).

</checklist>

When dispatching to a debug pass, surface **every** candidate cause with the specific evidence for or against it; the debug subagent then triages. Do NOT pre-filter.

The skill *surfaces* the disagreement; the calling skill (or `superpowers:systematic-debugging` if dispatched) diagnoses. Do not silently average.

## Composition

- After this skill runs, common follow-ups (offered via `AskUserQuestion`):
  - **Accept and write up** — comparison closes; route to `/reproduce-paper` close or the writing skills.
  - **Debug the disagreement** — route to `superpowers:systematic-debugging` with both runs as evidence.
  - **Tighten budgets and re-run** — bond-dim sweep, longer chains, larger basis; this skill re-invoked once new budgets are in.
  - **Done**.

## Notes

**Binding.**

- This skill MUST NOT invent the secondary method. Defaults come from the model card's method-recommendation table; the calling skill or the user can override.
- Cross-diagnostic checks are a special case where the two paths differ in physical content but converge on the same physical question; surface the methodological claim transparently.

**Frontier caveat.** When the comparison sits inside an active literature debate, the report MUST name the debate (cite the relevant arxiv ids via `arxiv-search` or `.knowledge/literature/`) and present the result as a position within the debate, not as a closing answer.
