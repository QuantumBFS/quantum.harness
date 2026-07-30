#!/bin/bash
#SBATCH --job-name=occam71-ip-milp
#SBATCH --partition=home
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/ip-milp/run-%j.log

set -euo pipefail
ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search/ip_milp"
VENV="$ROOT/results/occam71/tools/scipy-milp-venv"
OUT="$ROOT/results/occam71/ip-milp/job-${SLURM_JOB_ID}"
REF="$ROOT/results/occam71/reference-355"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
mkdir -p "$OUT"
sha256sum "$CODE/exact_milp.py" "$CODE/run_experiments.py" \
  "$CODE/requirements.lock" "$0" > "$OUT/source-sha256.txt"
printf 'job_id=%s\nnode=%s\nsubmitted_seed=42\n' \
  "$SLURM_JOB_ID" "$(hostname)" > "$OUT/submission.txt"
"$VENV/bin/python" -u "$CODE/run_experiments.py" \
  --reference-dir "$REF" \
  --output-dir "$OUT" \
  --mode all \
  --time-limit 300 \
  --witness-count 128 \
  --windows-per-circuit 3
