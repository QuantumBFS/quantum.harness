#!/bin/sh
set -eu

export LC_ALL=C

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
data_root="$repo_root/vendor/occam-circuit/datasets"
solution_root="$repo_root/challenge-71-occam/solutions/rewrite-it-in-rust"
mode=${1:-write}

if [ ! -d "$data_root" ]; then
    "$repo_root/scripts/fetch-occam-data.sh"
fi

if [ "$mode" = "--check" ]; then
    "$repo_root/scripts/learn-occam71-mdl.sh" --check
    "$repo_root/scripts/optimize-occam71.sh" --check
    "$repo_root/scripts/run-occam-experiments.sh" --check
    "$repo_root/scripts/render-occam-research" \
        --raw "$repo_root/experiments/occam-generalization/raw.jsonl" \
        --output "$repo_root/experiments/occam-generalization" \
        --check
    "$repo_root/scripts/root-occam-research-evidence" --check
    cargo test --quiet -p occam71_rust --manifest-path "$repo_root/Cargo.toml" \
        --test optimized_artifacts
    cargo test --quiet -p occam71_rust --manifest-path "$repo_root/Cargo.toml" \
        --test research_artifacts
    cargo test --quiet -p occam71_rust --manifest-path "$repo_root/Cargo.toml" \
        --test solution_artifacts
    julia --startup-file=no "$repo_root/scripts/verify-occam71.jl"
    echo "Occam #71 optimized artifacts are reproducible and independently verified."
    exit 0
fi

cargo build --release -p occam71_rust --manifest-path "$repo_root/Cargo.toml"
binary="$repo_root/target/release/occam71_rust"

if [ "$mode" = "write" ]; then
    generated_root="$solution_root"
else
    echo "usage: $0 [--check]" >&2
    exit 2
fi

for suffix in A B C D; do
    instance="mystery-$suffix"
    "$binary" learn \
        --instance "$instance" \
        --train "$data_root/$instance/train.csv" \
        --test-inputs "$data_root/$instance/test_inputs.csv" \
        --commitment "$data_root/$instance/commitment.sha256" \
        --output-dir "$generated_root"
done

"$binary" write-manifest --output-dir "$generated_root"

echo "Occam #71 artifacts written to $solution_root"
