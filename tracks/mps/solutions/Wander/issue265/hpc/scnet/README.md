# SCNet xh5 execution

This directory contains the Slurm entry points used on the SCNet xh5
`xhacnormalb` partition.  All code, environments, logs, checkpoints, and raw
datasets live below the team-quota path
`/work/share/giggleliu/cfys01/kharkov_burgers_20260729`.

The personal home directory is intentionally not used for job output or
package caches.

`preflight.sbatch` runs the registered FCS condition on a tiny grid and records
GNU `time -v` diagnostics.  `coarse_t2_resource_pilot.sbatch` retains the
registered coarse spatial/tensor resolution but shortens the physical time to
measure realistic early-time cost.  `run_convergence.sbatch` is the common
entry point for the twelve registered convergence jobs; the submitter supplies
`KH_JOB_ID`, CPU count, memory, wall time, and log paths on the `sbatch`
command line after the pilot measurements are accepted.

`j2_preflight.sbatch` is the compute-node evidence gate for the grouped
\(J_1\)-\(J_2\) purification backend.  In one fail-fast job it runs both
\(J_2=0.1\) wall directions, dense exact-evolution comparisons, paired
spin-flip/continuity/FCS checks, the \(J_2=0\) grouped-versus-ordinary
equivalence check, and a grouped-checkpoint reload.  Local exact-version
artifacts are mirrored under `data/preflight/j2_local_validation`; the
machine-readable gate is
`results_research_program/hpc/j2_validation_20260730.json`.

The first SCNet submission attempt was rejected before Slurm created a job
because the `giggleliu` association had reached `AssocGrpSubmitJobsLimit`
(200/200).  A rejection is recorded in `jobs/j2_preflight_attempt.json` with a
six-hour `retry_not_before` backoff.  Only a real accepted submission may
create `jobs/j2_preflight_submission.json`.  Monitoring must not infer
association capacity from the visible `squeue -A giggleliu` count, must not
submit again before the recorded time, and must never duplicate a job once the
success record exists.

Convergence slices checkpoint every ten saved output intervals, corresponding
to two physical time units on the registered output grid.  This bounds lost
work if a seven-day Slurm slice ends during the high-entanglement regime.

The offline environment lock is in `requirements.lock.txt`.  The cluster's
Anaconda module supplies NumPy, SciPy, and h5py; only the compatible TeNPy
wheel is installed into the shared virtual environment.

`submit_convergence.py` enforces the completed-pilot gate, checks that the
manifest contains exactly twelve convergence jobs, submits each one once, and
atomically records every Slurm ID in the team directory.  Its resource table
distinguishes FCS jobs from single-branch jobs and stays within the partition's
per-node CPU/memory limits.

`continuation_controller.sbatch` and `continue_convergence.py` form the
checkpoint continuation gate.  A controller is submitted with an `afterany`
dependency on the current twelve-job slice.  It automatically resumes only
`TIMEOUT`, `OUT_OF_MEMORY`, `NODE_FAIL`, `PREEMPTED`, or `BOOT_FAIL` outcomes;
OOM retries increase CPU/memory together within xh5 node limits.  Code
failures, manual cancellations, missing checkpoints, and exhausted retry
limits stop for inspection instead of looping.  When all twelve datasets are
complete, the controller rewrites only the manifest paths for the team
filesystem and runs the frozen convergence audit with `--require-accepted`.

The two gates are independent.  Passing the J2 preflight changes the
production-A bundle from 29 ready / 2 J2-blocked to 31 ready / 0 J2-blocked,
but it does not authorize production A until the twelve formal convergence
datasets have also passed the frozen audit.  Production B remains locked until
production A is complete and the one-time unblinding step is explicitly run.

`production_v2_preflight.sbatch` is the compute-node gate for the approved
tiered two-mode/FCS amendment.  It uses the isolated production wrapper to run
the exact uniform \(m=0\) equilibrium state and the matched positive/negative
Gaussian pulses, checks equilibrium null observables, transfer-FCS conjugacy,
pulse spin flip, checkpoint reload, manifest counts, source closure, and the
independent J2 evidence.  A successful runtime writes
`results_research_program/hpc/production_v2_validation_20260730.json` with
status `pass`.  Its local status is only `local_pass_cluster_pending`.

The production-v2 bundle is a pure builder.  Its current execution matrix has
68 logical rows, 0 ready rows, 2 unaccepted reuse rows, and
`submission_performed=false`.  Do not submit its compute preflight until both
the frozen convergence audit is `accepted` and the J2 compute-node evidence is
`pass`; do not execute `submit_ready.sh` merely because it exists.

## Production-B v1.2 operator sequence

Production B is not an automatic continuation of Production A. Protocol v1.2
allows the independent long-window stage only if the frozen validation status
is one of:

- `scalar_surrogate_not_rejected`;
- `independent_two_burgers_supported`;
- `coupled_two_mode_supported`.

`memory_or_more_modes_required` and every unresolved or inconsistent state
stop. The registered operator sequence is:

```bash
python hpc/scnet/submit_two_mode_analysis.py --team-root "$TEAM_ROOT" --resume
python scripts/unblind_research_test.py --team-root "$TEAM_ROOT"
python scripts/unblind_research_test.py --team-root "$TEAM_ROOT" --confirm-unblind
python hpc/scnet/submit_production_b.py --team-root "$TEAM_ROOT"
python hpc/scnet/submit_production_b.py --team-root "$TEAM_ROOT" --submit
python hpc/scnet/submit_production_b.py --team-root "$TEAM_ROOT" --resume
```

The first unblinding command deliberately refuses: it previews the human
boundary and must not create a record. Run the confirmed command only after
reviewing the frozen selection. The Production-B command is also a dry run
unless `--submit` or `--resume` is explicitly present. It must report exactly
34 execute rows, 3 FCS rows, and 0 Production-A scripts.

The authoritative records are `jobs/unblinding.json` and
`jobs/production_b_submission.json`. Never delete or overwrite either to
force progress. `TIMEOUT`, `NODE_FAIL`, `PREEMPTED`, and `BOOT_FAIL` may resume
only from a nonempty checkpoint; `OUT_OF_MEMORY` may use the registered
CPU/memory escalation. Code failures, cancellations, invalid completed
outputs, and interrupted external-submission intents require manual
reconciliation.
