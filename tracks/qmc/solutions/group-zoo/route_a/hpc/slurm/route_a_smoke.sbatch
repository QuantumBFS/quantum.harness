#!/usr/bin/env bash
#SBATCH --account=giggleliu
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:20:00
#SBATCH --mem=4G

set -euo pipefail
: "${RELEASE:?RELEASE is required}"
export LC_ALL=C
export SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID:-0}
exec bash "$RELEASE/project/hpc/slurm/route_a_array.sbatch"
