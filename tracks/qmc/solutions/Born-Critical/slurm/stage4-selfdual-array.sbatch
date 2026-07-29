#!/bin/bash
#SBATCH --job-name=born-critical-selfdual
#SBATCH --output=/tmp/born-critical-selfdual-%A_%a.out
#SBATCH --error=/tmp/born-critical-selfdual-%A_%a.err
#SBATCH --chdir=/tmp

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical}"
run_spec_relative="${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
run_path_relative="${run_spec_relative%/run_spec.json}"
ws0_run_path="${BORN_CRITICAL_RUN_PATH:-/home/ystu/quantum.harness/${run_path_relative}}"
cell_offset="${BORN_CRITICAL_CELL_OFFSET:-0}"
task_id="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"
cell_index=$((cell_offset + task_id))
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/selfdual-${job_id}-${task_id}"
source_root="${work_root}/source"
local_run="${work_root}/run"
local_output="${work_root}/output"
combined_log="${work_root}/runner.log"
mkdir -p "$source_root" "$local_run" "$local_output"
exec > >(tee -a "$combined_log") 2>&1
cell_id=""

sync_back() {
    local exit_code=$?
    trap - EXIT INT TERM
    set +e
    local local_cell remote_cell temporary parent
    if [[ -n "$cell_id" ]]; then
        local_cell="${local_output}/cells/${cell_id}"
        remote_cell="${ws0_run_path}/cells/${cell_id}"
        temporary="${ws0_run_path}/cells/.${cell_id}.incoming-${job_id}-${task_id}"
        parent="${ws0_run_path}/cells"
    else
        local_cell="${local_output}/startup-failure"
        remote_cell="${ws0_run_path}/startup-failures/job-${job_id}-task-${task_id}"
        temporary="${remote_cell}.incoming"
        parent="${ws0_run_path}/startup-failures"
    fi
    if [[ ! -d "$local_cell" ]]; then
        mkdir -p "$local_cell"
        printf '{"schema_version":1,"status":"startup-failed","return_code":%d,"cell_index":%d}\n' \
            "$exit_code" "$cell_index" > "$local_cell/manifest.json"
    fi
    cp "$combined_log" "$local_cell/runner.log"
    ssh "$ws0_host" "mkdir -p '${parent}' && test ! -e '${remote_cell}' && test ! -e '${temporary}'"
    rsync -a "$local_cell/" "${ws0_host}:${temporary}/"
    ssh "$ws0_host" "mv '${temporary}' '${remote_cell}'"
    exit "$exit_code"
}
trap sync_back EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${ws0_source_path}/" "$source_root/"
rsync -a "${ws0_host}:${ws0_run_path}/run_spec.json" "$local_run/run_spec.json"
cell_id="$(python3 -c '
import json,sys
spec=json.load(open(sys.argv[1]))
print(spec["cells"][int(sys.argv[2])-1]["cell_id"])
' "$local_run/run_spec.json" "$cell_index")"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$source_root"
PYTHONPATH=src python -u scripts/run_selfdual_array_cell.py \
    --run-spec "$local_run/run_spec.json" \
    --cell-index "$cell_index" \
    --output-root "$local_output"
