# B4 Thread Status: Stage 6 Pilot and A800 Calibration

## Thread identity

- Thread: B4
- Date opened: 2026-07-29
- Scope: implementation-plan Task 14 / Stage 6 only
- Branch retained: `challenge/issue28-pure-neural`
- HEAD retained: `a734162e0e75098fd9326e0aeb45e9ae3247b0f5`
- State: Stage 6 in progress; A800 throughput passed, temperature ladder requires recalibration

No commit, push, branch switch, PR mutation, Stage 7 production submission,
L=45 production calculation, or second RG has been performed.

## Completed

1. Re-probed qdeshell and confirmed the only visible partition remains
   `qdagnormal` with eight A800 GPUs per node and a 24-hour harness cap.
2. Confirmed the account/QOS association is
   `giggleliu/user_zhangdazhong`. The QOS priority contribution remains zero and
   fair share remains low, while short jobs can still backfill onto free A800s.
3. Pulled and hash-locked the Python 3.12.11 base SIF and installed a pinned
   external JAX CUDA 12 environment. Added the missing core dependency
   `numba==0.66.0`; `pip check` reports no broken requirements.
4. Completed A800 backend job `5314955`: JAX saw `cuda:0`, x64 was enabled,
   no CPU fallback occurred, and the manifest checksum passed.
5. Implemented a checkpointable JAX parallel-tempering backend with complete
   replica swaps, independent walker pairs, temperature labels, online
   round-trip state, overlap fields, swap statistics, and trajectory-identical
   checkpoint restore.
6. Completed full-ladder PT backend job `5314958` at L=12 with 48 temperatures
   and four chain pairs. All 47 swap edges were exercised; replica-label and
   overlap invariants passed.
7. Added the fixed Stage 6 config, 120-cell full-ladder run-spec builder,
   A800-bound resource projection, immutable launch package, checkpointed
   calibration cells, pilot-cell CLI, profile-neutral Slurm wrapper, and
   fail-closed production-candidate freeze.
8. Generated immutable launch package
   `results/hard_goal/stage6-b4-calibration-v1/` and verified cell 1 both
   locally and inside the remote SIF/venv.
9. Submitted formal Stage 6 calibration job `5314982` for cell `L12-J0000`:
   one A800, eight CPUs, 16 GiB, 1:30:00 walltime, 4096 sweeps, checkpoint every
   256 sweeps. Current state at this update: `PENDING (Priority)`, with Slurm
   backfill start scheduled for 2026-07-29 13:17:28 Asia/Shanghai on `gpu20`.

## Test results

- Full HG3D suite after final launch-package hardening:
  `260 passed in 123.84s`.
- Focused Stage 6/backend/freeze/Slurm suite: `33 passed`.
- Python compilation for all new Stage 6 modules and scripts: PASS.
- Bash syntax for all three A800 Slurm scripts: PASS.
- Scoped whitespace check: PASS.
- Remote container dry-run for cell 1: PASS, spec SHA-256
  `f19fa39df23ece0233fce824ddbc2153ca9a59c813518ad729a386f19688f6f6`.

## Measured resource evidence

- Base JAX smoke `5314955`: 655,963 warm spin proposals/s, 9.85 s first
  compile wall, approximately 34 MiB peak device memory.
- Full-ladder PT smoke `5314958`: 940,039 warm spin proposals/s, 16.95 s first
  compile wall, approximately 46.8 MiB peak device memory and 0.64 GiB peak
  host RSS.
- Conservative L=12 calibration estimate: 2,891 s (48.2 min) per J sample.
- Conservative first-pass 120-cell estimate: 314.1 A800-hours. Per-cell
  1.5x-margin wall requests remain below 24 hours for L=12/18/24/27.
- Maximum 1,048,576-sweep equilibration does not fit one job and must use the
  implemented checkpointed extension protocol.

## Key design decisions

- One cell owns one complete 48-temperature ladder; temperature is never an
  array axis.
- Adjacent walkers form independent thermal replica pairs for overlap.
- The first remote Stage 6 action is one L=12 calibration cell, not the full
  120-cell array. The complete array is released only after measured steady
  throughput, swap statistics, round trips, checkpoint integrity, and wall
  margin are reviewed.
- Calibration manifests explicitly state `tc_evidence=false` and cannot satisfy
  the Stage 6 scientific PASS or production freeze by themselves.
