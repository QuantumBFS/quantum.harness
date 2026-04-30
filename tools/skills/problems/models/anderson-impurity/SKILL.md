---
name: anderson-impurity
description: Use when the user is working on an Anderson impurity ground-state problem — a local interacting impurity coupled to a non-interacting bath, with finite-bath benchmarks, hybridization functions, or Kondo / local-moment physics.
---

# Anderson Impurity

Solve Anderson impurity ground-state problems. The Hamiltonian decomposes into a local interacting piece, a bath, and a hybridization. Bath discretization quality is the dominant practical concern.

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** single-orbital symmetric Anderson (ε_d = -U/2), U and Γ from the user's prompt, flat-band bath with L_bath=6, half-filling, target occupancy + local moment + T_K estimate.

**Proposal pattern:** "Going with: single-orbital symmetric Anderson, U/Γ=[value], flat-band bath L_bath=6, half-filling. Target: ⟨n_d⟩, local moment, T_K estimate (Haldane formula + ED cross-check). Override any, or pick: multi-orbital (→ multiorbital-hubbard), asymmetric Anderson (ε_d ≠ -U/2), longer bath chain (DMRG)."

If multi-orbital, hand off to `multiorbital-hubbard`. Build per `knowledge-base/conventions.md`.

## Workflow

1. Choose bath representation: star geometry (direct from `Δ(ω)`) or chain geometry (after Lanczos-style mapping). Document.
2. Set up sites; pin `(N↑, N↓)` sector.
3. Pick method per the table.
4. First short run; verify particle / spin numbers, impurity occupancy at trivial limits.
5. Vary bath size (or chain length, bond dim) until target observable converges.
6. Verify (next section).

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Finite bath, small system (`L_bath` ≲ 8) | ED | `knowledge-base/methods/ed.md` |
| Bath as a chain, longer chains | DMRG / MPS impurity solver | `knowledge-base/methods/dmrg.md` |
| Continuous bath, low-energy Kondo scaling | NRG-style reasoning (out of current scope to run; note conceptually). | — |
| DMFT lattice self-consistency | Out of current scope; flag and discuss the embedding context. | — |

## Branch table

| Condition | Action |
|---|---|
| Question is about Kondo screening, local moment formation, screening scales | Call `kondo-effect`. |
| Multi-orbital, Hund's coupling, Kanamori interactions | Switch to `multiorbital-hubbard`. |
| Impurity arises from a lattice DMFT loop | Out of current scope; surface and discuss. |

## Verification

Default checks:

- **Limit checks** via `knowledge-base/limits.md`: `V = 0` → impurity decouples (trivial atomic limit); `U = 0` → resonant level model (exactly solvable); symmetric Anderson at `ε_d = -U/2` → particle-hole symmetric, `⟨n_d⟩ = 1`.
- **Symmetry**: total particle count, `S^z`, particle-hole at the symmetric point.
- **Bath-size convergence**: report the trend of the observable as `L_bath` (or chain length) grows.
- **Internal consistency**: variance; impurity occupancy; local moment.
- **Cross-method validation** (when feasible) — re-solve at smaller bath with ED for an exact reference; for chain-mapped problems, cross-check star vs chain bath geometry. See AGENTS.md "Verification practice".

Optional check:

- Symmetric Anderson Kondo scale via Haldane formula in `knowledge-base/limits.md` (`T_K`); compare against a finite-bath estimate where possible. Treat as order-of-magnitude consistency, not a benchmark match.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then route to `scientific-writing` / `latex-paper-en` / `scientific-visualization`. See AGENTS.md "Writeup handoff".

## Related skills

`kondo-effect`, `multiorbital-hubbard`, `mott-transition` (lattice context).
