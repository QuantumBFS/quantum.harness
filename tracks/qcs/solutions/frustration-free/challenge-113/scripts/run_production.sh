#!/usr/bin/env bash
set -euo pipefail

: "${CHALLENGE113_ACK_PRODUCTION:?set CHALLENGE113_ACK_PRODUCTION=1}"
test "${CHALLENGE113_ACK_PRODUCTION}" = "1"
: "${CHALLENGE113_EXPECTED_REVISION:?set the deployed canonical git revision}"
: "${CHALLENGE113_ARCHIVE_SHA256:?set the deployed archive SHA256}"
: "${CHALLENGE113_EVIDENCE_REVISION:?set the measured evidence revision}"

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
  --expected-revision "${CHALLENGE113_EXPECTED_REVISION}" \
  --expected-archive-sha256 "${CHALLENGE113_ARCHIVE_SHA256}" \
  --expected-evidence-revision "${CHALLENGE113_EVIDENCE_REVISION}"
uv run python -c 'import jax; expected = __import__("os").environ["JAX_PLATFORMS"]; actual = jax.devices()[0].platform; assert jax.config.x64_enabled; assert actual == expected, (actual, expected)'
/usr/bin/time -v uv run python -u run.py sweep --kind production --output "${OUTPUT}"
