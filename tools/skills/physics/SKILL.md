---
name: physics
description: |
  MUST invoke when user asks a cross-model physics question (mechanism,
  phase identification, diagnostic) rather than naming a specific model.
  Supported topics:
  - criticality: second-order transitions, exponents, finite-size scaling
  - frustration: geometric or exchange-induced frustration
  - spin-liquid: fractionalized phases, topological order, RVB
  - mott-transition: interaction-driven metal-insulator
  - kondo-effect: local-moment screening
  - magic: non-stabilizerness, SRE, long-range magic
  - confinement: gauge-theory confinement diagnostics
  Read knowledge-base/physics/<topic>/PHYSICS.md; grep ^signal in
  knowledge-base/physics/<topic>/TACITS.toml before any verdict.
---

# physics dispatcher

Auto-triggered when the user asks about a cross-model phenomenon, mechanism,
or diagnostic. Different from `/model`: `/physics` fires for "is this a spin
liquid?" or "what would Kondo physics look like here?", not for "solve
Heisenberg" (that's `/model`).

## Workflow

1. **Match.** Resolve to one canonical topic name.
2. **Read the card.** `knowledge-base/physics/<topic>/PHYSICS.md` defines
   the evidence rubric and cross-checks.
3. **Grep tacits.** `knowledge-base/physics/<topic>/TACITS.toml` if present.
4. **Compose.** Most physics questions cross models; the card lists model
   hooks (`see knowledge-base/models/<model>/MODEL.md`) and primitive
   compositions (`/parameter-scan`, `/scaling-fit`, `/cross-method-check`).
5. **Report.** Caveat-after, not caveat-first.

## Anti-patterns

- Declaring a phase without running the evidence rubric.
- Ignoring the model hooks the topic card declares.
