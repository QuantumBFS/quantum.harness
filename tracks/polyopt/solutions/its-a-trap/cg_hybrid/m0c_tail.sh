#!/usr/bin/env bash
# M0-C tail — waits for local queue v3 to finish, then runs the 4 regression
# pairs (8 isolated julia processes) from the METHOD worktree, then re-runs
# the M1 tower gates for row provenance. Serial; one systemd scope per cell.
set -u
WT="$(cd "$(dirname "$0")/../../../../.." && pwd)"      # method worktree root
MAINQ="$HOME/code/quantum.harness/tracks/polyopt/results/targets-20260728-171149/queue.out"
OUT="$WT/tracks/polyopt/solutions/its-a-trap/cg_hybrid/m0c_results.jsonl"
LOG="$WT/tracks/polyopt/solutions/its-a-trap/cg_hybrid/m0c_gate.txt"
CELL="$WT/tracks/polyopt/solutions/its-a-trap/cg_hybrid/m0c_cell.jl"
export PATH="$HOME/.juliaup/bin:$PATH"

echo "m0c_tail armed $(date -Is); waiting for queue v3" > "$LOG"
until grep -q 'TARGETS QUEUE v3 FINISHED' "$MAINQ" 2>/dev/null; do sleep 120; done
echo "queue v3 finished; starting M0-C $(date -Is)" >> "$LOG"

for spec in "10 rdm8" "14 rdm8" "10 configA" "14 configA"; do
  set -- $spec
  for variant in stock adapter; do
    echo "=== m0c N=$1 cfg=$2 variant=$variant start $(date -Is)" >> "$LOG"
    systemd-run --user --scope --quiet -p MemoryMax=19G -p MemorySwapMax=512M \
      julia -t 2 --project="$WT/julia-env" "$CELL" "$1" "$2" "$variant" "$OUT" >> "$LOG" 2>&1
    echo "=== exit=$? $(date -Is)" >> "$LOG"
  done
done

python3 - "$OUT" "$LOG" <<'PY'
import json, sys, itertools
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
ok = True
with open(sys.argv[2], "a") as log:
    for (N, cfg) in [(10,"rdm8"),(14,"rdm8"),(10,"configA"),(14,"configA")]:
        es = {r["variant"]: r["E"] for r in rows if r["N"]==N and r["cfg"]==cfg}
        if len(es) < 2:
            log.write(f"M0C {cfg} N={N}: MISSING ARM {sorted(es)}\n"); ok = False; continue
        d = abs(es["stock"] - es["adapter"]); passed = d <= 1e-8; ok &= passed
        log.write(f"M0C {cfg} N={N}: |E_adapter-E_GSB| = {d:.3e}  {'PASS' if passed else 'FAIL'}\n")
    log.write("M0-C GATE " + ("GREEN" if ok else "RED") + "\n")
PY

# M1 gates re-run for provenance (writes tower gate outputs in the worktree)
systemd-run --user --scope --quiet -p MemoryMax=8G \
  julia -t 2 --project="$WT/julia-env" \
  "$WT/tracks/polyopt/solutions/its-a-trap/cg_hybrid/tower.jl" \
  "$WT/tracks/polyopt/solutions/its-a-trap/cg_hybrid" >> "$LOG" 2>&1
echo "M0C TAIL DONE $(date -Is)" >> "$LOG"