- Stage 7 remains separately gated by a measured Stage 6 PASS candidate and an
  exact resource preview/approval.

## Not completed

- Job `5314982` has not started or produced its first checkpoint yet.
- The remaining 119 calibration cells have not been submitted.
- No doubling equilibration, 8192-sweep measurement, VMCRG route comparison,
  conditioned-linear comparison, power calculation, or production candidate
  exists.
- No Stage 6 PASS, L=45 data, finite-size crossing, Tc estimate, or Hard Goal
  completion claim exists.

## Next step

Monitor `5314982` through `PENDING -> RUNNING`, tail the first checkpoint log,
fetch and rehash the completed cell, then compare measured wall/swap/round-trip
evidence to the launch estimate. Only a clean result authorizes a reviewed
expansion of the Stage 6 calibration array.

## Update: 2026-07-29 13:06 CST

### Completed since the prior update

1. Job `5314982` started on `gpu20` but failed before Python with exit `1:0`
   after four seconds. The exact root cause was Bash 4.2 nounset behavior for
   an empty `resume_args` array in `jobs/hard_goal_pilot.slurm`.
2. Added a regression covering the pilot and Stage 7 wrappers, replaced the
   possibly empty array with an always-nonempty `command_args` array, and
   verified `20 passed`, `bash -n`, and `git diff --check`.
3. Preserved the failed v1 package and generated immutable v2 package
   `results/hard_goal/stage6-b4-calibration-v2/`. The v2 run-spec SHA-256 is
   `f6611972624c60fd1a5e6126c1f60e6747cf3ca1f65cf00c0b5e189c8dae4318`.
4. Job `5315015` completed on `gpu20` with exit `0:0` in 4 minutes 5 seconds.
   The final manifest SHA-256 is
   `7d6aba56023dde6a54c52cd95550075a34775b9eeb27c8df66f2c0a846c418e3`.
5. Fetched cell `L12-J0000` locally. All 34 manifest-listed artifacts exist
   and match their SHA-256 values; the cell spec SHA-256 is
   `f902110441c4b6b285fb598992bf101830872f72fbac0ec898c58efb79bb080a`.

### Measured result

- 2,717,908,992 proposals in 198.999 seconds: 13,657,877 proposals/s.
- Peak host RSS: 612 MiB by Slurm, 660,008,960 bytes in the backend record.
- Peak device memory: 46,835,456 bytes; compile time: 3.480 seconds.
- All 47 exchange edges were exercised. Acceptance ranged from 0.5350 to
  0.8853, with mean 0.7545 and median 0.7820.
- Round trips ranged from zero to two after 4,096 sweeps.
- Operational classification is `CALIBRATION_COMPLETE`; scientific ladder
  decision is `RECALIBRATE`; `tc_evidence=false`.
- The measured throughput reduces the first-pass 120-cell calibration estimate
  from 314.1 to approximately 21.6 A800-hours before queue effects.

### Key decision and next step

The remaining 119 cells remain blocked because no exchange edge lies inside
the required upper target at or below 0.50 and the minimum round-trip count is
zero. Run two paired, hash-bound adaptive-beta candidates targeting exchange
acceptance 0.35 and 0.40 with the same J, chain count, endpoints, and 4,096
sweeps. Release the full calibration array only after one measured candidate
places every edge in 0.20-0.50 and improves temperature travel. No Stage 6
PASS, production candidate, Stage 7 submission, L=45 result, or Tc estimate
exists yet.

## Update: 2026-07-29 13:40 CST

### Completed in this result-reading thread

1. Job `5315033`, array selector 65 (`L18-J0000`), completed on `gpu22`
   with exit `0:0` in 8 minutes 4 seconds. Slurm reported peak batch RSS
   `635112K` for the one-A800, eight-CPU, 16-GiB request.
2. Located the result at the calculator-normalized remote path
   `~/quantum.harness/results/hard_goal/stage6-b4-calibration-v2/cells/L18-J0000/`
   and fetched it into the track-local result tree. The final manifest
   SHA-256 is
   `53d744cb2dacbc46e703879ce7ca2b027136bbeaef0c8620da2db2ce9067c247`.
