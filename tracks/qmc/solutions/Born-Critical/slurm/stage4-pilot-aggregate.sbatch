#!/bin/bash
#SBATCH --job-name=born-critical-s4-aggregate
#SBATCH --output=/tmp/born-critical-s4-aggregate-%j.out
#SBATCH --error=/tmp/born-critical-s4-aggregate-%j.err
#SBATCH --chdir=/tmp
set -euo pipefail
ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
source_path="/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical"
run_path="${BORN_CRITICAL_RUN_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/selfdual-pilot-v1}"
job_id="${SLURM_JOB_ID:?}"
work="${TMPDIR:-/tmp}/born-critical/s4-aggregate-${job_id}"
mkdir -p "$work/source" "$work/run"
rsync -a --exclude '__pycache__/' "${ws0_host}:${source_path}/" "$work/source/"
rsync -a "${ws0_host}:${run_path}/" "$work/run/"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
cd "$work/source"
set +e
PYTHONPATH=src python -u scripts/aggregate_selfdual_pilot.py --run "$work/run"
code=$?
set -e
rsync -a "$work/run/aggregate/" "${ws0_host}:${run_path}/aggregate/"
exit "$code"
