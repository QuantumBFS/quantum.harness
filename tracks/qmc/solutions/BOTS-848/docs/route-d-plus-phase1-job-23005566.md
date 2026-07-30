# Route D+ Phase 1 job 23005566

Date: 2026-07-29

## Submission

- Job ID: `23005566`
- Partition: `xhhgnormal01`
- Accelerator request: `gpu:NVIDIAGeForceRTX3090:1`
- Resources: one node, 2 CPU, 6 GiB, 15 minutes
- Remote commit: `182fe7742241ee2b8a1aad0bb019725a6b700c94`
- Submitted run ID: `route-d-plus-phase1-20260729-07`

## Scheduler outcome

`sacct` reported:

```text
State=FAILED
ExitCode=2:0
Elapsed=00:00:02
NodeList=c05r05
MaxRSS=2724K
```

The standard output was empty. Standard error ended with:

```text
validated dependency lock does not exist under
/work/home/jiabohan5/quantum.harness-collab/tracks/qmc/results/route-d-plus-phase1-20260729-07
```

No run directory or environment manifest was created for
`route-d-plus-phase1-20260729-07`.

## Diagnosis

The offline installation and dependency lock belong to the existing Phase 1
run `route-d-plus-phase1-20260729-06`. Validation mode intentionally reads
`requirements-lock.txt` from the selected run directory. Submitting a new
`-07` run ID therefore pointed validation at a nonexistent lock.

This was an operator run-ID mismatch, not an environment, GPU, CUDA, JAX, or
physics failure. The entrypoint exited before JAX or project computation ran.
No source-code change is required.

## Corrected retry

Reuse `ROUTE_D_PLUS_RUN_ID=route-d-plus-phase1-20260729-06` so the compute-node
validation consumes the installed lock and writes the manifest beside it.
Keep the ratified RTX 3090 resources unchanged and assign a new Slurm job ID.
