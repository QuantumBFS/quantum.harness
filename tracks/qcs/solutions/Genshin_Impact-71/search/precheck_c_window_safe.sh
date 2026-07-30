#!/usr/bin/env bash
set -euo pipefail

root=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
search_dir="$root/tracks/qcs/solutions/Genshin_Impact-71/search"

sinfo -o "%P %a %l %D %t %N %G"
squeue -u user_milksang -o "%.18i %.9P %.20j %.2t %.10M %.6D %R"
scontrol show node n006 | grep -E "NodeName=|State=|CfgTRES=|AllocTRES="

cd "$search_dir"
bash -n c_window_safe_rerun_t02_v1.slurm
sha256sum \
  d_window_sat_safe_remote.py \
  d_window_sat_hpc_safe.py \
  c_window_safe_rerun_t02_v1.slurm
