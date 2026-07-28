#!/bin/bash
# LOCAL, after fetch: merge per-cell results.csv files (one header + all rows)
# into a single results.csv in the run dir. Usage: merge_results.sh <rundir>
set -eu
RUN="${1:?usage: merge_results.sh <rundir>}"
first=1
for f in "$RUN"/cell_*/results.csv; do
  [ -f "$f" ] || continue
  if [ $first -eq 1 ]; then cat "$f"; first=0; else tail -n +2 "$f"; fi
done > "$RUN/results.csv"
echo "merged: $(($(wc -l < "$RUN/results.csv") - 1)) rows -> $RUN/results.csv"
