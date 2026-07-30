# DIRECT-CG MVP — SUMMARY (FINAL CUT scope; N=10 primary ruling)

2026-07-30, gates + six solves complete 15:56. Operational direct
replacement — deleted fine variables NEVER created (machine-asserted).
All numbers from soundness_gates.csv / build_costs.csv / solve_results.csv.
Chassis d=4, rdm=false, pso=0, lso=false; reference: N=10/8 high-precision
Bethe values; D=2 dual-parity map vumps_A_D2.json (recertified at load).

## Gates — ALL PASS (G0–G5 + Gmap + Gifc + G6bundle)

- G0: Gram-induced partition, frozen allowlists hashed. N=10:
  |W_full| = 527, |W_R| = 472, |W_D| = 55. N=8: DEGENERATE (|W_D| = 0 —
  closure(G_r=2) refills every separation on the 8-ring; A ≡ B) — kept as
  the control row per ruling.
- Gmap: per-parity isometry 5.1e-16 (CP/normalization); dual-parity flow
  identity residual 0.0 — the machine certificate, not a VUMPS energy.
- Gifc: all 3 coarse link pullback words lie in W_R (enumerated).
- G1: C-arm post-extension tsupp ≡ W_R exactly; seam_newwords = 0;
  deleted_words_created = 0.
- G2: objective class canon([1,4]) in W_R with exact coefficient.
- G3: coarse blocks Ω_4^p(y_ED) PSD (eigmin ≥ −1e-12); link residual
  ≤ 1e-10 over all rows; retained-Gram witness PSD.
- G4: link-coefficient sign-flip mutation goes RED (mutated E = +0.0999
  ≫ E0/N).
- G5: structural cost C/A = 20432/29315 = **0.697 — meets the preferred
  0.7 threshold at N=10** (largest block 66 vs 84). N=8 control: 0.805
  with no deletion possible (A≡B).

## Four arms at N=10 (+ degenerate control at N=8) — all OPTIMAL

| arm | E (per site) | psd_scalars | wall_s | rss_gb |
|---|---|---|---|---|
| A FullFine (r=5) | −0.4515446346 | 29315 | 19.6 | 1.21 |
| B RetainedCore (r=2) | −0.4515496061 | 19376 | 18.7 | 1.22 |
| C DirectCG | −0.4515496069 | 19376 | 19.1 | 1.25 |
| D DirectCG+Bundle | −0.4515496069 | 19397 | 18.8 | 1.25 |

- d = L_A − L_B = **+4.9715e-06, resolved-positive** (ε_cmp(A,B)=1.6e-08).
- Recovery UNRESOLVED as one-sided bounds: eta_CG < 0.525% of d,
  eta_total < 0.540% of d (central values −0.016%, inside the band);
  stated beside their cost ratios: structural 0.697, wall ≈ 0.97,
  RSS ≈ 1.03 (both ≈ parity; solver portion is seconds at this size).
- Orderings: L_B ≤ L_C ≤ L_D within ε_cmp ✓ (differences ≤ 8.1e-10 inside
  2.6e-08 band); every row ≤ E_Bethe + 5e-7 ✓; N=8 control: |C−B| =
  2.1e-10 ≤ ε_cmp ✓ (degenerate as predicted).
- A@10 lands 8e-10 above the N=10 Bethe value (inside the 5e-7 solver
  tolerance): r=N/2 saturates the relaxation at this size — d measures
  exactly the reach information that deletion removed.

## Bundle finding (G6bundle)

Declared W_bundle came out EMPTY at N=10: every closure/product word of
B_half (s=5) already lies in closure(G_r=2) — the same closure-refill
mechanism that degenerates N=8 absorbs this bundle at N=10. Assertion
created_words_D ∩ W_D = W_bundle = ∅ holds exactly (seam_newwords = 0);
D differs from C only by the 21-scalar Γ block over retained words and its
bound is identical to C within 1e-11. FINDING: at N=10 the declared
correction bundle does not reach W_D at all; a correction registry that
actually carries deleted-zone content must anchor on words in W_D (the 55
classes are enumerated in BASIS_PARTITION_N10.json) — future work, not
today's scope.

## Axis verdict (success axes split, patch §4)

- ARCHITECTURE: **GREEN** — all assertions, ED feasibility, mutation red,
  exact objective; deleted objects provably never created.
- COST: **GREEN structurally at N=10** (0.697, preferred threshold met)
  with realized wall/RSS at parity — unlike the morning's additive D=4
  tower (structural 0.85 came with 9x wall / 5.7x RSS at N=20), the D=2
  direct registry's 32-dim blocks are free in realized terms at this size.
- RECOVERY: UNRESOLVED (< 0.53% of d) — the single D=2 level carries no
  measurable reach information at N=10, and the declared bundle
  degenerates into the retained closure. The recovery axis needs either
  depth, larger windows, or W_D-anchored corrections — all out of today's
  scope by the FINAL CUT.

## Process notes

- First driver run aborted by the stop law on a G4 harness scope bug (the
  same top-level-try soft-scope class as the degate incident; ≤10-min
  mechanical fix; first-run gate CSV preserved as
  soundness_gates_run1_scopebug.txt). Gates were all green on the fixed
  rerun before any solve.
- The 15-minute read-only additive-tower audit (patch §2) PASSED with
  containment PROVEN: all 3 tower link words at N=14 lie inside the
  retained closure — the four-hour experiment's η attribution stands.
