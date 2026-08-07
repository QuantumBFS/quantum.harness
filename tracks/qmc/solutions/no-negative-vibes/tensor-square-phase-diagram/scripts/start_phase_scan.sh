#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 4 ]]; then
  echo "usage: $0 <wsl|cpu> <workers> <python> <project-dir>" >&2
  exit 2
fi

machine="$1"
workers="$2"
python_executable="$3"
project_dir="$4"
output_dir="${project_dir}/results/stage3_coarse_20260729"
log_path="${output_dir}/run_${machine}.log"
pid_path="${output_dir}/run_${machine}.pid"
mkdir -p "${output_dir}"

nohup env \
  PYTHONPATH="${project_dir}/src" \
  OMP_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 \
  "${python_executable}" \
  "${project_dir}/scripts/run_phase_scan.py" \
  --output-dir "${output_dir}" \
  --machine "${machine}" \
  --workers "${workers}" \
  >"${log_path}" 2>&1 </dev/null &

pid="$!"
printf '%s\n' "${pid}" >"${pid_path}"
echo "started machine=${machine} pid=${pid} log=${log_path}"
