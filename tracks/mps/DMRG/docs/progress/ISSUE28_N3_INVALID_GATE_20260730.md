# Issue 28 N3 Invalid Gate Incident, 2026-07-30

## Status

The N3 pilot produced useful historical data, but its training, validation,
classification, and freeze decisions are invalidated by a protocol
implementation defect. The affected artifacts must not be deleted, overwritten,
or promoted into `config/issue28_formal_v1.json`.

This record distinguishes preserved experimental output from valid scientific
evidence. It does not claim that the sampler, neural Hamiltonian, BAR estimator,
checkpoint format, or round handoff is incorrect.

## Provenance

- Umbrella protocol SHA-256:
  `a08eef49f356f40b40eed878b62993e671d383fb98d8b201e09bc51ff88464e6`
- N3 code SHA-256 recorded by the round manifests:
  `e8f5e3c9163eab8db9f0df3cccdc4f853844d049a8cf58df7db5e991c2a0ad31`
- Operator basis SHA-256:
  `a6c7f3126675cdf468465eee7667a82b35b41f5a821d48efc5b38028addfe9f0`
- Local source run:
  `results/issue28-n3-local-20260728-02`
- Remote continuation run:
  `results/issue28-n3-hpc-replica-20260729-01/cells/pilot`
- Preserved local copy of completed remote round 4:
  `results/history/issue28-n3-invalid-gate-20260730/round-04`
- Original Slurm job `5315057` was cancelled after round 4.
- Resume job `5315103` continued round 5 with the same invalid pre-fix code.
- At user direction, resume job `5315103` was cancelled at 2026-07-30 11:13:53
  CST after about 325 of 1000 old-code round-5 updates. Its staging directory
  contained no published files after cleanup.
- The obsolete freeze/N4/N5 jobs `5315106`, `5315107`, `5315127`, `5315128`,
  and `5315132` were cancelled before any of them ran.

The cancelled partial round 5 is historical timing/progress evidence only. It
has no manifest and cannot be resumed or promoted.

## Preserved Results

| Round | Manifest SHA-256 | Validation SHA-256 | Operator bound | Patch bound | Recorded gates |
|---|---|---|---:|---:|---|
| 1 | `dae51c19bb272e323da9b2d123725db3364e59ba2dd5cc71c98c9d6262686dec` | `aa009179861f17dc1cd5f27099ac2c3d358a44eec671f2749607dd773b27996c` | 0.258610 | 0.313538 excess | training `NOT_CONVERGED`, validation `FAIL`, objective `IDENTIFIABLE` |
| 2 | `4b90d10f1ab66c25a66f48e1daf94d6d54c9f496b2d2f333ae944949eed2f2e7` | `eb140ccdd743dc8c907df4e6c368abd01ff1f29690e53e0e0c56de5fd7a1a57c` | 0.212841 | 0.301902 raw two-sample | training `NOT_CONVERGED`, validation `FAIL`, objective `IDENTIFIABLE` |
| 3 | `a71fc9c9a6afa22c1c5727927cb8d005affbe18e5b06161a5e0592604224238b` | `66ef0ac6f8db1ff7137b93558b9123551eecf2061d7b9b9cc830579bb747bf9a` | 0.077681 | 0.137724 raw two-sample | training `NOT_CONVERGED`, validation `FAIL`, objective `IDENTIFIABLE` |
| 4 | `6d05d3dc7a126ea98bf149f77520e448c850852c57574343201a0f36d91f57a5` | `94480f4a25ad7097a35bfb09de9b0caf9809e9e8100ce482227953eb7f4ae81b` | 0.026534 | 0.094025 raw two-sample | training `NOT_CONVERGED`, validation `FAIL`, objective `IDENTIFIABLE` |

Round 4 preserved-file hashes also include:

- `training.json`: `09116615e8a52ecdd5b06fd06c669cf65b0eceb57bd775c38440db5265c1cb94`
- `objective.json`: `5ca4451b88e74ed97b28a2ae9c95045916300b628c8e2479a05e3533077cc74c`
- `round_report.json`: `c11e22ce61a300b095aaf3cbf50bc7bb7fbe11f334ad0a90b022f80ef7ef4c19`
- original job log `slurm-5315057.out`:
  `9856ce31a86a5e3698db6f4ad9a3e21b94b94b19330c78879be93ec9a94bb188`
- cancelled resume log `slurm-5315103.out`:
  `fa7a38cfc53d10f1c5b4aee85ef9f54d18b2f247dc417dac8e17002cf93e937f`

The operator trend and acceptance-rate trend remain descriptive historical
observations. They are not erased by this invalidation.

## Root Cause 1: Uncalibrated Patch-TV Gate

The frozen design requires an excess patch-TV statistic. The established N2
validation computes

`TV(observed, uniform) - TV(independent_target, uniform)`.

N3 instead computed

`TV(observed_empirical, independent_target_empirical)`

and compared that raw two-sample value with the same `0.02` excess-TV threshold.
Finite-sample noise therefore creates a positive floor even when both samples
come from the exact same uniform distribution.

A null simulation using the production 15 x 15 periodic patch histogram gave:

