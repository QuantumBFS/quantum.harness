#!/bin/bash
#SBATCH --job-name=born-critical-s3-cross
#SBATCH --output=/tmp/born-critical-s3-cross-%j.out
#SBATCH --error=/tmp/born-critical-s3-cross-%j.err
#SBATCH --chdir=/tmp

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical}"
ws0_upstream_path="${BORN_CRITICAL_UPSTREAM_PATH:-/home/ystu/upstream/fermionic-transfer-matrix-rbim}"
ws0_eigen_path="${BORN_CRITICAL_EIGEN_PATH:-/home/ystu/upstream/deps/eigen-3.4.0}"
ws0_result_path="${BORN_CRITICAL_RESULT_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage3-crosschecks}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/stage3-crosschecks-${job_id}"
source_root="${work_root}/source"
upstream_root="${work_root}/upstream"
eigen_root="${work_root}/eigen"
build_root="${work_root}/build"
scratch_root="${work_root}/scratch"
result_root="${work_root}/result"
combined_log="${work_root}/runner.log"
remote_result_path="${ws0_result_path}/job-${job_id}"
mkdir -p "$source_root" "$upstream_root" "$eigen_root" "$build_root" "$scratch_root" "$result_root"
exec > >(tee -a "$combined_log") 2>&1

sync_back() {
    local exit_code=$?
    local temporary="${remote_result_path}.incoming"
    trap - EXIT INT TERM
    set +e
    cp "$combined_log" "$result_root/runner.log"
    if [[ ! -f "$result_root/manifest.json" ]]; then
        printf '{\n  "schema_version": 1,\n  "stage": "stage3-rbim-crosschecks",\n  "status": "startup-failed",\n  "return_code": %d,\n  "hostname": "%s",\n  "slurm_job_id": "%s"\n}\n' \
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
rsync -a "${ws0_host}:${ws0_upstream_path}/" "$upstream_root/"
rsync -a "${ws0_host}:${ws0_eigen_path}/" "$eigen_root/"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

compat="${source_root}/references/upstream-compat"
compile_flags=(-std=c++17 -O3 -march=native "-I${compat}" "-I${upstream_root}/inc" "-I${eigen_root}")
link_flags=("-L${CONDA_PREFIX}/lib" "-Wl,-rpath,${CONDA_PREFIX}/lib" -lmkl_rt -lpthread -lm -ldl)
g++ "${compile_flags[@]}" "${compat}/rbim_stream.cpp" "${link_flags[@]}" -o "${build_root}/rbim-stream"
g++ "${compile_flags[@]}" "${compat}/fixed_driver.cpp" "${compat}/pfapack_stub.cpp" "${link_flags[@]}" -o "${build_root}/fixed-driver"

cd "$source_root"
PYTHONPATH=src python -u scripts/run_stage3_crosschecks.py \
    --config configs/rbim-crosschecks.json \
    --binary "${build_root}/rbim-stream" \
    --upstream-driver "${build_root}/fixed-driver" \
    --work "$scratch_root" \
    --output "$result_root" \
    --workers "${SLURM_CPUS_PER_TASK:-1}"
