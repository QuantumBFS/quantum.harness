# Route D+ Phase 1 progress evidence

Date: 2026-07-29

## Scope

This incremental evidence supplements, without modifying, the pinned AITP
import source in `aitp-2-migration-handoff.md`. It records environment
installation and scheduler state only. It does not establish a successful
GPU validation or any physics result.

## Offline environment installation

- Remote repository:
  `/work/home/jiabohan5/quantum.harness-collab`
- Remote validation commit:
  `182fe7742241ee2b8a1aad0bb019725a6b700c94`
- Login-node import-only inspection:
  - JAX 0.4.38
  - NumPy 2.0.2
  - SciPy 1.16.3
  - Optax 0.2.4
  - `pywigxjpf` 1.13.3
  - CFFI 2.0.0
- Installed lock:
  `tracks/qmc/results/route-d-plus-phase1-20260729-06/requirements-lock.txt`
- Lock SHA-256:
  `f77cad4f76b1b086c06a2953a448e1d48e230205a74da561b12d019fde86589c`

The evidence above establishes that the offline Python environment was
installed. It does not show JAX x64 mode, GPU visibility, CUDA device
selection, or the complete Phase 1 environment manifest.

## Scheduler-capacity blocker

The corrected Phase 1 validation submission requested 2 CPU, 6 GiB, 15
minutes, and one RTX 3080. Slurm rejected it before assigning a job ID because
account `giggleliu` had reached `AssocGrpSubmitJobsLimit` with 200 submitted
jobs. This is a scheduler-capacity blocker, not an environment or physics
failure.

A later read-only `squeue` check returned no jobs owned by `jiabohan5`.
Account-wide jobs were not visible, so this observation does not establish
that the association limit has cleared. The next action is to retry the same
validation submission, then preserve its job ID, manifest, lock digest, and
scheduler logs.
