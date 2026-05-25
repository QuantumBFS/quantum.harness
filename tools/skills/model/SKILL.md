---
name: model
user-invocable: false
description: |
  Use when the user names or describes a harness-tracked quantum lattice
  model. Match user prose to one of:
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
  Fires for each named model the user touches in a session, not just the
  first match.
---

# model dispatcher

Auto-triggered. The user does not type `/model`; the description above fires
the skill when their prose names a harness-tracked model.

## Audience definition (binding)

<audience>
The reader is a working physicist with no harness-internal context. They
want the result with embedded reasoning (what method, why, what was
verified), not the agent's process. They do NOT know harness vocabulary
(manifest, deviation). Every user-facing line is anchored to this audience.
</audience>

## Workflow

1. **Match.** Resolve user's prose to one canonical model name. Handle
   aliases (TFIM → transverse-field-ising, SIAM → anderson-impurity, …).
2. **Read the card.** `.knowledge/models/<name>/MODEL.md` is
   authoritative; agent memory is not. Work through the following checklist
   before any compute:

   <checklist name="card-read">
   - Hamiltonian definition and sign/normalization conventions read
   - Declared phases and their order parameters identified
   - Observables and their canonical forms noted
   - Recommended method(s) and their stack noted
   - Verification rubric (limit / symmetry / convergence / cross-method) noted
   </checklist>

3. **Execute.** Follow the card's declared workflow. The card names which
   primitive skills to compose (`/solve`, `/parameter-scan`,
   `/scaling-fit`, `/cross-method-check`, `/slurm`, `/reproduce-paper`). Do
   NOT substitute a different primitive because it feels more familiar; the
   card's choice is authoritative.

4. **Report.** Three lines or fewer in prose: primary quantity (value +
   units), verification status (which checks passed), and one-line
   reasoning (method + why). Auto-generate and embed the relevant
   convergence or stability plot — never report a result without the visual
   proof it converged.

## Anti-patterns

<checklist name="anti-patterns">
- Substituting generic ED/DMRG defaults for the card's declared workflow — fail.
- Acting on agent memory ("I remember Heisenberg has 3 phases") instead of re-reading the card — fail. Memory drifts; cards don't.
</checklist>

<example name="memory-substitution bad">
"Heisenberg has 3 phases — AFM, FM, and PM — so I'll measure ⟨S·S⟩ and ⟨Sᶻ⟩."
</example>

<example name="memory-substitution good">
"Re-reading .knowledge/models/heisenberg/MODEL.md before naming phases. The card declares [list from card]; observables [list from card]."
</example>
