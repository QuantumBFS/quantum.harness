#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

output=${1:-benchmarks/experiments/2026-07-28-direct-ingestion-apple-m4}
generated=benchmarks/generated
raw=benchmarks/results/raw/ingestion
binary=target/release/occam71_rust
mkdir -p "$output" "$generated" "$raw"

cargo build --quiet --release -p occam71_rust

"$binary" generate-adder --bits 8 --output "$generated/add-8.txt"
"$binary" generate-multiplier --bits 4 --output "$generated/mul-4.txt"

generate_case() {
  operation=$1
  bits=$2
  samples=$3
  seed=$4
  path=$5
  "$binary" generate-dataset --operation "$operation" --bits "$bits" \
    --samples "$samples" --seed "$seed" --output "$path"
}

generate_case add 8 100000 115008 "$generated/add-8-100000.csv"
generate_case add 8 1000000 115108 "$generated/add-8-1000000.csv"
generate_case multiply 4 100000 115004 "$generated/mul-4-100000.csv"
generate_case multiply 4 1000000 115104 "$generated/mul-4-1000000.csv"

run_case() {
  label=$1
  circuit=$2
  dataset=$3

  "$binary" benchmark --backend packed --warmup 5 --iterations 30 --batches 5 \
    --circuit "$circuit" --dataset "$dataset" --json "$output/$label.json" \
    > "$raw/$label-benchmark.txt"

  for backend in packed packed-legacy; do
    for repetition in 1 2 3 4 5; do
      /usr/bin/time -l -o "$raw/$label-$backend-$repetition.time" \
        "$binary" verify --backend "$backend" --circuit "$circuit" \
        --dataset "$dataset" > "$raw/$label-$backend-$repetition.out"
    done
  done
}

run_case add-8-100000 "$generated/add-8.txt" "$generated/add-8-100000.csv"
run_case add-8-1000000 "$generated/add-8.txt" "$generated/add-8-1000000.csv"
run_case mul-4-100000 "$generated/mul-4.txt" "$generated/mul-4-100000.csv"
run_case mul-4-1000000 "$generated/mul-4.txt" "$generated/mul-4-1000000.csv"

python3 - "$raw" "$output/process.json" <<'PY'
import json
import platform
import re
import statistics
import subprocess
import sys
from pathlib import Path

raw = Path(sys.argv[1])
destination = Path(sys.argv[2])
cases = ("add-8-100000", "add-8-1000000", "mul-4-100000", "mul-4-1000000")

def parse_time(path):
    text = path.read_text()
    wall = re.search(r"([0-9.]+) real", text)
    rss = re.search(r"([0-9]+)  maximum resident set size", text)
    if wall is None or rss is None:
        raise SystemExit(f"cannot parse {path}")
    return float(wall.group(1)), int(rss.group(1))

processor = platform.processor()
if processor in ("", "arm", "arm64", "aarch64"):
    processor = "Apple M4"

result = {
    "schema_version": 1,
    "profile": "apple-m4-direct-ingestion",
    "platform": platform.platform(),
    "processor": processor,
    "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
    "repetitions": 5,
    "cases": {},
}
for case in cases:
    result["cases"][case] = {}
    for backend in ("packed", "packed-legacy"):
        measurements = [
            parse_time(raw / f"{case}-{backend}-{index}.time")
            for index in range(1, 6)
        ]
        wall = [item[0] for item in measurements]
        rss = [item[1] for item in measurements]
        result["cases"][case][backend] = {
            "wall_seconds": wall,
            "maximum_resident_bytes": rss,
            "median_wall_seconds": statistics.median(wall),
            "median_maximum_resident_bytes": statistics.median(rss),
        }
destination.write_text(json.dumps(result, indent=2) + "\n")
PY

./scripts/render-ingestion-report --output "$output/report.md" \
  --results "$output"

echo "direct-ingestion benchmark artifacts written to $output"
