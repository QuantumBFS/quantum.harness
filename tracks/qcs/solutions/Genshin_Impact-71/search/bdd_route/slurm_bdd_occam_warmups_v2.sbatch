#!/usr/bin/env bash
#SBATCH --job-name=occ71-bddocc-warm
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/bdd-route/logs/%A_occwarm_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/bdd-route/logs/%A_occwarm_%a.err

set -euo pipefail

ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search/bdd_route"
DATA="$ROOT/results/occam71/occam-circuit/datasets"
PYSAT_VENV="${PYSAT_VENV:?PYSAT_VENV must name the audited offline environment}"
RUN="$ROOT/results/occam71/bdd-route/job-${SLURM_ARRAY_JOB_ID}/occam-warmup-${SLURM_ARRAY_TASK_ID}"
mkdir -p "$RUN"

instances=(practice-add-n4 practice-mul-n4)
instance="${instances[$SLURM_ARRAY_TASK_ID]}"

"$PYSAT_VENV/bin/python" -u "$CODE/bdd_sat_occam_v2.py" \
  --dataset-root "$DATA" \
  --instance "$instance" \
  --output-dir "$RUN" \
  --seed 42 \
  --max-width 16 \
  --conflict-budget 2000000 \
  --solver cadical195 \
  --sift-variables 6 \
  --adjacent-passes 2

set +e
"$PYSAT_VENV/bin/python" -u "$CODE/independent_bdd_audit.py" \
  --instance "$instance" \
  --netlist "$RUN/${instance}.selected.occam-bdd.txt" \
  --json "$RUN/${instance}.selected.occam-audit.json"
audit_status=$?
set -e
printf '%s\n' "$audit_status" > "$RUN/audit_exit_status.txt"
sha256sum \
  "$CODE/bdd_sat_occam_v2.py" \
  "$CODE/bdd_sat_refine.py" \
  "$CODE/decision_diagram_learn.py" \
  "$CODE/decision_diagram_learn_v2.py" \
  "$CODE/independent_bdd_audit.py" \
  "$DATA/$instance/train.csv" \
  "$RUN/${instance}.selected.occam-bdd.txt" > "$RUN/SHA256SUMS"
printf 'BDD_OCCAM_WARMUP_COMPLETE instance=%s audit_status=%s\n' \
  "$instance" "$audit_status" > "$RUN/COMPLETE"
cat "$RUN/COMPLETE"
