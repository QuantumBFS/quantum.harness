#!/usr/bin/env bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --gres=gpu:A800:1
#SBATCH --time=04:00:00
set -euo pipefail
cd "$HOME/quantum.harness"
source .venv/bin/activate
export PYTHONPATH="$PWD/tracks/peps/solutions/avi7ii${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OPENBLAS_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export JAX_PLATFORM_NAME=gpu
printf '{"event":"start","host":"%s","kind":"pepo-probe","steps":1}\n' "$(hostname)"
python -u -m qh147.run evolve \
  --config tracks/peps/solutions/avi7ii/configs/pepo-h3-d4.json \
  --run-root tracks/peps/results/issue147-pepo/cells/cell-0002 \
  --compression-mode thermodynamic \
  --stop-after-steps 1
