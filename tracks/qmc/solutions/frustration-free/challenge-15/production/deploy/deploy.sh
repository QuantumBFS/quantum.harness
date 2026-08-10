#!/usr/bin/env bash
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
BUNDLE_ROOT= BUNDLE_SHA256= WHEELHOUSE= REQUIREMENTS= DESTINATION_ROOT= DRY_RUN_RECEIPT= OUTPUT_DIR= PROFILE=
while (($#)); do
  case "$1" in
    --bundle-root|--bundle) BUNDLE_ROOT="$2"; shift 2 ;;
    --bundle-sha256) BUNDLE_SHA256="$2"; shift 2 ;;
    --wheelhouse) WHEELHOUSE="$2"; shift 2 ;;
    --requirements) REQUIREMENTS="$2"; shift 2 ;;
    --destination-root) DESTINATION_ROOT="$2"; shift 2 ;;
    --dry-run-receipt) DRY_RUN_RECEIPT="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    *) die "unexpected argument: $1" ;;
  esac
done
for value in BUNDLE_ROOT BUNDLE_SHA256 WHEELHOUSE REQUIREMENTS DESTINATION_ROOT DRY_RUN_RECEIPT OUTPUT_DIR PROFILE; do
  [[ "${!value:-}" ]] || die "missing deployment argument: $value"
done
[[ -d "$BUNDLE_ROOT" && ! -L "$BUNDLE_ROOT" ]] || die "bundle root must be a regular directory"
COMPUTED_BUNDLE_SHA="$(
  cd "$BUNDLE_ROOT"; shopt -s globstar nullglob; files=()
  for member in **/*; do [[ -f "$member" && ! -L "$member" ]] && files+=("$member"); done
  printf '%s\0' "${files[@]}" | sort -z | xargs -0 sha256sum -- |
    sha256sum | awk '{print $1}'
)"
[[ "$COMPUTED_BUNDLE_SHA" == "$BUNDLE_SHA256" ]] ||
  die "bundle SHA256 mismatch"
(cd -- "$BUNDLE_ROOT" && sha256sum -c -- SHA256SUMS)
PROFILE_SHA="$(jq -er '.payload_sha256' "$PROFILE")"
[[ "$PROFILE_SHA" == "$(jq -er '.payload.profile_sha256' "$DRY_RUN_RECEIPT")" ]] ||
  die "dry-run profile mismatch"
APPROVED_ROOT="$(jq -er '.payload.approved_project_root' "$PROFILE")"
[[ "$DESTINATION_ROOT" == "$APPROVED_ROOT" ]] ||
  die "deployment root is not profile-bound"
[[ "$DESTINATION_ROOT" == "$(jq -er '.payload.destination' "$DRY_RUN_RECEIPT")" ]] ||
  die "dry-run destination mismatch"
[[ "$BUNDLE_SHA256" == "$(jq -er '.payload.bundle_sha256' "$DRY_RUN_RECEIPT")" ]] ||
  die "dry-run bundle mismatch"
jq -e '.payload.scheduler_test | length > 0 and
  all(.[]; .argv[0:2] == ["sbatch","--test-only"] and
    (.script_sha256 | test("^[0-9a-f]{64}$")))' "$DRY_RUN_RECEIPT" >/dev/null ||
  die "dry-run scheduler test evidence mismatch"
DRY_INTERPRETER="$(jq -er '.payload.interpreter' "$DRY_RUN_RECEIPT")"
[[ -x "$DRY_INTERPRETER" &&
   "$(sha256sum -- "$DRY_INTERPRETER" | awk '{print $1}')" == "$(jq -er '.payload.interpreter_sha256' "$DRY_RUN_RECEIPT")" ]] ||
  die "dry-run interpreter tuple is stale"
FINAL="$DESTINATION_ROOT/$BUNDLE_SHA256"
RECEIPT="$OUTPUT_DIR/$BUNDLE_SHA256.json"
validate_existing() {
  [[ -d "$FINAL" && ! -L "$FINAL" && -x "$FINAL/venv/bin/python" ]] ||
    die "existing deployment is incomplete"
  [[ "$(jq -er '.payload.bundle_sha256' "$RECEIPT")" == "$BUNDLE_SHA256" &&
     "$(jq -er '.payload.profile_sha256' "$RECEIPT")" == "$PROFILE_SHA" &&
     "$(jq -er '.payload.deployment_root' "$RECEIPT")" == "$FINAL" ]] ||
    die "existing deployment receipt mismatch"
  [[ -s "$FINAL/.deployment-sha256s" ]] ||
    die "existing deployment byte manifest is missing"
  (cd "$FINAL" && sha256sum -c -- .deployment-sha256s)
  [[ "$(sha256sum -- "$FINAL/venv/bin/python" | awk '{print $1}')" ==
     "$(jq -er '.payload.interpreter_sha256' "$RECEIPT")" ]] ||
    die "existing deployment interpreter changed"
  [[ "$(sha256sum -- "$FINAL"/.built-wheel/challenge15_nqs-*.whl | awk 'NR==1 {print $1}')" ==
     "$(jq -er '.payload.installed_wheel_sha256' "$RECEIPT")" ]] ||
    die "existing deployed wheel changed"
}
if [[ -s "$RECEIPT" ]]; then validate_existing; printf '%s\n' "$RECEIPT"; exit 0; fi
PARTIAL="$DESTINATION_ROOT/.partial.$BUNDLE_SHA256.$(cat /proc/sys/kernel/random/uuid)"
mkdir -m 700 -p -- "$DESTINATION_ROOT" "$OUTPUT_DIR"
if [[ -d "$FINAL" && ! -L "$FINAL" ]]; then
  INTERPRETER="$FINAL/venv/bin/python"
  [[ -x "$INTERPRETER" ]] || die "promoted deployment is incomplete"
  INTERPRETER_SHA="$(sha256sum -- "$INTERPRETER" | awk '{print $1}')"
  INSTALLED_WHEEL_SHA="$(sha256sum -- "$FINAL"/.built-wheel/challenge15_nqs-*.whl | awk 'NR==1 {print $1}')"
  [[ -s "$FINAL/.deployment-sha256s" ]] ||
    die "promoted deployment byte manifest is missing"
  (cd "$FINAL" && sha256sum -c -- .deployment-sha256s)
else
mkdir -m 700 -- "$PARTIAL"
trap 'rm -rf -- "$PARTIAL"' EXIT
tar -xf "$BUNDLE_ROOT/source.tar" -C "$PARTIAL"
PYTHON312="$(command -v python3.12 || true)"
[[ "$PYTHON312" = /* ]] || die "absolute CPython 3.12 interpreter is unavailable"
"$PYTHON312" -m venv "$PARTIAL/venv"
INTERPRETER="$PARTIAL/venv/bin/python"
"$INTERPRETER" -m pip install --no-index --require-hashes --only-binary=:all: \
  --find-links "$WHEELHOUSE" -r "$REQUIREMENTS"
mkdir -- "$PARTIAL/.built-wheel"
"$INTERPRETER" -m pip wheel --no-index --no-deps --no-build-isolation \
  --wheel-dir "$PARTIAL/.built-wheel" "$PARTIAL"
PACKAGE_WHEELS=("$PARTIAL"/.built-wheel/challenge15_nqs-*.whl)
[[ "${#PACKAGE_WHEELS[@]}" == 1 && -f "${PACKAGE_WHEELS[0]}" ]] ||
  die "deployment did not build exactly one project wheel"
"$INTERPRETER" -m pip install --no-index --no-deps "${PACKAGE_WHEELS[0]}"
INSTALLED_WHEEL_SHA="$(sha256sum -- "${PACKAGE_WHEELS[0]}" | awk '{print $1}')"
INTERPRETER_SHA="$(sha256sum -- "$INTERPRETER" | awk '{print $1}')"
(cd "$PARTIAL"; shopt -s globstar nullglob; files=()
 for member in **/*; do
   [[ -f "$member" && ! -L "$member" && "$member" != .deployment-sha256s ]] &&
     files+=("$member")
 done
 printf '%s\0' "${files[@]}" | sort -z | xargs -0 sha256sum -- > .deployment-sha256s
 sync -f .deployment-sha256s)
