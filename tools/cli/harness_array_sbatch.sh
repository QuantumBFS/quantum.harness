#!/bin/bash
#SBATCH --job-name=harness-array
#SBATCH --output=slurm-%A_%a.out

# Generic harness array wrapper. The submitter supplies:
#   HARNESS_RUN_SPEC=<path to run_spec.json>
#   HARNESS_ENTRYPOINT=<Julia script>
# and supplies --array=1-N plus cluster resources at sbatch time. Partition,
# account, QoS, memory, wall-clock, node, task, and CPU choices come from the
# active cluster profile or the submitter's explicit sbatch flags, not this
# wrapper.
#
# Example:
#   sbatch --partition=<queue> --time=<walltime> --cpus-per-task=<n> --array=1-<n_cells> --export=ALL,HARNESS_RUN_SPEC=results/run/run_spec.json,HARNESS_ENTRYPOINT=scripts/foo.jl tools/cli/harness_array_sbatch.sh

set -euo pipefail
if [[ -n "${HARNESS_JULIA_BIN:-}" ]]; then
  JULIA_CMD="$HARNESS_JULIA_BIN"
elif [[ -d "$HOME/.juliaup/bin" ]]; then
  export PATH="$HOME/.juliaup/bin:$PATH"
  JULIA_CMD="julia"
else
  JULIA_CMD="julia"
fi
cd "$SLURM_SUBMIT_DIR"

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to a run_spec.json path}"
: "${HARNESS_ENTRYPOINT:?Set HARNESS_ENTRYPOINT to a Julia script path}"

echo "Cell index: ${SLURM_ARRAY_TASK_ID}"
echo "Run spec:   ${HARNESS_RUN_SPEC}"
echo "Entrypoint: ${HARNESS_ENTRYPOINT}"
echo "Started:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"

stdbuf -oL "$JULIA_CMD" --project="${HARNESS_JULIA_PROJECT:-julia-env}" "$HARNESS_ENTRYPOINT"

echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
