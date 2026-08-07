#!/bin/bash
#SBATCH --job-name=occ71-cwin-v3
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-99%16
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/c-window-safe-v3/logs/%A_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/c-window-safe-v3/logs/%A_%a.err

set -euo pipefail

ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
SEARCH="$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search"
INPUT="$ROOT/results/occam71/reference-355/mystery-C.txt"
RANKING="$ROOT/results/occam71/c-window-safe/c_joint_window_ranking_safe_v3.json"
OUT_ROOT="$ROOT/results/occam71/c-window-safe-v3"
PYSAT_VENV="${PYSAT_VENV:?submit with the audited PySAT venv}"
PYTHON_BIN="$PYSAT_VENV/bin/python"

mkdir -p "$OUT_ROOT/logs"
test -x "$PYTHON_BIN"
test -s "$RANKING"
"$PYTHON_BIN" -c 'import pysat, pysat.solvers'

read -r ROOT_A ROOT_B GATES < <(
  "$PYTHON_BIN" -c '
import json
import sys
payload = json.load(open(sys.argv[1], "r", encoding="utf-8"))
record = payload["records"][int(sys.argv[2])]
assert payload["safety"]["boundary_excludes_root_descendants"] is True
assert payload["safety"]["roots_functional_of_boundary"] is True
assert int(record["candidate_gates"]) == int(record["removed_count"]) - 1
print(record["roots"][0], record["roots"][1], record["candidate_gates"])
' "$RANKING" "$SLURM_ARRAY_TASK_ID"
)

CASE_INDEX=$(printf "%03d" "$SLURM_ARRAY_TASK_ID")
CASE_NAME="${CASE_INDEX}_${ROOT_A}_${ROOT_B}_k${GATES}"
CASE_OUT="$OUT_ROOT/$CASE_NAME"
mkdir -p "$CASE_OUT"

{
  printf 'job_id=%s\n' "$SLURM_ARRAY_JOB_ID"
  printf 'array_task_id=%s\n' "$SLURM_ARRAY_TASK_ID"
  printf 'node=%s\n' "$SLURMD_NODENAME"
  printf 'seed=42\n'
  printf 'roots=%s,%s\n' "$ROOT_A" "$ROOT_B"
  printf 'candidate_gates=%s\n' "$GATES"
  sha256sum "$INPUT" "$RANKING" \
    "$SEARCH/c_window_rank_safe_v3.py" \
    "$SEARCH/d_window_sat_safe_remote.py" \
    "$SEARCH/d_window_sat_hpc_safe.py"
} > "$CASE_OUT/metadata.txt"

"$PYTHON_BIN" -u "$SEARCH/d_window_sat_hpc_safe.py" "$INPUT" \
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
