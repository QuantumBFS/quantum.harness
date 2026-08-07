#!/usr/bin/env bash
#SBATCH --job-name=rdp-opt-repair
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:1
#SBATCH --mem=48G
#SBATCH --time=04:00:00

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the clean remediation checkout}"
: "${ROUTE_D_PLUS_RUN_ROOT:?set the isolated remediation run root}"
: "${ROUTE_D_PLUS_PHASE6_RUN:?set the immutable Phase 6 source run}"
: "${ROUTE_D_PLUS_PHASE7_GATE:?set the Phase 7 stage gate}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
solution_root="${repo_root}/tracks/qmc/solutions/BOTS-848"
python="${repo_root}/.venv/bin/python"
protocol="${solution_root}/route_d_plus/optimization-remediation-protocol.json"

mkdir -p "${ROUTE_D_PLUS_RUN_ROOT}"
cd "${solution_root}"

nvidia-smi \
  --query-gpu=index,name,uuid,driver_version \
  --format=csv,noheader
test -n "${CUDA_VISIBLE_DEVICES:-}"

export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4

"${python}" -m route_d_plus.remediate_dplus0 \
  --repo-root "${repo_root}" \
  --phase7-stage-gate "${ROUTE_D_PLUS_PHASE7_GATE}" \
  --protocol "${protocol}" \
  --architecture "${ROUTE_D_PLUS_PHASE6_RUN}/architecture.json" \
  --checkpoint "${ROUTE_D_PLUS_PHASE6_RUN}/seeds/seed-848/checkpoint.json" \
  --checkpoint "${ROUTE_D_PLUS_PHASE6_RUN}/seeds/seed-1848/checkpoint.json" \
  --checkpoint "${ROUTE_D_PLUS_PHASE6_RUN}/seeds/seed-2848/checkpoint.json" \
  --output-dir "${ROUTE_D_PLUS_RUN_ROOT}/seeds" \
  --output "${ROUTE_D_PLUS_RUN_ROOT}/optimization-remediation.json"

sha256sum \
  "${ROUTE_D_PLUS_RUN_ROOT}/optimization-remediation.json" \
  "${ROUTE_D_PLUS_RUN_ROOT}"/seeds/*/checkpoint.json \
  "${ROUTE_D_PLUS_RUN_ROOT}"/seeds/*/seed-certificate.json
