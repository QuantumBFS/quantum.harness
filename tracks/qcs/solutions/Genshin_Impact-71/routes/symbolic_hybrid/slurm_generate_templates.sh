#!/usr/bin/env bash
#SBATCH --job-name=occ71-templates
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/arithmetic-templates-seed42/logs/job-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/arithmetic-templates-seed42/logs/job-%j.err

set -euo pipefail
export PYTHONHASHSEED=42

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
code="$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid"
search="$repo/tracks/qcs/solutions/Genshin_Impact-71/search"
discovery="$repo/results/occam71/routes/symbolic-hybrid-seed42"
out="$repo/results/occam71/routes/arithmetic-templates-seed42"

mkdir -p "$out/logs"
python -u "$code/generate_arithmetic_templates.py" \
    --discovery-root "$discovery" \
    --search-dir "$search" \
    --out "$out"
{
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'slurm_node=%s\n' "$SLURMD_NODENAME"
    printf 'root_seed=%s\n' 42
} > "$out/run-metadata.txt"
sha256sum "$out/template-summary.json" \
    "$out"/*/template.txt "$out"/*/template-audit.json \
    > "$out/SHA256SUMS"
