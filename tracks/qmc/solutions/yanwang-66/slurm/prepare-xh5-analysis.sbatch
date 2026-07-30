#!/usr/bin/env bash
#SBATCH --job-name=q66-xh5-analysis-prep
#SBATCH --partition=xhhgnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=prepare-xh5-analysis-%j.out
#SBATCH --error=prepare-xh5-analysis-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
venv_dir=${project_root}/.venv-q66-v1
venv_staging=${venv_dir}.staging-${SLURM_JOB_ID}
reuse_locked_venv=${Q66_REUSE_LOCKED_VENV:-0}
matrix=${project_root}/research/requests/discovery/discovery-matrix-v1.json
matrix_sha256=${Q66_DISCOVERY_MATRIX_SHA256:?Q66_DISCOVERY_MATRIX_SHA256 is required}
snapshot_id=${Q66_ANALYSIS_SNAPSHOT_ID:?Q66_ANALYSIS_SNAPSHOT_ID is required}
snapshot_root=${project_root}/results/analysis-snapshots/${snapshot_id}
snapshot_staging=${snapshot_root}.staging-${SLURM_JOB_ID}
snapshot_checksums=${snapshot_root}.checksums-${SLURM_JOB_ID}
if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    printf 'invalid analysis snapshot ID: %s\n' "${snapshot_id}" >&2
    exit 2
fi
if [[ "${reuse_locked_venv}" != 0 && "${reuse_locked_venv}" != 1 ]]; then
    printf 'Q66_REUSE_LOCKED_VENV must be 0 or 1\n' >&2
    exit 2
fi
if [[ -e "${venv_staging}" || -e "${snapshot_root}" \
    || -e "${snapshot_staging}" || -e "${snapshot_checksums}" ]]; then
    printf 'staging or snapshot path already exists\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${matrix}" | cut -d ' ' -f 1)" != "${matrix_sha256}" ]]; then
    printf 'discovery matrix checksum mismatch\n' >&2
    exit 2
fi

module load anaconda3/2023.09
(
    cd "${project_root}/environment"
    sha256sum --check wheels.sha256
)
if [[ "${reuse_locked_venv}" == 1 ]]; then
    if [[ ! -x "${venv_dir}/bin/python" ]]; then
        printf 'locked venv is missing or incomplete: %s\n' "${venv_dir}" >&2
        exit 2
    fi
    test_python=${venv_dir}/bin/python
else
    python3 -m venv "${venv_staging}"
    "${venv_staging}/bin/python" -m pip install \
        --no-cache-dir \
        --no-index \
        --find-links "${project_root}/environment/wheels" \
        --require-hashes \
        --requirement "${project_root}/environment/requirements.lock"
    test_python=${venv_staging}/bin/python
fi
"${test_python}" -m pip check

export PYTHONPATH="${project_root}/src"
export Q66_INSTANCE_FILE="${project_root}/research/database/surface_code_instances.jsonl"
export PYTHONDONTWRITEBYTECODE=1
(
    cd "${project_root}/results"
    "${test_python}" -m pytest -q \
        "${project_root}/tests/test_experiment_core.py" \
        "${project_root}/tests/test_discovery_contract.py"
)

if [[ "${reuse_locked_venv}" == 0 ]]; then
    if [[ -e "${venv_dir}" ]]; then
        mv "${venv_dir}" "${venv_dir}.incomplete-before-${SLURM_JOB_ID}"
    fi
    mv "${venv_staging}" "${venv_dir}"
fi

mkdir -p \
    "${snapshot_staging}/environment" \
    "${snapshot_staging}/tests" \
    "${snapshot_staging}/src" \
    "${snapshot_staging}/research/controls" \
    "${snapshot_staging}/research/database" \
    "${snapshot_staging}/research/requests/discovery" \
    "${snapshot_staging}/research/requests/pilot"
cp -a "${project_root}/src/." "${snapshot_staging}/src/"
cp -a "${project_root}/tests/." "${snapshot_staging}/tests/"
cp "${project_root}/pyproject.toml" "${snapshot_staging}/pyproject.toml"
cp "${project_root}/environment/requirements.lock" \
    "${project_root}/environment/wheels.sha256" \
    "${snapshot_staging}/environment/"
cp -a "${project_root}/research/controls/." \
    "${snapshot_staging}/research/controls/"
cp -a "${project_root}/research/database/." \
    "${snapshot_staging}/research/database/"
cp -a "${project_root}/research/requests/pilot/." \
    "${snapshot_staging}/research/requests/pilot/"
cp "${matrix}" \
    "${snapshot_staging}/research/requests/discovery/discovery-matrix-v1.json"
(
    cd "${snapshot_staging}"
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum \
        > "${snapshot_checksums}"
)
mv "${snapshot_checksums}" "${snapshot_staging}/snapshot-checksums.sha256"
mv "${snapshot_staging}" "${snapshot_root}"
(
    cd "${snapshot_root}"
    sha256sum --quiet --check snapshot-checksums.sha256
)
sha256sum "${snapshot_root}/snapshot-checksums.sha256"
printf 'analysis_snapshot_root=%s\n' "${snapshot_root}"
