# Potential Discoveries

Record unexpected results even when they arise from failed experiments.
An entry is not a discovery claim until independent checks are complete.

## Entry template

### YYYY-MM-DD — Short observation

- **Status:** artifact | unresolved anomaly | robust result | publication candidate
- **Observation:**
- **Experiment and commit:**
- **Parameters, sizes, and seeds:**
- **Reproduction evidence:**
- **Systematic checks:**
- **Independent validation:**
- **Possible explanations:**
- **Novelty/literature search:**
- **Cheapest decisive follow-up:**
- **Current conclusion:**

### 2026-07-27 — Static sign-free vertices can conceal a nonergodic field update

- **Status:** artifact
- **Observation:** The first custom abstract-loop SSE model passed static
  Hamiltonian, sign, and transition-table checks, and eight chains reported
  sign one with small autocorrelation estimates, yet all measured observables
  coincided with the `h=0` classical model rather than the requested nonzero
  transverse-field model.
- **Experiment and commit:** attempt-003,
  `fde14bb90bf0da93c6449c63424d617aafc304e1`, Slurm job `22962458`.
- **Parameters, sizes, and seeds:** `J=0.73`, `h=1.17`, `beta=0.85`;
  honeycomb L=2 and triangular L=3; seeds 41001–41004; 100000 measurement and
  20000 thermalization sweeps.
- **Reproduction evidence:** The wrong-ensemble behavior repeats across all
  four seeds and both lattice families; six ED comparison z scores range from
  96.5 to 835.
- **Systematic checks:** Every chain has sign exactly one and 18 rebinned
  samples. The final checkpoint inspected during diagnosis contains only
  diagonal vertices, despite the static vertex table containing nonzero
  off-diagonal field vertices.
- **Independent validation:** Independent Julia and Python dense ED
  implementations agree within `3.3e-15`. Separate classical enumeration
  matches the QMC central values closely.
- **Possible explanations:** The generic abstract-loop update is nonergodic
  for this decomposition, or the two-site distribution of one-site field
  operators is incompatible with the package's loop construction.
- **Novelty/literature search:** None; this is presently an implementation
  artifact, not a physics result. The standard TFIM SSE literature uses
  dedicated diagonal, off-diagonal, and cluster updates rather than this
  unvalidated decomposition.
- **Cheapest decisive follow-up:** Instrument nonzero-field operator occupancy
  and validate a dedicated TFIM SSE update against the same two ED clusters
  before measuring any crossing.
- **Current conclusion:** Rejected implementation. Static sign-free checks are
  insufficient; an interacting ED comparison is mandatory. Follow-up
  attempt-004 replaced the update with a dedicated TFIM quantum-cluster SSE
  and passed the same six ED gates (maximum `|z|=1.70`), confirming that the
  anomaly was an algorithmic artifact rather than physics.

### 2026-07-27 — Lattice-dependent finite-beta correction in Binder pilots

- **Status:** unresolved anomaly
- **Observation:** At the published approximate critical fields and L=4,6,
  the honeycomb Binder ratio changes by 4.27–5.98 sigma between beta=L and
  beta=2L, whereas the triangular change is only 0.13–1.29 sigma.
- **Experiment and commit:** attempt-005, `e62977c`, Slurm jobs `22963174` and
  `22963278`.
- **Parameters, sizes, and seeds:** J=1; honeycomb h=2.13250, triangular
  h=4.76811; L=4,6; beta/L=0.5,1,2; seeds 51001–51002.
- **Reproduction evidence:** The direction repeats at both honeycomb sizes;
  the triangular near-convergence also repeats at both sizes. Follow-up
  attempt-006 used fresh seeds, added L=8, and found beta=2L and beta=4L
  compatible at 0.89-1.04 sigma for all three honeycomb sizes.
- **Systematic checks:** All 24 cells have sign one, active field operators,
  string fill below 0.47, and at least 16 rebinned samples after continuation
  to 8000 sweeps. All 18 follow-up cells independently pass the same health
  class, with beta/L=2,3,4 and string fill 0.447-0.463.
