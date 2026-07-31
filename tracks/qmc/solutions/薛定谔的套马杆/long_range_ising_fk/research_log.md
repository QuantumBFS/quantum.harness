# Research log

## 2026-07-27 source audit

- Read arXiv:2512.04805v2 PDF and TeX source.
- Confirmed square torus minimum-image distance and sum_j J_ij = 4.
- Corrected the brief's tentative polynomial: the paper defines
  Rp = <R2> - q<R0>; therefore Ising uses Rp = <R2> - 2<R0>.
- Existing Clock script is retained as a thermodynamic baseline only because it
  cannot produce FK winding observables.
- Selected a direct FK reference and an exactly equivalent Poisson-event
  Fukui-Todo production update.

## 2026-07-27 local validation

- Julia 1.11.4 deterministic tests: 20/20 passed.
- Requested smoke grid completed: sigma=1.875; L=8,16,32; beta=0.326985,
  0.336985,0.346985; two seeds; 1000 thermalization and 5000 measurements.
- All coupling sums equal 4.0; no NaN. Rp increases monotonically across the
  beta window and independent seeds agree at smoke precision.
- NN control at exact beta_c gave Qm=0.8584,0.8593,0.8574 for L=8,16,32,
  consistent with 0.856216. Rp was 0.0200,0.0272,0.0317 with block errors
  0.0146,0.0172,0.0140; this is close but the latter two are about two standard
  errors high and should be monitored with more seeds.
- Production outputs preserve per-cell summaries, raw block values, metadata,
  and scheduler logs in non-overlapping directories.

## 2026-07-27 SCNet production pilot

- Slurm job: `22957014_1`, partition `xhacnormalb`.
- Scheduler result: `COMPLETED`, exit code `0:0`, elapsed 13 s, peak RSS
  305484 KiB.
- Compute node `a01r04n07`, Julia 1.12.6.
- Cell: L=16, sigma=1.75, beta=0.326136, seed=11002, 10000 thermalization
  sweeps and 100000 measurement sweeps.
- Results: Qm=0.6457855520, chi=56.66194297, R0=0.51451, R2=0.22275,
  Rp=-0.80627, tau_int(m2)=3.169, sumJ=3.9999999999999987.
- stderr was empty. Summary, 20 raw blocks, metadata, and scheduler logs were
  fetched to local `results/production_20260727/`.

## 2026-07-27 Track A partial production validation

- Slurm array `22958313`: the complete L=64,128,256 subset (72 cells) was
  fetched while all 24 L=512 cells continued running.
- Partial escrow is complete: 72 summaries, 72 block files, 72 metadata files,
  and zero non-empty stderr logs.
- Maximum observed tau_int(m2) is 7.311 sweeps; maximum normalization error is
  2.22e-15.
- The sigma=2.5 central-beta control trends toward the published SR values:
  Rp = -0.03368, -0.00506, 0.00267 and Qm = 0.83641, 0.84443, 0.84716 for
  L=64,128,256. Rp is already consistent with convergence to zero; Qm remains
  below 0.857 at these finite sizes but moves monotonically toward it.
- All preregistered Rp and Qm crossings for 64/128 and 128/256 lie inside the
  sampled beta window. Final fits and conclusions remain blocked on L=512.

## 2026-07-28 Track A final result

- Slurm array `22958313` completed all 96 cells with exit code 0:0.
- Local escrow verified: 96 summaries, 96 raw block files, 96 metadata files,
  and zero non-empty stderr logs.
- At published beta_c, the L=512 values are:
  - sigma=1.75: Rp=-0.454225, Qm=0.741986.
  - sigma=1.875: Rp=-0.271760, Qm=0.785230.
  - sigma=2.0: Rp=-0.130795, Qm=0.815894.
  - sigma=2.5: Rp=0.009190, Qm=0.852077.
- Eta fits using L>=64 (L>=128) are 0.3834 (0.3729), 0.3290 (0.3204),
  0.2962 (0.2915), and 0.2541 (0.2546) for the four sigma values.
- The sigma=2.5 SR control approaches Rp=0, Qm=0.857, eta=0.25.
- At sigma=1.875 the finite-size data move toward the published Rp=-0.207(9),
  Qm=0.815(8), and eta=0.293(3), but have not converged by L=512.
- With four sizes, unrestricted three-parameter power/log correction fits have
  only one residual degree of freedom; after dropping L=64 they are
  underdetermined. AICc is undefined and model-dependent limits are unstable.
- Locked conclusion: finite-size reproduction successful; thermodynamic
  discrimination is inconclusive at school-scale L<=512.

## 2026-07-29 extension and Clock cross-check

- Locked a pure-Julia distinguishability analysis before inspecting the full
  large-size aggregate. It compares power and marginal corrections using
  AICc, BIC, leave-one-size-out prediction, size-window stability, 1000
  parametric bootstrap replicas, and a 3-sigma distinguishable-size forecast.
