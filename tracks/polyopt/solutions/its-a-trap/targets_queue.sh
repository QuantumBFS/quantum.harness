#!/usr/bin/env bash
# Tonight's Track-1 queue (plan correction 4 — priority order):
#   1  N=100 J2=0      CONFIG A       validation + memory probe
#   2  N=140 J2=0      CONFIG A       memory probe #2
#   -  RSS gate: fit RSS(m) from cells 1-2, project N=200; <= MAX_RSS_GB to run
#   3  N=200 J2=0      CONFIG A       CONDITIONAL on the gate
#   4  N=100 J2=0.5    CONFIG A pso=0 (Remark 6.1)  MG exact ref
#   5  N=100 J2=0.2    CONFIG A pso=0
#   6  N=100 J2=1.0    CONFIG A pso=0
#   7-9 N=100 J2=0.4/0.6/0.8  CONFIG A pso=0   fill-if-room
# Each cell = its own Julia process; an OOM/kill burns only that cell.
set -u
OUT="$1"; export PATH="$HOME/.juliaup/bin:$PATH"
export MAX_WALL_S=7200 MAX_RSS_GB=18 MAX_PROC_SWAP_GB=0.5
H=tracks/polyopt/solutions/its-a-trap/overnight_harness.jl
STEP=t1q

run_cell() {  # label cellspec
  echo "=== $1 start $(date -Is)"
  julia -t 2 --project=julia-env "$H" "$OUT" "$STEP" "$2"
  local rc=$?
  echo "=== $1 exit=$rc $(date -Is)"
  return $rc
}

run_cell "cell1_N100" "v100:100" || true
run_cell "cell2_N140" "v140:140" || true

# ---- RSS gate: linear fit peak_rss vs m from cells 1-2, project N=200 ----
GATE=$(python3 - "$OUT" <<'PY'
import csv, re, sys, glob
out = sys.argv[1]
rows = [r for r in csv.DictReader(open(f"{out}/results.csv")) if r["step"] == "t1q"]
pts = []
for r in rows:
    if r["label"].startswith("v") and r["opt"]:
        logs = glob.glob(f"{out}/cell_logs/t1q_{r['label']}_N{r['N']}.log")
        m = None
        for lg in logs:
            mm = re.search(r"m = (\d+)", open(lg).read())
            if mm: m = int(mm.group(1))
        if m: pts.append((int(r["N"]), m, float(r["peak_rss_gb"])))
if len(pts) < 2:
    print("SKIP insufficient_probe_points", pts); sys.exit()
(n1, m1, r1), (n2, m2, r2) = pts[:2]
mslope = (m2 - m1) / (n2 - n1); m200 = m2 + mslope * (200 - n2)
rslope = (r2 - r1) / (m2 - m1) if m2 != m1 else 0.0
r200 = r2 + rslope * (m200 - m2)
verdict = "RUN" if r200 <= 18.0 else "SKIP"
print(f"{verdict} m100={m1} m140={m2} m200_proj={m200:.0f} rss100={r1:.2f} rss140={r2:.2f} rss200_proj={r200:.2f}GB")
PY
)
echo "RSS_GATE: $GATE" | tee -a "$OUT/LOG.md"
if [[ "$GATE" == RUN* ]]; then
  run_cell "cell3_N200" "v200:200" || true
else
  echo "- N=200 SKIPPED by RSS gate: $GATE" >> "$OUT/LOG.md"
fi

for J2 in 0.5 0.2 1.0 0.4 0.6 0.8; do
  run_cell "cell_J2_${J2}" "j2_${J2}:100:model=j1j2,J2=${J2},pso=0" || true
done

echo "TARGETS QUEUE FINISHED $(date -Is)" | tee -a "$OUT/LOG.md"
