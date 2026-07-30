#!/usr/bin/env bash
#SBATCH --job-name=occam71-bdd
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-5
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/bdd-route/logs/%A_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/bdd-route/logs/%A_%a.err

set -euo pipefail

ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search/bdd_route"
DATA="$ROOT/results/occam71/occam-circuit/datasets"
RUN="$ROOT/results/occam71/bdd-route/job-${SLURM_ARRAY_JOB_ID}/task-${SLURM_ARRAY_TASK_ID}"
mkdir -p "$RUN"

instances=(
  practice-add-n4
  practice-mul-n4
  mystery-A
  mystery-B
  mystery-C
  mystery-D
)
instance="${instances[$SLURM_ARRAY_TASK_ID]}"

python3 -u "$CODE/decision_diagram_learn_v2.py" \
  --dataset-root "$DATA" \
  --instance "$instance" \
  --output-dir "$RUN" \
  --seed 42 \
  --validation-fraction 0.2 \
  --sift-variables 6 \
  --adjacent-passes 2

set +e
python3 -u "$CODE/independent_bdd_audit.py" \
  --instance "$instance" \
  --netlist "$RUN/${instance}.bdd.txt" \
  --json "$RUN/${instance}.independent-audit.json"
audit_status=$?
set -e

printf '%s\n' "$audit_status" > "$RUN/audit_exit_status.txt"
sha256sum \
  "$CODE/decision_diagram_learn.py" \
  "$CODE/decision_diagram_learn_v2.py" \
  "$CODE/independent_bdd_audit.py" \
  "$DATA/$instance/train.csv" \
  "$RUN/${instance}.bdd.txt" > "$RUN/SHA256SUMS"
printf 'BDD_ROUTE_COMPLETE instance=%s audit_status=%s\n' \
  "$instance" "$audit_status" > "$RUN/COMPLETE"
cat "$RUN/COMPLETE"
