#!/bin/bash
# run_smalln.sh — small-N comparison (4A.7 + 4B.7): 5 arms x N=10/12/14 on the
# lso=false chassis. Sequential, one process per arm, 18G cap, 4G-free guard.
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_PROJECT="$HOME/code/qh-method/julia-env"
CSV=results/smalln_arms_raw.csv
[ -f "$CSV" ] || echo "N,arm,E,pfeas,dfeas,mu,wall_s,rss_gb,scalarized,nrows,newwords" > "$CSV"
for N in 10 12 14; do
  for ARM in full core corerg coresel adaptive; do
    grep -q "^$N,$ARM," "$CSV" && { echo "skip $N/$ARM (resume)"; continue; }
    FREE=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
    [ "$FREE" -lt 4 ] && { echo "MEM-GUARD ${FREE}G free -> abort before $N/$ARM"; exit 4; }
    systemd-run --user --scope -q -p MemoryMax=18G -p MemorySwapMax=0 \
      julia smalln_arm.jl "$N" "$ARM" 2>&1 | tail -1
    echo "$(date -Is) $N $ARM rc=$?" >> results/smalln_driver.log
  done
done
echo "SMALLN ARMS COMPLETE"
