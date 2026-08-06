#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

output=${1:-benchmarks/results/linux-x86-runner}
generated=benchmarks/generated
binary=target/release/occam71_rust
mkdir -p "$output" "$generated"

./scripts/fetch-occam-data.sh
cargo build --quiet --release -p occam71_rust

"$binary" generate-adder --bits 8 --output "$generated/add-8.txt"
"$binary" generate-dataset --operation add --bits 8 --samples 100000 \
  --seed 115008 --output "$generated/add-8-100000.csv"
"$binary" generate-adder --bits 16 --output "$generated/add-16.txt"
"$binary" generate-dataset --operation add --bits 16 --samples 100000 \
  --seed 115016 --output "$generated/add-16-100000.csv"
"$binary" generate-multiplier --bits 4 --output "$generated/mul-4.txt"
"$binary" generate-dataset --operation multiply --bits 4 --samples 100000 \
  --seed 115004 --output "$generated/mul-4-100000.csv"

run_case() {
  label=$1
  circuit=$2
  dataset=$3
  "$binary" verify --backend cross-check --circuit "$circuit" --dataset "$dataset"
  julia vendor/occam-circuit/verify.jl "$circuit" "$dataset"
  for backend in scalar packed; do
    "$binary" benchmark --backend "$backend" --warmup 5 --iterations 30 --batches 5 \
      --circuit "$circuit" --dataset "$dataset" \
      --json "$output/$label-$backend.json"
  done
}

run_case official-add-8 vendor/occam-circuit/adder8.txt \
  vendor/occam-circuit/datasets/mystery-A/train.csv
run_case add-8-100000 "$generated/add-8.txt" "$generated/add-8-100000.csv"
run_case add-16-100000 "$generated/add-16.txt" "$generated/add-16-100000.csv"
run_case mul-4-100000 "$generated/mul-4.txt" "$generated/mul-4-100000.csv"

python3 - "$output" <<'PY'
import json
import platform
import subprocess
import sys
from pathlib import Path

output = Path(sys.argv[1])
cases = ("official-add-8", "add-8-100000", "add-16-100000", "mul-4-100000")

def command(*args):
    return subprocess.check_output(args, text=True).strip()

protocol = {
    "schema_version": 1,
    "profile": "github-actions-linux-x86-64",
    "platform": platform.platform(),
    "architecture": platform.machine(),
    "processor": command("bash", "-lc", "lscpu | awk -F: '/Model name/{gsub(/^ +/,\"\",$2); print $2; exit}'"),
    "logical_cores": int(command("nproc")),
    "memory_bytes": int(command("bash", "-lc", "awk '/MemTotal/{print $2*1024}' /proc/meminfo")),
    "rust": command("rustc", "--version"),
    "julia": command("julia", "--version"),
}
(output / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")

lines = [
    "# Linux x86-64 GitHub Actions Benchmark",
    "",
    f"- Platform: {protocol['platform']}",
    f"- Processor: {protocol['processor']}",
    f"- Logical cores: {protocol['logical_cores']}",
    f"- Memory: {protocol['memory_bytes'] / 1e9:.1f} GB",
    f"- Rust: `{protocol['rust']}`",
    f"- Julia: `{protocol['julia']}`",
    "",
    "| Case | Samples | Gates | Scalar median ms | Packed median ms | Speedup |",
    "|---|---:|---:|---:|---:|---:|",
]
for case in cases:
    scalar = json.loads((output / f"{case}-scalar.json").read_text())
    packed = json.loads((output / f"{case}-packed.json").read_text())
    assert scalar["schema_version"] == packed["schema_version"] == 3
    assert scalar["exact_matches"] == packed["exact_matches"] == scalar["samples"]
    assert scalar["correct_bits"] == packed["correct_bits"] == scalar["total_bits"]
    scalar_ns = scalar["evaluation"]["median_ns"]
    packed_ns = packed["evaluation"]["median_ns"]
    lines.append(
        f"| {case} | {scalar['samples']:,} | {scalar['gates']} | "
        f"{scalar_ns / 1e6:.6f} | {packed_ns / 1e6:.6f} | {scalar_ns / packed_ns:.2f}× |"
    )
(output / "report.md").write_text("\n".join(lines) + "\n")
PY

echo "portable benchmark artifacts written to $output"
