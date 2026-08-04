#!/bin/bash
#SBATCH --job-name=qgeom-susy-pilot-v7
#SBATCH --account=giggleliu
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail
umask 0002

ARRAY_ID="${SLURM_ARRAY_TASK_ID:?submit with --array=0-7}"
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
mkdir -p logs output/susy_hodge_v7_checkpoints output/susy_hodge_v7_null_banks

# The remote account is often close to its submitted-job cap.  Preserve the
# registered 160 logical jobs but bundle them into eight quota-safe workers.
for ((TASK_ID=ARRAY_ID; TASK_ID<160; TASK_ID+=8)); do
    if [[ "$TASK_ID" -lt 96 ]]; then
        N=10
        COUNT=48
        LOCAL_ID="$TASK_ID"
    else
        N=12
        COUNT=32
        LOCAL_ID=$((TASK_ID - 96))
    fi

    SECTOR_INDEX=$((LOCAL_ID / COUNT))
    REALIZATION=$((LOCAL_ID % COUNT))
    case "$SECTOR_INDEX" in
        0) SECTOR="central" ;;
        1) SECTOR="adjacent" ;;
        *) exit 2 ;;
    esac

    echo "logical_task=${TASK_ID} N=${N} sector=${SECTOR} realization=${REALIZATION}"
    python3 -u run_susy_hodge_geometric_eth_v7.py realization \
        --N "$N" \
        --sector "$SECTOR" \
        --realization "$REALIZATION"

    for PANEL_KIND in sparse isotropic; do
        python3 -u run_susy_hodge_geometric_eth_v7.py panel \
            --N "$N" \
            --sector "$SECTOR" \
            --realization "$REALIZATION" \
            --panel-kind "$PANEL_KIND"
        python3 -u run_susy_hodge_null_bank_v7.py \
            --N "$N" \
            --sector "$SECTOR" \
            --realization "$REALIZATION" \
            --panel-kind "$PANEL_KIND" \
            --draws 128
    done
done
