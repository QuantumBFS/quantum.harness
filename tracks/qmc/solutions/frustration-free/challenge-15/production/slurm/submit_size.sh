#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
declare -A A=()
CREATE_ONLY=false
while (($#)); do
  case "$1" in
    --create-only) CREATE_ONLY=true; shift ;;
    --particles|--expected-ranks|--expected-seeds|\
    --prerequisite-terminal-selection|--prerequisite-terminal-selection-sha256|\
    --cpu-profile|--gpu-profile|--runtime-attestations|\
    --runtime-attestations-sha256|--cpu-deployment-receipt|\
    --gpu-deployment-receipt|--source-manifest|--source-manifest-sha256|\
    --policy|--policy-sha256|--cpu-results-root|--gpu-results-root|\
    --transfer-work-root)
      [[ "$#" -ge 2 ]] || die "missing value for $1"
      A["${1#--}"]="$2"
      shift 2
      ;;
    *) die "unexpected argument: $1" ;;
  esac
done
$CREATE_ONLY || die "--create-only is required"
required=(
  particles expected-ranks expected-seeds cpu-profile gpu-profile
  runtime-attestations runtime-attestations-sha256 cpu-deployment-receipt
  gpu-deployment-receipt source-manifest source-manifest-sha256 policy
  policy-sha256 cpu-results-root gpu-results-root transfer-work-root
)
for key in "${required[@]}"; do [[ "${A[$key]:-}" ]] || die "missing --$key"; done
[[ "${A[expected-seeds]}" == "0,1,2,3,4" ]] || die "expected seeds must be 0,1,2,3,4"
case "${A[particles]}" in
  6)
    [[ -z "${A[prerequisite-terminal-selection]:-}${A[prerequisite-terminal-selection-sha256]:-}" ]] ||
      die "N=6 must omit prerequisite flags"
    ;;
  7|8)
    [[ "${A[prerequisite-terminal-selection]:-}" && "${A[prerequisite-terminal-selection-sha256]:-}" ]] ||
      die "N=7/N=8 require both prerequisite flags"
    ;;
  *) die "particles must be 6, 7, or 8" ;;
esac
sha_check() {
  [[ "$(jq -er '.payload_sha256' "$1")" == "$2" ]] ||
    die "stale digest for $1"
}
sha_check "${A[runtime-attestations]}" "${A[runtime-attestations-sha256]}"
sha_check "${A[source-manifest]}" "${A[source-manifest-sha256]}"
sha_check "${A[policy]}" "${A[policy-sha256]}"
if [[ "${A[particles]}" != 6 ]]; then
  sha_check "${A[prerequisite-terminal-selection]}" "${A[prerequisite-terminal-selection-sha256]}"
fi
INTERPRETER="$(jq -er '.payload.interpreter' "${A[cpu-deployment-receipt]}")"
[[ "$INTERPRETER" = /* && -x "$INTERPRETER" ]] || die "CPU deployment interpreter is invalid"
if [[ "${A[particles]}" != 6 ]]; then
  "$INTERPRETER" -m challenge15.cli validate-prerequisite \
    --particles "$((A[particles]-1))" \
    --terminal-selection "${A[prerequisite-terminal-selection]}" \
    --terminal-selection-sha256 "${A[prerequisite-terminal-selection-sha256]}" \
    --policy "${A[policy]}" --source-manifest "${A[source-manifest]}" \
    --runtime-attestations "${A[runtime-attestations]}"
fi
[[ ! -e "${A[transfer-work-root]}" && ! -L "${A[transfer-work-root]}" ]] ||
  die "transfer work root already exists"
mkdir -m 700 -p -- "${A[cpu-results-root]}" "${A[gpu-results-root]}"
mkdir -m 700 -- "${A[transfer-work-root]}"
printf '%s\n' "validated N=${A[particles]} submission inputs; state machine must invoke submit-once" >&2
