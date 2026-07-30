# CAMPAIGN INVENTORY — challenge #49, team its-a-trap (facts + provenance only)

Compiled 2026-07-30 ~17:20 CST. Sources: repo = PR #193 branch
challenge/polyopt-coarse-grained-npa (head 2e64247 at compile time; direct
N-extension rows local, not yet pushed). RS = tracks/polyopt/solutions/
its-a-trap/rg_selection. Values not traceable to a CSV row / commit are
marked UNTRACED.

## 1. NUMBERS

| quantity | value | source | class |
|---|---|---|---|
| R_struct additive C6/A @N=14/20/26/30 | 1.447 / 0.848 / 0.610 / 0.530 | RS/results/replacement_build.csv (psd_scalars rows C6,A per N) | resolved (exact counts) |
| R_struct DirectCG C/A @N=10/12/20/26/30 | 0.697 / 0.611 / 0.383 / 0.345 / 0.336 | RS/direct/build_costs.csv (C rows; A@20-30 from replacement_build.csv) | resolved; C@14 pending at compile |
| 30.3% figure | 1 − 20432/29315 @N=10 | RS/direct/build_costs.csv rows 10,C / 10,A | resolved |
| largest PSD block: additive tower / DirectCG / fine-rich A | 128 / 66 / 84(N=10) 96(14) 114(20) 132(26) 144(30) | replacement_build.csv, direct/build_costs.csv | resolved |
| realized additive C6/A: wall, RSS @14/20 | 10.7x, 11.8x / 9.0x, 5.7x | RS/results/replacement_summary.csv | resolved |
| realized DirectCG C/A: wall @10/12/20 | 0.97 / 1.01 / 0.75 | direct/solve_results.csv ÷ same or replacement_solve.csv A rows | resolved (wall load-dominated at 10/12) |
| realized DirectCG C/A: RSS @10/12/20 | 1.03 / ~1.04 / 0.51 | same rows (rss_gb) | resolved |
| d = L_A − L_B @N=10/12/14/20 | +4.9715e-06 / +3.070e-05 / +4.679e-05 / +1.566e-04 | direct/solve_results.csv (10,12); replacement_solve.csv (14,20) | resolved-positive (each > ε_cmp) |
| recovery bounds, additive C6 @14/20 | < 0.557% (ε_cmp 2.607e-07) / < 0.139% (ε_cmp 2.182e-07) | replacement_solve.csv rows via LAW ε_cmp; replacement_summary.csv | one-sided bound |
| recovery bounds, DirectCG @10/12/20 | < 0.525% (ε 2.61e-08) / < 0.073% (ε ~2.2e-08) / < 0.219% (ε 3.43e-07); centrals −0.016% / +0.019% / +0.007% | direct/solve_results.csv rows, ε_cmp per LAW | one-sided bound |
| C13 counts (proxy failure point) | N=20: psd 90367 (C6) vs 106615 (A) = 0.848 at wall 9.0x | replacement_build.csv + replacement_summary.csv | resolved |
| pool/bundle marginal scalars (D − C) | +21 (N=10, also 12), +36 (26), +55 (30) | direct/build_costs.csv D vs C rows | resolved |
| W_bundle per bundle per N (4 bundles × N=10/12/14/20) | ALL 16 cells = 0 | RS/direct/wbundle_table.csv | resolved |
| map certificates: isometry D2 / D4 | 5.09e-16 / 1.54e-15 | direct/soundness_gates.csv Gmap1 rows | resolved |
| flow identity (dual parity) D2 / D4 | 0.00e+00 / 1.14e-16 | direct/soundness_gates.csv Gmap2 rows | resolved |
| ED link residuals: tower(768 rows) / n=10 tower(1792) / direct D2@N=10 / direct D2@N=14 | 1.7e-15 / ≤1.7e-15 / PASS at 1e-10 (G3b) / 1.4e-15 over 64 rows | results/vcheck.csv V1; direct/depth_admit_n10.txt; direct/soundness_gates.csv G3b, Ged_D2_N14 | resolved |
| oracle / compatibility (G2) | 2.78e-10 / 1.14e-16 | RS/results/gates.csv G2a, G2b | resolved |
| mutation-red values | V3 +0.4689; R3 +0.0102; degate +0.563; direct G4 +0.0999 | results/vcheck.csv; results/a200_release_gates.csv; results/replacement_degate.txt; direct/soundness_gates.csv | resolved (all red) |
| T1 best row | E_LB −0.4432395015 @N=100 r=9, gap +9.931e-06 | freeze/MASTER.csv v100e8/scnet-20260729-001929 | resolved |
| T1 ladder N=50–140 (r=5) gaps | +1.638e-05 … +2.476e-05 | freeze/MASTER.csv v50–v140 rows | resolved |
| T2 brackets J2=0.2/0.4/0.5/0.6/0.8/1.0 | +3.469e-05 / +5.006e-04 / −4.304e-09 (MG exact) / +7.616e-04 / +4.210e-03 / +6.561e-03 | freeze/MASTER.csv T2 rows + dmrg refs | resolved per row |
| T4 rows 10×10 J2=0.2 / 0.5 | −0.6007562490 (bracket ≈3.3e-3) / −0.5116536004 (≈1.5e-2) | freeze/MASTER.csv c2d10_j02 / c2d10_j05; brackets vs published variational: UNTRACED to machine-readable ref (prose only) | resolved / ref-untraced |
| T3 probe chain L=4/6/8 | −0.7024963 (vs exact −0.7017802) / −0.6821741 / −0.6789488; basis rows 20854→30928 (L=6→8) | freeze/MASTER.csv t2d rows; hpc/2d/check_row.jl:25 (ref) | resolved; 16×16 conceded |
| N=200 frontier data | CONFIG A build >11.7h no solve; 64c V_{S*} TIMEOUT 6h/182G; 128c probe TIMEOUT 6h/MaxRSS 174G in construction; pair 23009660 24h-wall RUNNING (>8h at compile) | n200 state files; sacct 23009659; A200_DEPLOYMENT_RECORD.md | frontier rows |
| N=14 holdout (additive-family, training chassis) | joint − base = +5.5e-09 vs ε_cmp ≈1.5e-07 | audit/holdout.csv (from g4_arms.csv) | unresolved-null |
| partitions | N=8: 145/145/0; N=10: 527/472/55 (W_full/W_R/W_D) | direct/BASIS_PARTITION_N8.json, _N10.json | resolved |

