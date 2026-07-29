# Quantum Harness Issue #88 — remote research agent status

Updated: 2026-07-29T18:46:54Z

- Objective: obtain a new reproducible numerical certificate for an
  unrestricted frustrated spin-1/2 model, prioritizing the Shastry--Sutherland
  local KMS gap relaxation at `g=4/5`, `gamma=2`, complete degree `d=2`.
- Local branch: `remote/challenge88-terminal-solve`; ray-replay code is at
  `3e4820d` with this status update following it.
- Local checkout was clean at takeover. No user changes were shipped or
  overwritten.
- Preserved SCNet baseline job `118171391`: `RUNNING` on `kshcnormal`, 32 CPUs,
  114000 MiB, 12-hour limit. At 2026-07-29T14:48Z it was in exact `L=2,d=2`
  coefficient/isotypic assembly before JuMP/Mosek, with about 6.1 GB process
  RSS. It has not been cancelled or modified.
- Preserved xH5 baseline job `23011251`: `PENDING (Priority)` on
  `xhacnormalb`, 64 CPUs, 240 GB, 12-hour limit. It has not been cancelled or
  modified.
- Scientific interpretation guard: the run is an unrestricted finite
  relaxation feasibility test. A clean feasible result does not prove a
  physical gap; an infeasible status is not a certificate until an independent
  infeasibility-ray/residual replay passes.
- Immediate changed action: audit the single-pass construction opportunity and
  the missing post-solve numerical residual export while both immutable
  baseline jobs continue.
- Source-prepared improvement: the exact isotypic coefficient inventory now
  fingerprints bounded batches of row payloads through an incremental SHA-256
  context. It preserves the byte framing and coefficient hash while removing
  the all-entries `Vector{String}` and whole-stream `IOBuffer`. Julia syntax and
  a direct old-vs-streaming UTF-8 framing check pass locally. The full L=1
  structural pipeline also passes locally in 225.425 s for its coefficient
  stage: 7,231 moments, 75,967 PSD entries, and the unchanged regression hash
  `2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679`.
- xH5 baseline job `23011251` entered `RUNNING` at 2026-07-29T14:49:17Z from
  its immutable older commit `2de1678`; it is in the same first coefficient
  pass as SCNet. Both baseline jobs remain untouched.
- Source-prepared audit change: direct solves now export every primal moment by
  exact Float64 bits, reconstruct and diagonalize every named real PSD block,
  measure normalization/equality/PSD residuals, and classify results as
  residual-checked feasible, infeasibility-candidate-needing-ray-replay, or
  unknown. A standalone synthetic Mosek regression is included; its remote
  Slurm run is the next software gate.
- Synthetic audit test r1, SCNet job `118172524`, failed before model creation:
  the top-level audit script had not imported `LinearAlgebra`, so `Symmetric`
  was undefined. This is an entry-point import error, not a solver or
  mathematical result. The shared build entry now imports `LinearAlgebra`;
  r2 will test that changed source once.
- Synthetic audit r2, SCNet job `118172573`, passed 9/9 cone-audit and
  classification assertions in a 47-second job (515,632 KiB MaxRSS). Extended
  r3, job `118172627`, additionally passed exact-bit primal export and artifact
  hashing: 14/14 assertions in 55 seconds (517,356 KiB MaxRSS). The audit path
  is authorized for the next decision-relevant solve, not as a duplicate of
  either running baseline.
- Artifact regression r4, SCNet job `118172817`, passed 23/23 assertions in
  41 seconds (509,788 KiB MaxRSS). The direct path can now write hashed Mosek
  interior-solution and compressed task artifacts for later infeasibility-ray
  replay; solver-reported infeasibility still remains only a candidate until
  that independent replay succeeds.
- SCNet baseline job `118171391` was still `RUNNING` at 2026-07-29T15:19Z,
  44:46 elapsed, in its first coefficient pass. It remains untouched.
- Both protected baselines completed their first exact coefficient inventory
  and entered the second coefficient pass used to construct the JuMP/Mosek
  model. At 2026-07-29T15:46Z, SCNet job `118171391` was still running at
  1:11 elapsed with 7.81 GB MaxRSS; xH5 job `23011251` was still running at
  0:57 elapsed with 9.20 GB MaxRSS. Neither had entered `optimize!`.
- Native Mosek text/JSON/binary solution reloads were rejected after tiny
  tests showed lost status/zero rays or read error 1050. The changed route
  exports every scalar and semidefinite dual-ray component by exact Float64
  bits in a versioned binary artifact, pairs it with the binary task, and
  reconstructs it into a fresh task for Mosek's independent solution-quality
  calculation. SCNet job `118173664` passed the scalar Farkas fixture 29/29:
  dual objective 1.0, normalized separation 1.0, zero dual violation.
  Semidefinite fixture r15, job `118173766`, passed the ray numerically but
  exposed that MosekTools stores its 2-by-2 PSD ray as an affine-conic dual,
  not a bar variable. Corrected r16, job `118173855`, passed 36/36 tests: its
  three-component PSD dual replayed with dual objective 0.7526914264,
  normalized separation 0.5981688277, and zero dual violation.
