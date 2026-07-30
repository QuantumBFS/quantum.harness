#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
INTENT= CLAIM_ROOT= RECEIPT_DIR= SCRIPT= PROFILE= RUNTIME_SET=
SBATCH_ARGS=()
while (($#)); do
  case "$1" in
    --intent) INTENT="$2"; shift 2 ;;
    --claim-root) CLAIM_ROOT="$2"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="$2"; shift 2 ;;
    --script) SCRIPT="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --runtime-set) RUNTIME_SET="$2"; shift 2 ;;
    --sbatch-arg) SBATCH_ARGS+=("$2"); shift 2 ;;
    *) die "unexpected argument: $1" ;;
  esac
done
for value in INTENT CLAIM_ROOT RECEIPT_DIR SCRIPT PROFILE RUNTIME_SET; do
  [[ "${!value:-}" ]] || die "missing --${value,,}"
done
CORRELATION_ID="$(jq -er '.payload.correlation_id' "$INTENT")"
[[ "$(jq -er '.schema' "$INTENT")" == "challenge15.orchestration-attempt-intent.v1" ]] ||
  die "invalid attempt intent"
[[ "$(jq -Sc '.payload' "$INTENT" | sha256sum | awk '{print $1}')" == "$(jq -er '.payload_sha256' "$INTENT")" ]] ||
  die "attempt intent payload SHA256 mismatch"
cmp -s -- <(jq -Sc . "$INTENT") "$INTENT" ||
  die "attempt intent is not canonical JSON"
[[ "$(sha256sum -- "$SCRIPT" | awk '{print $1}')" == "$(jq -er '.payload.script_sha256' "$INTENT")" ]] ||
  die "intent script SHA256 mismatch"
JOB_NAME="c15-${CORRELATION_ID:0:24}"
[[ "$JOB_NAME" == "$(jq -er '.payload.scheduler_job_name' "$INTENT")" ]] ||
  die "intent scheduler job name mismatch"
[[ "$CORRELATION_ID" == "$(jq -er '.payload.scheduler_comment' "$INTENT")" ]] ||
  die "intent scheduler comment mismatch"
mkdir -p -- "$CLAIM_ROOT" "$RECEIPT_DIR"
RECEIPT="$RECEIPT_DIR/$CORRELATION_ID.json"
INTENT_SHA="$(sha256sum -- "$INTENT" | awk '{print $1}')"
PROFILE_SHA="$(jq -er '.payload_sha256' "$PROFILE")"
RUNTIME_SET_SHA="$(jq -er '.payload_sha256' "$RUNTIME_SET")"
[[ "$PROFILE_SHA" == "$(jq -er '.payload.profile_sha256' "$INTENT")" ]] ||
  die "intent profile SHA256 mismatch"
[[ "$RUNTIME_SET_SHA" == "$(jq -er '.payload.runtime_set_sha256' "$INTENT")" ]] ||
  die "intent runtime-set SHA256 mismatch"
