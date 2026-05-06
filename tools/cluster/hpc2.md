# HPC2 Cluster Profile

## Identity

HPC2 — HKUST(GZ) institutional Slurm cluster. CPU-heavy stack with a small GPU annex. Used by the harness for `(L, parameter)` grid sweeps in DMRG / TTN / Pauli-Markov workflows. ITensors.jl is CPU-only; the harness's validation paper (magic-paper reproduction) does not require GPU resources.

Cluster admin contact and login URL are in the user's institution onboarding docs; this card stays cluster-agnostic about credentials.

## Account

- Default account: `hzhou361` (the user's institutional account). Works without an explicit `--account` / `-A` flag — Slurm picks the user's default automatically.
- No project / billing code required for the partitions the harness uses.

When running a skill that constructs a sbatch script, *do not* emit `#SBATCH --account=` unless the user asks — the empty-account default is correct.

## Partitions

| Name | Cores / node | Memory | Max wall | GPU | Tag | Notes |
|---|---|---|---|---|---|---|
| `i64m512u` | 64 | 512 GB | 7 days | — | **default-cpu** | Standard CPU partition; harness default. |
| `i96m3tu` | 96 | 3 TB | 7 days | — | high-memory | For large-MPS / large-`χ` workloads needing >512 GB. |
| `a128m512u` | 128 | 512 GB | 7 days | — | high-core | Single-node parallelism beyond 64 cores. |
| `debug` | varies | varies | 30 min | — | debug | Quick test runs; auto-routed for `< 30 min` jobs. |
| `long_cpu` | varies | varies | 14 days | — | long | Multi-week sweeps. |
| `i64m1tga800u` | 64 | 1 TB | 7 days | a800 ×8 | gpu | For workloads requiring NVIDIA A800; harness's ITensors.jl stack does not need this. |
| `i64m1tga40u` | 64 | 1 TB | 7 days | a40 ×8 | gpu | NVIDIA A40 alternative. |

The harness picks `i64m512u` for any CPU job by default. Override via the `partition:` field of a `/slurm-grid` invocation when the run profile demands more memory or cores.

## Sbatch idioms

### Single-cell job

```bash
#!/bin/bash
#SBATCH --job-name=<name>
#SBATCH --partition=i64m512u
#SBATCH --time=1-00:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --output=results/<run>/cells/<cell_id>/slurm-%j.out

module load julia/1.10.9
cd $SLURM_SUBMIT_DIR
julia --project=julia-env <script>.jl
```

Default time `1-00:00:00` (1 day) is the harness convention for entry-level grid cells. Bump for explicit long-runs.

### Array job (parameter grid)

```bash
#!/bin/bash
#SBATCH --job-name=<name>-grid
#SBATCH --partition=i64m512u
#SBATCH --time=1-00:00:00
#SBATCH --array=1-<N_cells>
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --output=results/<run>/cells/cell-%a/slurm-%A_%a.out

module load julia/1.10.9
cd $SLURM_SUBMIT_DIR

CELL_ID=$(printf "%03d" $SLURM_ARRAY_TASK_ID)
julia --project=julia-env scripts/run-cell.jl --cell $CELL_ID --plan results/<run>/grid.plan.json
```

Array idiom: `#SBATCH --array=N-M` with `$SLURM_ARRAY_TASK_ID` as the cell index inside each task. The `/slurm-grid` skill emits exactly this shape.

## Status / queue commands

| Purpose | Command |
|---|---|
| List my queued / running jobs | `squeue -u $USER` |
| Show partition state and capacity | `spartition` (HPC2-flavored alias for `sinfo` summary) |
| Show one job's full state | `scontrol show job <jobid>` |
| Accounting / completed jobs | `sacct -u $USER --starttime=now-1day` |
| Show partition definitions | `scontrol show partition` |

`spartition` is the HPC2-local convenience wrapper that reports partition utilization in a one-screen format. `squeue`, `sacct`, and `scontrol` are stock Slurm.

## Environment setup

Module loads (added at the top of every harness-emitted sbatch script):

```bash
module load julia/1.10.9
# Optional, when MPI is needed (DMRG-cylinder parallelism, etc.):
# module load gcc-13.1.0 openmpi-4.1.6   # or mpich-4.3.2
```

Available modules (verified):

- `julia/1.10.9` — default Julia version. Matches the version expected by `make install julia` against the harness's `Project.toml`.
- `gcc-13.1.0` — C compiler for any native build steps.
- `openmpi-4.1.6` and `mpich-4.3.2` — MPI implementations; pick `openmpi` unless the user has a reason for `mpich`.

Julia depot setup (one-time, on first login):

```bash
mkdir -p $HOME/.julia
# Optional: redirect depot to home if /tmp is small
export JULIA_DEPOT_PATH="$HOME/.julia"
```

The harness's `julia-env/` directory (created by `make install itensors`) is project-local and travels with the repo; no cluster-side setup needed beyond having Julia on `$PATH` via the module.

## Filesystem

| Path | Purpose | Notes |
|---|---|---|
| `/hpc2hdd/home/<user>` | Home directory | Standard read/write. The user's checkout of the harness lives here. |
| (none) | Scratch | HPC2 has *no* `/scratch` partition — all workloads run out of `$HOME`. The harness should not assume a scratch directory exists. |
| Project shared space | Group `jinguoliu_team` | Filesystem path is institution-local; consult cluster docs. |

The lack of `/scratch` means large run outputs (multi-GB tensor files, long Markov chains) live under `$HOME` — keep an eye on quota. Use `du -sh results/<run>` periodically and offload completed runs to long-term storage outside `$HOME` if needed.

## Notes

- ITensors.jl is *CPU only* in the harness's stack — no GPU partition needed for the magic-paper reproduction. Do not auto-route to the GPU partitions.
- Group ownership: `jinguoliu_team`. Files created by harness skills inherit this group; no extra `chgrp` needed.
- Network egress is generally available (e.g., `arxiv-search` and `download-ref` work from compute nodes), but compute nodes may not see public DNS for some hosts — fetch references on the login node before submitting if possible.
- Default `--time=1-00:00:00` is conservative; the harness's `/slurm-grid` will bump if a method-card runtime estimate exceeds 1 day.
- HPC2-specific facts (account name, partition list, `spartition` alias, module versions, filesystem layout) live ONLY in this card. Skills consult `tools/cluster/active.md` (or the env var) and never bake HPC2 specifics into their workflow text.
