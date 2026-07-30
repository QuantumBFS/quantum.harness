#!/usr/bin/env bash
#SBATCH --job-name=occ71-abc-routes
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/abc-routes-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/abc-routes-%j.err

set -euo pipefail

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
code="$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid"
work="$repo/results/occam71/routes/symbolic-hybrid-seed42"
abc="$repo/results/occam71/tools/abc-e76768b9d34f/job-42912/source/abc"

test -x "$abc"
mkdir -p "$work/logs"
cd "$code"
python3 -m py_compile routes.py run_experiments.py run_abc_only.py test_routes.py
python3 test_routes.py -v
python3 routes.py bdd --work "$work"
python3 run_abc_only.py --work "$work" --abc "$abc"
{
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'slurm_node=%s\n' "$SLURMD_NODENAME"
    printf 'root_seed=%s\n' 42
    sha256sum "$abc" routes.py run_experiments.py run_abc_only.py test_routes.py
} > "$work/abc-run-metadata-$SLURM_JOB_ID.txt"
test -f "$work/ABC_FLOW_COMPLETE"