- **Independent validation:** The underlying kernel passed interacting ED in
  attempt-004. No independent beta scan exists yet.
- **Possible explanations:** Larger nonuniversal imaginary-time correction on
  the honeycomb lattice, different effective velocity/aspect ratio, or the
  approximate honeycomb field being farther from its finite-size crossing.
- **Novelty/literature search:** Not yet performed; no novelty claim.
- **Cheapest decisive follow-up:** Completed at fixed field in attempt-006.
  Attempt-007 then found that multi-size Binder crossing locations from
  beta=2L and beta=4L agree within 0.31 and 0.67 sigma. The remaining
  decisive check is a larger-size baseline run at the published beta*h=L
  aspect ratio.
- **Current conclusion:** Do not use a common beta=L ground-state pilot rule.
  beta=2L is adequate for honeycomb crossing pilots under both frozen gates,
  but no production beta is frozen. The effect remains a systematic-method
  observation, not a discovery.

### 2026-07-28 — Strong adjacent-size drift in small honeycomb Binder crossings

- **Status:** unresolved anomaly
- **Observation:** The L=6/8 Binder crossing lies about 0.018 above the L=4/6
  crossing at both beta=2L and beta=4L.
- **Experiment and commit:** attempt-007, source commit
  `e5ce7e3fcdc975cfdfc0e3155382f27ae8231ddf`, Slurm job `22969892`.
- **Parameters, sizes, and seeds:** J=1; honeycomb L=4,6,8; beta/L=2,4;
  h=2.1025--2.1625 in 0.01 steps; seeds 53001 and 53002; 8000 measurement
  and 2000 thermalization sweeps.
- **Reproduction evidence:** The drift is 0.0187750 +/- 0.0031808
  (5.90 sigma) at beta=2L and 0.0183572 +/- 0.0029040 (6.32 sigma) at
  beta=4L. It therefore repeats across both beta routes and all seeds used in
  their pooled estimates.
- **Systematic checks:** All 84 cells passed chain health checks. Both beta
  routes bracketed the crossings, passed chi2/dof<=3, and had at most 0.34%
  failed bootstrap resamples. The beta shift of either same-size-pair
  crossing is below 0.7 sigma, so incomplete beta convergence does not explain
  the adjacent-size drift.
- **Independent validation:** The QMC kernel passed interacting dense-ED
  checks in attempt-004, but the crossing drift has not been reproduced by an
  independent QMC implementation or a second dimensionless observable.
- **Possible explanations:** Ordinary corrections to 3D-Ising scaling,
  dominance of the very small L=4 system, the chosen torus geometry, or
  lattice-specific aspect-ratio corrections.
- **Novelty/literature search:** The Blöte-Deng baseline reports honeycomb
  final-fit cutoffs \(L_{\min}=10,L_{\max}=20\), so strong drift at L=4--8
  is compatible with known finite-size methodology. The paper does not give
  the complete size roster. No dedicated novelty search has been performed
  and no novelty claim is made.
- **Cheapest decisive follow-up:** Run a low-statistics literal beta*h=L
  baseline pilot including L=10,12 and larger, then compare fits with and
  without L=4,6.
- **Current conclusion:** Methodologically robust warning, not a physics
  discovery. Small-size crossings must not be promoted to a critical-field
  estimate.

### 2026-07-28 — Equal-time Binder is not the literal 2002 baseline observable

- **Status:** artifact
- **Observation:** Attempts 006/007 measured propagated equal-time moments,
  whereas the Blöte–Deng baseline forms its Binder ratio from the
  magnetization density of the full space--continuous-direction classical
  system, corresponding to a space--imaginary-time averaged worldline
  magnetization.
- **Experiment and commit:** Source audit preceding attempt-008; attempts
  006/007 remain valid equal-time pilots and are not relabelled.
- **Parameters, sizes, and seeds:** The distinction is estimator-semantic and
  applies to every size, field, beta, and seed in those attempts.
- **Reproduction evidence:** The paper's Eq. (21) definition and continuous
  geometry were checked against the implementation of
  `propagated_moments`; they average different nonlinear quantities.
