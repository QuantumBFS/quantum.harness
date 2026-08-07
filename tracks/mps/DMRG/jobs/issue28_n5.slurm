#!/bin/bash
#SBATCH --job-name=issue28-n5-report
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
N4_CELLS="${HARNESS_N4_CELLS:-$REPO_ROOT/results/issue28-n4-20260729-01/cells}"
N5_OUTPUT="${HARNESS_N5_OUTPUT:-$REPO_ROOT/results/issue28-n5-20260729-01}"

[[ -x "$PYTHON" ]] || { echo "HARNESS_PYTHON is not executable: $PYTHON" >&2; exit 2; }
[[ -d "$N4_CELLS" ]] || { echo "N4 cells directory is missing: $N4_CELLS" >&2; exit 2; }
[[ ! -e "$N5_OUTPUT" ]] || { echo "refusing to overwrite N5 output: $N5_OUTPUT" >&2; exit 2; }

export PYTHONHASHSEED=0
export MPLCONFIGDIR="${HARNESS_CACHE_ROOT:-$HOME/scratch/issue28-cache}/matplotlib-n5-${SLURM_JOB_ID:-local}"
mkdir -p "$MPLCONFIGDIR"

cd "$TRACK_ROOT"
exec "$PYTHON" -u scripts/issue28_report.py \
  --root "$N4_CELLS" \
  --protocol config/issue28_formal_v1.json \
  --output "$N5_OUTPUT"
