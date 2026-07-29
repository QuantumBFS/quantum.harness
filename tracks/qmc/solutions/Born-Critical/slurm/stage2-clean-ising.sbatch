#!/bin/bash
#
# Resource flags are supplied by the submit command after a queue probe.
# This CPU-only job needs NumPy but does not require a GPU.
#SBATCH --job-name=born-critical-stage2
#SBATCH --output=/tmp/born-critical-stage2-%j.out
#SBATCH --error=/tmp/born-critical-stage2-%j.err

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
ws0_source_path="${BORN_CRITICAL_WS0_SOURCE_PATH:-/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical}"
ws0_result_path="${BORN_CRITICAL_WS0_RESULT_PATH:-/home/ystu/quantum.harness/tracks/qmc/results/born-critical/stage2-clean-ising}"
requested_conda_environment="${BORN_CRITICAL_CONDA_ENV:-}"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work_root="${TMPDIR:-/tmp}/born-critical/stage2-${job_id}"
source_root="${work_root}/source"
result_root="${work_root}/result"
combined_log="${work_root}/runner.log"
remote_result_path="${ws0_result_path}/job-${job_id}"

mkdir -p "$source_root" "$result_root"
exec > >(tee -a "$combined_log") 2>&1

sync_back() {
    local exit_code=$?
    local remote_temporary_path="${remote_result_path}.incoming"
    trap - EXIT INT TERM
    set +e
    cp "$combined_log" "$result_root/runner.log"
    if [[ ! -f "$result_root/manifest.json" ]]; then
        printf '{\n  "schema_version": 1,\n  "stage": "stage2-clean-ising",\n  "status": "startup-failed",\n  "return_code": %d,\n  "hostname": "%s",\n  "slurm_job_id": "%s"\n}\n' \
            "$exit_code" "$(hostname)" "$job_id" > "$result_root/manifest.json"
    fi
    ssh "$ws0_host" "mkdir -p '${ws0_result_path}' && test ! -e '${remote_result_path}' && test ! -e '${remote_temporary_path}'"
    rsync -a "$result_root/" "${ws0_host}:${remote_temporary_path}/"
    ssh "$ws0_host" "mv '${remote_temporary_path}' '${remote_result_path}'"
    local sync_code=$?
    if [[ $sync_code -ne 0 ]]; then
        echo "[stage2] result sync failed with code ${sync_code}" >&2
    fi
    exit "$exit_code"
}
trap sync_back EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "[stage2] copying source from ${ws0_host}:${ws0_source_path}/"
rsync -a \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    "${ws0_host}:${ws0_source_path}/" "$source_root/"

source /opt/miniconda3/etc/profile.d/conda.sh
conda_environment=""
for candidate in "$requested_conda_environment" QC torch base; do
    [[ -n "$candidate" ]] || continue
    if conda run -n "$candidate" python -c "import numpy" >/dev/null 2>&1; then
        conda_environment="$candidate"
        break
    fi
done
if [[ -z "$conda_environment" ]]; then
    echo "[stage2] no Conda environment with NumPy is available" >&2
    exit 1
fi
conda activate "$conda_environment"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"

echo "[stage2] host=$(hostname) conda=${conda_environment}"
cd "$source_root"
python -u scripts/run_stage2_clean_ising.py --output "$result_root"
