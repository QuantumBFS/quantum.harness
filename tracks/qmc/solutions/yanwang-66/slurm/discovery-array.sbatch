#!/usr/bin/env bash
#SBATCH --job-name=q66-discovery
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --array=0-181%8
#SBATCH --output=discovery-%A_%a.out
#SBATCH --error=discovery-%A_%a.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
research_root=${Q66_RESEARCH_ROOT:-${project_root}}
matrix=${Q66_DISCOVERY_MATRIX:-${research_root}/research/requests/discovery/discovery-matrix-v1.json}
output_root="${project_root}/results/discovery/phase-1/${SLURM_ARRAY_JOB_ID}"
export PYTHONPATH="${research_root}/src"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy

task_index=${SLURM_ARRAY_TASK_ID}
if (( task_index < 18 )); then
    group_start=$((task_index * 4))
    group_stop=$((group_start + 4))
    if (( group_stop > 70 )); then
        group_stop=70
    fi
elif (( task_index < 42 )); then
    group_start=$((70 + (task_index - 18) * 3))
    group_stop=$((group_start + 3))
    if (( group_stop > 140 )); then
        group_stop=140
    fi
elif (( task_index < 112 )); then
    group_start=$((140 + task_index - 42))
    group_stop=$((group_start + 1))
elif (( task_index < 182 )); then
    group_start=$((210 + task_index - 112))
    group_stop=$((group_start + 1))
else
    printf 'bundle task index outside 0-181: %s\n' "${task_index}" >&2
    exit 2
fi

for ((group_index = group_start; group_index < group_stop; group_index++)); do
    "${project_root}/.venv-q66-v1/bin/python" -m reload_qec.matrix run-group \
        --matrix "${matrix}" \
        --group-index "${group_index}" \
        --output-root "${output_root}"
done
