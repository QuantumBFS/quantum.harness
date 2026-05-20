---
name: model
description: |
  MUST invoke when user wants to solve, investigate, or reproduce any
  harness-tracked quantum lattice model. Supported (match user prose to one):
  - transverse-field-ising (TFIM): quantum-critical Ising chain / 2D Wilson-Fisher
  - heisenberg: SU(2) magnet, AFM or FM by sign of J
  - j1-j2: frustrated Heisenberg, J2/J1≈0.5 spin-liquid candidate
  - t-v: spinless fermions + NN repulsion (CDW vs Luttinger)
  - hubbard: t-U electrons; Mott transition, cuprate parent
  - t-j: strong-coupling Hubbard with no-double-occupancy
  - anderson-impurity (SIAM): impurity-in-bath, Kondo
  - multiorbital-hubbard: multi-band + Hund's J
  - spin-1-xxz: Haldane phase, AKLT
  - potts-clock: q-state, first-order / continuous / BKT by q
  Read knowledge-base/models/<name>/MODEL.md; grep ^signal in
  knowledge-base/models/<name>/TACITS.toml before any verdict.
---

# model dispatcher

Auto-triggered. The user does not type `/model`; the description above fires
the skill when their prose names a harness-tracked model.

## Workflow

1. **Match.** Resolve user's prose to one canonical model name. Handle
   aliases (TFIM → transverse-field-ising, SIAM → anderson-impurity, …).
2. **Read the card.** `knowledge-base/models/<name>/MODEL.md` carries the
   definition, conventions, phases, observables, recommended methods, and
   verification rubric. The card is authoritative; agent memory is not.
3. **Grep tacits.** If `knowledge-base/models/<name>/TACITS.toml` exists,
   grep `^signal` to scan for relevant lore before doing compute.
4. **Execute.** Follow the card's declared workflow using primitive skills
   (`/solve`, `/parameter-scan`, `/verify`, `/scaling-fit`,
   `/cross-method-check`, `/slurm`, `/reproduce-paper` as appropriate).
5. **Report.** Per AGENTS.md output norms (≤3 lines + convergence plot).

## Anti-patterns

- Substituting generic ED/DMRG defaults for the card's declared workflow.
- Acting on "I remember Heisenberg has 3 phases" instead of re-reading the
  card. Memory drifts; cards don't.
- Ignoring TACITS.toml signals when the audited artifact's symptom matches.
