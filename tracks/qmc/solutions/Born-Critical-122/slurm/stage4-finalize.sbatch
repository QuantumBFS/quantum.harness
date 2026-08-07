#!/bin/bash
#SBATCH --job-name=born-critical-stage4-finalize
#SBATCH --output=/tmp/born-critical-stage4-finalize-%j.out
#SBATCH --error=/tmp/born-critical-stage4-finalize-%j.err
#SBATCH --chdir=/tmp

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
source_path="/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical-122"
result_root="/home/ystu/quantum.harness/tracks/qmc/results/born-critical"
regression_job="${STAGE4_REGRESSION_JOB:?STAGE4_REGRESSION_JOB is required}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work="$(mktemp -d "/tmp/born-critical-stage4-finalize-${job_id}-XXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/source" "$work/input"
rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${source_path}/" "$work/source/"
rsync -a "${ws0_host}:${result_root}/selfdual-production-v1/aggregate/metrics.json" \
    "$work/input/production.json"
rsync -a "${ws0_host}:${result_root}/stage4-crosschecks/job-17613/metrics.json" \
    "$work/input/crosschecks.json"
rsync -a "${ws0_host}:${result_root}/stage4a-tests/job-${regression_job}/manifest.json" \
    "$work/input/regression.json"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
cd "$work/source"
PYTHONPATH=src python -u scripts/finalize_stage4.py \
    --production "$work/input/production.json" \
    --crosschecks "$work/input/crosschecks.json" \
    --regression "$work/input/regression.json" \
    --output "$work/stage4-acceptance.json"
rsync -a "$work/stage4-acceptance.json" \
    "${ws0_host}:${result_root}/stage4-acceptance.json"
