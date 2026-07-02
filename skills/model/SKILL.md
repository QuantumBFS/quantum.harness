---
name: model
user-invocable: false
description: |
  Use when the user names or describes a harness-tracked quantum lattice
  model. Match user prose to one of:
  - transverse-field-ising (TFIM): quantum-critical Ising chain / 2D Wilson-Fisher
  - heisenberg: SU(2) magnet, AFM or FM by sign of J
  - xxz-chain: spin-1/2 XXZ, Bethe-ansatz integrable, Δ tunes FM / Luttinger / Néel
  - j1-j2: frustrated Heisenberg, J2/J1≈0.5 spin-liquid candidate
  - shastry-sutherland: orthogonal-dimer AFM, exact dimer phase, magnetization plateaus
  - spin-1-xxz: Haldane phase, single-ion anisotropy
  - aklt: spin-1 bilinear-biquadratic, exact VBS ground state
  - kitaev-honeycomb: bond-dependent exchange, exactly solvable Z2 spin liquid, anyons
  - spin-ice-pyrochlore: 2-in-2-out ice rule, Coulomb phase, magnetic monopoles
  - mbl-disordered-heisenberg: random-field XXZ chain, ETH-to-MBL transition
  - rydberg-pxp: blockaded Rydberg chain, quantum many-body scars, |Z2⟩ revivals
  - dissipative-spin-lindblad: open spin lattice, Liouvillian spectrum, steady states
  - potts-clock: q-state, first-order / continuous / BKT by q
  - t-v: spinless fermions + NN repulsion (CDW vs Luttinger)
  - hubbard: t-U electrons; Mott transition, cuprate parent
  - attractive-hubbard: U<0 pairing, BCS-BEC crossover, sign-free QMC
  - t-j: strong-coupling Hubbard with no-double-occupancy
  - multiorbital-hubbard: multi-band + Hund's J
  - falicov-kimball: itinerant + frozen electrons, CDW, DMFT-exact
  - kondo-lattice: local moments + conduction electrons, heavy fermions
  - anderson-impurity (SIAM): impurity-in-bath, Kondo
  - anderson-localization: single particle + disorder, mobility edge in 3D
  - bose-hubbard: lattice bosons, superfluid-Mott transition
  - sachdev-ye-kitaev (SYK): random all-to-all Majoranas, maximal chaos, no lattice
  - ssh: dimerized hopping chain, 1D topological insulator, edge modes
  - kitaev-chain: p-wave superconducting wire, Majorana end modes
  - haldane-chern: honeycomb Chern insulator, quantum anomalous Hall
  - hofstadter: lattice + rational flux, butterfly spectrum, Chern bands
  - toric-code: Z2 stabilizer model, topological order, e/m anyons
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

3. **Serve.** Surface the card's facts relevant to the moment — Hamiltonian
   and conventions, phases and observables, method recommendations,
   verification pointers — into whatever workflow is active
   (`/reproduce-paper`, `/solve`, a method skill). The card informs that
   workflow; it does not re-route or replace it.

## Anti-patterns

<checklist name="anti-patterns">
- Substituting generic defaults from memory for the card's declared facts and recommendations — fail.
- Acting on agent memory ("I remember Heisenberg has 3 phases") instead of re-reading the card — fail. Memory drifts; cards don't.
</checklist>

<example name="memory-substitution bad">
"Heisenberg has 3 phases — AFM, FM, and PM — so I'll measure ⟨S·S⟩ and ⟨Sᶻ⟩."
</example>

<example name="memory-substitution good">
"Re-reading .knowledge/models/heisenberg/MODEL.md before naming phases. The card declares [list from card]; observables [list from card]."
</example>
