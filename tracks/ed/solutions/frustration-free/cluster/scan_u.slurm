#!/bin/bash
#SBATCH --job-name=hubbard-pump-u
#SBATCH --output=scan_u_%j.out
#SBATCH --error=scan_u_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=24:00:00

set -euo pipefail

cd "${SLURM_SUBMIT_DIR}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"

PUMP_PYTHON="${PUMP_PYTHON:-python3}"
exec "${PUMP_PYTHON}" scripts/run.py scan-u --config configs/default.yaml "$@"
