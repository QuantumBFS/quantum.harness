#!/usr/bin/env bash
set -euo pipefail

die() { printf '%s\n' "$*" >&2; exit 2; }
require_absolute() { [[ "$2" = /* ]] || die "$1 must be absolute"; }
require_under() {
  local resolved root
  resolved="$(realpath -e -- "$1")"
  root="$(realpath -e -- "$2")"
  [[ "$resolved" == "$root" || "$resolved" == "$root/"* ]] ||
    die "path is outside approved root: $1"
}
receipt_field() {
  jq -er --arg field "$2" '.payload[$field]' "$1"
}
resolve_interpreter() {
  local receipt="$1" expected_profile_sha="$2" interpreter root expected actual
  [[ "$(jq -er '.schema' "$receipt")" == "challenge15.deployment-receipt.v1" ]] ||
    die "invalid deployment receipt schema"
  [[ "$(receipt_field "$receipt" profile_sha256)" == "$expected_profile_sha" ]] ||
    die "deployment profile mismatch"
  interpreter="$(receipt_field "$receipt" interpreter)"
  root="$(receipt_field "$receipt" deployment_root)"
  require_absolute interpreter "$interpreter"
  require_under "$interpreter" "$root"
  expected="$(receipt_field "$receipt" interpreter_sha256)"
  actual="$(sha256sum -- "$interpreter" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || die "deployment interpreter SHA256 mismatch"
  printf '%s\n' "$interpreter"
}
validate_profile_root() {
  local profile="$1" expected_sha="$2" results_root="$3" actual approved
  actual="$(jq -er '.payload_sha256' "$profile")"
  [[ "$actual" == "$expected_sha" ]] || die "profile SHA256 mismatch"
  approved="$(jq -er '.payload.approved_results_root' "$profile")"
  [[ "$results_root" == "$approved" ]] || die "RESULTS_ROOT is not profile-bound"
}
resolve_array_task() {
  local interpreter="$1" identity_map="$2" stage="$3" expected_concurrency="$4"
  [[ "${SLURM_ARRAY_TASK_ID:-}" =~ ^[0-9]+$ ]] || die "Slurm array task ID is required"
  local declared
  declared="$(jq -er '.payload.array_concurrency' "$identity_map")"
  [[ "$declared" == "$expected_concurrency" ]] || die "identity-map concurrency mismatch"
  "$interpreter" -m challenge15.cli identity-map-task \
    --identity-map "$identity_map" --task-id "$SLURM_ARRAY_TASK_ID" --stage "$stage"
}
validate_scheduler() {
  [[ "${SLURM_JOB_ID:-}" ]] || die "wrapper requires Slurm"
  [[ "${SLURM_JOB_PARTITION:-}" == "$1" ]] || die "partition mismatch"
  [[ "${SLURM_JOB_ACCOUNT:-}" == "$2" ]] || die "account mismatch"
  [[ "${SLURM_JOB_QOS:-}" == "$3" ]] || die "QOS mismatch"
}
guarded_scratch() {
  local approved="$1" task="${SLURM_ARRAY_TASK_ID:-0}" scratch
  if [[ -n "${SLURM_TMPDIR:-}" && -d "$SLURM_TMPDIR" && -w "$SLURM_TMPDIR" ]]; then
    scratch="$SLURM_TMPDIR/challenge15-$SLURM_JOB_ID-$task"
  else
    scratch="$approved/scratch/job-$SLURM_JOB_ID-task-$task"
  fi
  [[ ! -e "$scratch" && ! -L "$scratch" ]] || die "scratch already exists"
  mkdir -m 700 -p -- "$(dirname -- "$scratch")"
  mkdir -m 700 -- "$scratch"
  require_under "$scratch" "${SLURM_TMPDIR:-$approved}"
  printf '%s\n' "$scratch"
}
