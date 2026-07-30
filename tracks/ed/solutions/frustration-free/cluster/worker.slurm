#!/bin/bash
#SBATCH --partition=ihicnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=02:00:00
#SBATCH --requeue

set -euo pipefail

: "${SCAN_STAGE:?SCAN_STAGE is required}"
: "${SCAN_PYTHON:?SCAN_PYTHON is required}"
: "${SCAN_SOURCE_DIR:?SCAN_SOURCE_DIR is required}"
: "${SCAN_TASK_MAP:?SCAN_TASK_MAP is required}"
: "${SCAN_CHERN_DIR:?SCAN_CHERN_DIR is required}"
: "${SCAN_STATIC_DIR:?SCAN_STATIC_DIR is required}"
: "${SCAN_REFINED_DIR:?SCAN_REFINED_DIR is required}"
: "${SCAN_REALTIME_DIR:?SCAN_REALTIME_DIR is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

WORKER="$SCAN_SOURCE_DIR/scripts/cluster_worker.py"
L=${SCAN_L:-8}

case "$SCAN_STAGE" in
    static)
        arguments=(
            static
            --task-map "$SCAN_TASK_MAP"
            --task-id "$SLURM_ARRAY_TASK_ID"
            --L "$L"
            --delta0 "${SCAN_DELTA0:-0.9}"
            --Delta0 "${SCAN_CAPITAL_DELTA0:-3.0}"
            --chern-sizes 5 10
            --polarization-points "${SCAN_POLARIZATION_POINTS:-10}"
            --chern-dir "$SCAN_CHERN_DIR"
            --static-dir "$SCAN_STATIC_DIR"
        )
        if [[ -n ${SCAN_LEGACY_DIR:-} ]]; then
            arguments+=(--resume-dir "$SCAN_LEGACY_DIR")
        fi
        ;;
    refine)
        arguments=(
            refine
            --task-map "$SCAN_TASK_MAP"
            --task-id "$SLURM_ARRAY_TASK_ID"
            --static-dir "$SCAN_STATIC_DIR"
            --refined-dir "$SCAN_REFINED_DIR"
            --target-grid "${SCAN_REFINED_GRID:-20}"
        )
        ;;
    realtime)
        arguments=(
            realtime
            --task-map "$SCAN_TASK_MAP"
            --task-id "$SLURM_ARRAY_TASK_ID"
            --static-dir "$SCAN_STATIC_DIR"
            --realtime-dir "$SCAN_REALTIME_DIR"
            --initial-time-step "${SCAN_INITIAL_TIME_STEP:-0.05}"
            --charge-tolerance "${SCAN_CHARGE_TOLERANCE:-0.005}"
            --max-refinements "${SCAN_TIME_REFINEMENTS:-3}"
        )
        ;;
    *)
        echo "Unknown SCAN_STAGE: $SCAN_STAGE" >&2
        exit 2
        ;;
esac

cd "$SCAN_SOURCE_DIR"
exec "$SCAN_PYTHON" "$WORKER" "${arguments[@]}"
