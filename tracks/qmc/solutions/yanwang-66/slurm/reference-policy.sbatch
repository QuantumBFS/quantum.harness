#!/usr/bin/env bash
#SBATCH --job-name=q66-policy-oracle
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=reference-policy-%j.out
#SBATCH --error=reference-policy-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
module load anaconda3/2023.09
python3 "${project_root}/research/reference/policy_oracle.py" \
    --fixtures "${project_root}/research/database/policy_cases.jsonl"
