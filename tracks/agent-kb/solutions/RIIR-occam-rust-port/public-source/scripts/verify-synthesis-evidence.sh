#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d "${TMPDIR:-/tmp}/occam71-synthesis.XXXXXX")"
trap 'rm -rf -- "$temporary"' EXIT

cd "$root"

cargo run --quiet --release -p occam71_rust --bin occam71_rust -- synthesize \
  --dataset challenge-71-occam/tests/fixtures/half-adder.csv \
  --max-gates 2 \
  --timeout-seconds 30 \
  --output "$temporary/half-adder.txt" \
  --certificate "$temporary/half-adder-certificate.json"

cmp docs/synthesis/half-adder.txt "$temporary/half-adder.txt"

python3 - \
  docs/synthesis/half-adder-certificate.json \
  "$temporary/half-adder-certificate.json" <<'PY'
import json
import sys

def normalized(path):
    with open(path, encoding="utf-8") as source:
        certificate = json.load(source)
    for attempt in certificate["attempts"]:
        attempt["elapsed_ms"] = 0
    return certificate

checked, regenerated = map(normalized, sys.argv[1:])
if checked != regenerated:
    raise SystemExit("regenerated synthesis certificate differs from checked-in evidence")
PY

julia vendor/occam-circuit/verify.jl \
  "$temporary/half-adder.txt" \
  challenge-71-occam/tests/fixtures/half-adder.csv
