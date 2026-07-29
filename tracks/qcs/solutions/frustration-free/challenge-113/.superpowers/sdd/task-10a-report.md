# Task 10A report: measured production gate

## Status

Task 10A adds deterministic restartable sweep shards, guarded local runners,
Slurm pilot/array entry points, a representative calibration tool, and initial
operator/scientific documentation. Preferred and fallback SSH aliases both
passed read-only Slurm access checks; `xhacnormalb` on the preferred cluster was
selected for the CPU pilot.

The broad 9,500-trial array is not yet submitted. It remains gated on strict
completion of the full remote pilot and on the discovered seed-coverage
concern: the mandatory two-qubit open-loop acceptance fails for seed 0, which
is present in the canonical production plan.

## Local evidence

- Frozen sync: successful.
- Full suite before final commit: 385 tests passed; final post-fix verification
  is recorded with the commit.
- Shell and Python syntax checks: successful.
- Development sweep: 84/84 complete, strict validation valid, 175.0 s wall,
  926,300 KiB peak RSS, 1,710,921 bytes.
- Representative p=80 calibration: 0.212 s compilation-inclusive first query,
  525 warm queries/s, 7.65 s open-loop, 5.83 s landscape, 0.0382 s exact
  trajectory for 20 queries, 1.62 s geometry, 0.347 s restricted optimization,
  848,664 KiB peak RSS, JAX CPU/x64.
- Preliminary projection: 23.3 s/trial, 61.5 trial-hours or 492 core-hours at
  eight cores/trial, and approximately 1.9 GB. The remote full pilot supersedes
  these preliminary estimates.

## Cluster deployment

Deployment is an exact archive of the clean Task 10 commit plus `uv.lock`, with
the revision recorded in `.source-revision` and the archive SHA256 recorded
alongside the immutable revision directory. Runtime output uses a separate
revision/run-ID directory. Absolute host paths and credentials are not stored
in the repository.

Remote revision, archive digest, pilot job ID/state, strict validation result,
and any production array job ID are appended after clean commit and submission.

## Concerns

1. A failed first development attempt exposed that full-space trials requested
   an invalid `leading_count == parameter_count`. A regression now keeps the
   full-space landscape request at the physical `d² - 1` count.
2. Two-qubit seed 0 fails the existing hard open-loop acceptance threshold.
   The accepted representative seed 5 is used for calibration and pilot, but
   this does not establish feasibility for every production seed.
3. Cluster login nodes do not provide a default Python 3 executable. Deployment
   must use the existing shared CPython 3.12 runtime with a frozen uv sync; the
   Slurm scripts require the uv executable path explicitly and never fall back.
