# t-J

Solve t-J ground-state problems. The no-double-occupancy projection makes the local Hilbert space three-dimensional (empty / up / down) and changes both diagnostics and method choice relative to Hubbard.

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 1D chain, J/t=0.4 (corresponds to Hubbard U/t=10), filling from the user's prompt (if not given, default n=0.875 — 12.5% doping), OBC, N=20, target E/N + spin-charge correlations. No three-site terms unless specifically requested.

**Proposal pattern:** "Going with: 1D chain, J/t=[value], n=[filling], OBC, N=20, no-double-occupancy projected, target E/N + spin-charge correlations. Override any, or pick: 2D square cylinder (Ly=4), comparison to Hubbard at large U, zero-doping limit (→ Heisenberg)."

Build per `.knowledge/conventions.md`: `H = -t P(c†c+h.c.)P + J Σ(S·S - nn/4)`.

## Workflow

1. Set up sites with `("Electron"; conserve_qns=true)` in ITensors (or equivalent), pinned to the target `(N↑, N↓)`. Verify that double occupancy is excluded by the construction.
2. Pick method per the table.
3. First short run; verify projection, particle counts, fermionic signs.
4. Sweep convergence parameter; track observable.
5. Verify (next section).
6. If the user is comparing to Hubbard or asking about Mott / large-U emergence, hand off.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Small cluster, exact reference | Projected ED pending refreshed references | `skills/method-ed/SKILL.md` |
| 1D chain, narrow cylinder | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time route | TEBD | `skills/method-mps/SKILL.md` |
| 2D doped variational (VMC / NQS) | VMC via NetKet for projected wavefunctions. Requires `make install netket`. | `skills/method-vmc/SKILL.md` |

## Branch table

| Condition | Action |
|---|---|
| User wants the connection to large-U Hubbard and Mott physics | Call `mott-transition`. |
| Frustrated lattice (triangular t-J, etc.) | Call `frustration`. |
| Questions about pairing / superconductivity / stripes in 2D doped t-J | Surface as out of current scope (variational territory); offer a 1D / narrow-cylinder DMRG analog. |
| At zero doping, the model reduces to Heisenberg | Switch to `heisenberg`. |

## Verification

Default checks:

- **Projection enforcement**: every site has occupancy ∈ {0, ↑, ↓}; double occupancy literally absent in the basis.
- **Limit checks** via `.knowledge/limits.md`: at zero doping → Heisenberg; at infinite-`J` limit → spin-isolated singlet pairs; at `t/J → ∞` and small doping → kinetic-dominated regime.
- **Symmetry**: particle counts; `S^z` (and SU(2) when isotropic); lattice symmetries.
- **Convergence**: bond-dim sweep; cylinder-width comparison for 2D.
- **Hubbard cross-check**: when `J = 4t²/U` is being claimed, run the corresponding Hubbard at large `U` and compare ground-state energies up to the expected `O((t/U)^4)` correction.
- **Cross-method validation** (when feasible) — re-run on a small projected cluster with an independent method; use ED only after `skills/method-ed/SKILL.md` is rebuilt. See AGENTS.md "Verification practice".

Optional check:

- Use known integrable points (1D supersymmetric t-J at `J = 2t`) as a benchmark.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then route to `scientific-visualization`. See AGENTS.md "Writeup handoff".

## Related skills

`hubbard`, `mott-transition`, `heisenberg` (zero-doping), `frustration`.
