#!/usr/bin/env bash
#SBATCH --account=giggleliu
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=04:00:00
#SBATCH --mem=16G

set -euo pipefail
: "${RELEASE:?RELEASE is required}"
export LC_ALL=C
unset STOP_AFTER_BINS
exec bash "$RELEASE/project/hpc/slurm/route_a_array.sbatch"
