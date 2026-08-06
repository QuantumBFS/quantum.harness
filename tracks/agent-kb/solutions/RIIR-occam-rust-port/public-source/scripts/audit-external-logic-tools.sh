#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output="$repo_root/target/tool-audit.json"

while (($#)); do
    case "$1" in
        --output) output=$2; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

yosys=$(command -v yosys || true)
yosys_abc=$(command -v yosys-abc || true)
espresso=$(command -v espresso || true)

for entry in "yosys:$yosys" "yosys-abc:$yosys_abc" "espresso:$espresso"; do
    name=${entry%%:*}
    executable=${entry#*:}
    if [[ -z "$executable" || ! -x "$executable" ]]; then
        echo "$name is not installed or executable" >&2
        exit 1
    fi
done

cargo run --quiet \
    --manifest-path "$repo_root/Cargo.toml" \
    -p occam71_rust \
    --bin tool_audit \
    -- \
    --yosys "$yosys" \
    --yosys-abc "$yosys_abc" \
    --espresso "$espresso" \
    --espresso-source-commit 0288253ca9459539d341bb1ada10406a74efc721 \
    --output "$output"

echo "Independent Yosys, Yosys ABC, and Espresso audit written to $output"
