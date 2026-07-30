#!/usr/bin/env bash
#SBATCH --job-name=anderson-block2
#SBATCH --output=anderson-block2-%j.out

# Resource directives are intentionally supplied at submission time so this
# wrapper remains valid across Slurm clusters and partitions.

set -euo pipefail

cluster_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
solution_dir="$(cd "$cluster_dir/.." && pwd)"
python_bin="${PYTHON_BIN:-$solution_dir/.venv/bin/python}"
default_apptainer_image="$HOME/containers/anderson-block2-py312.sif"
if [[ -v APPTAINER_IMAGE ]]; then
  apptainer_image="$APPTAINER_IMAGE"
elif [[ -f "$default_apptainer_image" ]]; then
  apptainer_image="$default_apptainer_image"
else
  apptainer_image=""
fi
apptainer_bin="${APPTAINER_BIN:-/public/software/apps/apptainer/1.2.4/bin/apptainer}"
container_python="${CONTAINER_PYTHON_BIN:-/opt/anderson/.venv/bin/python}"
config_path="${CONFIG_PATH:-$solution_dir/configs/anderson-production.toml}"
run_dir="${RUN_DIR:-$solution_dir/../../../results/issue-119-cluster/anderson-ga}"
target_m="${TARGET_M:-1000}"

if [[ -n "$apptainer_image" && ! -f "$apptainer_image" ]]; then
  echo "missing Apptainer image: $apptainer_image" >&2
  exit 2
fi
if [[ -n "$apptainer_image" && "$apptainer_bin" == */* && ! -x "$apptainer_bin" ]]; then
  echo "missing Apptainer executable: $apptainer_bin" >&2
  exit 2
fi
if [[ -n "$apptainer_image" && "$apptainer_bin" != */* ]] && ! command -v "$apptainer_bin" >/dev/null 2>&1; then
  echo "missing Apptainer command: $apptainer_bin" >&2
  exit 2
fi
if [[ -z "$apptainer_image" && ! -x "$python_bin" ]]; then
  echo "missing Python environment: $python_bin" >&2
  echo "prepare it on the login node with uv, or set APPTAINER_IMAGE" >&2
  exit 2
fi
if [[ ! -f "$config_path" ]]; then
  echo "missing DMRG config: $config_path" >&2
  exit 2
fi

mkdir -p "$run_dir"
cd "$solution_dir"

echo "Anderson block2 Slurm entrypoint"
echo "  config:   $config_path"
echo "  run dir:  $run_dir"
echo "  target M: $target_m"
echo "  job id:   ${SLURM_JOB_ID:-unset}"
echo "  CPUs:     ${SLURM_CPUS_PER_TASK:-unset}"
echo "  memory:   ${SLURM_MEM_PER_NODE:-${SLURM_MEM_PER_CPU:-unset}}"
if [[ -n "$apptainer_image" ]]; then
  echo "  runtime:  Apptainer ($apptainer_image)"
else
  echo "  runtime:  native ($python_bin)"
fi

arguments=(
  -u -m src.cluster_entrypoint
  --config "$config_path"
  --run-dir "$run_dir"
  --target-m "$target_m"
)
if [[ "${PREFLIGHT_ONLY:-0}" == "1" ]]; then
  arguments+=(--preflight-only)
fi

if [[ -n "$apptainer_image" ]]; then
  exec "$apptainer_bin" exec \
    --cleanenv \
    --bind "$solution_dir:$solution_dir" \
    --bind "$run_dir:$run_dir" \
    --pwd "$solution_dir" \
    --env "SLURM_JOB_ID=${SLURM_JOB_ID:-}" \
    --env "SLURM_CPUS_PER_TASK=${SLURM_CPUS_PER_TASK:-1}" \
    --env "SLURM_MEM_PER_NODE=${SLURM_MEM_PER_NODE:-}" \
    --env "SLURM_MEM_PER_CPU=${SLURM_MEM_PER_CPU:-}" \
    --env "OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1}" \
    --env "OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1}" \
    "$apptainer_image" \
    "$container_python" "${arguments[@]}"
fi

exec "$python_bin" "${arguments[@]}"
