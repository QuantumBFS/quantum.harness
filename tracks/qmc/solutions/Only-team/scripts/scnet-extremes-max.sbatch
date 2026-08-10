#!/usr/bin/env bash
#SBATCH --job-name=tfim-ext-max
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --array=1-14%8
#SBATCH --output=extremes-max-%A_%a.log

set -euo pipefail

export SIZE_ROLE=max
export HARNESS_RUN_SPEC="tracks/qmc/results/Only-team/challenge-extremes-max-20260729/run_spec.json"

exec "$SLURM_SUBMIT_DIR/tracks/qmc/solutions/Only-team/scripts/run_extreme_scan_cell.sh"
