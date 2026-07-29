#!/bin/bash
#SBATCH --job-name=born-critical-rbim-prod
#SBATCH --output=/tmp/born-critical-rbim-prod-%A_%a.out
#SBATCH --error=/tmp/born-critical-rbim-prod-%A_%a.err

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical-122}"
ws0_eigen_path="${BORN_CRITICAL_EIGEN_PATH:-/home/ystu/upstream/deps/eigen-3.4.0}"
run_spec_relative="${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
run_path_relative="${run_spec_relative%/run_spec.json}"
ws0_run_path="${BORN_CRITICAL_RUN_PATH:-/home/ystu/quantum.harness/${run_path_relative}}"
task_id="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/rbim-production-${job_id}-${task_id}"
source_root="${work_root}/source"
eigen_root="${work_root}/eigen"
local_run="${work_root}/run"
local_output="${work_root}/output"
combined_log="${work_root}/runner.log"
mkdir -p "$source_root" "$eigen_root" "$local_run" "$local_output"
exec > >(tee -a "$combined_log") 2>&1

sync_back() {
    local exit_code=$?
    trap - EXIT INT TERM
    set +e
    if [[ -d "$local_output/cells" ]]; then
        for local_cell in "$local_output"/cells/cell-*; do
            [[ -d "$local_cell" ]] || continue
            cell_id="$(basename "$local_cell")"
            remote_cell="${ws0_run_path}/cells/${cell_id}"
            temporary="${ws0_run_path}/cells/.${cell_id}.incoming-${job_id}-${task_id}"
            cp "$combined_log" "$local_cell/runner.log"
            ssh "$ws0_host" "mkdir -p '${ws0_run_path}/cells' && test ! -e '${remote_cell}' && test ! -e '${temporary}'"
            rsync -a "$local_cell/" "${ws0_host}:${temporary}/"
            ssh "$ws0_host" "mv '${temporary}' '${remote_cell}'"
        done
    fi
    group_remote="${ws0_run_path}/groups/group-${task_id}-job-${job_id}"
    group_temporary="${group_remote}.incoming"
    mkdir -p "$local_output/group"
    cp "$combined_log" "$local_output/group/runner.log"
    if [[ -f "$local_output/group-manifest.json" ]]; then
        cp "$local_output/group-manifest.json" "$local_output/group/manifest.json"
    else
        printf '{"status":"startup-failed","return_code":%d}\n' "$exit_code" > "$local_output/group/manifest.json"
    fi
    ssh "$ws0_host" "mkdir -p '${ws0_run_path}/groups' && test ! -e '${group_remote}' && test ! -e '${group_temporary}'"
    rsync -a "$local_output/group/" "${ws0_host}:${group_temporary}/"
    ssh "$ws0_host" "mv '${group_temporary}' '${group_remote}'"
    exit "$exit_code"
}
trap sync_back EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${ws0_source_path}/" "$source_root/"
rsync -a "${ws0_host}:${ws0_eigen_path}/" "$eigen_root/"
rsync -a "${ws0_host}:${ws0_run_path}/run_spec.json" "$local_run/run_spec.json"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
compat="${source_root}/references/upstream-compat"
g++ -std=c++17 -O3 -march=native -I"$compat" -I"$eigen_root" \
    "$compat/rbim_stream.cpp" \
    "-L${CONDA_PREFIX}/lib" "-Wl,-rpath,${CONDA_PREFIX}/lib" \
    -lmkl_rt -lpthread -lm -ldl -o "$work_root/rbim-stream"

cd "$source_root"
group_count="$(python -c '
import json, sys
spec=json.load(open(sys.argv[1]))
print(len({cell["params"]["size"] for cell in spec["cells"]}))
' "$local_run/run_spec.json")"
python -u scripts/run_rbim_production_group.py \
    --run-spec "$local_run/run_spec.json" \
    --group-index "$task_id" \
    --groups "$group_count" \
    --binary "$work_root/rbim-stream" \
    --output-root "$local_output" \
    --work "$work_root/binary-output" \
    --workers "${SLURM_CPUS_PER_TASK:-1}"
