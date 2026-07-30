#!/usr/bin/env bash
#SBATCH --job-name=occ71-bddocc-main
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-3
#SBATCH --cpus-per-task=1
#SBATCH --mem=48G
#SBATCH --time=18:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/bdd-route/logs/%A_occmain_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/bdd-route/logs/%A_occmain_%a.err

set -euo pipefail

ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search/bdd_route"
DATA="$ROOT/results/occam71/occam-circuit/datasets"
PYSAT_VENV="${PYSAT_VENV:?PYSAT_VENV must name the audited offline environment}"
RUN="$ROOT/results/occam71/bdd-route/job-${SLURM_ARRAY_JOB_ID}/occam-main-${SLURM_ARRAY_TASK_ID}"
mkdir -p "$RUN"

instances=(mystery-A mystery-B mystery-C mystery-D)
order_names=(lsb_interleaved msb_interleaved lsb_interleaved lsb_interleaved)
orders=(
  0,8,1,9,2,10,3,11,4,12,5,13,6,14,7,15
  6,13,5,12,4,11,3,10,2,9,1,8,0,7
  0,6,1,7,2,8,3,9,4,10,5,11
  0,5,1,6,2,7,3,8,4,9
)
max_widths=(8 8 16 16)
instance="${instances[$SLURM_ARRAY_TASK_ID]}"
order_name="${order_names[$SLURM_ARRAY_TASK_ID]}"
order="${orders[$SLURM_ARRAY_TASK_ID]}"
max_width="${max_widths[$SLURM_ARRAY_TASK_ID]}"

set +e
"$PYSAT_VENV/bin/python" -u "$CODE/bdd_sat_occam_fixed.py" \
  --fixed-order "$order" \
  --fixed-order-name "$order_name" \
  --dataset-root "$DATA" \
  --instance "$instance" \
  --output-dir "$RUN" \
  --seed 42 \
  --max-width "$max_width" \
  --conflict-budget 500000 \
  --solver cadical195 \
  --sift-variables 0 \
  --adjacent-passes 0
learner_status=$?
set -e

netlist="$RUN/${instance}.selected.occam-bdd.txt"
audit_status=NA
if test -f "$netlist"; then
  set +e
  "$PYSAT_VENV/bin/python" -u "$CODE/independent_bdd_audit.py" \
    --instance "$instance" \
    --netlist "$netlist" \
    --json "$RUN/${instance}.selected.occam-audit.json"
  audit_status=$?
  set -e
fi
printf '%s\n' "$learner_status" > "$RUN/learner_exit_status.txt"
printf '%s\n' "$audit_status" > "$RUN/audit_exit_status.txt"
sha256sum \
  "$CODE/bdd_sat_occam_fixed.py" \
  "$CODE/bdd_sat_occam_v2.py" \
  "$CODE/bdd_sat_refine.py" \
  "$CODE/decision_diagram_learn.py" \
  "$CODE/decision_diagram_learn_v2.py" \
  "$CODE/independent_bdd_audit.py" \
  "$DATA/$instance/train.csv" > "$RUN/INPUT_SHA256SUMS"
if test -f "$netlist"; then
  sha256sum "$netlist" > "$RUN/NETLIST_SHA256SUM"
fi
printf 'BDD_OCCAM_MAIN_COMPLETE instance=%s learner_status=%s audit_status=%s\n' \
  "$instance" "$learner_status" "$audit_status" > "$RUN/COMPLETE"
cat "$RUN/COMPLETE"