3. All 34 manifest-bound artifacts exist and match their SHA-256 values.
   The diagnostic manifest also binds all three generated CSV/PDF/PNG
   artifacts with no mismatch and records `tc_evidence=false`.
4. Visually inspected the L=18 acceptance diagnostic. It shows the measured
   curve crossing the allowed upper boundary rather than an isolated noisy
   outlier.

### Measured L=18 result

- Completed 4,096 sweeps at 20,805,053 spin proposals/s; backend elapsed time
  was 440.900 seconds, peak host memory was 674,951,168 bytes, and peak device
  memory was 150,701,312 bytes.
- All 47 exchange edges were attempted. Acceptance ranged from 0.2473 to
  0.7816 with mean 0.5754. Round trips ranged from zero to one.
- Operational classification is `CALIBRATION_COMPLETE`, but the ladder
  decision is `RECALIBRATE`; `target_band_passed=false`,
  `second_rg_enabled=false`, and `tc_evidence=false`.

### Not completed

- Job `5315032`, selector 97 (`L24-J0000`), remains `PENDING (Priority)` with
  no log or result manifest.
- Job `5315031`, selector 113 (`L27-J0000`), remains `PENDING (Priority)` with
  no log or result manifest.
- The L=18 calibration is not an equilibrium run and does not authorize a
  Stage 6 PASS, expansion of the 48-temperature array, Stage 7 production,
  L=45 production, second RG, or a Tc estimate.

### Key decision and next step

The original 48-temperature ladder is over-dense for both measured L=12 and
L=18 cells. Preserve these runs as calibration-only evidence and do not
release their remaining disorder samples. Complete the hash-bound adaptive
ladder measurements separately by size; meanwhile monitor `5315032` and
`5315031`, fetch each terminal manifest, and derive L=24 and L=27 ladder
candidates from their own measured acceptance profiles rather than reusing
the L=12 candidate unchanged.

## Update: 2026-07-29 14:10 CST

### Additional cluster access completed

1. Installed the user-provided Huazhong and Huabei private keys outside the
   repository as `~/.ssh/scnet_key` and `~/.ssh/xh5_huabei_key`, both mode
   `0600`. Added independent SSH aliases without changing the existing
   Shandong `qdeshell` alias.
2. Batch login verification passed: Huazhong reaches the `zz-login` pool and
   Huabei reaches the `login` pool. The known Huazhong RSA-host-key warning is
   non-fatal; the connection is pinned through the accepted ED25519 key.
3. The existing `scnet.toml` profile now passes precheck. Its visible
   `hx1hdnormal01` partition currently includes 29 idle nodes, each with 128
   CPU cores, about 510 GB memory, and eight Hygon DCUs. The CUDA/JAX backend
   is not assumed compatible with those DCUs.
4. Created the confirmed private profile
   `skills/using-slurm/profiles/xh5-huabei.toml` and excluded it through local
   `.git/info/exclude`. The persistent active profile remains `qdeshell.toml`;
   Huazhong and Huabei require explicit `HARNESS_CLUSTER_PROFILE` selection.
5. Huabei exposes RTX 3080, RTX 3090, V100, and CPU partitions. Exact
   `sbatch --test-only` probes selected `xhhgnormal01` as the default because a
   one-RTX-3090, eight-CPU, 16-GiB, one-hour request had an immediate estimated
   start. The other tested partitions had impractically distant estimates
   despite some nominally idle nodes.
6. Huabei login internet is available and Singularity 3.8.7 is installed;
   Apptainer is not advertised. The remote `~/quantum.harness` checkout does
   not yet exist and the 25-GB home filesystem is otherwise empty.

### Verification and remaining gate

- Profile field parsing, SSH precheck, partition probing, key/config modes,
  Git-local exclusion, and the profile-derived RTX 3090 GRES dry-run passed.
- No code, container, run spec, result, or job was shipped to Huazhong or
  Huabei. No real job was submitted there.
- Before using Huabei for Stage 6, ship only a reviewed immutable package,
  adapt the wrapper from Apptainer to Singularity-compatible execution, run a
  compute-node CUDA/JAX smoke, fetch its manifest, and compare its throughput
  against the measured A800 backend. Huazhong requires a separate CPU or
  validated DCU route rather than silent CUDA fallback.

## Update: 2026-07-29 14:44 CST

### L=24 and L=27 calibration results

