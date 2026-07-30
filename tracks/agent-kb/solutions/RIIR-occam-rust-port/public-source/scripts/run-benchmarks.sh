#!/bin/sh
set -eu

mode=${1:-full}
if [ "$mode" != "full" ] && [ "$mode" != "--verify-only" ]; then
  echo "usage: $0 [full|--verify-only]" >&2
  exit 2
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

generated="benchmarks/generated"
results="benchmarks/results"
raw="$results/raw"
binary="target/release/occam71_rust"

if [ ! -f "vendor/occam-circuit/verify.jl" ]; then
  "./scripts/fetch-occam-data.sh"
fi

mkdir -p "$generated" "$results" "$raw"
cargo build --quiet --release --manifest-path "Cargo.toml" -p occam71_rust

{
  date -u '+utc=%Y-%m-%dT%H:%M:%SZ'
  pmset -g batt | sed -n "1s/^/power_source=/p"
  pmset -g batt | sed -n '2s/.*\t\([0-9][0-9]*%; [^;]*\).*/battery_state=\1/p'
  pmset -g custom | awk '/lowpowermode/{print "lowpowermode=" $2; exit}'
  uptime | sed 's/^/system_load=/'
} > "$raw/apple-m4-environment.txt"

"$binary" generate-adder --bits 8 --output "$generated/add-8.txt"
"$binary" generate-dataset --operation add --bits 8 --samples 100000 \
  --seed 115008 --output "$generated/add-8-100000.csv"
"$binary" generate-adder --bits 16 --output "$generated/add-16.txt"
"$binary" generate-dataset --operation add --bits 16 --samples 100000 \
  --seed 115016 --output "$generated/add-16-100000.csv"
"$binary" generate-multiplier --bits 4 --output "$generated/mul-4.txt"
"$binary" generate-dataset --operation multiply --bits 4 --samples 100000 \
  --seed 115004 --output "$generated/mul-4-100000.csv"

verify_case() {
  label=$1
  circuit=$2
  dataset=$3
  "$binary" verify --backend cross-check --circuit "$circuit" --dataset "$dataset" \
    > "$raw/$label-cross-check.txt"
  julia "vendor/occam-circuit/verify.jl" "$circuit" "$dataset" \
    > "$raw/$label-julia-verify.txt"
}

verify_case official-add-8 \
  "vendor/occam-circuit/adder8.txt" \
  "vendor/occam-circuit/datasets/mystery-A/train.csv"
verify_case add-8-100000 "$generated/add-8.txt" "$generated/add-8-100000.csv"
verify_case add-16-100000 "$generated/add-16.txt" "$generated/add-16-100000.csv"
verify_case mul-4-100000 "$generated/mul-4.txt" "$generated/mul-4-100000.csv"

if [ "$mode" = "--verify-only" ]; then
  echo "all Julia/Rust correctness checks passed"
  exit 0
fi

benchmark_case() {
  label=$1
  circuit=$2
  dataset=$3
  order=$4
  for backend in $order; do
    "$binary" benchmark --backend "$backend" --warmup 5 --iterations 30 --batches 5 \
      --circuit "$circuit" --dataset "$dataset" \
      --json "$results/$label-$backend.json" \
      > "$raw/$label-$backend-summary.txt"
    for repetition in 1 2 3 4 5; do
      /usr/bin/time -l -o "$raw/$label-$backend-process-time-$repetition.txt" \
        "$binary" verify --backend "$backend" --circuit "$circuit" --dataset "$dataset" \
        > "$raw/$label-$backend-process-output-$repetition.txt"
    done
  done
  for repetition in 1 2 3 4 5; do
    /usr/bin/time -l -o "$raw/$label-julia-process-time-$repetition.txt" \
      julia "vendor/occam-circuit/verify.jl" "$circuit" "$dataset" \
      > "$raw/$label-julia-process-output-$repetition.txt"
  done
}

benchmark_case official-add-8 \
  "vendor/occam-circuit/adder8.txt" \
  "vendor/occam-circuit/datasets/mystery-A/train.csv" "scalar packed"
benchmark_case add-8-100000 "$generated/add-8.txt" "$generated/add-8-100000.csv" \
  "packed scalar"
benchmark_case add-16-100000 "$generated/add-16.txt" "$generated/add-16-100000.csv" \
  "scalar packed"
benchmark_case mul-4-100000 "$generated/mul-4.txt" "$generated/mul-4-100000.csv" \
  "packed scalar"

./scripts/summarize-process-results \
  --raw "$raw" \
  --protocol benchmarks/protocols/apple-m4.json \
  --environment "$raw/apple-m4-environment.txt" \
  --output "$results/apple-m4-process.json"

echo "benchmark results written to $repo_root/$results"
