#!/usr/bin/env bash
#SBATCH --partition=ihicnormal
#SBATCH --account=chenkun2025
#SBATCH --qos=user_student090
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=80000M
#SBATCH --time=24:00:00
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
export OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 OPENBLAS_NUM_THREADS=24 NUMEXPR_NUM_THREADS=24
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=24"
validate_scheduler ihicnormal chenkun2025 user_student090
[[ "$#" -ge 2 ]] || die "PROFILE_SHA DEPLOYMENT_RECEIPT and runtime-attest arguments required"
PROFILE_SHA="$1"; DEPLOYMENT_RECEIPT="$2"; shift 2
INTERPRETER="$(resolve_interpreter "$DEPLOYMENT_RECEIPT" "$PROFILE_SHA")"
"$INTERPRETER" -m challenge15.cli runtime-attest "$@"
