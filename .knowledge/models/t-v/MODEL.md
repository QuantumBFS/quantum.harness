# t-V

Solve spinless-fermion t-V ground-state problems. Density-density repulsion `V` competes with kinetic delocalization, driving charge order at strong coupling.

Distinguish from `t-J`: t-V has no spin index; t-J has projected spinful fermions with no double occupancy.

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 1D chain, half-filling (N_f = N/2), V/t from the user's prompt (if not given, default V/t=2 — near CDW transition), OBC, N=20, target E/N + charge structure factor N(q).

**Proposal pattern:** "Going with: 1D chain, spinless fermions, half-filling, V/t=[value], OBC, N=20, target E/N + N(q). Override any, or pick: V/t scan (CDW transition), 2D geometry."

Build per `.knowledge/conventions.md`: `H = -t Σ (c†c + h.c.) + V Σ n_i n_j`.

## Workflow

1. Set up sites with fixed-`N_f` sector; fermion ordering convention explicit.
2. Pick method per the table.
3. First run; confirm particle number conserved, fermionic signs handled.
4. Sweep convergence parameter; track target observable.
5. Verify (next section).
6. If competing-order or critical-point physics emerges, hand off.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Small chain or 2D cluster (N ≲ 24) | ED pending refreshed references | `skills/method-ed/SKILL.md` |
| 1D chain (any N), ladder | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time approach | TEBD | `skills/method-mps/SKILL.md` |
| Sign-problem-free 2D bipartite cases | QMC may be applicable; check sign condition before recommending. | — |

## Branch table

| Condition | Action |
|---|---|
| Lattice has frustration (triangular t-V, etc.) | Call `frustration` for regime classification. |
| User asks about the metal-CDW transition explicitly | Run the calculation here, then call `criticality`. |
| User wants spinful-fermion physics or doped Mott | Switch to `hubbard` or `t-j`. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `V = 0` → free fermions (exact tight-binding band); large `V` at half-filling → CDW with `E/N = -V z / 4` (for chain) or analogous lattice Madelung; particle-hole symmetry on bipartite lattices at half-filling.
- **Symmetry**: particle number conservation; lattice translation; sublattice exchange (bipartite).
- **Convergence**: bond-dim or basis-size sweep monotonic and asymptoting.
- **Internal consistency**: variance, density profile near edges (Friedel oscillations expected for OBC).
- **Cross-method validation** (when feasible) — re-run a small fixed-`N_f` cluster with an independent method, and check sign-problem-free QMC agreement when applicable. Use ED only after `skills/method-ed/SKILL.md` is rebuilt. See AGENTS.md "Verification practice".

Optional check:

- Compare to `.knowledge/benchmark-numbers.md` for the V=0 free-fermion limit and known integrable points.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then route to `scientific-visualization`. See AGENTS.md "Writeup handoff".

## Related skills

`frustration`, `criticality`, `hubbard` (spinful analog).
