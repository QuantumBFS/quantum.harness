#!/usr/bin/env bash
set -euo pipefail

run_dir="$1"
script="tracks/mps/solutions/unitempo_fig4_lower_dense_worker.jl"
mkdir -p "$run_dir/logs"
for worker in 0 1 2 3 4 5 6 7; do
  OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 julia --project=.external/fig2-unitempo-env "$script" "$run_dir" "$worker" 8 >"$run_dir/logs/worker-$worker.log" 2>&1 &
done
wait
