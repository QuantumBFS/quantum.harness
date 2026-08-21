#!/bin/bash
#SBATCH --job-name=qh86-calibration
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=00:30:00

set -euo pipefail

threads="${SLURM_CPUS_PER_TASK:?SLURM_CPUS_PER_TASK is required}"
case "$threads" in
  4|8) ;;
  *)
    echo "calibration requires exactly 4 or 8 allocated CPUs; got $threads" >&2
    exit 2
    ;;
esac

run_directory="tracks/mps/results/issue-86-calibration-${threads}t"
export HARNESS_RUN_SPEC="$run_directory/run_spec.json"
export ISSUE86_OUTPUT_DIR="$run_directory"
export ISSUE86_STAGE="calibration"
export RESOURCE_CLASS="A"
export ISSUE86_WORKERS="1"
export ISSUE86_CORES_PER_WORKER="$threads"

exec bash tracks/mps/solutions/issue-86/run_full.sbatch
