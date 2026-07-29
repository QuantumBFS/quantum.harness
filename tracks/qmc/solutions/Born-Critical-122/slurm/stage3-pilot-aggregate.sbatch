#!/bin/bash
#SBATCH --job-name=born-critical-s3-pilot-agg
#SBATCH --output=/tmp/born-critical-s3-pilot-agg-%j.out
#SBATCH --error=/tmp/born-critical-s3-pilot-agg-%j.err

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical-122}"
ws0_run_path="${BORN_CRITICAL_RUN_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/rbim-pilot-v2}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/stage3-pilot-aggregate-${job_id}"
source_root="${work_root}/source"
run_root="${work_root}/run"
result_root="${work_root}/aggregate"
combined_log="${work_root}/runner.log"
remote_result_path="${ws0_run_path}/aggregate"
mkdir -p "$source_root" "$run_root" "$result_root"
exec > >(tee -a "$combined_log") 2>&1

sync_back() {
    local exit_code=$?
    local temporary="${remote_result_path}.incoming-${job_id}"
    trap - EXIT INT TERM
    set +e
    cp "$combined_log" "$result_root/runner.log"
    if [[ ! -f "$result_root/metrics.json" ]]; then
        printf '{\n  "status": "failed",\n  "return_code": %d,\n  "hostname": "%s",\n  "slurm_job_id": "%s"\n}\n' \
            "$exit_code" "$(hostname)" "$job_id" > "$result_root/manifest.json"
    else
        printf '{\n  "status": "success",\n  "return_code": 0,\n  "hostname": "%s",\n  "slurm_job_id": "%s"\n}\n' \
            "$(hostname)" "$job_id" > "$result_root/manifest.json"
    fi
    ssh "$ws0_host" "test ! -e '${remote_result_path}' && test ! -e '${temporary}'"
    rsync -a "$result_root/" "${ws0_host}:${temporary}/"
    ssh "$ws0_host" "mv '${temporary}' '${remote_result_path}'"
    exit "$exit_code"
}
trap sync_back EXIT

rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${ws0_source_path}/" "$source_root/"
rsync -a "${ws0_host}:${ws0_run_path}/" "$run_root/"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
cd "$source_root"
python -u scripts/aggregate_rbim_pilot.py --run "$run_root" --output "$result_root"
