#!/bin/bash
#SBATCH --job-name=ole-c512-s1
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=256G
#SBATCH --time=01:00:00
#SBATCH --output=/home/zyli/quantum.harness/tracks/qcs/solutions/CCB-LV.999/issue-119-ole/slurm/%x-%j.out
#SBATCH --error=/home/zyli/quantum.harness/tracks/qcs/solutions/CCB-LV.999/issue-119-ole/slurm/%x-%j.out

set -euo pipefail

readonly OLE_ROOT="/home/zyli/quantum.harness/tracks/qcs/solutions/CCB-LV.999/issue-119-ole"
readonly JULIA_BIN="/home/zyli/.juliaup/bin/julia"

export JULIA_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=16
export OMP_NUM_THREADS=16

cd "$OLE_ROOT"

printf 'host=%s job_id=%s cpus=%s start=%s\n' \
    "$(hostname)" "${SLURM_JOB_ID:-unknown}" "${SLURM_CPUS_PER_TASK:-unknown}" \
    "$(date --iso-8601=seconds)"

/usr/bin/time -v "$JULIA_BIN" --project=. scripts/run_bp.jl \
    --seed 1 \
    --chi 512 \
    --delta 0.15 \
    --execute \
    --confirm 0a7122006cfc2ef0

printf 'finish=%s\n' "$(date --iso-8601=seconds)"