- **Systematic checks:** Analytic Dirichlet integration gives a separately
  named spacetime estimator without modifying the equal-time estimator.
- **Independent validation:** Attempt 009 passed the longitudinal-source
  ED/QMC comparison on both lattices and both general/literal beta cases:
  119/119 numerical checks, 16/16 chain checks, and 28/28 observable
  comparisons. Attempt 008 stopped before science at an old-Git provenance
  compatibility gate.
- **Possible explanations:** This is a reproduction-pipeline labeling error,
  not unexpected physics. Both observables should share the thermodynamic
  critical point but can have different fixed-point values and finite-size
  corrections.
- **Novelty/literature search:** The distinction is standard in worldline
  formulations; no novelty claim is made. The value is a reusable validation
  warning for precision reproductions.
- **Cheapest decisive follow-up:** Run the frozen low-statistics explicit
  \(L=10,12,14,16,18,20\) literal beta*h=L baseline grid and test
  fit-window/correction stability without using sqrt(5).
- **Current conclusion:** The old equal-time labeling is a confirmed pipeline
  artifact, not new physics. The separately named spacetime estimator is
  validated for baseline reproduction; existing equal-time pilot data remain
  useful diagnostics.

### 2026-07-28 — Historical correction term dominates low-stat baseline uncertainty

- **Status:** unresolved methodological observation
- **Observation:** In attempt-010 the frozen \(a_1,a_2,a_3,b_1\) historical
  fit gives \(\sigma_{h_c}=0.00263\), while the preregistered no-\(b_1\)
  sensitivity fit gives 0.000586. Both fits have acceptable \(p\)-values and
  conditioning, so the loss is driven by weak low-statistics identification
  of the finite-size correction rather than numerical failure.
- **Where/repetition:** The primary, all leave-one-size-out fits, the
  \(L_{\min}\)/\(L_{\max}\) variants, and the outer-window fit all completed
  with 4998--5000 shared bootstrap successes; every required paired shift
  remained below 1.58 sigma.
- **Possible explanations:** Only six sizes up to \(L=20\) and two seeds per
  point leave \(Q^\star\), \(h_c\), and \(b_1\) strongly correlated.
- **Novelty search:** No novelty search; this is standard finite-size-fit
  identifiability and no discovery claim is made.
- **Cheapest decisive follow-up:** One high-statistics campaign that both
  increases independent seeds and adds larger sizes, while retaining the
  exact \(L=10\ldots20\) historical reproduction as a separate frozen fit.
- **Current conclusion:** Use larger sizes plus high statistics in
  attempt-011; do not obtain apparent precision by silently dropping \(b_1\).

### 2026-07-28 — Per-chain rebin gate exposes size-dependent sampling margin

- **Status:** artifact
- **Observation:** Attempt-011 completed all 4032 chains, but 891 chains fail
  only the preregistered minimum of 16 rebinned samples. Failures are absent
  at L=10--14 and rise to 158, 345 and 388 chains at L=16,18,20.
- **Where/repetition:** The effect appears at every field for L=18 and L=20
  and most fields for L=16, across many independent seeds. Across all four
  monitored moments, rebin counts range from 13 to 19.
- **Possible explanations:** The fixed 300,000-sweep chain length leaves
  insufficient margin for the package's automatic rebin-length selection as
  lattice size grows. The reported autocorrelation times remain finite and
  short; there is no evidence here for a pathological Markov chain.
- **Novelty search:** None. This is a campaign-design artifact, not a physics
  discovery.
- **Cheapest decisive follow-up:** Keep every physics and analysis setting
  fixed and double each chain to 600,000 measurement sweeps. The observed
  worst count of 13 should then rise to roughly 26.
- **Current conclusion:** Attempt-012 falsified that proposed explanation:
  increasing the target to 600,000 did not increase the fixed 18-minute
  invocation. The issue was not an intrinsic size-dependent autocorrelation
  margin but incomplete target execution. Do not relax the health gate or fit
  incomplete pooled rows; use direct checkpoint progress as a mandatory gate.

