#!/bin/bash
#SBATCH --job-name=born-critical-stage3a
#SBATCH --output=/tmp/born-critical-stage3a-%j.out
#SBATCH --error=/tmp/born-critical-stage3a-%j.err

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical}"
ws0_upstream_path="${BORN_CRITICAL_UPSTREAM_PATH:-/home/ystu/upstream/fermionic-transfer-matrix-rbim}"
ws0_eigen_path="${BORN_CRITICAL_EIGEN_PATH:-/home/ystu/upstream/deps/eigen-3.4.0}"
ws0_result_path="${BORN_CRITICAL_WS0_RESULT_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage3a-baseline}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/stage3a-${job_id}"
source_root="${work_root}/source"
upstream_root="${work_root}/upstream"
eigen_root="${work_root}/eigen"
build_root="${work_root}/build"
smoke_root="${work_root}/upstream-smoke"
result_root="${work_root}/result"
combined_log="${work_root}/runner.log"
remote_result_path="${ws0_result_path}/job-${job_id}"

mkdir -p "$source_root" "$upstream_root" "$eigen_root" "$build_root" "$smoke_root" "$result_root"
exec > >(tee -a "$combined_log") 2>&1

sync_back() {
    local exit_code=$?
    local temporary="${remote_result_path}.incoming"
    trap - EXIT INT TERM
    set +e
    cp "$combined_log" "$result_root/runner.log"
    if [[ ! -f "$result_root/manifest.json" ]]; then
        printf '{\n  "schema_version": 1,\n  "stage": "stage3a-rbim-baseline",\n  "status": "startup-failed",\n  "return_code": %d,\n  "hostname": "%s",\n  "slurm_job_id": "%s"\n}\n' \
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
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"

compat_root="${source_root}/references/upstream-compat"
mkl_runtime="$(find "${CONDA_PREFIX}/lib" -maxdepth 1 -name 'libmkl_rt.so' -print -quit)"
if [[ -z "$mkl_runtime" ]]; then
    echo "[stage3a] libmkl_rt.so not found in ${CONDA_PREFIX}" >&2
    exit 1
fi

compile_flags=(
    -std=c++17 -O2
    "-I${compat_root}"
    "-I${upstream_root}/inc"
    "-I${eigen_root}"
)
link_flags=(
    "-L${CONDA_PREFIX}/lib"
    "-Wl,-rpath,${CONDA_PREFIX}/lib"
    -lmkl_rt -lpthread -lm -ldl
)
{
    echo "compiler=$(command -v g++)"
    echo "mkl_runtime=${mkl_runtime}"
    echo "upstream_commit=814c24775b6b46cab77f3b4829c9c3802cab2146"
    g++ "${compile_flags[@]}" \
        "${upstream_root}/src/main.cpp" \
        "${compat_root}/pfapack_stub.cpp" \
        "${link_flags[@]}" \
        -o "${build_root}/upstream-main"
    g++ "${compile_flags[@]}" \
        "${compat_root}/fixed_driver.cpp" \
        "${compat_root}/pfapack_stub.cpp" \
        "${link_flags[@]}" \
        -o "${build_root}/fixed-driver"
} 2>&1 | tee "$result_root/upstream-build.log"

coupling="$(python -c 'import math; p=0.1092212; print(0.5*math.log((1-p)/p))')"
temperature="$(python -c 'import math; p=0.1092212; print(1/(0.5*math.log((1-p)/p)))')"
printf '4 4 0 2 2 1 1\n%s\n0.1092212\n' "$temperature" > "$smoke_root/input"
(
    cd "$smoke_root"
    "${build_root}/upstream-main"
) 2>&1 | tee "$result_root/upstream-smoke.log"

cd "$source_root"
python -u scripts/run_stage3a_baseline.py \
    --output "$result_root" \
    --upstream-driver "${build_root}/fixed-driver" \
    --upstream-smoke "$smoke_root"
