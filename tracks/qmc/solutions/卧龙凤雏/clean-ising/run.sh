#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
config_arg="${1:-configs/quick.toml}"
if [[ "$config_arg" = /* ]]; then
  config_path="$config_arg"
else
  config_path="$script_dir/$config_arg"
fi
if [[ ! -f "$config_path" ]]; then
  echo "configuration not found: $config_path" >&2
  exit 2
fi

if [[ $# -ge 2 ]]; then
  run_dir="$2"
else
  run_dir="$script_dir/../../../results/clean-ising-$(date +%Y%m%d-%H%M%S)"
fi
mkdir -p "$run_dir"
run_dir="$(cd "$run_dir" && pwd -P)"
case "$run_dir/" in
  *"/solutions/"*)
    echo "output must not live inside tracks/qmc/solutions: $run_dir" >&2
    exit 2
    ;;
esac
if [[ -e "$run_dir/manifest.json" ]]; then
  echo "run directory already contains a manifest: $run_dir" >&2
  exit 2
fi
if [[ ! -x "$script_dir/.venv/bin/python" ]]; then
  echo "analysis environment missing; run 'make setup' in $script_dir" >&2
  exit 2
fi

mkdir -p "$run_dir/raw" "$run_dir/processed" "$run_dir/figures" "$run_dir/.matplotlib"
export MPLCONFIGDIR="$run_dir/.matplotlib"
start_time="$(perl -MTime::HiRes=clock_gettime,CLOCK_MONOTONIC -e 'print clock_gettime(CLOCK_MONOTONIC)')"

echo "building Rust release binary" >&2
cargo build --manifest-path "$script_dir/Cargo.toml" --release --locked
binary="$script_dir/target/release/clean-ising"
"$binary" exact \
  --config "$config_path" \
  --output "$run_dir/raw/exact.jsonl" \
  --manifest "$run_dir/manifest.json"
"$binary" mc \
  --config "$config_path" \
  --output "$run_dir/raw/mc_blocks.jsonl" \
  --manifest "$run_dir/manifest.json"

renderer="$script_dir/../../../../../skills/report/render_report.py"
"$script_dir/analysis/run_analysis_stage.sh" \
  "$run_dir" \
  "$start_time" \
  "$renderer" \
  "$script_dir/.venv/bin/python" \
  "$script_dir/analysis/finalize_runtime.py" \
  "$script_dir/.venv/bin/python" \
  "$script_dir/analysis/run_analysis.py" \
  "$run_dir" \
  --renderer "$renderer"
