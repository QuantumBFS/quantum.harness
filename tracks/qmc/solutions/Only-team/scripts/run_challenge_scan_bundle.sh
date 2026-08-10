#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
CELL_RUNNER="$REPO_ROOT/tracks/qmc/solutions/Only-team/scripts/run_challenge_scan_cell.sh"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

START_INDEX=11
END_INDEX=71
BUNDLE_COUNT=8
BUNDLE_ID="$SLURM_ARRAY_TASK_ID"
CELL_INDEX=$((START_INDEX + BUNDLE_ID - 1))

while (( CELL_INDEX <= END_INDEX ))
do
    printf 'bundle_progress bundle=%s cell_index=%s end=%s\n' \
        "$BUNDLE_ID" \
        "$CELL_INDEX" \
        "$END_INDEX"
    SLURM_ARRAY_TASK_ID="$CELL_INDEX" "$CELL_RUNNER"
    CELL_INDEX=$((CELL_INDEX + BUNDLE_COUNT))
done

printf 'bundle_complete bundle=%s\n' "$BUNDLE_ID"
