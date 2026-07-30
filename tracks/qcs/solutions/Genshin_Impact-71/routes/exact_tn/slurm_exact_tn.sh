#!/usr/bin/env bash
#SBATCH --job-name=occam71-exact-tn
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=04:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/exact-tn-seed42/logs/exact-tn-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/exact-tn-seed42/logs/exact-tn-%j.err

set -euo pipefail

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
code="$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/exact_tn"
symbolic="$repo/results/occam71/routes/symbolic-hybrid-seed42"
output="$repo/results/occam71/routes/exact-tn-seed42"

mkdir -p "$output/logs"
{
  echo "job_id=${SLURM_JOB_ID}"
  echo "host=$(hostname)"
  echo "start=$(date --iso-8601=seconds)"
  echo "root_seed=42"
  echo "python=$(python3 --version 2>&1)"
  echo "code_sha256=$(sha256sum "$code/exact_tn.py" | awk '{print $1}')"
  echo "slurm_sha256=$(sha256sum "$code/slurm_exact_tn.sh" | awk '{print $1}')"
} > "$output/run-metadata-${SLURM_JOB_ID}.txt"

python3 -u "$code/test_exact_tn.py" -v
python3 -u "$code/exact_tn.py" \
  --symbolic-root "$symbolic" \
  --route-dir "$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid" \
  --baseline-root "$symbolic" \
  --output "$output" \
  --instances mystery-A mystery-B mystery-C mystery-D

{
  echo "end=$(date --iso-8601=seconds)"
  echo "status=success"
} >> "$output/run-metadata-${SLURM_JOB_ID}.txt"
