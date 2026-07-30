#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
config="$repo_root/experiments/occam-generalization-v2/config.json"
tasks="$repo_root/experiments/occam-generalization-v2/tasks.json"
output="$repo_root/experiments/occam-generalization-v2"
jobs=1
check=false
smoke=false

while (($#)); do
    case "$1" in
        --config) config=$2; shift 2 ;;
        --tasks) tasks=$2; shift 2 ;;
        --output) output=$2; shift 2 ;;
        --jobs) jobs=$2; shift 2 ;;
        --check) check=true; shift ;;
        --smoke) smoke=true; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

cargo build --quiet --release -p occam71_rust --manifest-path "$repo_root/Cargo.toml"
binary="$repo_root/target/release/occam71_rust"
"$repo_root/scripts/fetch-abc.sh"
abc="$repo_root/target/tools/abc/e76768b9d34f9dc67cb6608efecd55db271ff849/abc"

if [[ "$smoke" == true ]]; then
    config="$repo_root/experiments/occam-generalization-v2/smoke-config.json"
    output="$repo_root/target/occam-research-smoke"
fi
mkdir -p "$output"

arguments=(
    experiment-run
    --config "$config"
    --tasks "$tasks"
    --raw-measured "$output/raw-measured.jsonl"
    --semantic "$output/semantic.jsonl"
    --abc "$abc"
    --jobs "$jobs"
)
if [[ "$check" == true ]]; then
    arguments+=(--check-semantic)
fi
"$binary" "${arguments[@]}"