1. Job `5315032`, selector 97 (`L24-J0000`), completed on one A800 with exit
   `0:0` in 18 minutes 3 seconds. Slurm peak batch RSS was `668092K`.
2. Job `5315031`, selector 113 (`L27-J0000`), completed on one A800 with exit
   `0:0` in 24 minutes 48 seconds. Slurm peak batch RSS was `690824K`.
3. Fetched both cells from the calculator-normalized remote result path. The
   L=24 manifest SHA-256 is
   `fd9b2a4f180f33e2e377da0c99f4953215575fbd358936d4983026b89cc50fd5`;
   the L=27 manifest SHA-256 is
   `d8a649291cd2c7576b0b35cbdd7e13357f656fe678fb1344cb3e203c5d735a05`.
4. Each manifest has 34/34 matching artifact hashes and exactly matches the
   immutable run-spec length, J seed, chain count, temperature ladder, and
   run-spec SHA-256. Both diagnostic manifests have 3/3 matching PNG/PDF/CSV
   hashes and remain `DIAGNOSTIC_ONLY`, `tc_evidence=false`.

### Measured diagnostics

- L=24 completed 4,096 sweeps at 20,884,681 proposals/s. Swap acceptance was
  0.0753 minimum, 0.4168 mean, and 0.6827 maximum. Of 47 edges, 10 were below
  0.20, 17 were inside 0.20-0.50, and 20 were above 0.50. Every chain recorded
  zero complete temperature round trips.
- L=27 completed 4,096 sweeps at 21,416,187 proposals/s. Swap acceptance was
  0.0369 minimum, 0.3439 mean, and 0.6255 maximum. Of 47 edges, 15 were below
  0.20, 18 were inside 0.20-0.50, and 14 were above 0.50. Every chain recorded
  zero complete temperature round trips.
- For both sizes, the minimum is the highest-temperature edge
  `T=2.0 -> 1.938144...`; the acceptance then rises across the ladder and is
  too high near the low-temperature endpoint. This is a redistribution
  failure, not a uniform too-dense or too-sparse ladder.
- Both operational classifications are `CALIBRATION_COMPLETE`, but both
  scientific decisions are `RECALIBRATE`; `target_band_passed=false`,
  `second_rg_enabled=false`, and `tc_evidence=false`.

### Predicted-only adaptive candidates

- L=24: target 0.35 predicts 46 temperatures; target 0.40 predicts 51.
- L=27: target 0.35 predicts 55 temperatures; target 0.40 predicts 61 (the
  one-sigma proxy interval is 60-61 temperatures).

These counts use the existing cumulative `erfc^-1(acceptance)` proxy and are
not measured successes. They must become new immutable run packages and pass
the same 4,096-sweep calibration with every edge in 0.20-0.50 and improved
round trips before selection.

### Decision and remaining gate

The original 48-temperature ladder is rejected for every measured size
L=12,18,24,27, for different size-dependent reasons. Do not release any
remaining disorder cells with it. Run paired adaptive candidates separately
for each size after the ladder-scan wrapper uses the verified container launch
contract. No Stage 6 PASS, production freeze, L=45 result, or Tc estimate is
authorized by these calibration-only results.

## Update: 2026-07-29 current-status report and ladder hardening

### Code corrections completed

1. Added a fail-closed adaptive-ladder selection gate: a measured candidate
   with zero minimum complete round trips is rejected even when every exchange
   edge lies inside 0.20-0.50.
2. Replaced the ladder-scan wrapper's host `HARNESS_PYTHON` launch with the
   verified hash-pinned Python 3.12.11 SIF and CUDA/JAX GPU environment.
3. The two new tests were observed failing for the intended pre-fix behavior,
   then passed after the minimal implementation changes.

### Verification

- Focused adaptive-ladder suite: `16 passed`.
- Full HG3D suite: `353 passed in 206.12 s`.
- Ladder wrapper `bash -n`: PASS.
- Scoped `git diff --check`: PASS.
- No adaptive L=24/L=27 package or cluster job was submitted in this update.

### Generated report

- Source document:
  `results/hard_goal/stage6-status-20260729/report.json`
- Self-contained HTML:
  `results/hard_goal/stage6-status-20260729/report.html`