[[ "${DEPLOYMENT_RECEIPT:-}" = /* && "${IDENTITY_MAP:-}" = /* ]] ||
  die "submission requires deployment and identity-map paths"
DEPLOYMENT_SHA="$(jq -er '.payload_sha256' "$DEPLOYMENT_RECEIPT")"
[[ "$DEPLOYMENT_SHA" == "$(jq -er '.payload.deployment_receipt_sha256' "$INTENT")" ]] ||
  die "intent deployment receipt SHA256 mismatch"
[[ "$(jq -er '.payload.profile_sha256' "$DEPLOYMENT_RECEIPT")" == "$PROFILE_SHA" ]] ||
  die "deployment/profile mismatch"
INTERPRETER="$(jq -er '.payload.interpreter' "$DEPLOYMENT_RECEIPT")"
INTERPRETER_SHA="$(jq -er '.payload.interpreter_sha256' "$DEPLOYMENT_RECEIPT")"
[[ -f "$INTERPRETER" && ! -L "$INTERPRETER" &&
   "$(sha256sum -- "$INTERPRETER" | awk '{print $1}')" == "$INTERPRETER_SHA" ]] ||
  die "deployment interpreter byte mismatch"
IDENTITY_MAP_SHA="$(jq -er '.payload_sha256' "$IDENTITY_MAP")"
[[ "$(jq -Sc '.payload' "$IDENTITY_MAP" | sha256sum | awk '{print $1}')" == "$IDENTITY_MAP_SHA" ]] ||
  die "identity-map payload SHA256 mismatch"
ARGV_JSON="$(jq -cn --args '$ARGS.positional' "${SBATCH_ARGS[@]}" "$SCRIPT")"
ARGV_SHA="$(printf '%s' "$ARGV_JSON" | sha256sum | awk '{print $1}')"
[[ "$ARGV_SHA" == "$(jq -er '.payload.canonical_argv_sha256' "$INTENT")" ]] ||
  die "actual sbatch argv does not match attempt intent"
RECOMPUTED_CORRELATION="$(jq -Sc '.payload | {
  state_key_sha256,transition_identity_sha256,attempt,action_kind,
  source_controller,destination_controller,script_sha256,
  canonical_argv_sha256,input_sha256s}' "$INTENT" | sha256sum | awk '{print $1}')"
[[ "$RECOMPUTED_CORRELATION" == "$CORRELATION_ID" ]] ||
  die "attempt intent correlation ID mismatch"
ARRAY_SPEC="none"
for argument in "${SBATCH_ARGS[@]}"; do
  if [[ "$argument" == --array=* ]]; then
    [[ "$ARRAY_SPEC" == "none" ]] || die "duplicate sbatch array argument"
    ARRAY_SPEC="${argument#--array=}"
  fi
done
TASK_COUNT="$(jq -er '.payload.task_count' "$IDENTITY_MAP")"
CONCURRENCY="$(jq -er '.payload.array_concurrency' "$IDENTITY_MAP")"
EXPECTED_ARRAY="0-$((TASK_COUNT - 1))%$CONCURRENCY"
[[ "$ARRAY_SPEC" == "$EXPECTED_ARRAY" ]] ||
  die "sbatch array does not exactly match identity map"
jq -e --argjson inputs "$(jq -c '.payload.input_sha256s' "$INTENT")" '
  all(.payload.tasks[].input_sha256; . as $sha | $inputs | index($sha) != null)' "$IDENTITY_MAP" >/dev/null ||
  die "identity-map inputs are not attempt-intent-bound"
validate_receipt() {
  [[ "$(jq -er '.schema' "$RECEIPT")" == "challenge15.submission-receipt.v1" ]] ||
    die "existing submission receipt schema mismatch"
  [[ "$(jq -er '.payload.correlation_id' "$RECEIPT")" == "$CORRELATION_ID" ]] ||
    die "existing submission receipt correlation mismatch"
  [[ "$(jq -er '.payload.remote_claim_sha256' "$RECEIPT")" == "$INTENT_SHA" ]] ||
    die "existing submission receipt intent mismatch"
  local computed
  computed="$(jq -Sc '.payload' "$RECEIPT" | sha256sum | awk '{print $1}')"
  [[ "$computed" == "$(jq -er '.payload_sha256' "$RECEIPT")" ]] ||
    die "existing submission receipt payload hash mismatch"
}
# submission-receipt is authoritative and checked before scheduler state.
if [[ -s "$RECEIPT" ]]; then
  validate_receipt
  jq -er '.payload.scheduler_job_id' "$RECEIPT"
  exit 0
fi
CLAIM="$CLAIM_ROOT/$CORRELATION_ID"
CLAIM_IDENTITY="$CLAIM/identity.json"
CLAIM_PAYLOAD="$(jq -Scn --arg intent "$INTENT_SHA" --arg correlation "$CORRELATION_ID" \
  --arg profile "$PROFILE_SHA" --arg runtime "$RUNTIME_SET_SHA" \
  '{intent_sha256:$intent,correlation_id:$correlation,profile_sha256:$profile,runtime_set_sha256:$runtime}')"
if mkdir -- "$CLAIM" 2>/dev/null; then
  printf '%s\n' "$CLAIM_PAYLOAD" > "$CLAIM_IDENTITY"
  sync -f "$CLAIM_IDENTITY"; sync -f "$CLAIM_ROOT"
else
  [[ -s "$RECEIPT" ]] && validate_receipt && jq -er '.payload.scheduler_job_id' "$RECEIPT" && exit 0
  [[ -s "$CLAIM_IDENTITY" && "$(jq -Sc . "$CLAIM_IDENTITY")" == "$CLAIM_PAYLOAD" ]] ||
    die "submission claim identity mismatch"
fi
SQUEUE="$(squeue --noheader --name "$JOB_NAME" --format '%i|%j|%k' || true)"
SACCT="$(sacct --noheader --name "$JOB_NAME" --parsable2 --format JobIDRaw,JobName,Comment,State || true)"
MISMATCH="$(printf '%s\n%s\n' "$SQUEUE" "$SACCT" |
  awk -F'|' -v n="$JOB_NAME" -v c="$CORRELATION_ID" '$2==n && $3!=c {print $1; exit}')"
[[ -z "$MISMATCH" ]] ||
  die "scheduler evidence hash/comment mismatch for submission claim: $MISMATCH"
mapfile -t MATCHES < <(printf '%s\n%s\n' "$SQUEUE" "$SACCT" |
  awk -F'|' -v n="$JOB_NAME" -v c="$CORRELATION_ID" '$2==n && $3==c {split($1,a,"."); print a[1]}' |
  sort -u)
if ((${#MATCHES[@]} > 1)); then
  die "ambiguous scheduler evidence for submission claim"
fi
if ((${#MATCHES[@]} == 1)); then
  JOB_ID="${MATCHES[0]}"
else
  JOB_ID="$(sbatch --parsable --job-name "$JOB_NAME" --comment "$CORRELATION_ID" "${SBATCH_ARGS[@]}" "$SCRIPT")"
fi
[[ "$JOB_ID" =~ ^[0-9]+([_;].*)?$ ]] || die "sbatch returned an invalid job id"
SUBMISSION_PAYLOAD="$(jq -Scn \
  --arg stage "$(jq -er '.payload.stage' "$IDENTITY_MAP")" \
  --arg identity "$IDENTITY_MAP_SHA" --arg profile "$PROFILE_SHA" \
  --arg interpreter "$INTERPRETER_SHA" --arg controller "$(jq -er '.payload.destination_controller' "$INTENT")" \
  --arg job "$JOB_ID" --arg array "$ARRAY_SPEC" --arg correlation "$CORRELATION_ID" \
  --arg name "$JOB_NAME" --arg comment "$CORRELATION_ID" \
  --arg script "$(jq -er '.payload.script_sha256' "$INTENT")" \
  --arg claim "$INTENT_SHA" \
  --arg policy "$(jq -er '.payload.policy_sha256' "$INTENT")" \
  --arg source "$(jq -er '.payload.source_manifest_sha256' "$INTENT")" \
  --argjson runtimes "$(jq -c '.payload.roles | with_entries(.value = {(.value.controller): .value.allowed_runtime_sha256})' "$RUNTIME_SET")" \
  --arg base "$(jq -er '.payload.base_configuration_sha256' "$INTENT")" \
  --argjson particles "$(jq -er '.payload.particles' "$INTENT")" \
  --argjson inputs "$(jq -c '.payload.input_sha256s' "$INTENT")" \
  --arg submitted "$(jq -er '.payload.created_at_utc' "$INTENT")" \
  '{policy_sha256:$policy,source_manifest_sha256:$source,
    runtime_attestations:$runtimes,base_configuration_sha256:$base,particles:$particles,
    stage:$stage,identity_map_sha256:$identity,profile_sha256:$profile,
    interpreter_sha256:$interpreter,submitted_at_utc:$submitted,controller:$controller,
    scheduler_job_id:$job,array_spec:$array,dependency_mode:"none",
    correlation_id:$correlation,scheduler_job_name:$name,scheduler_comment:$comment,
    script_sha256:$script,input_sha256s:$inputs,remote_claim_sha256:$claim}')"
SUBMISSION_SHA="$(printf '%s' "$SUBMISSION_PAYLOAD" | sha256sum | awk '{print $1}')"
PARTIAL="$RECEIPT.partial.$$"
jq -Scn --argjson payload "$SUBMISSION_PAYLOAD" --arg sha "$SUBMISSION_SHA" \
  '{schema:"challenge15.submission-receipt.v1",payload:$payload,payload_sha256:$sha}' \
  > "$PARTIAL"
sync -f "$PARTIAL"
mv -T -- "$PARTIAL" "$RECEIPT"
sync -f "$RECEIPT_DIR"
printf '%s\n' "$JOB_ID"
