#!/usr/bin/env bash
#SBATCH --job-name=q66-confirm-cycle
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --time=20:00:00
#SBATCH --output=confirmation-cycle-%j.out
#SBATCH --error=confirmation-cycle-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
snapshot_id=${Q66_CONFIRMATION_CYCLE_SNAPSHOT_ID:?Q66_CONFIRMATION_CYCLE_SNAPSHOT_ID is required}
snapshot_manifest_sha256=${Q66_CONFIRMATION_CYCLE_SNAPSHOT_MANIFEST_SHA256:?Q66_CONFIRMATION_CYCLE_SNAPSHOT_MANIFEST_SHA256 is required}
initial_job_id=${Q66_CONFIRMATION_INITIAL_JOB_ID:?Q66_CONFIRMATION_INITIAL_JOB_ID is required}
candidate_root=${Q66_CONFIRMATION_CANDIDATE_ROOT:?Q66_CONFIRMATION_CANDIDATE_ROOT is required}
instance_file=${Q66_CONFIRMATION_INSTANCE_FILE:?Q66_CONFIRMATION_INSTANCE_FILE is required}
instance_sha256=25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751
snapshot_root=${project_root}/results/analysis-snapshots/${snapshot_id}
snapshot_manifest=${snapshot_root}/snapshot-checksums.sha256
matrix=${project_root}/results/confirmation/matrices/confirmation-${initial_job_id}.json
matrix_checksum=${matrix}.sha256
initial_results=${project_root}/results/confirmation/initial/${initial_job_id}
analysis_root=${project_root}/results/confirmation/analysis
phase_root=${project_root}/results/confirmation/continuation
cycle_root=${project_root}/results/confirmation/cycles
cycle_summary=${cycle_root}/${SLURM_JOB_ID}.json
cycle_staging=${cycle_summary}.staging
resume_job_id=${Q66_CONFIRMATION_RESUME_JOB_ID:-}
resume_args=()

if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    printf 'invalid confirmation-cycle snapshot ID: %s\n' "${snapshot_id}" >&2
    exit 2
fi
if [[ ! "${snapshot_manifest_sha256}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid confirmation-cycle snapshot checksum\n' >&2
    exit 2
fi
if [[ ! "${initial_job_id}" =~ ^[0-9]+$ ]]; then
    printf 'invalid initial confirmation job ID\n' >&2
    exit 2
fi
if [[ -n "${resume_job_id}" ]]; then
    if [[ ! "${resume_job_id}" =~ ^[0-9]+$ \
        || "${resume_job_id}" == "${SLURM_JOB_ID}" ]]; then
        printf 'invalid confirmation resume job ID\n' >&2
        exit 2
    fi
    resume_analysis=
    for phase_index in $(seq 11 -1 1); do
        candidate=${analysis_root}/phase-${phase_index}/${resume_job_id}
        if [[ -f "${candidate}/analysis-summary.json" \
            && -f "${candidate}/analysis-checksums.sha256" ]]; then
            resume_analysis=${candidate}
            break
        fi
    done
    if [[ -z "${resume_analysis}" ]]; then
        printf 'no published confirmation analysis is available to resume\n' >&2
        exit 2
    fi
    resume_args=(--resume-analysis "${resume_analysis}")
fi
if [[ ! -d "${candidate_root}" ]]; then
    printf 'frozen confirmation candidate is missing: %s\n' "${candidate_root}" >&2
    exit 2
fi
if [[ ! -f "${instance_file}" ]]; then
    printf 'frozen confirmation instance database is missing: %s\n' \
        "${instance_file}" >&2
    exit 2
fi
for input in \
    "${snapshot_manifest}" \
    "${matrix}" \
    "${matrix_checksum}" \
    "${initial_results}/run-summary.json" \
    "${initial_results}/result-checksums.sha256"; do
    if [[ ! -f "${input}" ]]; then
        printf 'required confirmation input is missing: %s\n' "${input}" >&2
        exit 2
    fi
done
for output in "${cycle_summary}" "${cycle_staging}"; do
    if [[ -e "${output}" ]]; then
        printf 'confirmation-cycle output already exists: %s\n' "${output}" >&2
        exit 2
    fi
done
if [[ "$(sha256sum "${snapshot_manifest}" | cut -d ' ' -f 1)" \
    != "${snapshot_manifest_sha256}" ]]; then
    printf 'confirmation-cycle snapshot manifest checksum mismatch\n' >&2
    exit 2
fi
(
    cd "${snapshot_root}"
    sha256sum --quiet --check snapshot-checksums.sha256
)
sha256sum --quiet --check "${matrix_checksum}"
if [[ "$(sha256sum "${instance_file}" | cut -d ' ' -f 1)" \
    != "${instance_sha256}" ]]; then
    printf 'confirmation instance database checksum mismatch\n' >&2
    exit 2
fi
if [[ "$(jq -r '.groups[0].requests[0].instance_file' "${matrix}")" \
    != "${instance_file}" ]]; then
    printf 'matrix and confirmation instance paths differ\n' >&2
    exit 2
fi
(
    cd "${initial_results}"
    sha256sum --quiet --check result-checksums.sha256
)

export PYTHONPATH=${snapshot_root}/src
export Q66_INSTANCE_FILE=${instance_file}
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

cd "${snapshot_root}"
"${project_root}/.venv-q66-v1/bin/python" -m pytest -q \
    tests/test_confirmation_contract.py
mkdir -p "${cycle_root}"
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.confirmation_cycle cycle \
    --matrix "${matrix}" \
    --initial-results "${initial_results}" \
    --candidate-root "${candidate_root}" \
    --analysis-root "${analysis_root}" \
    --phase-root "${phase_root}" \
    --simulation-workers "${SLURM_CPUS_PER_TASK}" \
    --validation-workers 8 \
    --timeout-seconds 10800 \
    --bootstrap-resamples 20000 \
    "${resume_args[@]}" \
    > "${cycle_staging}"
mv "${cycle_staging}" "${cycle_summary}"
sha256sum "${cycle_summary}" > "${cycle_summary}.sha256"
