# Kondo Effect

Diagnose local-moment formation and screening in impurity or lattice settings. Identify whether the user's regime is local-moment, Kondo-screened, mixed-valent, or none of these.

## Diagnose

Infer the diagnostic framing from the user's prompt and propose it for ratification.

**Canonical framing:** "You're asking about Kondo physics at [U/Γ]. At U/Γ = [value], the system is in the [local-moment / mixed-valent / empty-orbital] regime. I'll estimate T_K via Haldane formula, then recommend whether a finite-bath ED cross-check is needed."

Do not ask 5 questions. Propose the framing — including the regime classification, since U/Γ usually pins it. Let the user correct if wrong.

## Evidence to gather

- **Local moment** `⟨(n_↑ - n_↓)²⟩` on the impurity — saturates near 1 in the local-moment regime, smaller in mixed-valent regimes.
- **Impurity-bath spin correlation** `⟨S_d · S_bath⟩` — negative and growing in magnitude indicates Kondo singlet formation.
- **Impurity spin susceptibility** `χ_d` — Curie-like (`χ ~ 1/T`) above `T_K`, finite as `T → 0` after screening.
- **Kondo scale estimate** — Haldane formula for symmetric Anderson:
  `T_K ~ 0.41 √(U Γ / 2) exp(-π U / 8 Γ)` (see `knowledge-base/limits.md`).
- **Wilson ratio** `R_W = (4 π² / 3) (T χ_d / γ)` — universal value 2 in Kondo regime.

For *how* to compute each, see `anderson-impurity` (and the relevant method card).

## Cross-checks

| Competing explanation | Test that rules it out |
|---|---|
| Trivial bath polarization (no Kondo) | The impurity-bath correlation should grow with bath size and saturate; trivial polarization scales with bath size differently. |
| Insufficient bath discretization | Vary `L_bath` (or chain length); the Kondo signature should converge, not drift. |
| Mixed-valent regime mistaken for Kondo | Check local moment: < 1 indicates significant valence fluctuation; > ~0.9 indicates real local moment. |
| Particle-hole asymmetry effects | Compare symmetric (`ε_d = -U/2`) vs asymmetric runs; the Haldane formula is for the symmetric case. |

## Interpretation rules

- A finite local moment alone does *not* mean "Kondo": it means the local-moment regime exists. Kondo screening is shown by the impurity-bath correlation and the spin susceptibility's behavior across `T_K`.
- The Kondo scale is exponentially sensitive to `U/Γ`. Order-of-magnitude consistency between Haldane formula and finite-bath estimate is acceptable; closer agreement requires careful bath discretization.
- For Kondo-lattice physics (heavy fermions): single-site Kondo physics enters via DMFT; lattice coherence (heavy Fermi-liquid formation) is a distinct regime that the harness does not currently cover at runtime.
- In multi-orbital impurities: Hund's coupling can suppress Kondo screening (Hund metal regime). Flag this explicitly when relevant.

## Model hooks

`anderson-impurity` (drives the calculation), `multiorbital-hubbard` (Hund metal / multi-orbital Kondo), `hubbard` (DMFT impurity context), `mott-transition` (boundary with localized regime).
