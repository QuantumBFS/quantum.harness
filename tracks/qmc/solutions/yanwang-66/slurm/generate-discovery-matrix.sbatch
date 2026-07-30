#!/usr/bin/env bash
#SBATCH --job-name=q66-matrix
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=generate-discovery-matrix-%j.out
#SBATCH --error=generate-discovery-matrix-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
source_commit=${Q66_SOURCE_COMMIT:?Q66_SOURCE_COMMIT is required}
environment_lock_sha256=${Q66_ENVIRONMENT_LOCK_SHA256:?Q66_ENVIRONMENT_LOCK_SHA256 is required}
export PYTHONPATH="${project_root}/src"

"${project_root}/.venv-q66-v1/bin/python" -m reload_qec.matrix generate \
    --families "${project_root}/research/database/benchmark_families.json" \
    --instances "${project_root}/research/database/surface_code_instances.jsonl" \
    --source-commit "${source_commit}" \
    --environment-lock-sha256 "${environment_lock_sha256}" \
    --shots 20000 \
    --shard-size 4096 \
    --out "${project_root}/research/requests/discovery/discovery-matrix-v1.json"
