# LAW — frozen rules (freeze-time grep and tier sentences copy from HERE)

## Terminology (per-source, once, everywhere)

| output | mandated term |
|---|---|
| SDP results | "numerical SDP lower bounds" |
| DMRG results | "variational upper bounds" |
| Bethe results | "high-precision Bethe references" |
| MG point J2=0.5, −0.375/site | may be called **exact** |

"certified" is BANNED everywhere. "CONFIG-A-equivalent" is BANNED for 2D
cells (full knob vector named per cell). The tower is never "a synergistic
moment set"; permitted phrase: "constraint-family complementarity
hypothesis".

## Primary metric

Signed per-site reference gap: `gap = E_Bethe − E_LB` (Bethe rows) or
`bracket_width = E_DMRG_upper − E_LB` (DMRG rows). Relative error is
supplementary only. Both columns in every CSV row and table.

## ε_cmp (replaces every bare tolerance in Δ classification)

`ε_cmp(a,b) = (g_a+g_b) + κ·(pfeas_a+dfeas_a+pfeas_b+dfeas_b) + (s_a+s_b)`
g = solver duality gap (MU); pfeas/dfeas = feasibility residuals; κ =
code-generated problem-scale factor; s = assembly residuals (oracle rows
for tower arms, 0 for stock). Classification: Δ > ε_cmp resolved-positive;
|Δ| ≤ ε_cmp unresolved; Δ < −ε_cmp per the sign rules below.

## Sign rules (exact-arithmetic grounds in cg_hybrid/THEOREM_CONTRACT.md §3)

- ΔCG8 = E(A_n*) − E(B8) ≥ 0; ΔCG8 < −ε_cmp = bug: stop, fix, no scale runs.
- ΔCG10 = E(C) − E(B10-E) ≥ 0, same rule.
- Δreplace = E(A_n*) − E(B10-E): NO sign constraint; negative is a valid
  result, reported signed.
- Monotonicity: E_6 ≤ E_9 ≤ E_13 within ε_cmp. Saturation: smallest n with
  per-level gain below max(5e-8, 0.05·(E_n − E(B8))) on two consecutive
  intervals.

## Claim ladder (report uses the highest tier EARNED, sentence verbatim)

Energy vs B10-E; time/memory vs B10-C (the fresh isolated M0-C CONFIG A
N=14 stock arm: wall 2155 s, RSS 14.09 GB); thresholds are ε_cmp.

| tier | condition | permitted sentence |
|---|---|---|
| 1 | E(A) ≥ E(B10-E) − ε_cmp AND T(A) < T(B10-C) AND M(A) < M(B10-C) | "the CG tower replaces the rdm=10 constraint family at lower cost" |
| 2 | E(A) < E(B10-E) but meets the relevant target accuracy | "the CG tower provides a cheaper target-sufficient alternative" |
| 3 | E(A) > E(B8) + ε_cmp only | "the CG tower tightens the rdm=8 baseline" |
| below | — | report the signed numbers and claim nothing |

## Route A pre-written language (consistency-only)

- Closed: "consistent with Table 3 using an N-dependent reach r ≈ N/2; the
  fixed-r=5 large-N deficit is explained by basis undercoverage." NEVER
  "identified the paper's configuration".
- Not closed: "reach extension to r=50 leaves a residual of X per site; the
  deficit is not (only) reach undercoverage."

## Track-2 gate definitions

- M0-C: |E_adapter − E_GSB| ≤ 1e-8 at N=10/14 × {CONFIG A, rdm=8} — GREEN
  (4/4 exact 0.0, method-lane commit 7e5d48c).
- M1: sandwich + strict unitary oracle + flow ≤1e-12 + ED feasibility
  ≤1e-10 + level monotonicity — GREEN (lossless-equality replaced by
  sandwich + oracle; GATE NOTE measured).
- THEOREM_CONTRACT.md: four mandated sections; numerical gates are echoes,
  never substitutes. Blocking before any M2 arm.
- F0 triggers (any of three): ΔCG null · deadline missed · contract cannot
  close.

## Standing rules

- QMBCertify checkout byte-untouched (chmod a-w); the ONE sanctioned fork
  is GSB_cg (sha-pinned textual fork). The 2D resort monkey-patch is
  EXTERNAL (@eval), method-lane only, arbiter-approved, recorded per row.
- No row, no claim. A measured miss is a result. Killed/failed cells record
  status N/A, never inferred OPTIMAL.
- Every quoted Δ carries its ε_cmp value and components.
- arXiv:2607.14755 gets ONE paragraph with exactly four clauses (moment
  contributions non-uniform/non-additive; 1D chain N=9,10 shows local basis
  compressible but not globally optimal; motivates budget-aware selection
  as future work; we implement none of PT/RBM/BO and compute no marginal
  synergy).

## Freeze-time audit greps

- report contains no "certified"; "exact" only at the MG point;
- SDP/DMRG/Bethe rows use the mandated terms verbatim;
- every number traces to a CSV row; tier sentence is copy-pasted from the
  table above.
