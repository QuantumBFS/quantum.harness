#!/bin/bash
# run_ext.sh — DirectCG N-extension driver (execution patch §7 order):
# provenance(done) -> C14 -> wbundle -> D14 -> C20 -> D20 -> C4@14 ->
# N12 grid -> N26/30 C/D builds. C-before-D short-circuit; D four-condition
# gate; per-N gates before every new-N C.
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_PROJECT="$HOME/code/qh-method/julia-env"
log() { echo "$(date -Is) $*" | tee -a driver.log; }
run() { local CAP=$1 TMO=$2; shift 2
  timeout "$TMO" systemd-run --user --scope -q -p MemoryMax="$CAP" -p MemorySwapMax=0 \
    julia direct_mvp.jl "$@" 2>&1 | grep -vE '^┌|^│|^└' | tail -4
  log "stage $* rc=$?"; }
OK() { grep -q "^$1,$2,.*OPTIMAL" solve_results.csv; }
HAVE() { grep -q "^$1,$2," solve_results.csv; }
solve1() { local NN=$1 AA=$2
  HAVE $NN $AA && { log "skip $AA@$NN"; return; }
  run 18G 1800 solve $NN $AA
  HAVE $NN $AA || echo "$NN,$AA,,,,,,,,,,KILLED" >> solve_results.csv; }
GPASS() { tail -40 soundness_gates.csv | grep "$1" | tail -1 | grep -q ",PASS,"; }

# C14 (gates first)
run 6G 900 gateN 14 D2
GPASS "Gifc_D2_N14" && GPASS "Ged_D2_N14" && solve1 14 C || log "C14 blocked by gates"
# wbundle (diagnostic table; does not change D's bundle id)
run 6G 900 wbundle
# D14 (needs C14 OPTIMAL + dgate)
if OK 14 C; then
  run 6G 900 dgate 14
  if GPASS "Gdgate_N14"; then solve1 14 D
  else HAVE 14 D || echo "14,D,,,,,,,,,,STRUCTURALLY_ABSORBED" >> solve_results.csv; fi
else HAVE 14 D || echo "14,D,,,,,,,,,,SKIPPED_AFTER_C_FAILURE" >> solve_results.csv; fi
# C20 / D20
run 6G 900 gateN 20 D2
GPASS "Gifc_D2_N20" && solve1 20 C || log "C20 blocked by gates"
if OK 20 C; then
  run 6G 900 dgate 20
  if GPASS "Gdgate_N20"; then solve1 20 D
  else HAVE 20 D || echo "20,D,,,,,,,,,,STRUCTURALLY_ABSORBED" >> solve_results.csv; fi
else HAVE 20 D || echo "20,D,,,,,,,,,,SKIPPED_AFTER_C_FAILURE" >> solve_results.csv; fi
# C4@14 (own map certificate + ED inside gateN D4)
run 6G 900 gateN 14 D4
GPASS "Gifc_D4_N14" && GPASS "Ged_D4_N14" && GPASS "Gmap2" && solve1 14 C4 || log "C4 blocked by gates"
run 6G 300 buildarm 14 C4
# N12 grid: gates, then B -> C -> A -> D
run 6G 900 gateN 12 D2
for AA in B C A; do solve1 12 $AA; done
if OK 12 C; then
  run 6G 900 dgate 12
  if GPASS "Gdgate_N12"; then solve1 12 D
  else HAVE 12 D || echo "12,D,,,,,,,,,,STRUCTURALLY_ABSORBED" >> solve_results.csv; fi
else HAVE 12 D || echo "12,D,,,,,,,,,,SKIPPED_AFTER_C_FAILURE" >> solve_results.csv; fi
for AA in A B C D; do run 3G 300 buildarm 12 $AA 2>/dev/null || true; done
# N26/30 C/D build probes (A/B build rows exist from the morning campaign)
for NN in 26 30; do for AA in C D; do run 3G 300 buildarm $NN $AA; done; done
log "EXT DRIVER COMPLETE"
