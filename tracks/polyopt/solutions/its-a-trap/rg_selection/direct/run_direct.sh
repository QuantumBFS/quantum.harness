#!/bin/bash
# run_direct.sh — DIRECT-CG MVP driver: G0..G5 gates, then arms B->C->A->D
# at N=10 (primary) + B->C at N=8 (degenerate control). Fresh process per
# stage/arm; 18G solve cap / 6G gate cap; 10-min debug law.
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_PROJECT="$HOME/code/qh-method/julia-env"
log() { echo "$(date -Is) $*" | tee -a driver.log; }
run() { # cap timeout stage...
  local CAP=$1 TMO=$2; shift 2
  timeout "$TMO" systemd-run --user --scope -q -p MemoryMax="$CAP" -p MemorySwapMax=0 \
    julia direct_mvp.jl "$@" 2>&1 | grep -vE '^┌|^│|^└' | tail -6
  log "stage $* rc=$?"
}
[ -f solve_results.csv ] || echo "N,arm,E,pfeas,dfeas,mu,scalarized,rows,newwords,wall_s,rss_gb,status" > solve_results.csv

run 6G 600 g0
run 6G 900 greg
# gates verdict check: all PASS required before solves (stop law)
if grep -q ",FAIL," soundness_gates.csv; then
  log "GATE FAILURE — stop law: no solves"; exit 1
fi
run 6G 600 g3
run 18G 1200 g4
if grep -q ",FAIL," soundness_gates.csv; then
  log "G3/G4 FAILURE — stop law: no solves"; exit 1
fi
for SPEC in "10 B" "10 C" "10 A" "10 D" "8 B" "8 C"; do
  grep -q "^${SPEC/ /,}," solve_results.csv && { log "skip $SPEC"; continue; }
  run 18G 1800 solve $SPEC
  grep -q "^${SPEC/ /,}," solve_results.csv || echo "${SPEC/ /,},,,,,,,,,,KILLED" >> solve_results.csv
done
log "DIRECT MVP DRIVER COMPLETE"
