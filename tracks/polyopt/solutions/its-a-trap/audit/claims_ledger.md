# CLAIMS LEDGER — every outward claim, its tier, and its evidence row
(terminology per LAW.md; ε_cmp classification throughout; signed gaps)

| # | claim (as worded in the report) | evidence | classification |
|---|---|---|---|
| C1 | Target 1 accuracy (1e-5) reached at N=100: numerical SDP lower bound −0.4432395015, signed gap vs high-precision Bethe reference +9.931e-06 | freeze/MASTER.csv row v100e8/scnet-20260729-001929 | resolved (gap > residual scale 1e-8) |
| C2 | Heisenberg-chain ladder N=50–140 at CONFIG A (r=5): signed gaps +1.638e-05 … +2.476e-05 | freeze/MASTER.csv rows v50–v140 | resolved |
| C3 | N=200: NO lower-bound row is claimed. Statements are resource-frontier measurements only: CONFIG A construction > 11.7 h wall (no solve); V_{S*}(200) 64-core build TIMEOUT at 6 h / 182 GB; 128-core probe TIMEOUT at 6 h / MaxRSS 174 GB still in construction (sacct 23009659, revision datum); matched base/joint pair (23009660, 24 h wall) RUNNING at revision time | n200 state files; sacct; A200_DEPLOYMENT_RECORD.md | status, not result |
| C4 | Target 2 (J1–J2 chain N=100): bracket = variational upper bound − numerical SDP lower bound ≤ 1e-3 for J2 ∈ {0.2, 0.4, 0.5, 0.6}; MG point J2=0.5 exact −0.375 bracketed at −4.3e-09; J2 ∈ {0.8, 1.0} land in the 1e-2 band (+4.2e-03, +6.6e-03) | freeze/MASTER.csv T2 rows; dmrg refs | resolved per row |
| C5 | Target 4 (2D J1–J2 10×10): numerical SDP lower bounds J2=0.2 −0.6007562490 (bracket ≈ 3.3e-3, inside 1e-2) and J2=0.5 −0.5116536004 (≈ 1.5e-2 band) | freeze/MASTER.csv T4 rows | resolved per row |
| C6 | Target 3 (2D 16×16): conceded on measured scaling (m: 20854→30928 at L=6→8; wall/RSS frontier); 2D probe chain L=4 lower bound valid vs exact torus ED | freeze/MASTER.csv 2D rows | concession, measured |
| C7 | Method: single implementation, gate-chain validated on tested small-N paths (G0–G4b all green; V1–V4 battery incl. newwords admission exercised at N=14 and mutation red-tests) | audit/gates.json (joint_gates, vcheck) | gate record |
| C8 | Blind selection: S* = {B_bond_edge, B_half} frozen before holdout, exact enumeration EXACT_ALL_SUBSETS_LE3 on N∈{10,12}, tie-break rule (b) fired | audit/FROZEN_SELECTION.json, audit/training.csv (28 rows) | gate record |
| C9 | N=14 holdout: joint − base = +5.5e-09 ≤ ε_cmp ≈ 1.5e-07 ⇒ UNRESOLVED-NULL (preregistered branch; no improvement claim is made for the joint family at N=14) | audit/holdout.csv | unresolved-null |
| C10 | Replacement-chassis (rdm=false, lso=false) release gates at N=10: R1 canary, R2 ED-feasibility (worst link residual 5.6e-16), R3 mutation red, R4b space-equivalence (auto = pool to 0.0, hashes equal) all PASS; the N=200 adaptive deployment itself was CANCELLED before submission and no N=200 adaptive number exists | rg_selection/results/a200_release_gates.csv; A200_DEPLOYMENT_RECORD.md | gate record + cancellation |
| C11 | Route A (closed, verbatim LAW language): consistent with Table 3 using an N-dependent reach r ≈ N/2; the fixed-r=5 large-N deficit is explained by basis undercoverage | ROUTE_A_ACTIVE.md (CLOSED) + reach rows in MASTER.csv | closed finding |
| C12 | No tier-1/2/3 claim-ladder sentence is claimed for the CG tower vs the rdm families; signed numbers are reported and nothing is claimed beyond them | LAW.md ladder; cg_hybrid m2 records | below-tier, by choice |

Banned-term compliance: "certified" nowhere in outward text; no "scalable",
no "first implementation", no "CONFIG-A-equivalent" for 2D cells; the tower
is described at most under the "constraint-family complementarity
hypothesis" phrase.