- Implemented an independent factorized-Metropolis Clock sampler. On a fixed
  L=4 configuration, 200,000 proposals gave acceptance 0.377645 versus
  0.377270 for explicit factorized Metropolis; the six-standard-error
  tolerance was 0.006504.
- Small-size Clock validation job 22990977 completed 4/4 cells with empty
  stderr. At sigma=1.875, Clock-minus-FK standardized differences were
  (Qm,chi)=(0.77,0.75) sigma at L=64 and (-0.67,-0.99) sigma at L=128.
  The preregistered 3-sigma gate passed.
- Submitted production Clock array 22991082: sigma=1.875,2.0; L=64,128,256,512;
  two seeds; 50k/100k/200k/300k thermalization sweeps by size and one million
  measurement sweeps per cell. It was initially pending on AssocGrpJobsLimit
  while the 16-slot FK large-size array continued running.

## 2026-07-29 interim extension analysis

- Analyzed 23/48 completed FK large-size cells and 12/16 completed Clock
  production cells using the pure-Julia scripts. All available summary,
  block, and metadata counts matched; stderr was empty.
- Sigma=1.75 and 1.875 had two-seed central-beta coverage through L=2048.
  At sigma=1.875, L=2048 gave Rp=-0.1885(103), Qm=0.80589(17), within 1.35
  and 1.11 combined standard errors of the published thermodynamic estimates.
- Power and marginal models remained indistinguishable at sigma=1.875:
  Delta AICc was 0.18 for Rp and 0.07 for Qm over L=64--2048. Window removal
  destabilized the inferred limits; the locked conclusion remained
  inconclusive.
- Some sigma=1.75 fits hit the minimum correction exponent and returned
  unphysical positive limits with poor absolute chi-square. These were marked
  as model misspecification, not interpreted as evidence.
- All six completed Clock points through L=256 passed the 3-sigma comparison
  gate. The largest standardized difference was 2.16 sigma for chi at
  sigma=2.0, L=64 and decreased at larger L.

## 2026-07-30 time-cutoff result

- Froze 36 successful large-size cells: 30 central-beta and 6 partial crossing
  cells. Central data reached L=2048 at every sigma; sigma=2.5 lacked one seed
  at L=1024 and L=2048. Partial crossing coverage was retained but not
  extrapolated.
- Reran the locked pure-Julia analysis with 1000 bootstrap replicas. At
  sigma=1.875 and 2.0, absolute power-versus-marginal AICc differences were
  <=0.18 for Rp and Qm. No registered distinguishable-size forecast reached
  3 sigma by L=65536.
- The sigma=2.5 Qm power extrapolation was 0.85623 with 16--84% bootstrap
  interval [0.85494,0.85851], containing the known short-range value near
  0.857. Rp fits at sigma=2.5 and multiple sigma=1.75 fits had poor absolute
  chi-square or boundary-hitting parameters and were not interpreted.
- Completed Clock production had 16/16 cells. Comparisons through L=256
  passed the 3-sigma gate, while L=512 Qm failed at -3.21 and -4.38 sigma.
  Tau_int was approximately 7,860--8,372 sweeps, identifying insufficient
  local-update mixing rather than a discrepancy in the FK result.
- Cutoff conclusion: finite-size reproduction successful; thermodynamic
  discrimination inconclusive at the completed accessible scales.

## 2026-07-31 nearest-neighbor completion

- Slurm array `23025326` finished the registered strict-NN numerical work for
  all 28 cells: four seeds at each of
  `L=64,128,256,512,1024,2048,4096`.
- Every cell produced non-empty `summary.csv`, `blocks.csv`, and
  `metadata.txt`. The array exit code was 1 because the Python 2.7 wrapper
  raised a text/byte `TypeError` while writing `manifest.json` after Julia had
  completed; this was classified as a packaging failure, not a simulation
  failure.
- `scripts/nn_repair_manifests.py` rebuilt all 28 manifests from the frozen
  run specification and saved numerical evidence without recomputation.
- Four-seed unweighted means at `L=2048` were `Qm=0.8558951` and
  `Rp=0.0345500`; at `L=4096` they were `Qm=0.8517651` and `Rp=0.0094000`.
  The `L=4096` seed scatter is larger under its registered 5,000-sweep
  measurement budget and is retained without selection.

## 2026-07-30 public escrow and repository migration

- Relocated the unchanged implementation into the registered team directory
  `tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/`.
- Recorded generation-code revision
  `26234d49bddd6005398d35361ff98b5efbba6b88`.
- Published four frozen datasets containing 787 files and 285,369 bytes:
  the 96-cell base production, the 36-cell large-size cutoff snapshot, the
  16-cell Clock production, and the cutoff analysis tables.
- Added `data_manifest.sha256` with a per-file SHA-256 checksum and
  `data_manifest.md` with dataset-level tree digests and explicit exclusions.
- Public packaging occurred after the local locked analysis. Original cell
  timestamps, scheduler identifiers, locked protocols, and the immutable
  generation revision were retained for chronology auditing.
