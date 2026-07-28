#!/bin/sh
set -eu

export LC_ALL=C

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "usage: $0 DATASET_ROOT [OUTPUT_ROOT]" >&2
    exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
solution_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
dataset_root=$1
output_root=${2:-$solution_root}
target_dir=$(mktemp -d "${TMPDIR:-/tmp}/occam71-rust-target.XXXXXX")
trap 'rm -rf "$target_dir"' EXIT HUP INT TERM

for suffix in A B C D; do
    instance="mystery-$suffix"
    for input in train.csv test_inputs.csv commitment.sha256; do
        if [ ! -f "$dataset_root/$instance/$input" ]; then
            echo "missing $dataset_root/$instance/$input" >&2
            exit 1
        fi
    done
done

CARGO_TARGET_DIR="$target_dir" cargo build --release \
    --manifest-path "$script_dir/rust/Cargo.toml"
binary="$target_dir/release/occam71_rust"

for suffix in A B C D; do
    instance="mystery-$suffix"
    "$binary" learn \
        --instance "$instance" \
        --train "$dataset_root/$instance/train.csv" \
        --test-inputs "$dataset_root/$instance/test_inputs.csv" \
        --commitment "$dataset_root/$instance/commitment.sha256" \
        --output-dir "$output_root"
done

"$binary" write-manifest --output-dir "$output_root"
echo "Occam #71 artifacts written to $output_root"
