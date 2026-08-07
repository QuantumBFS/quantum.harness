#!/bin/bash
#SBATCH --job-name=born-critical-s3-cppbench
#SBATCH --output=/tmp/born-critical-s3-cppbench-%j.out
#SBATCH --error=/tmp/born-critical-s3-cppbench-%j.err

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical-122}"
ws0_eigen_path="${BORN_CRITICAL_EIGEN_PATH:-/home/ystu/upstream/deps/eigen-3.4.0}"
ws0_result_path="${BORN_CRITICAL_WS0_RESULT_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage3-cpp-benchmark}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/stage3-cppbench-${job_id}"
source_root="${work_root}/source"
eigen_root="${work_root}/eigen"
result_root="${work_root}/result"
combined_log="${work_root}/runner.log"
remote_result_path="${ws0_result_path}/job-${job_id}"
mkdir -p "$source_root" "$eigen_root" "$result_root"
exec > >(tee -a "$combined_log") 2>&1

sync_back() {
    local exit_code=$?
    local temporary="${remote_result_path}.incoming"
    trap - EXIT INT TERM
    set +e
    cp "$combined_log" "$result_root/runner.log"
    printf '{\n  "status": "%s",\n  "return_code": %d,\n  "hostname": "%s",\n  "slurm_job_id": "%s"\n}\n' \
        "$([[ $exit_code -eq 0 ]] && echo success || echo failed)" \
        "$exit_code" "$(hostname)" "$job_id" > "$result_root/manifest.json"
    ssh "$ws0_host" "mkdir -p '${ws0_result_path}' && test ! -e '${remote_result_path}' && test ! -e '${temporary}'"
    rsync -a "$result_root/" "${ws0_host}:${temporary}/"
    ssh "$ws0_host" "mv '${temporary}' '${remote_result_path}'"
    exit "$exit_code"
}
trap sync_back EXIT

rsync -a --exclude '__pycache__/' "${ws0_host}:${ws0_source_path}/" "$source_root/"
rsync -a "${ws0_host}:${ws0_eigen_path}/" "$eigen_root/"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
compat="${source_root}/references/upstream-compat"
g++ -std=c++17 -O3 -march=native -I"$compat" -I"$eigen_root" \
    "$compat/rbim_stream.cpp" \
    "-L${CONDA_PREFIX}/lib" "-Wl,-rpath,${CONDA_PREFIX}/lib" \
    -lmkl_rt -lpthread -lm -ldl -o "$work_root/rbim-stream"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
for size in 4 12 32; do
    echo "benchmark_size=${size}"
    "$work_root/rbim-stream" "$size" 12345 0.1092212 \
        1.0493604763025683 5 "$((20 * size))" 1000000 2500 1 \
        "$result_root/blocks-L${size}.bin" \
        | tee "$result_root/benchmark-L${size}.txt"
done
