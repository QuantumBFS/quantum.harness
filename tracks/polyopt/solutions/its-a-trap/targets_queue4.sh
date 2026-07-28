#!/usr/bin/env bash
# Queue v3 — J2@N=40 remainder at a raised memory budget.
# Why: j40_0.5 completed (78 s solve, MG point converges fast) but j40_0.2 was
# killed by the 16 GB in-process cap at RSS 16.02 GB at ~85% of the Mosek
# solve — generic J2 needs more than 16 GB at N=40 CONFIG A pso=0. New budget:
# cgroup MemoryMax=21G, monitor 18.5 GB (box has ~23.5 GB; per-cell scopes keep
# a burst from touching the driver — the queue-v2 protection stays).
set -u
OUT="$1"; export PATH="$HOME/.juliaup/bin:$PATH"
export MAX_WALL_S=7200 MAX_RSS_GB=20.3 MAX_PROC_SWAP_GB=0.5
H=tracks/polyopt/solutions/its-a-trap/overnight_harness.jl
STEP=t1q

run_cell() {
  echo "=== $1 start $(date -Is)"
  systemd-run --user --scope --quiet -p MemoryMax=21G -p MemorySwapMax=512M \
    julia -t 2 --project=julia-env "$H" "$OUT" "$STEP" "$2"
  local rc=$?
  echo "=== $1 exit=$rc $(date -Is)"
  if [ "$rc" -eq 137 ] || [ "$rc" -eq 9 ] || [ "$rc" -eq 139 ]; then
    echo "- $1 hit the memory frontier at 18.5 GB (rc=$rc)" >> "$OUT/LOG.md"
  fi
  return $rc
}

for J2 in 0.4 0.2 0.6 0.8; do
  run_cell "j2v3_${J2}_N40" "j40_${J2}:40:model=j1j2,J2=${J2},pso=0" || true
done

echo "TARGETS QUEUE v3 FINISHED (v4) $(date -Is)" | tee -a "$OUT/LOG.md"
