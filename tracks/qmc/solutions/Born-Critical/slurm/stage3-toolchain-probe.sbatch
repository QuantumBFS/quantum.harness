#!/bin/bash
#SBATCH --job-name=born-critical-s3-probe
#SBATCH --output=/tmp/born-critical-s3-probe-%j.out
#SBATCH --error=/tmp/born-critical-s3-probe-%j.err

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_result_path="${BORN_CRITICAL_WS0_RESULT_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage3-toolchain-probe}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/stage3-probe-${job_id}"
result_root="${work_root}/result"
remote_result_path="${ws0_result_path}/job-${job_id}"
log_path="${result_root}/toolchain.txt"
mkdir -p "$result_root"
exec > >(tee -a "$log_path") 2>&1

sync_back() {
    local exit_code=$?
    local temporary="${remote_result_path}.incoming"
    trap - EXIT INT TERM
    set +e
    printf '{\n  "schema_version": 1,\n  "stage": "stage3-toolchain-probe",\n  "status": "%s",\n  "return_code": %d,\n  "hostname": "%s",\n  "slurm_job_id": "%s"\n}\n' \
        "$([[ $exit_code -eq 0 ]] && echo success || echo failed)" \
        "$exit_code" "$(hostname)" "$job_id" > "$result_root/manifest.json"
    ssh "$ws0_host" "mkdir -p '${ws0_result_path}' && test ! -e '${remote_result_path}' && test ! -e '${temporary}'"
    rsync -a "$result_root/" "${ws0_host}:${temporary}/"
    ssh "$ws0_host" "mv '${temporary}' '${remote_result_path}'"
    exit "$exit_code"
}
trap sync_back EXIT

echo "hostname=$(hostname)"
echo "PATH=${PATH}"
echo "MKLROOT=${MKLROOT:-unset}"
for command_name in mpic++ g++ icpx mpiicpx cmake make gfortran python; do
    printf '%s=' "$command_name"
    command -v "$command_name" || true
done
for candidate in \
    /usr/include/eigen3/Eigen/Dense \
    /opt/intel/oneapi/mkl/latest/include/mkl.h \
    /opt/miniconda3/include/mkl.h \
    /usr/include/mkl.h; do
    [[ -e "$candidate" ]] && echo "found=${candidate}"
done
find /opt /usr/local /home/ystu -maxdepth 5 \
    \( -name pfapack.h -o -name libcpfapack.a -o -name libpfapack.a -o -name mkl.h \) \
    -print 2>/dev/null | head -200
source /opt/miniconda3/etc/profile.d/conda.sh
conda env list
for environment_name in QC torch base; do
    if conda env list | awk '{print $1}' | grep -Fxq "$environment_name"; then
        echo "environment=${environment_name}"
        conda run -n "$environment_name" bash -c '
            echo "prefix=${CONDA_PREFIX}"
            for item in mpic++ g++ gfortran python; do
                printf "%s=" "$item"
                command -v "$item" || true
            done
            find "${CONDA_PREFIX}" -maxdepth 5 \
                \( -name mkl.h -o -name "libmkl_core.so*" -o -path "*/Eigen/Dense" -o -name pfapack.h \) \
                -print 2>/dev/null | head -100
        '
    fi
done
