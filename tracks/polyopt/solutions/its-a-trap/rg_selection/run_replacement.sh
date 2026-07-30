#!/bin/bash
# run_replacement.sh — FOUR-HOUR LOCK driver (plan v4 + FINAL EXECUTION PATCH).
# Phases: P2a builds(N=14,20) -> mandatory solves (B->C6->D->A at 14 then 20,
# degate before first D) -> P2b builds(26,30) -> depth lane C10@20 (admission)
# -> E lane. Short-circuits per patch §2/2b. One process at a time.
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_PROJECT="$HOME/code/qh-method/julia-env"
R=results
BUILD_CSV=$R/replacement_build.csv
SOLVE_CSV=$R/replacement_solve.csv
[ -f $BUILD_CSV ] || echo "N,arm,psd_scalars,psd_blocks,largest_block,tsupp_rows,cons_nnz,rg_rows,build_s,rss_gb,status,config_sha16" > $BUILD_CSV
[ -f $SOLVE_CSV ] || echo "N,arm,E,pfeas,dfeas,mu,scalarized,mosek_rows,newwords,gamma2_dim,rg_rows,wall_s,rss_gb,status,config_sha16" > $SOLVE_CSV
log() { echo "$(date -Is) $*" | tee -a $R/replacement_driver.log; }

memguard() {
  FREE=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
  [ "$FREE" -ge 4 ] || { log "MEM-GUARD only ${FREE}G free"; return 1; }
}

build_row() { # N ARM — 3G cap, 180 s, no optimize!
  local NN=$1 AA=$2
  grep -q "^$NN,$AA," $BUILD_CSV && { log "skip build $AA@$NN (resume)"; return 0; }
  memguard || return 1
  timeout 180 systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=0 \
    julia replace_arm.jl "$NN" "$AA" build 2>&1 | tail -3
  local RC=$?
  grep -q "^$NN,$AA," $BUILD_CSV || echo "$NN,$AA,,,,,,,,,KILLED_rc$RC," >> $BUILD_CSV
  log "build $AA@$NN rc=$RC"
}

SOLVED_OK() { grep -q "^$1,$2,.*,OPTIMAL," $SOLVE_CSV; }

solve_row() { # N ARM — 18G cap, 1800 s
  local NN=$1 AA=$2
  grep -q "^$NN,$AA," $SOLVE_CSV && { log "skip solve $AA@$NN (resume)"; return 0; }
  memguard || { echo "$NN,$AA,,,,,,,,,,,,MEMGUARD_SKIP," >> $SOLVE_CSV; return 1; }
  timeout 1800 systemd-run --user --scope -q -p MemoryMax=18G -p MemorySwapMax=0 \
    julia replace_arm.jl "$NN" "$AA" solve 2>&1 | tail -3
  local RC=$?
  grep -q "^$NN,$AA," $SOLVE_CSV || echo "$NN,$AA,,,,,,,,,,,,KILLED_rc$RC," >> $SOLVE_CSV
  log "solve $AA@$NN rc=$RC"
}

# ---- P2a: mandatory build rows first (patch §5) ----
for NN in 14 20; do for AA in B C6 D A; do build_row $NN $AA; done; done
log "P2a build rows done"

# ---- degate (patch §1): before any D/E solve; failure blocks D/E only ----
DE_OK=0
if [ -f $R/replacement_degate.txt ] && grep -q "^degate PASS" $R/replacement_degate.txt; then
  DE_OK=1; log "degate cached PASS"
else
  timeout 1800 systemd-run --user --scope -q -p MemoryMax=18G -p MemorySwapMax=0 \
    julia replace_arm.jl degate 2>&1 | tail -4
  grep -q "^degate PASS" $R/replacement_degate.txt 2>/dev/null && DE_OK=1
  log "degate DE_OK=$DE_OK"
fi

# ---- mandatory solves: B -> C6 -> D -> A at N=14 then N=20 ----
for NN in 14 20; do
  solve_row $NN B
  solve_row $NN C6
  if SOLVED_OK $NN C6; then
    if [ "$DE_OK" -eq 1 ]; then solve_row $NN D
    else echo "$NN,D,,,,,,,,,,,,DEGATE_BLOCKED," >> $SOLVE_CSV; log "D@$NN blocked by degate"; fi
  else
    echo "$NN,D,,,,,,,,,,,,C6_SHORT_CIRCUIT," >> $SOLVE_CSV; log "D@$NN short-circuited (C6 not OPTIMAL)"
  fi
  solve_row $NN A
done
log "MANDATORY EIGHT ROWS COMPLETE (or recorded)"

# ---- P2b: optional build rows (N=26,30) ----
for NN in 26 30; do for AA in B C6 D A; do build_row $NN $AA; done; done
log "P2b build rows done"

# ---- depth lane @N=20 (v4 §4/§5, patch 2b): C10 then C14 ----
if SOLVED_OK 20 C6; then
  build_row 20 C10
  if grep -q "^20,C10,.*BUILD_OK" $BUILD_CSV; then
    # admission: ED substitution of the n=10 tower at the largest ED-feasible
    # size (N=14; Lemma-1 n<=N-1). Link residuals checked row by row.
    timeout 900 systemd-run --user --scope -q -p MemoryMax=18G -p MemorySwapMax=0 \
      julia replace_arm_admit.jl 2>&1 | tail -3
    if [ -f $R/depth_admit_n10.txt ] && grep -q PASS $R/depth_admit_n10.txt; then
      solve_row 20 C10
    else
      echo "20,C10,,,,,,,,,,,,ADMISSION_FAIL," >> $SOLVE_CSV; log "C10@20 admission fail"
    fi
  else
    log "C10@20 build failed -> depth axis closed at N=20"
  fi
  # C14: ED substitution requires N>=15; dense-ED ceiling is N=14 with the
  # existing machinery -> UNAVAILABLE by the depth-admission law (no new code)
  grep -q "^20,C14," $SOLVE_CSV || echo "20,C14,,,,,,,,,,,,UNAVAILABLE_ED_CEILING," >> $SOLVE_CSV
  if grep -q "^20,C10,.*,OPTIMAL," $SOLVE_CSV; then :; else
    log "C10@20 not OPTIMAL -> C14@20 stays UNAVAILABLE (patch §2)"
  fi
else
  log "depth lane skipped (C6@20 not OPTIMAL)"
fi

# ---- E lane (opportunistic; requires degate + C6@N OPTIMAL) ----
for NN in 14 20; do
  if [ "$DE_OK" -eq 1 ] && SOLVED_OK $NN C6; then
    solve_row $NN E
  else
    grep -q "^$NN,E," $SOLVE_CSV || echo "$NN,E,,,,,,,,,,,,SKIPPED_GATE_OR_C6," >> $SOLVE_CSV
  fi
done
log "DRIVER COMPLETE"
