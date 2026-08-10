#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
ONLY_TEAM_ROOT="$REPO_ROOT/tracks/qmc/solutions/Only-team"
HELPER="$ONLY_TEAM_ROOT/scripts/prepare_extreme_scan_cell.py"
RUN_SCRIPT="$ONLY_TEAM_ROOT/scripts/run.jl"
MPIEXECJL="$HOME/.julia/bin/mpiexecjl"
PYTHON3="/public/software/apps/anaconda3/2023.09/bin/python3"

: "${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

for required in "$HELPER" "$RUN_SCRIPT" "$MPIEXECJL" "$PYTHON3"
do
    [[ -f "$required" ]] || {
        printf 'missing required file: %s\n' "$required" >&2
        exit 2
    }
done

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export JULIA_NUM_THREADS=1
module purge

CONTEXT_PATH="$(
    "$PYTHON3" "$HELPER" prepare \
        --run-spec "$HARNESS_RUN_SPEC" \
        --index "$SLURM_ARRAY_TASK_ID" \
        --role scan \
        --repo-root "$REPO_ROOT"
)"
CONFIG_PATH="$(dirname "$CONTEXT_PATH")/config.toml"

printf 'cell_start job=%s task=%s context=%s\n' \
    "${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-unknown}}" \
    "$SLURM_ARRAY_TASK_ID" \
    "$CONTEXT_PATH"
printf 'sampling ranks=32 nWarm=10000 NmBin=32 NSwep=2000 nLocal=1 nWolff=5\n'

"$MPIEXECJL" --project="$ONLY_TEAM_ROOT" -n 32 \
    julia --project="$ONLY_TEAM_ROOT" \
    "$RUN_SCRIPT" \
    "$CONFIG_PATH"

MANIFEST_PATH="$(
    "$PYTHON3" "$HELPER" finalize \
        --context "$CONTEXT_PATH" \
        --job-id "${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-unknown}}" \
        --array-task-id "$SLURM_ARRAY_TASK_ID"
)"
printf 'cell_complete job=%s task=%s manifest=%s\n' \
    "${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-unknown}}" \
    "$SLURM_ARRAY_TASK_ID" \
    "$MANIFEST_PATH"