### 2026-07-28 — Requested Carlo sweeps can differ sharply from realized checkpoint progress

- **Status:** artifact
- **Observation:** Every attempt-012 result record reported the requested
  `sweeps=600000`, yet none of the 4032 HDF5 checkpoints had accumulated
  600,000 post-thermalization sweeps. Actual progress ranged from 14,309 to
  577,809 with median 118,690, and the median fell monotonically from 488,041
  at L=10 to 33,240 at L=20. The frozen minimum-rebin gate rejected 986 cells
  and prevented a finite-size fit from opening.
- **Experiment and commit:** attempt-012, frozen source
  `8bbf07b73374f8725b7f1058bdf3ccf1d6ffa6b5`; XH array job `22977642`,
  frozen analysis `22979338`, independent checkpoint audit on WZ job
  `41439155`.
- **Parameters, sizes, and seeds:** honeycomb PBC, J=1, beta*h=L,
  L=10,12,14,16,18,20, seven fields 2.1025--2.1625, seeds 61001--61096,
  target 600,000 measurement and 20,000 thermalization sweeps per cell.
- **Reproduction evidence:** The checkpoint audit read every
  `run0001.dump.h5` directly. All 672 cells at each of six sizes were below
  target. The array used 1276.13 core-hours and every 32-cell pack stopped
  after 18:45--19:21, nearly the same runtime as the earlier nominal-300k
  attempt, despite the doubled target.
- **Systematic checks:** The frozen analyzer found exactly 4032 manifests and
  scheduler records. The only 986 health failures were the minimum-rebin
  check; finite values, sign, active field updates, string fill, parameter
  identity and nonnegative autocorrelation checks passed. The direct progress
  table and aggregate summary are checksum-pinned in the attempt result
  index.
- **Independent validation:** Carlo 0.3.4 source inspection shows that
  `JobInfo(run_time="18:00")` stops a run at wall time and that `status`, not
  the requested parameter echoed into results, determines target completion.
  HDF5 checkpoint counters independently agree with rebin-length/count
  magnitudes. This validates the diagnosis, not the physics result.
- **Possible explanations:** The packed wrapper called `run` once, then
  unconditionally called `merge` and generated a manifest. It never checked
  `Carlo ... status`. Larger systems therefore accumulated fewer sweeps in the
  same 18-minute invocation.
- **Novelty/literature search:** No novelty search. This is a workflow and
  provenance artifact, not a physics discovery. It may be a reusable warning
  for Carlo-based precision campaigns.
- **Cheapest decisive follow-up:** Resume every retained checkpoint and RNG
  state using the remaining Slurm wall time; require checkpoint progress
  `>=600000` before merge and manifest generation. Rerun the unchanged frozen
  analysis only after all 4032 completion checks pass.
- **Current conclusion:** Confirmed campaign-control artifact. Target
  parameters are not completion evidence. Attempt-013 must fix only the
  control flow, preserve every scientific setting and gate, and reuse all
  valid accumulated samples.

### 2026-07-28 — Carlo Slurm remaining-time helper is timezone-sensitive

- **Status:** artifact
- **Observation:** Carlo 0.3.4 `run_time_from_slurm` reports less than five
  minutes remaining inside a fresh 15-minute Slurm allocation on the Wuzhen
  cluster, even when supplied a synthetic end epoch one hour in the future.
- **Experiment and commit:** attempt-013 preflight source `a3c137f`, Wuzhen
  job `41440502`; the strict continuation-control test failed before any QMC
  continuation began.
- **Parameters, sizes, and seeds:** This is scheduler-control behavior
  independent of lattice, field, size and seed. The reproducer uses
  `SLURM_JOB_END_TIME = round(Int,time()) + 3600` and grace factor 0.95.
- **Reproduction evidence:** The failure repeats for the real Slurm end epoch
  and the synthetic one-hour epoch on a CST compute node. Source inspection
  shows `unix2datetime(end_epoch) - now()`: the former is a naive UTC
  `DateTime`, while the latter follows local system time.
