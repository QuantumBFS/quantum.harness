#!/usr/bin/env bash
set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the absolute remote repository root}"
: "${ROUTE_D_PLUS_PHASE5_CERTIFICATE:?set the Phase 5 certificate path}"
: "${ROUTE_D_PLUS_PHASE6A_CERTIFICATE:?set the Phase 6A certificate path}"
: "${ROUTE_D_PLUS_RUN_ID:?set a unique Route D+ Phase 6 run id}"

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

runtime_compat="/work/home/jiabohan5/.cache/route-d-plus/runtime-libs"
runtime_library="${runtime_compat}/libstdc++.so.6.0.29"
runtime_library_sha256="4f045231ff3a95c2fbfde450575f0ef45d23e95be15193c8729b521fc363ece4"
if [[ ! -f "${runtime_library}" ]]; then
  echo "Pinned Route D+ compatibility runtime is unavailable" >&2
  exit 2
fi
actual_runtime_sha256="$(sha256sum "${runtime_library}" | cut -d ' ' -f 1)"
if [[ "${actual_runtime_sha256}" != "${runtime_library_sha256}" ]]; then
  echo "Pinned Route D+ compatibility runtime hash mismatch" >&2
  exit 2
fi

nvidia_root="${repo_root}/.venv/lib/python3.11/site-packages/nvidia"
cuda_library_path="${runtime_compat}"
for component in \
  cuda_cupti cufft cudnn cusolver nvjitlink nccl cuda_runtime cublas cusparse
do
  component_library="${nvidia_root}/${component}/lib"
  if [[ ! -d "${component_library}" ]]; then
    echo "CUDA wheel library directory is unavailable: ${component_library}" >&2
    exit 2
  fi
  cuda_library_path="${cuda_library_path}:${component_library}"
done
export LD_LIBRARY_PATH="${cuda_library_path}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export JAX_ENABLE_X64=true
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

mkdir -p "${run_dir}"
cd "${repo_root}/tracks/qmc/solutions/BOTS-848"
"${repo_root}/.venv/bin/python" -m ruff check \
  route_d_plus tests/route_d_plus
"${repo_root}/.venv/bin/python" -m pytest \
  tests/route_d_plus/test_coordinate.py \
  tests/route_d_plus/test_lll.py \
  tests/route_d_plus/test_mother.py \
  tests/route_d_plus/test_scalar.py \
  tests/route_d_plus/test_tensor.py \
  tests/route_d_plus/test_train_dplus0.py \
  tests/route_d_plus/test_vmc.py \
  tests/route_d_plus/test_phase6_contract.py \
  tests/route_d_plus/test_phase6a_contract.py \
  tests/route_d_plus/test_symmetry_contract.py \
  -q
"${repo_root}/.venv/bin/python" -u \
  -m route_d_plus.certify_phase6 \
  --repo-root "${repo_root}" \
  --phase5-certificate "${ROUTE_D_PLUS_PHASE5_CERTIFICATE}" \
  --phase6a-certificate "${ROUTE_D_PLUS_PHASE6A_CERTIFICATE}" \
  --output "${run_dir}/phase6-certificate.json"
