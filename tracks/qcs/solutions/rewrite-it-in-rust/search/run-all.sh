#!/bin/sh
set -eu

export LC_ALL=C

search_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
solution_root=$(CDPATH= cd -- "$search_root/.." && pwd)
mode=${1:---check}

if [ "$mode" != "--check" ]; then
    echo "usage: $0 [--check]" >&2
    exit 2
fi

cargo test --locked --manifest-path "$search_root/Cargo.toml"

temporary=$(mktemp -d "${TMPDIR:-/tmp}/occam71-snapshot.XXXXXX")
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
cargo run --quiet --release --locked \
    --manifest-path "$search_root/Cargo.toml" -- \
    experiment-run \
    --config "$solution_root/research/config.json" \
    --tasks "$solution_root/research/tasks.json" \
    --raw "$temporary/raw.jsonl"

if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$temporary/raw.jsonl" | awk '{print $1}')
else
    actual=$(shasum -a 256 "$temporary/raw.jsonl" | awk '{print $1}')
fi
expected=$(awk -F'"' \
    '/"raw_matrix_sha256"/ { print $4; exit }' \
    "$solution_root/research-manifest.json")
if [ "$actual" != "$expected" ]; then
    echo "research raw matrix hash mismatch: expected $expected, got $actual" >&2
    exit 1
fi

echo "Standalone Occam source, artifacts, and 20,480-trial matrix verified."
