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

## Fine-variable elimination (consolidated findings; revisions 1–2)

> Eliminating fine variables reduced the tested SDP's structural size by
> 30.3% with no resolved wall-time or memory penalty, and the comparison
> with an additive tower of the same family localizes realized
> interior-point cost to PSD block dimension rather than model size.
> Accuracy recovery from the eliminated region remained unresolved in
> every configuration tested, and the correction channel intended to
> supply it has not yet been tested — once for resource reasons, and once
> because the declared bundle was structurally absorbed by the retained
> closure.

Two measurement campaigns on the deadline day probe one question — where
does the realized cost of coarse replacement come from, and what does it
buy: a pre-registered additive D=4 ω-tower comparison (arms A/B/C6/D/E at
N=14/20, builds to N=30; evidence table below, frozen CSVs under
`rg_selection/results/`, ledger C13–C15) and a gate-first direct
replacement MVP in which deleted fine variables are provably never
created (D=2, one level, N=10 primary; artifacts under
`rg_selection/direct/`, ledger C16–C18). Tables are bound to their frozen
CSVs and are reproduced unchanged; the narrative below is organized by
finding, not by experiment.

### 1. Structural size and realized solver cost separate [C13, C16]

Structural model size and realized interior-point cost are not
interchangeable, and PSD block dimension is the operative axis. Additive
D=4 depth-6 tower: structural ratio vs the fine-rich comparator
1.447 → 0.848 → 0.610 → 0.530 (N=14/20/26/30, crossover between 14 and
20) — but realized wall 10.7x/9.0x and RSS 11.8x/5.7x (N=14/20), largest
block 128. Direct D=2 one-level replacement at N=10: structural 0.697
(30.3% reduction, meeting the pre-declared 0.7 threshold) at realized
wall/RSS parity (19.1 s / 1.25 G vs 19.6 s / 1.21 G), largest block 66 —
BELOW the comparator's 84. Reading, with its confound in the same
sentence: PSD-scalar counts understate interior-point cost when scalars
concentrate in large blocks. The controlled check WAS subsequently run
(third revision): at the same N=14, same retained basis, same level count
and same link-family generator, swapping only the map package D=2 → D=4
(66-dim → 128-dim blocks) moved realized cost from wall 0.87x / RSS 0.90x
to wall 2.37x / RSS 6.80x of the comparator while the structural ratio
stayed below 1 (0.542 → 0.830) — the block-dimension package is isolated
as the realized-cost driver within that boundary (ledger C20).

### 2. The eliminated zone, and what reaches it [C14, C17]

Recovery of the truncated-reach information is unresolved in every
configuration measured, and the geometry explains why. The denominator is
resolved and grows with N: d = +4.679e-05 / +1.566e-04 (additive chassis,
N=14/20) and +4.97e-06 (direct chassis, N=10). The depth-6 D=4 tower
recovers < 0.557% / < 0.139% of d (N=14/20) — a one-sided bound that
TIGHTENS with N; the D=2 single level recovers < 0.53% (central value
−0.02%). Geometry: the eliminated separations extend to N/2 while the
tower's fine-side footprint is 3-site window moments (containment proven
by enumeration: every tower link word lies inside closure(G_retained)),
so the coarse layer can act on the eliminated zone only indirectly.
Window size / depth is the axis that would give a direct path — and the
depth attempt (C10 at N=20) PASSED its validity admission (1792 link
rows, residual ≤ 1.7e-15) with its interior-point solve crossing the
18 GiB local frontier. Third-revision extension: the direct D=2 curve
holds the same verdict at every solved size — recovery bounds < 0.525% /
< 0.072% / < 0.096% / < 0.219% of d at N=10/12/14/20 (central values
|·| ≤ 0.02%), beside cost ratios that IMPROVE with N (structural
0.697 → 0.383, wall 0.97 → 0.75, RSS 1.03 → 0.51); N=20 is the
campaign's first both-axes-cheaper configuration, still with unresolved
recovery (ledger C19).

### 3. The correction channel has not been tested [C15, C18]