## Revision additions (replacement prototype, 2026-07-30 afternoon)

| # | claim | evidence | classification |
|---|---|---|---|
| C13 | Structural crossover of the coarse representation vs fine-rich reach: PSD-scalar ratio C6/A = 1.447/0.848/0.610/0.530 at N=14/20/26/30 (build-only, code-generated counts) | rg_selection/results/replacement_build.csv | resolved (counts exact) |
| C14 | Tower recovery of the truncated-reach gap is UNRESOLVED, stated as a one-sided bound: d(A−B) resolved-positive at both sizes (+4.679e-05, +1.566e-04); L_C6−L_B inside the comparison band, so eta_CG(6) < 0.557% (N=14) and < 0.139% (N=20) of d, at wall/RSS ratios 10.7x/11.8x and 9.0x/5.7x | rg_selection/results/replacement_solve.csv + replacement_summary.csv | unresolved (one-sided bound) |
| C15 | Bundle/deeper-tower contributions (D, E, C10) are resource-frontier at N=14/20 under the 18 GiB single-process law (never numerical failure): frontier rows retained with status; C10 deeper-tower validity PASSED (ED substitution, 1792 rows ≤ 1.7e-15) | replacement_solve.csv OOM rows; depth_admit_n10.txt; journalctl record in replacement_driver.log | status/frontier, not result |

## Second-revision additions (direct MVP, late afternoon)

| # | claim | evidence | classification |
|---|---|---|---|
| C16 | DirectCG at N=10 deletes 55 of 527 fine classes with machine-proven non-creation (post-extension basis ≡ frozen allowlist, seam_newwords=0) and structural cost 0.697 of FullFine at realized wall/RSS parity; all soundness gates green (map certificate, ED, mutation red, exact objective) | rg_selection/direct/{soundness_gates.csv,build_costs.csv,solve_results.csv} | gate record + resolved structural ratio |
| C17 | Recovery by the one-level D=2 coarse layer at N=10 is UNRESOLVED: one-sided bound eta < 0.525% (eta_total < 0.540%) of the resolved reach gap d=+4.9715e-06 | rg_selection/direct/solve_results.csv | unresolved (one-sided bound) |
| C18 | Boundary findings: N=8 partition degenerate (closure refill, W_D=∅, A≡B; control row); declared B_half correction bundle absorbed by the retained closure at N=10 (W_bundle=∅ exactly) — W_D-anchored corrections identified as the required next step, not run today | rg_selection/direct/{BASIS_PARTITION_N8.json,BASIS_PARTITION_N10.json,soundness_gates.csv G6bundle} | measured boundary/finding |

## Third-revision additions (DirectCG N-extension)

| # | claim | evidence | classification |
|---|---|---|---|
| C19 | DirectCG cost curve improves monotonically with N on all three axes — structural 0.697/0.611/0.542/0.383 (→0.345/0.336 build-only at 26/30), wall 0.97/1.01/0.87/0.75, RSS 1.03/0.99/0.90/0.51 at N=10/12/14/20 — with recovery still unresolved (one-sided bounds 0.525%/0.072%/0.096%/0.219% of resolved d); N=20 is the first both-axes-cheaper configuration | rg_selection/direct/{solve_results.csv,build_costs.csv,EXTENSION_SUMMARY.md}; comparators per PROVENANCE_MATCH.md | resolved (cost) + unresolved bounds (recovery) |
| C20 | Same-N/basis/level/link-family map-package swap D=2→D=4 at N=14 moves realized cost from 0.87x/0.90x to 2.37x/6.80x (wall/RSS) while structural stays < 1 (0.542→0.830) — the block-dimension package is isolated as the realized interior-point cost driver within the stated boundary | rg_selection/direct/solve_results.csv rows 14,C / 14,C4; soundness_gates.csv (C4 map cert + ED 1.7e-15/256 rows) | resolved (controlled isolation) |
| C21 | The declared correction bundles cannot reach the deleted zone on this chassis at any tested size: W_bundle = 0 for all 4 bundles × N ∈ {10,12,14,20}; pre-registered B_half expectation FALSIFIED; W_D anchoring identified as the necessary construction | rg_selection/direct/wbundle_table.csv; BASIS_PARTITION_N10.json | resolved (enumeration; falsified pre-registration) |
