# Route D+ Phase 1 job 23005815 submission

Date: 2026-07-29

## Identity

- Job ID: `23005815`
- Job name: `route-d-plus-phase1-loader`
- Account: `giggleliu`
- QOS: `user_jiabohan5`
- Remote commit: `182fe7742241ee2b8a1aad0bb019725a6b700c94`
- Run ID: `route-d-plus-phase1-20260729-06`
- Entrypoint:
  `tracks/qmc/solutions/BOTS-848/route_d_plus/environment/phase1.sbatch`

## Ratified resources

- Partition: `xhhgnormal01`
- GRES: `gpu:NVIDIAGeForceRTX3090:1`
- Nodes: 1
- CPU: 2
- Memory: 6 GiB
- Wall time: 15 minutes

The `scontrol show job -dd` snapshot reported:

```text
JobState=PENDING Reason=Priority
SubmitTime=2026-07-29T17:40:47
StartTime=2026-07-29T20:21:53
SchedNodeList=c05r05
TRES=cpu=2,mem=6G,node=1,billing=2,gres/gpu=1
TresPerNode=gres:gpu:NVIDIAGeForceRTX3090:1
```

This pending snapshot is submission evidence only. It is not evidence that the
job ran or that Phase 1 passed.

## Runtime correction

The job prepends the following to `LD_LIBRARY_PATH`:

1. `/work/home/jiabohan5/.cache/route-d-plus/runtime-libs`
2. the installed CUDA 12 wheel library directories below
   `.venv/lib/python3.11/site-packages/nvidia/`:
   `cuda_cupti`, `cufft`, `cudnn`, `cusolver`, `nvjitlink`, `nccl`,
   `cuda_runtime`, `cublas`, and `cusparse`.

The compatibility directory contains `libstdc++.so.6.0.29`, pinned by
SHA-256:

```text
4f045231ff3a95c2fbfde450575f0ef45d23e95be15193c8729b521fc363ece4
```

The submission exports:

```text
ROUTE_D_PLUS_REPO_ROOT=/work/home/jiabohan5/quantum.harness-collab
JAX_PROFILE=cuda12
ROUTE_D_PLUS_RUN_ID=route-d-plus-phase1-20260729-06
```

## Evidence paths

- Standard output:
  `tracks/qmc/results/route-d-plus-phase1-20260729-06-loader-retry-slurm-23005815.out`
- Standard error:
  `tracks/qmc/results/route-d-plus-phase1-20260729-06-loader-retry-slurm-23005815.err`
- Expected manifest:
  `tracks/qmc/results/route-d-plus-phase1-20260729-06/environment-manifest.json`
- Installed lock:
  `tracks/qmc/results/route-d-plus-phase1-20260729-06/requirements-lock.txt`