| Budget | Mean raw two-sample TV | Minimum simulated TV | Threshold | Null passes |
|---|---:|---:|---:|---:|
| Pilot validation, 100 configurations | 0.084650 | 0.076044 | 0.02 | 0 / 120 |
| Formal validation, 1000 configurations | 0.027004 | 0.025400 | 0.02 | 0 / 30 |
| Pilot monitor, 64 configurations | 0.105663 | 0.095347 | 0.02 | 0 / 160 |

Consequences:

- N3 monitoring could not satisfy the patch-TV convergence condition under the
  frozen budget, even for a perfect uniform null.
- `NOT_CONVERGED` was mechanically forced by an unreachable conjunction.
- N3 validation patch failures, especially round 4, cannot be interpreted as
  scientific evidence.
- Rounds 1-3 still have independent operator-equivalence failures; those values
  remain valid descriptive evidence but do not repair the gate defect.

## Root Cause 2: Classification Did Not Consume Scientific Gates

The per-round N3 implementation classified every handoff-correct round as
`SCIENTIFIC_NEGATIVE`, regardless of training, validation, or objective status.
The chain implementation then classified any five-round pilot without a
correctness failure as `EASY_GOAL_SUCCESS`, again without requiring the five
round scientific gates to pass.

This allowed contradictory state:

- each round could record failed scientific gates;
- the completed chain could still claim `EASY_GOAL_SUCCESS`;
- the formal-protocol freezer trusted that top-level classification and did not
  independently verify every round gate.

The old labels are retained as historical output fields, not accepted as valid
classifications.

## Why Tests Did Not Catch It

The N3 tests covered round hashes, resume integrity, seed separation, resource
records, and overwrite protection. They did not include:

- a calibrated null test proving identical distributions can pass patch-TV;
- a test proving a scientific-negative round prevents pilot success;
- a freeze test that inspects all five round scientific gates.

Passing workflow tests therefore did not validate the statistical semantics.

## Corrective Requirements

1. Use the same explicit excess patch-TV definition in N2 monitoring, N3
   monitoring, and N3 validation.
2. Persist observed, target-noise, and excess patch-TV components separately.
3. Derive each N3 round classification from correctness plus frozen training,
   validation, and objective gates.
4. Require five gate-passing rounds for an N3 success classification.
5. Make formal freeze independently reject any missing or failed round gate.
6. Add null-calibration and fail-closed regression tests.
7. Never overwrite the paths listed above. A corrected N3 run must use a new
   output directory and a new recorded code SHA-256.

## Interpretation Boundary

This incident proves a gate and classification implementation error. It does
not by itself prove an error in neural energy evaluation, local Metropolis
deltas, cache maintenance, BAR overlap, checkpoint serialization, or the
`U_next = -V_frozen` handoff. Those correctness gates passed in the preserved
artifacts and must remain independently tested after the correction.

## Remediation Applied

The local corrected implementation has code SHA-256
`cd7dc4f219e86644e330e3d9ddb3852f48d1e2de4948ffbbf434e0150de765f7`.
It is intentionally different from the invalid-run code hash recorded above.

Applied changes:

- centralized the excess patch-TV definition and used it in N2 monitoring,
  N2 validation, N3 monitoring, and N3 validation;
- persisted observed, target-noise, excess, and raw two-sample patch-TV values;
- made N3 round and chain classifications consume the actual scientific gates;
- made formal freeze revalidate every round instead of trusting a top-level
  success label;
- prebuilt N2 objective operator bases and packed incidence on the main thread
  before parallel sampling, after combined testing exposed an intermittent
  concurrent-construction segmentation fault;
- added null-calibration and fail-closed freeze regression tests.

Verification:

- affected gate/classification suite: `33 passed in 65.56s`;
- Issue 28 focused suite under `PYTHONMALLOC=debug` and faulthandler:
  `135 passed in 89.01s`;
- related legacy neural validation suite: `17 passed in 0.72s`;
- Python compilation and scoped `git diff --check`: PASS.
- fresh two-round smoke in `/tmp/issue28-n3-gatefix-smoke-20260730`: completed as
  `SCIENTIFIC_NEGATIVE`, reported zero passing scientific rounds, and persisted
  observed, target-noise, excess, and raw two-sample patch-TV components.

The corrected code was never injected into the old N3 process, so the preserved
code provenance remains unambiguous. The obsolete remote dependency chain was
cancelled before starting a corrected local run in a new output directory.

## Corrected Local Relaunch Incidents

The first corrected local launch exposed a separate concurrency defect. These
failed launches are retained and are not counted as N3 scientific rounds.

| Launch | Start | Terminal evidence | Last durable progress | Disposition |
|---|---|---|---|---|
| `results/issue28-n3-local-gatefix-20260730-01` | 2026-07-30 11:17:44 CST, PID 97916 | WSL kernel recorded `SIGSEGV` at 11:20:45 | round-1 temporary input only; no manifest | preserved, never resume |
| `results/issue28-n3-local-gatefix-3round-20260730-01` | 2026-07-30 11:23:12 CST, runner PID 98655, Python PID 98658 | faulthandler stack plus `background_exit status=139` at 11:25:56 | round 1 update 75/1000; crash while entering the update-100 monitor | preserved, never resume |

