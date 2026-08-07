#!/usr/bin/env bash
set -euo pipefail

root=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
search_dir="$root/tracks/qcs/solutions/Genshin_Impact-71/search"
build_run="$root/results/occam71/tools/eslim-build-51e9f774/job-42598"

sinfo -o "%P %a %l %D %t %N %G"
squeue -u user_milksang -o "%.18i %.9P %.20j %.2t %.10M %.6D %R"
scontrol show node n006 | grep -E "NodeName=|State=|CfgTRES=|AllocTRES="

cd "$search_dir"
bash -n slurm_eslim_grid_abc_d109_seed42.sh
grep -qx SUCCESS "$build_run/BUILD_READY"
sha256sum --check "$build_run/built_modules_sha256.txt"
test -s "$root/results/occam71/reference-355/mystery-A.txt"
test -s "$root/results/occam71/reference-355/mystery-B.txt"
test -s "$root/results/occam71/reference-355/mystery-C.txt"
test -s "$root/results/occam71/eslim/D-pilot-build42598-size6-seed42/job-42633/candidate.txt"
sha256sum \
  slurm_eslim_grid_abc_d109_seed42.sh \
  bridge.py \
  verify_candidate.py \
  audit_d_formula.py \
  "$root/results/occam71/reference-355/mystery-A.txt" \
  "$root/results/occam71/reference-355/mystery-B.txt" \
  "$root/results/occam71/reference-355/mystery-C.txt" \
  "$root/results/occam71/eslim/D-pilot-build42598-size6-seed42/job-42633/candidate.txt"
