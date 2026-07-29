#!/bin/bash
#SBATCH --job-name=born-critical-stage4-xcheck
#SBATCH --output=/tmp/born-critical-stage4-xcheck-%j.out
#SBATCH --error=/tmp/born-critical-stage4-xcheck-%j.err
#SBATCH --chdir=/tmp

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
source_path="/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical-122"
result_path="/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage4-crosschecks"
stage2_metrics="/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage2-clean-ising/job-17178/metrics.json"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work="$(mktemp -d "/tmp/born-critical-stage4-xcheck-${job_id}-XXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/source" "$work/output"
rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${source_path}/" "$work/source/"
rsync -a "${ws0_host}:${stage2_metrics}" "$work/stage2-metrics.json"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$work/source"
PYTHONPATH=src python -u scripts/run_stage4_crosschecks.py \
    --output "$work/output/job-${job_id}" \
    --stage2-metrics "$work/stage2-metrics.json"
rsync -a "$work/output/" "${ws0_host}:${result_path}/"
