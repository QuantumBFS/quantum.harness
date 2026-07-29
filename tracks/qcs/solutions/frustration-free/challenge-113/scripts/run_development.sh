#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export JAX_ENABLE_X64=1
export JAX_PLATFORMS="${CHALLENGE113_JAX_PLATFORM:-cpu}"
OUTPUT="${CHALLENGE113_DEVELOPMENT_OUTPUT:-${ROOT}/results/development}"
case "${OUTPUT}" in
  *"/production"|*"/production/"*) echo "development output cannot use a production path" >&2; exit 2 ;;
esac

uv sync --frozen --group dev
uv run python -c 'import jax; expected = __import__("os").environ["JAX_PLATFORMS"]; actual = jax.devices()[0].platform; assert jax.config.x64_enabled; assert actual == expected, (actual, expected)'
/usr/bin/time -v uv run python -u run.py sweep --kind development --output "${OUTPUT}"
