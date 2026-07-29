#!/bin/bash
#SBATCH --job-name=born-critical-rbim
#SBATCH --output=/tmp/born-critical-rbim-%A_%a.out
#SBATCH --error=/tmp/born-critical-rbim-%A_%a.err

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical-122}"
run_spec_relative="${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
run_path_relative="${run_spec_relative%/run_spec.json}"
ws0_run_path="${BORN_CRITICAL_RUN_PATH:-/home/ystu/quantum.harness/${run_path_relative}}"
cell_offset="${BORN_CRITICAL_CELL_OFFSET:-0}"
task_id="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"
cell_index=$((cell_offset + task_id))
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/rbim-${job_id}-${task_id}"
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
    local local_cell remote_cell_path remote_temporary remote_parent
    if [[ -n "$cell_id" ]]; then
        local_cell="${local_output}/cells/${cell_id}"
        remote_cell_path="${ws0_run_path}/cells/${cell_id}"
        remote_temporary="${ws0_run_path}/cells/.${cell_id}.incoming-${job_id}-${task_id}"
        remote_parent="${ws0_run_path}/cells"
    else
        local_cell="${local_output}/startup-failure"
        remote_cell_path="${ws0_run_path}/startup-failures/job-${job_id}-task-${task_id}"
        remote_temporary="${remote_cell_path}.incoming"
        remote_parent="${ws0_run_path}/startup-failures"
    fi
    if [[ ! -d "$local_cell" ]]; then
        mkdir -p "$local_cell"
        printf '{\n  "schema_version": 1,\n  "cell_id": "%s",\n  "status": "startup-failed",\n  "return_code": %d,\n  "hostname": "%s",\n  "slurm_job_id": "%s",\n  "slurm_array_task_id": "%s"\n}\n' \
            "${cell_id:-unresolved-index-${cell_index}}" "$exit_code" "$(hostname)" "$job_id" "$task_id" \
            > "$local_cell/manifest.json"
    fi
    cp "$combined_log" "$local_cell/runner.log"
    ssh "$ws0_host" "mkdir -p '${remote_parent}' && test ! -e '${remote_cell_path}' && test ! -e '${remote_temporary}'"
    rsync -a "$local_cell/" "${ws0_host}:${remote_temporary}/"
    ssh "$ws0_host" "mv '${remote_temporary}' '${remote_cell_path}'"
    exit "$exit_code"
}
trap sync_back EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${ws0_source_path}/" "$source_root/"
rsync -a "${ws0_host}:${ws0_run_path}/run_spec.json" "$local_run/run_spec.json"

cell_id="$(python3 -c '
import json, sys
spec=json.load(open(sys.argv[1]))
index=int(sys.argv[2])
print(spec["cells"][index-1]["cell_id"])
' "$local_run/run_spec.json" "$cell_index")"

source /opt/miniconda3/etc/profile.d/conda.sh
for environment_name in QC torch base; do
    if conda run -n "$environment_name" python -c "import numpy" >/dev/null 2>&1; then
        conda activate "$environment_name"
        break
    fi
done
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

cd "$source_root"
python -u scripts/run_rbim_cell.py \
    --run-spec "$local_run/run_spec.json" \
    --cell-index "$cell_index" \
    --output-root "$local_output"
