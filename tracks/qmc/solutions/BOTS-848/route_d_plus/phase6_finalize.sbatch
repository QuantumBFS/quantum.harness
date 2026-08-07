#!/usr/bin/env bash
#SBATCH --job-name=rdp6-freeze
#SBATCH --partition=xhhgnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --gres=gpu:1
#SBATCH --time=00:20:00

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the absolute remote repository root}"
: "${ROUTE_D_PLUS_RUN_DIR:?set the completed Phase 6 run directory}"
: "${ROUTE_D_PLUS_TRAINING_JOB_ID:?set the completed training job id}"
: "${ROUTE_D_PLUS_TRAINING_STDOUT:?set the training stdout path}"
: "${ROUTE_D_PLUS_TRAINING_STDERR:?set the training stderr path}"
: "${ROUTE_D_PLUS_PHASE6A_CERTIFICATE:?set the Phase 6A certificate path}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
run_dir="$(cd -- "${ROUTE_D_PLUS_RUN_DIR}" && pwd)"
test -z "$(cd "${repo_root}" && git status --porcelain)"

runtime_compat="/work/home/jiabohan5/.cache/route-d-plus/runtime-libs"
nvidia_root="${repo_root}/.venv/lib/python3.11/site-packages/nvidia"
cuda_library_path="${runtime_compat}"
for component in \
  cuda_cupti cufft cudnn cusolver nvjitlink nccl cuda_runtime cublas cusparse
do
  cuda_library_path="${cuda_library_path}:${nvidia_root}/${component}/lib"
done
export LD_LIBRARY_PATH="${cuda_library_path}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export JAX_ENABLE_X64=true

sacct_path="${run_dir}/training-sacct-${ROUTE_D_PLUS_TRAINING_JOB_ID}.txt"
sacct -j "${ROUTE_D_PLUS_TRAINING_JOB_ID}" \
  --format=JobID,JobName,Cluster,Partition,State,ExitCode,Elapsed,NodeList,AllocCPUS,ReqMem,AllocTRES%100 \
  -P > "${sacct_path}"

cd "${repo_root}/tracks/qmc/solutions/BOTS-848"
"${repo_root}/.venv/bin/python" -u -m route_d_plus.finalize_phase6 finalize \
  --repo-root "${repo_root}" \
  --phase6 "${run_dir}/phase6-certificate.json" \
  --phase6a "${ROUTE_D_PLUS_PHASE6A_CERTIFICATE}" \
  --stdout "${ROUTE_D_PLUS_TRAINING_STDOUT}" \
  --stderr "${ROUTE_D_PLUS_TRAINING_STDERR}" \
  --sacct "${sacct_path}" \
  --output "${run_dir}/phase6-final-certificate.json"
"${repo_root}/.venv/bin/python" -u -m route_d_plus.finalize_phase6 verify \
  --repo-root "${repo_root}" \
  --final "${run_dir}/phase6-final-certificate.json" \
  --output "${run_dir}/phase6-final-readback.json"
test -z "$(cd "${repo_root}" && git status --porcelain)"
echo "PHASE6_FROZEN_GATE=passed"
