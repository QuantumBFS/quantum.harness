#!/usr/bin/env bash
#SBATCH --account=giggleliu
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
#SBATCH --mem=128G

set -euo pipefail
umask 077

die() {
    printf 'route_b_bundle: %s\n' "$*" >&2
    exit 1
}

: "${TASK_PATHS:?TASK_PATHS is required}"
: "${RELEASE:?RELEASE is required}"
: "${RESULT_ROOT:?RESULT_ROOT is required}"
: "${LOG_ROOT:?LOG_ROOT is required}"
: "${JULIA_RELEASE:?JULIA_RELEASE is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

bundle_size=${BUNDLE_SIZE:-4}
[[ "$bundle_size" =~ ^[1-9][0-9]*$ ]] || die "BUNDLE_SIZE must be positive"
[[ "$SLURM_ARRAY_TASK_ID" =~ ^[0-9]+$ ]] || die "array index must be nonnegative"
[[ -f "$TASK_PATHS" && ! -L "$TASK_PATHS" ]] || die "invalid task_paths file"
[[ "$RELEASE" == /* && -d "$RELEASE" && ! -L "$RELEASE" ]] || die "invalid release"
release_commit=$(basename -- "$RELEASE")
[[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || die "release must end in a Git commit"
[[ "$RESULT_ROOT" == /* && ! -L "$RESULT_ROOT" ]] || die "invalid result root"
[[ "$LOG_ROOT" == /* && ! -L "$LOG_ROOT" ]] || die "invalid log root"
[[ "$JULIA_RELEASE" == /* && -d "$JULIA_RELEASE" && ! -L "$JULIA_RELEASE" ]] ||
    die "invalid Julia release"
julia="$JULIA_RELEASE/julia/bin/julia"
project="$RELEASE/project/route_b"
runner="$project/scripts/run_task.jl"
[[ -x "$julia" ]] || die "Julia executable is unavailable"
[[ -f "$project/Project.toml" && -f "$project/Manifest.toml" ]] ||
    die "Route B project is incomplete"
[[ -f "$runner" && ! -L "$runner" ]] || die "Route B runner is unavailable"

task_count=$(awk 'END { print NR }' "$TASK_PATHS")
(( task_count > 0 )) || die "task_paths is empty"
start_index=$((10#$SLURM_ARRAY_TASK_ID * bundle_size))
(( start_index < task_count )) || die "bundle index is out of range"
end_index=$((start_index + bundle_size - 1))
(( end_index < task_count )) || end_index=$((task_count - 1))
task_directory=$(cd -- "$(dirname -- "$TASK_PATHS")" && pwd -P)

mkdir -p -- "$RESULT_ROOT" "$LOG_ROOT"
export LC_ALL=C
export ROUTE_B_RELEASE_COMMIT="$release_commit"
export JULIA_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

node_tmp=${SLURM_TMPDIR:-${TMPDIR:-/tmp}}
[[ "$node_tmp" == /* && -d "$node_tmp" && ! -L "$node_tmp" ]] ||
    die "node-local temporary directory is unavailable"
job_token=${SLURM_JOB_ID:-manual-$$}
[[ "$job_token" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe Slurm job identifier"
job_depot="$node_tmp/route-b-depot-$job_token"
mkdir -p -- "$job_depot"
cleanup_depot() { rm -rf -- "$job_depot"; }
trap cleanup_depot EXIT
export JULIA_DEPOT_PATH="$job_depot:$JULIA_RELEASE/depot"
export JULIA_PKG_PRECOMPILE_AUTO=0
"$julia" --startup-file=no --project="$project" -e 'using RouteBWorm, JSON'

pids=()
indices=()
for ((task_index = start_index; task_index <= end_index; task_index++)); do
    line_number=$((task_index + 1))
    task_entry=$(sed -n "${line_number}p" "$TASK_PATHS")
    [[ -n "$task_entry" && "$task_entry" != *$'\r'* ]] ||
        die "invalid task entry at line $line_number"
    [[ "$task_entry" != . && "$task_entry" != .. && "$task_entry" == "$(basename -- "$task_entry")" ]] ||
        die "task_paths entries must be basenames"
    task_file="$task_directory/$task_entry"
    output_file="$RESULT_ROOT/$task_entry"
    checkpoint_file="$output_file.checkpoint"
    [[ -f "$task_file" && ! -L "$task_file" ]] || die "invalid task file $task_index"
    if [[ -s "$output_file" ]] && "$julia" --startup-file=no --project="$project" -e \
        'using JSON; get(JSON.parsefile(ARGS[1]), "status", "") == "complete" || exit(1)' \
        "$output_file" >/dev/null 2>&1; then
        printf 'route_b_bundle: skip complete task %d\n' "$task_index"
        continue
    fi
    resume=false
    [[ -s "$checkpoint_file" ]] && resume=true
    task_log_prefix="$LOG_ROOT/task-$(printf '%04d' "$task_index")"
    (
        "$julia" --startup-file=no --project="$project" "$runner" \
            --task "$task_file" --output "$output_file" \
            --checkpoint "$checkpoint_file" --resume "$resume"
    ) >"$task_log_prefix.out" 2>"$task_log_prefix.err" &
    pids+=("$!")
    indices+=("$task_index")
done

failed=0
for position in "${!pids[@]}"; do
    if ! wait "${pids[$position]}"; then
        printf 'route_b_bundle: task %s failed; see %s/task-%04d.err\n' \
            "${indices[$position]}" "$LOG_ROOT" "${indices[$position]}" >&2
        failed=1
    fi
done
(( failed == 0 )) || die "one or more bundled tasks failed"
printf 'route_b_bundle: completed task indices %d-%d\n' "$start_index" "$end_index"