- **Systematic checks:** The existing scheduler, cell-contract and dedicated
  SSE suites passed 103 tests in the same job. Unix epoch subtraction
  `end_epoch - time()` is timezone independent and gives the expected
  approximately 3,420 seconds for the synthetic case. The first full-node
  array then established that Wuzhen does not export `SLURM_JOB_END_TIME` at
  all; one `scontrol show job` call per pack is therefore required to obtain
  its authoritative `EndTime` before workers launch.
- **Independent validation:** The source-level unit mismatch and the
  scheduled synthetic reproducer are independent routes to the same cause.
  A second Carlo implementation or upstream maintainer review has not yet
  been obtained.
- **Possible explanations:** Carlo assumes a UTC host timezone when
  subtracting naive `DateTime` values. On UTC+8 hosts this introduces an
  eight-hour negative offset.
- **Novelty/literature search:** No literature or upstream-issue search yet;
  this is a software portability artifact, not a physics discovery.
- **Cheapest decisive follow-up:** Run the fixed epoch-arithmetic unit test
  and the real incomplete-checkpoint negative control under Slurm, then
  consider filing a minimal upstream Carlo issue with the reproducer.
- **Current conclusion:** Use Unix epoch arithmetic for attempt-013. Do not
  use Carlo 0.3.4 `run_time_from_slurm` on non-UTC clusters without an
  explicit timezone check, and do not assume that Slurm exports an end-time
  epoch. Resolve and validate the allocation end once in the batch wrapper.

### 2026-07-28 — ALPS/looper's default Binder observable is equal-time, not spacetime

- **Status:** unresolved anomaly
- **Observation:** In pinned ALPS/looper commit
  `048b4ef6468a36be46de1ba8fdaa41f048bd57b0`, the normal estimator's
  built-in `Binder Ratio of Magnetization` uses the \(\tau=0\) accumulator
  `umag`, while the continuous-imaginary-time accumulator `umag_a` enters
  susceptibility but has no second/fourth-moment or Binder output. Thus
  running the path-integral algorithm does not by itself make the reported
  Binder ratio a space--imaginary-time Binder ratio.
- **Where/repetition:** The distinction is explicit in
  `looper/susceptibility.h` for every lattice handled by the normal
  estimator. It is not inferred from either triangular or honeycomb result
  values. Attempt-015 adds only named spacetime-density moments derived from
  `2*umag_a/volume` and their ratio; the original equal-time observable
  remains unchanged.
- **Possible explanations:** Equal-time magnetization is the conventional
  static Binder observable in many QMC workflows, whereas the 2002
  Blöte--Deng reproduction uses the magnetization of the full
  space--imaginary-time classical system. The two estimators are both valid
  but answer different finite-size questions.
- **Novelty/literature search:** The ALPS/looper manual lists the default
  magnetization moments and susceptibility but does not document a
  spacetime Binder estimator. The source audit is definitive for the pinned
  version; no broader novelty claim or upstream-version survey has yet been
  completed.
- **Cheapest decisive follow-up:** Build the pinned executable with the
  minimal named-observable patch, verify its \(J_z=-4J,\Gamma=2h\) Pauli
  mapping, and require both equal-time and spacetime moments to agree with
  independent ED at the frozen 70-comparison B0 gate.
- **Current conclusion:** Treat this as a reusable estimator-semantics
  warning, not a discovery. It becomes a robust methodological result only
  if the patched continuous-time route passes ED across both lattices and an
  independent source review confirms the normalization.

### 2026-07-28 — ALPS bond-type and geometric-volume defaults can silently change a lattice model

- **Status:** artifact
- **Observation:** Attempt-018 failed 61 of 70 blinded QMC/ED comparisons.
  Source and runtime logs show that ALPS' honeycomb unit cell has bond types
  0, 1 and 2, but the generic `Jz` parameter coupled only type 0; eight of 12
  L=2 honeycomb bonds therefore had zero Ising coupling. Separately, ALPS
  reports densities per geometric `Volume`, not per physical spin.
