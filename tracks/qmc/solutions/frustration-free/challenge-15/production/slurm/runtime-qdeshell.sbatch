#!/usr/bin/env bash
#SBATCH --partition=dzagnormal
#SBATCH --account=giggleliu
#SBATCH --qos=user_jiangweiqi
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:NVIDIAA80080GBPCIeLC:1
#SBATCH --mem=60000M
#SBATCH --time=24:00:00
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8
validate_scheduler dzagnormal giggleliu user_jiangweiqi
[[ "$#" -ge 2 ]] || die "PROFILE_SHA DEPLOYMENT_RECEIPT and runtime-attest arguments required"
PROFILE_SHA="$1"; DEPLOYMENT_RECEIPT="$2"; shift 2
INTERPRETER="$(resolve_interpreter "$DEPLOYMENT_RECEIPT" "$PROFILE_SHA")"
"$INTERPRETER" -m challenge15.cli runtime-attest "$@"
