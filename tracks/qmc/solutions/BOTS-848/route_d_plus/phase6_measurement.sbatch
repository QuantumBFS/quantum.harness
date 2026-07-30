#!/usr/bin/env bash
#SBATCH --job-name=rdp6-measure
#SBATCH --partition=xhhgnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --gres=gpu:1
#SBATCH --time=04:00:00

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the absolute remote repository root}"
: "${ROUTE_D_PLUS_PHASE6_ATTEMPT:?set the immutable Phase 6 attempt path}"
: "${ROUTE_D_PLUS_MEASUREMENT_RUN_ID:?set a unique measurement run id}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
run_dir="${repo_root}/tracks/qmc/results/${ROUTE_D_PLUS_MEASUREMENT_RUN_ID}"
test -d "${repo_root}/.git"
test -x "${repo_root}/.venv/bin/python"
test -f "${ROUTE_D_PLUS_PHASE6_ATTEMPT}"
test -z "$(cd "${repo_root}" && git status --porcelain)"

runtime_compat="/work/home/jiabohan5/.cache/route-d-plus/runtime-libs"
runtime_library="${runtime_compat}/libstdc++.so.6.0.29"
runtime_library_sha256="4f045231ff3a95c2fbfde450575f0ef45d23e95be15193c8729b521fc363ece4"
test -f "${runtime_library}"
actual_runtime_sha256="$(sha256sum "${runtime_library}" | cut -d ' ' -f 1)"
test "${actual_runtime_sha256}" = "${runtime_library_sha256}"

nvidia_root="${repo_root}/.venv/lib/python3.11/site-packages/nvidia"
cuda_library_path="${runtime_compat}"
for component in \
  cuda_cupti cufft cudnn cusolver nvjitlink nccl cuda_runtime cublas cusparse
do
  component_library="${nvidia_root}/${component}/lib"
  test -d "${component_library}"
  cuda_library_path="${cuda_library_path}:${component_library}"
done
export LD_LIBRARY_PATH="${cuda_library_path}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export JAX_ENABLE_X64=true
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

mkdir -p "${run_dir}"
cd "${repo_root}/tracks/qmc/solutions/BOTS-848"
"${repo_root}/.venv/bin/python" -m ruff check \
  route_d_plus/extend_phase6_measurement.py \
  tests/route_d_plus/test_phase6_measurement_contract.py
"${repo_root}/.venv/bin/python" -m pytest \
  tests/route_d_plus/test_phase6_measurement_contract.py \
  tests/route_d_plus/test_phase6_contract.py \
  tests/route_d_plus/test_train_dplus0.py \
  tests/route_d_plus/test_vmc.py \
  -q
"${repo_root}/.venv/bin/python" -u \
  -m route_d_plus.extend_phase6_measurement \
  --repo-root "${repo_root}" \
  --attempt "${ROUTE_D_PLUS_PHASE6_ATTEMPT}" \
  --output "${run_dir}/phase6-measurement-certificate.json" \
  --workers "${SLURM_CPUS_PER_TASK}"
test -z "$(cd "${repo_root}" && git status --porcelain)"
echo "PHASE6_MEASUREMENT_EXTENSION=passed"
