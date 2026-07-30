#!/usr/bin/env bash
#SBATCH --job-name=tfim-ext-min
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --array=1-14%8
#SBATCH --output=extremes-min-%A_%a.log

set -euo pipefail

export SIZE_ROLE=min
export HARNESS_RUN_SPEC="tracks/qmc/results/Only-team/challenge-extremes-min-20260729/run_spec.json"

exec "$SLURM_SUBMIT_DIR/tracks/qmc/solutions/Only-team/scripts/run_extreme_scan_cell.sh"
