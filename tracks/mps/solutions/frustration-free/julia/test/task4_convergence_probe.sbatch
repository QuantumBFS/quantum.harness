#!/bin/bash
#SBATCH --job-name=task4-qn-probe
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --output=task4-qn-probe-%j.log
#SBATCH --error=task4-qn-probe-%j.err

set -euo pipefail
umask 077

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
: "${OUTPUT:?Set OUTPUT to the destination JSON path}"

project="tracks/mps/solutions/frustration-free/julia"
probe="$project/test/task4_convergence_probe.jl"
output_dir="$(dirname "$OUTPUT")"
mkdir -p "$output_dir"
temporary="$(mktemp "${OUTPUT}.tmp.XXXXXX")"
trap 'rm -f "$temporary"' EXIT

export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export PROBE_GIT_COMMIT="${PROBE_GIT_COMMIT:-$(git rev-parse HEAD)}"

julia --project="$project" "$probe" >"$temporary"
test -s "$temporary"
mv -f "$temporary" "$OUTPUT"
trap - EXIT
printf 'Published Task4 convergence probe: %s\n' "$OUTPUT"
