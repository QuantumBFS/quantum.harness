# Route D+ Phase 1 scheduler feasibility evidence

Date: 2026-07-29

## Exact request

The remote Slurm feasibility check used `sbatch --test-only` with:

- partition `xhhgnormal`;
- one node;
- 2 CPU;
- 6 GiB memory;
- 15-minute wall time;
- GRES `gpu:NVIDIAGeForceRTX3080:1`;
- the profile-neutral Route D+ `phase1.sbatch` entrypoint.

`--test-only` performs scheduler feasibility analysis and does not create or
run a job.

## Scheduler response

Slurm accepted feasibility identifier `23005318` and reported:

```text
Job 23005318 to start at 2027-11-13T10:40:50 using 2 processors on nodes
e12r04 in partition xhhgnormal
```

This response establishes that the earlier `AssocGrpSubmitJobsLimit`
rejection was not active at the time of this check. It does not establish that
a real submission would start soon, because the estimated start is more than
one year away. No real validation job was submitted.

## Consequence

The installed environment remains unvalidated on a GPU compute node. Before a
real job is left queued, choose among waiting on `xhhgnormal`, checking a
compatible alternate GPU partition, or stopping until scheduling conditions
change.
