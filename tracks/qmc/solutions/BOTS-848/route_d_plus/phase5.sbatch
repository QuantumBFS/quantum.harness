#!/usr/bin/env bash
set -euo pipefail

# Resource directives intentionally come from the active cluster profile and
# the ratified submit command.

: "${ROUTE_D_PLUS_REPO_ROOT:?set the absolute remote repository root}"
: "${ROUTE_D_PLUS_PHASE4_CERTIFICATE:?set the Phase 4 certificate path}"
: "${ROUTE_D_PLUS_RUN_ID:?set a unique Route D+ Phase 5 run id}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
run_dir="${repo_root}/tracks/qmc/results/${ROUTE_D_PLUS_RUN_ID}"

if [[ ! -d "${repo_root}/.git" ]]; then
  echo "ROUTE_D_PLUS_REPO_ROOT is not a Git checkout: ${repo_root}" >&2
  exit 2
fi
if [[ ! -x "${repo_root}/.venv/bin/python" ]]; then
  echo "Route D+ Python environment is unavailable" >&2
  exit 2
fi

mkdir -p "${run_dir}"
cd "${repo_root}/tracks/qmc/solutions/BOTS-848"
"${repo_root}/.venv/bin/python" -m ruff check \
  route_d_plus tests/route_d_plus
"${repo_root}/.venv/bin/python" -m pytest \
  tests/route_d_plus -q
"${repo_root}/.venv/bin/python" -u \
  -m route_d_plus.certify_phase5 \
  --repo-root "${repo_root}" \
  --phase4-certificate "${ROUTE_D_PLUS_PHASE4_CERTIFICATE}" \
  --output "${run_dir}/phase5-certificate.json"
