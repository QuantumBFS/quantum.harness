#!/bin/bash
set -euo pipefail

N="${1:?usage: submit_moore_read_geometric_eth_v9.sh N}"
case "$N" in
    4|6|8) ;;
    *)
        echo "N must be an opened Moore--Read v9 production size: 4, 6, or 8" >&2
        exit 2
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${QGEOM_REMOTE_ROOT:?export the shen/acamtw70yu v9 runtime as QGEOM_REMOTE_ROOT}"
SLURM_ACCOUNT="${QGEOM_SLURM_ACCOUNT:-giggleliu}"
PANEL_CONCURRENCY="${MOORE_READ_PANEL_CONCURRENCY:-4}"

cd "$SCRIPT_DIR"
mkdir -p logs "$PROJECT_ROOT/01_task_folder/task_05/script/output/moore_read_v9"

KERNEL_JOB=$(
    sbatch \
        --parsable \
        --account="$SLURM_ACCOUNT" \
        run_moore_read_geometric_eth_v9.sbatch kernel "$N"
)
PANEL_JOB=$(
    sbatch \
        --parsable \
        --account="$SLURM_ACCOUNT" \
        --dependency="afterok:${KERNEL_JOB}" \
        --array="0-23%${PANEL_CONCURRENCY}" \
        run_moore_read_geometric_eth_v9.sbatch panel "$N"
)
STRUCTURED_JOB=$(
    sbatch \
        --parsable \
        --account="$SLURM_ACCOUNT" \
        --dependency="afterok:${KERNEL_JOB}" \
        run_moore_read_geometric_eth_v9.sbatch panel "$N" -1
)

echo "kernel_job=${KERNEL_JOB}"
echo "panel_array_job=${PANEL_JOB}"
echo "structured_job=${STRUCTURED_JOB}"
