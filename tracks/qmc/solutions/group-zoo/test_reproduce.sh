#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
output=$("$root/reproduce.sh" --help)
[[ "$output" == "usage: ./tracks/qmc/solutions/group-zoo/reproduce.sh [RUN_DIR]" ]]

temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
if "$root/reproduce.sh" "$temporary" >"$temporary/stdout" 2>"$temporary/stderr"; then
    printf 'expected an incomplete run directory to fail\n' >&2
    exit 1
fi
grep -q 'run.json is missing' "$temporary/stderr"
