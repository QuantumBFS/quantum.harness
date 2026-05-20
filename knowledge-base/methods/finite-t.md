# Finite-Temperature Methods (Stub)

Methods for computing thermal observables: susceptibility χ(T), specific heat C(T), thermal expectation values. **This is a stub** — the harness does not currently drive finite-T calculations end-to-end. It exists so that agents route here instead of negotiating for 3 rounds.

## When this fires

A user asks for susceptibility vs T, specific heat, thermal averages, finite-temperature phase diagrams, or any T-dependent observable. Model skills' branch tables route "finite-T" here.

## What the agent should do

1. **State in one line:** "Finite-T is outside current scope — but the ground state and low-lying spectrum are in scope and often answer the real question."
2. **Offer options via `AskUserQuestion`:**
   - `"Ground state + gap (Recommended)"` — "In scope. Ground-state energy and spin gap already tell you the low-T scale. I run it now."
   - `"Full-spectrum ED (small N)"` — "Exact χ(T) via Boltzmann trace. Limited to N ≤ 16 (spin-1/2) or N ≤ 12 (Hubbard). Off-skill but straightforward."
   - `"Off-skill finite-T approach"` — "Purification DMRG, METTS, or finite-T Lanczos for larger N. Not harness-verified."
3. **If user picks full-spectrum ED:** proceed off-skill. Build all-sector eigenvalues, compute χ(T) = (1/NT) Σ (S^z)² exp(-E_n/T) / Z. Label as off-skill.
4. **If user picks off-skill finite-T:** proceed, label all output as "Off-skill — not harness-verified."

## Common finite-T methods (reference only)

| Method | Idea | System size | Key reference |
|---|---|---|---|
| Full-spectrum ED + Boltzmann | Diagonalize all sectors, thermal trace | N ≤ 16 (spin), N ≤ 12 (fermion) | Dagotto, RMP 66, 763 (1994). |
| Finite-T Lanczos (FTLM) | Random-vector trace approximation | N ≤ 36 (spin) | Jaklič & Prelovšek, PRB 49, 5065 (1994). |
| METTS | Stochastic MPS sampling of thermal states | Larger N, 1D | White, PRL 102, 190601 (2009). |
| Purification DMRG | Double Hilbert space, imaginary-time evolution | 1D, moderate N | Feiguin & White, PRB 72, 220401 (2005). |

## Known results for common models (cross-reference)

- **1D Heisenberg χ(T):** Bonner-Fisher curve. Peak at T ≈ 0.64J. Exact from Bethe ansatz thermodynamics.
- **1D Heisenberg C(T):** Peak at T ≈ 0.48J.
- For specific benchmark values, check `knowledge-base/benchmark-numbers.md` and the relevant model card.
