#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 {cpu|cuda12} WHEELHOUSE DESTINATION" >&2
  exit 2
fi

PROFILE=$1
WHEELHOUSE=$2
DESTINATION=$3
RUNTIME_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
case "$PROFILE" in
  cpu|cuda12) ;;
  *)
    echo "unknown candidate profile: $PROFILE" >&2
    exit 2
    ;;
esac
if [[ ! -d "$WHEELHOUSE" || -L "$WHEELHOUSE" ]]; then
  echo "wheelhouse must be a real directory: $WHEELHOUSE" >&2
  exit 1
fi
if [[ ! -d "$(dirname -- "$DESTINATION")" ]]; then
  echo "destination parent does not exist: $(dirname -- "$DESTINATION")" >&2
  exit 1
fi

LOCK="${DESTINATION}.lock"
if ! mkdir -- "$LOCK"; then
  echo "exclusive publication lock already exists: $LOCK" >&2
  exit 1
fi

PARTIAL="${DESTINATION}.partial.$$"
PRESERVE_PARTIAL=0
cleanup() {
  status=$?
  if [[ "$PRESERVE_PARTIAL" -eq 0 && -d "$PARTIAL" ]]; then
    rm -rf -- "$PARTIAL"
  fi
  rmdir -- "$LOCK" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT

if [[ -e "$DESTINATION" || -L "$DESTINATION" ]]; then
  echo "destination already exists: $DESTINATION" >&2
  exit 1
fi

python3.12 "$RUNTIME_ROOT/verify_wheelhouse.py" \
  --profile "$PROFILE" --root "$WHEELHOUSE"

if [[ -e "$PARTIAL" || -L "$PARTIAL" ]]; then
  echo "partial destination already exists: $PARTIAL" >&2
  exit 1
fi

python3.12 -m venv "$PARTIAL"
"$PARTIAL/bin/python" -m pip install \
  --no-index \
  --find-links "$WHEELHOUSE" \
  --require-hashes \
  --only-binary=:all: \
  --requirement "$RUNTIME_ROOT/$PROFILE/requirements.txt"
"$PARTIAL/bin/python" -m pip check
if ! python3.12 "$RUNTIME_ROOT/publish_noreplace.py" \
  "$PARTIAL" "$DESTINATION"; then
  PRESERVE_PARTIAL=1
  echo "atomic publication failed; recoverable partial preserved: $PARTIAL" >&2
  exit 1
fi
rmdir -- "$LOCK"
trap - EXIT
