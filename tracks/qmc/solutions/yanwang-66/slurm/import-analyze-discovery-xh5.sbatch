#!/usr/bin/env bash
#SBATCH --job-name=q66-import-analyze
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=import-analyze-discovery-%j.out
#SBATCH --error=import-analyze-discovery-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
array_job_id=${Q66_DISCOVERY_ARRAY_JOB_ID:?Q66_DISCOVERY_ARRAY_JOB_ID is required}
archive_sha256=${Q66_DISCOVERY_ARCHIVE_SHA256:?Q66_DISCOVERY_ARCHIVE_SHA256 is required}
snapshot_id=${Q66_ANALYSIS_SNAPSHOT_ID:?Q66_ANALYSIS_SNAPSHOT_ID is required}
snapshot_manifest_sha256=${Q66_ANALYSIS_SNAPSHOT_MANIFEST_SHA256:?Q66_ANALYSIS_SNAPSHOT_MANIFEST_SHA256 is required}
matrix_sha256=${Q66_DISCOVERY_MATRIX_SHA256:?Q66_DISCOVERY_MATRIX_SHA256 is required}
if [[ ! "${array_job_id}" =~ ^[0-9]+$ ]]; then
    printf 'invalid discovery array job ID: %s\n' "${array_job_id}" >&2
    exit 2
fi
if [[ ! "${archive_sha256}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid discovery archive SHA-256\n' >&2
    exit 2
fi
if [[ ! "${snapshot_manifest_sha256}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid analysis snapshot manifest SHA-256\n' >&2
    exit 2
fi
if [[ ! "${matrix_sha256}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid discovery matrix SHA-256\n' >&2
    exit 2
fi
if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    printf 'invalid analysis snapshot ID: %s\n' "${snapshot_id}" >&2
    exit 2
fi

archive=${project_root}/results/transfers/phase-1/phase-1-${array_job_id}.tar
snapshot_root=${project_root}/results/analysis-snapshots/${snapshot_id}
matrix=${snapshot_root}/research/requests/discovery/discovery-matrix-v1.json
phase_root=${project_root}/results/discovery/phase-1
results_root=${phase_root}/${array_job_id}
import_staging=${project_root}/results/import-staging/phase-1-${array_job_id}-${SLURM_JOB_ID}
analysis_root=${project_root}/results/discovery/analysis/phase-1/${SLURM_JOB_ID}
analysis_staging=${analysis_root}.staging
if [[ ! -f "${archive}" ]]; then
    printf 'discovery archive is missing: %s\n' "${archive}" >&2
    exit 2
fi
if [[ -e "${results_root}" && ! -d "${results_root}" ]]; then
    printf 'discovery result path exists but is not a directory\n' >&2
    exit 2
fi
if [[ -e "${import_staging}" || -e "${analysis_root}" \
    || -e "${analysis_staging}" ]]; then
    printf 'staging or analysis output already exists\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${archive}" | cut -d ' ' -f 1)" != "${archive_sha256}" ]]; then
    printf 'discovery archive checksum mismatch\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${snapshot_root}/snapshot-checksums.sha256" | cut -d ' ' -f 1)" \
    != "${snapshot_manifest_sha256}" ]]; then
    printf 'analysis snapshot manifest checksum mismatch\n' >&2
    exit 2
fi
(
    cd "${snapshot_root}"
    sha256sum --quiet --check snapshot-checksums.sha256
)
if [[ "$(sha256sum "${matrix}" | cut -d ' ' -f 1)" != "${matrix_sha256}" ]]; then
    printf 'discovery matrix checksum mismatch\n' >&2
    exit 2
fi
if ! cmp -s \
    "${snapshot_root}/research/database/surface_code_instances.jsonl" \
    "${project_root}/research/database/surface_code_instances.jsonl"; then
    printf 'live and analysis-snapshot instance databases differ\n' >&2
    exit 2
fi

export PYTHONPATH="${snapshot_root}/src"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export Q66_INSTANCE_FILE="${snapshot_root}/research/database/surface_code_instances.jsonl"
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
(
    cd "${snapshot_root}"
    "${project_root}/.venv-q66-v1/bin/python" -m pytest -q \
        tests/test_experiment_core.py \
        tests/test_discovery_contract.py \
        tests/test_confirmation_contract.py \
        tests/test_sensitivity_contract.py
)

while IFS= read -r member; do
    case "${member}" in
        /*|../*|*/../*|*/..)
            printf 'unsafe archive member: %s\n' "${member}" >&2
            exit 2
            ;;
    esac
    case "${member}" in
        "${array_job_id}"|"${array_job_id}/"|"${array_job_id}/"*) ;;
        *)
            printf 'archive member outside phase root: %s\n' "${member}" >&2
            exit 2
            ;;
    esac
done < <(tar -tf "${archive}")

if [[ -d "${results_root}" ]]; then
    shopt -s nullglob
    result_entries=("${results_root}"/*)
    if (( ${#result_entries[@]} != 280 )); then
        printf 'existing discovery import is not exactly 280 groups\n' >&2
        exit 2
    fi
    for (( group_index = 0; group_index < 280; group_index++ )); do
        printf -v expected_group 'group-%03d' "${group_index}"
        if [[ ! -d "${results_root}/${expected_group}" ]]; then
            printf 'existing discovery import is missing %s\n' \
                "${expected_group}" >&2
            exit 2
        fi
    done
else
    mkdir -p "${import_staging}" "${phase_root}"
    tar --no-same-owner --no-same-permissions \
        -xf "${archive}" -C "${import_staging}"
    shopt -s nullglob
    import_entries=("${import_staging}"/*)
    if (( ${#import_entries[@]} != 1 )) \
        || [[ ! -d "${import_staging}/${array_job_id}" ]]; then
        printf 'imported archive does not contain one phase root\n' >&2
        exit 2
    fi
    mv "${import_staging}/${array_job_id}" "${results_root}"
    rmdir "${import_staging}"
fi

cd "${snapshot_root}"
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.discovery analyze \
    --matrix "${matrix}" \
    --latest-spec "${matrix}" \
    --latest-results "${results_root}" \
    --out "${analysis_staging}" \
    --bootstrap-resamples 20000
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.discovery \
    continuation-bundle-summary \
    --plan "${analysis_staging}/continuation-plan.json" \
    > "${analysis_staging}/continuation-bundles.json"
(
    cd "${analysis_staging}"
    sha256sum continuation-bundles.json \
        > continuation-bundles.json.sha256
)
mv "${analysis_staging}" "${analysis_root}"
sha256sum "${analysis_root}/analysis-checksums.sha256"
