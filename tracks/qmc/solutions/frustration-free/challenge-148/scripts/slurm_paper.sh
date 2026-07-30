#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${CH148_PLAN:?CH148_PLAN is required}"
: "${CH148_SOLUTION_DIR:?CH148_SOLUTION_DIR is required}"
: "${CH148_QMC_SSE:?CH148_QMC_SSE is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

if [[ ! "$SLURM_ARRAY_TASK_ID" =~ ^[0-9]+$ ]] ||
   (( 10#$SLURM_ARRAY_TASK_ID > 139 )); then
    printf '%s\n' 'SLURM_ARRAY_TASK_ID must be an integer from 0 through 139' >&2
    exit 64
fi
if [[ ! -f "$CH148_PLAN" ]]; then
    printf 'CH148_PLAN is not a regular file: %s\n' "$CH148_PLAN" >&2
    exit 66
fi
if [[ ! -d "$CH148_SOLUTION_DIR" ]]; then
    printf 'CH148_SOLUTION_DIR is not a directory: %s\n' "$CH148_SOLUTION_DIR" >&2
    exit 66
fi
runner="$CH148_SOLUTION_DIR/scripts/run_cell.py"
if [[ ! -f "$runner" ]]; then
    printf 'cell runner is not a regular file: %s\n' "$runner" >&2
    exit 66
fi
if [[ ! -f "$CH148_QMC_SSE" || ! -x "$CH148_QMC_SSE" ]]; then
    printf 'CH148_QMC_SSE is not an executable regular file: %s\n' "$CH148_QMC_SSE" >&2
    exit 66
fi

exec python "$runner" \
    --plan "$CH148_PLAN" \
    --cell-index "$SLURM_ARRAY_TASK_ID" \
    --qmc-sse "$CH148_QMC_SSE" \
    --timeout-seconds 3600
