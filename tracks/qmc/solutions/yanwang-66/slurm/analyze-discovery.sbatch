#!/usr/bin/env bash
#SBATCH --job-name=q66-discovery-analysis
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --output=analyze-discovery-%j.out
#SBATCH --error=analyze-discovery-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
research_root=${Q66_RESEARCH_ROOT:-${project_root}}
matrix=${Q66_DISCOVERY_MATRIX:-${research_root}/research/requests/discovery/discovery-matrix-v1.json}
snapshot_manifest_sha256=${Q66_ANALYSIS_SNAPSHOT_MANIFEST_SHA256:?Q66_ANALYSIS_SNAPSHOT_MANIFEST_SHA256 is required}
matrix_sha256=${Q66_DISCOVERY_MATRIX_SHA256:?Q66_DISCOVERY_MATRIX_SHA256 is required}
instance_file=${Q66_INSTANCE_FILE:?Q66_INSTANCE_FILE is required}
instance_sha256=25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751
confirmation_family=${instance_file%/*}/confirmation_families.json
confirmation_family_sha256=33b4ce05177179be9036a40d5e28b66dd62219a543d391750bb28ef5b4c1635a
latest_spec=${Q66_DISCOVERY_LATEST_SPEC:?Q66_DISCOVERY_LATEST_SPEC is required}
latest_results=${Q66_DISCOVERY_LATEST_RESULTS:?Q66_DISCOVERY_LATEST_RESULTS is required}
analysis_phase=${Q66_DISCOVERY_ANALYSIS_PHASE:?Q66_DISCOVERY_ANALYSIS_PHASE is required}
analysis_root="${project_root}/results/discovery/analysis"
output_root="${analysis_root}/phase-${analysis_phase}/${SLURM_JOB_ID}"
output_staging=${output_root}.staging
snapshot_manifest=${research_root}/snapshot-checksums.sha256
if [[ ! "${snapshot_manifest_sha256}" =~ ^[0-9a-f]{64}$ \
    || ! "${matrix_sha256}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid discovery analysis checksum input\n' >&2
    exit 2
fi
if [[ ! "${analysis_phase}" =~ ^[1-9][0-9]*$ ]]; then
    printf 'invalid discovery analysis phase\n' >&2
    exit 2
fi
for input in \
    "${snapshot_manifest}" \
    "${matrix}" \
    "${latest_spec}" \
    "${instance_file}" \
    "${confirmation_family}"; do
    if [[ ! -f "${input}" ]]; then
        printf 'discovery analysis input is missing: %s\n' "${input}" >&2
        exit 2
    fi
done
if [[ ! -d "${latest_results}" ]]; then
    printf 'discovery result root is missing: %s\n' "${latest_results}" >&2
    exit 2
fi
if [[ -e "${output_root}" || -e "${output_staging}" ]]; then
    printf 'discovery analysis output already exists\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${snapshot_manifest}" | cut -d ' ' -f 1)" \
    != "${snapshot_manifest_sha256}" ]]; then
    printf 'discovery analysis snapshot checksum mismatch\n' >&2
    exit 2
fi
(
    cd "${research_root}"
    sha256sum --quiet --check snapshot-checksums.sha256
)
if [[ "$(sha256sum "${matrix}" | cut -d ' ' -f 1)" \
    != "${matrix_sha256}" ]]; then
    printf 'discovery matrix checksum mismatch\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${instance_file}" | cut -d ' ' -f 1)" \
    != "${instance_sha256}" \
    || "$(sha256sum "${confirmation_family}" | cut -d ' ' -f 1)" \
    != "${confirmation_family_sha256}" ]]; then
    printf 'discovery analysis contract database checksum mismatch\n' >&2
    exit 2
fi
export PYTHONPATH="${research_root}/src"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

(
    cd "${research_root}"
    "${project_root}/.venv-q66-v1/bin/python" -m pytest -q \
        tests/test_experiment_core.py \
        tests/test_discovery_contract.py \
        tests/test_confirmation_contract.py \
        tests/test_sensitivity_contract.py
)
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.discovery analyze \
    --matrix "${matrix}" \
    --latest-spec "${latest_spec}" \
    --latest-results "${latest_results}" \
    --out "${output_staging}" \
    --bootstrap-resamples 20000
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.discovery \
    continuation-bundle-summary \
    --plan "${output_staging}/continuation-plan.json" \
    > "${output_staging}/continuation-bundles.json"
(
    cd "${output_staging}"
    sha256sum continuation-bundles.json \
        > continuation-bundles.json.sha256
    sha256sum --quiet --check analysis-checksums.sha256
    sha256sum --quiet --check continuation-bundles.json.sha256
)
mv "${output_staging}" "${output_root}"
sha256sum "${output_root}/analysis-checksums.sha256"
