#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
solution_root="$repo_root/challenge-71-occam/solutions/rewrite-it-in-rust"
data_root="$repo_root/vendor/occam-circuit/datasets"
staging_root="$repo_root/target/occam71-optimization"
commit=e76768b9d34f9dc67cb6608efecd55db271ff849
abc="$repo_root/target/tools/abc/$commit/abc"
mode=${1:-write}
instances=(mystery-B mystery-D mystery-C mystery-A)

if [[ "$mode" != "write" && "$mode" != "--check" && "$mode" != "--verify" ]]; then
    echo "usage: $0 [--check|--verify]" >&2
    exit 2
fi

if [[ ! -d "$data_root" ]]; then
    "$repo_root/scripts/fetch-occam-data.sh"
fi
"$repo_root/scripts/fetch-abc.sh"
cargo build --quiet --release -p occam71_rust --manifest-path "$repo_root/Cargo.toml"
binary="$repo_root/target/release/occam71_rust"

rm -rf "$staging_root"
mkdir -p "$staging_root/circuits" "$staging_root/reports"

for instance in "${instances[@]}"; do
    baseline="$staging_root/$instance-baseline.txt"
    git -C "$repo_root" show \
        "v0.2.0:challenge-71-occam/solutions/rewrite-it-in-rust/circuits/$instance.txt" \
        >"$baseline"
    "$binary" optimize-circuit \
        --circuit "$baseline" \
        --abc "$abc" \
        --output "$staging_root/circuits/$instance.txt" \
        --report "$staging_root/reports/$instance.json"
    "$binary" verify \
        --dataset "$data_root/$instance/train.csv" \
        --circuit "$staging_root/circuits/$instance.txt" \
        --backend cross-check >"$staging_root/$instance-train-verification.txt"
    "$binary" verify \
        --dataset "$solution_root/predictions/$instance/test_outputs.csv" \
        --circuit "$staging_root/circuits/$instance.txt" \
        --backend cross-check >"$staging_root/$instance-test-verification.txt"
done

jq -n \
    --arg abc_commit "$commit" \
    --slurpfile a "$staging_root/reports/mystery-A.json" \
    --slurpfile b "$staging_root/reports/mystery-B.json" \
    --slurpfile c "$staging_root/reports/mystery-C.json" \
    --slurpfile d "$staging_root/reports/mystery-D.json" \
    '{
      schema_version: 1,
      baseline: "baseline.json",
      abc_commit: $abc_commit,
      processing_order: ["mystery-B", "mystery-D", "mystery-C", "mystery-A"],
      instances: {
        "mystery-A": $a[0],
        "mystery-B": $b[0],
        "mystery-C": $c[0],
        "mystery-D": $d[0]
      }
    }' >"$staging_root/report.json"

if [[ "$mode" == "--check" ]]; then
    for instance in "${instances[@]}"; do
        cmp "$staging_root/circuits/$instance.txt" "$solution_root/circuits/$instance.txt"
        cmp "$staging_root/reports/$instance.json" \
            "$solution_root/optimization/$instance.json"
    done
    cmp "$staging_root/report.json" "$solution_root/optimization/report.json"
    echo "Occam #71 optimization artifacts are byte-for-byte reproducible."
elif [[ "$mode" == "--verify" ]]; then
    for instance in "${instances[@]}"; do
        jq -e \
            --slurpfile expected "$solution_root/optimization/$instance.json" \
            '
              .selected_gate_count == $expected[0].selected_gate_count and
              .exhaustive_mismatches == 0 and
              .abc.accepted_candidates > 0 and
              .abc.selected_gate_count == .selected_gate_count
            ' "$staging_root/reports/$instance.json" >/dev/null
    done
    jq -e \
        --slurpfile expected "$solution_root/optimization/report.json" \
        '
          .abc_commit == $expected[0].abc_commit and
          ([.instances[] | .exhaustive_mismatches] | all(. == 0)) and
          ([.instances[] | .selected_gate_count] | sort) ==
            ([$expected[0].instances[] | .selected_gate_count] | sort)
        ' "$staging_root/report.json" >/dev/null
    echo "Occam #71 optimization gate counts and full-domain semantics verified."
else
    mkdir -p "$solution_root/optimization"
    for instance in "${instances[@]}"; do
        cp "$staging_root/circuits/$instance.txt" "$solution_root/circuits/$instance.txt"
        cp "$staging_root/reports/$instance.json" \
            "$solution_root/optimization/$instance.json"
    done
    cp "$staging_root/report.json" "$solution_root/optimization/report.json"
    echo "Occam #71 optimized circuits and reports written to $solution_root"
fi
