#!/bin/bash
#SBATCH --job-name=qgeom-susy-N14-seal-v7
#SBATCH --account=giggleliu
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail
umask 0002

PROJECT_ROOT="${QGEOM_REMOTE_ROOT:-/work/share/giggleliu/Chaos-of-Quantum-Geometry}"
export PATH="/public/software/apps/anaconda3/2023.09/bin:$PATH"
export LC_ALL=C
export LANG=C
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONPATH="$PROJECT_ROOT/01_task_folder/task_05/script"

cd "$PROJECT_ROOT/01_task_folder/task_05/script"
mkdir -p logs output
python3 -u analyze_susy_hodge_geometric_eth_v7.py predict --null-replicates 2000
sha256sum output/susy_hodge_v7_N14_prediction.json
echo "prediction sealed; stop here for independent inspection"
