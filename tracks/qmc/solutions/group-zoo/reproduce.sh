#!/usr/bin/env bash
set -euo pipefail

usage='usage: ./tracks/qmc/solutions/group-zoo/reproduce.sh [RUN_DIR]'
if [[ ${1:-} == --help ]]; then
    printf '%s\n' "$usage"
    exit 0
fi
(( $# <= 1 )) || { printf '%s\n' "$usage" >&2; exit 2; }

solution_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$solution_root/../../../.." && pwd -P)
run_dir=${1:-"$repo_root/tracks/qmc/results/group-zoo-challenge148-20260730"}
[[ "$run_dir" == /* ]] || run_dir="$repo_root/$run_dir"
[[ -f "$run_dir/run.json" ]] || { printf 'reproduce: run.json is missing: %s\n' "$run_dir" >&2; exit 1; }

route_a="$solution_root/route_a"
manifest="$route_a/config/benchmark.json"
raw="$run_dir/route-a/raw"
analysis="$run_dir/route-a/analysis"
[[ -f "$manifest" ]] || { printf 'reproduce: benchmark manifest is missing\n' >&2; exit 1; }
[[ -d "$raw" ]] || { printf 'reproduce: Route A raw-result directory is missing\n' >&2; exit 1; }

julia_bin=${JULIA:-julia}
python_bin=${PYTHON:-python3}

if [[ ${RUN_TESTS:-1} == 1 ]]; then
    "$julia_bin" --project="$route_a" "$route_a/test/test_available_analysis.jl"
    "$julia_bin" --project="$route_a" "$route_a/test/test_runner.jl"
    "$julia_bin" --project="$solution_root/route_b" "$solution_root/route_b/test/runtests.jl"
    "$python_bin" "$route_a/test/test_plot_available_analysis.py"
fi

"$julia_bin" --project="$route_a" "$route_a/scripts/analyze_available_results.jl" \
    --manifest "$manifest" --results "$raw" --output "$analysis"

"$python_bin" -c 'import matplotlib' >/dev/null 2>&1 || {
    printf 'reproduce: matplotlib is required; install route_a/requirements.txt\n' >&2
    exit 1
}
"$python_bin" "$route_a/scripts/plot_available_analysis.py" \
    "$analysis/route_a_available_analysis.json" \
    "$analysis/fit_window_stability.png"

printf 'reproduce: analysis=%s\n' "$analysis/route_a_available_analysis.json"
printf 'reproduce: figure=%s\n' "$analysis/fit_window_stability.png"
