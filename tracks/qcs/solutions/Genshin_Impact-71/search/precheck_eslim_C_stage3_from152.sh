#!/usr/bin/env bash
set -euo pipefail

root=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
search_dir="$root/tracks/qcs/solutions/Genshin_Impact-71/search"
build_run="$root/results/occam71/tools/eslim-build-51e9f774/job-42598"
parent="$root/results/occam71/eslim/C-stage2-from154-grid-seed42/03-size7-job43188/candidate.txt"

sinfo -o "%P %a %l %D %t %N %G"
squeue -u user_milksang -o "%.18i %.9P %.20j %.2t %.10M %.6D %R"
scontrol show node n006 | grep -E "NodeName=|State=|CfgTRES=|AllocTRES="

cd "$search_dir"
bash -n slurm_eslim_C_stage3_from152_grid.sh
python -m py_compile audit_c_formula.py
grep -qx SUCCESS "$build_run/BUILD_READY"
sha256sum --check "$build_run/built_modules_sha256.txt"
test "$(sha256sum "$parent" | cut -d' ' -f1)" = \
  "67540307369fedfffdb2b1a6473eff5e0bbfeb0e4873d03fddbeceb653cd071c"
python audit_c_formula.py "$parent" \
  --report "$root/results/occam71/eslim/grid-build42598-seed42/05-C-size5-job43027/pre-stage3-formula-audit.json" \
  > /dev/null
sha256sum \
  slurm_eslim_C_stage3_from152_grid.sh \
  audit_c_formula.py \
  bridge.py \
  verify_candidate.py \
  "$parent"
