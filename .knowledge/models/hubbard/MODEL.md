# Hubbard

Solve Hubbard ground-state problems as correlated-electron tasks. Doping, extended terms (`t'`, `V`), lattice, and DMFT-style embedding are all workflow choices inside this problem — not separate skills.

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 1D chain, half-filling (N↑=N↓=N/2), U/t from the user's prompt (if not given, default U/t=4 — moderate correlation), NN hopping only, OBC, N=20, target E/N + double occupancy.

**Proposal pattern:** "Going with: 1D chain, half-filled, U/t=[value], NN hopping, OBC, N=20, target E/N + ⟨n↑n↓⟩. Override any, or pick: 2D square cylinder (Ly=4), doped system (specify filling), extended Hubbard (t', V terms)."

Build per `.knowledge/conventions.md`: `H = -t Σ (c†c + h.c.) + U Σ n↑n↓`.

## Workflow

1. Set up sites with `(N↑, N↓)` conservation; choose initial state in target sector.
2. Pick method per the table.
3. First short run; verify particle/spin numbers, particle-hole at half-filling, fermionic signs.
4. Sweep convergence parameter; track observable.
5. Verify (next section).
6. If the question becomes a Mott / large-U / multi-orbital question, hand off.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Small cluster (N ≲ 16 sites) | ED pending refreshed references | `.knowledge/methods/ed/METHOD.md` |
| 1D chain, ladder, narrow cylinder | DMRG | `.knowledge/methods/mps-based-algorithm.md` |
| Imaginary-time route to ground state | TEBD | `.knowledge/methods/mps-based-algorithm.md` |
| Half-filled bipartite at moderate `U` | AFQMC may be sign-free; recommend only after checking. | — |
| Frustrated / doped 2D variational (VMC / NQS) | Compare ansatz energies. Requires `make install netket`. | `.knowledge/methods/variational-monte-carlo-neural-quantum-states.md` |
| Local self-energy / Mott transition framing | DMFT — out of current scope unless an install target lands; surface explicitly. | — |

## Branch table

| Condition | Action |
|---|---|
| `U/t ≫ 1` and finite hole density | Switch to `t-j` (faithful large-U reduction with `J = 4t²/U`). |
| Question is about Mott localization, double occupancy, charge gap | Call `mott-transition`. |
| Multiple orbitals or Hund's coupling | Switch to `multiorbital-hubbard`. |
| Question is about quantum critical behavior (e.g., Mott QCP) | Call `criticality` after the calculation. |
| Frustrated lattice (triangular Hubbard, etc.) | Call `frustration`. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `U = 0` → free fermions on lattice (compute analytically); `U → ∞` half-filled bipartite → Heisenberg AFM with `J = 4t²/U`; atomic limit `t = 0` → trivial occupation.
- **Symmetry**: `(N↑, N↓)` conservation; SU(2) for `H_Hubbard` with no field; particle-hole symmetry at half-filling on bipartite lattices.
- **Convergence**: bond-dim sweep + cylinder-width when 2D.
- **Internal consistency**: variance, double-occupancy trend (decreases with `U/t`), spin-spin correlations build up at large `U`.
- **Cross-method validation** (when feasible) — check the U→∞ Heisenberg mapping at large U/t; use ED only after `.knowledge/methods/ed/METHOD.md` is rebuilt. See AGENTS.md "Verification practice".

Optional check:

- 1D chain at half-filling: compare to Lieb-Wu integral equations (`.knowledge/benchmark-numbers.md`). For 2D, the field is contested at intermediate `U` and finite doping — report values with their convergence trend rather than claiming a benchmark.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then route to `scientific-visualization`. See AGENTS.md "Writeup handoff".

## Related skills

`mott-transition`, `t-j`, `multiorbital-hubbard`, `frustration`, `criticality`.
