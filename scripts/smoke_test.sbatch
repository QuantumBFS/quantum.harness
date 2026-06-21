#!/bin/bash
#SBATCH --job-name=harness-smoke
#SBATCH --output=results/smoke/smoke-%j.out
# Minimal end-to-end smoke test for the cluster pipeline: prove ship -> submit
# -> run -> fetch works. Writes a one-line manifest into results/smoke/.
set -euo pipefail
mkdir -p results/smoke
echo "host=$(hostname)"
echo "date=$(date -Is)"
echo "cpus=$(nproc)"
echo "cwd=$(pwd)"
printf '{"host":"%s","slurm_job_id":"%s","cpus":%s,"status":"ok"}\n' \
  "$(hostname)" "${SLURM_JOB_ID:-NA}" "$(nproc)" > results/smoke/manifest.json
echo "smoke OK"
