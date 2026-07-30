#!/usr/bin/env bash
#SBATCH --job-name=q66-core-tests
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=test-experiment-core-%j.out
#SBATCH --error=test-experiment-core-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
export PYTHONPATH="${project_root}/src"
export Q66_INSTANCE_FILE="${project_root}/research/database/surface_code_instances.jsonl"
"${project_root}/.venv-q66-v1/bin/python" -m pytest -q \
    "${project_root}/tests/test_experiment_core.py"
