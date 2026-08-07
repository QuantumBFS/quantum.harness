#!/bin/bash
#SBATCH --job-name=hg3d-pt-smoke
#SBATCH --output=slurm-%j.out

set -euo pipefail
umask 077

set +u
source "${HARNESS_SYSTEM_PROFILE:-/etc/profile}"
set -u
module load apptainer/1.2.4

readonly REPO_ROOT="${SLURM_SUBMIT_DIR:?}"
readonly TRACK_ROOT="$REPO_ROOT/tracks/mps/DMRG"
readonly SIF="${HG3D_SIF:-$HOME/scratch/containers/python-3.12.11-slim-bookworm.sif}"
readonly VENV="${HG3D_VENV:-$HOME/scratch/hg3d-venv-v1}"
readonly PYTHON="$VENV/bin/python"
readonly RUN_ID="stage6-pt-backend-smoke-${SLURM_JOB_ID:?}"
readonly OUTPUT="$REPO_ROOT/results/hard_goal/$RUN_ID"
readonly EXPECTED_SIF_SHA256="59ebde5239057c558b86ef30ae12f6ffc7a8280e3244120f2dfd6397fa578b6c"
readonly EXPECTED_FREEZE_SHA256="61f20c075caf592265e925aa297e7bb23bc1768d625a5781d479d139defcebca"
readonly EXPECTED_REQUIREMENTS_SHA256="614dac1c70184b8ddb4a7e9dc50ebd2d6b4399a5a038c43bced5de81b04266f3"

[[ -f "$SIF" ]] || { echo "missing SIF: $SIF" >&2; exit 2; }
[[ -L "$PYTHON" ]] || { echo "missing container venv Python link: $PYTHON" >&2; exit 2; }
[[ -f "$VENV.freeze.txt" ]] || { echo "missing freeze: $VENV.freeze.txt" >&2; exit 2; }
[[ ! -e "$OUTPUT" ]] || { echo "refusing overwrite: $OUTPUT" >&2; exit 2; }

actual_sif_sha256="$(sha256sum "$SIF" | awk '{print $1}')"
actual_freeze_sha256="$(sha256sum "$VENV.freeze.txt" | awk '{print $1}')"
actual_requirements_sha256="$(sha256sum "$TRACK_ROOT/containers/hg3d-a800-requirements.txt" | awk '{print $1}')"
[[ "$actual_sif_sha256" == "$EXPECTED_SIF_SHA256" ]] || { echo "SIF hash mismatch" >&2; exit 2; }
[[ "$actual_freeze_sha256" == "$EXPECTED_FREEZE_SHA256" ]] || { echo "freeze hash mismatch" >&2; exit 2; }
[[ "$actual_requirements_sha256" == "$EXPECTED_REQUIREMENTS_SHA256" ]] || { echo "requirements hash mismatch" >&2; exit 2; }

mkdir -p "$OUTPUT"
echo "PT smoke phase=start node=$(hostname) output=$OUTPUT"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

apptainer exec --nv \
  --bind "$REPO_ROOT:$REPO_ROOT" \
  --pwd "$TRACK_ROOT" \
  --env "PYTHONPATH=$TRACK_ROOT/src" \
  --env PYTHONNOUSERSITE=1 \
  --env JAX_PLATFORM_NAME=gpu \
  --env JAX_ENABLE_X64=true \
  --env XLA_PYTHON_CLIENT_PREALLOCATE=false \
  "$SIF" "$PYTHON" -u scripts/hard_goal_pt_smoke.py \
    --length 12 \
    --temperatures 48 \
    --chain-pairs 4 \
    --warmup-sweeps 1 \
    --sweeps 8 \
    --seed 2026073193 \
    --require-platform gpu \
    --output "$OUTPUT/manifest.json"

sha256sum "$OUTPUT/manifest.json" > "$OUTPUT/SHA256SUMS"
sync
echo "PT smoke phase=complete manifest=$OUTPUT/manifest.json"
