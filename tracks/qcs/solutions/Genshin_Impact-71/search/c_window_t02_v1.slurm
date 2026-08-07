#!/bin/bash
#SBATCH --job-name=occam71-cwin
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-11
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/c-window-slurm/logs/%A_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/c-window-slurm/logs/%A_%a.err

set -euo pipefail

ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
SEARCH="$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search"
INPUT="$ROOT/results/occam71/reference-355/mystery-C.txt"
OUT_ROOT="$ROOT/results/occam71/c-window-slurm"
PYSAT_VENV="${PYSAT_VENV:?submit with the audited PySAT venv}"
PYTHON_BIN="$PYSAT_VENV/bin/python"

mkdir -p "$OUT_ROOT/logs"
test -x "$PYTHON_BIN"
"$PYTHON_BIN" -c 'import pysat, pysat.solvers'

CASES=(
  "w67 w71 5"
  "w88 w92 5"
  "w110 w111 5"
  "w130 w131 5"
  "w143 w144 5"
  "w53 w54 5"
  "w64 w65 5"
  "w80 w81 5"
  "w51 w55 5"
  "w108 w112 5"
  "w128 w132 5"
  "w39 w43 5"
)
read -r ROOT_A ROOT_B GATES <<< "${CASES[$SLURM_ARRAY_TASK_ID]}"
CASE_NAME="${ROOT_A}_${ROOT_B}_k${GATES}"
CASE_OUT="$OUT_ROOT/$CASE_NAME"
mkdir -p "$CASE_OUT"

"$PYTHON_BIN" -u "$SEARCH/d_window_sat_hpc_remote.py" "$INPUT" \
  --roots "$ROOT_A" "$ROOT_B" \
  --gates "$GATES" \
  --timeout 10 \
  --output-dir "$CASE_OUT"

test -s "$CASE_OUT/report.json"
CANDIDATE="$CASE_OUT/mystery-C.candidate.txt"
if [[ -s "$CANDIDATE" ]]; then
  "$PYTHON_BIN" -u "$SEARCH/verify_candidate.py" \
    "$INPUT" "$CANDIDATE" \
    --report "$CASE_OUT/independent-full-domain-audit.json"
  test -s "$CASE_OUT/independent-full-domain-audit.json"
  touch "$CASE_OUT/CANDIDATE_AUDITED"
fi
touch "$CASE_OUT/COMPLETE"
