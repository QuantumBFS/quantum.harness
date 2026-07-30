# FOUR-HOUR OPERATIONAL COARSE-REPLACEMENT + MOMENT-POOL TEST — SUMMARY

2026-07-30, T0=13:25, mandatory grid complete 13:56 (0:31), full driver +
degate re-run complete 14:42. Operational replacement prototype — NOT a
completed implementation of Sec. III-D-2. All numbers below are from
replacement_build.csv / replacement_solve.csv / replacement_summary.csv only.
Chassis: d=4, rdm=false, pso=0, lso=false. Reference: high-precision Bethe
values (hpc/refs/bethe_ref.json). One process per solve, 18 GiB cap, 1800 s,
no retry.

## Headline findings

1. **Structural-cost crossover CONFIRMED (pre-registered §6).** PSD-scalar
   ratio C6/A: 1.447 (N=14) → **0.848 (N=20)** → 0.610 (N=26, build) →
   0.530 (N=30, build); cons-nnz ratio at N=30 is 0.35. Tower structural
   cost is nearly flat (77k → 132k scalars over N=14→30) while fine-rich
   reach (r=N/2) grows 54k → 250k.

2. **Realized solver cost is NOT reduced at tested sizes.** Wall ratio
   C6/A = 10.7 (N=14), 9.0 (N=20); RSS ratio 11.8 (N=14), 5.7 (N=20).
   The tower's fourteen 128-dim dual Z blocks dominate MOSEK's actual work;
   the scalar count undersells them. Both realized ratios DECREASE with N,
   consistent with (1), but remain ≫ 1 at N ≤ 20.

3. **Accuracy recovery is a measured negative.** d = L_A − L_B is
   resolved-positive at both sizes (+4.679e-05 @N=14, +1.566e-04 @N=20) —
   the reach axis resolves exactly as Route A motivated. But
   eta_CG(6) = +0.0013 (N=14) and +0.0003 (N=20): the depth-6 tower
   recovers essentially none of the truncated-reach information (C6−B is
   inside ε_cmp at both sizes). Pre-declared branch of record: "cheaper
   (structurally) but gives no resolved recovery."

4. **Pool/transferred marginals are untestable under today's local memory
   law.** D (C6+full pool) and E (C6+transferred pair) were OOM-killed at
   the 18 GiB cap at BOTH sizes (journalctl oom-kill evidence; C6 alone
   peaks at 16.3–16.4 GiB on this chassis). eta_pool_given_CG,
   eta_transferred_given_CG, eta_residual_given_E, eta_total: NOT
   MEASURABLE today; frontier rows retained.

5. **Depth lane.** C10@N=20: admission PASS (ED substitution of the n=10
   tower at N=14 — all ω blocks PSD to 1e-16, 1792 link rows ≤ 1.7e-15;
   structural counts recorded: psd 156k > A@20's 107k, i.e. deeper towers
   REVERSE the structural saving) but solve OOM at 18 GiB → frontier row.
   C14: UNAVAILABLE (dense-ED ceiling N=14 < n+1; and depth short-circuit
   after C10 failure).

6. **Validity.** Every accepted row obeys L ≤ E_Bethe + 5e-7. L_B ≤ L_A at
   both sizes (patch 3b: the extra-override kwarg acceptance test — PASS,
   no IMPLEMENTATION RED). L_B ≤ L_C6 within ε_cmp at both sizes. Required
   orderings involving D/E: NA (arms OOM).

## Interpretation vs pre-registered criteria

Success required R_cost_D < 1 AND eta_total resolved-positive: **NOT MET**
(D unmeasurable; eta_CG ≈ 0). The result of record is the pre-declared
measured-negative branch, refined: the structural cost crossover is real
and monotone in N, but at n=6 the coarse representation carries almost no
additional spectral information on this truncated chassis, and its dual
blocks are expensive in realized solver terms at N ≤ 20. Any claim that
coarse replacement "reduces cost at matched accuracy" is NOT supported at
tested sizes; the supported statement is the crossover of structural size
plus the resolved reach-axis gap it would need to close.

## Process notes

- degate (full-pool ED substitution + B_pair_edge diagonal-negation
  red-test): first run FAIL was a harness defect (top-level try soft-scope
  swallowed the mutation verdict); after the ≤10-minute mechanical fix the
  gate PASSes with mutated-E = +0.563 ≫ E_Bethe (RED as required). Both
  records retained; D/E were solved only after the gate passed — and then
  hit the memory frontier.
- Arm configs: printed + sha256-hashed pre-solve; replacement_configs.jsonl
  → configs.json.
- Depth-nesting source inspection (v4 §2): build_tower blocks/links for
  shared M are constructed identically and blk indices are n-independent →
  constraint-set nesting HOLDS; the C6 ≤ C10 ordering would have been
  imposed had C10 solved.
