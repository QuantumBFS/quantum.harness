# FOUR-HOUR OPERATIONAL COARSE-REPLACEMENT + MOMENT-POOL TEST — SUMMARY

2026-07-30, T0=13:25. Mandatory grid (B, C6, D, A at N=14, 20 = 8 cells):
**6/8 OPTIMAL + 2/8 resource-frontier (D@14, D@20 at the 18 GiB local
frontier)**. Six OPTIMAL rows landed by 13:56; the two D cells were
gate-blocked at first pass, and after the degate harness fix reached the
memory frontier at 14:25–14:42. Operational replacement prototype — NOT a
completed coarse replacement and NOT an implementation of Sec. III-D-2.
All numbers are from replacement_build.csv / replacement_solve.csv /
replacement_summary.csv only. Chassis: d=4, rdm=false, pso=0, lso=false.
Reference: high-precision Bethe values (hpc/refs/bethe_ref.json). One
process per solve, 18 GiB cap, 1800 s, no retry; killed rows retained as
rows with status.

## Main result

The operational coarse-replacement prototype exhibits a clear separation
between structural and realized solver cost. The PSD-scalar ratio of the
depth-6 tower relative to the fine-rich reach comparator decreases from
1.447 at N=14 to 0.848, 0.610 and 0.530 at N=20, 26 and 30, establishing a
structural crossover between N=14 and N=20. At the solved sizes, however,
the tower remained substantially more expensive in wall time and peak RSS.
The truncated reach gap was resolved, whereas the depth-6 tower recovered
less than ~0.56% (N=14) and less than ~0.14% (N=20) of the resolved reach
gap — the numerator lies inside the comparison band while the denominator
is resolved (d = 4.679e-05 and 1.566e-04 per site). Full-pool and
deeper-tower solves reached the 18 GiB local-memory frontier, so their
accuracy contributions remain unavailable. Coarse graining therefore
reduced structural model size at moderate N, but the current
interior-point formulation did not yet convert that reduction into lower
realized cost or resolved accuracy recovery.

## Findings

1. **Structural crossover (pre-registered §6) confirmed.** PSD-scalar
   ratio C6/A: 1.447 (N=14) → 0.848 (N=20) → 0.610 (N=26, build) →
   0.530 (N=30, build); cons-nnz ratio at N=30 is 0.35. Tower structural
   size is nearly flat (77k → 132k scalars over N=14→30) while the
   fine-rich reach basis (r=N/2) grows 54k → 250k.

2. **Realized solver cost still favors A at the solved sizes.** Wall ratio
   C6/A = 10.7 (N=14), 9.0 (N=20); RSS ratio 11.8 (N=14), 5.7 (N=20);
   both decrease with N but remain ≫ 1.

3. **PSD-scalar count is an unreliable cost proxy when block-dimension
   distributions differ** (not pre-registered; the most transferable
   observation). At N=20 the structural ratio is 0.85 while the wall and
   RSS ratios are approximately 9x and 5.7x. The tower concentrates its
   scalars in dimension-128 blocks, for which the interior-point method
   pays super-linearly.

4. **Accuracy recovery: UNRESOLVED, stated as a one-sided bound.**
   d = L_A − L_B is resolved-positive at both sizes (+4.679e-05 @N=14,
   +1.566e-04 @N=20). L_C6 − L_B lies inside the comparison band at both
   sizes (central values +0.13% and +0.03% of d, both positive), so
   eta_CG(6) is bounded: < eps_cmp/d = 0.557% (N=14) and 0.139% (N=20).
   The bound TIGHTENS with N, consistent with window geometry: the
   eliminated zone grows to separation N/2 while the tower's window stays
   at ~6 sites. Two points only. Cost context for these bounds: the same
   C6 arm carries wall/RSS ratios 10.7x/11.8x (N=14) and 9.0x/5.7x (N=20).

5. **Full-pool and transferred-pair marginals: resource-frontier, not
   numerical failure.** D (C6 + full declared pool) and E (C6 +
   transferred fixed bundle) reached the 18 GiB local-memory frontier at
   both sizes (journalctl oom-kill records; C6 alone peaks 16.3–16.4 GiB
   on this chassis). eta_pool_given_CG, eta_transferred_given_CG,
   eta_residual_given_E, eta_total: UNAVAILABLE today; frontier rows
   retained with status.

6. **Depth lane.** C10@N=20: deeper-tower validity passed (1792 link rows,
   residual <= 1.7e-15, all ω blocks PSD at the ED state); its
   interior-point solve crossed the local 18 GiB frontier. The
   mathematical interface passed; the solve route failed. Structural
   counts: psd 156k > A@20's 107k — deeper towers REVERSE the structural
   saving. C14: UNAVAILABLE (dense-ED ceiling N=14 < n+1, and depth
   short-circuit after C10).

7. **Validity.** Every accepted row obeys L ≤ E_Bethe + 5e-7. L_B ≤ L_A at
   both sizes (patch 3b acceptance of the extra-override kwarg — PASS).
   L_B ≤ L_C6 within eps_cmp at both sizes. Orderings involving D/E: NA
   (resource-frontier).

## Interpretation vs pre-registered criteria

Success required R_cost_D < 1 AND eta_total resolved-positive: NOT MET —
D is at the memory frontier and eta_CG(6) is unresolved (bounded above by
0.56%/0.14%). No cost-at-matched-accuracy claim is supported at tested
sizes. No extrapolation of a realized-cost crossover is made: two solved
points, and the solve-side mechanism remains open.

## Future work (not conclusions)

The program's scalar-count cost budget requires block-dimension weighting;
the first-order / chain-KKT solver item moves from fallback to
load-bearing — now quantified at two sizes rather than resting on one open
number.

## Process notes

- degate (full-pool ED substitution + B_pair_edge diagonal-negation
  red-test): first run FAIL was a harness defect (top-level try soft-scope
  swallowed the mutation verdict); after the ≤10-minute mechanical fix the
  gate PASSes with mutated-E = +0.563 ≫ E_Bethe (RED as required). Both
  records retained; D/E solves were attempted only after the gate passed —
  and then reached the memory frontier.
- Arm configs printed + sha256-hashed pre-solve; replacement_configs.jsonl
  → configs.json (28 entries).
- Depth-nesting source inspection (v4 §2): build_tower blocks/links for
  shared M are constructed identically and blk indices are n-independent →
  constraint-set nesting HOLDS; the C6 ≤ C10 ordering would have been
  imposed had C10 solved.
