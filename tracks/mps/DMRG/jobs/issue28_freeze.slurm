#!/bin/bash
#SBATCH --job-name=issue28-freeze
#SBATCH --output=slurm-%j.out

set -euo pipefail
: "${SLURM_SUBMIT_DIR:?Slurm must provide SLURM_SUBMIT_DIR}"

if [[ "${HARNESS_SKIP_MODULES:-0}" != "1" ]]; then
  set +u
  source "${HARNESS_SYSTEM_PROFILE:-/etc/profile}"
  set -u
  module load compiler/intel/2017.5.239
  module load python/3.8.10
fi

REPO_ROOT="${HARNESS_REPO_ROOT:-$SLURM_SUBMIT_DIR}"
TRACK_ROOT="${HARNESS_TRACK_ROOT:-$REPO_ROOT/tracks/mps/DMRG}"
PYTHON="${HARNESS_PYTHON:-$HOME/quantum.harness/.venv-issue28/bin/python}"
[[ -x "$PYTHON" ]] || { echo "HARNESS_PYTHON is not executable: $PYTHON" >&2; exit 2; }

cd "$TRACK_ROOT"
exec "$PYTHON" -u scripts/freeze_issue28_formal_protocol.py \
  --umbrella config/issue28_easy_v1.json \
  --pilot "$REPO_ROOT/results/issue28-n3-hpc-replica-20260729-01/cells/pilot/manifest.json" \
  --output config/issue28_formal_v1.json
