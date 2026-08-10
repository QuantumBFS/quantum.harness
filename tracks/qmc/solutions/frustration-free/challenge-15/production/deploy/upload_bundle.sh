#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
BUNDLE= BUNDLE_SHA256= HOST= DESTINATION_ROOT= INTENT= CLAIM_ROOT= RECEIPT_DIR= PROFILE= SOURCE_CONTROLLER= SOURCE_PROFILE=
while (($#)); do
  case "$1" in
    --bundle) BUNDLE="$2"; shift 2 ;;
    --bundle-sha256) BUNDLE_SHA256="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --destination-root) DESTINATION_ROOT="$2"; shift 2 ;;
    --intent) INTENT="$2"; shift 2 ;;
    --claim-root) CLAIM_ROOT="$2"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --source-controller) SOURCE_CONTROLLER="$2"; shift 2 ;;
    --source-profile) SOURCE_PROFILE="$2"; shift 2 ;;
    *) die "unexpected argument: $1" ;;
  esac
done
for value in BUNDLE BUNDLE_SHA256 HOST DESTINATION_ROOT INTENT CLAIM_ROOT RECEIPT_DIR PROFILE SOURCE_CONTROLLER SOURCE_PROFILE; do
  [[ "${!value:-}" ]] || die "missing upload argument: $value"
done
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")/../orchestrate" && pwd -P)"
exec "$SCRIPT_DIR/transfer_once.sh" \
  --intent "$INTENT" --claim-root "$CLAIM_ROOT" --receipt-dir "$RECEIPT_DIR" \
  --source-host "$SOURCE_CONTROLLER" --destination-host "$HOST" --source "$BUNDLE" \
  --destination "$DESTINATION_ROOT/$BUNDLE_SHA256" \
  --expected-sha256 "$BUNDLE_SHA256" --profile "$PROFILE" \
  --source-profile "$SOURCE_PROFILE" --create-only
