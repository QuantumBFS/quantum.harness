#!/usr/bin/env bash
#SBATCH --job-name=q66-discovery-contract
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=test-discovery-contract-%j.out
#SBATCH --error=test-discovery-contract-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
export PYTHONPATH="${project_root}/src"
database_root="${project_root}/research/database"
export Q66_INSTANCE_FILE="${database_root}/surface_code_instances.jsonl"
"${project_root}/.venv-q66-v1/bin/python" -m pytest -q \
    "${project_root}/tests/test_discovery_contract.py" \
    "${project_root}/tests/test_dev_validator_contract.py"
