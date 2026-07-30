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
[[ "$#" -ge 5 ]] || die "PROFILE PROFILE_SHA DEPLOYMENT_RECEIPT RESULTS_ROOT IDENTITY_MAP and exact arguments required"
PROFILE="$1"; PROFILE_SHA="$2"; DEPLOYMENT_RECEIPT="$3"; RESULTS_ROOT="$4"; IDENTITY_MAP="$5"; shift 5
validate_profile_root "$PROFILE" "$PROFILE_SHA" "$RESULTS_ROOT"
INTERPRETER="$(resolve_interpreter "$DEPLOYMENT_RECEIPT" "$PROFILE_SHA")"
TASK_COUNT="$("$INTERPRETER" -m challenge15.cli identity-map-count --identity-map "$IDENTITY_MAP")"
ARRAY_SPEC="0-$((TASK_COUNT-1))%1"
[[ "${SLURM_ARRAY_TASK_ID:-0}" -lt "$TASK_COUNT" ]] || die "array index exceeds identity map"
TASK="$(resolve_array_task "$INTERPRETER" "$IDENTITY_MAP" exact 1)"
SEED="$(jq -er '.seed' <<<"$TASK")"; RANK="$(jq -er '.rank' <<<"$TASK")"
INPUT_SHA="$(jq -er '.input_sha256' <<<"$TASK")"
INPUT="$(jq -er '.input_path_identity' <<<"$TASK")"
[[ -f "$INPUT" && "$(jq -er '.payload_sha256' "$INPUT")" == "$INPUT_SHA" ]] ||
  die "identity-map exact input hash mismatch"
SCRATCH="$(guarded_scratch "$RESULTS_ROOT")"; trap 'rm -rf -- "$SCRATCH"' EXIT
[[ "${SOURCE_MANIFEST:-}" = /* && "${RUNTIME_SET:-}" = /* ]] || die "verified source/runtime paths required"
"$INTERPRETER" -m challenge15.cli verify-execution-inputs \
  --source-manifest "$SOURCE_MANIFEST" --runtime-set "$RUNTIME_SET" \
  --role exact --controller lasg02
"$INTERPRETER" -m challenge15.cli exact-shard "$@" \
  --generation "$INPUT" --destination "$RESULTS_ROOT/exact/rank=$RANK/seed=$SEED"
