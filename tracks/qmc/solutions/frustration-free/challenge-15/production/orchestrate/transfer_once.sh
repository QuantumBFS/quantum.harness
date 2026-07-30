#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
INTENT= CLAIM_ROOT= RECEIPT_DIR= SOURCE_HOST= DESTINATION_HOST= SOURCE= DESTINATION= EXPECTED_SHA256= PROFILE= SOURCE_PROFILE=
CREATE_ONLY=false
while (($#)); do
  case "$1" in
    --intent) INTENT="$2"; shift 2 ;;
    --claim-root) CLAIM_ROOT="$2"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="$2"; shift 2 ;;
    --source-host) SOURCE_HOST="$2"; shift 2 ;;
    --destination-host) DESTINATION_HOST="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --destination) DESTINATION="$2"; shift 2 ;;
    --expected-sha256) EXPECTED_SHA256="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --source-profile) SOURCE_PROFILE="$2"; shift 2 ;;
    --create-only) CREATE_ONLY=true; shift ;;
    *) die "unexpected argument: $1" ;;
  esac
done
for value in INTENT CLAIM_ROOT RECEIPT_DIR SOURCE_HOST DESTINATION_HOST SOURCE DESTINATION EXPECTED_SHA256 PROFILE SOURCE_PROFILE; do
  [[ "${!value:-}" ]] || die "missing transfer argument: $value"
