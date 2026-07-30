#!/usr/bin/env bash
#SBATCH --job-name=tcng-vqetape
#SBATCH --account=giggleliu
#SBATCH --partition=xhhgnormal01
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --time=00:30:00
#SBATCH --output=/work/share/giggleliu/vqetape_issue33_20260730/logs/tcng-vqetape-%j.out

set -euo pipefail

run_root=/work/share/giggleliu/vqetape_issue33_20260730
stage_root="$run_root/tcng-baseline-20260730"
env_root="$run_root/env/py312"
overlay_root="$run_root/env/tcng-overlay-py312"
result_root="$run_root/results/tensorcircuit-ng-matched-job${SLURM_JOB_ID}"
reference_json="$stage_root/issue33/outputs/vqetape-gpu-rtx3090-statevector-n10-d4.json"
result_json="$result_root/tensorcircuit-ng-matched-n10-d4.json"
memory_samples="$result_root/gpu-memory-samples.csv"

mkdir -p "$result_root"

module purge
module load nvidia/cuda/12.2

export PYTHONPATH="$overlay_root:$stage_root/issue33/src${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$env_root/lib/python3.12/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH:-}"
export JAX_PLATFORMS=cuda
export JAX_ENABLE_X64=1
export JAX_DEFAULT_MATMUL_PRECISION=highest
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export XLA_PYTHON_CLIENT_ALLOCATOR=platform
export TMPDIR="$run_root/tmp"

python_bin="$env_root/bin/python"
contractor="${TCNG_CONTRACTOR:-omeco}"

printf 'START|%s\n' "$(date --iso-8601=seconds)"
printf 'HOST|%s\n' "$(hostname)"
printf 'SLURM_JOB_ID|%s\n' "$SLURM_JOB_ID"
printf 'CONTRACTOR|%s\n' "$contractor"
"$python_bin" -u -c 'import jax; print("JAX_DEVICES|" + repr(jax.devices()), flush=True)'
"$python_bin" -u -c 'import tensorcircuit, omeco, cotengra; print("TCNG_IMPORT|ok", flush=True)'
nvidia-smi -L | sed 's/^/GPU|/'
nvidia-smi --query-gpu=name,driver_version,memory.total,pci.bus_id \
  --format=csv,noheader > "$result_root/gpu.csv"
"$python_bin" -m pip freeze > "$result_root/pip-freeze.txt"

sample_gpu_memory() {
  while true; do
    timestamp=$(date +%s.%N)
    used=$(nvidia-smi \
      --query-compute-apps=used_memory \
      --format=csv,noheader,nounits 2>/dev/null \
      | awk 'NF {sum += $1} END {print sum + 0}')
    printf '%s,%s\n' "$timestamp" "$used"
    sleep 0.1
  done
}

sample_gpu_memory > "$memory_samples" &
sampler_pid=$!
cleanup_sampler() {
  kill "$sampler_pid" 2>/dev/null || true
  wait "$sampler_pid" 2>/dev/null || true
}
trap cleanup_sampler EXIT

"$python_bin" -u -m vqetape.tensorcircuit_baseline_cli \
  --nqubits 10 \
  --depth 4 \
  --dtype complex64 \
  --seed 33 \
  --warm-repeats 5 \
  --expected-steps 100 \
  --contractor "$contractor" \
  --reference "$reference_json" \
  --output "$result_json"

cleanup_sampler
trap - EXIT

"$python_bin" - "$result_json" "$memory_samples" <<'PY'
import json
import os
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
sample_path = Path(sys.argv[2])
peak = 0
for line in sample_path.read_text(encoding="utf-8").splitlines():
    if not line:
        continue
    _, used = line.split(",", 1)
    peak = max(peak, int(used))
payload = json.loads(report_path.read_text(encoding="utf-8"))
payload["memory"]["nvml_job_peak_mib"] = peak
temporary = report_path.with_suffix(report_path.suffix + ".tmp")
temporary.write_text(
    json.dumps(payload, indent=2, allow_nan=False),
    encoding="utf-8",
)
os.replace(temporary, report_path)
PY

awk -F, 'BEGIN {max = 0} $2 + 0 > max {max = $2 + 0} END {print max}' \
  "$memory_samples" > "$result_root/nvml-peak-used-mib.txt"
sha256sum "$result_root"/* > "$result_root/SHA256SUMS"
printf 'RESULT_ROOT|%s\n' "$result_root"
printf 'END|%s\n' "$(date --iso-8601=seconds)"
