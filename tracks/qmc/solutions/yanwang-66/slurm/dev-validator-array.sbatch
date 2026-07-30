#!/usr/bin/env bash
#SBATCH --job-name=q66-dev-validator
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --array=0-15%4
#SBATCH --output=dev-validator-%A_%a.out
#SBATCH --error=dev-validator-%A_%a.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
validator_root=${Q66_VALIDATOR_ROOT:-${project_root}}
matrix=${Q66_DEV_MATRIX:-${validator_root}/research/requests/validator/dev-matrix-v1.json}
candidate_root=${Q66_CANDIDATE_ROOT:?Q66_CANDIDATE_ROOT is required}
candidate_id=${Q66_CANDIDATE_ID:?Q66_CANDIDATE_ID is required}
output_root="${project_root}/results/validator/dev/${SLURM_ARRAY_JOB_ID}"
export PYTHONPATH="${validator_root}/src"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.dev_validator \
    --matrix "${matrix}" \
    --candidate-root "${candidate_root}" \
    --candidate-id "${candidate_id}" \
    --output-root "${output_root}" \
    --timeout-seconds 2700