- Integrated the single-pass native Mosek primal at `e50da6c`. Post-merge ray
  replay job `118174144` passed 36/36 tests. Corrected native L=1 truth job
  `118174309` passed in 1:12 with 1,468,728 KiB MaxRSS, reproducing 7,231
  moments, 23 PSD cones, 75,967 packed entries, 233,206 scalar coefficient
  terms, and required hash
  `2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679`.
- Target native commit `6aa430b` adds a fail-closed check for the exact L=2
  coefficient-map hash
  `935aab36220ec3f0b2bfaa92ea7527463c9dc1a2d579014798e4fe5534b6b1b4`.
  SCNet job `118174488` started at 2026-07-29T16:13:27Z on 32 CPUs / 114000
  MiB. It is the current decision solve: one streamed coefficient pass into
  native Mosek, followed by residual-checked primal export or explicit Farkas
  ray preservation/replay.
- At 2026-07-29T16:14Z protected SCNet baseline `118171391` was still running
  after 1:39 with 8,377,328 KiB MaxRSS, and protected xH5 baseline `23011251`
  after 1:25 with 10,432,348 KiB MaxRSS. Both logs still ended at JuMP model
  materialization; neither was cancelled, modified, or interpreted.
- Native launch job `118174488` failed before constructing the model because
  deployment had left the isolated checkout at detached `HEAD`; its source
  provenance guard rejected `git symbolic-ref`. The branch will be reattached
  cleanly and the same decision signature submitted once. This is an
  operational launch failure, not evidence about feasibility or the gap.
- The isolated checkout is now attached and clean at commit `4f33981`.
  Replacement native L=2 job `118174638` started at
  2026-07-29T16:17:15Z on 32 CPUs / 114000 MiB.
- Native job `118174638` passed the full exact construction gate in 1,733.452
  s with 13,829,968 KiB stage RSS: 461,186 moments, 26 affine PSD cones /
  4,446,492 rows, 15,802,343 scalar terms, zero remaining equalities, and the
  required coefficient-map hash
  `935aab36220ec3f0b2bfaa92ea7527463c9dc1a2d579014798e4fe5534b6b1b4`.
  Mosek started and completed presolve in 6.28 s. A terminal numerical status
  and residual or independently replayed ray are still required.
- Protected xH5 baseline `23011251` printed its `attach Mosek and optimize`
  marker after about 1:40, but had not yet emitted a Mosek iteration log at
  2026-07-29T16:50Z. Treat it as model transfer/bridging, not a result.
- Protected xH5 baseline `23011251` subsequently ended naturally as
  `OUT_OF_MEMORY` (`0:125`) after 1:48:50, before any Mosek iteration. Slurm
  recorded 234,603,960 KiB MaxRSS and `/usr/bin/time` 251,835,816 KiB against
  its 240 GB request. Exact coefficient assembly took 1,835.530 s and JuMP
  construction 3,991.145 s; the OOM occurred during JuMP→Mosek transfer. It
  was not cancelled, is not a feasibility result, and should not be rerun with
  the same signature.
- Commit `09729d7` prepares the native dual route with exact L=2 coefficient
  hashing, residual checks, exact-bit bar-matrix certificate export, and
  fresh-task replay. Synthetic SCNet job `118177325` ended immediately as
  `JobLaunchFailure` (`0:53`) on `a01r4n14`, with zero runtime and no log. One
  unchanged resubmission is authorized because no test process ran.
- Audit r2 `118177473` repeated launch failure (`0:53`, two seconds) on a
  different node. The verified common cause is a missing gitignored
  `results/_slurm` directory in the fresh clone, preventing Slurm from opening
  stdout. Create that exact directory and preflight it before r3.
- Audit r3 `118177590` executed for 1:25 (582,504 KiB MaxRSS) and passed 43/46
  tests. The native bar-matrix artifact passed source-status/RHS checks but
  fresh-task primal violation was 1.0 because constraint activities were not
  inserted. The revised artifact stores those exact-bit activities so Mosek
  can recheck the complete primal solution tuple in r4.
- Corrected dual audit r4 `118177811` passed all 46 tests in 1:07 at 514,500
  KiB MaxRSS. Its fresh-task native bar-matrix certificate replay has correct
  one-minus-one/all-other-zero RHS structure and maximum primal violation 0.
- Native primal job `118174638` ended naturally `OUT_OF_MEMORY` (`0:125`) after
  52:21 during post-presolve system formation and before iterations. Slurm
  MaxRSS was 104,717,420 KiB; `/usr/bin/time` measured 116,125,540 KiB against
  114000 MiB. Exact construction/hash evidence remains valid, but this is not
  a feasibility result. The next changed action is the native bar-variable
  dual solve on xH5 (64 CPUs / 240 GB) with fail-closed hash and replay output.
