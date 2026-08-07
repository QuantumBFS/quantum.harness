#!/usr/bin/env bash
#SBATCH --job-name=rdp6-freeze-v2
#SBATCH --partition=xhhgnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --gres=gpu:1
#SBATCH --time=00:25:00

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the absolute remote repository root}"
: "${ROUTE_D_PLUS_FINAL_RUN_DIR:?set the Phase 6 v2 final run directory}"
: "${ROUTE_D_PLUS_PHASE6_ATTEMPT:?set the input Phase 6 attempt}"
: "${ROUTE_D_PLUS_MEASUREMENT_CERTIFICATE:?set the measurement certificate}"
: "${ROUTE_D_PLUS_PHASE6A_CERTIFICATE:?set the Phase 6A certificate}"
: "${ROUTE_D_PLUS_TRAINING_JOB_ID:?set the training attempt job id}"
: "${ROUTE_D_PLUS_TRAINING_STDOUT:?set the training stdout path}"
: "${ROUTE_D_PLUS_TRAINING_STDERR:?set the training stderr path}"
: "${ROUTE_D_PLUS_ATTEMPT_READBACK_JOB_ID:?set the attempt readback job id}"
: "${ROUTE_D_PLUS_ATTEMPT_READBACK_STDOUT:?set readback stdout path}"
: "${ROUTE_D_PLUS_ATTEMPT_READBACK_STDERR:?set readback stderr path}"
: "${ROUTE_D_PLUS_MEASUREMENT_JOB_ID:?set the measurement job id}"
: "${ROUTE_D_PLUS_MEASUREMENT_STDOUT:?set measurement stdout path}"
: "${ROUTE_D_PLUS_MEASUREMENT_STDERR:?set measurement stderr path}"
: "${ROUTE_D_PLUS_PHASE7_RUN_ID:?set the pre-registered Phase 7 run id}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
run_dir="$(cd -- "${ROUTE_D_PLUS_FINAL_RUN_DIR}" && pwd)"
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

sacct_format="JobID,JobName,Cluster,Partition,State,ExitCode,Elapsed,NodeList,AllocCPUS,ReqMem,AllocTRES%100"
training_sacct="${run_dir}/training-sacct-${ROUTE_D_PLUS_TRAINING_JOB_ID}.txt"
attempt_readback_sacct="${run_dir}/attempt-readback-sacct-${ROUTE_D_PLUS_ATTEMPT_READBACK_JOB_ID}.txt"
measurement_sacct="${run_dir}/measurement-sacct-${ROUTE_D_PLUS_MEASUREMENT_JOB_ID}.txt"
sacct -j "${ROUTE_D_PLUS_TRAINING_JOB_ID}" \
  --format="${sacct_format}" -P > "${training_sacct}"
sacct -j "${ROUTE_D_PLUS_ATTEMPT_READBACK_JOB_ID}" \
  --format="${sacct_format}" -P > "${attempt_readback_sacct}"
sacct -j "${ROUTE_D_PLUS_MEASUREMENT_JOB_ID}" \
  --format="${sacct_format}" -P > "${measurement_sacct}"

cd "${repo_root}/tracks/qmc/solutions/BOTS-848"
"${repo_root}/.venv/bin/python" -m ruff check \
  route_d_plus/finalize_phase6_v2.py \
  route_d_plus/prepare_phase7.py \
  tests/route_d_plus/test_phase6_final_v2_contract.py \
  tests/route_d_plus/test_phase7_registration_contract.py
"${repo_root}/.venv/bin/python" -m pytest \
  tests/route_d_plus/test_phase6_final_v2_contract.py \
  tests/route_d_plus/test_phase7_registration_contract.py -q
"${repo_root}/.venv/bin/python" -u \
  -m route_d_plus.finalize_phase6_v2 finalize \
  --repo-root "${repo_root}" \
  --attempt "${ROUTE_D_PLUS_PHASE6_ATTEMPT}" \
  --measurement "${ROUTE_D_PLUS_MEASUREMENT_CERTIFICATE}" \
  --phase6a "${ROUTE_D_PLUS_PHASE6A_CERTIFICATE}" \
  --training-job-id "${ROUTE_D_PLUS_TRAINING_JOB_ID}" \
  --training-state FAILED \
  --training-exit-code 1:0 \
  --training-stdout "${ROUTE_D_PLUS_TRAINING_STDOUT}" \
  --training-stderr "${ROUTE_D_PLUS_TRAINING_STDERR}" \
  --training-sacct "${training_sacct}" \
  --attempt-readback-job-id "${ROUTE_D_PLUS_ATTEMPT_READBACK_JOB_ID}" \
  --attempt-readback-state COMPLETED \
  --attempt-readback-exit-code 0:0 \
  --attempt-readback-stdout "${ROUTE_D_PLUS_ATTEMPT_READBACK_STDOUT}" \
  --attempt-readback-stderr "${ROUTE_D_PLUS_ATTEMPT_READBACK_STDERR}" \
  --attempt-readback-sacct "${attempt_readback_sacct}" \
  --measurement-job-id "${ROUTE_D_PLUS_MEASUREMENT_JOB_ID}" \
  --measurement-state COMPLETED \
  --measurement-exit-code 0:0 \
  --measurement-stdout "${ROUTE_D_PLUS_MEASUREMENT_STDOUT}" \
  --measurement-stderr "${ROUTE_D_PLUS_MEASUREMENT_STDERR}" \
  --measurement-sacct "${measurement_sacct}" \
  --output "${run_dir}/phase6-final-v2-certificate.json"
"${repo_root}/.venv/bin/python" -u \
  -m route_d_plus.finalize_phase6_v2 verify \
  --repo-root "${repo_root}" \
  --final "${run_dir}/phase6-final-v2-certificate.json" \
  --output "${run_dir}/phase6-final-v2-readback.json"
phase7_root="${repo_root}/tracks/qmc/results/${ROUTE_D_PLUS_PHASE7_RUN_ID}"
"${repo_root}/.venv/bin/python" -u -m route_d_plus.prepare_phase7 \
  --repo-root "${repo_root}" \
  --phase6-final "${run_dir}/phase6-final-v2-certificate.json" \
  --run-id "${ROUTE_D_PLUS_PHASE7_RUN_ID}" \
  --run-root "${phase7_root}" \
  --output-dir "${phase7_root}/_dispatch" \
  --output "${phase7_root}/_dispatch/phase7-registration.json"
test -z "$(cd "${repo_root}" && git status --porcelain)"
echo "PHASE6_FROZEN_GATE_V2=passed"
