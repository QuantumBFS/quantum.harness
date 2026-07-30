#!/usr/bin/env bash
#SBATCH --job-name=q66-dev-score
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=score-dev-validator-%j.out
#SBATCH --error=score-dev-validator-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
validator_root=${Q66_VALIDATOR_ROOT:-${project_root}}
array_job_id=${Q66_DEV_ARRAY_JOB_ID:?Q66_DEV_ARRAY_JOB_ID is required}
matrix=${Q66_DEV_MATRIX:-${validator_root}/research/requests/validator/dev-matrix-v1.json}
results_root="${project_root}/results/validator/dev/${array_job_id}"
out="${project_root}/results/validator/scores/${SLURM_JOB_ID}.json"
export PYTHONPATH="${validator_root}/src"
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.dev_score \
    --matrix "${matrix}" \
    --results-root "${results_root}" \
    --out "${out}"
