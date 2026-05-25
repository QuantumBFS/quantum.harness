---
name: physics
user-invocable: false
description: |
  Use when the user asks a phase, mechanism, or diagnostic question —
  whether or not a specific model is named. Triggering topics:
  - criticality: second-order transitions, exponents, finite-size scaling
  - frustration: geometric or exchange-induced frustration
  - spin-liquid: fractionalized phases, topological order, RVB, "is this a spin liquid"
  - mott-transition: interaction-driven metal-insulator
  - kondo-effect: local-moment screening
  - magic: non-stabilizerness, SRE, long-range magic
  - confinement: gauge-theory confinement diagnostics
  Fires once per topic the user names, not once per session.
---

# physics dispatcher

Auto-triggered when the user asks about a cross-model phenomenon, mechanism,
or diagnostic. Different from `/model`: `/physics` fires for diagnostic or
mechanism questions, not for "solve <model>" (that's `/model`).

<example name="physics good">
"Is this a spin liquid?" — /physics fires on the diagnostic question.
"What would Kondo physics look like here?" — /physics fires on the mechanism question.
</example>

<example name="physics not-applicable">
"Solve Heisenberg" — /model fires; /physics does not.
"Compute the ground state of TFIM" — /model fires; /physics does not.
</example>

## Workflow

1. **Match.** Resolve to one canonical topic name.
2. **Read the card.** `.knowledge/physics/<topic>/PHYSICS.md` is
   authoritative. Work through the following checklist before any compute:

   <checklist name="card-read">
   - Evidence rubric (which observables, which sectors, which limits) noted
   - Cross-checks (independent methods or diagnostics) noted
   - Model hooks (which `.knowledge/models/<model>/MODEL.md` files to consult) noted
   </checklist>

3. **Compose.** Read every model hook the topic card declares — not just
   the one that feels most relevant. The card chooses the cross-model
   evidence pattern; an agent that consults only one model when the card
   lists three has weakened the evidence rubric. Then compose the named
   primitives (`/parameter-scan`, `/scaling-fit`,
   `/cross-method-check`) per the card's declared workflow.

   Coverage, not filtering: gather every item in the topic's evidence
   rubric before issuing a verdict. Reporting "I checked the obvious one
   and it looked right" is a failed verdict.

4. **Report.** Caveat-after, not caveat-first.

   <example name="caveat-after bad">
   "While there is some debate, and the picture is not fully settled, the evidence is consistent with a spin liquid in the J2/J1 ≈ 0.5 regime."
   </example>

   <example name="caveat-after good">
   "The evidence is consistent with a spin-liquid phase at J2/J1 ≈ 0.5. The exact nature of the liquid (Z2 vs gapless U(1)) remains debated in the literature."
   </example>

## Anti-patterns

<checklist name="anti-patterns">
- Declaring a phase without running the card's full evidence rubric — fail.
- Ignoring the model hooks the topic card declares — fail.
</checklist>

<example name="evidence-rubric bad">
"The structure factor peaks at q = (π, π), so this is the AFM Néel phase."
(One diagnostic, no cross-check, no scaling, no limit; the card declared a multi-item rubric.)
</example>

<example name="evidence-rubric good">
"Running the card's full rubric: structure factor at q = (π, π), staggered magnetization, spin gap, and the J → 0 limit cross-check. All four agree with AFM Néel; verdict stands."
</example>

<example name="model-hooks bad">
"The topic card lists Heisenberg, J1-J2, and Hubbard as model hooks; I'll just use J1-J2 since it feels most relevant."
</example>

<example name="model-hooks good">
"The topic card lists Heisenberg, J1-J2, and Hubbard as model hooks. Reading all three cards before composing the cross-model evidence pattern."
</example>
