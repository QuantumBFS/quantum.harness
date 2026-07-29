#!/usr/bin/env bash
set -euo pipefail

: "${CHALLENGE113_ACK_PRODUCTION:?set CHALLENGE113_ACK_PRODUCTION=1}"
test "${CHALLENGE113_ACK_PRODUCTION}" = "1"
: "${CHALLENGE113_EXPECTED_REVISION:?set the deployed canonical git revision}"
: "${CHALLENGE113_ARCHIVE_PATH:?set the immutable deployment archive path}"
: "${CHALLENGE113_ARCHIVE_SHA256:?set the deployed archive SHA256}"
: "${CHALLENGE113_DEPLOYMENT_METADATA:?set external deployment metadata path}"
: "${CHALLENGE113_EVIDENCE_REVISION:?set the measured evidence revision}"
: "${CHALLENGE113_SIF_SHA256:?set expected Apptainer SIF SHA256}"
: "${CHALLENGE113_PYPROJECT_SHA256:?set expected pyproject.toml SHA256}"
: "${CHALLENGE113_UV_LOCK_SHA256:?set expected uv.lock SHA256}"
: "${CHALLENGE113_CLUSTER_PROFILE:?set approved cluster profile}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  test -z "$(git status --porcelain=v1 --untracked-files=all)"
  SOURCE_REVISION="$(git rev-parse HEAD)"
elif [[ -f .source-revision ]]; then
  SOURCE_REVISION="$(<.source-revision)"
else
  echo "cannot establish canonical source revision" >&2
  exit 2
fi
test "${SOURCE_REVISION}" = "${CHALLENGE113_EXPECTED_REVISION}"

export JAX_ENABLE_X64=1
: "${CHALLENGE113_JAX_PLATFORM:?set CHALLENGE113_JAX_PLATFORM explicitly}"
export JAX_PLATFORMS="${CHALLENGE113_JAX_PLATFORM}"
OUTPUT="${CHALLENGE113_PRODUCTION_OUTPUT:-${ROOT}/results/production}"
case "${OUTPUT}" in
  *"/development"|*"/development/"*) echo "production output cannot use a development path" >&2; exit 2 ;;
esac

uv sync --frozen --group dev
uv run python scripts/verify_deployment.py \
  --root "${ROOT}" \
  --archive "${CHALLENGE113_ARCHIVE_PATH}" \
  --deployment-metadata "${CHALLENGE113_DEPLOYMENT_METADATA}" \
  --expected-revision "${CHALLENGE113_EXPECTED_REVISION}" \
  --expected-archive-sha256 "${CHALLENGE113_ARCHIVE_SHA256}" \
  --expected-evidence-revision "${CHALLENGE113_EVIDENCE_REVISION}" \
  --expected-sif-sha256 "${CHALLENGE113_SIF_SHA256}" \
  --expected-pyproject-sha256 "${CHALLENGE113_PYPROJECT_SHA256}" \
  --expected-uv-lock-sha256 "${CHALLENGE113_UV_LOCK_SHA256}" \
  --expected-cluster-profile "${CHALLENGE113_CLUSTER_PROFILE}"
uv run python -c 'import jax; expected = __import__("os").environ["JAX_PLATFORMS"]; actual = jax.devices()[0].platform; assert jax.config.x64_enabled; assert actual == expected, (actual, expected)'
if [[ "${CHALLENGE113_CHECK_ONLY:-0}" == "1" ]]; then
  printf '%s\n' '{"production_gate":"ready"}'
  exit 0
fi
/usr/bin/time -v uv run python -u run.py sweep --kind production --output "${OUTPUT}"
