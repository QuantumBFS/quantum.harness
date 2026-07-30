#!/usr/bin/env bash
set -euo pipefail

root=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
search_dir="$root/tracks/qcs/solutions/Genshin_Impact-71/search"
ranking="$root/results/occam71/c-window-safe/c_joint_window_ranking_safe_v2.json"

sinfo -o "%P %a %l %D %t %N %G"
squeue -u user_milksang -o "%.18i %.9P %.20j %.2t %.10M %.6D %R"
scontrol show node n006 | grep -E "NodeName=|State=|CfgTRES=|AllocTRES="

cd "$search_dir"
bash -n c_window_safe_ranked_array_v2.slurm
python -m py_compile c_window_rank_safe_v2.py
test -s "$ranking"
python -c '
import json
import sys
p = json.load(open(sys.argv[1], "r", encoding="utf-8"))
assert p["safety"] == {
    "acyclic_boundary": True,
    "boundary_excludes_removed": True,
    "boundary_excludes_root_descendants": True,
}
assert len(p["records"]) == 100
for r in p["records"]:
    assert len(r["roots"]) == 2
    assert r["candidate_gates"] == r["removed_count"] - 1
' "$ranking"
sha256sum \
  c_window_rank_safe_v2.py \
  d_window_sat_safe_remote.py \
  d_window_sat_hpc_safe.py \
  c_window_safe_ranked_array_v2.slurm \
  "$ranking"
