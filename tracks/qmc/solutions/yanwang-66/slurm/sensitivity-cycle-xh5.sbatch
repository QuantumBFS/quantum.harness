#!/usr/bin/env bash
#SBATCH --job-name=q66-sensitivity-cycle
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --mem=480G
#SBATCH --time=14:00:00
#SBATCH --deadline=2026-07-30T13:30:00
#SBATCH --output=sensitivity-cycle-%j.out
#SBATCH --error=sensitivity-cycle-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
snapshot_id=${Q66_SENSITIVITY_SNAPSHOT_ID:?Q66_SENSITIVITY_SNAPSHOT_ID is required}
snapshot_manifest_sha256=${Q66_SENSITIVITY_SNAPSHOT_MANIFEST_SHA256:?Q66_SENSITIVITY_SNAPSHOT_MANIFEST_SHA256 is required}
candidate_root=${Q66_SENSITIVITY_CANDIDATE_ROOT:?Q66_SENSITIVITY_CANDIDATE_ROOT is required}
instance_file=${Q66_SENSITIVITY_INSTANCE_FILE:?Q66_SENSITIVITY_INSTANCE_FILE is required}
discovery_analysis=${Q66_DISCOVERY_FINAL_ANALYSIS:?Q66_DISCOVERY_FINAL_ANALYSIS is required}
discovery_matrix=${Q66_DISCOVERY_MATRIX:?Q66_DISCOVERY_MATRIX is required}
source_commit=0a73ba334a4b85403634e710f3d768ef8831d16d
environment_lock_sha256=f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8
instance_sha256=25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751
family_sha256=ff5fddd9b6019b06a61fe43e59c50fc385ec29921351ff815a2d7d233affa900
snapshot_root=${project_root}/results/analysis-snapshots/${snapshot_id}
snapshot_manifest=${snapshot_root}/snapshot-checksums.sha256
family_file=${snapshot_root}/research/database/cost_sensitivity_families.json
matrix_root=${project_root}/results/sensitivity/matrices
matrix=${matrix_root}/cost-sensitivity-${SLURM_JOB_ID}.json
matrix_staging=${matrix}.staging
initial_root=${project_root}/results/sensitivity/initial/${SLURM_JOB_ID}
initial_analysis=${project_root}/results/sensitivity/analysis/phase-1/${SLURM_JOB_ID}
cycle_root=${project_root}/results/sensitivity/cycles/${SLURM_JOB_ID}
final_analysis=${project_root}/results/sensitivity/analysis/final/${SLURM_JOB_ID}

if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ \
    || ! "${snapshot_manifest_sha256}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid cost-sensitivity snapshot input\n' >&2
    exit 2
fi
for input in \
    "${snapshot_manifest}" \
    "${family_file}" \
    "${instance_file}" \
    "${discovery_matrix}" \
    "${discovery_analysis}/analysis-summary.json" \
    "${discovery_analysis}/analysis-checksums.sha256"; do
    if [[ ! -f "${input}" ]]; then
        printf 'cost-sensitivity input is missing: %s\n' "${input}" >&2
        exit 2
    fi
done
if [[ ! -d "${candidate_root}" ]]; then
    printf 'cost-sensitivity candidate is missing: %s\n' "${candidate_root}" >&2
    exit 2
fi
for output in \
    "${matrix}" \
    "${matrix_staging}" \
    "${initial_root}" \
    "${initial_analysis}" \
    "${cycle_root}" \
    "${final_analysis}"; do
    if [[ -e "${output}" ]]; then
        printf 'cost-sensitivity output already exists: %s\n' "${output}" >&2
        exit 2
    fi
done
if [[ "$(sha256sum "${snapshot_manifest}" | cut -d ' ' -f 1)" \
    != "${snapshot_manifest_sha256}" ]]; then
    printf 'cost-sensitivity snapshot manifest checksum mismatch\n' >&2
    exit 2
fi
(
    cd "${snapshot_root}"
    sha256sum --quiet --check snapshot-checksums.sha256
)
if [[ "$(sha256sum "${instance_file}" | cut -d ' ' -f 1)" \
    != "${instance_sha256}" \
    || "$(sha256sum "${family_file}" | cut -d ' ' -f 1)" \
    != "${family_sha256}" ]]; then
    printf 'cost-sensitivity frozen input checksum mismatch\n' >&2
    exit 2
fi
(
    cd "${discovery_analysis}"
    sha256sum --quiet --check analysis-checksums.sha256
)

export PYTHONPATH=${snapshot_root}/src
export Q66_INSTANCE_FILE=${instance_file}
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.sensitivity_gate \
    --discovery-analysis "${discovery_analysis}" \
    --discovery-matrix "${discovery_matrix}"

(
    cd "${snapshot_root}"
    "${project_root}/.venv-q66-v1/bin/python" -m pytest -q \
        tests/test_experiment_core.py \
        tests/test_sensitivity_contract.py
)
mkdir -p "${matrix_root}"
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.sensitivity \
    --families "${family_file}" \
    --instances "${instance_file}" \
    --source-commit "${source_commit}" \
    --environment-lock-sha256 "${environment_lock_sha256}" \
    --shard-size 4096 \
    --out "${matrix_staging}"
mv "${matrix_staging}" "${matrix}"
sha256sum "${matrix}" > "${matrix}.sha256"

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.sensitivity_run \
    --matrix "${matrix}" \
    --candidate-root "${candidate_root}" \
    --output-root "${initial_root}" \
    --simulation-workers "${SLURM_CPUS_PER_TASK}" \
    --validation-workers 32 \
    --timeout-seconds 10800
(
    cd "${initial_root}"
    sha256sum --quiet --check result-checksums.sha256
)

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.sensitivity_analysis \
    --sensitivity-matrix "${matrix}" \
    --sensitivity-results "${initial_root}" \
    --discovery-matrix "${discovery_matrix}" \
    --discovery-analysis "${discovery_analysis}" \
    --out "${initial_analysis}" \
    --bootstrap-resamples 20000
(
    cd "${initial_analysis}"
    sha256sum --quiet --check analysis-checksums.sha256
)

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.sensitivity_cycle \
    --matrix "${matrix}" \
    --initial-results "${initial_root}" \
    --initial-analysis "${initial_analysis}" \
    --discovery-matrix "${discovery_matrix}" \
    --discovery-analysis "${discovery_analysis}" \
    --candidate-root "${candidate_root}" \
    --output-root "${cycle_root}" \
    --final-analysis-root "${final_analysis}" \
    --workers "${SLURM_CPUS_PER_TASK}" \
    --validation-workers 32 \
    --timeout-seconds 10800 \
    --bootstrap-resamples 20000
(
    cd "${final_analysis}"
    sha256sum --quiet --check analysis-checksums.sha256
)
sha256sum "${cycle_root}/cycle-summary.json"
