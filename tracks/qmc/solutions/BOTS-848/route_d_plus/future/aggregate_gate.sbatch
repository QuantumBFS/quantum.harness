#!/usr/bin/env bash
#SBATCH --job-name=rdp-future-gate
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --time=00:20:00

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the remote repository root}"
: "${ROUTE_D_PLUS_DISPATCH:?set the immutable stage dispatch}"
: "${ROUTE_D_PLUS_STAGE_GATE:?set the stage decision gate}"
: "${ROUTE_D_PLUS_AGGREGATE_OUTPUT:?set the aggregate output path}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
solution_root="${repo_root}/tracks/qmc/solutions/BOTS-848"
python="${repo_root}/.venv/bin/python"

cd "${solution_root}"
"${python}" -m route_d_plus.future.verify aggregate \
  --dispatch "${ROUTE_D_PLUS_DISPATCH}" \
  --stage-gate "${ROUTE_D_PLUS_STAGE_GATE}" \
  --repo-root "${repo_root}" \
  --output "${ROUTE_D_PLUS_AGGREGATE_OUTPUT}"
