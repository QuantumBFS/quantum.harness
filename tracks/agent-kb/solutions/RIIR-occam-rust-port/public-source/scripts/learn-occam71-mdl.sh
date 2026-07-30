#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
data_root="$repo_root/vendor/occam-circuit/datasets"
generated_root="$repo_root/target/occam71-mdl"
research_manifest="$repo_root/challenge-71-occam/solutions/rewrite-it-in-rust/research-manifest.json"
mode=${1:-run}
instances=(mystery-A mystery-B mystery-C mystery-D)

if [[ "$mode" != "run" && "$mode" != "--check" ]]; then
    echo "usage: $0 [--check]" >&2
    exit 2
fi

if [[ ! -d "$data_root" ]]; then
    "$repo_root/scripts/fetch-occam-data.sh"
fi

cargo build --quiet --release -p occam71_rust --manifest-path "$repo_root/Cargo.toml"
binary="$repo_root/target/release/occam71_rust"

rm -rf "$generated_root"
mkdir -p "$generated_root"

for instance in "${instances[@]}"; do
    instance_root="$generated_root/$instance"
    mkdir -p "$instance_root"
    "$binary" learn-mdl \
        --train "$data_root/$instance/train.csv" \
        --test-inputs "$data_root/$instance/test_inputs.csv" \
        --commitment "$data_root/$instance/commitment.sha256" \
        --circuit "$instance_root/circuit.txt" \
        --predictions "$instance_root/test_outputs.csv" \
        --report "$instance_root/report.json"
    "$binary" verify \
        --dataset "$data_root/$instance/train.csv" \
        --circuit "$instance_root/circuit.txt" \
        --backend cross-check >"$instance_root/verification.txt"
done

if [[ "$mode" == "--check" ]]; then
    if [[ ! -f "$research_manifest" ]]; then
        echo "research manifest is absent: $research_manifest" >&2
        exit 1
    fi
    for instance in "${instances[@]}"; do
        actual=$(shasum -a 256 "$generated_root/$instance/report.json" | awk '{print $1}')
        expected=$(jq -er \
            ".official_mdl_reports[\"$instance\"].report_sha256" \
            "$research_manifest")
        if [[ "$actual" != "$expected" ]]; then
            echo "$instance report mismatch: expected $expected, got $actual" >&2
            exit 1
        fi
    done
    echo "Occam #71 MDL report hashes match the committed research manifest."
else
    echo "Occam #71 MDL artifacts written to $generated_root"
fi
