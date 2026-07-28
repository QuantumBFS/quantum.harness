#!/usr/bin/env bash
# Relaunched Track-1 queue after the N=100 memory frontier (Tue evening).
# Facts forcing the change: CONFIG A v100 killed at 18.5 GB (Mosek factor);
# v140 killed in lso construction; J2=0.5@N=100 (pso=0) killed by the KERNEL
# OOM at 23.8 GB — the burst outran the 0.5 s in-process monitor, and the
# OOM took the whole tmux scope (driver included) down with it.
#
# Fixes in this driver:
#   * every cell runs in its OWN systemd scope with MemoryMax=17G — a memory
#     burst OOMs the cell (exit 137), never the driver;
#   * ascending-N Target-1 ladder at sizes that fit: N = 50, 60, 80
#     (all Table 3 rows, all with Bethe references);
#   * Target-2 J2 sweep moved N=100 → N=40: fits memory AND gains published
#     source-of-record references (paper Table 4 is the N=40 J1-J2 table;
#     MG J2=0.5 stays exact at -0.375).
# N >= 100 is conceded on 24 GB hardware pending the .wslconfig decision.
set -u
OUT="$1"; export PATH="$HOME/.juliaup/bin:$PATH"
export MAX_WALL_S=7200 MAX_RSS_GB=16 MAX_PROC_SWAP_GB=0.5
H=tracks/polyopt/solutions/its-a-trap/overnight_harness.jl
STEP=t1q

run_cell() {  # label cellspec
  echo "=== $1 start $(date -Is)"
  systemd-run --user --scope --quiet -p MemoryMax=17G -p MemorySwapMax=512M \
    julia -t 2 --project=julia-env "$H" "$OUT" "$STEP" "$2"
  local rc=$?
  echo "=== $1 exit=$rc $(date -Is)"
  if [ "$rc" -eq 137 ] || [ "$rc" -eq 9 ]; then
    echo "- $1 hit the memory frontier (rc=$rc)" >> "$OUT/LOG.md"
  fi
  return $rc
}

# Target-1 ladder, ascending; a memory death truncates the remaining ladder
LADDER_ALIVE=1
for N in 50 60 80; do
  if [ "$LADDER_ALIVE" -eq 1 ]; then
    run_cell "lad_N$N" "v$N:$N" || { rc=$?; if [ "$rc" -eq 137 ] || [ "$rc" -eq 9 ]; then LADDER_ALIVE=0; fi; }
  else
    echo "- ladder N=$N skipped (frontier above)" >> "$OUT/LOG.md"
  fi
done

# Target-2 J2 sweep at N=40 (independent of the ladder's fate)
for J2 in 0.5 0.2 1.0 0.4 0.6 0.8; do
  run_cell "j2_${J2}_N40" "j40_${J2}:40:model=j1j2,J2=${J2},pso=0" || true
done

echo "TARGETS QUEUE v2 FINISHED $(date -Is)" | tee -a "$OUT/LOG.md"
