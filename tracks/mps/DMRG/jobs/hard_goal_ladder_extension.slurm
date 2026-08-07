#!/bin/bash
#SBATCH --job-name=hg3d-ladder-extension
#SBATCH --output=slurm-%A_%a.out

set -euo pipefail
umask 077

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable extension run spec}"
: "${SLURM_ARRAY_TASK_ID:?Slurm must provide SLURM_ARRAY_TASK_ID}"

readonly REQUIRED_PLATFORM="${HARNESS_REQUIRED_PLATFORM:-gpu}"
readonly CHECKPOINT_EVERY="${HARNESS_CHECKPOINT_EVERY:-256}"
readonly RESUME="${HARNESS_RESUME:-0}"
[[ "$REQUIRED_PLATFORM" == "gpu" ]] || { echo "GPU is required" >&2; exit 2; }
[[ "$CHECKPOINT_EVERY" =~ ^[1-9][0-9]*$ ]] || { echo "invalid checkpoint cadence" >&2; exit 2; }
[[ "$RESUME" == "0" || "$RESUME" == "1" ]] || { echo "HARNESS_RESUME must be 0 or 1" >&2; exit 2; }

set +u
source "${HARNESS_SYSTEM_PROFILE:-/etc/profile}"
set -u
module load apptainer/1.2.4

readonly REPO_ROOT="${HARNESS_REPO_ROOT:-${SLURM_SUBMIT_DIR:?Slurm must provide SLURM_SUBMIT_DIR}}"
readonly TRACK_ROOT="$REPO_ROOT/tracks/mps/DMRG"
readonly ENV_ROOT="${HG3D_ENV_ROOT:-$HOME/scratch}"
readonly SIF="${HG3D_SIF:-$ENV_ROOT/containers/python-3.12.11-slim-bookworm.sif}"
readonly VENV="${HG3D_VENV:-$ENV_ROOT/hg3d-venv-v1}"
readonly PYTHON="$VENV/bin/python"
readonly EXPECTED_SIF_SHA256="59ebde5239057c558b86ef30ae12f6ffc7a8280e3244120f2dfd6397fa578b6c"
readonly EXPECTED_FREEZE_SHA256="61f20c075caf592265e925aa297e7bb23bc1768d625a5781d479d139defcebca"
readonly EXPECTED_REQUIREMENTS_SHA256="614dac1c70184b8ddb4a7e9dc50ebd2d6b4399a5a038c43bced5de81b04266f3"

run_spec="$HARNESS_RUN_SPEC"
[[ "$run_spec" = /* ]] || run_spec="$REPO_ROOT/$run_spec"
readonly RUN_SPEC="$run_spec"
[[ -f "$RUN_SPEC" ]] || { echo "missing run spec: $RUN_SPEC" >&2; exit 2; }
[[ -f "$SIF" ]] || { echo "missing SIF: $SIF" >&2; exit 2; }
[[ -L "$PYTHON" ]] || { echo "missing container venv Python link: $PYTHON" >&2; exit 2; }
[[ -f "$VENV.freeze.txt" ]] || { echo "missing freeze: $VENV.freeze.txt" >&2; exit 2; }

[[ "$(sha256sum "$SIF" | awk '{print $1}')" == "$EXPECTED_SIF_SHA256" ]] || { echo "SIF hash mismatch" >&2; exit 2; }
[[ "$(sha256sum "$VENV.freeze.txt" | awk '{print $1}')" == "$EXPECTED_FREEZE_SHA256" ]] || { echo "freeze hash mismatch" >&2; exit 2; }
[[ "$(sha256sum "$TRACK_ROOT/containers/hg3d-a800-requirements.txt" | awk '{print $1}')" == "$EXPECTED_REQUIREMENTS_SHA256" ]] || { echo "requirements hash mismatch" >&2; exit 2; }

command_args=(scripts/hard_goal_ladder_extension_cell.py --run-spec "$RUN_SPEC" --selector "$SLURM_ARRAY_TASK_ID" --require-platform "$REQUIRED_PLATFORM" --checkpoint-every "$CHECKPOINT_EVERY")
[[ "$RESUME" == "0" ]] || command_args+=(--resume)

nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
exec apptainer exec --nv \
  --bind "$REPO_ROOT:$REPO_ROOT" \
  --pwd "$TRACK_ROOT" \
  --env "PYTHONPATH=$TRACK_ROOT/src" \
  --env "HARNESS_REPO_ROOT=$REPO_ROOT" \
  --env PYTHONNOUSERSITE=1 \
  --env PYTHONHASHSEED=0 \
  --env JAX_PLATFORM_NAME=gpu \
  --env JAX_ENABLE_X64=true \
  --env XLA_PYTHON_CLIENT_PREALLOCATE=false \
  "$SIF" "$PYTHON" -u "${command_args[@]}"