- Report JSON SHA-256:
  `a2683d8340dd578bd601e80eb6aaf697616cbad725d604f849ead399c320d43b`
- Report HTML SHA-256:
  `49665d0a816224b357049c0553751bf2611b2bcfed223b57e8c269c62fdef2c5`
- Both L=24 and L=27 acceptance figures are embedded in the offline HTML;
  their copied SHA-256 values match the immutable diagnostic originals.

### Current gate and next step

Stage 6 remains in progress. Generate immutable L=24 candidates with 46 and
51 temperatures and L=27 candidates with 55 and 61 temperatures, run the
qdeshell test-only feasibility check, and submit only those four calibration
cells. Selection still requires every edge in 0.20-0.50 and at least one
complete round trip; a passing ladder alone does not freeze production.

## Update: 2026-07-29 adaptive execution and VMCRG integration

### Completed in this thread

1. Re-ran the complete HG3D source suite after the sparse biased-update
   changes: `357 passed in 270.97 s`.
2. Generated and hash-verified the immutable adaptive packages:
   - `stage6-b4-l24-adaptive-v1`: 46- and 51-temperature candidates;
   - `stage6-b4-l27-adaptive-v1`: 55- and 61-temperature candidates.
3. Submitted the reviewed qdeshell arrays on `qdagnormal`:
   - job `5315125`: two L=24 cells;
   - job `5315124`: two L=27 cells.
   Each cell requests one A800, eight CPUs, 16 GiB, and one hour. No duplicate
   submission was made.
4. Job `5315124_1` (`L27-J0000-A035`) completed operationally with exit `0:0`
   in `00:23:17`. Its launch log binds the expected L=27 run spec, reports an
   A800, and contains all 16 checkpoint pulses through 4,096 sweeps.
5. Fetched the A035 result and verified the immutable package, run-spec, cell
   manifest, declared artifact inventory, and hashes. The cell manifest SHA-256
   is `99cab6398f55d755501f2d01cc6b23078325bb2e480bdde103fc79f1841e1fb8`.
6. Added the whole-disorder VMCRG training boundary: immutable
   `(J, draw, token)` batches, a stable structural sampler contract, explicit
   mean-within-J then mean-across-J gradients, ordered-J checkpoint provenance,
   frozen draw/token schema, complete RNG evidence, and transactional rollback.
7. Closed all four Important and two Minor findings from the independent batch
   contract review. Independent focused verification in the controller process
   passed `31` contract tests and `14` checkpoint tests.

### Measured A035 result and decision

- All 54 exchange edges are inside the required 0.20-0.50 band; acceptance is
  `0.34765625-0.36944580078125`.
- The cell-level calibration code records `ladder_decision=PASS`, but every
  chain records zero complete low-high-low round trips.
- The hardened selector therefore rejects A035 with
  `measured calibration has fewer than 1 complete round trip` and returns
  `RECALIBRATE`. No `selection.json` was persisted while A040 is missing.
- This is calibration-only evidence: `tc_evidence=false`, second RG remains
  disabled, and the result does not authorize the multi-J pilot or Stage 7.

### Tests and review evidence

- Full HG3D suite: `357 passed in 270.97 s`.
- Whole-J VMCRG contract implementation: sharded coverage over all 49 VMCRG
  nodes; focused controller rerun `31 passed`.
- VMCRG checkpoint file: `14 passed` in the implementer run and `14 passed in
  5.52 s` in the controller rerun.
- Independent re-review: Important 1-4 and Minor 1-2 `ADDRESSED`; no new
  Critical or Important finding.
- A long single-process VMCRG run still has an intermittent native exit 139 at
  varying pre-existing gauge/template symmetry calls. All affected tests pass
  in fresh-process shards; no unsupported source fix or pass claim was made.

### In progress and not completed

- `5315124_2` (L27 A040) and both L=24 cells remain `PENDING (Priority)`.
- A first correctness-only multi-J JAX VMCRG adapter is under TDD. Target-slot
  sampling, equal-per-J raw-pool selection, checkpoint trajectory equivalence,
  all-J rollback, and resource telemetry are being verified locally at L=3.
- Bias refresh is not yet connected transactionally to `VMCRGTrainer`, and the
  Stage 6 runner still does not produce representation-comparison evidence.
