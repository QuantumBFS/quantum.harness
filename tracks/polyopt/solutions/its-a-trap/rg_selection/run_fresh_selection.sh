#!/bin/bash
# Fresh replacement-chassis selection driver (Amendment 4C §3 + 4B.3 timer).
# Deterministic lexical order: BASELINE, singletons, pairs. 30-minute TOTAL
# wall from launch; at expiry STOP (no partial choice -> pilot branch).
# Local memory law: one process at a time, 18 GiB scope cap, >=4 GiB free.
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_PROJECT="$HOME/code/qh-method/julia-env"
T0=$(date +%s)
CSV=results/fresh_selection.csv
echo "S,E,pfeas,dfeas,mu,scalarized,nrows,gamma2_dim,newwords,wall_s,rss_gb" > "$CSV"
echo "timer_start=$(date -Is)" > results/fresh_selection_timer.txt
KEYS=(BASELINE
  B_bond_edge B_bond_half B_half B_pair_edge
  B_bond_edge+B_bond_half B_bond_edge+B_half B_bond_edge+B_pair_edge
  B_bond_half+B_half B_bond_half+B_pair_edge B_half+B_pair_edge)
for K in "${KEYS[@]}"; do
  EL=$(( $(date +%s) - T0 ))
  if [ "$EL" -ge 1800 ]; then
    echo "TIMER-EXPIRED at ${EL}s before $K -> STOP (pilot branch)" | tee -a results/fresh_selection_timer.txt
    exit 3
  fi
  FREE=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
  if [ "$FREE" -lt 4 ]; then
    echo "MEM-GUARD: only ${FREE}G free before $K -> STOP" | tee -a results/fresh_selection_timer.txt
    exit 4
  fi
  # 18 GiB HARD scope cap via cgroup (ulimit -v is virtual-address, kills julia)
  systemd-run --user --scope -q -p MemoryMax=18G -p MemorySwapMax=0 \
    julia selection_arm.jl "$K" 2>&1 | tail -2
  RC=$?
  echo "$(date -Is) $K rc=$RC elapsed=$(( $(date +%s) - T0 ))s" >> results/fresh_selection_timer.txt
done
echo "ENUMERATION-COMPLETE elapsed=$(( $(date +%s) - T0 ))s" | tee -a results/fresh_selection_timer.txt
