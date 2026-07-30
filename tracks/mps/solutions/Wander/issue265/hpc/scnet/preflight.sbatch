#!/usr/bin/env bash
#SBATCH --job-name=kharkov-preflight
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:30:00
#SBATCH --output=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/preflight-%j.out
#SBATCH --error=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/preflight-%j.err

set -euo pipefail
unset LC_ALL
export LANG=C

source /usr/share/Modules/init/bash
module purge
module load anaconda3/2023.09

ROOT=/work/share/giggleliu/cfys01/kharkov_burgers_20260729
SOURCE="$ROOT/source"
PYTHON="$ROOT/env/tenpy-py311/bin/python"
OUTPUT="$ROOT/data/preflight/amp_mu005_up__smoke.npz"

export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK}"

mkdir -p "$ROOT/data/preflight" "$ROOT/logs"
cd "$SOURCE"

/usr/bin/time -v "$PYTHON" scripts/run_tenpy_research_job.py \
  --manifest "$SOURCE/results_research_program/manifest.json" \
  --job-id amp_mu005_up__convergence__coarse \
  --smoke \
  --output "$OUTPUT" \
  --checkpoint-every 1 \
  --overwrite

