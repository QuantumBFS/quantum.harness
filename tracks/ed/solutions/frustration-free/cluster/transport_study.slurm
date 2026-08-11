#!/bin/bash
#SBATCH --partition=ihicnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=06:00:00
#SBATCH --requeue

set -euo pipefail

: "${TRANSPORT_STAGE:?TRANSPORT_STAGE is required}"
: "${TRANSPORT_PYTHON:?TRANSPORT_PYTHON is required}"
: "${TRANSPORT_SOURCE_DIR:?TRANSPORT_SOURCE_DIR is required}"
: "${TRANSPORT_TASK_MAP:?TRANSPORT_TASK_MAP is required}"
: "${TRANSPORT_RUN_DIR:?TRANSPORT_RUN_DIR is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

arguments=(
    "$TRANSPORT_STAGE"
    --task-map "$TRANSPORT_TASK_MAP"
    --task-id "$SLURM_ARRAY_TASK_ID"
    --L 8
    --chern-dir "$TRANSPORT_RUN_DIR/chern10"
    --static-dir "$TRANSPORT_RUN_DIR/static"
    --refined-dir "$TRANSPORT_RUN_DIR/chern20"
    --realtime-dir "$TRANSPORT_RUN_DIR/realtime"
)

cd "$TRANSPORT_SOURCE_DIR"
exec "$TRANSPORT_PYTHON" scripts/transport_study.py "${arguments[@]}"
