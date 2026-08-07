#!/usr/bin/env bash
#SBATCH --job-name=q66-pilot-analysis
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=analyze-pilot-%j.out
#SBATCH --error=analyze-pilot-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
pilot_job_id=${PILOT_JOB_ID:?PILOT_JOB_ID must name the completed pilot job}
pilot_root="${project_root}/results/pilot/${pilot_job_id}"
comparison_root="${pilot_root}/comparisons"
export PYTHONPATH="${project_root}/src"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
mkdir -p "${comparison_root}"

for candidate in 01-immediate 02-periodic-d 03-threshold-005; do
    "${project_root}/.venv-q66-v1/bin/python" -m reload_qec.analyze \
        --baseline "${pilot_root}/00-none" \
        --candidate "${pilot_root}/${candidate}" \
        --out "${comparison_root}/${candidate}-vs-none.json"
done
