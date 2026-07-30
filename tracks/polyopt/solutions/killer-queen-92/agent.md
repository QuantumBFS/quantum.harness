# Agent handoff and decision log — issue #92

Last updated: **2026-07-30 16:55 CST**
Active workflow: [`status.md`](status.md) — **Gate 3 nested lattice levels**,
with `W0.5` blocked on a Mosek license
Issue: [certified bulk spectral-gap bounds for truncated Bose--Hubbard models
on hyperbolic lattices](https://github.com/QuantumBFS/quantum.harness/issues/92)

## 1. Purpose of this file

This is the compact handoff record for future agents. It keeps only:

- the issue's scientific finish line;
- the current handoff state;
- non-negotiable claim rules;
- durable implementation decisions and corrections;
- a short chronological record.

The authoritative task checklist, model grid, coverage counts, gate
dependencies, and acceptance tests live in [`status.md`](status.md). Update
that file after ordinary implementation work. Update this file only when a
decision, correction, blocker, or handoff instruction changes.

Other references:

- [`submission/report.html`](submission/report.html): self-contained professor-facing
  challenge report with curated accepted/certified tables and a source manifest;
- [`results/deadline_analysis/CURRENT_HPC_REPORT.html`](results/deadline_analysis/CURRENT_HPC_REPORT.html):
  accepted and floating SCNet calculation snapshot;
- [`PHYSICS_TALK.html`](PHYSICS_TALK.html): audience-level physical explanation;
- [`ALGORITHM.md`](ALGORITHM.md): mathematical derivation;
- [`SURVEY.md`](SURVEY.md): software assessment;
- [`REPORT.md`](REPORT.md): stage-I numerical report;
- [`README.md`](README.md): reproduction commands and artifact index.

## 2. Issue finish line

The challenge is complete only when the code implements paper-defined,
explicitly labeled state-polynomial relaxation levels `(L,d)` for the
occupation-truncated Bose--Hubbard model and uses several nested levels to
produce the requested thermodynamic results.

Minimum scientific deliverables per completed level:

| deliverable | mandatory `nmax=1,2` | optional/feasible `nmax=3` |
|---|---:|---:|
| gap upper endpoints `Gamma_(L,d)` | 30 | +15 |
| observable min/max objectives | 540 | +270 |

Every result must identify graph, `(t,U,mu)`, cutoff, symmetry class, `L`, `d`,
basis/buffer convention, matrix sizes, solver/status, runtime, residuals, and
the gap or observable bound. The final discussion must compare `t`, `mu`, the
three geometries, cutoff, and movement with `(L,d)`.

Current completion against that finish line:

- proper paper-defined hierarchy implementation: **complete in code**;
- complete observable result cells in the current deadline snapshot: **24**;
- proper requested-width `Gamma_(L,d)` endpoints: **3**;
- certified complete-level upper statements: **9**;
- nested-level comparisons: **0**;
- verified non-atomic fixed-`gamma` exclusion records: **48**.

## 3. Current handoff

| item | state |
|---|---|
| active gate | Gate 3 — nested, geometry-sensitive lattice levels |
| active work item | monitor optimized cutoff-two TS2 `(1,3)` dry job `41542822` followed by serial `(2,2)` guard `41544379`; geometry tasks 1/2 completed, tasks 3--6 run, and task 7 waits; task 0 failed with node-level `SIGBUS` and dependency-safe recovery `41546113` is queued after the full array; synchronize every durable checkpoint and freeze the report before 20:00 CST |
| carried blocker | `W0.5` — SCNet is configured, but the pinned upstream Ising solve still lacks a Mosek license |
| central implementation | `julia/src/` plus Python graph/campaign bridge |
| work that must wait | required-width endpoint and full-grid claims until unresolved scans and mandatory cells finish; nested comparisons until memory is redesigned |

Next action: preserve and analyze each completed MKL checkpoint, let the
geometry refinements continue without stepping over `UNKNOWN` trials, preserve
the TS2 dry resource gate (including task 28's low-RSS `SIGBUS` as a runtime
`UNKNOWN`, not an OOM), and
keep the current report synchronized through the 20:00 deadline.  Afterward, reduce
optimizer/workspace memory for `(1,3)` and `(2,2)` before another nested solve.
The pinned Ising reproduction still requires a Mosek license.

## 4. Non-negotiable scientific rules

### R1 — Use the paper's terminology accurately

`src/issue92/rooted_sdp.py` is a custom **root-local thermodynamic outer test**.
“Rooted SDP” was our historical label. The model is not a paper-defined
`(L,d)` level and must never be reported as one.

### R2 — Preserve the certificate direction

- `INFEASIBLE` at an exact level excludes the assumed `gamma` and gives a gap
  **upper** bound.
- `FEASIBLE` means only “not excluded at this level.”
- Feasibility is not a gap lower bound and does not prove a gapped state exists.

### R3 — Keep thermodynamic and finite-volume evidence separate

The paper's window is a local consistency/commutator window for an infinite
state, not an open finite Hamiltonian. ED spectra are exact only for the stated
4- or 5-site open cluster and carry no thermodynamic bound.

### R4 — Label symmetry scope

All current thermodynamic prototypes impose `U(1)` invariance. Their implication
concerns `U(1)`-invariant KMS ground states only. Never describe such a result
as unrestricted.

### R5 — Treat numerical uncertainty honestly

- `solver_error` is `UNKNOWN`;
- `optimal_inaccurate` with a material PSD violation is unresolved;
- `infeasible_inaccurate` is not a clean exclusion;
- a floating `infeasible` status is a candidate until a dual ray is preserved
  and independently checked.

### R6 — Use the exact cutoff algebra

At cutoff `nmax`, one site is `M_(nmax+1)(C)` and

`[b,bdag] = I - (nmax+1) |nmax><nmax|`.

Do not use an infinite CCR simplifier plus nilpotency; it is a different
algebra.

### R7 — Require geometry-sensitive levels

The root-local test sees only coordination, so `{12,4}` and `L({8,3})` are
identical. A completed hierarchy must include multi-site support sufficient to
see their different loop structures.

### R8 — Do not substitute scan volume for algorithm completion

The 135 pilot feasibility rows cover the parameter loops but not the requested
`Gamma_(L,d)` hierarchy. More runs of the same custom test do not advance the
central deliverable.

## 5. Reusable work

| artifact | reusable contribution | boundary |
|---|---|---|
| `src/issue92/local_algebra.py` | exact matrix-unit cutoff algebra | retain and test in hierarchy engine |
| `src/issue92/graphs.py` | `{8,3}`, `{12,4}`, and line-graph rooted windows | interior/buffer semantics still need Gate 0 specification |
| `src/issue92/atomic_sdp.py` | exact atomic validation and three-way bisection | special benchmark, not a general `(L,d)` level |
| `src/issue92/rooted_sdp.py` | root-local moment, stationarity, covariance, and gap prototype | not a complete level; preserve as regression test |
| `src/issue92/ed.py` | independent sign/cutoff/observable validation | diagnostic only |
| result CSV schema | solver, size, status, and PSD diagnostics | must add `L`, `d`, basis, buffer, bracket, and certificate fields |
| 21 Python tests and 575 Julia assertions | algebra, graph stability, exact ladder filtration, hierarchy bases/localizers, TS2, incremental/reference chordal-closure equivalence, campaign/resource counts, classification/report/submission-tier separation, floating-progress reporting, dry-level report ingestion, unresolved-span reporting, Slurm allocation parsing, resume, primal/dual checks, interval/exact-negative-witness/pivoted-exact-Schur PSD verification, exact exclusion and observable-bound projection, atomic and root-local validation | nested numerical directions and the full production grid remain unrun |

Software conclusion: no inspected package supplies issue #92 end to end.
`SpectralGap.jl` is the reference implementation for the authors' hierarchy,
but its published reference calculation has not yet been reproduced here.

## 6. Current evidence snapshot

- Atomic benchmark: analytical `Delta=0.5`, numerically bracketed by
  `[0.5, 0.5000009537)` for `nmax=1,2,3`.
- Root-local fixed-gap pilot: 135 rows; 57 `optimal`, 54
  `optimal_inaccurate`, and 24 `solver_error`; no usable infeasibility at
  `gamma=0,0.05,0.10`.
- Root-local observables: 36 pilot objectives at
  `(t,mu,gamma)=(0.06,0.5,0.1)` for `nmax=1,2`, versus 540 mandatory objectives
  required at each proper level.
- Requested-width `Gamma_(L,d)` endpoints: three, the `{8,3}` P1, P4, and P5
  hard-core complete `(1,2)` results at `0.505U`, `0.165U`, and `0.755U`.
  The same campaign gives additional certified P2 and P3 statements
  `Gamma/U<=0.511` and `<=0.518`, restricted to the stated
  `U(1)`-invariant hierarchy; their unresolved interior samples remain visible.
- `{12,4}` P2 is now certified `Gamma/U<=0.520` above checked FEASIBLE `0.510`.
  The line graph is checked FEASIBLE at `0.510` and exact-certified
  `Gamma/U<=0.530`; no true-gap ordering is inferred.
- The current complete-level observable subset contains 26 independently
  checked one-sided objectives and 100 floating endpoints.  P5 at
  `gamma/U=0.050` supplies the first two accepted intervals, for `rho0` and
  the exactly related hard-core `F0`; no `K0` interval is accepted.
- Both `{8,3}` nested solve attempts are `UNKNOWN` after Julia
  `OutOfMemoryError` under 192-GiB requests.
- Cutoff-two TS2 dry task `(1,3)` produced no level record after a low-RSS
  `SIGBUS`; `(2,2)` remains active and a different-node `(1,3)` retry is queued.
- Refinement P2 `0.500` and `0.505` are checked FEASIBLE; the transition
  micro-scan exactly excludes `0.511` and independently checks `0.509` as
  FEASIBLE, while `0.510` remains `UNKNOWN`.  The current search span is `0.002U`.
  P4 is complete at requested
  spacing with checked FEASIBLE `0.160` and exact EXCLUDED `0.165`.
- P3 micro-refinement checks `0.514` as FEASIBLE and exactly excludes `0.518`;
  `0.515` and `0.516` remain `UNKNOWN`, so its `0.004U` distance is also a
  search span rather than a clean bracket.
- Test suite: 21/21 Python tests and 575/575 Julia assertions passing at the last
  full validation.

Detailed tables belong in `status.md` and `REPORT.md`, not here.

## 7. Durable decisions and corrections

| ID | decision/correction | reason |
|---|---|---|
| `D1` | build on the paper's state-polynomial hierarchy, replacing its Pauli backend with exact finite matrix algebra | closest correct route to the issue target |
| `D2` | reserve `(L,d)` labels for complete, explicitly specified levels | prevents the custom prototype from inheriting an unproved convergence claim |
| `D3` | preserve the root-local test and atomic SDP as regression models | they validate locality, lifting, and the atomic threshold |
| `D4` | impose covariance PSD independently of the gap block | the initial root-local model omitted it; a consistency audit caught and corrected this |
| `D5` | use an independent basis or eliminate matrix-unit dependencies before larger levels | redundant PSD faces caused poor `nmax=3` conditioning |
| `D6` | assemble explicit `U(1)` charge blocks | implicit zeros waste canonicalization and obscure numerical conditioning |
| `D7` | parameterize `t`, `mu`, and `gamma` in a cached template | current wall time is dominated by rebuilding CVXPY expressions |
| `D8` | reproduce one `SpectralGap.jl` Ising result before hierarchy implementation | establishes a term-by-term reference for the new assembler |
| `D9` | make `status.md` the workflow and this file the handoff log | prevents duplicated milestones from drifting apart |
| `D10` | proceed with the user-directed Julia implementation while keeping W0.5 explicitly blocked | a missing local Mosek license is external; it blocks numerical acceptance, not implementation or exact structural tests |
| `D11` | treat the matrix encoding as complete and the current ladder matrix-unit grading as partial until a filtration-adapted combination basis is added | exact row reduction shows low-degree ladder combinations such as `b` need not be individual matrix units |
| `D12` | retain one live JuMP constraint graph but reset the attached optimizer after parameter coefficient changes | an independent dual residual test found that Clarabel could otherwise retain stale internal PSD-cone data after `MultirowChange` |
| `D13` | use SCNet partition `wzacnormal03` with its per-CPU memory policy; the accepted node maximum tested here is 128 CPUs/237 GiB, under the separate 450-GiB issue cap | literal 249/256-GiB requests are rejected and the old 225-GiB assumption was too conservative |
| `D14` | use exact charge-adapted ladder-word combinations as filtered coordinates and rebase raw physical operators into them | a degree assigned independently to raw matrix units omits low-degree directions such as `b`; graded row reduction preserves the complete filtration |
| `D15` | stage the pinned Julia depot and run SCNet compute nodes in package-offline mode | compute nodes have no public DNS; package downloads belong neither in jobs nor on the login node |
| `D16` | unload SCNet's default devtoolset and load `compiler/gcc/12.2.0` for Mosek jobs | Mosek 11.2's bundled TBB requires newer `GLIBCXX`/`CXXABI` symbols than the base OS provides |
| `D17` | promote complete hard-core `(2,2)` and `(1,3)` production cells to 192 GB/104 CPUs and enforce the 450-GB concurrency cap globally across arrays | completed tighter assemblies use up to 25.3 GiB, while `{12,4}` `(2,2)` had already reached 51.6 GiB before its unsafe 64-GB trial was cancelled; solver workspace still needs headroom |
| `D18` | derive hard-core `F0` bounds from the opposite `rho0` bound using `F0=1-rho0` | this is an exact cutoff identity and removes two redundant conic solves while preserving the source primal/dual evidence |
| `D19` | use independent fixed-`gamma` trials for the 18-hour deadline rather than allowing one `UNKNOWN` to terminate bisection | partial scans remain informative without weakening three-way classification or certificate rules |
| `D20` | record the first `{12,4}` `(2,2)` workspace attempt as `ERROR` and retry on a different node | it ended in `SIGBUS` at 141.3 GiB, below the 192-GB allocation, so neither success nor ordinary OOM may be inferred |
| `D21` | present failed-residual optima as a separate `FLOATING` evidence tier while retaining their scientific classification `UNKNOWN` | calculations in progress are informative for a talk, but must not be confused with independently checked bounds or exclusions |
| `D22` | accept an exact-projected complete-lattice fixed-`gamma` exclusion as a certified coarse thermodynamic upper statement, while reserving “completed endpoint” for the requested-width search | the `{8,3}` P2/P4 rays pass exact coefficient projection, Arb signs, PSD LDL, and positive Farkas-margin checks, but their refinement grids remain incomplete |
| `D23` | call the distance between a checked FEASIBLE sample and a verified EXCLUDED sample a search span whenever any interior trial is `UNKNOWN` or unfinished | unknown outcomes never move a bisection endpoint and must not be hidden by bracket terminology |
| `D24` | when deriving hard-core `F0=1-rho0` from an exact observable certificate, transform the conservative certified endpoint rather than the floating optimum | affine derivation preserves rigor only if the reported number inherits the source certificate's conservative backoff |

## 8. Known blockers and risks

| blocker/risk | consequence | workflow response |
|---|---|---|
| pinned reference cannot run without Mosek license | assembler conventions lack the requested endpoint cross-check | MosekTools runtime is prepared; install a license or set `MOSEKLM_LICENSE_FILE`, then run `W0.5` on SCNet |
| SCNet compute nodes have no public DNS | unstaged Julia dependencies cannot be downloaded in jobs | stage pinned package sources/artifacts from the laptop and run offline |
| redundant basis and dense implicit charge sectors | solver instability at `nmax=3` | Gate 1 basis/charge work |
| complete cutoff-two baseline reaches the partition memory ceiling | the 192-GiB solve was cgroup-killed; 237-GiB MKL jobs `41540049`/`41540879` and QDLDL `41541639` all caught Julia `OutOfMemoryError` | complete `(1,2)` needs KKT/workspace redesign or Mosek; continue the formally labeled TS2 resource gate without substituting it for the complete result |
| root-only support | two degree-four geometries remain identical | Gate 3 nested multi-site levels |
| Clarabel refinement can fail near the transition with a zero pivot | required-width endpoint remains unresolved even though coarse exclusions are exact-projected | retain each failure as `UNKNOWN`, continue independent fixed-`gamma` trials, and never step over it |
| no public copy of the 28 July talk slides | possible missed practical strengthening choices | compare if slides become available; paper remains authoritative |

## 9. Condensed work log

### 2026-07-28 — Theory, software, and foundations

- Read issue #92 and the bulk-gap paper; established the upper-bound
  certificate direction and thermodynamic local-window interpretation.
- Surveyed `SpectralGap.jl`, NCTSSOS/NCTSSoS, general NC optimization tools,
  graph packages, and solvers; found mature components but no end-to-end
  truncated-boson implementation.
- Implemented and tested the exact cutoff algebra and three graph constructors.
- Implemented the atomic state-polynomial benchmark and finite-cluster ED
  diagnostics.

### 2026-07-28 — Root-local prototype and pilot data

- Implemented the `U(1)` root-local thermodynamic outer test with local
  positivity, root stationarity, lifted state products, covariance, gap block,
  and observable objectives.
- Detected the missing standalone covariance PSD constraint, corrected it,
  regenerated the root-local results, and reran the tests.
- Ran the 135-row fixed-gap parameter pilot, coarse hard-core probes, and 36
  observable pilot objectives.

### 2026-07-28/29 — Reporting and scientific-status correction

- Wrote the algorithm, survey, technical report, HTML audit report, and
  professor-style physics talk.
- Clarified the exact finite clusters diagonalized by ED and their lack of
  thermodynamic implication.
- Reclassified “rooted SDP” as the custom root-local outer test.
- Audited Target 2 and recorded that no paper-defined `Gamma_(L,d)` has yet
  been computed.
- Created `status.md`, then converted it into the gated operational workflow.
- Compacted this file from a duplicate research ledger into a decision and
  handoff record.

### 2026-07-29 — Specification and Julia hierarchy implementation

- Froze the complete matrix-family level/index convention and third-party
  pins; generated exact rooted graph JSON through radius three.
- Implemented the Julia hierarchy core, solver interfaces, `TS2`, result
  schema, and conservative independent certificate checker.
- Generated the 90-gap/1,620-observable primary campaign manifest and SCNet
  resumable array driver; did not launch production locally.
- Passed 546 Julia assertions and all 17 Python tests; added exact
  ladder-adapted filtered coordinates, full-data resumable checkpoints, and
  independent min/max dual validation and exact conservative bound projection.
- Configured SCNet SSH and its live CPU/memory profile; staged an offline Julia
  depot and passed all 520 assertions on compute node `b10r4n13`.
- Passed the complete-hierarchy atomic Gate-2 check: `gamma=0.49` feasible,
  `gamma=0.51` exactly excluded with zero affine residual and normalized
  Farkas margin one, and primal/dual-checked `rho0` extrema equal to one within
  `2.8e-8`.  Raw evidence is
  `results/atomic/julia-hierarchy-certificate.json`.
- Added disjoint certificate kinds for exclusions, lower bounds, and upper
  bounds.  The exact-projected atomic `rho0` interval is
  `[986498/986499, 5806375/5806374]`; exact-bound failure cannot promote an
  observable result or reinterpret feasibility as exclusion.
- The then-current 544-assertion suite passed on SCNet in job `41500730` (after the
  543-assertion run in `41499485`); job `41499566` regenerated the atomic
  evidence with all three exact certificate kinds.
- Preserved W0.5 as a hard numerical-acceptance blocker because this host has
  no Mosek license; stopped an exact local dual-projection probe after it
  exceeded the intended laptop budget and recorded no exclusion from it.

### 2026-07-30 — Deadline SCNet results

- Activated Clarabel's MKL/Pardiso path and ran the complete hard-core `(1,2)`
  deadline subset under a checked 450-GiB aggregate request cap.
- Preserved 11 accepted one-sided observable objectives and 45 explicitly
  floating optima in a refreshable HTML/CSV report; nested `(1,3)` and `(2,2)`
  attempts remain explicit `UNKNOWN` after 192-GiB Julia out-of-memory errors.
- Verified exact-projected `{8,3}` exclusions beginning at P2
  `gamma/U=0.515` and P4 `0.165`.  P4 is the first requested-width endpoint;
  P2 retains `0.510` as `UNKNOWN` and therefore has a `0.010U` search span.
- Changed report terminology from bracket width to search span whenever an
  unresolved trial lies inside, and passed all 19 Python tests.
- Used the extension to 20:00 CST for an independent P2 transition micro-scan
  (`41534382`) and dependency-safe `{12,4}`/line-graph endpoint refinements
  (`41534386`, `41534390`), retaining the 448-GiB aggregate request ceiling.
- The micro-scan exactly verified P2 `gamma/U=0.511`, strengthening the
  certified complete-level upper statement to `Gamma/U<=0.511`; no conclusion
  was inferred for the still-unresolved `0.510` trial.  Its checked `0.509`
  sample narrows the search span to `0.002U` but is not a physical lower bound.
- Added the certified `{8,3}` P1 statement `Gamma/U<=0.600`, began P3/P5 scans
  in serial array `41534717`, and queued nine remaining-point observable cells,
  exact P4 observable projection, and one cutoff-two representative under the
  checked 448-GiB dependency schedule.
- Fixed exact hard-core `F0` derivation to use the source certificate's backed-off
  rational endpoint; reran all 547 Julia assertions and 19 Python tests.
- Required the auxiliary strictly-interior observable-certificate SDP to use
  the configured Clarabel backend and thread profile.  The replacement P4
  exact-bound job therefore uses MKL/Pardiso instead of silently reverting to
  single-threaded QDLDL; all 547 Julia assertions still pass after this change.
- Added the first certified P3 hard-core statement and then tightened it to
  `Gamma/U<=0.600` when the `ALMOST_INFEASIBLE` trial passed exact projection,
  256-bit Arb signs, PSD LDL, and the positive-margin check.  The `{12,4}` and
  line-graph P2 coarse scans independently passed the same exact check at
  `gamma/U=0.600`; no geometry difference is inferred before refinement.
- Preserved the alternate-QDLDL P2 `0.510` outcome as
  `UNKNOWN/NUMERICAL_ERROR` after 6,298 seconds, then canceled only its
  redundant `0.515` continuation because an exact MKL exclusion already
  exists.  Reassigned the released 64-GiB lane by raising Target-2 refinement
  array `41538360` from throttle one to two; after validating a 256-bit Arb
  interval-LDL fast path with exact-field fallback, replaced its three-minute
  tasks by resumable array `41539201`.  The dependency schedule still peaks
  at 448 GiB.
- Tightened the P3 hard-core complete-level statement to `Gamma/U<=0.518`:
  `0.514` is checked FEASIBLE and `0.518` has exact projection, zero affine
  residual, rigorous 256-bit PSD verification, and Farkas margin one.
  Interior `0.515`/`0.516` remain `UNKNOWN`, so the report calls `0.004U` a
  search span rather than a clean bracket.
- Recorded the cutoff-two resource gate without inventing a result.  Job
  `41535172` assembled in 158.5 seconds and then OOMed at a 192-GiB request;
  the accepted maximum-size retry `41540049` rebuilt in 162.1 seconds at
  128 CPUs/237 GiB, reached 237,910,752 KiB RSS, and safely checkpointed all
  four probes as `UNKNOWN/OutOfMemoryError`.
- Eight-thread MKL retry `41540879` reduced Slurm MaxRSS only to 233,357,596
  KiB and again checkpointed four `UNKNOWN/OutOfMemoryError` probes.  One-thread
  QDLDL job `41541639` lowered MaxRSS to 214,327,588 KiB but likewise OOMed on
  all probes, establishing a KKT-structure rather than thread/backend gate.
- Added an exact negative-quadratic witness before the slow exact PSD fallback.
  Numerical eigenvectors only choose integer candidates; exact field arithmetic
  decides negativity, so the path can only reject and cannot falsely certify.
  Singular/inconclusive matrices use symmetrically pivoted exact Schur
  complements; 575 Julia assertions pass, and a rank-deficient `100x100`
  integer Gram benchmark certifies in 4.7 seconds.
- The original `{12,4}` `0.520` certificate passed after 1,943 seconds of exact
  PSD fallback, tightening the certified statement to `Gamma/U<=0.520` with
  zero affine residual and Farkas margin one.  Its duplicate continuation was
  stopped after sync because independent `0.510`/`0.540` job `41541949` was
  already ahead.  TS2 dry array `41541783` was safely released after QDLDL
  failed, keeping the active request at 384 GiB.
- Replayed the stored `{12,4}` `0.520` Gram matrices with the optimized checker:
  all eight blocks (largest `222x222`) pass rigorous interval LDL in 3.125
  seconds versus the legacy job's 1,943-second exact fallback, without changing
  the exact affine or margin evidence.
- Submitted `{12,4}` `0.515` and line-graph `0.530` as midpoint array
  `41542751`; combined active requests are exactly 448 GiB.  These are
  independent probes and remain `UNKNOWN` until the standard checker passes.
- TS2 dry task `41541783_28` died with `SIGBUS` after 648 seconds at only
  1,878,056 KiB MaxRSS, so it is recorded as a node/runtime `UNKNOWN` rather
  than an OOM.  Task `41541783_31` remains active; different-node retry
  `41542822` is dependency-queued behind it and preserves the 450-GiB cap.
- Independent `{12,4}` recovery `41541949` checks `gamma/U=0.510` as FEASIBLE;
  the certified `0.520` exclusion therefore gives a `0.010U` search span while
  midpoint `0.515` remains unresolved.
- Submitted extended geometry-grid job `41543225`: eight complete hard-core
  `(1,2)` cells for `{12,4}`/`L({8,3})` at P1/P3/P4/P5, with one coarse
  exclusion candidate and a `gamma/U=0` anchor each.  It is dependency-held
  behind the active 64-GiB refinements, throttled to four, and all tasks exclude
  the four failed/suspect nodes, preserving the 448-GiB maximum request.
- Replaced TS2 chordal completion's repeated cubic active-degree scan by
  incrementally maintained degrees with identical deterministic tie-breaking.
  Nineteen direct comparisons reproduce the old clique sequence, all 575 Julia
  assertions pass, and a 220-vertex microbenchmark is 20.6x faster.  The tested
  source is staged for retry `41542822`; running task 31 is unaffected.
- Parallelized the read-only TS2 support-pair scan and retained a serial
  lexicographic merge, so 104-thread dry retries preserve deterministic output.
  The `(1,3)`/`(2,2)` moment bases contain 10,921/5,421 monomials and
  11.60/3.11 million charge-compatible pairs per closure pass.  All 575 Julia
  assertions pass with four threads; phase progress is enabled for dry jobs.
- Line refinement `41534390_1` exact-certified `gamma/U=0.540` after its
  pre-optimization 1,950-second PSD fallback.  The proof was synchronized,
  then only the redundant `0.560` continuation was canceled.  The certified
  line-graph statement is now `Gamma/U<=0.540` above FEASIBLE `0.510`.
- Released only extended-grid task `41543225_0` into the freed 64-GiB lane;
  tasks 1-7 remain dependency-held, so active requests stay at 448 GiB.
- Recovery `41541949` exact-certified its redundant `{12,4}` `0.540` probe
  with the optimized eight-block PSD check taking 0.87 seconds.  Its released
  lane now runs grid task 1; tasks 2-7 remain held and the cap is unchanged.
- Queued resumable optimized `(2,2)` TS2 guard `41544379` after optimized
  `(1,3)` retry `41542822`.  The 192-GiB jobs cannot overlap; a pre-existing
  complete task-31 record makes the guard skip safely.
- Line midpoint `41542751_1` exact-certified `gamma/U=0.530`; its eight-block
  rigorous PSD pass took 0.67 seconds.  Because `0.520` remains UNKNOWN, the
  `0.510`--`0.530` interval is a search span, not a bracket.  Grid task 2 now
  occupies the released 64-GiB lane.
- `{12,4}` midpoint `41542751_0` is explicit `UNKNOWN/ERROR` after 2,495 s;
  it does not alter the `0.510`--`0.520` search span.  Its completion released
  all grid dependencies: tasks 0-3 run and tasks 4-7 wait only on throttle 4.
- Canceled old serial TS2 task `41541783_31` after 50 minutes and no checkpoint;
  optimized different-node `(1,3)` retry `41542822` now runs on `b11r2n01`,
  followed serially by resumable optimized `(2,2)` guard `41544379`.  This
  changes no classification and preserves the 448-GiB active request.
- Formalized the PR/presentation boundary in generated `submission/`: accepted
  and exact-certified rows are curated separately from floating calculations,
  raw data remain ignored, and source hashes map every table back to the live
  aggregate.  A new fail-closed test proves that a solver-only exclusion cannot
  become a report endpoint or a decisive interior sample; 21 Python tests and
  575 Julia assertions pass.
- Extended-grid `{12,4}` P4 `gamma/U=0.300` and P5 `1.000` are exact-verified
  coarse upper statements.  P1 task 0 died with `SIGBUS` on `b10r4n25` during
  exact projection and remains `UNKNOWN`; dependency-safe recovery `41546113`
  runs only after array `41543225` and excludes all five suspect nodes.
- Geometry tasks 1/2 completed: `{12,4}` P3 is `FEASIBLE(0)` plus
  `UNKNOWN(0.600)` and therefore produces no gap statement; P4 is
  `FEASIBLE(0)` plus exact `EXCLUDED(0.300)`, a coarse certified span.  The
  refreshed snapshot has 150/205 durable rows (67 FEASIBLE, 48 EXCLUDED,
  90 UNKNOWN).  Submission commit `d1ebd7d` is public in Harness PR #267;
  only independently accepted follow-up evidence may update it.

## 10. Handoff protocol

Before starting work:

1. read Sections 0, 1, 7, and 9 of `status.md`;
2. confirm the dashboard has exactly one `ACTIVE` gate;
3. work on its first unchecked item;
4. preserve unrelated worktree changes.

Before ending work:

1. run the tests relevant to the changed algebra/level code;
2. attach evidence to the completed workflow checkbox;
3. update coverage and the dated log in `status.md`;
4. update this file only for a new decision, correction, blocker, or handoff;
5. never report a new gap number without symmetry, level, status, residual,
   and certificate classification.
