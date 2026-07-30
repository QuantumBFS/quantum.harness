#!/usr/bin/env bash
#SBATCH --job-name=tfim-hon-recovery
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=10:00:00
#SBATCH --array=1-8%8
#SBATCH --output=precision-hon-bundle-%A_%a.log

set -euo pipefail

export HARNESS_RUN_SPEC="tracks/qmc/results/Only-team/challenge-precision-recovery-honeycomb-20260729/run_spec.json"

exec "$SLURM_SUBMIT_DIR/tracks/qmc/solutions/Only-team/scripts/run_precision_recovery_bundle.sh"
