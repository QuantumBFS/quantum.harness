#!/bin/bash
#SBATCH --job-name=qgeom-susy-N14-v7
#SBATCH --account=giggleliu
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail
umask 0002

ARRAY_ID="${SLURM_ARRAY_TASK_ID:?submit with an N14 response array}"
WORKER_COUNT="${N14_RESPONSE_WORKERS:-16}"
PROJECT_ROOT="${QGEOM_REMOTE_ROOT:-/work/share/giggleliu/Chaos-of-Quantum-Geometry}"

if [[ "$WORKER_COUNT" -lt 1 || "$ARRAY_ID" -ge "$WORKER_COUNT" ]]; then
    echo "invalid N14 response worker mapping" >&2
    exit 2
fi

export PATH="/public/software/apps/anaconda3/2023.09/bin:$PATH"
export LC_ALL=C
export LANG=C
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONPATH="$PROJECT_ROOT/01_task_folder/task_05/script"

cd "$PROJECT_ROOT/01_task_folder/task_05/script"
mkdir -p logs output/susy_hodge_v7_checkpoints output/susy_hodge_v7_null_banks

# Forty-eight realization jobs (24 per sector), quota-safely bundled into 16
# workers.  This stage writes responses only; null banks run independently.
for ((LOGICAL_ID=ARRAY_ID; LOGICAL_ID<48; LOGICAL_ID+=WORKER_COUNT)); do
    SECTOR_INDEX=$((LOGICAL_ID / 24))
    REALIZATION=$((LOGICAL_ID % 24))
    case "$SECTOR_INDEX" in
        0) SECTOR="central" ;;
        1) SECTOR="adjacent" ;;
        *) exit 2 ;;
    esac

    echo "logical_task=${LOGICAL_ID} N=14 sector=${SECTOR} realization=${REALIZATION}"
    python3 -u run_susy_hodge_geometric_eth_v7.py realization \
        --N 14 \
        --sector "$SECTOR" \
        --realization "$REALIZATION"

    for PANEL_KIND in sparse isotropic; do
        python3 -u run_susy_hodge_geometric_eth_v7.py panel \
            --N 14 \
            --sector "$SECTOR" \
            --realization "$REALIZATION" \
            --panel-kind "$PANEL_KIND"
    done
done