- **Experiment and commit:** attempt-018, source `6788434`, QMC array
  `22986369`, failed gate `22986370`; correction isolated in attempt-020.
- **Parameters, sizes, and seeds:** The frozen B0 campaign has 10 honeycomb
  and triangular ED points, 64 seeds per point, one million measurements and
  100,000 thermalization sweeps per seed.
- **Reproduction evidence:** The L=2 honeycomb runtime model lists 12 bonds:
  four with `Jz=-2.92` and eight with `Jz=0`. The L=3 triangular runtime model
  couples all 27 bonds. Triangular scale-invariant equal-time and spacetime
  Binder ratios agree with ED while every honeycomb Binder ratio fails.
- **Systematic checks:** Output XML gives geometric `Volume=3.4641016` for
  honeycomb L=2 and `7.7942286` for triangular L=3. Dividing ALPS total
  triangular energy by nine spins recovers the ED energy, and converting
  moments by the recorded geometric-volume/spin-count factors recovers the ED
  normalization. These checks do not use a critical field or the ratio.
- **Independent validation:** The graph structure is checked against the
  independently maintained ED fixtures. Full corrected QMC/ED validation is
  the frozen attempt-020 follow-up and remains pending.
- **Possible explanations:** ALPS uses type-specific model parameters when a
  lattice edge declares a type, and its `Volume` is the determinant-derived
  spatial volume. Both are legitimate framework conventions that were
  incorrectly assumed to mean a uniform bond and site count.
- **Novelty/literature search:** None. This is a reproducibility trap and
  implementation artifact, not a physics discovery.
- **Cheapest decisive follow-up:** On a compute node, require all 12 L=2
  honeycomb runtime bonds to print the same nonzero `Jz`, then rerun the exact
  640-chain B0 roster and require all 70 Holm-corrected QMC/ED comparisons to
  pass.
- **Current conclusion:** Attempt-018 is rejected. Attempt-019 production
  remains blocked until attempt-020 independently closes both defects.

### 2026-07-29 — Precision can invalidate a previously adequate crossing window

- **Status:** artifact
- **Observation:** The complete 600,000-sweep honeycomb campaign passed all
  4,032 technical and chain-health checks, yet every frozen seven-field
  straight-line crossing fit failed with
  \(\chi^2/\mathrm{dof}=468\)--2251. The primary five-field historical FSS
  truncation also failed with \(\chi^2/\mathrm{dof}=180\).
- **Where/repetition:** Attempt-013, all five adjacent size pairs
  \(10/12,\ldots,18/20\), 96 seeds at every \((L,h)\), and every one of the
  14 frozen primary/systematic FSS fits.
- **Possible explanations:** The low-statistics pilot could not resolve
  curvature across the broad \(2.1025\)--\(2.1625\) scan. At roughly
  \(10^{-4}\) pooled Binder errors, a straight crossing line over that whole
  interval and a cubic scaling-field expansion over the inner
  \(2.1125\)--\(2.1525\) interval are no longer adequate. This is analysis
  truncation, not evidence that the QMC critical point moved.
- **Repetition and systematic checks:** All crossings remain bracketed and
  have the expected slope. A diagnostic local interpolation of the two points
  nearest the literature center gives \(h_c=2.1325252\), compatible with
  \(2.13250(4)\), while the frozen broad-window estimator gives visibly biased
  crossings near 2.135--2.136. A degree-six per-size interpolation used only
  as pilot design evidence predicts that a symmetric five-field
  \(2.1275\)--\(2.1375\) scan restores the historical-model fit quality.
- **Independent validation:** Not yet. These are post-opening diagnostics of
  one SSE data set and cannot validate a replacement analysis.
- **Novelty/literature search:** No novelty search. The need to shrink a
  scaling window as statistical resolution improves is standard FSS practice;
  no discovery claim is made.
- **Cheapest decisive follow-up:** Freeze the symmetric, literature-centered
  narrow window and all fit/coverage gates, then generate wholly new seeds at
  those fields. Accept only a held-out fit that reproduces the 2002 value and
  passes the unchanged \(p\)-value, covariance, crossing, seed and health
  gates.
