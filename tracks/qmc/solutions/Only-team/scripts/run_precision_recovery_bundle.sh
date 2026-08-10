#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
CELL_RUNNER="$REPO_ROOT/tracks/qmc/solutions/Only-team/scripts/run_challenge_scan_cell.sh"
PYTHON3="/public/software/apps/anaconda3/2023.09/bin/python3"

: "${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

BUNDLE_ID="$SLURM_ARRAY_TASK_ID"
CELL_INDICES="$(
    "$PYTHON3" - "$REPO_ROOT/$HARNESS_RUN_SPEC" "$BUNDLE_ID" <<'PY'
import json
import sys

spec_path = sys.argv[1]
bundle_id = int(sys.argv[2])
with open(spec_path, encoding="utf-8") as stream:
    spec = json.load(stream)
bundles = spec["execution"]["bundles"]
matches = [
    bundle for bundle in bundles
    if int(bundle["bundle_id"]) == bundle_id
]
if len(matches) != 1:
    raise SystemExit(f"expected one bundle {bundle_id}, found {len(matches)}")
print(" ".join(str(index) for index in matches[0]["cell_indices"]))
PY
)"

printf 'bundle_start job=%s bundle=%s cells=%s\n' \
    "${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-unknown}}" \
    "$BUNDLE_ID" \
    "$CELL_INDICES"

for cell_index in $CELL_INDICES
do
    export SLURM_ARRAY_TASK_ID="$cell_index"
    "$CELL_RUNNER"
done

printf 'bundle_complete job=%s bundle=%s cells=%s\n' \
    "${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-unknown}}" \
    "$BUNDLE_ID" \
    "$CELL_INDICES"
