#!/bin/bash
#SBATCH --job-name=c2d-fit
#SBATCH --partition=xhacnormalb
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=slurm-2d-%j.out
# Fit-check: reads the L6 row; exit code IS the verdict for releasing L8.
set -u
cd "$HOME/qh-method"
python3 - "tracks/polyopt/results/${RUN_NAME:?}/cell_c2d_L6/results.csv" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
assert rows, "no L6 row"
r = rows[-1]
opt  = r["opt"]
wall = float(r["wall_s"]) if r["wall_s"] and r["wall_s"] != "NaN" else 1e12
rss  = float(r["peak_rss_gb"]) if r["peak_rss_gb"] and r["peak_rss_gb"] != "NaN" else 1e12
print(f"L6: opt={opt} wall={wall:.0f}s rss={rss:.1f}GB "
      f"status={r['termination_status']} limit={r['limit_hit']}")
# release L8 iff: real optimum, no budget breach, and margins leave room for
# the L6->L8 growth (64/36 sites, superlinear): wall<=6h of 7.5h, rss<=80/110
verdict = bool(opt) and not r["limit_hit"] and wall <= 21600 and rss <= 80
print("FIT-CHECK", "PASS -> L8 may be released" if verdict else "FAIL -> stop the chain")
sys.exit(0 if verdict else 1)
PY
