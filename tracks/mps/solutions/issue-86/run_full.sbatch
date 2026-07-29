#!/bin/bash
#SBATCH --job-name=qh86-track-b
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --mem=480G
#SBATCH --time=24:00:00
#SBATCH --output=tracks/mps/results/issue-86-full/slurm-%x-%j.out

set -euo pipefail

ISSUE86_RUN_SPEC="${ISSUE86_RUN_SPEC:-${HARNESS_RUN_SPEC:-}}"
: "${ISSUE86_RUN_SPEC:?set ISSUE86_RUN_SPEC or submit with --run-spec}"
ISSUE86_OUTPUT_DIR="${ISSUE86_OUTPUT_DIR:-$(dirname "$ISSUE86_RUN_SPEC")}"
selector="${HARNESS_COMMAND:-}"
if [[ "$selector" == *:* ]]; then
  ISSUE86_STAGE="${ISSUE86_STAGE:-${selector%%:*}}"
  RESOURCE_CLASS="${RESOURCE_CLASS:-${selector##*:}}"
else
  ISSUE86_STAGE="${ISSUE86_STAGE:-}"
  RESOURCE_CLASS="${RESOURCE_CLASS:-${selector:-A}}"
fi

mkdir -p "$ISSUE86_OUTPUT_DIR"
if [[ ! -s "$ISSUE86_RUN_SPEC" ]]; then
  : "${ISSUE86_STAGE:?missing run spec requires selector STAGE:CLASS}"
  config="tracks/mps/solutions/issue-86/configs/${ISSUE86_STAGE}.toml"
  julia --project=julia-env \
    tracks/mps/solutions/issue-86/generate_run_spec.jl \
    "$config" "$ISSUE86_RUN_SPEC" "issue-86-${ISSUE86_STAGE}" "$ISSUE86_STAGE"
fi

case "$RESOURCE_CLASS" in
  A)
    : "${ISSUE86_CORES_PER_WORKER:=8}"
    ;;
  B)
    : "${ISSUE86_CORES_PER_WORKER:=16}"
    ;;
  C)
    : "${ISSUE86_CORES_PER_WORKER:=32}"
    ;;
  D)
    : "${ISSUE86_CORES_PER_WORKER:=64}"
    ;;
  *)
    echo "unknown RESOURCE_CLASS=$RESOURCE_CLASS" >&2
    exit 2
    ;;
esac

allocated_cpus="${SLURM_CPUS_PER_TASK:-128}"
if [[ ! "$allocated_cpus" =~ ^[1-9][0-9]*$ ]]; then
  echo "invalid SLURM_CPUS_PER_TASK=$allocated_cpus" >&2
  exit 2
fi
: "${ISSUE86_WORKERS:=$((allocated_cpus / ISSUE86_CORES_PER_WORKER))}"
if (( ISSUE86_WORKERS < 1 ||
      ISSUE86_WORKERS * ISSUE86_CORES_PER_WORKER > allocated_cpus )); then
  echo "worker layout exceeds the $allocated_cpus allocated CPUs" >&2
  exit 2
fi

bash tracks/mps/solutions/issue-86/packed_worker.sh \
  "$ISSUE86_RUN_SPEC" "$ISSUE86_OUTPUT_DIR" "$RESOURCE_CLASS" \
  "$ISSUE86_WORKERS" "$ISSUE86_CORES_PER_WORKER"
