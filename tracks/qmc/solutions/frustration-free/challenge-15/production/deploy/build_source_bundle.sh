#!/usr/bin/env bash
set -euo pipefail
[[ "$#" == 2 && "$1" == "--output-dir" ]] || { printf '%s\n' "usage: build_source_bundle.sh --output-dir PATH" >&2; exit 2; }
ROOT="$(cd -- "$(dirname -- "$0")/../.." && pwd -P)"
OUT="$2"
[[ "$OUT" = /* && ! -e "$OUT" ]] || { printf '%s\n' "output must be a new absolute path" >&2; exit 2; }
mkdir -m 700 -- "$OUT"
(cd "$ROOT" && {
  printf '%s\n' src production pyproject.toml uv.lock |
    LC_ALL=C sort > "$OUT/MEMBERS"
  tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
    -cf "$OUT/source.tar" src production pyproject.toml uv.lock
})
sha256sum -- "$OUT/source.tar" "$OUT/MEMBERS" | LC_ALL=C sort -k2 > "$OUT/SHA256SUMS"
sync -f "$OUT/SHA256SUMS"
