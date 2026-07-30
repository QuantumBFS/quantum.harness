#!/bin/bash
#SBATCH --job-name=occam71-dwin
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-9
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/d-window-slurm/logs/%A_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/d-window-slurm/logs/%A_%a.err

set -euo pipefail

ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
SEARCH="$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search"
INPUT="$ROOT/results/occam71/reference-355/mystery-D.txt"
OUT_ROOT="$ROOT/results/occam71/d-window-slurm"
DEFAULT_VENV="$ROOT/results/occam71/tools/pysat-venv"
PYSAT_VENV="${PYSAT_VENV:-$DEFAULT_VENV}"
PYTHON_BIN="$PYSAT_VENV/bin/python"

mkdir -p "$OUT_ROOT/logs"
test -x "$PYTHON_BIN"
"$PYTHON_BIN" -c 'import pysat, pysat.solvers'

CASES=(
  "w87 w97 12"
  "w101 w106 11"
  "w110 w113 11"
  "w50 w62 10"
  "w57 w71 10"
  "w67 w78 10"
  "w35 w38 9"
  "w89 w94 9"
  "w66 w76 7"
  "w109 w111 6"
)
read -r ROOT_A ROOT_B GATES <<< "${CASES[$SLURM_ARRAY_TASK_ID]}"
CASE_NAME="${ROOT_A}_${ROOT_B}_k${GATES}"
CASE_OUT="$OUT_ROOT/$CASE_NAME"
mkdir -p "$CASE_OUT"

"$PYTHON_BIN" -u "$SEARCH/d_window_sat_hpc_remote.py" "$INPUT" \
  --roots "$ROOT_A" "$ROOT_B" \
  --gates "$GATES" \
  --timeout 50 \
  --output-dir "$CASE_OUT"

test -s "$CASE_OUT/report.json"
CANDIDATE="$CASE_OUT/mystery-D.candidate.txt"
if [[ -s "$CANDIDATE" ]]; then
  "$PYTHON_BIN" -u "$SEARCH/verify_candidate.py" \
    "$INPUT" "$CANDIDATE" \
    --report "$CASE_OUT/independent-full-domain-audit.json"
  test -s "$CASE_OUT/independent-full-domain-audit.json"
  touch "$CASE_OUT/CANDIDATE_AUDITED"
fi
touch "$CASE_OUT/COMPLETE"
