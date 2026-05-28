# Confinement

Diagnose confinement and the confinement-deconfinement transition on a concrete model. Identify whether the regime is confined, deconfined, or critical between them; cross-check across multiple diagnostics so the conclusion does not rest on a single observable.

## Diagnose

Infer the diagnostic framing from the user's prompt and propose it for ratification.

**Canonical framing:** "You're asking whether [model on lattice] at [coupling] is in a confined phase. I'll frame this as: compute the Wilson-loop-like operator (or its dual order parameter), check the area-law vs perimeter-law decay, and cross-check with at least one independent diagnostic (Binder cumulant, susceptibility). The model card driving the calculation is [model card]."

For models accessible via duality (e.g., 2D `Z_2` lattice gauge ↔ 2D Ising on the dual square lattice via Wegner duality), state the route explicitly: "I'll run the calculation on the dual model where it is computationally cleaner; the duality preserves the diagnostics that matter."

Do not ask 6 questions. Propose the framing; let the user correct if wrong.

## Evidence to gather

For each item, the relevant model card drives the calculation; this skill specifies *what to compute* and *what to look for*.

- **Wilson-loop-like operator** — area-law decay `~ exp(−σ A)` in the confined phase; perimeter-law decay `~ exp(−κ P)` in the deconfined phase. The transition shows up as a change in scaling.
- **Order parameter on the dual side** — when a duality maps the gauge problem to a spin model, the dual magnetization (or its moments) plays the role of the order parameter; finite in one phase, vanishing in the other.
- **Binder cumulant** `U = 1 − ⟨s^4⟩ / (3 ⟨s²⟩²)` of the dual order parameter — crossings of `U(L)` curves locate the transition. Sensitive to bond dimension; document `χ` used.
- **Susceptibility** — divergence at the transition with universality-class exponent.
- **Correlation length** — diverges at the transition; the data-collapse exponent `ν` is the universal anchor.

How to compute each: see the relevant model card (`transverse-field-ising` for the 2D-Ising route, `t-j` / extended-Hubbard for fermionic confinement contexts) and method card.

## Cross-checks

| Competing explanation | Test that rules it out |
|---|---|
| Crossover, not a real transition | Multiple `L` show consistent crossing/divergence; the apparent transition does not drift with `L` once `χ` is large enough. |
| Bond-dimension truncation faking deconfinement | Sweep `χ`; if the crossing or divergence depends on `χ`, raise `χ` until it stops. |
| Wrong sector (e.g., charge-non-zero in a gauge problem) | Verify Gauss-law / sector occupation explicitly; duality-based calculations require the charge-free dual sector. |
| Symmetry-broken state mistaken for deconfined phase | The dual ferromagnetic phase corresponds to *confined*, not deconfined. Map carefully. |
| Finite-size artifact | Run multiple `L`; consistent scaling argues against artifact. |
| Topological-order content not separated from confinement | Compute topological entanglement entropy or ground-state degeneracy explicitly when the question requires it. |

## Interpretation rules

- A *single* observable showing confinement-like behavior is suggestive, not conclusive. Demand at least two consistent indicators (e.g., area-law Wilson loop AND order-parameter onset, or Binder cumulant AND susceptibility divergence).
- For models accessible via duality, state the duality explicitly in the report: "Computed via dual model X; order parameters preserved by Y duality." Otherwise the user cannot interpret the numbers.
- The 2D Z_2 confinement-deconfinement transition sits in 3D Ising universality; its `ν` lives in the literature *range* containing the established `ν_{3D} ≃ 0.63`. Compare against the range, not a single number.

## Frontier flag

Confinement diagnostics in models beyond the canonical pure `Z_2` gauge / 2D Ising case are an active area:

- Extended Hubbard / `t-J` interpretations of confinement (electron-spinon binding) are debated.
- Higgs phase boundaries in coupled gauge-matter theories often have ambiguous order parameters.
- Topological-order content adjacent to the deconfined phase complicates interpretation.

When the user is in a frontier regime, run the diagnostic plan, then invoke `arxiv-search` with a tailored query (e.g., `<lattice> confinement deconfinement transition`, `<model> Higgs phase`) before interpreting the result. Cite the literature range; do not claim closure.

## Model hooks

- `transverse-field-ising` — drives the actual calculation in the 2D `Z_2` ↔ 2D Ising case (Wegner duality preserves the relevant diagnostics).
- `t-j` and `hubbard` (extended-interaction settings) — fermionic confinement contexts.
- `.knowledge/physics/criticality/PHYSICS.md` — once a transition is located, criticality drives finite-size scaling and exponent extraction.