- No multi-J equilibration/ESS result, Route C/B versus conditioned-linear
  paired-J bootstrap, power calculation, production candidate, L=45 result,
  finite-size crossing, or Tc estimate exists.

### Key decisions and next step

1. Preserve A035 as a scientifically rejected calibration. Wait for A040 and
   both L=24 candidates before deciding whether to retain the accepted spacing
   and extend the calibration length; do not redesign spacing solely because
   4,096 sweeps were too short for a complete trip.
2. Finish and independently review the multi-J JAX adapter, then add
   transactional stage-specific bias installation. C1 must sample a strictly
   linear-only action; C2/C3/B must use the corresponding current TT action.
3. Produce a small hash-bound representation cell before any medium-size Route
   C/B comparison. Only equilibrated, equal-J evidence may enter model
   selection.
4. Stage 6 remains `IN PROGRESS / NO-GO FOR FREEZE`; Stage 7 preview and L=45
   production remain blocked by M6.

## Update: 2026-07-29 22:04 CST adaptive result readout

### Completed in this result-reading thread

1. Classified both qdeshell arrays after they left the live queue. All four
   cells completed with Slurm exit `0:0`: L27 A035 in `00:23:17`, L27 A040 in
   `00:27:27`, L24 A035 in `00:17:22`, and L24 A040 in `00:20:38`.
2. Fetched the calculator-normalized remote outputs into the track-local
   `results/hard_goal/` tree. Verified each immutable package/run spec and all
   34 manifest-declared artifacts per cell with the hardened ladder selector.
   There are no missing artifacts or SHA-256 mismatches.
3. Read all four launch logs. Every cell used the expected run spec, one
   NVIDIA A800 80GB device, x64 JAX on `cuda:0`, and all sixteen 256-sweep
   checkpoints through 4,096 sweeps. The reported `hwloc_set_cpubind` message
   was non-fatal and did not cause CPU fallback.

### Measured result and tests

| Cell | Acceptance range | Minimum complete round trips | Selector result |
|---|---:|---:|---|
| L24-J0000-A035 | 0.345947-0.371826 | 0 | rejected |
| L24-J0000-A040 | 0.392700-0.418762 | 0 | rejected |
| L27-J0000-A035 | 0.347656-0.369446 | 0 | rejected |
| L27-J0000-A040 | 0.396057-0.424866 | 0 | rejected |

- All measured exchange edges pass the predeclared `[0.20,0.50]` band.
- The adaptive-ladder selector returned `RECALIBRATE` for both sizes because every
  candidate has fewer than one complete low-high-low temperature round trip.
- This thread ran the artifact-validating selector for both paired packages;
  it did not run a new simulation or alter any immutable result.

### Key decision, incomplete work, and next step

The adaptive spacing problem is resolved for this J sample, but 4,096 sweeps
is too short to establish temperature travel. Preserve all four v1 cells as
calibration-only (`tc_evidence=false`) and do not release the multi-J pilot or
Stage 7. Implement and review the additive parent-checkpoint extension
contract, then extend the paired candidates under one predeclared staged rule.
Selection still requires an actually measured minimum round-trip count of at
least one; Stage 6 remains `IN PROGRESS / NO-GO FOR FREEZE`.

## Update: 2026-07-30 Stage 6 extension implementation and first submission

### Completed

1. Implemented additive, parent-checkpoint-bound calibration extensions with
   complete PT-state restore, child-hash checkpoints, immutable package
   lineage, atomic output/resume, package-bound selector evidence, paired-cell
   selection, GPU-only evidence, and strict counter/travel/path validation.
2. Closed the independent review's Critical/Important findings through
   test-first regressions. Fresh-process shards pass: backend `19`, pilot `33`,
   ladder selector `31`, extension `41`, for `124 passed` total. Bash syntax,
   Python compilation, scoped whitespace, real-parent planning, and all five
   immutable L27 A035 v1 anchors pass.
3. Generated and dry-run validated four immutable 4,096-to-8,192 packages:
   L24/L27 x A035/A040. Synced only the eight hash-bound execution files and
   four packages to qdeshell; remote hashes match local hashes.
4. qdeshell precheck passed. `qdagnormal` is the only visible partition (four
   mixed and four allocated nodes). Exact one-A800/eight-CPU/16-GiB/one-hour
   test-only passed but returned a conservative 2027-07-02 start estimate.
