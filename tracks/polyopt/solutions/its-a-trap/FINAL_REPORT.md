# its-a-trap — Final report: coarse-grained NPA for spin-1/2 ground states (challenge #49)

Team **its-a-trap** (Yan-Bai Zhang) · PR #193 · 2026-07-30 · report snapshot:
`freeze/MASTER.csv` (74 rows, sha256 in `audit/provenance.csv`), method
artifacts under `rg_selection/results/`. Every number below is generated
from those CSVs; nothing is hand-derived. Terminology per `LAW.md`:
SDP results are **numerical SDP lower bounds**, DMRG results are
**variational upper bounds**, Bethe values are **high-precision Bethe
references**; only the MG point (−0.375/site) and the 4×4 torus ED are
called exact.

## Scoreboard

| target | asked | delivered | status |
|---|---|---|---|
| T1 1D Heisenberg ≤ 200 spins @ 1e-5 | gap ≤ 1e-5 | **+9.931e-06 at N=100** (reach-extended); ladder N=50–140 at +1.6…2.5e-05; N=200 = measured resource frontier, no bound row | met at N=100; frontier documented to N=200 |
| T2 1D J1–J2 ≤ 100 spins @ 1e-3 | bracket ≤ 1e-3 | N=100 brackets ≤ 1e-3 for J2 ∈ {0.2,0.4,0.5,0.6}; MG point −4.3e-09; J2 ∈ {0.8,1.0} in the 1e-2 band | met for J2 ≤ 0.6 |
| T3 2D Heisenberg ≤ 16×16 @ 1e-3 | bound at 16×16 | conceded on measured scaling (basis rows 20854→30928 at L=6→8); valid L=4 probe vs exact torus ED | concession, measured |
| T4 2D J1–J2 10×10 @ 1e-2 | bound at 10×10 | J2=0.2: −0.6007562490 (bracket ≈ 3.3e-3); J2=0.5: −0.5116536004 (≈ 1.5e-2 band) | two 10×10 rows delivered |

## Target 1 — Heisenberg chain, signed per-site gap = E_Bethe − E_LB

| N | config | E_LB (numerical SDP lower bound) | gap | row |
|---|---|---|---|---|
| 50 | CONFIG A (r=5) | −0.4434935081 | +1.638e-05 | v50/scnet-20260729-001929 |
| 60 | CONFIG A (r=5) | −0.4433963315 | +2.011e-05 | v60/scnet-20260729-001929 |
| 80 | CONFIG A (r=5) | −0.4432993172 | +2.337e-05 | v80/scnet-20260729-001929 |
| 100 | CONFIG A (r=5) | −0.4432532120 | +2.364e-05 | v100/scnet-20260729-001929 |
| 120 | CONFIG A (r=5) | −0.4432291490 | +2.476e-05 | v120/scnet-20260729-001929 |
| 140 | CONFIG A (r=5) | −0.4432129679 | +2.377e-05 | v140/scnet-20260729-001929 |
| 100 | CONFIG A + extra=8 (r=9) | −0.4432395015 | **+9.931e-06** | v100e8/scnet-20260729-001929 |

The 1e-5 target is reached at N=100 by extending the two-site reach
(r = 9). Reach is the operative lever (Route A, closed): the results are
consistent with Table 3 of arXiv:2604.01555 using an N-dependent reach
r ≈ N/2; the fixed-r=5 large-N deficit is explained by basis
undercoverage. Fingerprint cells v14/v14fp match Table 3 to all seven
printed digits on the compute nodes.

