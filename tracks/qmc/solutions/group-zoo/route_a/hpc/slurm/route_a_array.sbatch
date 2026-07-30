#!/usr/bin/env bash
#SBATCH --account=giggleliu
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1

set -euo pipefail
umask 077

die() {
    printf 'route_a_array: %s\n' "$*" >&2
    exit 1
}

: "${TASK_PATHS:?TASK_PATHS is required}"
: "${RELEASE:?RELEASE is required}"
: "${RESULT_ROOT:?RESULT_ROOT is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

[[ "$SLURM_ARRAY_TASK_ID" =~ ^[0-9]+$ ]] || die "array index must be a nonnegative integer"
[[ -f "$TASK_PATHS" && ! -L "$TASK_PATHS" ]] || die "TASK_PATHS must be a regular non-symlink file"
[[ "$RELEASE" == /* && -d "$RELEASE" && ! -L "$RELEASE" ]] ||
    die "RELEASE must be an exact absolute release directory"
release_commit=$(basename -- "$RELEASE")
[[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || die "RELEASE basename must be a 40-hex commit"
export CHALLENGE148_RELEASE_COMMIT="$release_commit"
[[ "$RESULT_ROOT" == /* && ! -L "$RESULT_ROOT" ]] ||
    die "RESULT_ROOT must be an absolute non-symlink path"

line_number=$((10#$SLURM_ARRAY_TASK_ID + 1))
task_entry=$(sed -n "${line_number}p" "$TASK_PATHS")
[[ -n "$task_entry" && "$task_entry" != *$'\r'* ]] || die "array index is out of range"
[[ "$task_entry" != . && "$task_entry" != .. && "$task_entry" == "$(basename -- "$task_entry")" ]] ||
    die "task_paths entries must be basenames"

task_directory=$(cd -- "$(dirname -- "$TASK_PATHS")" && pwd -P)
task_file="$task_directory/$task_entry"
[[ -f "$task_file" && ! -L "$task_file" ]] || die "selected task must be a regular non-symlink file"
[[ -x "$RELEASE/julia/bin/julia" ]] || die "release Julia is unavailable"
[[ -f "$RELEASE/project/Project.toml" && -f "$RELEASE/project/Manifest.toml" ]] ||
    die "release project is incomplete"
runner="$RELEASE/project/scripts/run_cluster.jl"
[[ -f "$runner" && ! -L "$runner" ]] || die "release runner is unavailable"

mkdir -p -- "$RESULT_ROOT"
cd -- "$RESULT_ROOT"
runner_args=(--task "$task_file")
if [[ -n ${STOP_AFTER_BINS:-} ]]; then
    [[ "$STOP_AFTER_BINS" =~ ^[1-9][0-9]*$ ]] || die "STOP_AFTER_BINS must be a positive integer"
    runner_args+=(--stop-after-bins "$STOP_AFTER_BINS")
fi

export LC_ALL=C
node_tmp=${SLURM_TMPDIR:-${TMPDIR:-/tmp}}
[[ "$node_tmp" == /* && -d "$node_tmp" && ! -L "$node_tmp" ]] ||
    die "node-local temporary directory is unavailable"
job_token=${SLURM_JOB_ID:-manual-$$}
[[ "$job_token" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe Slurm job identifier"
job_depot="$node_tmp/challenge148-depot-$job_token"
mkdir -p -- "$job_depot"
cleanup_depot() { rm -rf -- "$job_depot"; }
trap cleanup_depot EXIT
export JULIA_DEPOT_PATH="$job_depot:$RELEASE/depot"
export JULIA_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
"$RELEASE/julia/bin/julia" --startup-file=no --project="$RELEASE/project" \
    "$runner" "${runner_args[@]}"
