# DirectCG N-EXTENSION — SUMMARY (tiers T0–T5, executed 16:57–17:35)

All rows from direct/solve_results.csv + direct/build_costs.csv (+ morning
A/B comparators per PROVENANCE_MATCH.md). Gates per N in
soundness_gates.csv (Gifc/Gobj/Ged rows; the first gateN run crashed on a
top-level soft-scope harness bug — same class as the two earlier incidents
— fixed ≤10 min, gates green on rerun before the blocked solves ran).

## The curve (DirectCG C vs fine-rich A; every eta beside its cost ratios)

| N | R_struct C/A | wall C/A | RSS C/A | d = L_A−L_B | recovery central | one-sided bound |
|---|---|---|---|---|---|---|
| 10 | 0.697 | 0.97 | 1.03 | +4.972e-06 | −0.016% | < 0.525% |
| 12 | 0.611 | 1.01 | 0.99 | +3.070e-05 | +0.019% | < 0.072% |
| 14 | 0.542 (29014/53563) | 0.87 | 0.90 | +4.679e-05 | +0.010% | < 0.096% |
| 20 | 0.383 | 0.75 | 0.51 | +1.566e-04 | +0.001% | < 0.219% |
| 26 | 0.345 (build-only) | — | — | — | — | — |
| 30 | 0.336 (build-only) | — | — | — | — | — |

N=20 is the first configuration in the campaign where replacement is
cheaper on BOTH axes (structural 0.383, wall 0.75, RSS 0.51) — at a still
unresolved recovery. All tripwires pass; every d resolved-positive.

## C4 — the block-dimension isolation (settles the C13 mechanism)

Same N (14), same retained basis (allowlist r_of(14)), same level count
(one), same link-family generator; ONLY the map package changes
(D=2, dω=16, 66-dim embedded blocks, 64 link rows → D=4, dω=64, 128-dim
blocks, 256 link rows). Own map certificate (isometry 1.54e-15, flow
1.14e-16) and own ED gate (residual 1.7e-15 over 256 rows) passed first.

| arm@N=14 | R_struct | wall vs A | RSS vs A |
|---|---|---|---|
| C (D=2) | 0.542 | 0.87 | 0.90 |
| C4 (D=4) | 0.830 (44470/53563) | 2.37 | 6.80 |

Realized cost jumps 2.7x (wall) / 7.6x (RSS) relative to C from the map
package change alone, while the structural ratio stays below 1. Claim
boundary honoured: attribution is to the D=4 one-level PACKAGE
(block dimension + its dω-scaled row count); within that boundary the
result localizes the additive tower's realized cost (14 such blocks,
16.3 G; one level already 9.4 G) to PSD block dimension rather than model
size or level count.

## Bundle channel — pre-registration FALSIFIED

wbundle_table.csv: W_bundle = 0 for ALL four pool bundles at ALL
N ∈ {10,12,14,20} (the T2 pre-registration expected B_half to become
nonempty by N=14–20: MISS; the edge bundles staying empty: HIT).
Mechanism: the translation-quotiented Gram closure of the retained basis
already contains every plain pair/bond product class at every tested N;
W_D consists of other (extended/mixed) classes. Consequence recorded: D =
STRUCTURALLY_ABSORBED at N=12/14/20 (label FIXED_B_HALF_CORRECTION_
NO_SELECTION never yielded an independent test); a correction registry
that reaches W_D must anchor on the enumerated W_D classes themselves
(55 at N=10, BASIS_PARTITION_N10.json).

## Order-of-record notes

- Execution followed the patch order (provenance → C14* → wbundle → D14 →
  C20 → D20 → C4@14* → N12 grid → 26/30 builds); (*) C14 and C4@14 were
  gate-blocked by the harness bug at first pass and solved after the
  gate rerun (17:2x–17:3x), i.e. later than their slot — with gates green
  before each solve, per the size-specific gate law.
- N=12 C solve preceded its Ged_D2_N12 row (harness bug window); the gate
  passed post hoc (residual 1.4e-16). Deviation recorded here; row valid.
