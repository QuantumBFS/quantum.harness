#!/usr/bin/env bash
#SBATCH --job-name=q66-discovery-next
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --requeue
#SBATCH --output=discovery-next-%A_%a.out
#SBATCH --error=discovery-next-%A_%a.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
research_root=${Q66_RESEARCH_ROOT:-${project_root}}
plan=${Q66_DISCOVERY_CONTINUATION_PLAN:?Q66_DISCOVERY_CONTINUATION_PLAN is required}
phase_index=${Q66_DISCOVERY_PHASE_INDEX:?Q66_DISCOVERY_PHASE_INDEX is required}
phase_root="${project_root}/results/discovery/phase-${phase_index}"
output_root="${phase_root}/${SLURM_ARRAY_JOB_ID}"
export PYTHONPATH="${research_root}/src"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.discovery \
    run-continuation-bundle \
    --plan "${plan}" \
    --bundle-index "${SLURM_ARRAY_TASK_ID}" \
    --output-root "${output_root}"
