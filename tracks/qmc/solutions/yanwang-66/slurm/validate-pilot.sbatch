#!/usr/bin/env bash
#SBATCH --job-name=q66-pilot-validate
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=validate-pilot-%j.out
#SBATCH --error=validate-pilot-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
pilot_job_id=${PILOT_JOB_ID:?PILOT_JOB_ID must name the completed pilot job}
pilot_root="${project_root}/results/pilot/${pilot_job_id}"
export PYTHONPATH="${project_root}/src"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.validate_artifacts \
    --pilot-root "${pilot_root}" \
    --request-root "${project_root}/research/requests/pilot" \
    --out "${pilot_root}/validation-report.json"
