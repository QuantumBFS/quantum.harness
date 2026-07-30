#!/usr/bin/env bash
#SBATCH --job-name=kharkov-two-mode-cv
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=7-00:00:00
#SBATCH --array=0-26
#SBATCH --output=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/two-mode-cv-%A_%a.out
#SBATCH --error=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/two-mode-cv-%A_%a.err

set -euo pipefail
unset LC_ALL
export LANG=C

source /usr/share/Modules/init/bash
module purge
module load anaconda3/2023.09

KH_ROOT=/work/share/giggleliu/cfys01/kharkov_burgers_20260729
KH_SOURCE="$KH_ROOT/source"
KH_PYTHON="$KH_ROOT/env/tenpy-py311/bin/python"

export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OPENBLAS_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export MKL_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export NUMEXPR_NUM_THREADS="$SLURM_CPUS_PER_TASK"

mkdir -p "$KH_ROOT/logs"
cd "$KH_SOURCE"
PYTHONPATH=. "$KH_PYTHON" scripts/run_two_mode_cross_validation.py \
  --action run \
  --task-index "$SLURM_ARRAY_TASK_ID" \
  --data-root "$KH_ROOT/data/research/raw" \
  --convergence-audit "$KH_ROOT/jobs/convergence_audit.json" \
  --reuse-attestations "$KH_ROOT/jobs/production_v2_reuse_attestations.json"
