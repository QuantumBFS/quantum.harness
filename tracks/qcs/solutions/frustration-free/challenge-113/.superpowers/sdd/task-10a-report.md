# Task 10A report: measured production gate

## Status

Task 10A adds deterministic restartable sweep shards, guarded local runners,
Slurm pilot/array entry points, a representative calibration tool, and initial
operator/scientific documentation. Preferred and fallback SSH aliases both
passed read-only Slurm access checks; `xhacnormalb` on the preferred cluster was
selected for the CPU pilot.

The broad 9,500-trial array is not submitted. The full local representative
pilot passed, but the exact frozen runtime is incompatible with both authorized
clusters and the discovered seed-coverage concern remains: mandatory
two-qubit open-loop acceptance fails for seed 0, which is present in the
canonical production plan.

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
  eight cores/trial, and approximately 1.9 GB. The full local pilot supersedes
  these preliminary estimates.
- Full representative pilot: 929 exact queries, 19.12 s wall, 860,224 KiB peak
  RSS, 551,237-byte canonical trial artifact, strict validation valid.
- Full-pilot projection: 50.5 trial-hours, approximately 404 core-hours at eight
  cores/trial, and 5.24 GB. Selected class: 8 CPU cores, 24 GiB, 12-hour limit,
  concurrency 32.

## Cluster deployment

The first clean Task 10 revision was deployed as an exact archive, with
revision `5dc1ceb5cad54e3840d606761feb8770842d1fb5` and archive SHA256
`8db29d3b421254933570da43d1cc27bdc093ffaab272a5441f0296c1a9dda5fc`.
The remote archive hash matched before extraction. Runtime output is configured
for a separate revision/run-ID directory; absolute host paths and credentials
are not stored in the repository.

No Slurm pilot or array job ID exists. Frozen sync stopped before submission:
both the preferred and fallback clusters expose glibc 2.17, but locked
`jaxlib==0.11.0` provides x86-64 wheels requiring manylinux 2.27. The final
array manifest selects 32-way concurrency but records submission as blocked.

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
4. The shared CPython runtime does not solve the glibc ABI mismatch. Neither
   authorized cluster advertises Apptainer/Singularity, so an exact locked
   execution environment is unavailable without an explicit environment
   decision outside Task 10A.
