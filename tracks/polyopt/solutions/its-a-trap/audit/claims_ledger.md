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