mv -T -- "$PARTIAL" "$FINAL"
sync -f "$DESTINATION_ROOT"
trap - EXIT
fi
[[ ! -e "$RECEIPT" ]] || die "deployment receipt exists"
PAYLOAD="$(jq -Scn --arg dry "$(jq -er '.payload_sha256' "$DRY_RUN_RECEIPT")" \
  --arg profile "$PROFILE_SHA" --arg bundle "$BUNDLE_SHA256" --arg root "$FINAL" \
  --arg interpreter "$FINAL/venv/bin/python" --arg ih "$INTERPRETER_SHA" \
  --arg wheel "$INSTALLED_WHEEL_SHA" \
  '{dry_run_receipt_sha256:$dry,profile_sha256:$profile,bundle_sha256:$bundle,deployment_root:$root,interpreter:$interpreter,interpreter_sha256:$ih,installed_wheel_sha256:$wheel,deployed_at_utc:(now|todateiso8601)}')"
PAYLOAD_SHA="$(printf '%s' "$PAYLOAD" | sha256sum | awk '{print $1}')"
jq -Scn --argjson payload "$PAYLOAD" --arg sha "$PAYLOAD_SHA" \
  '{schema:"challenge15.deployment-receipt.v1",payload:$payload,payload_sha256:$sha}' > "$RECEIPT"
sync -f "$RECEIPT"
sync -f "$OUTPUT_DIR"
printf '%s\n' "$RECEIPT"