5. Submitted only the L24 A035 operational continuation as job `5315277`.
   Current state: `PENDING (Priority)`. The remaining three cells are held until
   this new wrapper produces a healthy compute-node startup/result.

### Not completed and next step

No extension result, new round trip, Stage 6 PASS, production freeze, L=45
result, crossing, or Tc estimate exists yet. Monitor `5315277`; on start, tail
the launch/checkpoint log. On completion, fetch and hash-validate the terminal
manifest. Submit the other paired continuation cells only after that
operational gate passes. Stage 7 remains blocked.

## Update: 2026-07-30 paired continuation release

### Completed

1. The user explicitly authorized direct release of the remaining three paired
   continuation cells without waiting for the first cell to complete.
2. Submitted all three reviewed 4,096-to-8,192 packages on qdeshell
   `qdagnormal`, each requesting one A800, eight CPUs, 16 GiB, and one hour:
   - `5315301`: L24 A040;
   - `5315302`: L27 A035;
   - `5315303`: L27 A040.
3. Checked all four continuation jobs once after submission. Jobs `5315277`,
   `5315301`, `5315302`, and `5315303` are all `PENDING (Priority)` with one
   task each. Submission succeeded; no startup result exists yet.

### Current gate and next step

Wait for all four jobs to become terminal, then classify with Slurm accounting,
fetch every run, verify package lineage/manifests/artifact hashes, and aggregate
the paired A035/A040 round-trip evidence. Stage 6 remains `IN PROGRESS / NO-GO
FOR FREEZE` until the measured minimum complete round trips are at least one.
Stage 7/L=45 remains blocked.

## Update: 2026-07-30 8,192-sweep readout and 16,384 preview

### Completed

1. Slurm accounting confirms all four 4,096-to-8,192 continuation cells
   completed with exit `0:0`: jobs `5315277`, `5315301`, `5315302`, and
   `5315303` ran for 15-24 minutes with peak batch RSS below 0.8 GiB.
2. Fetched all four terminal result trees locally. The selector revalidated
   every package artifact, parent/child lineage edge, cumulative and extension
   counter, terminal/target checkpoint, runtime record, and declared SHA-256.
3. Fixed the result-reader boundary so immutable historical scan/extension
   packages remain selectable after source evolution. Actual cell execution
   still requires exact equality with the current source hashes; only the
   read-only selector accepts a complete valid historical source inventory.
4. The paired selectors produced durable `RECALIBRATE` records:
   - `results/hard_goal/stage6-status-20260730/L24-selection.json`, SHA-256
     `a81fc790b3981bdf4918bf12c08b3e078c3eceffd9b6cf107c225810a748052f`;
   - `results/hard_goal/stage6-status-20260730/L27-selection.json`, SHA-256
     `5db10eabcf14815bf807e1c79d1529f7280c3f56d3874e726be578e39325da54`.
5. Generated four immutable, chained 8,192-to-16,384 continuation previews.
   Each copies and hash-binds the verified 8,192-sweep terminal checkpoint and
   resolves one canonical child under local GPU-required dry-run.

### Measured result

| Cell | Cumulative acceptance | Complete round trips min/max | Selector |
|---|---:|---:|---|
| L24 A035 | 0.343262-0.370331 | 0/0 | rejected |
| L24 A040 | 0.393616-0.420197 | 0/1 | rejected |
| L27 A035 | 0.343719-0.366180 | 0/0 | rejected |
| L27 A040 | 0.391235-0.422150 | 0/0 | rejected |

All four ladders retain every edge inside the frozen `[0.20,0.50]` band. The
only selector failure is the predeclared requirement that the minimum complete
low-high-low round-trip count across all trackers be at least one. Stage 6
therefore remains `IN PROGRESS / NO-GO FOR FREEZE`.

### Verification and preview

- Ladder scan plus extension regression: `74 passed in 15.13 s`.
- Focused historical-package regression and extension suite: `44 passed`.
- Python compilation and scoped whitespace check: PASS.
- Additional 8,192-sweep wall projection from measured throughput:
  approximately 29-33 minutes for L=24 and 45-48 minutes for L=27; a 1.5x
  margin requires up to approximately 72 minutes.
