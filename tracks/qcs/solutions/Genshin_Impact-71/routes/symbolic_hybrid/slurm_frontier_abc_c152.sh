#!/usr/bin/env bash
#SBATCH --job-name=occ71-c152-abc
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/frontier-abc-c152-d109-seed42/logs/job-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/frontier-abc-c152-d109-seed42/logs/job-%j.err

set -euo pipefail
export PYTHONHASHSEED=42

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
code="$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid"
search="$repo/tracks/qcs/solutions/Genshin_Impact-71/search"
work="$repo/results/occam71/routes/frontier-abc-c152-d109-seed42"
abc="$repo/results/occam71/tools/abc-e76768b9d34f/job-42912/source/abc"
circuit_c="$repo/results/occam71/eslim/C-stage2-from154-grid-seed42/03-size7-job43188/candidate.txt"
circuit_d="$repo/results/occam71/frontier-349/netlists/mystery-D.txt"

mkdir -p "$work/logs"
test "$(sha256sum "$abc" | awk '{print $1}')" = \
    a971b5a85892e3bf2d09b6d62eaf6f608d7638936e39d6e4b3095e9c72c9c771
test "$(sha256sum "$circuit_c" | awk '{print $1}')" = \
    67540307369fedfffdb2b1a6473eff5e0bbfeb0e4873d03fddbeceb653cd071c
test "$(sha256sum "$circuit_d" | awk '{print $1}')" = \
    cd3f317f4a0b88818e54869e40b4550fd67549f8eb4a5eb02c74db4ec6864dbd

python -u "$code/run_frontier_abc_c152.py" \
    --work "$work" \
    --abc "$abc" \
    --bridge "$search/bridge.py" \
    --circuit-c "$circuit_c" \
    --circuit-d "$circuit_d"

{
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'slurm_node=%s\n' "$SLURMD_NODENAME"
    printf 'root_seed=%s\n' 42
    printf 'abc_sha256=%s\n' "$(sha256sum "$abc" | awk '{print $1}')"
} > "$work/run-metadata.txt"
sha256sum "$work/frontier-abc-summary.json" \
    "$work/C/summary.partial.json" "$work/D/summary.partial.json" \
    > "$work/SHA256SUMS"
