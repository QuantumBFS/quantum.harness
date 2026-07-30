#!/usr/bin/env bash
#SBATCH --job-name=q66-public-final-audit
#SBATCH --partition=dzagnormal
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --time=01:00:00
#SBATCH --deadline=2026-07-30T15:20:00
#SBATCH --output=public-final-audit-%j.out
#SBATCH --error=public-final-audit-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
snapshot_id=${Q66_FINAL_AUDIT_SNAPSHOT_ID:?Q66_FINAL_AUDIT_SNAPSHOT_ID is required}
snapshot_manifest_sha256=${Q66_FINAL_AUDIT_SNAPSHOT_MANIFEST_SHA256:?Q66_FINAL_AUDIT_SNAPSHOT_MANIFEST_SHA256 is required}
candidate_root=${Q66_FINAL_CANDIDATE_ROOT:?Q66_FINAL_CANDIDATE_ROOT is required}
discovery_analysis=${Q66_FINAL_DISCOVERY_ANALYSIS:?Q66_FINAL_DISCOVERY_ANALYSIS is required}
confirmation_analysis=${Q66_FINAL_CONFIRMATION_ANALYSIS:?Q66_FINAL_CONFIRMATION_ANALYSIS is required}
sensitivity_analysis=${Q66_FINAL_SENSITIVITY_ANALYSIS:?Q66_FINAL_SENSITIVITY_ANALYSIS is required}
negative_controls=${Q66_FINAL_NEGATIVE_CONTROLS:?Q66_FINAL_NEGATIVE_CONTROLS is required}
independent_evidence=${Q66_FINAL_INDEPENDENT_EVIDENCE:?Q66_FINAL_INDEPENDENT_EVIDENCE is required}
report=${Q66_FINAL_REPORT:?Q66_FINAL_REPORT is required}
science_gate=${Q66_FINAL_SCIENCE_GATE:?Q66_FINAL_SCIENCE_GATE is required}
holdout_spend=${Q66_HOLDOUT_SPEND:?Q66_HOLDOUT_SPEND is required}
snapshot_root=${project_root}/results/analysis-snapshots/${snapshot_id}
snapshot_manifest=${snapshot_root}/snapshot-checksums.sha256
output_root=${project_root}/results/final-audit/${SLURM_JOB_ID}

if [[ ! "${snapshot_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ \
    || ! "${snapshot_manifest_sha256}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid final-audit snapshot identity\n' >&2
    exit 2
fi
for input in \
    "${snapshot_manifest}" \
    "${negative_controls}" \
    "${independent_evidence}" \
    "${report}" \
    "${science_gate}"; do
    if [[ ! -f "${input}" ]]; then
        printf 'public final-audit input is missing: %s\n' "${input}" >&2
        exit 2
    fi
done
for directory in \
    "${candidate_root}" \
    "${discovery_analysis}" \
    "${confirmation_analysis}" \
    "${sensitivity_analysis}"; do
    if [[ ! -d "${directory}" ]]; then
        printf 'public final-audit directory is missing: %s\n' "${directory}" >&2
        exit 2
    fi
done
if [[ -e "${holdout_spend}" || -e "${output_root}" ]]; then
    printf 'holdout spend or public-audit output already exists\n' >&2
    exit 2
fi
if [[ "$(sha256sum "${snapshot_manifest}" | cut -d ' ' -f 1)" \
    != "${snapshot_manifest_sha256}" ]]; then
    printf 'final-audit snapshot manifest checksum mismatch\n' >&2
    exit 2
fi
(
    cd "${snapshot_root}"
    sha256sum --quiet --check snapshot-checksums.sha256
)

export PYTHONPATH=${snapshot_root}/src
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.final_audit \
    --candidate-root "${candidate_root}" \
    --discovery-analysis "${discovery_analysis}" \
    --confirmation-analysis "${confirmation_analysis}" \
    --sensitivity-analysis "${sensitivity_analysis}" \
    --negative-controls-report "${negative_controls}" \
    --independent-evidence "${independent_evidence}" \
    --report "${report}" \
    --science-gate "${science_gate}" \
    --holdout-spend "${holdout_spend}" \
    --out "${output_root}"
sha256sum --quiet --check "${output_root}/public-preflight.json.sha256"
sha256sum "${output_root}/public-preflight.json.sha256"
