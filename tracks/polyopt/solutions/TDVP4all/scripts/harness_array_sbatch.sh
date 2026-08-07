#!/bin/bash
#SBATCH --job-name=harness-array
#SBATCH --output=slurm-%A_%a.out

# Generic harness array wrapper. The submitter supplies:
#   HARNESS_RUN_SPEC=<path to run_spec.json>
#   HARNESS_COMMAND=<shell command>
# or, as a convenience fallback:
#   HARNESS_ENTRYPOINT=<script path>
#   HARNESS_RUNNER=<optional runner command>
# Optional minimal-input mode also supplies:
#   HARNESS_STAGING_MANIFEST=<slurm-staging-manifest.json>
# The manifest is produced by the schema-v2 runner and is the authoritative
# allow-list for the transferred snapshot. It contains only the selected
# problem/instance, referenced shared structure/reduction, Julia source and
# environment, this wrapper, and the run spec.
# and supplies --array=1-N plus cluster resources at sbatch time. Partition,
# account, QoS, memory, wall-clock, node, task, and CPU choices come from the
# active cluster profile or the submitter's explicit sbatch flags, not this
# wrapper.
#
# Example:
#   sbatch --partition=<queue> --time=<walltime> --cpus-per-task=<n> --array=1-<n_cells> --export=ALL,HARNESS_RUN_SPEC=results/run/run_spec.json,HARNESS_COMMAND='julia --project=julia-env scripts/foo.jl' scripts/harness_array_sbatch.sh

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

run_line_buffered() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL "$@"
  else
    "$@"
  fi
}

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to a run_spec.json path}"
if [[ -z "${HARNESS_COMMAND:-}" && -z "${HARNESS_ENTRYPOINT:-}" ]]; then
  echo "Set HARNESS_COMMAND, or set HARNESS_ENTRYPOINT with optional HARNESS_RUNNER" >&2
  exit 2
fi
CELL_SELECTOR="${SLURM_ARRAY_TASK_ID:-${HARNESS_CELL_INDEX:-${HARNESS_CELL_ID:-single}}}"

echo "Cell selector: ${CELL_SELECTOR}"
echo "Run spec:   ${HARNESS_RUN_SPEC}"
if [[ -n "${HARNESS_STAGING_MANIFEST:-}" ]]; then
  [[ -f "$HARNESS_STAGING_MANIFEST" ]] || {
    echo "Missing staging manifest: $HARNESS_STAGING_MANIFEST" >&2
    exit 2
  }
  echo "Staging:    ${HARNESS_STAGING_MANIFEST}"
  if command -v sha256sum >/dev/null 2>&1; then
    echo "Stage SHA:  $(sha256sum "$HARNESS_STAGING_MANIFEST" | awk '{print $1}')"
  elif command -v shasum >/dev/null 2>&1; then
    echo "Stage SHA:  $(shasum -a 256 "$HARNESS_STAGING_MANIFEST" | awk '{print $1}')"
  else
    echo "A SHA-256 utility is required for staged schema-v2 jobs" >&2
    exit 2
  fi
fi
[[ -n "${HARNESS_COMMAND:-}" ]] && echo "Command:    ${HARNESS_COMMAND}"
[[ -n "${HARNESS_ENTRYPOINT:-}" ]] && echo "Entrypoint: ${HARNESS_ENTRYPOINT}"
[[ -n "${HARNESS_RUNNER:-}" ]] && echo "Runner:     ${HARNESS_RUNNER}"
echo "Started:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ -n "${HARNESS_COMMAND:-}" ]]; then
  run_line_buffered bash -lc "$HARNESS_COMMAND"
elif [[ -n "${HARNESS_RUNNER:-}" ]]; then
  run_line_buffered bash -lc "$HARNESS_RUNNER \"\$1\"" _ "$HARNESS_ENTRYPOINT"
elif [[ "${HARNESS_ENTRYPOINT}" == *.jl ]]; then
  if [[ -n "${HARNESS_JULIA_BIN:-}" ]]; then
    JULIA_CMD="$HARNESS_JULIA_BIN"
  elif [[ -d "$HOME/.juliaup/bin" ]]; then
    export PATH="$HOME/.juliaup/bin:$PATH"
    JULIA_CMD="julia"
  else
    JULIA_CMD="julia"
  fi
  run_line_buffered "$JULIA_CMD" --project="${HARNESS_JULIA_PROJECT:-julia-env}" "$HARNESS_ENTRYPOINT"
else
  run_line_buffered "$HARNESS_ENTRYPOINT"
fi

echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
