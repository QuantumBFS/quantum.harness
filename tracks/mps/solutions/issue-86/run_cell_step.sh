#!/bin/bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: run_cell_step.sh CELL_INDEX" >&2
  exit 2
fi

: "${ISSUE86_RUN_SPEC_ABS:?missing ISSUE86_RUN_SPEC_ABS}"
: "${ISSUE86_OUTPUT_DIRECTORY:?missing ISSUE86_OUTPUT_DIRECTORY}"
: "${ISSUE86_SOLUTION_DIRECTORY:?missing ISSUE86_SOLUTION_DIRECTORY}"
: "${ISSUE86_JULIA_PROJECT:?missing ISSUE86_JULIA_PROJECT}"
: "${ISSUE86_CORES_PER_WORKER:?missing ISSUE86_CORES_PER_WORKER}"
: "${ISSUE86_MEMORY_PER_WORKER_MB:?missing ISSUE86_MEMORY_PER_WORKER_MB}"

index="$1"
if srun --exact --exclusive --nodes=1 --ntasks=1 \
    --cpus-per-task="$ISSUE86_CORES_PER_WORKER" \
    --mem="${ISSUE86_MEMORY_PER_WORKER_MB}M" \
    --cpu-bind=cores --unbuffered \
    julia --project="$ISSUE86_JULIA_PROJECT" \
      "$ISSUE86_SOLUTION_DIRECTORY/run_cell.jl" \
      "$ISSUE86_RUN_SPEC_ABS" "$index" "$ISSUE86_OUTPUT_DIRECTORY"; then
  exit 0
else
  status="$?"
  echo "cell index $index failed with srun status $status" >&2
  # GNU xargs treats 255 as "abort immediately". Normalize every cell failure
  # so the bounded pool still attempts the remaining independent cells.
  exit 1
fi
