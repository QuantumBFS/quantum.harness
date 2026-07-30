#!/usr/bin/env bash
#SBATCH --account=giggleliu
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --mem=128G

set -euo pipefail
umask 077

die() {
    printf 'route_a_bundle: %s\n' "$*" >&2
    exit 1
}

: "${TASK_PATHS:?TASK_PATHS is required}"
: "${RELEASE:?RELEASE is required}"
: "${RESULT_ROOT:?RESULT_ROOT is required}"
: "${LOG_ROOT:?LOG_ROOT is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

bundle_size=${BUNDLE_SIZE:-8}
[[ "$bundle_size" =~ ^[1-9][0-9]*$ ]] || die "BUNDLE_SIZE must be a positive integer"
[[ "$SLURM_ARRAY_TASK_ID" =~ ^[0-9]+$ ]] || die "array index must be a nonnegative integer"
[[ -f "$TASK_PATHS" && ! -L "$TASK_PATHS" ]] || die "TASK_PATHS must be a regular non-symlink file"
[[ "$RELEASE" == /* && -d "$RELEASE" && ! -L "$RELEASE" ]] ||
    die "RELEASE must be an exact absolute release directory"
release_commit=$(basename -- "$RELEASE")
[[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || die "RELEASE basename must be a 40-hex commit"
[[ "$RESULT_ROOT" == /* && ! -L "$RESULT_ROOT" ]] ||
    die "RESULT_ROOT must be an absolute non-symlink path"
[[ "$LOG_ROOT" == /* && ! -L "$LOG_ROOT" ]] ||
    die "LOG_ROOT must be an absolute non-symlink path"
[[ -x "$RELEASE/julia/bin/julia" ]] || die "release Julia is unavailable"
[[ -f "$RELEASE/project/Project.toml" && -f "$RELEASE/project/Manifest.toml" ]] ||
    die "release project is incomplete"
runner="$RELEASE/project/scripts/run_cluster.jl"
[[ -f "$runner" && ! -L "$runner" ]] || die "release runner is unavailable"

task_count=$(awk 'END { print NR }' "$TASK_PATHS")
(( task_count > 0 )) || die "TASK_PATHS is empty"
start_index=$((10#$SLURM_ARRAY_TASK_ID * bundle_size))
(( start_index < task_count )) || die "bundle index is out of range"
end_index=$((start_index + bundle_size - 1))
(( end_index < task_count )) || end_index=$((task_count - 1))

task_directory=$(cd -- "$(dirname -- "$TASK_PATHS")" && pwd -P)
task_files=()
task_indices=()
for ((task_index = start_index; task_index <= end_index; task_index++)); do
    line_number=$((task_index + 1))
    task_entry=$(sed -n "${line_number}p" "$TASK_PATHS")
    [[ -n "$task_entry" && "$task_entry" != *$'\r'* ]] || die "invalid task entry at line $line_number"
    [[ "$task_entry" != . && "$task_entry" != .. && "$task_entry" == "$(basename -- "$task_entry")" ]] ||
        die "task_paths entries must be basenames"
    task_file="$task_directory/$task_entry"
    [[ -f "$task_file" && ! -L "$task_file" ]] || die "task $task_index is not a regular file"
    task_files+=("$task_file")
    task_indices+=("$task_index")
done

mkdir -p -- "$RESULT_ROOT" "$LOG_ROOT"
cd -- "$RESULT_ROOT"

export LC_ALL=C
export CHALLENGE148_RELEASE_COMMIT="$release_commit"
export JULIA_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

node_tmp=${SLURM_TMPDIR:-${TMPDIR:-/tmp}}
[[ "$node_tmp" == /* && -d "$node_tmp" && ! -L "$node_tmp" ]] ||
    die "node-local temporary directory is unavailable"
job_token=${SLURM_JOB_ID:-manual-$$}
[[ "$job_token" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe Slurm job identifier"
job_depot="$node_tmp/challenge148-bundle-depot-$job_token"
mkdir -p -- "$job_depot"
cleanup_depot() { rm -rf -- "$job_depot"; }
trap cleanup_depot EXIT
export JULIA_DEPOT_PATH="$job_depot:$RELEASE/depot"
export CHALLENGE148_PROJECT="$RELEASE/project"

# Warm the shared node-local depot once before launching concurrent chains.
"$RELEASE/julia/bin/julia" --startup-file=no --project="$RELEASE/project" -e \
    'include(joinpath(ENV["CHALLENGE148_PROJECT"], "scripts", "run_cluster.jl"))'
export JULIA_PKG_PRECOMPILE_AUTO=0

pids=()
for position in "${!task_files[@]}"; do
    task_index=${task_indices[$position]}
    task_file=${task_files[$position]}
    task_log_prefix="$LOG_ROOT/task-$(printf '%04d' "$task_index")"
    (
        export SLURM_ARRAY_TASK_ID="$task_index"
        "$RELEASE/julia/bin/julia" --startup-file=no --project="$RELEASE/project" \
            "$runner" --task "$task_file"
    ) >"$task_log_prefix.out" 2>"$task_log_prefix.err" &
    pids+=("$!")
done

failed=0
for position in "${!pids[@]}"; do
    if ! wait "${pids[$position]}"; then
        printf 'route_a_bundle: task index %s failed; see %s/task-%04d.err\n' \
            "${task_indices[$position]}" "$LOG_ROOT" "${task_indices[$position]}" >&2
        failed=1
    fi
done
(( failed == 0 )) || die "one or more bundled tasks failed"
printf 'route_a_bundle: completed task indices %d-%d\n' "$start_index" "$end_index"
