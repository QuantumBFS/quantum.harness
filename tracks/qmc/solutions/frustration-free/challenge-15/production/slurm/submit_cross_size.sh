#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
declare -A A=()
CREATE_ONLY=false
while (($#)); do
  case "$1" in
    --create-only) CREATE_ONLY=true; shift ;;
    --*) [[ "$#" -ge 2 ]] || die "missing value for $1"; A["${1#--}"]="$2"; shift 2 ;;
    *) die "unexpected argument: $1" ;;
  esac
done
$CREATE_ONLY || die "--create-only is required"
required=(
  n6-terminal-selection n7-terminal-selection n8-terminal-selection
  runtime-attestation-set-n6 runtime-attestation-set-n7 runtime-attestation-set-n8
  n8-provisional-finalization n8-reduction n8-import-receipt n8-transfer-receipt
  policy source-manifest deployment-receipt output-dir receipt-dir
)
for key in "${required[@]}"; do
  [[ "${A[$key]:-}" ]] || die "missing --$key"
  [[ -s "${A[$key]}" || "$key" =~ ^(output-dir|receipt-dir)$ ]] ||
    die "missing input file for --$key"
done
[[ ! -e "${A[output-dir]}" && ! -L "${A[output-dir]}" ]] || die "output exists"
mkdir -m 700 -- "${A[output-dir]}"
printf '%s\n' "cross-size inputs validated; invoke reduce-cross-size through submit-once" >&2
