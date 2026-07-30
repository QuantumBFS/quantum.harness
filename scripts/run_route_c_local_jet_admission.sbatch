#!/usr/bin/env bash
#SBATCH --job-name=qmc-c-local-jet
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=00:20:00
#SBATCH --output=results/route-c-local-jet-admission/slurm-%j.out
#SBATCH --error=results/route-c-local-jet-admission/slurm-%j.err

set -euo pipefail

mkdir -p results/route-c-local-jet-admission
export PYTHONPATH="$PWD/tracks/qmc/solutions/BOTS-848"
export JAX_PLATFORM_NAME=cpu
export JAX_ENABLE_X64=True
export OMP_NUM_THREADS=32
export OPENBLAS_NUM_THREADS=32
export MKL_NUM_THREADS=32
export XLA_FLAGS="--xla_disable_hlo_passes=constant_folding --xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=32"

.venv/bin/python -u -m scalable_v1.routes.cf_operator_nqs.microbenchmark \
  --n-electrons 6 \
  --batch-size 512 \
  --platform cpu \
  --warmups 2 \
  --repetitions 5 \
  --output results/route-c-local-jet-admission/action-microbenchmark.json
