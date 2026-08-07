#!/usr/bin/env bash
#SBATCH --job-name=q66-analyze-next
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=analyze-discovery-next-%j.out
#SBATCH --error=analyze-discovery-next-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
snapshot_id=${Q66_ANALYSIS_SNAPSHOT_ID:?Q66_ANALYSIS_SNAPSHOT_ID is required}
snapshot_manifest_sha256=${Q66_ANALYSIS_SNAPSHOT_MANIFEST_SHA256:?Q66_ANALYSIS_SNAPSHOT_MANIFEST_SHA256 is required}
matrix_sha256=${Q66_DISCOVERY_MATRIX_SHA256:?Q66_DISCOVERY_MATRIX_SHA256 is required}
phase_index=${Q66_DISCOVERY_PHASE_INDEX:?Q66_DISCOVERY_PHASE_INDEX is required}
array_job_id=${Q66_DISCOVERY_ARRAY_JOB_ID:?Q66_DISCOVERY_ARRAY_JOB_ID is required}
latest_plan=${Q66_DISCOVERY_LATEST_PLAN:?Q66_DISCOVERY_LATEST_PLAN is required}
latest_plan_sha256=${Q66_DISCOVERY_LATEST_PLAN_SHA256:?Q66_DISCOVERY_LATEST_PLAN_SHA256 is required}
previous_analysis=${latest_plan%/continuation-plan.json}
if [[ "${previous_analysis}" == "${latest_plan}" ]]; then
    printf 'latest plan path does not identify its analysis root\n' >&2
    exit 2
fi

if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    printf 'invalid analysis snapshot ID: %s\n' "${snapshot_id}" >&2
    exit 2
fi
for checksum in \
    "${snapshot_manifest_sha256}" \
    "${matrix_sha256}" \
    "${latest_plan_sha256}"; do
    if [[ ! "${checksum}" =~ ^[0-9a-f]{64}$ ]]; then
        printf 'invalid SHA-256 value\n' >&2
        exit 2
    fi
done
if [[ ! "${phase_index}" =~ ^([2-9]|[1-9][0-9]+)$ ]]; then
    printf 'invalid continuation phase index: %s\n' "${phase_index}" >&2
    exit 2
fi
if [[ ! "${array_job_id}" =~ ^[0-9]+$ ]]; then
    printf 'invalid discovery array job ID: %s\n' "${array_job_id}" >&2
    exit 2
fi
case "${latest_plan}" in
    "${project_root}"/results/discovery/analysis/phase-*/*/continuation-plan.json) ;;
    *)
        printf 'latest plan is outside a discovery analysis root: %s\n' \
            "${latest_plan}" >&2
        exit 2
        ;;
esac

snapshot_root=${project_root}/results/analysis-snapshots/${snapshot_id}
matrix=${project_root}/research/requests/discovery/discovery-matrix-v1.json
latest_results=${project_root}/results/discovery/phase-${phase_index}/${array_job_id}
analysis_root=${project_root}/results/discovery/analysis/phase-${phase_index}/${SLURM_JOB_ID}
if [[ ! -d "${latest_results}" ]]; then
    printf 'latest continuation results are missing: %s\n' "${latest_results}" >&2
    exit 2
fi
if [[ ! -f "${latest_plan}" ]]; then
    printf 'latest continuation plan is missing: %s\n' "${latest_plan}" >&2
    exit 2
fi
if [[ -e "${analysis_root}" ]]; then
    printf 'analysis output already exists: %s\n' "${analysis_root}" >&2
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
if [[ "$(sha256sum "${latest_plan}" | cut -d ' ' -f 1)" \
    != "${latest_plan_sha256}" ]]; then
    printf 'latest continuation plan checksum mismatch\n' >&2
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
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
cd "${snapshot_root}"
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.discovery analyze \
    --matrix "${matrix}" \
    --previous-analysis "${previous_analysis}" \
    --latest-spec "${latest_plan}" \
    --latest-results "${latest_results}" \
    --out "${analysis_root}" \
    --bootstrap-resamples 20000
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.discovery \
    continuation-bundle-summary \
    --plan "${analysis_root}/continuation-plan.json" \
    > "${analysis_root}/continuation-bundles.json"
sha256sum "${analysis_root}/continuation-bundles.json" \
    > "${analysis_root}/continuation-bundles.json.sha256"
