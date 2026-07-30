#!/usr/bin/env bash
set -euo pipefail

root=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
search_dir="$root/tracks/qcs/solutions/Genshin_Impact-71/search"
ranking="$root/results/occam71/c154-window-safe/c154_joint_window_ranking_safe_v3.json"
parent="$root/results/occam71/eslim/grid-build42598-seed42/05-C-size5-job43027/candidate.txt"

sinfo -o "%P %a %l %D %t %N %G"
squeue -u user_milksang -o "%.18i %.9P %.20j %.2t %.10M %.6D %R"
scontrol show node n006 | grep -E "NodeName=|State=|CfgTRES=|AllocTRES="

cd "$search_dir"
bash -n c154_window_safe_ranked_array_v3.slurm
test -s "$ranking"
python -c '
import json
import sys
p = json.load(open(sys.argv[1], "r", encoding="utf-8"))
assert p["safety"] == {
    "acyclic_boundary": True,
    "boundary_excludes_removed": True,
    "boundary_excludes_root_descendants": True,
    "roots_functional_of_boundary": True,
}
assert p["valid_structural_candidates"] >= 100
assert len(p["records"]) == 100
for r in p["records"]:
    assert len(r["roots"]) == 2
    assert r["candidate_gates"] == r["removed_count"] - 1
' "$ranking"
test "$(sha256sum "$parent" | cut -d' ' -f1)" = \
  "f9396ee77462152c03fe061a4676944dc04e83787ef2a3915263bd2be8010bd9"
python audit_c_formula.py "$parent" > /dev/null
sha256sum \
  c154_window_safe_ranked_array_v3.slurm \
  c_window_rank_safe_v3.py \
  d_window_sat_safe_remote.py \
  d_window_sat_hpc_safe.py \
  audit_c_formula.py \
  "$ranking" \
  "$parent"
