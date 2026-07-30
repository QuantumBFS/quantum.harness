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
#SBATCH --array=0-4%5
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8
validate_scheduler dzagnormal giggleliu user_jiangweiqi
[[ "$#" -ge 5 ]] || die "PROFILE PROFILE_SHA DEPLOYMENT_RECEIPT RESULTS_ROOT IDENTITY_MAP and coordinate arguments required"
PROFILE="$1"; PROFILE_SHA="$2"; DEPLOYMENT_RECEIPT="$3"; RESULTS_ROOT="$4"; IDENTITY_MAP="$5"; shift 5
validate_profile_root "$PROFILE" "$PROFILE_SHA" "$RESULTS_ROOT"
INTERPRETER="$(resolve_interpreter "$DEPLOYMENT_RECEIPT" "$PROFILE_SHA")"
TASK="$(resolve_array_task "$INTERPRETER" "$IDENTITY_MAP" coordinate 5)"
SEED="$(jq -er '.seed' <<<"$TASK")"; RANK="$(jq -er '.rank' <<<"$TASK")"
INPUT_SHA="$(jq -er '.input_sha256' <<<"$TASK")"
INPUT="$(jq -er '.input_path_identity' <<<"$TASK")"
[[ -f "$INPUT" && "$(jq -er '.payload_sha256' "$INPUT")" == "$INPUT_SHA" ]] ||
  die "identity-map coordinate input hash mismatch"
SCRATCH="$(guarded_scratch "$RESULTS_ROOT")"; trap 'rm -rf -- "$SCRATCH"' EXIT
[[ "${SOURCE_MANIFEST:-}" = /* && "${RUNTIME_SET:-}" = /* ]] || die "verified source/runtime paths required"
"$INTERPRETER" -m challenge15.cli verify-execution-inputs \
  --source-manifest "$SOURCE_MANIFEST" --runtime-set "$RUNTIME_SET" \
  --role coordinate --controller qdeshell
"$INTERPRETER" -m challenge15.cli coordinate-shard "$@" \
  --generation "$INPUT" --destination "$RESULTS_ROOT/coordinate/rank=$RANK/seed=$SEED"
