#!/bin/bash
#SBATCH --job-name=qmb-gpu
#SBATCH --partition=i64m1tga800u
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:a800:1
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=results/%x-%j.out
#
# HKUST-GZ HPC2 — GPU job template (Apptainer container, A800).
# Build a CUDA-enabled image first with /build-apptainer-image, then:
#   sbatch skills/using-slurm/profiles/templates/hkust-gz/gpu.sbatch path/to/script.py [args...]
#
# A800 partition is heavily contended (often 0 idle) — expect a queue wait;
# this is batch, not interactive. For A40 instead: --partition=i64m1tga40u --gres=gpu:a40:1
set -euo pipefail

IMAGE="${QMB_IMAGE:-$HOME/containers/qmb.sif}"        # set QMB_IMAGE or edit
SCRIPT="${1:?usage: sbatch gpu.sbatch <script.py|.jl> [args...]}"; shift || true

[ -f "$IMAGE" ] || { echo "ERROR: image not found: $IMAGE (run /build-apptainer-image)"; exit 1; }
mkdir -p results

module load apptainer-1.4.5
echo "host=$(hostname) gpu=$CUDA_VISIBLE_DEVICES image=$IMAGE script=$SCRIPT"
# --nv exposes the host NVIDIA driver/devices to the container.
srun --unbuffered apptainer exec --nv --cleanenv --bind "$PWD" --pwd "$PWD" "$IMAGE" \
  python "$SCRIPT" "$@"

# Julia+CUDA variant — replace the line above with:
#   srun --unbuffered apptainer exec --nv --cleanenv --bind "$PWD" --pwd "$PWD" "$IMAGE" \
#     julia --project=/opt/project "$SCRIPT" "$@"
