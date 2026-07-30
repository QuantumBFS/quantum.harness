# Route D+ Phase 1 GPU partition comparison

Date: 2026-07-29

## Scope

Three `sbatch --test-only` checks compared the same Phase 1 request across the
GPU partitions recorded in the active private cluster profile. These checks
did not create or run real jobs.

Each request used one node, 2 CPU, 6 GiB memory, a 15-minute wall time, one
partition-specific GPU, and the Route D+ `phase1.sbatch` entrypoint.

## Scheduler estimates

| Partition | Accelerator | Test-only identifier | Estimated start |
| --- | --- | --- | --- |
| `xhhgnormal` | RTX 3080 | `23005318` | `2027-11-13T10:40:50` |
| `xhhgnormal01` | RTX 3090 | `23005384` | `2026-07-29T17:06:14` |
| `xhhgnormal02` | V100 16 GiB | `23005385` | `2026-09-15T07:57:21` |

The RTX 3090 partition is the only operationally reasonable candidate from
this comparison. The estimate is scheduler state, not scientific evidence,
and does not guarantee actual dispatch time.

## Guardrail limitation

The local Slurm helper calls `python3`, which is Python 3.10 on the development
host. Its TOML parser imports the Python 3.11 standard-library module
`tomllib`, so the local profile/script guardrail emitted
`ModuleNotFoundError: tomllib` during these checks. The helper still sent the
explicit partition, memory, CPU, wall-time, and GRES flags to remote Slurm, so
the returned scheduling estimates correspond to the intended requests.

Before a real submission, run the helper with `python3` resolved to the
available Python 3.11 interpreter and repeat the exact RTX 3090 feasibility
check. A real job must not be submitted unless that guarded check passes.

## Compatibility boundary

The installed JAX environment uses the CUDA 12 profile. RTX 3090 is selected
only as a scheduler candidate here; driver visibility, CUDA initialization,
JAX x64 mode, and device selection remain part of the Phase 1 compute-node
manifest gate.
