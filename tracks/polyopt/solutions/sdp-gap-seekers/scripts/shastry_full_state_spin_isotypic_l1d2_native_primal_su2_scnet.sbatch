#!/usr/bin/env bash
#SBATCH --job-name=ss-l1-primal-su2
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=32000M
#SBATCH --time=01:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/scnet-ss-l1-native-primal-su2-%j.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export SS_MOSEK_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export SS_MOSEK_TIME_LIMIT_SECONDS=2400
export SS_MOSEK_LOG_LEVEL=2
export SS_AUDIT_TOLERANCE=1e-9
export SHASTRY_STREAM_ROW_BATCH="${SLURM_CPUS_PER_TASK:-32}"
export SHASTRY_NATIVE_FINGERPRINT=1
export SHASTRY_SU2_RANK4_REDUCTION=1

readonly EXPECTED_ROOT="${SS_EXPECTED_ROOT:-$HOME/quantum-hackson/checkouts/ss-remote-su2-audit}"
readonly EXPECTED_COMMIT="${SS_EXPECTED_COMMIT:?SS_EXPECTED_COMMIT is required}"
readonly EXPECTED_HASH="7308c57ba6b515501fd1c0c00f753868c0bb8cb32531429398fd902b4d63231a"
readonly JULIA_ROOT="$HOME/quantum-hackson/toolchains/julia-1.11.5"
readonly JULIA_BIN="$JULIA_ROOT/bin/julia"
readonly JULIA_PROJECT="$HOME/quantum-hackson/envs/ss-full-state"
readonly MOSEK_LICENSE="$HOME/quantum-hackson/licenses/mosek.lic"
readonly OUTPUT_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-spin-isotypic-l1d2-g0p8-gamma2-native-primal-su2-scnet-${SLURM_JOB_ID}"

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
[[ "$PWD" == "$EXPECTED_ROOT" ]] || {
    echo "unexpected checkout: $PWD" >&2
    exit 2
}
[[ "$(git rev-parse HEAD)" == "$EXPECTED_COMMIT" ]] || {
    echo "unexpected commit: $(git rev-parse HEAD)" >&2
    exit 2
}
[[ -z "$(git status --porcelain)" ]] || {
    echo "refusing dirty checkout" >&2
    exit 2
}
[[ ! -e "$OUTPUT_DIR" ]] || {
    echo "output directory already exists: $OUTPUT_DIR" >&2
    exit 2
}
export SS_EXPECTED_COEFFICIENT_MAP_SHA256="$EXPECTED_HASH"

export LD_LIBRARY_PATH="$JULIA_ROOT/lib/julia:${LD_LIBRARY_PATH:-}"
export MOSEKLM_LICENSE_FILE="$MOSEK_LICENSE"

printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'expected_hash=%s\n' "$EXPECTED_HASH"
printf 'host=%s cpus=%s start=%s\n' \
    "$(hostname)" \
    "${SLURM_CPUS_PER_TASK:-unknown}" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

/usr/bin/time -v -o "${OUTPUT_DIR}.process-time.txt" \
    "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spin_isotypic_mof.jl \
    --coupling 4/5 \
    --gamma 2 \
    --patch-level 1 \
    --mode native \
    --output "$OUTPUT_DIR"

printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