- Exact proposed request per cell: one A800, eight CPUs, 16 GiB, `01:20:00`,
  checkpoint every 256 sweeps. Four cells add about 2.6 A800-hours measured,
  or 3.9 A800-hours with the 1.5x planning margin.
- Estimated new output is approximately 118 MB total, or 177 MB with the
  frozen 1.5x output margin.
- Synced the eight hash-bound execution files and four preview packages to
  qdeshell; 16/16 compared source/package hashes match locally with zero
  mismatches.
- Exact qdeshell `sbatch --test-only` accepted the one-A800/eight-CPU/16-GiB/
  `01:20:00` request, but returned a conservative estimated start of
  `2027-05-21 21:52:23` on `gpu4`. No real job was created.

No 16,384-sweep job has been submitted. Before real compute, re-confirm the
unchanged iid +/-J Edwards-Anderson Hamiltonian, periodic L=24/L=27 lattices,
two-copy overlap observable, 0.8-2.0 temperature endpoints, and continuation
of all four paired A035/A040 candidates under the same J and seeds. Stage 7,
L=45, second RG, and Tc claims remain blocked.

## Update: 2026-07-30 16,384-sweep continuation submission

The user explicitly reconfirmed the unchanged physical and execution setup.
Submitted the four reviewed 8,192-to-16,384 continuation packages to qdeshell
`qdagnormal` without duplication:

| Cell | Job ID | Initial state | Estimated start |
|---|---:|---|---|
| L24 A035 | `5315365` | `PENDING (Priority)` | 2026-07-31 02:00 CST |
| L27 A035 | `5315366` | `PENDING (Priority)` | 2026-07-31 03:00 CST |
| L27 A040 | `5315367` | `PENDING (Priority)` | 2026-07-31 03:00 CST |
| L24 A040 | `5315368` | `PENDING (Priority)` | 2026-07-31 03:00 CST |

Each job has exactly one array cell and requests one A800, eight CPUs, 16 GiB,
and `01:20:00`. `scontrol` confirms `gres/gpu:A800:1`, the expected wrapper,
and the correct qdeshell repository work directory for all four jobs. No
compute-node startup log or 16,384-sweep result exists yet. On start, verify
the A800/container/source-hash banner and first checkpoint before treating the
jobs as operationally healthy. Stage 6 remains `IN PROGRESS / NO-GO FOR
FREEZE` pending terminal artifacts and the minimum-round-trip gate.

## Update: 2026-07-30 local-only terminal submission

The user withdrew authorization for supercomputer execution and requested a
local-only submission before 16:00 CST. Jobs `5315365`, `5315366`, `5315367`,
and `5315368` were cancelled before start; Slurm accounting records
`CANCELLED by 51160`, zero elapsed time, and no compute-node allocation for all
four. The qdeshell user queue was empty immediately after cancellation.

Local capacity audit:

- Host: 13th Gen Intel Core i9-13980HX, 32 logical CPUs, 31 GiB RAM.
- NVIDIA access is blocked by the operating system; JAX exposes CPU only.
- A complete L=12, 48-temperature, four-chain-pair CPU smoke measured
  1,567,363 spin proposals/s and passed label/overlap invariants.
- At that measured rate, the fixed 120-cell Stage 6 first-pass calibration
  alone projects to approximately 188.4 local wall hours, before doubling
  equilibration, measurement, VMCRG representation comparison, or power
  analysis. Full Stage 7 is therefore infeasible under the local-only deadline.

The terminal result is classified `RESOURCE_NO_GO`, not `PASS`. Stage 4 and
Stage 5 retain their verified `PASS` classifications; Stage 6 does not pass
equilibration, Stage 7 has no L=45 production, and Stage 8 has no valid input
for FSS or RG-flow inference. No Tc value is reported.

Upload-ready Stage 9 artifacts:

- Self-contained report:
  `results/hard_goal/submission-20260730/report.html`.
- Evidence directory manifest:
  `results/hard_goal/submission-20260730/manifest.json`.
- Deterministic archive:
  `results/hard_goal/submission-20260730.zip`.
- Archive SHA-256:
  `399bb40e9f4407956d67d40f8304326043a9ad97de32964dd76623b015aea33c`.
- Stage 6-8 workflow verification: 67 tests passed in isolated files.
- Submission builder end-to-end test: 1 passed; ZIP integrity and all
  manifest-bound artifact hashes passed.
