#!/usr/bin/env bash
set -euo pipefail

# Resource directives intentionally come from the active cluster profile and
# the ratified submit command. This file must not invent a partition, GPU type,
# CPU count, memory request, or wall time.

: "${ROUTE_D_PLUS_REPO_ROOT:?set the absolute remote repository root}"
: "${JAX_PROFILE:?set JAX_PROFILE to the CUDA profile selected for the cluster}"
: "${ROUTE_D_PLUS_RUN_ID:?set a unique Route D+ Phase 1 run id}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
script_dir="${repo_root}/tracks/qmc/solutions/BOTS-848/route_d_plus/environment"

if [[ ! -d "${repo_root}/.git" ]]; then
  echo "ROUTE_D_PLUS_REPO_ROOT is not a Git checkout: ${repo_root}" >&2
  exit 2
fi

export ROUTE_D_PLUS_RUN_DIR="${repo_root}/tracks/qmc/results/${ROUTE_D_PLUS_RUN_ID}"

bash "${script_dir}/bootstrap.sh"
