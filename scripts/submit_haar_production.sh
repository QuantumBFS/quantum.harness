#!/bin/bash
set -euo pipefail

project_root="${1:-/home/jhzhu/quantum.harness-haar}"
cd "$project_root"

run_id="haar-mipt-production-20260730"
run_spec="results/${run_id}/run_spec.json"
mkdir -p "results/${run_id}"

export PYTHONPATH="$project_root/.python-packages${PYTHONPATH:+:$PYTHONPATH}"

sbatch --parsable \
  --job-name=haar-mipt \
  --partition=batch \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=1 \
  --mem=2G \
  --time=06:00:00 \
  --array=1-300%100 \
  --output="results/${run_id}/slurm-%A_%a.out" \
  --export="ALL,HARNESS_RUN_SPEC=${run_spec},HARNESS_ENTRYPOINT=scripts/haar_mipt_slurm_cell.py,HARNESS_RUNNER=python3,PYTHONPATH=${PYTHONPATH}" \
  scripts/harness_array_sbatch.sh
