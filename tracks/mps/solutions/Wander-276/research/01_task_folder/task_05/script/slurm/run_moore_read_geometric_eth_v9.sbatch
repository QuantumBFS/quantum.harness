#!/bin/bash
#SBATCH --job-name=qgeom-mr-v9
#SBATCH --account=giggleliu
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=118G
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail
umask 0002

MODE="${1:?usage: sbatch run_moore_read_geometric_eth_v9.sbatch kernel|panel N [PANEL]}"
N="${2:?usage: sbatch run_moore_read_geometric_eth_v9.sbatch kernel|panel N [PANEL]}"
PROJECT_ROOT="${QGEOM_REMOTE_ROOT:?export the shen/acamtw70yu runtime as QGEOM_REMOTE_ROOT}"

export PATH="/public/software/apps/anaconda3/2023.09/bin:$PATH"
export LC_ALL=C
export LANG=C
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONPATH="$PROJECT_ROOT/01_task_folder/task_05/script"

cd "$PROJECT_ROOT/01_task_folder/task_05/script"
mkdir -p logs output/moore_read_v9/kernels output/moore_read_v9/panels

case "$MODE" in
    kernel)
        python3 -u run_moore_read_geometric_eth_v9.py --prepare-kernel "$N"
        ;;
    panel)
        PANEL="${3:-${SLURM_ARRAY_TASK_ID:?panel mode requires PANEL or a Slurm array index}}"
        python3 -u run_moore_read_geometric_eth_v9.py --panel "$N" "$PANEL"
        ;;
    *)
        echo "unknown mode: $MODE" >&2
        exit 2
        ;;
esac
