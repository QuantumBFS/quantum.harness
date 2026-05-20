# Criticality

Diagnose quantum critical behavior on a concrete model. Produce evidence and a scaling argument, not a course on phase transitions.

## Diagnose

Infer the diagnostic framing from the user's prompt and propose it for ratification.

**Canonical framing:** "You're asking about criticality in [model] near [control parameter ≈ value]. I'll treat this as: locate the transition, check continuous vs first-order, estimate the critical exponent / universality class via finite-size scaling. The model card driving the calculation is [model card]."

If the user already has data at multiple sizes, adjust: "You have [observables at sizes]. I'll run a finite-size scaling analysis on what you have, then recommend what to compute next."

Do not ask 6 questions. Propose the framing; let the user correct if wrong.

## Evidence to gather

- **Order parameter** — vanishes continuously at the critical point if continuous QPT; jumps discontinuously if first-order.
- **Gap behavior** — closes as a power law with system size at criticality (`Δ ~ L^{-z}`); stays open in gapped phases.
- **Susceptibility** — diverges at criticality with universal exponent.
- **Correlation length** — diverges at criticality. Use `ξ ~ L` finite-size scaling form.
- **Entanglement entropy** — at 1D criticality, `S_A ~ (c/6) log L` (open) or `(c/3) log L` (periodic) where `c` is the central charge.
- **Finite-size scaling collapse** — order parameter, susceptibility, correlation length collapsed onto a universal scaling function.

For *how* to compute each, see the model card (`heisenberg`, `transverse-field-ising`, `j1-j2`, `hubbard`) and the relevant method card.

## Cross-checks

| Competing explanation | Test that rules it out |
|---|---|
| First-order transition | Order parameter discontinuous at the candidate point; coexisting phases. |
| Crossover (no real transition) | No size-divergent susceptibility / correlation length. |
| Finite-size artifact | Multiple sizes show consistent scaling; the apparent transition does not drift with `L`. |
| Wrong universality class | Independently estimate two exponents; if they fail the universal scaling relations, reconsider. |
| Gapless phase (not a critical point) | Compare with limit/known-gapless regions in `knowledge-base/limits.md`. |

## Interpretation rules

- A *single* observable showing critical-looking behavior is suggestive, not conclusive. Demand at least two consistent indicators (e.g., gap closing AND scaling collapse).
- Quote uncertainties on exponent estimates from finite-size extrapolation; do not claim three significant figures from `L = 6, 8, 10`.
- For known-universality classes (1D Ising at `Γ = J` is `c = 1/2`, free-Majorana / Ising CFT), check consistency with the established conformal data, not just any fit.
- For contested cases (J1-J2 around `J2/J1 ≈ 0.5`, deconfined criticality candidates), report your evidence's position within the literature debate. Do not claim closure where the field has none.

## Frontier flag

Genuine open questions in QMB criticality — deconfined criticality on the SU(2) checkerboard, the J1-J2 intermediate region, multi-orbital Mott QCPs — should be presented as constraint-only diagnostics rather than identification claims.

Before interpreting evidence in a frontier regime, invoke the `arxiv-search` skill with a tailored query (e.g., `J1-J2 square deconfined criticality`, `kagome Heisenberg gap exponent`) to surface the current state of the debate. The harness's claim should sit inside the literature, not outside it.

## Model hooks

`transverse-field-ising` (canonical Z2 QCP at `Γ = J`), `heisenberg` (gapless 1D, BKT), `j1-j2` (intermediate-regime debate), `hubbard` (Mott QCP), `t-j` (doping-driven transitions).
