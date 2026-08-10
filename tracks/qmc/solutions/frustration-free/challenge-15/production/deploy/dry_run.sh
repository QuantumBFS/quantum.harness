#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
PROFILE= BUNDLE_ROOT= DESTINATION= INTERPRETER= OUTPUT=
SBATCH_SCRIPTS=()
while (($#)); do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --bundle-root|--bundle) BUNDLE_ROOT="$2"; shift 2 ;;
    --destination) DESTINATION="$2"; shift 2 ;;
    --interpreter) INTERPRETER="$2"; shift 2 ;;
    --sbatch-script) SBATCH_SCRIPTS+=("$2"); shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    *) die "unexpected argument: $1" ;;
  esac
done
for value in PROFILE BUNDLE_ROOT DESTINATION INTERPRETER OUTPUT; do
  [[ "${!value:-}" ]] || die "missing dry-run argument: $value"
done
[[ "$INTERPRETER" = /* && -x "$INTERPRETER" ]] || die "interpreter must be absolute and executable"
((${#SBATCH_SCRIPTS[@]})) || die "at least one --sbatch-script is required"
[[ ! -e "$OUTPUT" ]] || die "dry-run receipt is create-only"
[[ -d "$BUNDLE_ROOT" && ! -L "$BUNDLE_ROOT" ]] || die "bundle root must be a regular directory"
PROFILE_SHA="$(jq -er '.payload_sha256' "$PROFILE")"
APPROVED_ROOT="$(jq -er '.payload.approved_project_root' "$PROFILE")"
[[ "$DESTINATION" == "$APPROVED_ROOT" || "$DESTINATION" == "$APPROVED_ROOT/"* ]] ||
  die "dry-run destination is outside profile-approved project root"
BUNDLE_SHA="$(
  cd "$BUNDLE_ROOT"
  shopt -s globstar nullglob
  files=()
  for member in **/*; do [[ -f "$member" && ! -L "$member" ]] && files+=("$member"); done
  ((${#files[@]})) || die "bundle root is empty"
  printf '%s\0' "${files[@]}" | sort -z | xargs -0 sha256sum -- |
    sha256sum | awk '{print $1}'
)"
INTERPRETER_SHA="$(sha256sum -- "$INTERPRETER" | awk '{print $1}')"
SCHEDULER_TEST="$(jq -cn '[]')"
for script in "${SBATCH_SCRIPTS[@]}"; do
  [[ "$script" = /* && -f "$script" && ! -L "$script" ]] ||
    die "sbatch test script must be an absolute regular file"
  OUTPUT_TEXT="$(sbatch --test-only "$script" 2>&1)" ||
    die "sbatch --test-only rejected $script: $OUTPUT_TEXT"
  SCRIPT_SHA="$(sha256sum -- "$script" | awk '{print $1}')"
  SCHEDULER_TEST="$(jq -Sc --arg path "$script" --arg sha "$SCRIPT_SHA" \
    --arg output "$OUTPUT_TEXT" '. + [{argv:["sbatch","--test-only",$path],script_sha256:$sha,output:$output}]' \
    <<<"$SCHEDULER_TEST")"
done
PAYLOAD="$(jq -Scn --arg p "$PROFILE_SHA" --arg b "$BUNDLE_SHA" --arg d "$DESTINATION" \
  --arg i "$INTERPRETER" --arg ih "$INTERPRETER_SHA" --argjson scheduler "$SCHEDULER_TEST" \
  '{profile_sha256:$p,bundle_sha256:$b,destination:$d,interpreter:$i,interpreter_sha256:$ih,scheduler_test:$scheduler,validated_at_utc:(now|todateiso8601)}')"
PAYLOAD_SHA="$(printf '%s' "$PAYLOAD" | sha256sum | awk '{print $1}')"
jq -Scn --argjson payload "$PAYLOAD" --arg sha "$PAYLOAD_SHA" \
  '{schema:"challenge15.dry-run-receipt.v1",payload:$payload,payload_sha256:$sha}' > "$OUTPUT"
sync -f "$OUTPUT"
