#!/bin/bash
# Resource flags are supplied only after the per-node CPU/GPU audit.
#SBATCH --job-name=born-critical-stage4a
#SBATCH --output=/tmp/born-critical-stage4a-%j.out
#SBATCH --error=/tmp/born-critical-stage4a-%j.err
#SBATCH --chdir=/tmp

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical-122}"
ws0_result_path="${BORN_CRITICAL_RESULT_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage4a-tests}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/stage4a-${job_id}"
source_root="${work_root}/source"
result_root="${work_root}/result"
combined_log="${work_root}/runner.log"
remote_result_path="${ws0_result_path}/job-${job_id}"
mkdir -p "$source_root" "$result_root"
exec > >(tee -a "$combined_log") 2>&1

sync_back() {
    local exit_code=$?
    local temporary="${remote_result_path}.incoming"
    trap - EXIT INT TERM
    set +e
    cp "$combined_log" "$result_root/runner.log"
    if [[ ! -f "$result_root/manifest.json" ]]; then
        printf '{"schema_version":1,"stage":"stage4a","status":"startup-failed","return_code":%d,"hostname":"%s","slurm_job_id":"%s"}\n' \
            "$exit_code" "$(hostname)" "$job_id" > "$result_root/manifest.json"
    fi
    ssh "$ws0_host" "mkdir -p '${ws0_result_path}' && test ! -e '${remote_result_path}' && test ! -e '${temporary}'"
    rsync -a "$result_root/" "${ws0_host}:${temporary}/"
    ssh "$ws0_host" "mv '${temporary}' '${remote_result_path}'"
    exit "$exit_code"
}
trap sync_back EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${ws0_source_path}/" "$source_root/"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
cd "$source_root"
PYTHONPATH=src python -u scripts/run_stage4a_checks.py --output "$result_root"
