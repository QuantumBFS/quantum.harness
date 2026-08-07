#!/usr/bin/env bash
#SBATCH --job-name=q66-graph-oracle
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=reference-graph-%j.out
#SBATCH --error=reference-graph-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
"${project_root}/.venv-q66-v1/bin/python" \
    "${project_root}/research/reference/graph_oracle.py" \
    --instances "${project_root}/research/database/surface_code_instances.jsonl"
