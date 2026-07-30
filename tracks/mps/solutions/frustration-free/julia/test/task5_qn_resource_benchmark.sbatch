#!/bin/bash
#SBATCH --job-name=task5-qn-resource
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=task5-qn-resource-%j.log
#SBATCH --error=task5-qn-resource-%j.err

set -euo pipefail
umask 077

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
: "${MODE:?Set MODE to non_qn or qn}"
: "${OUTPUT:?Set OUTPUT to an isolated destination JSON path}"
: "${EXPECTED_GIT_COMMIT:?Set EXPECTED_GIT_COMMIT}"
: "${BATH_ARTIFACT_PATH:?Set BATH_ARTIFACT_PATH}"
: "${MAPPING_ARTIFACT_PATH:?Set MAPPING_ARTIFACT_PATH}"
: "${EXPECTED_BATH_FILE_SHA256:?Set EXPECTED_BATH_FILE_SHA256}"
: "${EXPECTED_MAPPING_FILE_SHA256:?Set EXPECTED_MAPPING_FILE_SHA256}"

test -f DEPLOYED_GIT_COMMIT
test "$(tr -d '\n' < DEPLOYED_GIT_COMMIT)" = "$EXPECTED_GIT_COMMIT"
test "$MODE" = non_qn || test "$MODE" = qn
test ! -e "$OUTPUT"

project="tracks/mps/solutions/frustration-free/julia"
benchmark="$project/test/task5_qn_resource_benchmark.jl"
mkdir -p "$(dirname "$OUTPUT")"
temporary="$(mktemp "${OUTPUT}.tmp.XXXXXX")"
trap 'rm -f "$temporary"' EXIT

export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
julia --project="$project" "$benchmark" >"$temporary"
test -s "$temporary"
mv "$temporary" "$OUTPUT"
trap - EXIT
printf 'Published Task5 resource sample: %s\n' "$OUTPUT"
