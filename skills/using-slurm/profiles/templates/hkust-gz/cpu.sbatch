#!/bin/bash
#SBATCH --job-name=qmb-cpu
#SBATCH --partition=i64m512u
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=results/%x-%j.out
#
# HKUST-GZ HPC2 — CPU job template (Apptainer container).
# Build the image first with /build-apptainer-image, then:
#   sbatch skills/using-slurm/profiles/templates/hkust-gz/cpu.sbatch path/to/script.jl [args...]
#
# Edit the knobs above for your job. i64m512u = 64-core/512 GB nodes, many idle.
# Mem rule of thumb: DefMemPerCPU=4 GB, MaxMemPerCPU≈31 GB (so --mem ≤ cpus*31 GB).
set -euo pipefail

IMAGE="${QMB_IMAGE:-$HOME/containers/qmb.sif}"        # set QMB_IMAGE or edit
SCRIPT="${1:?usage: sbatch cpu.sbatch <script.jl|.py> [args...]}"; shift || true

[ -f "$IMAGE" ] || { echo "ERROR: image not found: $IMAGE (run /build-apptainer-image)"; exit 1; }
mkdir -p results

module load apptainer-1.4.5
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
echo "host=$(hostname) cpus=${SLURM_CPUS_PER_TASK:-?} image=$IMAGE script=$SCRIPT"

# --cleanenv keeps the host environment from leaking in; --bind/--pwd run the job
# in the current repo dir so results/ lands locally for /cluster-jobs fetch.
srun --unbuffered apptainer exec --cleanenv --bind "$PWD" --pwd "$PWD" "$IMAGE" \
  julia --project=/opt/project -t "$JULIA_NUM_THREADS" "$SCRIPT" "$@"

# Python variant — replace the line above with:
#   srun --unbuffered apptainer exec --cleanenv --bind "$PWD" --pwd "$PWD" "$IMAGE" \
#     python "$SCRIPT" "$@"