**N=200 campaign (status, not results).** Three formulations were taken to
measured frontiers: CONFIG A construction alone exceeded 11.7 h wall with
no solve started; the V_{S*}(200) joint space on 64 cores hit the 6 h
build TIMEOUT at 182 GB; the 128-core construction probe (job 23009659)
likewise ended TIMEOUT at its 6 h template limit with MaxRSS 174 GB, still
inside model construction (revision datum, 11:42). One matched base/joint
pair (job 23009660, 24 h wall) was still RUNNING at revision time (base
arm in build/solve since 08:36). A replacement-chassis
adaptive deployment (rdm=false) passed its N=10 release gates
(R1/R2/R3/R4b, `rg_selection/results/a200_release_gates.csv`) and was then
cancelled by decision before any job was submitted; no N=200 adaptive
number exists and none is claimed. Any rows landing after this snapshot go
to a subsequent revision, never into these tables.

## Target 2 — J1–J2 chain N=100, bracket = E_DMRG_upper − E_LB

| J2 | E_LB | E_DMRG (variational upper bound) | bracket |
|---|---|---|---|
| 0.2 | −0.4086076123 | −0.4085729238 | +3.469e-05 |
| 0.4 | −0.3808885700 | −0.3803879204 | +5.006e-04 |
| 0.5 | −0.3749999957 | −0.375 (exact, MG) | −4.304e-09 |
| 0.6 | −0.3814148627 | −0.3806532275 | +7.616e-04 |
| 0.8 | −0.4249105577 | −0.4207006317 | +4.210e-03 |
| 1.0 | −0.4926313793 | −0.4860704208 | +6.561e-03 |

The 1e-3 target holds for J2 ≤ 0.6; the frustrated side (0.8, 1.0) lands
in the 1e-2 band. N=40 cross-validation: five J2 points agree with local
runs to ≤ 1e-10.

## Target 4 — 2D J1–J2 10×10 (lso=0, pso=0 per Remark 6.1)

| J2 | E_LB | note |
|---|---|---|
| 0.2 | −0.6007562490 | bracket vs published variational ≈ 3.3e-3 (inside 1e-2) |
| 0.5 | −0.5116536004 | ≈ 1.5e-2 band |

The J2=0.5 row sits at the boundary of the intermediate-phase window
discussed in arXiv:2602.21468v4; the lower bound is reported signed and
makes no phase claim.

## Target 3 — 2D Heisenberg (concession, measured)

2D probe chain: L=4 −0.7024963 (valid vs exact torus ED −0.7017802),
L=6 −0.6821741, L=8 −0.6789488. Basis rows grow 20854 → 30928 from L=6 to
L=8 with the wall/RSS frontier crossing our budget well before 16×16; the
target is conceded on these measurements.

## Method chapter — coarse-grained NPA layered on QMBCertify

Single implementation, gate-chain validated on tested small-N paths.
QMBCertify is pinned unmodified at be63c27; a textual fork (`cg_hybrid/
gsb_cg.jl`) adds one untyped seam hook, and every extension enters through
that seam (`rg_selection/src/local_cone_adapter.jl`).

- **Coarse-graining (RG) family**: a two-parity ω-tower built from a D=4
  parity-resolved VUMPS map (provenance-pinned JSON, hash in
  `audit/provenance.csv`); every link row is a Theorem-1 CP-map identity
  validated against an ED primal-row oracle to ≤ 1e-15
  (`cg_hybrid/tower_gen.jl`).
- **Moment-selection (Γ₂) family**: bundle rows anchored at canonical
  representatives (never ×N orbit materialization — gate G1c), real
  embedding of the Hermitian Γ₂ block, admitted at the seam only when a
  product class is genuinely outside the stock closure.
- **Gates** (all green; `audit/gates.json`): G1 builder identity/
  neutrality, G1c orbit scaling, G2 oracle + flow compatibility + sandwich,
  G3 exact subset enumeration (28/28 orderings, nesting monotone), G4
  holdout orderings + Γ-PSD at the ED state, G4b space equivalence.
- **Blind selection**: S* = {B_bond_edge, B_half} frozen before holdout
  (`audit/FROZEN_SELECTION.json`, tie-break rule (b), runner-up recorded).
