#!/usr/bin/env bash
#SBATCH --job-name=q66-pilot
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=pilot-experiment-%j.out
#SBATCH --error=pilot-experiment-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
run_root="${project_root}/results/pilot/${SLURM_JOB_ID}"
export PYTHONPATH="${project_root}/src"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONHASHSEED=0
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
mkdir -p "${run_root}"

requests=(
    00-none
    01-immediate
    02-periodic-d
    03-threshold-005
)

for request_name in "${requests[@]}"; do
    "${project_root}/.venv-q66-v1/bin/python" -m reload_qec.candidate \
        --request "${project_root}/research/requests/pilot/${request_name}.json" \
        --out "${run_root}/${request_name}"
done
