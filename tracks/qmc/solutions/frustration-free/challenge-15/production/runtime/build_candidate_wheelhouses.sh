#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 OUTPUT_ROOT" >&2
  exit 2
fi

OUTPUT=$1
RUNTIME_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -e "$OUTPUT" || -L "$OUTPUT" ]]; then
  echo "candidate output already exists: $OUTPUT" >&2
  exit 1
fi

mkdir -p -- "$(dirname -- "$OUTPUT")"
mkdir -- "$OUTPUT"
cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then
    rm -rf -- "$OUTPUT"
  fi
  exit "$status"
}
trap cleanup EXIT
mkdir -- "$OUTPUT/cpu" "$OUTPUT/cuda12"

python3.12 -m pip download \
  --dest "$OUTPUT/cpu" \
  --require-hashes \
  --requirement "$RUNTIME_ROOT/cpu/requirements.txt" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 312 \
  --abi cp312 \
  --abi abi3 \
  --only-binary=:all:

python3.12 -m pip download \
  --dest "$OUTPUT/cuda12" \
  --require-hashes \
  --requirement "$RUNTIME_ROOT/cuda12/requirements.txt" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 312 \
  --abi cp312 \
  --abi abi3 \
  --only-binary=:all:

python3.12 "$RUNTIME_ROOT/verify_wheelhouse.py" \
  --profile cpu --root "$OUTPUT/cpu"
python3.12 "$RUNTIME_ROOT/verify_wheelhouse.py" \
  --profile cuda12 --root "$OUTPUT/cuda12"
trap - EXIT