There is no measurement of moment-bundle recovery, for two distinct
reasons. On the additive chassis the full-pool and transferred-pair arms
first PASSED ED admission (gate green, mutation red at E = +0.563) and
then hit the 18 GiB frontier — status: admitted, resource-limited. On the
direct chassis the declared bundle's product closure fell entirely inside
W_R (W_bundle = ∅, machine-asserted; D ≡ C to 1e-11) — structural
absorption, not an independent test. The resulting criterion: a
correction bundle can carry eliminated-zone content only if its product
closure intersects W_D; the 55 enumerated W_D classes at N=10
(`BASIS_PARTITION_N10.json`) give the anchoring set. This is also the
structural reading of the week's earlier bundle null (28 training scores
in the e-9 band; the measured pool adds 55 PSD scalars ≈ 0.08% of the
model): those pools were chosen by geometric distance, not W_D anchoring.
(Whether the pool operators lie inside the Gram basis itself — which
would make Γ_S a principal submatrix and its positivity logically implied
— was checked only at the tsupp/closure level, not at the Gram-row level,
so that stronger statement is not claimed.) Third-revision enumeration
closes the question at every tested size: W_bundle = 0 for all four pool
bundles at all N ∈ {10, 12, 14, 20} (`direct/wbundle_table.csv`) — the
pre-registered expectation that B_half becomes W_D-reaching by N=14–20 is
FALSIFIED; the translation-quotiented closure contains every plain
pair/bond product class at every tested N, so the correction channel
remains untested for the structural reason at all sizes (ledger C21).

### 4. Architecture and soundness [C16; release gates C10]

Deleted words are machine-provably never created: post-extension basis ≡
frozen hashed allowlist, seam admits nothing (seam_newwords = 0), no
deleted variable/row/block exists. Map certificate: per-parity isometry
5.1e-16, dual-parity flow identity 0.0. ED gates: link residual ≤ 1e-10
over all rows, coarse and retained-witness Gram PSD at the ED state;
targeted link-coefficient mutation goes red (E = +0.0999); the objective
class is carried exactly. N=8 serves as the finite-size
partition-collapse control (closure refill ⇒ W_D = ∅, A ≡ B; |C−B| =
2.1e-10 — the machinery produces no spurious tightening in the degenerate
case). Positioning: a direct/operational replacement prototype — not a
completed implementation of Sec. III-D-2.

### Evidence table — additive-tower campaign (frozen CSVs, reproduced unchanged)

| finding | numbers |
|---|---|
| structural crossover (pre-registered) confirmed | PSD-scalar ratio C6/A: 1.447 (N=14) → 0.848 (N=20) → 0.610 (N=26) → 0.530 (N=30); nnz ratio 0.35 at N=30 |
| realized solver cost still favors A at the solved sizes | wall ratio C6/A ≈ 10.7 / 9.0; RSS ratio 11.8 / 5.7 (N=14 / 20), both decreasing with N |
| reach gap resolved; tower recovery UNRESOLVED (one-sided bound, beside its cost ratios) | d = +4.679e-05 / +1.566e-04 (resolved-positive); eta_CG(6) < 0.557% / < 0.139% of d (central values +0.13% / +0.03%, inside ε_cmp), at wall/RSS ratios 10.7x/11.8x and 9.0x/5.7x; bound tightens with N, consistent with window geometry (eliminated zone grows to N/2; tower window stays ~6 sites) |
| PSD-scalar count is an unreliable cost proxy when block-dimension distributions differ | at N=20: structural ratio 0.85 vs wall ~9x and RSS ~5.7x — the tower concentrates scalars in dimension-128 blocks, for which the interior-point method pays super-linearly |
| bundle / deeper-tower contributions: resource-frontier, not numerical failure | D, E at the 18 GiB frontier at both sizes; C10@N=20 deeper-tower validity passed (1792 link rows, residual ≤ 1.7e-15) and its interior-point solve crossed the local 18 GiB frontier; frontier rows retained with status |
| validity | every accepted row ≤ E_Bethe + 5e-7; L_B ≤ L_A and L_B ≤ L_C6 within ε_cmp at both sizes |

### Evidence table — direct-replacement campaign (frozen CSVs under `rg_selection/direct/`)

| N | R_struct C/A | wall C/A | RSS C/A | d = L_A−L_B | recovery bound (central) |
|---|---|---|---|---|---|
| 10 | 0.697 | 0.97 | 1.03 | +4.972e-06 | < 0.525% (−0.016%) |
| 12 | 0.611 | 1.01 | 0.99 | +3.070e-05 | < 0.072% (+0.019%) |
| 14 | 0.542 | 0.87 | 0.90 | +4.679e-05 | < 0.096% (+0.010%) |
| 20 | 0.383 | 0.75 | 0.51 | +1.566e-04 | < 0.219% (+0.001%) |
| 26 | 0.345 | build-only | — | — | — |
| 30 | 0.336 | build-only | — | — | — |
| 14 (C4, D=4 package) | 0.830 | 2.37 | 6.80 | same d | < 0.630% (+0.002%) |

A/B comparators at N=14/20 are reused from the morning campaign under the
exact-match record `rg_selection/direct/PROVENANCE_MATCH.md`; D rows at
N=12/14/20 are STRUCTURALLY_ABSORBED (W_bundle = 0, `wbundle_table.csv`).

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