- **Holdout verdict (preregistered)**: at N=14, joint − base = +5.5e-09
  against ε_cmp ≈ 1.5e-07 ⇒ **unresolved-null**; no improvement is claimed
  for the joint family at this size (`audit/holdout.csv`). This is the
  honest read of the constraint-family complementarity hypothesis at
  small N.
- **Verification battery** (`audit/gates.json` vcheck): V1 direct ED
  substitution per block (worst link residual 1.7e-15 over 768 rows), V2
  dual-solution reconstruction (all PSD blocks, 1174 equalities), V3
  newwords admission exercised at N=14 with a diagonal-negation mutation
  that goes red, V4 link-sign mutation red.
- **Replacement-chassis release gates** (2026-07-30): on the stripped
  chassis (rdm=false, pso=0, lso=false) at N=10 — R1 canary
  (E = −0.451549606105 ≤ E0/N, residuals ≤ 7.7e-09), R2 ED-feasibility,
  R3 mutation red, R4b diagnostic-pool vs auto space equivalence
  (bit-identical bounds, equal block hashes). The N=200 adaptive
  deployment built on these gates was cancelled before submission.

## Fine-variable elimination: operational replacement prototype (revision)

A four-hour pre-registered test of the Sec. III-D-2 replacement direction
(x_fine → x_retained ⊕ x_coarse), run on the deadline afternoon. Arms on
the stripped chassis (rdm=false, pso=0, lso=false): A = fine-rich reach
comparator (r=N/2); B = truncated core (r=r_of(N)); C6 = B + depth-6
ω-tower; D/E = C6 + moment bundles. All numbers from
`rg_selection/results/replacement_{build,solve,summary}.csv` (hashes in
`SHA256SUMS`); full narrative in `rg_selection/results/SUMMARY.md`.

| finding | numbers |
|---|---|
| structural-cost crossover (pre-registered) confirmed | PSD-scalar ratio C6/A: 1.447 (N=14) → 0.848 (N=20) → 0.610 (N=26) → 0.530 (N=30); nnz ratio 0.35 at N=30 |
| realized solver cost still favors A at tested sizes | wall ratio C6/A ≈ 10.7 / 9.0; RSS ratio 11.8 / 5.7 (N=14 / 20), both decreasing with N |
| reach gap resolves; depth-6 tower does not close it | d = L_A − L_B = +4.679e-05 (N=14), +1.566e-04 (N=20), both resolved-positive; eta_CG(6) = +0.0013 / +0.0003 (measured negative — no resolved recovery) |
| bundle marginals unmeasurable under the 18 GiB local law | D, E OOM at both sizes; C10@N=20 admission PASS (1792 link rows ≤ 1.7e-15) but solve OOM; frontier rows retained |
| validity | every accepted row ≤ E_Bethe + 5e-7; L_B ≤ L_A and L_B ≤ L_C6 within ε_cmp at both sizes |

The supported statement is deliberately narrow: the structural size of the
coarse representation crosses below the fine-rich reach basis between
N=14 and N=20 and keeps improving, but at depth 6 it carries essentially
no additional spectral information on this chassis, and its dual blocks
are expensive in realized solver terms at N ≤ 20. No cost-at-matched-
accuracy claim is made. This is an operational prototype, not a completed
coarse replacement.

## Reproducibility

`RESULTS.md` documents the paper-reproduction protocol (CONFIG A knob
vector, per-cell measurements, solver residuals — declared tolerance 1e-8,
so differences at or below ~1e-8 are not resolvable). The audit package is
under `audit/`: `gates.json`, `training.csv`, `holdout.csv`,
`FROZEN_SELECTION.json`, `provenance.csv` (sha256 per artifact),
`claims_ledger.md` (every claim → evidence row → classification),
`commit_list.txt` (46 commits), `diff_stat.txt`. HPC scripts and sbatch
templates are under `hpc/` and `rg_selection/`; environment quirks and
exact module paths are recorded in `A200_DEPLOYMENT_RECORD.md` and
`HISTORY.md`.