## 2. WORK INVENTORY (chronological; commit times CST)

| when | attempted | tested | outcome | artifact |
|---|---|---|---|---|
| 07-27 16:25 | register challenge #49 | — | PR #193 opened | 8b95732 |
| 07-28 00:42–10:33 | overnight reproduction protocol + harness + ladder | reproduce arXiv:2604.01555 Table 3 | v10/v14 match to 7 digits; ladder N≥18 killed in construction (MAX_WALL); rdm=8 ladder to N=40 | aacfde8, 8c7ca8d, b30c653, 77d1a0f; RESULTS.md |
| 07-28 13:43 | literature contract (Kull III-D-2 vs QMBCertify) | scope the method gap | contract written | eb4a006 |
| 07-28 17:14 | bethe_ref.jl 5-part validation | reference integrity | ED cross-check ≤1e-10 N=8-14 | d039125 |
| 07-28 17:20–19:41 | targets queue v1-v2 (local cells) | T1/T2 cells | gap/ref columns, J2@N=40 | 357fa3f, 94b5c82 |
| 07-28 18:43 | Track2 M0 recon + THEOREM_CONTRACT + tower module M1 | seam location + tower validity | M1 gates green | ba5f99e |
| 07-28 20:16 | GSB_cg textual fork (sha-pinned seam) | untyped tower hook | fork + interface contract | 07f920c |
| 07-28 20:40 | ω-tower generator + first coupled hybrid | tower↔GSB coupling | all gates green | 3ad0977 |
| 07-28 20:43–23:58 | SCNet bundle + queue v3/v4 | cluster T1 ladder + J2@100 | shipped; partition/QOS fixes | e286276…57a3b05 |
| 07-29 00:19–00:36 | SCNet partition move; 2D attempt | 2D chain | upstream resort bug found; fix prepared | 4e0d7c1, 1a41331 |
| 07-29 03:35–06:24 | M0-C regression gate | fork ≡ stock on 4 pairs | GREEN 4/4 exact | 64002ad, 7e5d48c |
| 07-29 07:51 | arbiter: release v120/v160, approve resort monkey-patch | — | 2D unblocked | 94750f6 |
| 07-29 08:22 | two-parity ω-tower + 2-site VUMPS D=2 | 1-site trap bypass | V-gates green; e=−0.42791 | f41c3bd; cg_hybrid/vumps_A_D2.json |
| 07-29 09:35 | M2 D2 arms verdict + D4 tensor | tower tier vs rdm | unresolved-positive; D4 arms exceed laptop | 5e89867 |
| 07-29 10:15–11:49 | governance split; Route A amendments 2-3 | reach-vs-knob attribution | adaptive + additive-pricing rules | f1c82ad, 546fb6a, f7a15a3 |
| 07-29 13:15 | DMRG upper bounds N=100 J1-J2 | T2 brackets | 6 J2 points | e4d6001 |
| 07-29 15:10–15:38 | rg_selection G0 (plan-of-record, pool freeze); Route A CLOSED | selection protocol; reach finding | pool hash frozen; reach ≈ N/2 is the lever | 599ec8d, b112e2b |
| 07-29 16:22–16:45 | Gates G1 (identity/neutrality/orbits), G2 (oracle/compat/sandwich) | builder + tower soundness | GREEN | 97e5cf5, bef4bbb, 8896fcb |
| 07-29 17:23–18:50 | G3 exact enumeration (28 evals) + vcheck suite | selection training + V1-V4 | orderings 28/28; V-battery green | 05e4af7, 306b8a1 |
| 07-29 22:04 | N=200 deployment kit (probe/pair runners) | target-scale feasibility | shipped | cebb8da |
| 07-30 00:14–00:39 | selection freeze S*; V3@N=14; G4 holdout | blind selection + holdout | S*={B_bond_edge,B_half}; holdout unresolved-null +5.5e-9 | a948a9b, 8893d60 |
| 07-30 02:41 | N=200 release ruling | mechanical 02:30 law | BLOCKED (no blind release) | 4b2a8d2 |
| 07-30 05:43 | 128c probe (23009659) started | V_{S*}(200) construction | TIMEOUT 6h / 174G in construction | sacct; A200_DEPLOYMENT_RECORD.md |
| 07-30 08:25–08:36 | R-night documentation; freeze candidate; pair released | — | MASTER.csv 74 rows; 23009660 running | f27403e, a80fc54, bef4dc6 |
| 07-30 09:00–10:50 | Amendments 4/4A/4B/4C: A200 adaptive-only | replacement-chassis N=200 | R1+R2+R3+R4b PASS at N=10; fresh selection → pilot (window infeasible); R4c killed; A200 CANCELLED by override; read-only diagnostic delivered (~/diag_extract.md) | 91af879 |
| 07-30 11:04–11:54 | Thursday delivery + probe harvest revision | report/audit | PR pushed e8c93ae → 67df8ac; PR title fixed | e8c93ae, 67df8ac |
| 07-30 13:25–14:45 | FOUR-HOUR replacement lock (A/B/C6/D/E, N=14/20; builds to 30; depth C10/C14) | additive coarse cost + recovery | 6/8 OPTIMAL + 2/8 frontier; crossover confirmed; eta unresolved; D/E/C10 OOM | 06e335f, 3ed38ac; replacement_*.csv |
| 07-30 14:52–15:16 | pre-push reconciliation + push | count/terminology per directive | pushed 5079129 | 5079129 |
| 07-30 15:25–16:00 | DIRECT-CG MVP (final cut; N=10 primary ruling) | true deletion + D=2 registry | all gates PASS; 0.697 at realized parity; recovery <0.53%; bundle absorbed; N=8 degenerate control | 29e2205, b664e86; direct/* |
| 07-30 16:0x | report restructure by finding + push | — | pushed 2e64247 | 2e64247 |
| 07-30 16:57–17:1x | DirectCG N-extension (patch order) | de-confound C@N; curve; bundle test | C20 OPTIMAL (0.383 struct / 0.75 wall / 0.51 RSS); wbundle all-zero; N12 grid OPTIMAL; C14/C4 gate-harness scope bug → fixed, gates rerun in progress | direct/solve_results.csv, wbundle_table.csv; local (unpushed) |

## 3. PREMISES FALSIFIED

| premise as held | killed by | number | recorded |
|---|---|---|---|
| Table-3 deficit attributable to rdm/pso/lso knobs | step2/step3 knob deltas at N=14 | δ_pso, δ_lso ~1e-8 (unresolvable at tol 1e-8); δ_rdm ~2.2e-06 only | RESULTS.md §2-3; Route A closure b112e2b |
| N=200 blocked by a MEMORY wall | 128c probe ended in TIME limit with RSS well inside scope | TIMEOUT 6:00:03, MaxRSS 174G < 460G scope | sacct 23009659; A200_DEPLOYMENT_RECORD.md |
| target-scale model construction is cheap relative to solve | CONFIG A N=200 construction alone | >11.7 h wall, no solve started | n200 state files; FINAL_REPORT C3 |
| Full−Core gap at N=14 usable as an η denominator | holdout on training chassis | +5.5e-09 ≤ ε_cmp 1.5e-07 (unresolved-null) | audit/holdout.csv |
| 17G selection-arm RSS caused by seam word growth ("real load") | read-only build probes: all builds ≤1.4G, seam_newwords=0 | 9 rows ≤1.41G vs 16.9G observed in solve | ~/diag_extract.md §1 (outside repo); A200_DEPLOYMENT_RECORD.md |
| PSD-scalar count is a usable cost proxy | additive N=20 structural vs realized | 0.848 structural vs 9.0x wall / 5.7x RSS | replacement_summary.csv; FINAL_REPORT §1 |
| W_bundle(B_half) becomes nonempty by N=14–20 (tier-plan pre-registration) | wbundle enumeration | 0 at every bundle × N ∈ {10,12,14,20} | direct/wbundle_table.csv |
| 1-site TI VUMPS suffices for the coarse map | spurious fixed points | ferro e=+0.25; Néel-cat −0.25 | vumps_tensor.jl header (history note) |
| N=8 usable as the smallest deletion demonstrator (FINAL CUT scope) | Gram-closure refill | W_D = 0 at N=8 (145/145) | direct/BASIS_PARTITION_N8.json |

## 4. PRE-REGISTRATIONS

| prediction | written (before data) | outcome |
|---|---|---|
| reach r ≈ N/2 recovers the Table-3 large-N deficit | Route A directive/amendments (546fb6a, f7a15a3) before reach cells ran | HIT (v100e8 gap +9.931e-06; closure language b112e2b) |
| G4 classification branches incl. unresolved-null | G0 plan-of-record + preregistration (599ec8d) before holdout | branch taken: unresolved-null (holdout.csv) |
| R_cost structural ratio decreases with N (tower ~fixed, reach grows) | v4 §6 (plan file, 13:2x) before build scan | HIT (1.447→0.530; replacement_build.csv) |
| eta bound tightens with N, window-geometry reading | pre-push directive §5 (14:5x) concurrent with computed bounds | consistent at 2 points (0.557%→0.139%); labeled consistent-with |
| the BUNDLE (not the D=2 layer) is the likely recovery carrier | MVP patch §4 (15:2x) before direct solves | MISS so far — bundle structurally absorbed at all tested N |
| W_bundle(B_half) nonempty by N=14–20; W_bundle(B_*_edge) empty at all N | tier plan T2 (16:2x) before wbundle ran | MISS (B_half all-zero) / HIT (edges all-zero) |
| block dimension (not level count) drives realized IPM cost | C13 finding + T5 design (16:2x) before C4 row | UNTESTED at compile (C4@14 pending) |
| F0 decision rule (state-picture tower lane) | overnight autorun plan (archived) | UNTESTED — lane parked INCOMPLETE/non-gating at 0bf8663 |

## 5. DEAD BRANCHES

| item | status | reason (as recorded) | survived |
|---|---|---|---|
| state-picture F-line (F0) | parked INCOMPLETE, non-gating | arbiter parking at 0bf8663 | nothing gating; docs |
| ω-tower as an accuracy lane | retired to validated infrastructure | M2 verdict unresolved-positive; D4 arms exceed laptop (5e89867) | tower generator + oracle (reused by every later lane) |
| Route A (config forensics) | CLOSED | reach is the lever; fixed-r deficit = basis undercoverage (b112e2b) | closure language; reach rows; T1L lever condition |
| T1L conditional cell | never fired | trigger conditions not met (whitelist item 3) | — |
| N=200 old pair blind release | BLOCKED (02:30 mechanical law, 4b2a8d2); later released as non-gating (bef4dc6) | no blind release post-freeze | 23009660 still running (24h wall) |
| A200 adaptive deployment | CANCELLED pre-submission (override ~10:49) | arbiter override; R4c incomplete | R1-R4b gate records; manifest+runner code |
| fresh replacement-chassis selection | abandoned at wall | 30-min window mathematically insufficient (1 arm >6 min ×11) | pilot label {B_bond_edge,B_half}; attempt logs |
| R-night numerical arms | CANCELLED (documentation-only, ruling #4) | overnight risk laws | REPLACEMENT_PROTOTYPE.md contract (f27403e) |
| full-window lossless arm | REJECTED at directive review | tautological (R-night directive §3) | — |
| R4c exact-runner gate | killed mid-run | A200 cancellation | manifest schema + a200 runner mode (committed) |
| Clarabel/SCS solver spike | cut by FINAL CUT §1 | scope law | open question (C13 mechanism) — later addressed by C4 design |
| additive-tower N-extension audit ≥15 min | capped to 15-min read-only | FINAL CUT | containment PROVEN (3/3 words inside closure) |
| OOM'd/killed arms (frontier rows) | recorded, no retry | 18G law / walls | replacement_solve.csv D14/D20/E14/E20/C10@20; MASTER lad N=46; ladder N≥18 construction kills; probe64/probe128 TIMEOUTs |

## 6. WHAT EXISTS

| artifact | function | where |
|---|---|---|
| cg_hybrid/gsb_cg.jl | sha-pinned textual fork of QMBCertify GSB with one untyped seam hook | in PR |
| rg_selection/src/local_cone_adapter.jl | RGExt seam consumer (newwords/Γ₂/ycoef/zblocks) + bundle pool | in PR |
| rg_selection/src/{rg_builder,moment_bundles,functional_rg,vcheck,semhash}.jl | single builder; Γ₂ blocks; rg_spec; V1-V4 battery; semantic hashes | in PR |
| cg_hybrid/{tower_gen.jl,vumps_tensor.jl,vumps_A_D2.json,vumps_A_D4.json} | two-parity ω-tower generator + ED oracle; VUMPS maps w/ gates | in PR |
| rg_selection/{run_small.jl,selection/enum/g3 finalizer, release_gates.jl, run_n200.jl(+a200), replace_arm.jl, run_replacement.sh, finalize_replacement.jl} | gate drivers G0-G4b/R-gates; N=200 runners; four-hour lock harness | in PR |
| rg_selection/direct/{direct_mvp.jl,run_direct.sh,run_ext.sh,p0_audit.jl,THEORY_CONTRACT.md,PROVENANCE_MATCH.md} | direct replacement MVP: partition/registry/gates/arms/extension | MVP in PR (29e2205); N-extension stages local-only at compile |
| hpc/ (sbatch templates, refs, 2d/resort_patch.jl) | SCNet drivers; **upstream lattice="square" resort bug + monkey-patch** (QMBCertify basic_function.jl:316 UndefVarError) | in PR |
| bethe_ref.jl / hpc/refs/bethe_ref.json; dmrg_ref_j1j2.jl; table4_refs.json | high-precision Bethe refs (validated); DMRG upper bounds; Table-4 refs | in PR |
| overnight_harness.jl + make_results_md.py | cell runner w/ RSS/wall guards; tables from CSV | in PR |
| CSV families | results.csv/MASTER.csv (74 rows); training/gates/vcheck/g4_arms/holdout; a200_release_gates; replacement_{build,solve,summary}; direct {build_costs,solve_results,soundness_gates,wbundle}; fresh_selection logs | in PR except direct-extension rows (local) |
| audit/ package | gates.json, training/holdout CSVs, FROZEN_SELECTION.json, provenance.csv, claims_ledger.md (C1-C18), commit_list, diff_stat | in PR |
| ~/diag_extract.md, ~/campaign_inventory.md | arbiter diagnostic extract; this inventory | outside repo |

TRUNCATION NOTE: §2 compresses same-purpose commit clusters (queue v1-v4,
SCNet bundle fixes) into single lines; individual SCNet bootstrap failures
(22989159/22991017/22991021/22992924, exit codes 10005/10009) folded into
the 07-28 23:xx line — full list in HISTORY.md.
