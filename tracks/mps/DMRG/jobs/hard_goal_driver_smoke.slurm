#!/bin/bash
#SBATCH --job-name=hg3d-driver-smoke
#SBATCH --output=slurm-%j.out

set -euo pipefail
umask 077

set +u
source "${HARNESS_SYSTEM_PROFILE:-/etc/profile}"
set -u
module load apptainer/1.2.4

readonly TRACK_ROOT="${SLURM_SUBMIT_DIR:?}/tracks/mps/DMRG"
readonly SIF="${HG3D_SIF:-$HOME/scratch/containers/python-3.12.11-slim-bookworm.sif}"
readonly VENV="${HG3D_VENV:-$HOME/scratch/hg3d-venv-v1}"
readonly PYTHON="$VENV/bin/python"
readonly RUN_ID="stage6-backend-smoke-${SLURM_JOB_ID:?}"
readonly OUTPUT="${SLURM_SUBMIT_DIR:?}/results/hard_goal/$RUN_ID"
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
readonly SCRIPT_SHA256="$(sha256sum "${BASH_SOURCE[0]}" | awk '{print $1}')"

echo "smoke phase=start node=$(hostname) output=$OUTPUT"
echo "smoke phase=environment apptainer=$(apptainer --version)"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

export SIF_SHA256="$actual_sif_sha256"
export FREEZE_SHA256="$actual_freeze_sha256"
export REQUIREMENTS_SHA256="$actual_requirements_sha256"
export SCRIPT_SHA256

apptainer exec --nv \
  --bind "${SLURM_SUBMIT_DIR:?}:${SLURM_SUBMIT_DIR:?}" \
  --pwd "$TRACK_ROOT" \
  --env "PYTHONPATH=$TRACK_ROOT/src" \
  --env PYTHONNOUSERSITE=1 \
  --env JAX_PLATFORM_NAME=gpu \
  --env JAX_ENABLE_X64=true \
  --env XLA_PYTHON_CLIENT_PREALLOCATE=false \
  "$SIF" "$PYTHON" - "$OUTPUT/manifest.json" <<'PY'
from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time

import jax

from spinglass3d.backend import BackendCase, checkpoint_nbytes
from spinglass3d.jax_backend import JaxBatchedBackend


output = Path(sys.argv[1])
devices = jax.devices()
device_platforms = [device.platform for device in devices]
if jax.default_backend() != "gpu" or not devices or any(
    item != "gpu" for item in device_platforms
):
    raise RuntimeError(
        f"GPU required; backend={jax.default_backend()} devices={devices!r}"
    )
if not bool(jax.config.jax_enable_x64):
    raise RuntimeError("JAX float64 mode is required")

case = BackendCase.random(
    length=12,
    temperatures=8,
    samples=1,
    walkers=2,
    seed=2026072901,
)
backend = JaxBatchedBackend(case)
compile_started = time.perf_counter()
backend.sweeps(1)
compile_wall_seconds = time.perf_counter() - compile_started
compile_seconds = backend.compile_seconds

backend.accepted_changes = 0
backend.proposed_changes = 0
warm_started = time.perf_counter()
backend.sweeps(2)
warm_elapsed_seconds = time.perf_counter() - warm_started
resources = backend.resource_snapshot()
checkpoint = backend.checkpoint_state()

manifest = {
    "schema_version": 1,
    "classification": "PASS",
    "scope": "stage6-backend-smoke-only",
    "job": {
        "job_id": os.environ["SLURM_JOB_ID"],
        "node": platform.node(),
    },
    "runtime": {
        "python": platform.python_version(),
        "jax": importlib.metadata.version("jax"),
        "jaxlib": importlib.metadata.version("jaxlib"),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "default_backend": jax.default_backend(),
        "devices": [str(device) for device in devices],
        "device_platforms": device_platforms,
        "x64_enabled": bool(jax.config.jax_enable_x64),
    },
    "benchmark": {
        "length": 12,
        "temperatures": 8,
        "samples": 1,
        "walkers": 2,
        "compile_sweeps": 1,
        "measured_sweeps": 2,
        "compile_wall_seconds": compile_wall_seconds,
        "backend_compile_seconds": compile_seconds,
        "warm_elapsed_seconds": warm_elapsed_seconds,
        "warm_spin_proposals_per_second": (
            backend.proposed_changes / warm_elapsed_seconds
        ),
        "accepted_changes_per_second": (
            backend.accepted_changes / warm_elapsed_seconds
        ),
        "checkpoint_bytes": checkpoint_nbytes(checkpoint),
        "peak_host_memory_bytes": int(resources["host_rss_bytes"]),
        "peak_device_memory_bytes": int(resources["device_memory_bytes"]),
    },
    "provenance": {
        "sif_sha256": os.environ["SIF_SHA256"],
        "freeze_sha256": os.environ["FREEZE_SHA256"],
        "requirements_sha256": os.environ["REQUIREMENTS_SHA256"],
        "job_script_sha256": os.environ["SCRIPT_SHA256"],
    },
}
temporary = output.with_name(output.name + ".tmp")
temporary.write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="ascii",
)
temporary.replace(output)
print(
    "smoke phase=benchmark "
    f"backend={manifest['runtime']['default_backend']} "
    f"compile_seconds={compile_wall_seconds:.6g} "
    "warm_proposals_per_second="
    f"{manifest['benchmark']['warm_spin_proposals_per_second']:.6g}",
    flush=True,
)
PY

sha256sum "$OUTPUT/manifest.json" > "$OUTPUT/SHA256SUMS"
sync
echo "smoke phase=complete manifest=$OUTPUT/manifest.json"
