#!/usr/bin/env bash
#SBATCH --partition=dzagnormal
#SBATCH --account=giggleliu
#SBATCH --qos=user_jiangweiqi
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --gres=gpu:NVIDIAA80080GBPCIeLC:8
#SBATCH --mem=480000M
#SBATCH --time=24:00:00
set -euo pipefail

die() {
  printf '%s\n' "$*" >&2
  exit 2
}

[[ $# -eq 1 ]] || die "usage: batch-script ABSOLUTE_MANIFEST"
MANIFEST=$1
[[ "$MANIFEST" = /* && -f "$MANIFEST" && ! -L "$MANIFEST" ]] ||
  die "manifest must be an absolute regular file"
[[ "${SLURM_JOB_ID:-}" ]] || die "Slurm job ID is required"
[[ "${SLURM_JOB_PARTITION:-}" == "dzagnormal" ]] || die "partition mismatch"
[[ "${SLURM_JOB_ACCOUNT:-}" == "giggleliu" ]] || die "account mismatch"
[[ "${SLURM_JOB_QOS:-}" == "user_jiangweiqi" ]] || die "QOS mismatch"
[[ -z "${SLURM_CPUS_PER_TASK:-}" || "$SLURM_CPUS_PER_TASK" == "64" ]] ||
  die "CPU resource mismatch"

BOOTSTRAP_PYTHON=${CHALLENGE15_PYTHON:-/work/share/giggleliu/jiangweiqi/challenge15/runtime/cuda12-591e5bc/python}
[[ "$BOOTSTRAP_PYTHON" = /* && -x "$BOOTSTRAP_PYTHON" && ! -L "$BOOTSTRAP_PYTHON" ]] ||
  die "portable bootstrap interpreter is unavailable"
INTERPRETER=$("$BOOTSTRAP_PYTHON" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["payload"]["runtime"]["interpreter"])' \
  "$MANIFEST") ||
  die "cannot read portable interpreter path"
INTERPRETER_SHA=$("$BOOTSTRAP_PYTHON" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["payload"]["runtime"]["interpreter_sha256"])' \
  "$MANIFEST") ||
  die "cannot read portable interpreter SHA256"
[[ "$INTERPRETER" = /* && -f "$INTERPRETER" && ! -L "$INTERPRETER" ]] ||
  die "portable interpreter must be an absolute regular file"
[[ "$(sha256sum -- "$INTERPRETER" | awk '{print $1}')" == "$INTERPRETER_SHA" ]] ||
  die "portable interpreter SHA256 mismatch"

BATCH=$(realpath -e -- "$0")
[[ ! -L "$0" ]] || die "batch script symlinks are forbidden"
RUNNER=$(python3 -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["payload"]["runner"]["path"])' \
  "$MANIFEST") ||
  die "cannot read task runner path"
[[ "$RUNNER" = /* && -f "$RUNNER" && ! -L "$RUNNER" ]] ||
  die "task runner must be an absolute regular file"

RUN_DIR=$(dirname -- "$MANIFEST")
LOG_DIR="$RUN_DIR/logs"
[[ ! -L "$LOG_DIR" && ( ! -e "$LOG_DIR" || -d "$LOG_DIR" ) ]] ||
  die "seed log path must be a real directory"
mkdir -p -m 700 -- "$LOG_DIR"

export OMP_NUM_THREADS=12
export MKL_NUM_THREADS=12
export OPENBLAS_NUM_THREADS=12
export NUMEXPR_NUM_THREADS=12

pids=()
for task_id in 0 1 2 3 4; do
  CUDA_VISIBLE_DEVICES="$task_id" \
    "$INTERPRETER" "$RUNNER" "$MANIFEST" "$task_id" "$BATCH" \
    >"$LOG_DIR/seed-$task_id.log" 2>&1 &
  pids+=("$!")
done

status=0
set +e
for pid in "${pids[@]}"; do
  wait "$pid"
  runner_status=$?
  if (( runner_status != 0 && status == 0 )); then
    status=$runner_status
  fi
done
set -e
exit "$status"
