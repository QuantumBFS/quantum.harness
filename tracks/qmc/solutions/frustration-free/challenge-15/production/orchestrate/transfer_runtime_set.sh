#!/usr/bin/env bash
set -euo pipefail
[[ "$#" -ge 1 ]] || { printf '%s\n' "runtime-set transfer requires transfer_once arguments" >&2; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd -P)"
exec "$SCRIPT_DIR/transfer_bytes.sh" "$@"