- **Current conclusion:** Treat attempt-013 as a successful high-statistics
  pilot but a rejected baseline. Do not weaken the goodness-of-fit gate or
  select the one-sided diagnostic after seeing the data.

### 2026-07-30 — Slurm array parent IDs can make a valid wall-time parser read many records

- **Status:** artifact
- **Observation:** Triangular source pack 25 exited in zero seconds with
  code `2:0`, while the other 24 packs started normally. Its stderr contains
  `could not parse Slurm EndTime` followed by many different timestamps.
- **Where/repetition:** Attempt-040 array `23009489`, task 25 on Xiongheng.
  `scontrol show job -o 23009489_25` reports that this task used the array
  parent ID `SLURM_JOB_ID=23009489`; querying that bare ID returns multiple
  array records. This has been observed once in production and has not yet
  been reproduced by a synthetic regression.
- **Possible explanation:** `resolve-slurm-end-time.sh` queries the bare
  `SLURM_JOB_ID`. For the array placeholder, that identifier is also the
  array parent. The greedy `sed` extraction therefore receives multiple
  `EndTime` fields and passes a newline-separated timestamp list to `date`.
  Ordinary array elements have distinct child job IDs and avoid the defect.
- **Systematic checks:** The failed task allocated a full node but ended at
  its start time, before a QMC worker or observable was produced. Its stderr
  records the parser error; the other 24 pack logs resolve one timestamp and
  proceed. No scientific value was inspected.
- **Novelty/literature search:** None. This is an HPC continuation-control
  artifact and reusable testing lesson, not a physics discovery.
- **Cheapest decisive follow-up:** Resolve array elements with the explicit
  identifier `${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}` when both
  variables are present, add synthetic single-record and multi-record
  regressions, run a scheduled test-only/preflight, and point the continuation
  controller at the immutable fixed snapshot.
- **Current conclusion:** Operational cause reproduced and fixed in
  attempt-050. Six local and six remote regressions passed, stage job
  `23015299` and fixed controller `23015301` were accepted, and the old
  controller was cancelled. Keep the status as an artifact until the
  explicit array-placeholder element resumes successfully in the live
  continuation.

### 2026-07-30 — Independent-route precision exposes lattice-dependent scaling mismatch

- **Status:** unresolved anomaly
- **Observation:** The completed 2,016-cell ALPS/looper route passes all
  source, scheduler, manifest-hash, checkpoint-resume, runtime, count, finite
  error and autocorrelation gates, but every one of 12 predeclared FSS
  variants fails the \(p\ge0.01\) goodness-of-fit gate on both lattices.
  The primary reduced chi-square is about 2,582 for honeycomb and 151 for
  triangular; even the most favorable predeclared `lmax20` variants remain at
  about 42 and 4.22, respectively.
- **Where/repetition:** Attempt-054 diagnostic job `89164`, immutable source
  `358444239098ee4a86204a8fd0784dc0376b1111`, 63 scheduler packs and all
  2,016 checksum-pinned cell manifests. The rejection repeats across minimum
  and maximum size changes, field-window changes, no/cubic/mixed correction
  terms, and two fixed irrelevant exponents.
- **Possible explanations:** The frozen scaling truncations may be inadequate
  at the achieved precision; pooled errors may omit a correlated or
  estimator-specific contribution; beta/aspect-ratio corrections may remain;
  or the patched spacetime estimator may have unusually large
  lattice-dependent correction amplitudes despite passing small-system ED.
  The larger honeycomb mismatch is qualitatively consistent with stronger
  corrections, but no cause is yet established.
