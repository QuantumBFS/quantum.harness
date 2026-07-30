#!/usr/bin/env bash
#SBATCH --job-name=q66-confirm-initial
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=confirmation-initial-%j.out
#SBATCH --error=confirmation-initial-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
snapshot_id=${Q66_CONFIRMATION_SNAPSHOT_ID:?Q66_CONFIRMATION_SNAPSHOT_ID is required}
snapshot_manifest_sha256=${Q66_CONFIRMATION_SNAPSHOT_MANIFEST_SHA256:?Q66_CONFIRMATION_SNAPSHOT_MANIFEST_SHA256 is required}
candidate_root=${Q66_CONFIRMATION_CANDIDATE_ROOT:?Q66_CONFIRMATION_CANDIDATE_ROOT is required}
source_commit=${Q66_CONFIRMATION_SOURCE_COMMIT:?Q66_CONFIRMATION_SOURCE_COMMIT is required}
environment_lock_sha256=${Q66_ENVIRONMENT_LOCK_SHA256:?Q66_ENVIRONMENT_LOCK_SHA256 is required}
family_sha256=${Q66_CONFIRMATION_FAMILY_SHA256:?Q66_CONFIRMATION_FAMILY_SHA256 is required}
instance_sha256=${Q66_INSTANCE_SHA256:?Q66_INSTANCE_SHA256 is required}
snapshot_root=${project_root}/results/analysis-snapshots/${snapshot_id}
snapshot_manifest=${snapshot_root}/snapshot-checksums.sha256
instance_file=${snapshot_root}/research/database/surface_code_instances.jsonl
family_file=${snapshot_root}/research/database/confirmation_families.json
matrix_root=${project_root}/results/confirmation/matrices
matrix=${matrix_root}/confirmation-${SLURM_JOB_ID}.json
matrix_staging=${matrix}.staging
output_root=${project_root}/results/confirmation/initial/${SLURM_JOB_ID}
controls_output=${project_root}/results/validator/negative-controls-v2/${SLURM_JOB_ID}

if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    printf 'invalid confirmation snapshot ID: %s\n' "${snapshot_id}" >&2
    exit 2
fi
for checksum in \
    "${snapshot_manifest_sha256}" \
    "${environment_lock_sha256}" \
    "${family_sha256}" \
    "${instance_sha256}"; do
    if [[ ! "${checksum}" =~ ^[0-9a-f]{64}$ ]]; then
        printf 'invalid SHA-256 input\n' >&2
        exit 2
    fi
done
if [[ ! "${source_commit}" =~ ^[0-9a-f]{40}$ ]]; then
    printf 'invalid confirmation source commit\n' >&2
    exit 2
fi
if [[ "${source_commit}" != 0a73ba334a4b85403634e710f3d768ef8831d16d ]]; then
    printf 'confirmation source differs from the frozen reference\n' >&2
    exit 2
fi
if [[ "${instance_sha256}" \
    != 25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751 ]]; then
    printf 'surface-code instance database differs from the frozen reference\n' >&2
    exit 2
fi
if [[ ! -d "${candidate_root}" ]]; then
    printf 'frozen confirmation candidate is missing: %s\n' "${candidate_root}" >&2
    exit 2
fi
for output in "${matrix}" "${matrix_staging}" "${output_root}" "${controls_output}"; do
    if [[ -e "${output}" ]]; then
        printf 'confirmation output already exists: %s\n' "${output}" >&2
        exit 2
    fi
done
if [[ "$(sha256sum "${snapshot_manifest}" | cut -d ' ' -f 1)" \
    != "${snapshot_manifest_sha256}" ]]; then
    printf 'confirmation snapshot manifest checksum mismatch\n' >&2
    exit 2
fi
(
    cd "${snapshot_root}"
    sha256sum --quiet --check snapshot-checksums.sha256
)
if [[ "$(sha256sum "${snapshot_root}/environment/requirements.lock" \
    | cut -d ' ' -f 1)" != "${environment_lock_sha256}" ]]; then
    printf 'confirmation environment lock checksum mismatch\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${family_file}" | cut -d ' ' -f 1)" \
    != "${family_sha256}" ]]; then
    printf 'confirmation family checksum mismatch\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${instance_file}" | cut -d ' ' -f 1)" \
    != "${instance_sha256}" ]]; then
    printf 'surface-code instance database checksum mismatch\n' >&2
    exit 2
fi

export PYTHONPATH="${snapshot_root}/src"
export Q66_INSTANCE_FILE="${instance_file}"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

(
    cd "${snapshot_root}"
    "${project_root}/.venv-q66-v1/bin/python" -m pytest -q \
        tests/test_experiment_core.py \
        tests/test_confirmation_contract.py \
        tests/test_dev_validator_contract.py
)
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.negative_controls \
    --controls-root "${snapshot_root}/research/controls" \
    --base-request "${snapshot_root}/research/requests/pilot/00-none.json" \
    --output-root "${controls_output}"

mkdir -p "${matrix_root}"
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.confirmation \
    --families "${family_file}" \
    --instances "${instance_file}" \
    --source-commit "${source_commit}" \
    --environment-lock-sha256 "${environment_lock_sha256}" \
    --shard-size 4096 \
    --out "${matrix_staging}"
mv "${matrix_staging}" "${matrix}"
sha256sum "${matrix}" > "${matrix}.sha256"

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.confirmation_run \
    --matrix "${matrix}" \
    --candidate-root "${candidate_root}" \
    --output-root "${output_root}" \
    --simulation-workers "${SLURM_CPUS_PER_TASK}" \
    --validation-workers 8 \
    --timeout-seconds 7200
(
    cd "${output_root}"
    sha256sum --quiet --check result-checksums.sha256
)
sha256sum "${output_root}/result-checksums.sha256"