done
$CREATE_ONLY || die "--create-only is required"
[[ "$SOURCE" = /* && "$DESTINATION" = /* ]] || die "transfer paths must be absolute"
CORRELATION_ID="$(jq -er '.payload.correlation_id' "$INTENT")"
STARTED_AT="$(jq -er '.payload.created_at_utc' "$INTENT")"
[[ "$(jq -er '.schema' "$INTENT")" == "challenge15.orchestration-attempt-intent.v1" ]] ||
  die "invalid transfer intent schema"
[[ "$(jq -Sc '.payload' "$INTENT" | sha256sum | awk '{print $1}')" == "$(jq -er '.payload_sha256' "$INTENT")" ]] ||
  die "transfer intent payload SHA256 mismatch"
cmp -s -- <(jq -Sc . "$INTENT") "$INTENT" ||
  die "transfer intent is not canonical JSON"
INTENT_SHA="$(sha256sum -- "$INTENT" | awk '{print $1}')"
[[ "$SOURCE_HOST" == "$(jq -er '.payload.source_controller' "$INTENT")" ]] ||
  die "transfer source host is not intent-bound"
[[ "$DESTINATION_HOST" == "$(jq -er '.payload.destination_controller' "$INTENT")" ]] ||
  die "transfer destination host is not intent-bound"
PROFILE_SHA="$(jq -er '.payload_sha256' "$PROFILE")"
[[ "$PROFILE_SHA" == "$(jq -er '.payload.profile_sha256' "$INTENT")" ]] ||
  die "transfer profile is not intent-bound"
[[ "$DESTINATION_HOST" == "$(jq -er '.payload.controller' "$PROFILE")" ]] ||
  die "transfer profile/controller mismatch"
APPROVED_ROOT="$(jq -er '.payload.approved_results_root' "$PROFILE")"
SOURCE_ROOT="$(jq -er '.payload.approved_results_root' "$SOURCE_PROFILE")"
[[ "$SOURCE_HOST" == "$(jq -er '.payload.controller' "$SOURCE_PROFILE")" ]] ||
  die "transfer source profile/controller mismatch"
[[ "$SOURCE" == "$SOURCE_ROOT" || "$SOURCE" == "$SOURCE_ROOT/"* ]] ||
  die "transfer source is outside source profile-approved root"
[[ "$DESTINATION" == "$APPROVED_ROOT" || "$DESTINATION" == "$APPROVED_ROOT/"* ]] ||
  die "transfer destination is outside profile-approved root"
if [[ "$SOURCE_HOST" == "$DESTINATION_HOST" ]]; then
  [[ "$(realpath -e -- "$SOURCE")" == "$SOURCE" ]] ||
    die "transfer source is not a canonical no-symlink path"
else
  [[ "$(ssh "$SOURCE_HOST" realpath -e -- "$SOURCE")" == "$SOURCE" ]] ||
    die "remote transfer source is not a canonical no-symlink path"
fi
DESTINATION_PARENT="$(dirname -- "$DESTINATION")"
mkdir -p -- "$DESTINATION_PARENT"
[[ "$(realpath -e -- "$DESTINATION_PARENT")/$(basename -- "$DESTINATION")" == "$DESTINATION" ]] ||
  die "transfer destination has a symlink or noncanonical ancestor"
mapfile -t INTENT_NAMESPACES < <(jq -er '.payload.create_only_namespace_identities[]' "$INTENT")
printf '%s\n' "${INTENT_NAMESPACES[@]}" | awk -v d="$DESTINATION" '
  d==$0 || index(d,$0 "/")==1 {found=1} END {exit !found}' ||
  die "transfer destination is outside intent namespace"
jq -e --arg sha "$EXPECTED_SHA256" '.payload.input_sha256s | index($sha) != null' "$INTENT" >/dev/null ||
  die "transfer byte hash is not intent-bound"
mkdir -p -- "$CLAIM_ROOT" "$RECEIPT_DIR" "$(dirname -- "$DESTINATION")"
RECEIPT="$RECEIPT_DIR/$CORRELATION_ID.json"
hash_path() {
  if [[ -f "$1" ]]; then
    sha256sum -- "$1" | awk '{print $1}'
  elif [[ -d "$1" ]]; then
    (
      cd "$1"
      shopt -s globstar nullglob
      files=()
      for member in **/*; do [[ -f "$member" && ! -L "$member" ]] && files+=("$member"); done
      ((${#files[@]})) || exit 2
      printf '%s\0' "${files[@]}" | sort -z |
        xargs -0 sha256sum -- | sha256sum | awk '{print $1}'
    )
  else
    return 1
  fi
}
validate_receipt() {
  [[ "$(jq -er '.schema' "$RECEIPT")" == "challenge15.transfer-receipt.v1" ]] ||
    die "existing transfer receipt schema mismatch"
  [[ "$(jq -er '.payload.attempt_intent_sha256' "$RECEIPT")" == "$(jq -er '.payload_sha256' "$INTENT")" &&
     "$(jq -er '.payload.correlation_id' "$RECEIPT")" == "$CORRELATION_ID" &&
     "$(jq -er '.payload.final_path' "$RECEIPT")" == "$DESTINATION" ]] ||
    die "existing transfer receipt identity mismatch"
  local computed
  computed="$(jq -Sc '.payload' "$RECEIPT" | sha256sum | awk '{print $1}')"
  [[ "$computed" == "$(jq -er '.payload_sha256' "$RECEIPT")" ]] ||
    die "existing transfer receipt payload hash mismatch"
  [[ "$(hash_path "$DESTINATION")" == "$EXPECTED_SHA256" ]] ||
    die "existing transfer receipt destination bytes changed"
  local export_sha import_path
  export_sha="$(jq -er '.payload.export_bundle_sha256' "$RECEIPT")"
  jq -e --arg sha "$export_sha" '.payload.input_sha256s | index($sha) != null' "$INTENT" >/dev/null ||
    die "existing transfer export identity is not intent-bound"
  import_path="$RECEIPT_DIR/import-$(jq -er '.payload.import_bundle_sha256' "$RECEIPT").json"
  [[ -s "$import_path" ]] || die "existing transfer import receipt is missing"
}
if [[ -s "$RECEIPT" ]]; then
  validate_receipt
  jq -er '.payload.final_path' "$RECEIPT"
  exit 0
fi
if [[ -e "$DESTINATION" || -L "$DESTINATION" ]]; then
  [[ "$(hash_path "$DESTINATION")" == "$EXPECTED_SHA256" ]] ||
    die "existing destination evidence has wrong SHA256"
  PARTIAL=""
else
  CLAIM="$CLAIM_ROOT/$CORRELATION_ID"
  CLAIM_IDENTITY="$CLAIM/identity.json"
  CLAIM_PAYLOAD="$(jq -Scn --arg intent "$INTENT_SHA" --arg source "$SOURCE_HOST:$SOURCE" \
    --arg destination "$DESTINATION_HOST:$DESTINATION" --arg expected "$EXPECTED_SHA256" \
    --arg profile "$PROFILE_SHA" \
    '{intent_sha256:$intent,source_identity:$source,destination_identity:$destination,expected_sha256:$expected,profile_sha256:$profile}')"
  if mkdir -- "$CLAIM" 2>/dev/null; then
    printf '%s\n' "$CLAIM_PAYLOAD" > "$CLAIM_IDENTITY"
    sync -f "$CLAIM_IDENTITY"; sync -f "$CLAIM_ROOT"
  else
    [[ -s "$RECEIPT" ]] && validate_receipt && jq -er '.payload.final_path' "$RECEIPT" && exit 0
    [[ -s "$CLAIM_IDENTITY" && "$(jq -Sc . "$CLAIM_IDENTITY")" == "$CLAIM_PAYLOAD" ]] ||
      die "transfer claim identity mismatch"
  fi
  mapfile -t RECOVERABLE < <(
    for candidate in "$(dirname -- "$DESTINATION")"/.partial."$EXPECTED_SHA256".*; do
      [[ -e "$candidate" && "$(hash_path "$candidate")" == "$EXPECTED_SHA256" ]] &&
        printf '%s\n' "$candidate"
    done
  )
  ((${#RECOVERABLE[@]} <= 1)) || die "ambiguous promoted transfer destinations"
  UUID="$(cat /proc/sys/kernel/random/uuid)"
  if ((${#RECOVERABLE[@]} == 1)); then
    PARTIAL="${RECOVERABLE[0]}"
  else
    PARTIAL="$(dirname -- "$DESTINATION")/.partial.$EXPECTED_SHA256.$UUID"
    [[ ! -e "$PARTIAL" && ! -L "$PARTIAL" ]] || die "partial destination exists"
    if [[ "$SOURCE_HOST" == "$DESTINATION_HOST" ]]; then
      cp -a -- "$SOURCE" "$PARTIAL"
    else
      scp -rp -- "$SOURCE_HOST:$SOURCE" "$PARTIAL"
    fi
  fi
  [[ "$(hash_path "$PARTIAL")" == "$EXPECTED_SHA256" ]] ||
    die "transferred bytes have wrong SHA256"
  mv -T -- "$PARTIAL" "$DESTINATION"
  sync -f "$(dirname -- "$DESTINATION")"
fi
EXPORT_FILE="$DESTINATION/export.json"
[[ "$(jq -er '.schema' "$EXPORT_FILE")" == "challenge15.export-bundle.v1" ]] ||
  die "destination export envelope is missing"
EXPORT_SHA="$(jq -er '.payload_sha256' "$EXPORT_FILE")"
[[ "$(jq -Sc '.payload' "$EXPORT_FILE" | sha256sum | awk '{print $1}')" == "$EXPORT_SHA" ]] ||
  die "destination export payload SHA256 mismatch"
jq -e --arg sha "$EXPORT_SHA" '.payload.input_sha256s | index($sha) != null' "$INTENT" >/dev/null ||
  die "transfer export identity is not intent-bound"
for field in policy_sha256 source_manifest_sha256 base_configuration_sha256 particles; do
  [[ "$(jq -c --arg field "$field" '.payload[$field]' "$EXPORT_FILE")" ==
     "$(jq -c --arg field "$field" '.payload[$field]' "$INTENT")" ]] ||
    die "transfer export provenance mismatch: $field"
done
IMPORT_PAYLOAD="$(jq -Sc \
  --arg controller "$DESTINATION_HOST" --arg root "$DESTINATION" \
  --arg verified "$STARTED_AT" \
  '.payload | {
    policy_sha256,source_manifest_sha256,runtime_attestations,
    base_configuration_sha256,particles,bundle_sha256,
    destination_controller:$controller,destination_root:$root,
    member_manifest,imported_artifact_sha256:.source_artifact_sha256,
    verified_at_utc:$verified
  }' "$EXPORT_FILE")"
IMPORT_SHA="$(printf '%s' "$IMPORT_PAYLOAD" | sha256sum | awk '{print $1}')"
IMPORT_RECEIPT="$RECEIPT_DIR/import-$IMPORT_SHA.json"
if [[ -e "$IMPORT_RECEIPT" ]]; then
  [[ "$(jq -er '.payload_sha256' "$IMPORT_RECEIPT")" == "$IMPORT_SHA" ]] ||
    die "existing import receipt is corrupt"
else
  jq -Scn --argjson payload "$IMPORT_PAYLOAD" --arg sha "$IMPORT_SHA" \
    '{schema:"challenge15.import-bundle.v1",payload:$payload,payload_sha256:$sha}' \
    > "$IMPORT_RECEIPT"
  sync -f "$IMPORT_RECEIPT"
fi
REMOTE_CLAIM_SHA="$INTENT_SHA"
BYTES="$(du -sb -- "$DESTINATION" | awk '{print $1}')"
TRANSFER_PAYLOAD="$(jq -Scn \
  --arg direction "$SOURCE_HOST->$DESTINATION_HOST" \
  --arg export_sha "$EXPORT_SHA" --arg import_sha "$IMPORT_SHA" \
  --arg source_controller "$SOURCE_HOST" --arg destination_controller "$DESTINATION_HOST" \
  --arg source_identity "$SOURCE_HOST:$SOURCE" \
  --arg destination_identity "$DESTINATION_HOST:$DESTINATION" \
  --arg partial "$PARTIAL" --arg final "$DESTINATION" --argjson bytes "$BYTES" \
  --arg intent "$(jq -er '.payload_sha256' "$INTENT")" \
  --arg correlation "$CORRELATION_ID" --arg claim "$REMOTE_CLAIM_SHA" \
  --arg started "$STARTED_AT" --arg verified "$STARTED_AT" \
  --arg policy "$(jq -er '.payload.policy_sha256' "$EXPORT_FILE")" \
  --arg source_manifest "$(jq -er '.payload.source_manifest_sha256' "$EXPORT_FILE")" \
  --argjson runtimes "$(jq -c '.payload.runtime_attestations' "$EXPORT_FILE")" \
  --arg base "$(jq -er '.payload.base_configuration_sha256' "$EXPORT_FILE")" \
  --argjson particles "$(jq -er '.payload.particles' "$EXPORT_FILE")" \
  '{policy_sha256:$policy,source_manifest_sha256:$source_manifest,
    runtime_attestations:$runtimes,base_configuration_sha256:$base,particles:$particles,
    direction:$direction,export_bundle_sha256:$export_sha,import_bundle_sha256:$import_sha,
    source_controller:$source_controller,destination_controller:$destination_controller,
    source_identity:$source_identity,destination_identity:$destination_identity,
    partial_path:$partial,final_path:$final,bytes:$bytes,
    attempt_intent_sha256:$intent,correlation_id:$correlation,
    remote_claim_sha256:$claim,started_at_utc:$started,
    verified_at_utc:$verified}')"
TRANSFER_SHA="$(printf '%s' "$TRANSFER_PAYLOAD" | sha256sum | awk '{print $1}')"
PARTIAL_RECEIPT="$RECEIPT.partial.$$"
jq -Scn --argjson payload "$TRANSFER_PAYLOAD" --arg sha "$TRANSFER_SHA" \
  '{schema:"challenge15.transfer-receipt.v1",payload:$payload,payload_sha256:$sha}' \
  > "$PARTIAL_RECEIPT"
sync -f "$PARTIAL_RECEIPT"
mv -T -- "$PARTIAL_RECEIPT" "$RECEIPT"
sync -f "$RECEIPT_DIR"
jq -er '.payload.final_path' "$RECEIPT"
