#!/bin/bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: packed_worker.sh RUN_SPEC.json OUTPUT_DIR RESOURCE_CLASS WORKERS CORES_PER_WORKER" >&2
  exit 2
fi

run_spec="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
output_directory="$2"
resource_class="$3"
workers="$4"
cores_per_worker="$5"
solution_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$solution_directory/../../../.." && pwd)"
julia_project="$repo_root/julia-env"

if (( workers < 1 || cores_per_worker < 1 )); then
  echo "worker and core counts must be positive" >&2
  exit 2
fi
if (( workers * cores_per_worker > 128 )); then
  echo "packed layout exceeds the 128-core node" >&2
  exit 2
fi

mkdir -p "$output_directory"
pending_indices=()
while IFS= read -r index; do
  [[ -n "$index" ]] && pending_indices+=("$index")
done < <(
  julia --project="$julia_project" \
    "$solution_directory/pending_cells.jl" \
    "$run_spec" "$output_directory" "$resource_class"
)

if (( ${#pending_indices[@]} == 0 )); then
  echo "no pending class-$resource_class cells"
  exit 0
fi

allocated_cpus="${SLURM_CPUS_PER_TASK:-128}"
effective_workers=$((allocated_cpus / cores_per_worker))
if (( effective_workers < 1 )); then
  echo "allocation has fewer CPUs than one worker requires" >&2
  exit 2
fi
(( effective_workers <= workers )) || effective_workers="$workers"

allocated_memory_mb="${SLURM_MEM_PER_NODE:?SLURM_MEM_PER_NODE is required}"
step_memory_mb="${ISSUE86_MEMORY_PER_WORKER_MB:-$((allocated_memory_mb / effective_workers))}"
if (( step_memory_mb < 4096 )); then
  echo "each worker needs at least 4096 MB; got ${step_memory_mb} MB" >&2
  exit 2
fi
if (( step_memory_mb * effective_workers > allocated_memory_mb )); then
  echo "worker memory requests exceed the job allocation" >&2
  exit 2
fi

echo "launching ${#pending_indices[@]} class-$resource_class cells: ${effective_workers} workers x ${cores_per_worker} cores x ${step_memory_mb} MB"
export JULIA_NUM_THREADS="$cores_per_worker"
export OPENBLAS_NUM_THREADS="$cores_per_worker"
export OMP_NUM_THREADS="$cores_per_worker"
export MKL_NUM_THREADS="$cores_per_worker"

export ISSUE86_RUN_SPEC_ABS="$run_spec"
export ISSUE86_OUTPUT_DIRECTORY="$output_directory"
export ISSUE86_SOLUTION_DIRECTORY="$solution_directory"
export ISSUE86_JULIA_PROJECT="$julia_project"
export ISSUE86_CORES_PER_WORKER="$cores_per_worker"
export ISSUE86_MEMORY_PER_WORKER_MB="$step_memory_mb"

set +e
printf '%s\n' "${pending_indices[@]}" |
  xargs -n 1 -P "$effective_workers" \
    bash "$solution_directory/run_cell_step.sh"
worker_status="${PIPESTATUS[1]}"
set -e

julia --project="$julia_project" \
  "$solution_directory/collect.jl" "$run_spec" "$output_directory"

if (( worker_status != 0 )); then
  echo "one or more cell steps failed; successful manifests were retained" >&2
  exit 1
fi
