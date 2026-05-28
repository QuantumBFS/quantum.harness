# Multiorbital Hubbard

Solve multiorbital Hubbard / Kanamori-interaction ground-state problems. Local Hilbert space grows as `4^M` for `M` orbitals — always cost out the local sector before recommending a method.

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 3-orbital, density-density Kanamori (no spin-flip/pair-hopping unless requested), impurity context (single site + bath), U and J_Hund from the user's prompt, half-filling per orbital, no spin-orbit, target orbital occupancies + total spin + local moment. Local Hilbert dimension 4^M — cost it out before committing.

**Proposal pattern:** "Going with: 3-orbital Kanamori impurity, density-density only, U=[value], J_Hund=[value], L_bath=4, half-filling. Target: orbital occupancies, total spin, local moment. Override any, or pick: full Kanamori (+ spin-flip + pair-hopping), 2-orbital, lattice context (→ out of current scope for runtime), single-orbital (→ anderson-impurity)."

Build per `.knowledge/conventions.md`. State which Kanamori terms are kept.

## Workflow

1. Cost out the local Hilbert space; if too large, push the user toward fewer orbitals or impurity-only setups.
2. Build interaction terms; document Kanamori relations and which terms are kept.
3. Pick method per the table.
4. First short run on a single-site or impurity problem; verify orbital occupancies and rotational invariance under SO(3) when full Kanamori is used.
5. Sweep convergence parameter; track observable.
6. Verify (next section).

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Single-site / impurity, small `M`, finite bath | ED pending refreshed references | `skills/method-ed/SKILL.md` |
| Multi-orbital impurity with longer bath chain | DMRG / MPS impurity solver | `skills/method-mps/SKILL.md` |
| Lattice multi-orbital | Out of current scope unless DMFT-embedded; flag explicitly. | — |
| DMFT impurity solver | Out of current scope to run; note the context. | — |

## Branch table

| Condition | Action |
|---|---|
| Single-orbital → user is actually doing `hubbard` | Switch to `hubbard`. |
| Question is about local-moment screening, Kondo, mixed valence | Call `kondo-effect`. |
| Question is about Mott / orbital-selective Mott | Call `mott-transition`. |
| Lattice context with self-consistent embedding | Surface DMFT framework as out of current scope. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `J_Hund = 0` reduces to multi-band Hubbard with only `U` and `U' = U`; full SO(3) rotational invariance only when full Kanamori is used; atomic limit at large `U/W` gives Hund's-rule multiplet (max total spin / orbital angular momentum).
- **Symmetry**: orbital occupancies; total particle count; `S^z` and total `S²` when SU(2) is preserved; rotational invariance check at the local level.
- **Hilbert space sanity**: confirm the basis size matches the analytic `4^M`-style count.
- **Convergence**: bond-dim sweep; bath-size sweep for impurity problems.
- **Cross-method validation** (when feasible) — re-solve at smaller orbital count or with density-density-only interactions as a sanity check; use ED only after `skills/method-ed/SKILL.md` is rebuilt. See AGENTS.md "Verification practice".

Optional check:

- For three-orbital Kanamori at canonical fillings, compare to published benchmarks where `U`, `J_Hund` match (e.g. the V-score paper arXiv:2302.04919).

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then route to `scientific-visualization`. See AGENTS.md "Writeup handoff".

## Related skills

`hubbard` (single-orbital reduction), `anderson-impurity` (impurity-flavored), `mott-transition`, `kondo-effect`.