The second failure supplied a precise stack. `_OneRoundMonitor.__call__`
constructed new microscopic and block-spin `OperatorBasis` objects while the
eight-worker training executor still existed. The earlier remediation had
prebuilt the objective-sampling bases, but it had not covered the training
monitor. The later-round N3 monitor had the same latent pattern.

The additional correction:

- constructs the N2 monitor's microscopic and block-spin bases before the
  optimizer starts its worker pool;
- constructs the N3 monitor basis before the later-round worker pool starts;
- reuses those bases in every monitoring window;
- adds regression tests that reject any basis construction inside the monitor
  callback or N3 monitor sampling path;
- records background process exit status instead of allowing another silent
  native crash.

The post-correction package code SHA-256 is
`d87513c2b674a35510d22fc9d3b2e16fdafca419a4a4ac6fa0841727c4dd6b7e`.
The complete N2/N3 test modules passed under `PYTHONMALLOC=debug` and
faulthandler: `16 passed in 68.67s`. The full `tests/test_issue28_*.py`
file-level suite then passed under the same runtime diagnostics:
`103 passed in 92.15s`.

A fresh three-round pilot was started in
`results/issue28-n3-local-gatefix-3round-20260730-02` at 2026-07-30 11:33:35
CST with eight walker workers and all nested BLAS, OpenMP, and Numba thread
counts fixed to one. It passed the formerly crashing update-100 monitor and
reached update 150 by 11:37:01. Completion and scientific gate results remain
pending; operational survival is not a scientific pass.

## Deadline Stop And Final-Report Boundary

At user direction, the corrected local run is to stop immediately after the
round-2 manifest is atomically published so that the complete two-round result
can be submitted before the 2026-07-30 evening deadline. The stop is an
operational deadline decision, not a change to the frozen scientific contract.

Every final report must state explicitly that formal Issue 28 execution
requires at least five consecutive N3 rounds and that every round must pass its
training, frozen-validation, and objective gates. A two-round deadline result
is interim evidence only: it cannot be classified as formal N3 completion,
cannot freeze `config/issue28_formal_v1.json`, and cannot authorize N4 or N5.

## Deadline Run Terminal Audit

The deadline run did not reach the planned round-2 publication boundary. Its
durable state at the 2026-07-30 18:52 CST audit is:

- round 1 is complete and hash-verified as `SCIENTIFIC_NEGATIVE`; its manifest
  SHA-256 is
  `fe1c1f33a49efe48270931f2120ce1ba38c987ac6d2d54ac01c869ce4bd27639`;
- round 2 completed all 1000 training updates as `NOT_CONVERGED` and completed
  independent validation as `FAIL`;
- the round-2 objective calculation was still running at the last live-process
  observation at 18:27 CST;
- by 18:52 CST, both the N3 runner and its stop-after-round-2 watchdog had
  disappeared without writing their normal exit records; no round-2 manifest
  and no round-3 directory had been published.

The machine had not rebooted. Neither the N3 log nor the watchdog log contains
a Python exception, faulthandler dump, `background_exit`, publication event, or
watchdog stop event. The evidence therefore establishes an abrupt external
execution interruption between 18:27 and 18:52 CST, but it does not identify
the exact signal or authorize attributing the interruption to scientific code.
The retained staging directory is
`results/issue28-n3-local-gatefix-3round-20260730-02/.round-02.staging-s35vk6dj`.
Its key artifact SHA-256 values are:

- `training.json`:
  `e397b6fc6f4afd53ebdc2fd989cb0ca6bcb2b962b3139ee088c616a6293acefe`;
- `validation.json`:
  `7a15d12416f92913f15d00f022913d3925ce65b466d39d711a4c35bd1bc2a551`;
- `candidate_26.json`:
  `748b98314b68164cd43701e4758bf6f1cff808259816e1064ef0834c4aab0914`;
- `trajectory.npz`:
  `03705264b6afa50c962da48ffda63d997bab675bfbd887b228750c423c6ad78d`;
- `bias_model.npz`:
  `3df9a88fa160f38dffcc1ad2ff09030a61388e7b752e64d2bd637e4e21814960`.

The last round-2 training monitor recorded gradient norm `0.0733603`, operator
equivalence `0.194306`, and excess patch-TV `0.149214`. Frozen validation
recorded operator-equivalence upper bound `0.212841` and excess patch-TV upper
bound `0.238629`, both above their `0.02` thresholds, with mean acceptance
`0.661250`. These are valid provisional negative gate observations, but the
missing objective and manifest mean round 2 is `INTERRUPTED_UNPUBLISHED`, not a
completed scientific round.

Future deadline runs must use a supervisor whose lifetime is independent of
the interactive execution environment and must continue to use atomic manifest
publication as the sole completion signal. A staging directory, even when it
contains training and validation files, must never be counted as a completed
round. Formal Issue 28 execution still requires at least five consecutive,
fully published N3 rounds passing every scientific gate.
