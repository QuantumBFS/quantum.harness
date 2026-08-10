#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
INTENT= SOURCE_STATE_MANIFEST= DESTINATION_URI= PROFILE= RECEIPT_DIR=
CREATE_ONLY=false
while (($#)); do
  case "$1" in
    --intent) INTENT="$2"; shift 2 ;;
    --source-state-manifest) SOURCE_STATE_MANIFEST="$2"; shift 2 ;;
    --destination-uri) DESTINATION_URI="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="$2"; shift 2 ;;
    --create-only) CREATE_ONLY=true; shift ;;
    *) die "unexpected argument: $1" ;;
  esac
done
$CREATE_ONLY || die "--create-only is required"
[[ "$DESTINATION_URI" =~ ^ssh://([^/]+)(/.*)$ ]] || die "destination must be an ssh URI"
HOST="${BASH_REMATCH[1]}"; DESTINATION="${BASH_REMATCH[2]}"
RESULTS_ROOT="$(jq -er '.results_root // .payload.approved_results_root' "$PROFILE")"
[[ "$DESTINATION" == "$RESULTS_ROOT" || "$DESTINATION" == "$RESULTS_ROOT/"* ]] ||
  die "backup destination is outside profile-approved results"
[[ "$HOST" == "$(jq -er '.payload.controller' "$PROFILE")" ]] ||
  die "backup host does not match destination profile"
[[ "$SOURCE_STATE_MANIFEST" = /* &&
   "$(realpath -e -- "$SOURCE_STATE_MANIFEST")" == "$SOURCE_STATE_MANIFEST" ]] ||
  die "backup source must be a canonical no-symlink absolute path"
[[ "$(jq -er '.schema' "$SOURCE_STATE_MANIFEST")" == "challenge15.orchestration-state-manifest.v1" ]] ||
  die "backup source is not a state manifest"
SHA="$(sha256sum -- "$SOURCE_STATE_MANIFEST" | awk '{print $1}')"
INTENT_SHA="$(sha256sum -- "$INTENT" | awk '{print $1}')"
[[ "$(jq -Sc '.payload' "$INTENT" | sha256sum | awk '{print $1}')" == "$(jq -er '.payload_sha256' "$INTENT")" ]] ||
  die "backup intent payload SHA256 mismatch"
PROFILE_SHA="$(jq -er '.payload_sha256' "$PROFILE")"
[[ "$PROFILE_SHA" == "$(jq -er '.payload.profile_sha256' "$INTENT")" ]] ||
  die "backup profile is not intent-bound"
FINAL="$DESTINATION/$SHA.json"
ssh -- "$HOST" "set -eu; mkdir -p -- '$DESTINATION'; test \"\$(realpath -e -- '$DESTINATION')/$SHA.json\" = '$FINAL'"
mkdir -p -- "$RECEIPT_DIR"
RECEIPT="$RECEIPT_DIR/$SHA.json"
validate_receipt() {
  [[ "$(jq -er '.schema' "$RECEIPT")" == "challenge15.state-manifest-backup-receipt.v1" &&
     "$(jq -er '.payload.source_sha256' "$RECEIPT")" == "$SHA" &&
     "$(jq -er '.payload.intent_sha256' "$RECEIPT")" == "$INTENT_SHA" &&
     "$(jq -er '.payload.destination' "$RECEIPT")" == "$HOST:$FINAL" ]] ||
    die "existing backup receipt identity mismatch"
  [[ "$(jq -Sc '.payload' "$RECEIPT" | sha256sum | awk '{print $1}')" == "$(jq -er '.payload_sha256' "$RECEIPT")" ]] ||
    die "existing backup receipt payload SHA256 mismatch"
}
REMOTE_SHA="$(ssh -- "$HOST" "if test -f '$FINAL'; then sha256sum -- '$FINAL' | awk '{print \$1}'; fi")"
if [[ -s "$RECEIPT" ]]; then
  validate_receipt
  [[ "$REMOTE_SHA" == "$SHA" ]] || die "existing backup receipt remote bytes changed"
  printf '%s\n' "$RECEIPT"
  exit 0
fi
if [[ -n "$REMOTE_SHA" ]]; then
  [[ "$REMOTE_SHA" == "$SHA" ]] || die "existing remote backup hash mismatch"
else
  PARTIAL="$FINAL.partial.$INTENT_SHA"
  ssh -- "$HOST" "set -eu; test ! -e '$PARTIAL'"
  scp -- "$SOURCE_STATE_MANIFEST" "$HOST:$PARTIAL"
  ssh -- "$HOST" "set -eu; test \"\$(sha256sum -- '$PARTIAL' | awk '{print \$1}')\" = '$SHA'; test ! -e '$FINAL'; mv -T -- '$PARTIAL' '$FINAL'; sync -f '$DESTINATION'"
fi
PAYLOAD="$(jq -Scn --arg source "$SOURCE_STATE_MANIFEST" --arg sha "$SHA" \
  --arg intent "$INTENT_SHA" --arg profile "$PROFILE_SHA" --arg destination "$HOST:$FINAL" \
  --arg created "$(jq -er '.payload.created_at_utc' "$INTENT")" \
  '{source_state_manifest:$source,source_sha256:$sha,intent_sha256:$intent,
    profile_sha256:$profile,destination:$destination,created_at_utc:$created}')"
PAYLOAD_SHA="$(printf '%s' "$PAYLOAD" | sha256sum | awk '{print $1}')"
PARTIAL_RECEIPT="$RECEIPT.partial.$$"
jq -Scn --argjson payload "$PAYLOAD" --arg sha "$PAYLOAD_SHA" \
  '{schema:"challenge15.state-manifest-backup-receipt.v1",payload:$payload,payload_sha256:$sha}' \
  > "$PARTIAL_RECEIPT"
sync -f "$PARTIAL_RECEIPT"
mv -T -- "$PARTIAL_RECEIPT" "$RECEIPT"
sync -f "$RECEIPT_DIR"
printf '%s\n' "$RECEIPT"