- xH5 rejected the dual before assigning a job ID because account `giggleliu`
  is at `AssocGrpSubmitJobsLimit` (200 jobs). No unrelated or pending job will
  be cancelled. The changed destination is SCNet high-memory
  `ksagnormal01`, 32 CPUs / 256000 MiB. That request is justified by measured
  failed-form peaks of 116,125,540 and 251,835,816 KiB, and the partition is
  up and permits the active account.
- SCNet test-only created no job and returned `QOSMinGRES`: high-memory
  `ksagnormal01` requires at least one GPU allocation. The runner now requests
  one GPU explicitly; the measured high-memory need justifies the reservation.
- Protected SCNet baseline `118171391` ended naturally `OUT_OF_MEMORY`
  (`0:125`) after 2:27:56 while transferring/bridging the JuMP model into
  Mosek, before an iteration. Slurm batch MaxRSS was 105,617,508 KiB and
  `/usr/bin/time` measured 114,714,824 KiB against 114000 MiB. It was not
  cancelled and supplies no feasibility evidence; both protected baselines
  are now closed OOM.
- First one-GPU high-memory submission `118178575` was rejected at time zero
  as `BadConstraints`: enforced GPU/CPU locality could not bind 32 CPUs to one
  GPU. The CPU-only solve now explicitly disables GRES binding while retaining
  the admission GPU. `sbatch --test-only` accepts that exact 32-CPU /
  256000-MiB request; next action is one real submission and live monitoring.
- SCNet ignores `--gres-flags=disable-binding` when supplied only in the
  script header, but accepts the identical runner when the option is explicit
  on the `sbatch` command. Native-dual job `118178932` is pending `Priority`
  from clean commit `a77fc0e`, requesting 32 CPUs / 256000 MiB / one GPU with
  `GresEnforceBind=No`. No duplicate high-memory solve will be launched while
  it remains queued.
- Source-prepared exact shrink: because `d=2` moments have at most four spin
  vector factors, continuous SO(3) averaging adds only the rank-four identity
  `T_xxxx = T_xxyy + T_xyxy + T_xyyx` beyond the established octahedral
  quotient. An opt-in native-dual projection now eliminates those coordinates
  under a separate coefficient fingerprint. It preserves unrestricted-state
  semantics and is not yet authorized for L=2: next gate is an L=1 exact
  construction/solve comparison on the configured SCNet environment.
- L=1 SO(3) job `118179614` completed in 13:40, peak 4,820,548 KiB. It
  reduced 7,231 equations to 5,314 and established hash
  `7308c57ba6b515501fd1c0c00f753868c0bb8cb32531429398fd902b4d63231a`,
  but returned an apparent native-dual certificate with violation
  `2.3730706288915826e-8`, contradicting the known feasible unreduced L=1
  relaxation. Fresh-task replay passes at `1e-7` and fails at `1e-9`; this is
  not scientific evidence. Reduced L=2 remains blocked pending an unreduced
  native-dual control and projection/scaling diagnosis.
- Unreduced native-dual control `118180537` completed in 13:18 at 10,652,388
  KiB, reproducing the exact established 7,231-moment hash. It too returned
  approximate `OPTIMAL`; maximum violation `1.053194864653051e-9` failed the
  required `1e-9` audit. This proves the bar-certificate status can be a weak
  numerical false positive on a known-feasible model. The next discriminator
  is a hash-gated SO(3)-reduced native-primal solve and `1e-9` residual audit;
  reduced L=2 remains unlaunched until that passes.
- Reduced native-primal control `118181379` completed from clean commit
  `4de8fc4` in 17:39 at 24,548,328 KiB Slurm MaxRSS. It reproduced the exact
  reduced hash
  `7308c57ba6b515501fd1c0c00f753868c0bb8cb32531429398fd902b4d63231a`,
  5,314 moments, 23 PSD cones / 75,967 packed rows, 241,903 scalar terms, and
  1,917 eliminated rank-four coordinates. Mosek returned primal-and-dual
  feasible; the saved audit is `feasible_residual_checked_float` at `1e-9`,
  with maximum affine-cone and equality violations both zero. The SO(3)
  rank-four quotient is now authorized for L=2; this is not itself a gap
  result.
- Immediate action: commit this gate, update the now-idle isolated checkout,
  and submit one exact build-only L=2 SO(3) construction. Use its hash as a
  mandatory input to a separate numerical solve. Unreduced high-memory job
  `118178932` remains pending and untouched.
- Exact L=2 SO(3) build-only job `118182637` is running on SCNet from clean,
  immutable commit `5a219a9` with 32 CPUs / 48000 MiB. It started at
  2026-07-29T18:45:55Z and cannot call the optimizer. Monitor it to obtain the
  reduced structural inventory and coefficient hash; do not update its shared
  checkout while it runs.

No user input or new credential is currently required.
