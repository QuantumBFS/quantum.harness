#!/usr/bin/env bash
#SBATCH --job-name=tcng-fig2-smoke
#SBATCH --account=giggleliu
#SBATCH --partition=xhhgnormal01
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --gres=gpu:1
#SBATCH --time=00:30:00
#SBATCH --output=/work/share/giggleliu/vqetape_issue33_20260730/logs/tcng-fig2-smoke-%j.out

# The default partition preserves the same RTX 3090 environment as the
# matched baseline.  A correctness-only smoke may override the partition at
# submission time; the script always records the actual GPU model.

set -euo pipefail

run_root=/work/share/giggleliu/vqetape_issue33_20260730
stage_root="$run_root/tcng-baseline-20260730"
env_root="$run_root/env/py312"
overlay_root="$run_root/env/tcng-overlay-py312"
result_root="$run_root/results/tensorcircuit-ng-fig2-job${SLURM_JOB_ID}"
path_json="$result_root/fig2-path.json"
result_json="$result_root/fig2-run.json"
memory_samples="$result_root/gpu-memory-samples.csv"

# Safe defaults are a correctness smoke test.  A formal attempt must set all
# scale variables explicitly; this prevents an accidental 640-trial path
# search from being submitted while inspecting the script.
nqubits="${TCNG_FIG2_NQUBITS:-6}"
depth="${TCNG_FIG2_DEPTH:-3}"
max_repeats="${TCNG_FIG2_MAX_REPEATS:-16}"
target_size_log2="${TCNG_FIG2_TARGET_SIZE_LOG2:-20}"
warm_repeats="${TCNG_FIG2_WARM_REPEATS:-3}"

for value in \
  "$nqubits" \
  "$depth" \
  "$max_repeats" \
  "$target_size_log2" \
  "$warm_repeats"; do
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    printf 'ERROR|expected a positive integer, got %q\n' "$value" >&2
    exit 2
  fi
done

verify_args=(--verify-direct)
if (( 10#$nqubits > 10 )); then
  verify_args=()
fi

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

printf 'START|%s\n' "$(date --iso-8601=seconds)"
printf 'HOST|%s\n' "$(hostname)"
printf 'SLURM_JOB_ID|%s\n' "$SLURM_JOB_ID"
printf 'PROTOCOL|n=%s|depth=%s|max_repeats=%s|target_log2=%s\n' \
  "$nqubits" "$depth" "$max_repeats" "$target_size_log2"
"$python_bin" -u -c 'import jax; print("JAX_DEVICES|" + repr(jax.devices()), flush=True)'
nvidia-smi --query-gpu=name,driver_version,memory.total,pci.bus_id \
  --format=csv,noheader > "$result_root/gpu.csv"

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

"$python_bin" -u -m vqetape.tensorcircuit_fig2_cli path \
  --nqubits "$nqubits" \
  --depth "$depth" \
  --max-repeats "$max_repeats" \
  --target-size-log2 "$target_size_log2" \
  --parallel 1 \
  --output "$path_json"

"$python_bin" -u -m vqetape.tensorcircuit_fig2_cli run \
  --path "$path_json" \
  --warm-repeats "$warm_repeats" \
  "${verify_args[@]}" \
  --output "$result_json"

cleanup_sampler
trap - EXIT

"$python_bin" - "$result_json" "$memory_samples" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

report_path = Path(sys.argv[1])
sample_path = Path(sys.argv[2])
peak = 0
for line in sample_path.read_text(encoding="utf-8").splitlines():
    if line:
        _, used = line.split(",", 1)
        peak = max(peak, int(used))
payload = json.loads(report_path.read_text(encoding="utf-8"))
payload["memory"]["nvml_job_peak_mib"] = peak
with tempfile.NamedTemporaryFile(
    mode="w",
    encoding="utf-8",
    dir=report_path.parent,
    prefix=f".{report_path.name}.",
    suffix=".tmp",
    delete=False,
) as handle:
    json.dump(payload, handle, indent=2, allow_nan=False)
    handle.write("\n")
    temporary = Path(handle.name)
os.replace(temporary, report_path)
PY

sha256sum "$result_root"/* > "$result_root/SHA256SUMS"
printf 'RESULT_ROOT|%s\n' "$result_root"
printf 'END|%s\n' "$(date --iso-8601=seconds)"
