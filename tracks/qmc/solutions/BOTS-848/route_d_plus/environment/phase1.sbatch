#!/usr/bin/env bash
set -euo pipefail

# Resource directives intentionally come from the active cluster profile and
# the ratified submit command. This file must not invent a partition, GPU type,
# CPU count, memory request, or wall time.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}" && git rev-parse --show-toplevel)"

: "${JAX_PROFILE:?set JAX_PROFILE to the CUDA profile selected for the cluster}"
: "${ROUTE_D_PLUS_RUN_ID:?set a unique Route D+ Phase 1 run id}"

export ROUTE_D_PLUS_RUN_DIR="${repo_root}/tracks/qmc/results/${ROUTE_D_PLUS_RUN_ID}"

bash "${script_dir}/bootstrap.sh"
