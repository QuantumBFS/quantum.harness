#!/usr/bin/env bash
#SBATCH --job-name=q66-discovery-prep
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=prepare-discovery-%j.out
#SBATCH --error=prepare-discovery-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
validator_root=${Q66_VALIDATOR_ROOT:?Q66_VALIDATOR_ROOT is required}
array_job_id=${Q66_DEV_ARRAY_JOB_ID:?Q66_DEV_ARRAY_JOB_ID is required}
score_job_id=${Q66_DEV_SCORE_JOB_ID:?Q66_DEV_SCORE_JOB_ID is required}
source_commit=${Q66_SOURCE_COMMIT:?Q66_SOURCE_COMMIT is required}
environment_lock_sha256=${Q66_ENVIRONMENT_LOCK_SHA256:?Q66_ENVIRONMENT_LOCK_SHA256 is required}
snapshot_id=${Q66_DISCOVERY_SNAPSHOT_ID:?Q66_DISCOVERY_SNAPSHOT_ID is required}
dev_matrix="${validator_root}/research/requests/validator/dev-matrix-v1.json"
dev_results="${project_root}/results/validator/dev/${array_job_id}"
dev_score="${project_root}/results/validator/scores/${score_job_id}.json"
resource_report="${project_root}/results/validator/resource-gates/${SLURM_JOB_ID}.json"
discovery_matrix_relative=research/requests/discovery/discovery-matrix-v1.json
discovery_matrix="${project_root}/${discovery_matrix_relative}"
export PYTHONDONTWRITEBYTECODE=1

if [[ ! -f "${validator_root}/snapshot-checksums.sha256" ]]; then
    printf 'validator snapshot checksum manifest is missing: %s\n' "${validator_root}" >&2
    exit 2
fi
(
    cd "${validator_root}"
    sha256sum --quiet -c snapshot-checksums.sha256
)

export PYTHONPATH="${project_root}/src"
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.resource_gate \
    --matrix "${dev_matrix}" \
    --results-root "${dev_results}" \
    --score "${dev_score}" \
    --out "${resource_report}" \
    --source-commit "${source_commit}" \
    --environment-lock-sha256 "${environment_lock_sha256}"
if ! grep -q '"discovery_authorized": true' "${resource_report}"; then
    printf 'resource gate did not authorize discovery: %s\n' "${resource_report}" >&2
    exit 3
fi

export PYTHONPATH="${validator_root}/src"
"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.matrix generate \
    --families "${project_root}/research/database/benchmark_families.json" \
    --instances "${project_root}/research/database/surface_code_instances.jsonl" \
    --source-commit "${source_commit}" \
    --environment-lock-sha256 "${environment_lock_sha256}" \
    --shots 20000 \
    --shard-size 4096 \
    --out "${discovery_matrix}"

export Q66_SNAPSHOT_ID="${snapshot_id}"
export Q66_SNAPSHOT_MATRIX_RELATIVE="${discovery_matrix_relative}"
export Q66_SNAPSHOT_SOURCE_ROOT="${validator_root}"
bash "${project_root}/slurm/stage-validator-snapshot.sbatch"