- **Systematic checks:** Only 18 of 2,016 primary records and 11 diagnostic
  records report non-converged internal errors, so a few explicit convergence
  flags do not explain the global failure. Covariance condition numbers are
  modest (about 34 for both primary fits), excluding obvious numerical
  singularity. Attempt-055 reconstructs every chi-square from checksum-pinned
  point residuals. The primary residual RMS is 47.0 (honeycomb) and 11.4
  (triangular), dominated by L=32 RMS values of 79.7 and 20.1. The
  predeclared L<=20 variant reduces those RMS values to 6.00 and 1.90, while
  field-edge residuals remain larger than the scan center. Median
  between/within-seed error ratios are 0.93 and 0.98, so the pooled errors do
  include comparable contributions from both sources. No accepted variant,
  bootstrap export, cross-lattice ratio, or verdict was produced.
- **Independent validation:** The same data route passed independent ED and
  source-review gates before this campaign. The present anomaly has not yet
  been reproduced with an independent QMC implementation or fresh held-out
  seeds and therefore is not a discovery.
- **Novelty/literature search:** No new novelty search has been performed.
  High-precision FSS exposing inadequate truncations is standard; only a
  reproducible estimator- or lattice-specific correction pattern could become
  a methodological result.
- **Cheapest decisive follow-up:** Export a ratio-blind residual table by
  lattice, size and field, compare standardized residual structure with
  within/between-seed errors and beta, and freeze one physically motivated
  held-out test using fresh seeds: a central narrow field window, explicit
  L=32 sensitivity, and a larger-beta subset. Do not reuse these data to
  accept a post-hoc model or rescale errors merely to force \(p\)-value
  acceptance.
- **Current conclusion:** Robust rejected-fit anomaly, not a critical-field
  estimate. Preserve the failure diagnostics and investigate the residual
  structure before spending on independent-route bootstrap or production.

### 2026-07-30 — Every accepted baseline central-variant ratio lies below square root five

- **Status:** unresolved anomaly
- **Observation:** The complete Cartesian product of the 22 accepted
  triangular and 17 accepted honeycomb baseline fit variants contains 374
  central ratios. All are below \(\sqrt5\), spanning
  `2.2358221939440344` to `2.236037352791315`; the closest displacement is
  `-3.062470847492449e-05`.
- **Where/repetition:** Attempt-075 combines the attempt-071 exact-RNG
  triangular 100,000-resample inventory, attempt-056 honeycomb
  100,000-resample inventory, and the predeclared Cartesian-product
  systematic rule. The primary ratio is `2.235979504194356`, with
  `R-sqrt(5)=-8.84733054338227e-05`.
- **Possible explanations:** The same-sign central shifts may be a real
  indication that the ratio is slightly below \(\sqrt5\), a common
  finite-size correction shared across accepted variants, or simply the
  consequence of many strongly correlated variants of the same two baseline
  data sets. Counting the 374 combinations as independent evidence would be
  invalid.
- **Systematic checks:** Both single-lattice primary fits pass their
  goodness-of-fit gates and the independent ALPS central ratio has the same
  sign of displacement. However, the frozen Cartesian systematic uncertainty
  is `1.5731025032161838e-04`, the total uncertainty is
  `1.611065056356336e-04`, and the primary displacement is only
  `0.5491603525553356` total standard deviations. The triangular crossing and
  production gates remain false.
- **Independent validation:** The ALPS route gives
  `R=2.2360196442165567`, also below \(\sqrt5\), but it is a pilot with a
  much larger total uncertainty and cannot promote this sign pattern to a
  result.
- **Novelty/literature search:** The literature and convention audit in
  `research/CATALOG.md` found no post-2002 exact relation. A targeted check of
  the classical star-triangle transformation and 2+1-dimensional Ising/gauge
  duality found no closed mapping between the two nearest-neighbor quantum
  TFIM Hamiltonians. This is summarized in the publish-candidate analytic
  note; no novelty claim is made.
- **Cheapest decisive follow-up:** Freeze a wider triangular crossing window
  before generating fresh seeds, require the crossing gate to pass, then run
  a separately preregistered high-statistics extension and the independent
  route without inspecting the ratio. Test whether every accepted joint
  production variant retains the same sign with the target total precision.
- **Current conclusion:** Directionally repeated but statistically
  inconclusive baseline pattern. It neither disproves exact equality nor
  proves a below-\(\sqrt5\) ratio.
