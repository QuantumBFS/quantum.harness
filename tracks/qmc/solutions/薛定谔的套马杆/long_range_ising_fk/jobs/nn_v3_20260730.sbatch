#!/bin/bash
#SBATCH --job-name=nn_v3
#SBATCH --partition=xhacnormalb
#SBATCH --array=1-24
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=results/nn_v3_20260730/logs/%A_%a.out
#SBATCH --error=results/nn_v3_20260730/logs/%A_%a.err

set -euo pipefail

cd "$HOME/quantum.harness/tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk"
mkdir -p results/nn_v3_20260730/logs

sizes=(64 128 256)
cell=$((SLURM_ARRAY_TASK_ID - 1))
size_index=$((cell / 8))
replica=$((cell % 8 + 1))
L=${sizes[$size_index]}
seed=$((930000 + 1000 * L + replica))
outdir=$(printf "results/nn_v3_20260730/cells/%03d" "$SLURM_ARRAY_TASK_ID")

julia --project=. scripts/nn_v3_point.jl "$L" "$seed" 20000 1000000 "$outdir"
