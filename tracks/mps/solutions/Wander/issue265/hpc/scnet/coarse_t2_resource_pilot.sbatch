#!/usr/bin/env bash
#SBATCH --job-name=kharkov-c256-t2
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/coarse-t2-%j.out
#SBATCH --error=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/coarse-t2-%j.err

set -euo pipefail
unset LC_ALL
export LANG=C

source /usr/share/Modules/init/bash
module purge
module load anaconda3/2023.09

ROOT=/work/share/giggleliu/cfys01/kharkov_burgers_20260729
SOURCE="$ROOT/source"
PYTHON="$ROOT/env/tenpy-py311/bin/python"
OUTPUT="$ROOT/data/preflight/amp_mu005_up__coarse_t2.npz"

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
  --L 256 \
  --dt 0.05 \
  --chi-max 256 \
  --truncation-cutoff 1e-8 \
  --t-max 2.0 \
  --output-dt 0.2 \
  --output "$OUTPUT" \
  --checkpoint-every 1 \
  --overwrite

