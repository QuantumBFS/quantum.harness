#!/usr/bin/env bash
#SBATCH --job-name=occam71-routes
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/routes-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/routes-%j.err

set -euo pipefail

: "${ABC_BUILD_JOB:?submit with --export=ALL,ABC_BUILD_JOB=<successful build job>}"
repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
code="$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid"
work="$repo/results/occam71/routes/symbolic-hybrid-seed42"
tools="$repo/results/occam71/tools/abc-e76768b9d34f/job-$ABC_BUILD_JOB"

test -f "$tools/BUILD_COMPLETE"
test -x "$tools/bin/abc"
test -x "$tools/bin/espresso"
mkdir -p "$work/logs"

cd "$code"
python3 -m py_compile routes.py run_experiments.py test_routes.py
python3 test_routes.py -v
python3 routes.py bdd --work "$work"
python3 run_experiments.py \
    --work "$work" \
    --abc "$tools/bin/abc" \
    --espresso "$tools/bin/espresso"

{
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'slurm_node=%s\n' "$SLURMD_NODENAME"
    printf 'abc_build_job=%s\n' "$ABC_BUILD_JOB"
    printf 'root_seed=%s\n' 42
    sha256sum routes.py run_experiments.py test_routes.py
} > "$work/run-metadata-$SLURM_JOB_ID.txt"
test -f "$work/FLOW_COMPLETE"
