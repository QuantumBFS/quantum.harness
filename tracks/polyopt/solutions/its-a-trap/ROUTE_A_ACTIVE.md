# ROUTE_A_ACTIVE — the agent executes from THIS file alone
(Amendment 2, adaptive form, Wed ~13:45. Rules by reference: ε_cmp, sign
rules, terminology, claim language = LAW.md. Family birth deadline 22:00.)

H_reach: the N=100 CONFIG A deficit (gap 2.364e-5 vs the paper's 8.3e-6) is
two-body-basis reach undercoverage (r = extra+1 = 5 fixed vs paper r≈⌈N/2⌉).

## A0 semantics gate — PASS (measured Wed 13:0x, routeA-20260729/step0)

- m: 1819 (r=5) < 1890 (r=7) = 1890 (r=14): growth + wrap plateau ✓
- E₅ = −0.4473967708 ≤ E₇ = −0.4473967065, Δ=+6.4e-8 > ε_cmp(≤4.4e-8) ✓
- r=14 (> ⌈N/2⌉): INFEASIBILITY_CERTIFICATE — separation-N wrap words put
  two letters on one site; loud model failure, NOT silent no-op. Safe
  domain: r ≤ N/2. (Screen max extra=49 → r=50 = N/2 at N=100 ✓.)
- Historical −0.4473967065 reproduced EXACTLY at rdm=8, pso=3, lso=true —
  provenance note on the Tuesday scan; diagnostic only.

## A1 first wave (SCNet, rdm=8, N=100) — THREE cells

- ACTIVE: rA_e4 (22991017, baseline), rA_e24 (22991019), rA_e49 (22991021);
  32c/110-cap, 64c/230-cap, 64c/230-cap.
- HELD by this amendment: rA_e14 (22991018), rA_e34 (22991020) — the at-most-
  ONE conditional fill releases 22991018 (early saturation) or 22991020
  (still rising). Never both.
- v100e8hi2 (rdm=10, r=9) is REASSIGNED to the rdm=10 reach curve
  (r=5 [=v100hi], r=9 [=v100e8hi2], future r*); it is NOT an rdm=8 point.

## A2 verdict (mechanical, in order)

1. Nested-monotonicity gate FIRST: E₅ ≤ E₂₅ ≤ E₅₀ within ε_cmp.
   Violation → audit basis nesting / wrap / parsing BEFORE interpretation.
2. r* = min{r : Δ_r(r) ≥ 0.9·Δ_r(50)}, Δ_r(r) = E_{8,r} − E_{8,5}.
3. At most ONE fill point: release e14 if early saturation, e34 if rising.
4. No resolved gain → report VERBATIM: "no resolved reach gain was observed
   on the rdm=8 screening relaxation; the hypothesis was not escalated to
   the rdm=10 test" — a resource decision, never "H_reach rejected".

## A3 confirm (after arbiter sees the A2 table)

- MANDATORY construction-only probe first: log m, PSD block signature,
  constraint nnz, build RSS; abort if build alone nears the node limit.
- Then ONE cell: N=100, rdm=10, extra = r*−1.
- Readout: 3-point rdm=10 reach curve (r = 5, 9, r*) vs 8.3e-6.
- Language: consistency-only (LAW.md Route A pre-written sentences).

## A4 N=200

Unchanged: fraction p = r*/50 deployment; requires confirm improvement AND
budget AND Thursday freeze capacity. Arbiter GO required.

## Report points

(i) A0 — done (above). (ii) after A2: Δ_r/m/RSS table + r* + confirm price
→ WAIT. Stop lines: no Route B; no N=200 large-reach without GO.
